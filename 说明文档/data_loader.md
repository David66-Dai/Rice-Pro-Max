# RiceDataLoader 类调用文档

`code/重构/data_loader.py` 中定义了一个 `RiceDataLoader` 类，统一负责**从 Hive 服务器读取**水稻智慧农业项目所需的全部数据，并按各模块需要做预处理，最终返回干净的 `pandas.DataFrame`。

> 设计目标：让 `disease.py / weather.py / soil.py / rice_yield.py` **不再依赖本地 CSV 文件**，而是统一通过 `RiceDataLoader` 从 Hive 拿数据。一处实例化、各处复用，构造函数只填一次连接信息，业务方法只传业务参数。

---

## 1. 总览

| 项 | 说明 |
| --- | --- |
| 类名 | `RiceDataLoader` |
| 数据源 | Hive（通过 SQLAlchemy + PyHive 协议连接） |
| 核心方法 | `load_weather()` / `load_disease()` / `load_soil()` / `load_yield()` |
| 当前状态 | ✅ `load_weather()` 已完整实现；其余 3 个方法以 `NotImplementedError` 占位，后续按同范式补 |
| 返回值 | `pandas.DataFrame`，可直接喂给现有的 `disease / weather / soil / rice_yield` 模块 |

---

## 2. 数据流总图

```
┌──────────────┐  pyhive    ┌────────────┐  pandas      ┌─────────────────┐
│  Hive 数据仓 │──────────▶ │ SQLAlchemy │ ───────────▶│ RiceDataLoader  │
│  (小时气象、  │  read_sql  │  Engine    │              │ ① 类型清洗       │
│   病虫害、土壤、│           └────────────┘              │ ② 时间加权聚合   │
│   产量等表)   │                                        │ ③ 列名/排序整理  │
└──────────────┘                                        └────────┬────────┘
                                                                 │ DataFrame
                                                                 ▼
                                       disease.py / weather.py / soil.py /
                                       rice_yield.py 等业务模块直接使用
```

---

## 3. 安装依赖

```bash
pip install sqlalchemy "pyhive[hive]"
```

> **Windows 用户特别注意**：`pyhive[hive]` 会拉 `sasl`，该包没有 Windows 预编译 wheel，会要求本地有 C++ 编译器。两种绕过方式（任选其一）：
>
> 1. 改用纯 Python 实现：`pip install pure-sasl thrift_sasl`
> 2. 把 Hive 服务端 `auth` 改为 `NOSASL` / `LDAP`，直接绕开 sasl 依赖

---

## 4. 导入方式

```python
from data_loader import RiceDataLoader
```

> 文件位置：`code/重构/data_loader.py`，与 `disease.py / weather.py / soil.py / rice_yield.py / hdfs_put.py` 同目录，可直接同包 import。

---

## 5. 建立连接（实例化）

```python
RiceDataLoader(
    host: str,
    port: int = 10000,
    user: str = "hive",
    database: str = "default",
    password: str | None = None,
    auth: str = "NOSASL",
    kerberos_service_name: str = "hive",
    table_weather_hour: str | None = None,
    weather_columns: dict[str, str] | None = None,
)
```

### 5.1 构造参数

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `host` | `str` | 必填 | Hive Server2 主机名或 IP |
| `port` | `int` | `10000` | Hive Server2 端口（HiveServer2 标准端口） |
| `user` | `str` | `"hive"` | 登录用户名 |
| `database` | `str` | `"default"` | 默认查询的 database/schema |
| `password` | `str \| None` | `None` | LDAP 认证时必填；`NOSASL` / `KERBEROS` 模式下忽略 |
| `auth` | `str` | `"NOSASL"` | 认证模式：`NOSASL` / `LDAP` / `KERBEROS`（不区分大小写） |
| `kerberos_service_name` | `str` | `"hive"` | 仅在 `auth="KERBEROS"` 时生效 |
| `table_weather_hour` | `str \| None` | `None` | 小时气象表名覆盖；`None` 时使用类常量 `TABLE_WEATHER_HOUR="weather_hour"` |
| `weather_columns` | `dict[str,str] \| None` | `None` | 气象表列名映射覆盖（详见 §7） |

