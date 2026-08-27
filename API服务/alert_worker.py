from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import pymysql


APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent
CONFIG_PATH = WORKSPACE_ROOT / "conf" / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pest-disease-alert-worker")


def _load_config() -> tuple[dict[str, Any], dict[str, Any]]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        config = json.load(fp)

    mysql_config = config["mysql"]
    astrbot_config = config.get("astrbot") or {}
    return mysql_config, astrbot_config


MYSQL_CFG, ASTRBOT_CFG = _load_config()


def _astrbot_settings() -> tuple[bool, str, str, list[str], int, int]:
    enabled = bool(ASTRBOT_CFG.get("enabled", False))
    base_url = str(ASTRBOT_CFG.get("base_url", "")).strip().rstrip("/")
    api_key = str(ASTRBOT_CFG.get("api_key", "")).strip()
    raw_umos = ASTRBOT_CFG.get("alert_umos", [])
    if isinstance(raw_umos, str):
        raw_umos = [raw_umos]
    umos = [str(item).strip() for item in raw_umos if str(item).strip()]
    poll_interval = max(5, int(ASTRBOT_CFG.get("poll_interval_seconds", 30)))
    timeout_seconds = max(3, int(ASTRBOT_CFG.get("timeout_seconds", 15)))
    return enabled, base_url, api_key, umos, poll_interval, timeout_seconds


def _validate_astrbot_settings() -> None:
    enabled, base_url, api_key, umos, _, _ = _astrbot_settings()
    if not enabled:
        raise RuntimeError("conf/config.json 中 astrbot.enabled 不是 true")
    if not base_url:
        raise RuntimeError("conf/config.json 缺少 astrbot.base_url")
    if not api_key:
        raise RuntimeError("conf/config.json 缺少 astrbot.api_key")
    if not umos:
        raise RuntimeError("conf/config.json 缺少 astrbot.alert_umos")


def _connect_mysql(*, dict_cursor: bool = False):
    kwargs: dict[str, Any] = {
        "host": MYSQL_CFG["host"],
        "port": int(MYSQL_CFG["port"]),
        "user": MYSQL_CFG["user"],
        "password": MYSQL_CFG["password"],
        "database": MYSQL_CFG["database"],
        "charset": "utf8mb4",
        "autocommit": True,
    }
    if dict_cursor:
        kwargs["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**kwargs)


def _ensure_alert_table() -> None:
    conn = _connect_mysql()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pest_disease_alerts (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    alert_key VARCHAR(255) NOT NULL,
                    point VARCHAR(64) NOT NULL,
                    monitor_date DATE NOT NULL,
                    item_key VARCHAR(64) NOT NULL,
                    item_name VARCHAR(64) NOT NULL,
                    item_value DECIMAL(12,2) NOT NULL,
                    threshold_value DECIMAL(12,2) NOT NULL,
                    unit VARCHAR(16) NOT NULL,
                    message_text TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                    attempts INT NOT NULL DEFAULT 0,
                    next_retry_at DATETIME NULL,
                    last_error TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP NULL,
                    UNIQUE KEY uk_pest_disease_alert (alert_key),
                    KEY idx_pest_disease_alert_retry (
                        status, attempts, next_retry_at
                    )
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    finally:
        conn.close()


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_number(value: Any) -> str:
    number = _to_float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _danger_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        ("leaf_blight", "细菌性叶枯病", "BacterialLeafBlightRate", 50, "%", "rate"),
        ("leaf_brown_spot", "褐斑病", "BrownSpotRate", 50, "%", "rate"),
        ("leaf_tungro", "东格鲁病害", "TungroVirusRate", 50, "%", "rate"),
        ("pest_borer", "二化螟", "PestScsNum", 2, "只", "count"),
        ("pest_planthopper", "褐飞虱", "PestRphNum", 2, "只", "count"),
        ("pest_leafroller", "稻纵卷叶螟", "PestCmNum", 2, "只", "count"),
    ]
    result: list[dict[str, Any]] = []
    for item_key, item_name, field, threshold, unit, value_type in specs:
        value: float | int
        if value_type == "count":
            value = _to_int(record.get(field))
        else:
            value = _to_float(record.get(field))
        if value < threshold:
            continue
        result.append(
            {
                "key": item_key,
                "name": item_name,
                "value": value,
                "threshold": threshold,
                "unit": unit,
            }
        )
    return result


def _build_message(record: dict[str, Any], item: dict[str, Any]) -> str:
    return "\n".join(
        [
            "🔴 病虫害红色告警",
            f"站点：{record['point']}",
            f"日期：{record['Date']}",
            f"病虫害：{item['name']}",
            f"监测值：{_format_number(item['value'])}{item['unit']}",
            f"红色阈值：{_format_number(item['threshold'])}{item['unit']}",
        ]
    )


def _discover_today_alerts() -> int:
    conn = _connect_mysql(dict_cursor=True)
    inserted = 0
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT point, `Date`,
                       BacterialLeafBlightRate, BrownSpotRate, TungroVirusRate,
                       PestRphNum, PestScsNum, PestCmNum
                FROM pest_disease_monitoring
                WHERE `Date` = CURDATE()
                ORDER BY point ASC
                """
            )
            records = cursor.fetchall() or []
            for record in records:
                for item in _danger_items(record):
                    alert_key = "|".join(
                        [
                            str(record["Date"]),
                            str(record["point"]),
                            str(item["key"]),
                            "danger",
                        ]
                    )
                    cursor.execute(
                        """
                        INSERT IGNORE INTO pest_disease_alerts (
                            alert_key, point, monitor_date,
                            item_key, item_name, item_value,
                            threshold_value, unit, message_text
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            alert_key,
                            record["point"],
                            record["Date"],
                            item["key"],
                            item["name"],
                            item["value"],
                            item["threshold"],
                            item["unit"],
                            _build_message(record, item),
                        ),
                    )
                    inserted += max(0, cursor.rowcount)
    finally:
        conn.close()
    return inserted


