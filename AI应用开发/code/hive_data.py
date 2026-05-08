"""
data_loader.py
============================================================================
统一从 Hive 读取并预处理"水稻智慧农业"项目所需的数据。

本模块对外只暴露一个类：RiceDataLoader

  loader = RiceDataLoader(host="...", port=10000, user="...", database="rice_db")
  weather_df = loader.load_weather()       # 小时气象 → 日尺度
  disease_df = loader.load_disease()       # 病虫害监测数据
  soil_df    = loader.load_soil()          # 土壤理化指标数据

  注意：产量预测基线数据也可从 Hive `rice_yield` 表加载，供 rice_yield.py 使用。

----------------------------------------------------------------------------
运行时依赖（请先 pip install）：

    pip install sqlalchemy "pyhive[hive]"

Windows 用户若遇 sasl 编译失败，可改用纯 Python 实现：
    pip install pure-sasl thrift_sasl
或者把 Hive 服务端的 auth 模式改为 NOSASL / LDAP，绕开 sasl 依赖。
============================================================================
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


class RiceDataLoader:
    """从 Hive 读 + 清洗，统一返回 DataFrame，供 disease/weather/soil/rice_yield 等模块直接使用。"""

    # ============================================================
    # 一、Hive 表名（默认值，可被构造参数覆盖）
    # ============================================================
    TABLE_WEATHER_HOUR = "weather_hour"      # 小时气象原始数据
    TABLE_PEST         = "pest_data"         # 病虫害监测数据
    TABLE_SOIL         = "soil_yield"         # 土壤理化指标数据
    TABLE_YIELD        = "rice_yield"        # 产量基线表（供 rice_yield.py 使用）

    # ============================================================
    # 二、气象表列名约定（纯英文 · 假设 Hive 已是这套命名）
    #    若你 Hive 表实际列名不一致，构造时传 weather_columns={...} 覆盖即可
    # ============================================================
    # ============================================================
    # 二.5、病虫害 / 土壤两张表的"Hive 列名 → 下游模块期望列名"映射
    #      Hive 列名默认全小写；下游 disease.py / soil.py 用的是 PascalCase。
    #      产量表（rice_yield）列名与代码一致，无需映射。
    # ============================================================
    DEFAULT_DISEASE_RENAME: dict[str, str] = {
        # Hive 实际列名（全小写）          # 代码期望列名 (disease.py)
        "point":                    "point",
        "date":                     "Date",
        "bacterialleafblightrate":  "BacterialLeafBlightRate",
        "brownspotrate":            "BrownSpotRate",
        "tungrovirusrate":          "TungroVirusRate",
        "pestrphnum":               "PestRphNum",
        "pestscsnum":               "PestScsNum",
        "pestcmnum":                "PestCmNum",
        "growthperiod":             "GrowthPeriod",
        "growthstatus":             "GrowthStatus",
    }
    DEFAULT_SOIL_RENAME: dict[str, str] = {
        # Hive 实际列名（全小写）     # 代码期望列名 (soil.py)
        "monitor_point":    "point",
        "monitor_date":     "date",
        "soil_om_percent":  "Soil_OM_percent",
        "soil_ph":          "Soil_pH",
        "soil_p_ppm":       "Soil_P_ppm",
        "soil_k_ppm":       "Soil_K_ppm",
        "soil_ec_ds_m":     "Soil_EC_dS_m",
    }
    DEFAULT_WEATHER_COLUMNS: dict[str, str] = {
        # 业务键          # Hive 实际列名（Hive 默认全部小写）
        "point":          "point",
        "date":           "weather_date",
        "hour":           "hour",
        "sunshine":       "sunshineduration",
        "wind_02":        "winddirection_02",
        "wind_08":        "winddirection_08",
        "wind_14":        "winddirection_14",
        "wind_20":        "winddirection_20",
        "avg_wind":       "dailyaveragewind",
        "precip":         "dailyprecipitation",
        "max_temp":       "dailymaximumtemperature",
        "min_temp":       "dailyminimumtemperature",
        "avg_temp":       "dailyaveragetemperature",
        "humidity":       "dailyrelativehumidity",
        "pressure":       "dailyaveragepressure",
    }

    # ============================================================
    # 三、时间加权权重（覆盖 24 小时）
    #   Hour 1 → 5.5h, Hour 7 → 6.0h, Hour 13 → 6.5h, Hour 20 → 6.0h
    # ============================================================
    HOUR_WEIGHTS: dict[int, float] = {1: 5.5, 7: 6.0, 13: 6.5, 20: 6.0}

    # ============================================================
    # 四、构造函数：注入 Hive 连接信息 + 可选的表名/列名覆盖
    # ============================================================
    def __init__(
        self,
        host: str,
        port: int = 10000,
        user: str = "hive",
        database: str = "default",
        password: Optional[str] = None,
        auth: str = "NONE",
        kerberos_service_name: str = "hive",
        # ── 表名覆盖（不传则使用类常量默认值）──
        table_weather_hour: Optional[str] = None,
        table_pest:         Optional[str] = None,
        table_soil:         Optional[str] = None,
        table_yield:        Optional[str] = None,
        # ── 气象列名覆盖（部分覆盖即可，未传的继承默认值）──
        weather_columns: Optional[dict[str, str]] = None,
        # ── 其他两张表的输出 rename 覆盖（部分覆盖即可）──
        disease_rename: Optional[dict[str, str]] = None,
        soil_rename:    Optional[dict[str, str]] = None,
    ):
        self.host                  = host
        self.port                  = port
        self.user                  = user
        self.database              = database
        self.password              = password
        self.auth                  = auth.upper()
        self.kerberos_service_name = kerberos_service_name

        self.table_weather_hour = table_weather_hour or self.TABLE_WEATHER_HOUR
        self.table_pest         = table_pest         or self.TABLE_PEST
        self.table_soil         = table_soil         or self.TABLE_SOIL
        self.table_yield        = table_yield        or self.TABLE_YIELD

        # 合并默认列名 + 用户覆盖
        self._weather_cols: dict[str, str] = {**self.DEFAULT_WEATHER_COLUMNS,
                                              **(weather_columns or {})}
        self._disease_rename: dict[str, str] = {**self.DEFAULT_DISEASE_RENAME,
                                                **(disease_rename or {})}
        self._soil_rename: dict[str, str]    = {**self.DEFAULT_SOIL_RENAME,
                                                **(soil_rename    or {})}

        # SQLAlchemy engine 懒加载——构造类不会立即连 Hive
        self._engine: Optional[Engine] = None

    # ============================================================
    # 五、Hive 连接（SQLAlchemy engine · 懒加载）
    # ============================================================
    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._build_engine()
        return self._engine

    def _build_engine(self) -> Engine:
        """根据 auth 模式构建 SQLAlchemy hive:// engine。

        ⚠ 客户端 auth 必须与 Hive 服务端 hive.server2.authentication 严格匹配，
           否则会报 `TTransportException: TSocket read 0 bytes`。
           - 服务端 NONE      ↔  这里 auth='NONE'    （走 SASL PLAIN，PyHive 默认）
           - 服务端 NOSASL    ↔  这里 auth='NOSASL'  （裸 thrift，无 SASL 层）
           - 服务端 LDAP      ↔  这里 auth='LDAP'    + user + password
           - 服务端 KERBEROS  ↔  这里 auth='KERBEROS'
           注意：'NONE' 与 'NOSASL' 是两种完全不同的协议！别混。
        """
        if self.auth == "KERBEROS":
            url = f"hive://{self.host}:{self.port}/{self.database}"
            return create_engine(url, connect_args={
                "auth": "KERBEROS",
                "kerberos_service_name": self.kerberos_service_name,
            })

        if self.auth == "LDAP":
            if self.password is None:
                raise ValueError("LDAP 认证需要传入 password")
            url = (f"hive://{self.user}:{self.password}"
                   f"@{self.host}:{self.port}/{self.database}")
            return create_engine(url, connect_args={"auth": "LDAP"})

        if self.auth == "NOSASL":
            url = f"hive://{self.user}@{self.host}:{self.port}/{self.database}"
            return create_engine(url, connect_args={"auth": "NOSASL"})

        # 默认 NONE：等价于 PyHive 的 SASL PLAIN，对应 Hive 默认服务端配置
        if self.password is not None:
            url = (f"hive://{self.user}:{self.password}"
                   f"@{self.host}:{self.port}/{self.database}")
        else:
            url = f"hive://{self.user}@{self.host}:{self.port}/{self.database}"
        return create_engine(url, connect_args={"auth": "NONE"})

    # ============================================================
    # 五.5、连通性诊断（建议在第一次跑全量前用 .ping 探一下）
    # ============================================================
    @property
    def ping(self) -> int:
        """轻量探活：执行 SELECT 1，验证连接 + 认证是否通。

        Returns:
            200 — 连接成功
            403 — 连接失败（不会抛异常）

        如果报 `TTransportException: TSocket read 0 bytes`，
        99% 是 auth 模式跟 Hive 服务端对不上，请按下表对照调整：

            服务端 hive.server2.authentication  →  这里传 auth=
                NONE      (Hive 默认)            →  "NONE"
                NOSASL                           →  "NOSASL"
                LDAP                             →  "LDAP" + user + password
                KERBEROS                         →  "KERBEROS"
        """
        try:
            with self.engine.connect() as conn:
                result = conn.exec_driver_sql("SELECT 1").fetchone()
            if not result or result[0] != 1:
                return 403
            return 200
        except Exception as e:
            return 403

    # ============================================================
    # 六、对外方法 —— 加载 + 清洗气象数据（已实现）
    # ============================================================
    def load_weather(self) -> pd.DataFrame:
        """从 Hive 读取小时气象 → 时间加权聚合 → 返回日尺度 DataFrame。

        聚合规则：
          日照时长        → 求和
          风向(二级/八级) → 取众数
          风向(14时/20时) → 分别取 Hour=13/20 的观测值
          日均风速/气温/湿度/气压 → 时间加权平均
          降水量          → 求和（"T"微量降水按 0.05mm 计入）
          最高/最低气温   → 取 max / min
        """
        cols = self._weather_cols
        select_cols = list(cols.values())

        # ① 拉取 Hive 数据（仅取必要列，节省网络）
        sql = f"SELECT {', '.join(select_cols)} FROM {self.table_weather_hour}"
        df = pd.read_sql(sql, self.engine)

        # ② 列存在性校验（即便 SQL 报错信息不友好，也给一道 Python 端兜底）
        missing = [c for c in select_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Hive 表 `{self.table_weather_hour}` 缺少必需列: {missing}\n"
                f"请通过 RiceDataLoader(weather_columns={{...}}) 覆盖列名映射。"
            )

        # ③ 类型清洗：降水含 "T"（微量降水）→ 0.05mm；其余转 numeric
        df[cols["precip"]] = pd.to_numeric(
            df[cols["precip"]].replace({"T": 0.05, "t": 0.05}), errors="coerce"
        )
        df[cols["sunshine"]] = pd.to_numeric(df[cols["sunshine"]], errors="coerce")
        for k in ("avg_wind", "avg_temp", "humidity", "pressure"):
            df[cols[k]] = pd.to_numeric(df[cols[k]], errors="coerce")

        # ④ 计算时间加权权重列（hour 统一转 float 再 map，避免类型不匹配）
        hour_num = pd.to_numeric(df[cols["hour"]], errors="coerce")
        df["_weight"] = hour_num.map(self.HOUR_WEIGHTS)

        # ⑤ 按 (站点, 日期) 分组聚合
        group_keys = [cols["point"], cols["date"]]
        grp = df.groupby(group_keys)

        parts: list[pd.Series] = []

        # 累计量：日照、降水
        parts.append(grp[cols["sunshine"]].sum(min_count=1).rename(cols["sunshine"]))
        parts.append(grp[cols["precip"]].sum(min_count=1).rename(cols["precip"]))

        # 极值：最高/最低气温
        parts.append(grp[cols["max_temp"]].max().rename(cols["max_temp"]))
        parts.append(grp[cols["min_temp"]].min().rename(cols["min_temp"]))

        # 众数：风向二级 / 八级
        parts.append(self._mode_agg(df, cols["wind_02"], group_keys))
        parts.append(self._mode_agg(df, cols["wind_08"], group_keys))

        # 定时观测：14时 / 20时风向
        parts.append(self._pick_hour_value(df, cols["wind_14"], 13, group_keys, cols["hour"]))
        parts.append(self._pick_hour_value(df, cols["wind_20"], 20, group_keys, cols["hour"]))

        # 时间加权平均：风速、气温、湿度、气压
        for k in ("avg_wind", "avg_temp", "humidity", "pressure"):
            parts.append(self._weighted_avg_agg(df, cols[k], group_keys))

        daily = pd.concat(parts, axis=1).reset_index()

        # ⑥ 整列顺序、四舍五入、排序
        col_order = [
            cols["point"], cols["date"],
            cols["sunshine"],
            cols["wind_02"], cols["wind_08"], cols["wind_14"], cols["wind_20"],
            cols["avg_wind"], cols["precip"],
            cols["max_temp"], cols["min_temp"], cols["avg_temp"],
            cols["humidity"], cols["pressure"],
        ]
        daily = daily[col_order]

        # ⑥.5 数据合理性清洗（日照负数归零、湿度超过100%截断）
        daily = self._clean_weather(daily, cols)

        for k in ("sunshine", "precip", "avg_wind", "avg_temp", "humidity", "pressure"):
            daily[cols[k]] = daily[cols[k]].round(2)

        # 站点升序、日期正序（mergesort 稳定排序，结果可复现）
        _date_sort = pd.to_datetime(daily[cols["date"]], errors="coerce")
        daily = (
            daily.assign(_date_sort=_date_sort)
                 .sort_values(by=[cols["point"], "_date_sort"],
                              ascending=[True, True],
                              kind="mergesort", na_position="last")
                 .drop(columns="_date_sort")
                 .reset_index(drop=True)
        )

        # ⑦ 兼容下游模块：把日期列从 Hive 列名（如 weather_date）重命名为 `date`
        #    这样 weather.py 等业务模块拿到 DataFrame 后无需再 rename 即可直接使用
        if cols["date"] != "date":
            daily = daily.rename(columns={cols["date"]: "date"})

        # ⑧ 日期列转为 datetime，兼容 weather.py 中的时间比较
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")

        return daily
    # ============================================================
    # 七、其他数据源：默认 SELECT * 读整张表 → 返回 DataFrame
    #     如需特定清洗逻辑，可以在子类里 override 或在调用方拿到 df 后再处理
    # ============================================================
    def _read_table(self, table: str) -> pd.DataFrame:
        """通用读表工具：SELECT * FROM <table>。"""
        return pd.read_sql(f"SELECT * FROM {table}", self.engine)

    def load_disease(self) -> pd.DataFrame:
        """从 Hive 读病虫害监测表（默认 `pest_data`），自动 rename 后返回。

        rename 规则：Hive 全小写列名 → disease.py 期望的 PascalCase（Date / BacterialLeafBlightRate / PestRphNum 等）。
        """
        df = self._read_table(self.table_pest)
        df = df.rename(columns=self._disease_rename)

        # Hive 全部列为 string 类型，将数值列转为 numeric
        numeric_cols = [
            "BacterialLeafBlightRate", "BrownSpotRate", "TungroVirusRate",
            "PestRphNum", "PestScsNum", "PestCmNum",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 数据合理性清洗
        df = self._clean_disease(df)

        return df

    def load_soil(self) -> pd.DataFrame:
        """从 Hive 读土壤理化指标表（默认 `soil_yield`），自动 rename 后返回。

        rename 规则：soil_om_percent → Soil_OM_percent、soil_ph → Soil_pH 等。
        """
        df = self._read_table(self.table_soil)
        df = df.rename(columns=self._soil_rename)

        # Hive 全部列为 string 类型，将数值列转为 numeric
        numeric_cols = ["Soil_OM_percent", "Soil_pH", "Soil_P_ppm", "Soil_K_ppm", "Soil_EC_dS_m"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 数据合理性清洗
        df = self._clean_soil(df)

        # 日期列转为 datetime，兼容 soil.py 中的时间比较
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        return df

    def load_yield(self) -> pd.DataFrame:
        """从 Hive 读分站点分年份产量基线表（默认 `rice_yield`），整张表返回。

        Hive 列名（如 point、2025firstcrop_pred）本就是小写，与 rice_yield.py 期望一致，无需 rename。
        """
        df = self._read_table(self.table_yield)
        return self._clean_yield(df)

    # ============================================================
    # 八、内部聚合工具（私有静态方法）
    # ============================================================
    @staticmethod
    def _clean_weather(df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
        """日聚合后的数据合理性清洗。

        清洗规则（可继续扩充）：
        ─────────────────────────────
        • 日照时长 (sunshine) < 0 → 归零（传感器异常负值）
        • 相对湿度 (humidity) > 100 → 截断为 100（传感器漂移 / 结露）
        • 降水 (precip) < 0 → 归零
        • 气压 (pressure) < 0 → 归零（极少见，但兜底）
        """
        _df = df.copy()

        # 日照时长：负数归零
        sunshine_col = cols.get("sunshine", "sunshineduration")
        if sunshine_col in _df.columns:
            _df.loc[_df[sunshine_col] < 0, sunshine_col] = 0.0

        # 相对湿度：超过 100% 截断为 100
        humidity_col = cols.get("humidity", "dailyrelativehumidity")
        if humidity_col in _df.columns:
            _df.loc[_df[humidity_col] > 100, humidity_col] = 100.0
            # 同时处理可能的负湿度
            _df.loc[_df[humidity_col] < 0, humidity_col] = 0.0

        # 降水量：负数归零
        precip_col = cols.get("precip", "dailyprecipitation")
        if precip_col in _df.columns:
            _df.loc[_df[precip_col] < 0, precip_col] = 0.0

        # 气压：负数归零
        pressure_col = cols.get("pressure", "dailyaveragepressure")
        if pressure_col in _df.columns:
            _df.loc[_df[pressure_col] < 0, pressure_col] = 0.0

        return _df

    @staticmethod
    def _clean_disease(df: pd.DataFrame) -> pd.DataFrame:
        """病虫害监测数据合理性清洗。

        清洗规则：
        ─────────────────────────────
        • 叶害覆盖率 (BacterialLeafBlightRate / BrownSpotRate / TungroVirusRate)
          < 0 → 归零，> 100 → 截断为 100
        • 虫害数量 (PestRphNum / PestScsNum / PestCmNum) < 0 → 归零
        """
        _df = df.copy()

        # 覆盖率类：夹逼到 [0, 100]
        rate_cols = ["BacterialLeafBlightRate", "BrownSpotRate", "TungroVirusRate"]
        for col in rate_cols:
            if col in _df.columns:
                _df.loc[_df[col] < 0, col] = 0.0
                _df.loc[_df[col] > 100, col] = 100.0

        # 虫害数量类：负数归零
        pest_cols = ["PestRphNum", "PestScsNum", "PestCmNum"]
        for col in pest_cols:
            if col in _df.columns:
                _df.loc[_df[col] < 0, col] = 0

        return _df

    @staticmethod
    def _clean_soil(df: pd.DataFrame) -> pd.DataFrame:
        """土壤理化指标数据合理性清洗。

        清洗规则：
        ─────────────────────────────
        • 有机质 (Soil_OM_percent) < 0 → 归零，> 100 → 截断为 100
        • pH (Soil_pH) < 0 → 归零，> 14 → 截断为 14
        • 磷/钾 (Soil_P_ppm / Soil_K_ppm) < 0 → 归零
        • 电导率 (Soil_EC_dS_m) < 0 → 归零
        """
        _df = df.copy()

        # 有机质：夹逼到 [0, 100]
        if "Soil_OM_percent" in _df.columns:
            _df.loc[_df["Soil_OM_percent"] < 0, "Soil_OM_percent"] = 0.0
            _df.loc[_df["Soil_OM_percent"] > 100, "Soil_OM_percent"] = 100.0

        # pH：夹逼到 [0, 14]
        if "Soil_pH" in _df.columns:
            _df.loc[_df["Soil_pH"] < 0, "Soil_pH"] = 0.0
            _df.loc[_df["Soil_pH"] > 14, "Soil_pH"] = 14.0

        # 磷/钾/电导率：负数归零
        nonneg_cols = ["Soil_P_ppm", "Soil_K_ppm", "Soil_EC_dS_m"]
        for col in nonneg_cols:
            if col in _df.columns:
                _df.loc[_df[col] < 0, col] = 0.0

        return _df

    @staticmethod
    def _clean_yield(df: pd.DataFrame) -> pd.DataFrame:
        """产量基线数据合理性清洗。

        清洗规则：
        ─────────────────────────────
        • 所有数值列（产量预测值等）< 0 → 归零
        • 排除 point / date 等非数值标识列
        """
        _df = df.copy()

        # 对所有数值列做非负归零（跳过 point 等字符串列）
        num_cols = _df.select_dtypes(include=["number"]).columns
        for col in num_cols:
            _df.loc[_df[col] < 0, col] = 0.0

        return _df

    @staticmethod
    def _weighted_avg_agg(df: pd.DataFrame, col: str,
                          group_keys: list[str]) -> pd.Series:
        """向量化时间加权平均：(Σ value*weight) / Σ weight，NaN 安全。"""
        weighted = df[col] * df["_weight"]
        valid_weight = df["_weight"].where(df[col].notna())
        wsum = weighted.groupby([df[k] for k in group_keys]).sum(min_count=1)
        wtot = valid_weight.groupby([df[k] for k in group_keys]).sum(min_count=1)
        return (wsum / wtot).rename(col)

    @staticmethod
    def _mode_agg(df: pd.DataFrame, col: str,
                  group_keys: list[str]) -> pd.Series:
        """取每组众数（最高频值），等频时保留第一个出现的。"""
        return (
            df.groupby(group_keys)[col]
              .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan)
              .rename(col)
        )

    @staticmethod
    def _pick_hour_value(df: pd.DataFrame, col: str, hour: int,
                         group_keys: list[str], hour_col: str) -> pd.Series:
        """从指定小时记录里直接取观测值。"""
        sub = df.loc[df[hour_col] == hour, group_keys + [col]].set_index(group_keys)[col]
        return sub.rename(col)

    # ============================================================
    # 九、资源管理（支持 with 语法）
    # ============================================================
    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def __enter__(self) -> "RiceDataLoader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ============================================================================
# 自测入口：演示如何调用（运行前请确认 Hive 连接可达）
# ============================================================================
if __name__ == "__main__":
    hive = RiceDataLoader(
        host="192.168.157.130",
        port=10000,
        user="root",
        database="farm"
    )
    if hive.ping == 200:
        weather_df = hive.load_weather()
        print("天气数据预览：")
        print(weather_df.head())

        disease_df = hive.load_disease()
        print("\n病虫害数据预览：")
        print(disease_df.head())

        soil_df = hive.load_soil()
        print("\n土壤数据预览：")
        print(soil_df.head())

        yield_df = hive.load_yield()
        print("\n产量数据预览：")
        print(yield_df.head())
    else:
        print("无法连接 Hive，请检查连接参数和服务状态。")