### 5.2 三种认证模式示例

```python
# ① NOSASL（无认证，最常见的开发环境）
loader = RiceDataLoader(
    host="192.168.x.x",
    port=10000,
    user="hive",
    database="rice_db",
    auth="NOSASL",
)

# ② LDAP（生产环境常见）
loader = RiceDataLoader(
    host="hive.company.com",
    user="danglong",
    password="********",
    database="rice_db",
    auth="LDAP",
)

# ③ KERBEROS（企业级安全部署）
loader = RiceDataLoader(
    host="hive.company.com",
    database="rice_db",
    auth="KERBEROS",
    kerberos_service_name="hive",
)
```

> 实例化后**不会立即连 Hive**——`engine` 属性是懒加载的，只在第一次调用 `load_xxx()` 时才真正建立连接。

---

## 6. 实例方法

### 6.1 `loader.load_weather()` — 小时气象 → 日尺度气象（已实现）

#### 签名

```python
loader.load_weather() -> pd.DataFrame
```

#### 行为

读取 Hive 表 `table_weather_hour`（默认 `weather_hour`），按"站点 × 日期"聚合为日尺度，返回干净的 `DataFrame`。

#### 聚合规则（遵循气象观测规范）

时间权重（每天 4 个观测时刻，合计 24 小时）：

| 观测时刻 | 权重 | 覆盖时段 |
| --- | --- | --- |
| Hour 1 | 5.5h | 22:00 – 04:00 |
| Hour 7 | 6.0h | 04:00 – 10:00 |
| Hour 13 | 6.5h | 10:00 – 16:30 |
| Hour 20 | 6.0h | 16:30 – 22:00 |

各字段处理方式：

| 字段类型 | 处理方式 |
| --- | --- |
| 日照时长 | 求和（各时段累计） |
| 风向（二级 / 八级） | 取众数（出现最多的方向，等频时取首个） |
| 风向（14时 / 20时观测） | 取 `Hour=13` / `Hour=20` 的对应值 |
| 日均风速 / 日平均气温 / 日平均湿度 / 日平均气压 | 时间加权平均（NaN 安全） |
| 日降水量 | 求和（`"T"` / `"t"` 微量降水按 `0.05mm` 计入） |
| 日最高气温 / 日最低气温 | 取 `max` / `min` |

#### 返回值列说明（默认列名 · 全小写）

> ⚠ **特别说明**：日期列在 Hive 里叫 `weather_date`，但本方法返回前会统一重命名为 `date`，以兼容 `weather.py` 中既有的字段约定。其余列名直接沿用 Hive 列名（全小写），无需再做 rename。

| 列名 | 含义 |
| --- | --- |
| `point` | 站点编号 |
| `date` | 日期（Hive 列 `weather_date` 自动重命名而来） |
| `sunshineduration` | 日照时长（小时） |
| `winddirection_02` / `winddirection_08` | 风向（二级 / 八级分类，字符串众数） |
| `winddirection_14` / `winddirection_20` | 风向（14时 / 20时观测） |
| `dailyaveragewind` | 日均风速（m/s，加权平均） |
| `dailyprecipitation` | 日降水量（mm，求和） |
| `dailymaximumtemperature` / `dailyminimumtemperature` | 日最高/最低气温（℃） |
| `dailyaveragetemperature` | 日平均气温（℃，加权平均） |
| `dailyrelativehumidity` | 日平均相对湿度（%，加权平均） |
| `dailyaveragepressure` | 日平均气压（hPa，加权平均） |

数值列均保留 2 位小数；结果按 `(站点 升序, 日期 正序)` 稳定排序。

#### 示例

```python
with RiceDataLoader(host="192.168.x.x", database="rice_db") as loader:
    weather_df = loader.load_weather()
    print(weather_df.head())
    print(f"共 {len(weather_df)} 行 · {weather_df['point'].nunique()} 个站点")
```

---

