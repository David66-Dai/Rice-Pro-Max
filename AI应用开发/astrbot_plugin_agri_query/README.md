# 智慧农业对话查询插件

这是一个独立的 AstrBot 插件，用于让管理人员通过微信自然语言查询 MySQL 中的病虫害监测数据和告警发送状态。

插件不会修改 `app.py`、算法模型、前端或 `alert_worker.py`，也不会向数据库写入数据。所有 SQL 都是固定的参数化 `SELECT` 查询。

LLM工具会将查询结果返回给AstrBot Agent，由AI整理为自然语言后再回复；不会把原始JSON直接发送给微信。

## 查询工具

- `query_station_monitoring`：查询某个站点某一天的数据。
- `query_all_monitoring_by_date`：查询某一天全部站点的数据。
- `query_monitoring_history`：查询某个站点一段时间的历史数据。
- `query_red_alerts`：查询某个站点或全部站点的红色告警。
- `query_alert_status`：查询微信告警的发送状态与失败原因。

数据来源：

- `pest_disease_monitoring`
- `pest_disease_alerts`

## 安装

1. 将整个 `astrbot_plugin_agri_query` 文件夹压缩为 ZIP。
2. 打开 AstrBot WebUI，进入“插件”。
3. 点击右下角 `+`，选择“文件上传”，上传 ZIP。
4. AstrBot 会根据 `requirements.txt` 安装 PyMySQL。
5. 进入插件配置，填写 MySQL 地址、端口、只读账号、密码和数据库名称。
6. 在 `allowed_umos` 中添加允许查询的微信会话 UMO。
7. 保存配置后重载插件。

如果不知道当前会话的 UMO，可先发送：

```text
/agri_query_status
```

未配置白名单时，插件会拒绝查询，并在回复中显示当前 UMO。

如需绕过AI直接验证监测表查询是否正常，可发送：

```text
/agri_query_all 2026-08-24
```

该指令会直接返回当日记录数和红色站点，不依赖模型是否支持工具调用。

## 建议创建只读数据库账号

下面的 SQL 需要由 MySQL 管理员执行，请替换密码和连接来源：

```sql
CREATE USER 'agri_ai_reader'@'%' IDENTIFIED BY '请替换为强密码';

GRANT SELECT ON rice_pro_max.pest_disease_monitoring
TO 'agri_ai_reader'@'%';

GRANT SELECT ON rice_pro_max.pest_disease_alerts
TO 'agri_ai_reader'@'%';

FLUSH PRIVILEGES;
```

如果 AstrBot 和 MySQL 位于固定服务器，建议将 `%` 替换成 AstrBot 服务器的 IP。

## AstrBot 人格提示词补充

```text
你是智慧农业病虫害对话告警助手。

当用户询问真实的站点监测数据、历史病虫害数据、红色告警或微信告警发送状态时，必须先调用对应的农业数据库工具，禁止根据历史对话猜测或编造数据。

用户没有提供日期时，默认查询当天。用户没有提供站点且查询工具需要站点时，应先询问站点编号。查询全部站点红色告警时，将 point 参数设置为 ALL。

用户要求查询某一天全部站点的病虫害监测数据时，必须调用 query_all_monitoring_by_date，不要要求用户粘贴原始数据。

回答时说明数据日期、站点、病虫害名称、监测值、红色阈值和发送状态。数据库没有记录时，直接说明没有查询到数据。不得展示数据库密码、连接信息、原始SQL或系统内部配置。
```

## 测试问题

安装并启用工具后，可以在微信中询问：

```text
查询今天 ST-002 的病虫害数据。
查询 2026-08-24 全部站点的病虫害数据。
查询 ST-002 最近七天的历史数据。
查询今天全部站点的红色告警。
ST-002 今天的微信告警发送成功了吗？
```

说明：`pest_disease_monitoring` 可以查询表中已有的历史监测数据；`pest_disease_alerts` 只能查询自动告警功能启用后实际生成的告警记录。
