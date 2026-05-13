#!/usr/bin/env python3
"""
Rice-Pro-Max 数据处理流水线
============================
双击运行或直接执行，自动完成全部操作：
  1. 天气小时→日聚合入库
  2. 土壤数据入库
  3. 病虫害监测数据入库
  4. 负值归零清洗

无脑运行:
  python data_pipeline.py            # 自动执行全部步骤

高级用法:
  python data_pipeline.py weather    # 仅天气数据
  python data_pipeline.py soil       # 仅土壤数据
  python data_pipeline.py pest       # 仅病虫害数据
  python data_pipeline.py cleanup    # 仅数据清洗
  python data_pipeline.py all        # 全部步骤(可配参数)
  python data_pipeline.py --dry-run  # 预览不写库
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pymysql

# ── 基础配置 ─────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEATHER_CSV = ROOT / "data" / "weather_hour.csv"
DEFAULT_SOIL_CSV = ROOT / "data" / "soil_data.csv"
DEFAULT_PEST_CSV = ROOT / "data" / "pest_data(病虫害数据).csv"

import json as _json
with open(ROOT.parent / "conf" / "config.json", "r", encoding="utf-8") as _f:
    _cfg = _json.load(_f)
_MYSQL = _cfg["mysql"]

ENV_MYSQL_HOST = _MYSQL["host"]
ENV_MYSQL_PORT = _MYSQL["port"]
ENV_MYSQL_USER = _MYSQL["user"]
ENV_MYSQL_PASSWORD = _MYSQL["password"]
ENV_MYSQL_DATABASE = _MYSQL["database"]

# ── 表结构定义 ───────────────────────────────────────────

WEATHER_HOUR_CSV_COLS = [
    "station_id", "stat_date", "hour",
    "sunshine_duration", "wd02", "wd08", "wd14", "wd20",
    "daily_avg_wind", "daily_precip", "daily_max_temp",
    "daily_min_temp", "daily_avg_temp", "daily_rel_humidity",
    "daily_avg_pressure",
]

SOIL_CSV_COLS = [
    "station_id", "stat_date",
    "soil_om_percent", "soil_ph", "soil_p_ppm", "soil_k_ppm", "soil_ec_ds_m",
]

CREATE_WEATHER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `{table}` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `station_id` VARCHAR(64) NOT NULL COMMENT '站点编号',
  `stat_date` DATE NOT NULL COMMENT '统计日期',
  `sunshine_duration_mean` DOUBLE NULL COMMENT '日照时间均值(小时)',
  `wind_speed_daily_mean` DOUBLE NULL COMMENT '日均平均风速',
  `precipitation_daily` DOUBLE NULL COMMENT '日降水量(小时累计)',
  `temperature_daily_mean` DOUBLE NULL COMMENT '日平均温度',
  `relative_humidity_daily_mean` DOUBLE NULL COMMENT '日平均相对湿度',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_station_date` (`station_id`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='气象小时数据聚合成日';
"""