### 6.2 `loader.load_disease() / load_soil() / load_yield()` — 占位

```python
loader.load_disease()  # raise NotImplementedError("load_disease() 待实现")
loader.load_soil()     # raise NotImplementedError("load_soil() 待实现")
loader.load_yield()    # raise NotImplementedError("load_yield() 待实现")
```

> 这三个方法是**为后续扩展预留的接口**，当前会直接抛 `NotImplementedError`。实现范式与 `load_weather()` 一致：
>
> 1. 用类常量 `TABLE_PEST` / `TABLE_SOIL` / `TABLE_YIELD` 定位 Hive 表；
> 2. `pd.read_sql(sql, self.engine)` 读取；
> 3. 按业务规则做清洗（病虫害一般不聚合按日取值；土壤可能也无需聚合；产量按年份分列）；
> 4. 返回与现有 `disease.py / soil.py / rice_yield.py` 兼容的 `DataFrame`。

---

## 7. 表名 / 列名定制（最常见踩坑点）

### 7.1 表名不一致

```python
loader = RiceDataLoader(
    host="...",
    database="rice_db",
    table_weather_hour="dwd_weather_hourly",   # 改这里
)
```

### 7.2 列名不一致

代码内置一份"业务键 → Hive 列名"默认映射，存放于类常量 `DEFAULT_WEATHER_COLUMNS`（Hive 默认列名是 case-insensitive、返回时统一小写，所以这里全部使用小写）：

| 业务键 | 默认 Hive 列名 |
| --- | --- |
| `point` | `point` |
| `date` | `weather_date` |
| `hour` | `hour` |
| `sunshine` | `sunshineduration` |
| `wind_02` / `wind_08` / `wind_14` / `wind_20` | `winddirection_02 / _08 / _14 / _20` |
| `avg_wind` | `dailyaveragewind` |
| `precip` | `dailyprecipitation` |
| `max_temp` / `min_temp` | `dailymaximumtemperature / dailyminimumtemperature` |
| `avg_temp` | `dailyaveragetemperature` |
| `humidity` | `dailyrelativehumidity` |
| `pressure` | `dailyaveragepressure` |

如果你的 Hive 表实际列名不一致，**只需覆盖不同的那几项**，其他保持默认：

```python
loader = RiceDataLoader(
    host="...",
    database="rice_db",
    weather_columns={
        "sunshine":  "sun_dur",                # 实际列名是 sun_dur
        "max_temp":  "t_max",
        "min_temp":  "t_min",
        # 其他字段会继续用默认映射，不必全部列出
    },
)
```

> 如果必需列在 Hive 表里**完全不存在**，方法会抛 `ValueError("Hive 表 ... 缺少必需列: [...]")`，错误信息会明确告诉你缺哪几列。

---

## 8. 与现有项目的衔接

### 8.1 在 `main.py` 里替换本地 CSV 加载

**改造前**（本地 CSV）：

```python
def load_resources() -> PipelineResources:
    return PipelineResources(
        management_df=pd.read_csv("./data/management_data.csv"),
        weather_df=load_weather_data("./data/monitor_data.csv"),
        soil_df=load_soil_data("./data/soil_data.csv"),
        yield_df=load_yield_data("./data/pre_rice_yield.csv"),
        ...
    )
```

**改造后**（Hive 数据源）：

```python
from data_loader import RiceDataLoader

def load_resources() -> PipelineResources:
    loader = RiceDataLoader(
        host="192.168.x.x", port=10000,
        user="hive", database="rice_db",
        auth="NOSASL",
    )
    return PipelineResources(
        management_df=loader.load_disease(),    # 等 load_disease 实现后启用
        weather_df=loader.load_weather(),
        soil_df=loader.load_soil(),             # 等 load_soil    实现后启用
        yield_df=loader.load_yield(),           # 等 load_yield   实现后启用
        ...
    )
```

> 下游 `disease.py / weather.py / soil.py / rice_yield.py` 完全**不用改**，因为它们只接受 `DataFrame` 参数，不关心来源。

### 8.2 单数据源测试

