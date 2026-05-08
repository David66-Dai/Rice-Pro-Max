# hdfs 类调用文档

`hdfs_put.py` 中定义了一个 `hdfs` 类，基于 WebHDFS REST API 封装了常用的 HDFS 操作（建目录、上传 JSON、上传本地文件）。

**新版使用方式：**先实例化 `hdfs(...)` 建立连接配置（只填一次主机、端口、用户名等公共参数），后续通过实例方法 `client.mkdirs(...)` / `client.upload_json(...)` / `client.upload_file(...)` 调用，**只需传业务相关参数即可**。

---

## 1. 导入方式

```python
from hdfs_put import hdfs
```

---

## 2. 建立连接（实例化）

```python
hdfs(
    namenode_host: str,
    namenode_port: int = 9870,
    user: str = "hdfs",
    timeout: int = 30,
)
```

**构造参数：**

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `namenode_host` | `str` | 必填 | NameNode 的主机名或 IP，例如 `"192.168.157.130"` |
| `namenode_port` | `int` | `9870` | NameNode 的 WebHDFS 端口 |
| `user` | `str` | `"hdfs"` | 代理用户名（`user.name` 参数），例如 `"root"` |
| `timeout` | `int` | `30` | 默认请求超时（秒）；各方法可单独覆盖（`upload_file` 默认至少 60s） |

**示例：**

```python
from hdfs_put import hdfs

client = hdfs(
    namenode_host="192.168.157.130",
    namenode_port=9870,
    user="root",
)
```

实例 `client` 保存了连接信息，后续所有方法调用都会复用它，无需再传主机/端口/用户名。

---

## 3. 实例方法

### 3.1 `client.mkdirs(...)` — 创建 HDFS 目录

**签名：**

```python
client.mkdirs(
    hdfs_dir: str,
    error_if_exists: bool = False,
    timeout: int | None = None,
) -> None
```

**参数：**

- `hdfs_dir`：要创建的 HDFS 目录绝对路径（支持多级，自动递归创建）。必须以 `/` 开头。
- `error_if_exists`：目录已存在时的处理策略，**默认 `False`**。
  - `False`：幂等行为，目录已存在也不报错（与 WebHDFS `MKDIRS` 默认语义一致）。
  - `True`：先调用 `op=GETFILESTATUS` 探测，若目录已存在则抛出 `FileExistsError`。
- `timeout`：本次调用的超时时间（秒），`None` 表示使用实例默认 `self.timeout`。

**行为：**

- 当 `error_if_exists=True` 时：
  1. 先发 `GET ?op=GETFILESTATUS` 检查目录是否存在。
  2. 返回 `200` → 目录已存在，抛 `FileExistsError`。
  3. 返回 `404` → 目录不存在，继续下一步。
  4. 其他非 2xx 状态 → 抛 `requests.HTTPError`。
- 调用 WebHDFS 的 `op=MKDIRS`；若响应的 `boolean` 不为 `True` 则抛 `RuntimeError`。
- HTTP 错误（非 2xx）会抛 `requests.HTTPError`。

**示例：**

```python
client.mkdirs("/user/danglong/rice/output")

try:
    client.mkdirs("/user/danglong/rice/output", error_if_exists=True)
except FileExistsError as e:
    print(f"目录已存在，跳过创建: {e}")
```

---

### 3.2 `client.upload_json(...)` — 上传 dict 为 JSON 文件

**签名：**

```python
client.upload_json(
    data: dict[str, Any],
    hdfs_path: str,
    overwrite: bool = True,
    timeout: int | None = None,
) -> None
```

**参数：**

- `data`：要上传的 Python 字典。内部会使用 `json.dumps(data, ensure_ascii=False, indent=2)` 序列化后以 UTF-8 写入。
- `hdfs_path`：HDFS 上的**文件**绝对路径（含文件名），例如 `/rice/output/2025-05-08/point_1/disease_output.json`。
- `overwrite`：是否覆盖已有文件，默认 `True`。
- `timeout`：本次调用的超时时间（秒），`None` 表示使用实例默认 `self.timeout`。

**行为：**

- 走 WebHDFS 标准的两步 `CREATE` 流程：先请求 NameNode 拿到 307 重定向到 DataNode，再把数据 PUT 到 DataNode。
- `Content-Type` 为 `application/json; charset=utf-8`。
- 任一步 HTTP 失败（非 2xx/307）都会抛 `RuntimeError` 或 `requests.HTTPError`。