CREATE_SOIL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `{table}` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `station_id` VARCHAR(64) NOT NULL COMMENT '站点编号',
  `stat_date` DATE NOT NULL COMMENT '观测日期',
  `soil_om_percent` DOUBLE NULL COMMENT '土壤有机质含量(%)',
  `soil_ph` DOUBLE NULL COMMENT '土壤 pH',
  `soil_p_ppm` DOUBLE NULL COMMENT '土壤磷含量(ppm)',
  `soil_k_ppm` DOUBLE NULL COMMENT '土壤钾含量(ppm)',
  `soil_ec_ds_m` DOUBLE NULL COMMENT '土壤电导率(dS/m)',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_station_date` (`station_id`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='土壤日观测';
"""

# ── 数据库连接 ───────────────────────────────────────────

def mysql_connect(database: str = ENV_MYSQL_DATABASE) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=ENV_MYSQL_HOST, port=ENV_MYSQL_PORT,
        user=ENV_MYSQL_USER, password=ENV_MYSQL_PASSWORD,
        database=database, charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )


def ensure_table(conn: pymysql.connections.Connection, create_sql: str, table: str) -> None:
    with conn.cursor() as cur:
        cur.execute(create_sql.format(table=table))
    conn.commit()


# ── CSV 读取 ─────────────────────────────────────────────

def read_weather_hour_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
    if len(df.columns) != len(WEATHER_HOUR_CSV_COLS):
        raise ValueError(f"列数应为 {len(WEATHER_HOUR_CSV_COLS)}，实际为 {len(df.columns)}")
    df.columns = WEATHER_HOUR_CSV_COLS

    numeric_cols = ["sunshine_duration", "daily_avg_wind", "daily_precip",
                    "daily_avg_temp", "daily_rel_humidity"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["stat_date"] = pd.to_datetime(df["stat_date"], errors="coerce")
    if df["stat_date"].isna().any():
        bad = df.loc[df["stat_date"].isna()].head(5)
        raise ValueError(f"存在无法解析的日期行，示例:\n{bad}")
    return df


def read_soil_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
    if len(df.columns) != len(SOIL_CSV_COLS):
        raise ValueError(f"列数应为 {len(SOIL_CSV_COLS)}，实际为 {len(df.columns)}")
    df.columns = SOIL_CSV_COLS

    for c in SOIL_CSV_COLS[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["stat_date"] = pd.to_datetime(df["stat_date"], errors="coerce")
    if df["stat_date"].isna().any():
        bad = df.loc[df["stat_date"].isna()].head(5)
        raise ValueError(f"存在无法解析的日期行，示例:\n{bad}")
    df["stat_date"] = df["stat_date"].dt.normalize()
    return df


# ── 天气聚合 ─────────────────────────────────────────────

def aggregate_weather_daily(df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        df.groupby(["station_id", "stat_date"], as_index=False)
        .agg(
            sunshine_duration_mean=("sunshine_duration", "mean"),
            wind_speed_daily_mean=("daily_avg_wind", "mean"),
            precipitation_daily=("daily_precip", "sum"),
            temperature_daily_mean=("daily_avg_temp", "mean"),
            relative_humidity_daily_mean=("daily_rel_humidity", "mean"),
        )
        .sort_values(["station_id", "stat_date"])
        .reset_index(drop=True)
    )

    for col in ["sunshine_duration_mean", "wind_speed_daily_mean", "precipitation_daily",
                "temperature_daily_mean", "relative_humidity_daily_mean"]:
        daily[col] = daily[col].round(4)

    daily["sunshine_duration_mean"] = daily["sunshine_duration_mean"].clip(lower=0)
    daily["wind_speed_daily_mean"] = daily["wind_speed_daily_mean"].clip(lower=0)
    daily["precipitation_daily"] = daily["precipitation_daily"].clip(lower=0)
    daily["stat_date"] = daily["stat_date"].dt.normalize()
    return daily


# ── 批量写入 ─────────────────────────────────────────────

def upsert_weather(conn: pymysql.connections.Connection, table: str,
                   daily: pd.DataFrame, chunk_size: int) -> int:
    sql = f"""
    INSERT INTO `{table}` (station_id, stat_date,
        sunshine_duration_mean, wind_speed_daily_mean, precipitation_daily,
        temperature_daily_mean, relative_humidity_daily_mean)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        sunshine_duration_mean = VALUES(sunshine_duration_mean),
        wind_speed_daily_mean = VALUES(wind_speed_daily_mean),
        precipitation_daily = VALUES(precipitation_daily),
        temperature_daily_mean = VALUES(temperature_daily_mean),
        relative_humidity_daily_mean = VALUES(relative_humidity_daily_mean)
    """
    return _batch_insert(conn, sql, daily, [
        ("station_id", str),
        ("stat_date", lambda d: d.date() if hasattr(d, "date") else d),
        ("sunshine_duration_mean", _or_none),
        ("wind_speed_daily_mean", _or_none),
        ("precipitation_daily", _or_none),
        ("temperature_daily_mean", _or_none),
        ("relative_humidity_daily_mean", _or_none),
    ], chunk_size)


def upsert_soil(conn: pymysql.connections.Connection, table: str,
                df: pd.DataFrame, chunk_size: int) -> int:
    sql = f"""
    INSERT INTO `{table}` (station_id, stat_date,
        soil_om_percent, soil_ph, soil_p_ppm, soil_k_ppm, soil_ec_ds_m)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        soil_om_percent = VALUES(soil_om_percent),
        soil_ph = VALUES(soil_ph),
        soil_p_ppm = VALUES(soil_p_ppm),
        soil_k_ppm = VALUES(soil_k_ppm),
        soil_ec_ds_m = VALUES(soil_ec_ds_m)
    """
    return _batch_insert(conn, sql, df, [
        ("station_id", str),
        ("stat_date", lambda d: d.date() if hasattr(d, "date") else d),
        ("soil_om_percent", _or_none),
        ("soil_ph", _or_none),
        ("soil_p_ppm", _or_none),
        ("soil_k_ppm", _or_none),
        ("soil_ec_ds_m", _or_none),
    ], chunk_size)


def _or_none(val: Any) -> float | None:
    return float(val) if pd.notna(val) else None


def _batch_insert(conn: pymysql.connections.Connection, sql: str,
                  df: pd.DataFrame, cols: list[tuple[str, Any]],
                  chunk_size: int) -> int:
    rows: list[tuple] = []
    total = 0
    for _, r in df.iterrows():
        rows.append(tuple(fn(r[name]) for name, fn in cols))
        if len(rows) >= chunk_size:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()
            total += len(rows)
            rows = []
    if rows:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
        total += len(rows)
    return total


# ── 病虫害数据导入 ────────────────────────────────────────

PEST_CSV_COLS = [
    "point", "Date", "GrowthPeriod", "GrowthStatus",
    "BacterialLeafBlightRate", "BrownSpotRate", "TungroVirusRate",
    "PestRphNum", "PestScsNum", "PestCmNum",
]

CREATE_PEST_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `{table}` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `point` VARCHAR(64) NOT NULL COMMENT '监测点编号',
  `Date` DATE NOT NULL COMMENT '监测日期',
  `GrowthPeriod` VARCHAR(64) NOT NULL COMMENT '生育期',
  `GrowthStatus` VARCHAR(32) NOT NULL COMMENT '生长状况',
  `BacterialLeafBlightRate` DECIMAL(6,2) NOT NULL COMMENT '白叶枯病发病率',
  `BrownSpotRate` DECIMAL(6,2) NOT NULL COMMENT '褐斑病发病率',
  `TungroVirusRate` DECIMAL(6,2) NOT NULL COMMENT '东格鲁病毒病发病率',
  `PestRphNum` INT NOT NULL COMMENT '稻飞虱数量',
  `PestScsNum` INT NOT NULL COMMENT '二化螟数量',
  `PestCmNum` INT NOT NULL COMMENT '稻纵卷叶螟数量',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_point_date` (`point`, `Date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='病虫害监测数据';
"""


def read_pest_csv(csv_path: Path) -> pd.DataFrame:
    """Read pest monitoring CSV. Header is verbose (Chinese descriptions), we assign our own column names."""
    df = pd.read_csv(csv_path, encoding="utf-8", header=0, low_memory=False)
    if len(df.columns) != len(PEST_CSV_COLS):
        raise ValueError(f"列数应为 {len(PEST_CSV_COLS)}，实际为 {len(df.columns)}")
    df.columns = PEST_CSV_COLS

    # Date format: "2020/1/1" → datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if df["Date"].isna().any():
        bad = df.loc[df["Date"].isna()].head(5)
        raise ValueError(f"存在无法解析的日期行，示例:\n{bad}")
    df["Date"] = df["Date"].dt.normalize()

    # Numeric columns
    for c in PEST_CSV_COLS[4:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df


def upsert_pest(conn: pymysql.connections.Connection, table: str,
                df: pd.DataFrame, chunk_size: int) -> int:
    sql = f"""
    INSERT INTO `{table}` (point, `Date`, GrowthPeriod, GrowthStatus,
        BacterialLeafBlightRate, BrownSpotRate, TungroVirusRate,
        PestRphNum, PestScsNum, PestCmNum)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        GrowthPeriod = VALUES(GrowthPeriod),
        GrowthStatus = VALUES(GrowthStatus),
        BacterialLeafBlightRate = VALUES(BacterialLeafBlightRate),
        BrownSpotRate = VALUES(BrownSpotRate),
        TungroVirusRate = VALUES(TungroVirusRate),
        PestRphNum = VALUES(PestRphNum),
        PestScsNum = VALUES(PestScsNum),
        PestCmNum = VALUES(PestCmNum)
    """
    return _batch_insert(conn, sql, df, [
        ("point", str),
        ("Date", lambda d: d.date() if hasattr(d, "date") else d),
        ("GrowthPeriod", str),
        ("GrowthStatus", str),
        ("BacterialLeafBlightRate", _or_none),
        ("BrownSpotRate", _or_none),
        ("TungroVirusRate", _or_none),
        ("PestRphNum", lambda v: int(float(v)) if pd.notna(v) else 0),
        ("PestScsNum", lambda v: int(float(v)) if pd.notna(v) else 0),
        ("PestCmNum", lambda v: int(float(v)) if pd.notna(v) else 0),
    ], chunk_size)


# ── 数据清洗 ─────────────────────────────────────────────

def cleanup_negative_sunshine(conn: pymysql.connections.Connection, table: str) -> int:
    sql = (f"UPDATE `{table}` SET `sunshine_duration_mean` = 0 "
           f"WHERE `sunshine_duration_mean` IS NOT NULL AND `sunshine_duration_mean` <= 0")
    with conn.cursor() as cur:
        cur.execute(sql)
        n = cur.rowcount
    conn.commit()
    return n


def cleanup_negative_wind_precip(conn: pymysql.connections.Connection, table: str) -> tuple[int, int]:
    sql_wind = (f"UPDATE `{table}` SET `wind_speed_daily_mean` = 0 "
                f"WHERE `wind_speed_daily_mean` IS NOT NULL AND `wind_speed_daily_mean` < 0")
    sql_precip = (f"UPDATE `{table}` SET `precipitation_daily` = 0 "
                  f"WHERE `precipitation_daily` IS NOT NULL AND `precipitation_daily` < 0")
    with conn.cursor() as cur:
        cur.execute(sql_wind)
        nw = cur.rowcount
        cur.execute(sql_precip)
        np_ = cur.rowcount
    conn.commit()
    return nw, np_


# ── 子命令 ───────────────────────────────────────────────

def cmd_weather(args: argparse.Namespace) -> int:
    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"找不到 CSV: {csv_path}", file=sys.stderr)
        return 1

    print(f"读取: {csv_path}")
    df = read_weather_hour_csv(csv_path)
    print(f"原始行数: {len(df)}")

    daily = aggregate_weather_daily(df)
    print(f"聚合后日记录: {len(daily)}，站点数: {daily['station_id'].nunique()}")

    if args.dry_run:
        print(daily.head(10).to_string(index=False))
        print("(dry-run，未写入数据库)")
        return 0

    conn = mysql_connect(args.database)
    try:
        ensure_table(conn, CREATE_WEATHER_TABLE_SQL, args.table)
        n = upsert_weather(conn, args.table, daily, args.chunk_size)
        print(f"写入完成: {n} 行")
    finally:
        conn.close()
    return 0


def cmd_soil(args: argparse.Namespace) -> int:
    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"找不到 CSV: {csv_path}", file=sys.stderr)
        return 1

    print(f"读取: {csv_path}")
    df = read_soil_csv(csv_path)
    print(f"行数: {len(df)}，站点数: {df['station_id'].nunique()}")

    if args.dry_run:
        print(df.head(10).to_string(index=False))
        print("(dry-run，未写入数据库)")
        return 0

    conn = mysql_connect(args.database)
    try:
        ensure_table(conn, CREATE_SOIL_TABLE_SQL, args.table)
        n = upsert_soil(conn, args.table, df, args.chunk_size)
        print(f"写入完成: {n} 行")
    finally:
        conn.close()
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    conn = mysql_connect(args.database)
    try:
        ns = cleanup_negative_sunshine(conn, args.table)
        nw, np_ = cleanup_negative_wind_precip(conn, args.table)
        print(f"日照 <=0 归零: {ns} 行")
        print(f"风速负值归零: {nw} 行")
        print(f"降水负值归零: {np_} 行")
    finally:
        conn.close()
    return 0


def cmd_pest(args: argparse.Namespace) -> int:
    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"找不到 CSV: {csv_path}", file=sys.stderr)
        return 1

    print(f"读取: {csv_path}")
    df = read_pest_csv(csv_path)
    print(f"行数: {len(df)}，站点数: {df['point'].nunique()}")

    if args.dry_run:
        print(df.head(10).to_string(index=False))
        print("(dry-run，未写入数据库)")
        return 0

    conn = mysql_connect(args.database)
    try:
        ensure_table(conn, CREATE_PEST_TABLE_SQL, args.table)
        n = upsert_pest(conn, args.table, df, args.chunk_size)
        print(f"写入完成: {n} 行")
    finally:
        conn.close()
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = 0
    if args.weather_csv:
        w_args = argparse.Namespace(
            csv=args.weather_csv, table=args.weather_table, database=args.database,
            chunk_size=args.chunk_size, dry_run=args.dry_run,
        )
        rc |= cmd_weather(w_args)
    if args.soil_csv:
        s_args = argparse.Namespace(
            csv=args.soil_csv, table=args.soil_table, database=args.database,
            chunk_size=args.chunk_size, dry_run=args.dry_run,
        )
        rc |= cmd_soil(s_args)
    if args.with_pest:
        p_args = argparse.Namespace(
            csv=args.pest_csv, table=args.pest_table, database=args.database,
            chunk_size=args.chunk_size, dry_run=args.dry_run,
        )
        rc |= cmd_pest(p_args)
    if args.cleanup:
        c_args = argparse.Namespace(
            table=args.weather_table, database=args.database,
        )
        rc |= cmd_cleanup(c_args)
    return rc


# ── 入口 ─────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="Rice-Pro-Max 数据处理流水线")
    sub = p.add_subparsers(dest="command")

    # weather
    wp = sub.add_parser("weather", help="天气小时→日聚合入库")
    wp.add_argument("--csv", type=Path, default=DEFAULT_WEATHER_CSV)
    wp.add_argument("--table", default="station_weather_daily")
    wp.add_argument("--chunk-size", type=int, default=2000)
    wp.add_argument("--database", default=ENV_MYSQL_DATABASE)
    wp.add_argument("--dry-run", action="store_true")

    # soil
    sp = sub.add_parser("soil", help="土壤 CSV 入库")
    sp.add_argument("--csv", type=Path, default=DEFAULT_SOIL_CSV)
    sp.add_argument("--table", default="station_soil_daily")
    sp.add_argument("--chunk-size", type=int, default=2000)
    sp.add_argument("--database", default=ENV_MYSQL_DATABASE)
    sp.add_argument("--dry-run", action="store_true")

    # cleanup
    cp = sub.add_parser("cleanup", help="负值归零清洗")
    cp.add_argument("--table", default="station_weather_daily")
    cp.add_argument("--database", default=ENV_MYSQL_DATABASE)

    # pest
    pp = sub.add_parser("pest", help="病虫害监测数据入库")
    pp.add_argument("--csv", type=Path, default=DEFAULT_PEST_CSV)
    pp.add_argument("--table", default="pest_disease_monitoring")
    pp.add_argument("--chunk-size", type=int, default=2000)
    pp.add_argument("--database", default=ENV_MYSQL_DATABASE)
    pp.add_argument("--dry-run", action="store_true")

    # all
    ap = sub.add_parser("all", help="执行全部步骤")
    ap.add_argument("--weather-csv", type=Path, default=DEFAULT_WEATHER_CSV)
    ap.add_argument("--soil-csv", type=Path, default=DEFAULT_SOIL_CSV)
    ap.add_argument("--pest-csv", type=Path, default=DEFAULT_PEST_CSV)
    ap.add_argument("--weather-table", default="station_weather_daily")
    ap.add_argument("--soil-table", default="station_soil_daily")
    ap.add_argument("--pest-table", default="pest_disease_monitoring")
    ap.add_argument("--chunk-size", type=int, default=2000)
    ap.add_argument("--database", default=ENV_MYSQL_DATABASE)
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument("--with-pest", action="store_true", help="同时导入病虫害数据")
    ap.add_argument("--dry-run", action="store_true")

    args = p.parse_args()

    # ── 无参数直接双击运行 → 自动执行全部 ──
    if args.command is None:
        print("=" * 60)
        print("  Rice-Pro-Max 数据处理流水线（自动模式）")
        print("=" * 60)
        auto = argparse.Namespace(
            weather_csv=DEFAULT_WEATHER_CSV,
            soil_csv=DEFAULT_SOIL_CSV,
            pest_csv=DEFAULT_PEST_CSV,
            weather_table="station_weather_daily",
            soil_table="station_soil_daily",
            pest_table="pest_disease_monitoring",
            chunk_size=2000,
            database=ENV_MYSQL_DATABASE,
            cleanup=True,
            with_pest=DEFAULT_PEST_CSV.is_file(),
            dry_run=False,
        )
        rc = cmd_all(auto)
        print()
        if rc == 0:
            print("[OK] 全部完成！")
        else:
            print("[ERROR] 部分步骤出错，请查看上方日志")
        return rc

    if args.command == "weather":
        return cmd_weather(args)
    elif args.command == "soil":
        return cmd_soil(args)
    elif args.command == "cleanup":
        return cmd_cleanup(args)
    elif args.command == "pest":
        return cmd_pest(args)
    elif args.command == "all":
        return cmd_all(args)
    else:
        p.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