```python
from data_loader import RiceDataLoader

with RiceDataLoader(host="...", database="rice_db") as loader:
    df = loader.load_weather()
    df.to_csv("monitor_data_from_hive.csv", index=False, encoding="utf-8-sig")
```

可以用此命令对比 Hive 抽出的数据与本地 `monitor_data.csv` 是否一致。

---

## 9. 资源管理

支持上下文管理器（推荐）：

```python
with RiceDataLoader(host="...", database="rice_db") as loader:
    df1 = loader.load_weather()
    # df2 = loader.load_disease()
# 退出 with 块时自动 close()，释放连接池
```

也可以手动管理：

```python
loader = RiceDataLoader(host="...", database="rice_db")
try:
    df = loader.load_weather()
finally:
    loader.close()
```

---

## 10. 可能的异常

| 异常类型 | 触发场景 |
| --- | --- |
| `ValueError` | LDAP 模式未传 `password`；Hive 表缺少必需列 |
| `sqlalchemy.exc.OperationalError` | Hive 服务不可达 / 认证失败 / database 不存在 |
| `sqlalchemy.exc.ProgrammingError` | SQL 执行失败（表名错误、列名错误等） |
| `NotImplementedError` | 调用了尚未实现的 `load_disease / load_soil / load_yield` |
| `ImportError` | 未安装 `sqlalchemy` 或 `pyhive` |

---

## 11. 小贴士

- **懒加载**：`engine` 是 `@property`，构造时不会立即连 Hive，第一次调用 `load_xxx()` 才建立连接。
- **复用一个实例**：整个进程只需一个 `RiceDataLoader` 实例，所有 `load_xxx()` 方法共享 engine 和连接池。
- **必传字段最少化**：使用上下文管理器并仅传 `host` / `database` 这两个最关键的参数，其他默认值能 cover 80% 场景。
- **列名覆盖只写差异**：`weather_columns={...}` 只需要写**与默认值不同的字段**，未写的会自动继承默认映射。
- **聚合在 Python 端**：本类**没有用 Hive SQL 写 GROUP BY**，因为"时间加权 + NaN 安全 + 风向众数"用 SQL 实现起来既冗长又难调；改放到 Python 用 pandas 向量化做更清晰。
- **后续扩展**：补 `load_disease / load_soil / load_yield` 时，照搬 `load_weather` 结构即可——读 Hive、做清洗、返回 DataFrame，三步走。

---

## 12. 完整使用示例

```python
from data_loader import RiceDataLoader
import requests
from main import build_inputs, run_final_workflow, parse_json_like
from hdfs_put import hdfs

TARGET_DATE = "2025-05-08"
HDFS_PATH   = f"/rice/output/{TARGET_DATE}"

with RiceDataLoader(
    host="192.168.x.x",
    port=10000,
    user="hive",
    database="rice_db",
    auth="NOSASL",
) as loader:
    weather_df = loader.load_weather()
    # disease_df = loader.load_disease()  # TODO
    # soil_df    = loader.load_soil()     # TODO
    # yield_df   = loader.load_yield()    # TODO

    print(f"气象数据：{len(weather_df)} 行 · "
          f"{weather_df['point'].nunique()} 个站点 · "
          f"{weather_df['date'].nunique()} 个日期")
    print(weather_df.head())
```

---

## 13. 后续扩展模板（写给未来的自己）

实现 `load_disease()` 时可参考下面的范式：

```python
def load_disease(self) -> pd.DataFrame:
    sql = f"SELECT * FROM {self.table_pest}"          # ① 读 Hive
    df = pd.read_sql(sql, self.engine)

    # ② 业务清洗（按需调整 · Hive 列名实际是全小写）
    df['date'] = pd.to_datetime(df['date'], errors="coerce").dt.normalize()
    df['point'] = df['point'].astype(str)
    # ……可参照 disease.py 中已有的字段约定（必要时 rename 成大写以兼容下游模块）

    # ③ 返回直接可被 disease.disease() 使用的 DataFrame
    return df
```

`load_soil()` / `load_yield()` 同理。