def _send_astrbot_message(message_text: str) -> None:
    _, base_url, api_key, umos, _, timeout_seconds = _astrbot_settings()
    for umo in umos:
        body = json.dumps(
            {
                "umo": umo,
                "message": [{"type": "plain", "text": message_text}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib_request.Request(
            f"{base_url}/api/v1/im/message",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"AstrBot HTTP {exc.code}: {error_body}") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"AstrBot 连接失败: {exc.reason}") from exc

        try:
            result = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"AstrBot 返回非 JSON: {response_body[:300]}") from exc
        if result.get("status") != "ok":
            raise RuntimeError(f"AstrBot 发送失败: {response_body[:500]}")


def _retry_delay_seconds(attempts_after_failure: int) -> int:
    delays = [10, 30, 120, 600, 1800]
    index = min(max(attempts_after_failure - 1, 0), len(delays) - 1)
    return delays[index]


def _process_pending_alerts() -> int:
    conn = _connect_mysql(dict_cursor=True)
    sent = 0
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, point, item_name, message_text, attempts
                FROM pest_disease_alerts
                WHERE status IN ('PENDING', 'FAILED')
                  AND attempts < 5
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY id ASC
                LIMIT 50
                """
            )
            alerts = cursor.fetchall() or []

            for alert in alerts:
                alert_id = int(alert["id"])
                cursor.execute(
                    """
                    UPDATE pest_disease_alerts
                    SET status = 'SENDING'
                    WHERE id = %s AND status IN ('PENDING', 'FAILED')
                    """,
                    (alert_id,),
                )
                if cursor.rowcount != 1:
                    continue

                try:
                    _send_astrbot_message(str(alert["message_text"]))
                except Exception as exc:
                    attempts = _to_int(alert.get("attempts")) + 1
                    retry_delay = _retry_delay_seconds(attempts)
                    cursor.execute(
                        """
                        UPDATE pest_disease_alerts
                        SET status = 'FAILED', attempts = %s,
                            next_retry_at = DATE_ADD(NOW(), INTERVAL %s SECOND),
                            last_error = %s
                        WHERE id = %s
                        """,
                        (attempts, retry_delay, str(exc)[:2000], alert_id),
                    )
                    logger.warning(
                        "微信告警发送失败: id=%s 站点=%s 病虫害=%s error=%s",
                        alert_id,
                        alert["point"],
                        alert["item_name"],
                        exc,
                    )
                    continue

                cursor.execute(
                    """
                    UPDATE pest_disease_alerts
                    SET status = 'SENT', attempts = attempts + 1,
                        next_retry_at = NULL, last_error = NULL,
                        sent_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
                sent += 1
                logger.info(
                    "微信告警发送成功: id=%s 站点=%s 病虫害=%s",
                    alert_id,
                    alert["point"],
                    alert["item_name"],
                )
    finally:
        conn.close()
    return sent


def run_once() -> tuple[int, int]:
    _ensure_alert_table()
    discovered = _discover_today_alerts()
    sent = _process_pending_alerts()
    return discovered, sent


def main() -> None:
    _validate_astrbot_settings()
    _, _, _, umos, poll_interval, _ = _astrbot_settings()
    logger.info(
        "病虫害微信告警服务已启动: 轮询=%s秒 接收人=%s",
        poll_interval,
        len(umos),
    )
    while True:
        try:
            discovered, sent = run_once()
            if discovered or sent:
                logger.info("本轮完成: 新告警=%s 已发送=%s", discovered, sent)
        except Exception:
            logger.exception("病虫害告警轮询失败")
        time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        if "--test-message" in sys.argv[1:]:
            _validate_astrbot_settings()
            _send_astrbot_message(
                "🔴 病虫害自动告警程序联调测试\n"
                "这不是实际告警，仅用于验证独立告警程序可以发送中文微信。"
            )
            logger.info("AstrBot 微信测试消息发送成功")
        elif "--once" in sys.argv[1:]:
            _validate_astrbot_settings()
            discovered_count, sent_count = run_once()
            logger.info(
                "单次执行完成: 新告警=%s 已发送=%s",
                discovered_count,
                sent_count,
            )
        else:
            main()
    except KeyboardInterrupt:
        logger.info("病虫害微信告警服务已停止")
