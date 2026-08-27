from __future__ import annotations

import asyncio
import json
import re
from datetime import date as date_type
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pymysql
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star


STATION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

MONITORING_COLUMNS = """
    point, `Date`, GrowthPeriod, GrowthStatus,
    BacterialLeafBlightRate, BrownSpotRate, TungroVirusRate,
    PestRphNum, PestScsNum, PestCmNum
"""

RISK_SPECS = [
    ("细菌性叶枯病", "BacterialLeafBlightRate", 50, "%", "rate"),
    ("褐斑病", "BrownSpotRate", 50, "%", "rate"),
    ("东格鲁病害", "TungroVirusRate", 50, "%", "rate"),
    ("二化螟", "PestScsNum", 2, "只", "count"),
    ("褐飞虱", "PestRphNum", 2, "只", "count"),
    ("稻纵卷叶螟", "PestCmNum", 2, "只", "count"),
]


class AgriQueryPlugin(Star):
    """智慧农业病虫害数据库只读查询插件。"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _authorization_error(self, event: AstrMessageEvent) -> str | None:
        raw_umos = self.config.get("allowed_umos", [])
        if isinstance(raw_umos, str):
            raw_umos = [raw_umos]
        allowed_umos = {
            str(item).strip() for item in raw_umos if str(item).strip()
        }
        if not allowed_umos:
            return (
                "农业数据库查询插件尚未配置 allowed_umos 白名单，"
                "请管理员先在插件配置中添加当前微信会话的 UMO。"
            )
        if event.unified_msg_origin not in allowed_umos:
            logger.warning(
                "拒绝未授权的农业数据库查询: umo=%s",
                event.unified_msg_origin,
            )
            return "当前微信会话没有农业数据库查询权限。"
        return None

    def _connect_mysql(self):
        required_keys = (
            "mysql_host",
            "mysql_port",
            "mysql_user",
            "mysql_database",
        )
        missing = [key for key in required_keys if not self.config.get(key)]
        if missing:
            raise RuntimeError("插件缺少数据库配置：" + ", ".join(missing))

        return pymysql.connect(
            host=str(self.config["mysql_host"]),
            port=int(self.config["mysql_port"]),
            user=str(self.config["mysql_user"]),
            password=str(self.config.get("mysql_password", "")),
            database=str(self.config["mysql_database"]),
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _select(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        if not sql.lstrip().upper().startswith("SELECT"):
            raise RuntimeError("插件只允许执行 SELECT 查询")

        conn = self._connect_mysql()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall() or [])
        finally:
            conn.close()

    async def _select_async(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._select, sql, params)

    @staticmethod
    def _parse_date(value: str, parameter_name: str) -> date_type:
        normalized = str(value).strip().lower()
        today = date_type.today()
        relative_dates = {
            "today": today,
            "今天": today,
            "yesterday": today - timedelta(days=1),
            "昨天": today - timedelta(days=1),
        }
        if normalized in relative_dates:
            return relative_dates[normalized]
        try:
            return datetime.strptime(normalized, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"{parameter_name} 必须是 YYYY-MM-DD、今天或昨天"
            ) from exc

    def _parse_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> tuple[date_type, date_type]:
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        if start > end:
            raise ValueError("start_date 不能晚于 end_date")

        configured_limit = int(self.config.get("max_range_days", 31))
        max_range_days = min(max(configured_limit, 1), 366)
        requested_days = (end - start).days + 1
        if requested_days > max_range_days:
            raise ValueError(
                f"单次最多查询 {max_range_days} 天，当前请求为 {requested_days} 天"
            )
        return start, end

    @staticmethod
    def _validate_point(point: str, *, allow_all: bool = False) -> str:
        normalized = str(point).strip()
        if allow_all and normalized.upper() in {"ALL", "全部", "所有"}:
            return "ALL"
        if not STATION_PATTERN.fullmatch(normalized):
            raise ValueError(
                "站点编号只能包含字母、数字、下划线和连字符，长度不超过64"
            )
        return normalized

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, (datetime, date_type)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        raise TypeError(f"无法序列化类型：{type(value).__name__}")

    def _dump(self, payload: dict[str, Any]) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            default=self._json_default,
        )

    @staticmethod
    def _red_items(record: dict[str, Any]) -> list[dict[str, Any]]:
        red_items: list[dict[str, Any]] = []
        for name, field, threshold, unit, value_type in RISK_SPECS:
            raw_value = record.get(field)
            try:
                value = int(raw_value or 0) if value_type == "count" else float(raw_value or 0)
            except (TypeError, ValueError):
                value = 0
            if value >= threshold:
                red_items.append(
                    {
                        "病虫害": name,
                        "监测值": value,
                        "红色阈值": threshold,
                        "单位": unit,
                    }
                )
        return red_items

    def _monitoring_record(self, record: dict[str, Any]) -> dict[str, Any]:
        result = dict(record)
        result["risk_level"] = "red" if self._red_items(record) else "normal"
        result["red_items"] = self._red_items(record)
        return result

    @filter.llm_tool(name="query_station_monitoring")
    async def query_station_monitoring(
        self,
        event: AstrMessageEvent,
        point: str,
        date: str,
    ):
        """查询指定站点在某一天的病虫害监测数据和红色项目。

        Args:
            point(string): 站点编号，例如 ST-002
            date(string): 查询日期，使用 YYYY-MM-DD；也可传今天或昨天
        """
        authorization_error = self._authorization_error(event)
        if authorization_error:
            return authorization_error

        try:
            normalized_point = self._validate_point(point)
            query_date = self._parse_date(date, "date")
            rows = await self._select_async(
                f"""
                SELECT {MONITORING_COLUMNS}
                FROM pest_disease_monitoring
                WHERE point = %s AND `Date` = %s
                LIMIT 1
                """,
                (normalized_point, query_date),
            )
            records = [self._monitoring_record(row) for row in rows]
            return self._dump(
                {
                    "ok": True,
                    "data_source": "pest_disease_monitoring",
                    "point": normalized_point,
                    "date": query_date,
                    "count": len(records),
                    "records": records,
                }
            )
        except Exception as exc:
            logger.exception("查询单日站点病虫害数据失败")
            return f"数据库查询失败：{exc}"

    @filter.llm_tool(name="query_monitoring_history")
    async def query_monitoring_history(
        self,
        event: AstrMessageEvent,
        point: str,
        start_date: str,
        end_date: str,
    ):
        """查询指定站点一段时间内的历史病虫害数据和红色项目。

        Args:
            point(string): 站点编号，例如 ST-002
            start_date(string): 开始日期，格式 YYYY-MM-DD
            end_date(string): 结束日期，格式 YYYY-MM-DD
        """
        authorization_error = self._authorization_error(event)
        if authorization_error:
            return authorization_error

        try:
            normalized_point = self._validate_point(point)
            start, end = self._parse_date_range(start_date, end_date)
            rows = await self._select_async(
                f"""
                SELECT {MONITORING_COLUMNS}
                FROM pest_disease_monitoring
                WHERE point = %s AND `Date` BETWEEN %s AND %s
                ORDER BY `Date` ASC
                LIMIT 366
                """,
                (normalized_point, start, end),
            )
            records = [self._monitoring_record(row) for row in rows]
            return self._dump(
                {
                    "ok": True,
                    "data_source": "pest_disease_monitoring",
                    "point": normalized_point,
                    "start_date": start,
                    "end_date": end,
                    "count": len(records),
                    "records": records,
                }
            )
        except Exception as exc:
            logger.exception("查询历史病虫害数据失败")
            return f"数据库查询失败：{exc}"

    @filter.llm_tool(name="query_all_monitoring_by_date")
    async def query_all_monitoring_by_date(
        self,
        event: AstrMessageEvent,
        date: str,
    ):
        """查询某一天全部站点的病虫害监测数据和红色项目。

        Args:
            date(string): 查询日期，使用 YYYY-MM-DD；也可传今天或昨天
        """
        authorization_error = self._authorization_error(event)
        if authorization_error:
            return authorization_error

        try:
            query_date = self._parse_date(date, "date")
            rows = await self._select_async(
                f"""
                SELECT {MONITORING_COLUMNS}
                FROM pest_disease_monitoring
                WHERE `Date` = %s
                ORDER BY point ASC
                LIMIT 200
                """,
                (query_date,),
            )
            records = [self._monitoring_record(row) for row in rows]
            return self._dump(
                {
                    "ok": True,
                    "data_source": "pest_disease_monitoring",
                    "date": query_date,
                    "count": len(records),
                    "records": records,
                    "truncated": len(records) >= 200,
                }
            )
        except Exception as exc:
            logger.exception("查询全部站点单日病虫害数据失败")
            return f"数据库查询失败：{exc}"

    @filter.llm_tool(name="query_red_alerts")
    async def query_red_alerts(
        self,
        event: AstrMessageEvent,
        point: str,
        start_date: str,
        end_date: str,
    ):
        """查询某个站点或全部站点在日期范围内生成的红色告警。

        Args:
            point(string): 站点编号；查询全部站点时传 ALL
            start_date(string): 开始日期，格式 YYYY-MM-DD
            end_date(string): 结束日期，格式 YYYY-MM-DD
        """
        authorization_error = self._authorization_error(event)
        if authorization_error:
            return authorization_error

        try:
            normalized_point = self._validate_point(point, allow_all=True)
            start, end = self._parse_date_range(start_date, end_date)
            sql = """
                SELECT point, monitor_date, item_name,
                       item_value, threshold_value, unit,
                       status, attempts, created_at, sent_at, last_error
                FROM pest_disease_alerts
                WHERE monitor_date BETWEEN %s AND %s
            """
            params: tuple[Any, ...] = (start, end)
            if normalized_point != "ALL":
                sql += " AND point = %s"
                params += (normalized_point,)
            sql += " ORDER BY monitor_date DESC, point ASC, id DESC LIMIT 200"

            rows = await self._select_async(sql, params)
            return self._dump(
                {
                    "ok": True,
                    "data_source": "pest_disease_alerts",
                    "point": normalized_point,
                    "start_date": start,
                    "end_date": end,
                    "count": len(rows),
                    "alerts": rows,
                    "truncated": len(rows) >= 200,
                }
            )
        except Exception as exc:
            logger.exception("查询红色告警记录失败")
            return f"数据库查询失败：{exc}"

    @filter.llm_tool(name="query_alert_status")
    async def query_alert_status(
        self,
        event: AstrMessageEvent,
        point: str,
        date: str,
    ):
        """查询指定站点某一天的微信告警发送状态和失败原因。

        Args:
            point(string): 站点编号，例如 ST-002
            date(string): 告警日期，使用 YYYY-MM-DD；也可传今天或昨天
        """
        authorization_error = self._authorization_error(event)
        if authorization_error:
            return authorization_error

        try:
            normalized_point = self._validate_point(point)
            query_date = self._parse_date(date, "date")
            rows = await self._select_async(
                """
                SELECT point, monitor_date, item_name,
                       item_value, threshold_value, unit,
                       status, attempts, created_at, sent_at, last_error
                FROM pest_disease_alerts
                WHERE point = %s AND monitor_date = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (normalized_point, query_date),
            )
            return self._dump(
                {
                    "ok": True,
                    "data_source": "pest_disease_alerts",
                    "point": normalized_point,
                    "date": query_date,
                    "count": len(rows),
                    "alerts": rows,
                }
            )
        except Exception as exc:
            logger.exception("查询微信告警发送状态失败")
            return f"数据库查询失败：{exc}"

    @filter.command("agri_query_status")
    async def agri_query_status(self, event: AstrMessageEvent):
        """检查农业数据库查询插件的授权和数据库连接。"""
        authorization_error = self._authorization_error(event)
        if authorization_error:
            yield event.plain_result(
                authorization_error
                + f"\n当前 UMO：{event.unified_msg_origin}"
            )
            return

        try:
            rows = await self._select_async("SELECT 1 AS connected", ())
            connected = bool(rows and rows[0].get("connected") == 1)
            yield event.plain_result(
                "农业数据库查询插件运行正常。"
                if connected
                else "数据库返回结果异常。"
            )
        except Exception as exc:
            logger.exception("农业数据库连接测试失败")
            yield event.plain_result(f"数据库连接失败：{exc}")

    @filter.command("agri_query_all")
    async def agri_query_all(self, event: AstrMessageEvent, date: str):
        """不经过AI，直接查询某一天全部站点的病虫害数据。"""
        authorization_error = self._authorization_error(event)
        if authorization_error:
            yield event.plain_result(authorization_error)
            return

        try:
            query_date = self._parse_date(date, "date")
            rows = await self._select_async(
                f"""
                SELECT {MONITORING_COLUMNS}
                FROM pest_disease_monitoring
                WHERE `Date` = %s
                ORDER BY point ASC
                LIMIT 200
                """,
                (query_date,),
            )
            records = [self._monitoring_record(row) for row in rows]
            red_records = [row for row in records if row["red_items"]]
            lines = [
                f"查询日期：{query_date.isoformat()}",
                f"站点记录：{len(records)}条",
                f"红色站点：{len(red_records)}个",
            ]
            if not records:
                lines.append("数据库中没有该日期的病虫害监测记录。")
            elif red_records:
                lines.append("红色项目：")
                for record in red_records:
                    descriptions = [
                        f"{item['病虫害']} {item['监测值']}{item['单位']}"
                        for item in record["red_items"]
                    ]
                    lines.append(f"- {record['point']}：" + "；".join(descriptions))
            else:
                lines.append("当日没有达到红色阈值的站点。")
            yield event.plain_result("\n".join(lines))
        except Exception as exc:
            logger.exception("直接查询全部站点病虫害数据失败")
            yield event.plain_result(f"数据库查询失败：{exc}")