**示例：**

```python
payload = {
    "point": "point_1",
    "date": "2025-05-08",
    "output1": "示例输出1",
}

client.upload_json(
    payload,
    "/user/danglong/rice/output/2025-05-08/point_1/disease_output.json",
    overwrite=True,
)
```

---

### 3.3 `client.upload_file(...)` — 上传本地文件到 HDFS

**签名：**

```python
client.upload_file(
    local_file_path: str,
    hdfs_path: str,
    overwrite: bool = True,
    timeout: int | None = None,
) -> None
```

**参数：**

- `local_file_path`：本地文件路径（以二进制方式读取，支持任意文件类型）。
- `hdfs_path`：HDFS 上的目标文件绝对路径（含文件名）。
- `overwrite`：是否覆盖已有文件，默认 `True`。
- `timeout`：本次调用的超时时间（秒），`None` 表示使用 `max(self.timeout, 60)`（大文件可显式传更大值）。

**行为：**

- 同样走两步 `CREATE` 流程，`Content-Type` 为 `application/octet-stream`。
- 使用流式 `open(..., "rb")` 读取并传输。

**示例：**

```python
client.upload_file(
    local_file_path=r".\code\重构\main.py",
    hdfs_path="/user/danglong/rice/output/ceshi.py",
    overwrite=True,
)
```

---

### 3.4 内部工具方法（一般无需调用）

- `client._build_url(hdfs_path, query)`：拼接 WebHDFS 请求 URL，格式为 `http://{host}:{port}/webhdfs/v1{hdfs_path}?{query}`。若 `hdfs_path` 不以 `/` 开头会抛 `ValueError`。
- `client._with_user(query)`：自动在查询字符串末尾追加 `&user.name={user}`。

---

## 4. 完整使用示例

```python
from hdfs_put import hdfs

HOST = "192.168.157.130"
PORT = 9870
USER = "root"
HDFS_DIR = "/user/danglong/rice/output/2025-05-08"

client = hdfs(namenode_host=HOST, namenode_port=PORT, user=USER)

client.mkdirs(HDFS_DIR)

client.upload_json(
    {"point": "point_1", "output": "示例"},
    f"{HDFS_DIR}/point_1/disease_output.json",
)

client.upload_file(
    local_file_path=r".\code\重构\main.py",
    hdfs_path=f"{HDFS_DIR}/main.py",
    overwrite=True,
)
```

---

## 5. 可能的异常

| 异常类型 | 触发场景 |
| --- | --- |
| `ValueError` | `hdfs_path` / `hdfs_dir` 不是以 `/` 开头的绝对路径 |
| `requests.HTTPError` | HTTP 响应返回非 2xx 状态（`raise_for_status()`） |
| `RuntimeError` | `mkdirs` 响应 `boolean != True`；或 `CREATE` 第一步状态码不是 201/307；或未拿到 DataNode 的 `Location` 重定向地址 |
| `requests.Timeout` | 请求超时（可调大 `timeout` 参数） |
| `FileNotFoundError` | `upload_file` 指定的本地文件不存在 |
| `FileExistsError` | `mkdirs` 在 `error_if_exists=True` 时检测到目录已存在 |

---

## 6. 小贴士

- 一次性实例化一个 `client`，整个脚本/进程复用即可，无需每次传 host/port/user。
- 默认 `mkdirs` 是幂等的（目录已存在不报错）；如需"已存在则报错"的严格模式，传 `error_if_exists=True`。
- 路径必须是 HDFS 的绝对路径（以 `/` 开头），不要误传 Windows/Linux 本地路径。
- 大文件上传可在调用时显式传 `timeout=...` 覆盖实例默认超时。
- 如果 NameNode 启用了 HA，需要连接 active 的那台；本类暂不处理自动切换。

---

## 7. 从旧版（静态方法）迁移

**旧写法（每次都要重复传 host/port/user）：**

```python
hdfs.mkdirs(HDFS_PATH, namenode_host=HOST, namenode_port=PORT, user=USER)
hdfs.upload_json(data, hdfs_path, namenode_host=HOST, namenode_port=PORT, user=USER)
```

**新写法（建立连接后只传业务参数）：**

```python
client = hdfs(namenode_host=HOST, namenode_port=PORT, user=USER)
client.mkdirs(HDFS_PATH)
client.upload_json(data, hdfs_path)
```
