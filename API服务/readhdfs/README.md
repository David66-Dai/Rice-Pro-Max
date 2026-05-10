# HDFS 文件浏览器 API 使用文档

## 一、概述

本服务基于 **FastAPI** 构建，部署在 Hadoop 集群节点上，通过 `hdfs dfs` 命令读取 HDFS 文件，以 HTTP 接口的形式向前端提供数据访问能力。

### HDFS 数据结构

```
/rice/output/
├── 2025-05-08/
│   ├── point_1/
│   │   ├── disease_output.json
│   │   ├── weather_output.json
│   │   ├── soil_output.json
│   │   ├── yield_output.json
│   │   └── main_output.json
│   ├── point_2/
│   │   └── ...
│   └── point_30/
│       └── ...
└── 2025-05-09/
    └── ...
```

### 架构

```
前端（浏览器） ──HTTP请求──▶ FastAPI 服务（Hadoop 节点） ──hdfs dfs──▶ HDFS
```

---

## 二、服务端部署

### 2.1 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Linux（CentOS / Ubuntu） |
| Python | 3.10+ |
| Hadoop | 已安装并可执行 `hdfs dfs` 命令 |
| Java | Hadoop 依赖的 JDK（通常 JDK 8 或 11） |

### 2.2 检查 Hadoop 环境

登录到 Hadoop 集群任意节点（NameNode 或 DataNode 均可），执行：

```bash
hdfs dfs -ls /
hadoop version
```

如果提示 `command not found`，需要配置环境变量。编辑 `~/.bashrc`：

```bash
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64   # 替换为实际路径
export HADOOP_HOME=/opt/hadoop                         # 替换为实际路径
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
```

生效：

```bash
source ~/.bashrc
```

### 2.3 安装 Python 依赖

```bash
pip install fastapi uvicorn
```

### 2.4 上传代码到服务器

在本地 Windows 终端执行（以 scp 为例）：

```bash
scp read_hdfs.py root@192.168.157.130:/home/root/api/
```

也可以使用 FileZilla、WinSCP 等工具上传。

### 2.5 启动服务

```bash
cd /home/root/api

# 方式一：前台运行（调试阶段使用，Ctrl+C 停止）
uvicorn read_hdfs:app --host 0.0.0.0 --port 8000

# 方式二：后台运行（正式使用）
nohup uvicorn read_hdfs:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
```

参数说明：

| 参数 | 含义 |
|---|---|
| `read_hdfs:app` | 文件名 `read_hdfs.py` 中的 `app` 对象 |
| `--host 0.0.0.0` | 允许外部网络访问（不加则只能本机访问） |
| `--port 8000` | 监听端口，可自行修改 |

### 2.6 放通防火墙端口

```bash
# CentOS / RHEL
firewall-cmd --add-port=8000/tcp --permanent
firewall-cmd --reload

# Ubuntu
ufw allow 8000
```

### 2.7 验证服务

浏览器访问以下地址（将 IP 替换为你的服务器地址）：

| 地址 | 用途 |
|---|---|
| `http://192.168.157.130:8000/docs` | Swagger 交互式 API 文档（可直接在页面测试） |
| `http://192.168.157.130:8000/api/dates` | 测试获取日期列表 |

### 2.8 停止服务

```bash
# 查找进程
ps aux | grep uvicorn

# 杀掉进程
kill <PID>
```

---

## 三、API 接口说明

> 以下示例中 `BASE_URL = http://192.168.157.130:8000`

### 3.1 业务快捷接口

#### 获取所有可用日期

```
GET /api/dates
```

返回示例：

```json
["2025-05-08", "2025-05-09"]
```

---

#### 获取某日期下所有站点

```
GET /api/{date}/points
```

示例：`GET /api/2025-05-08/points`

返回示例：

```json
["point_1", "point_2", "point_3", "...", "point_30"]
```

---

#### 一次获取某站点全部输出（最常用）

```
GET /api/{date}/{point}
```

示例：`GET /api/2025-05-08/point_1`

返回示例：

```json
{
  "disease_output": { "...": "..." },
  "weather_output": { "...": "..." },
  "soil_output": { "...": "..." },
  "yield_output": { "...": "..." },
  "main_output": { "...": "..." }
}
```

将该站点目录下所有 `.json` 文件的内容合并为一个对象返回，key 为文件名（去掉 `.json` 后缀）。

---

#### 读取单个文件

```
GET /api/{date}/{point}/{filename}
```

示例：`GET /api/2025-05-08/point_1/disease_output.json`

- `.json` 文件 → 直接返回 JSON 对象
- `.txt` / `.csv` 等文本文件 → 返回 `{"content": "文件内容..."}`
- 其他类型 → 以二进制流下载

---

### 3.2 通用浏览接口

#### 列出任意 HDFS 目录

```
GET /api/hdfs/list?path=/任意路径
```

示例：`GET /api/hdfs/list?path=/rice/output/2025-05-08`

返回示例：

```json
[
  {
    "name": "point_1",
    "path": "/rice/output/2025-05-08/point_1",
    "type": "DIRECTORY",
    "size": 0,
    "modified": "2025-05-08 14:30"
  }
]
```

---

#### 读取任意 HDFS 文件

```
GET /api/hdfs/read?path=/任意文件路径
```

示例：`GET /api/hdfs/read?path=/rice/output/2025-05-08/point_1/main_output.json`

---

## 四、前端调用示例

### 4.1 原生 fetch 写法

```javascript
const API = "http://192.168.157.130:8000";

// 获取所有日期
const dates = await fetch(`${API}/api/dates`).then(r => r.json());

// 获取某天所有站点
const points = await fetch(`${API}/api/2025-05-08/points`).then(r => r.json());

// 一次拿到 point_1 全部输出
const allData = await fetch(`${API}/api/2025-05-08/point_1`).then(r => r.json());
console.log(allData.disease_output);
console.log(allData.weather_output);
console.log(allData.main_output);

// 只读单个文件
const disease = await fetch(`${API}/api/2025-05-08/point_1/disease_output.json`).then(r => r.json());
```

### 4.2 axios 写法（Vue / React 项目）

```javascript
import axios from "axios";

const api = axios.create({ baseURL: "http://192.168.157.130:8000" });

// 获取所有日期
const { data: dates } = await api.get("/api/dates");

// 获取某天所有站点
const { data: points } = await api.get("/api/2025-05-08/points");

// 一次拿到 point_1 全部输出
const { data: allData } = await api.get("/api/2025-05-08/point_1");

// 只读单个文件
const { data: disease } = await api.get("/api/2025-05-08/point_1/disease_output.json");
```

### 4.3 查看 HDFS 目录信息

通用浏览接口 `/api/hdfs/list` 可以浏览 HDFS 上任意目录，实现类似"文件管理器"的效果。

#### fetch 写法

```javascript
const API = "http://192.168.157.130:8000";

// 列出 HDFS 根目录
const root = await fetch(`${API}/api/hdfs/list?path=/`).then(r => r.json());
console.log(root);
// → [
//   { name: "rice", path: "/rice", type: "DIRECTORY", size: 0, modified: "2025-05-08 10:00" },
//   { name: "tmp",  path: "/tmp",  type: "DIRECTORY", size: 0, modified: "2025-05-07 09:00" }
// ]

// 逐层深入浏览
const dates = await fetch(`${API}/api/hdfs/list?path=/rice/output`).then(r => r.json());
// → [{ name: "2025-05-08", path: "/rice/output/2025-05-08", type: "DIRECTORY", ... }]

const points = await fetch(`${API}/api/hdfs/list?path=/rice/output/2025-05-08`).then(r => r.json());
// → [{ name: "point_1", ... }, { name: "point_2", ... }, ...]

const files = await fetch(`${API}/api/hdfs/list?path=/rice/output/2025-05-08/point_1`).then(r => r.json());
// → [
//   { name: "disease_output.json", type: "FILE", size: 2048, ... },
//   { name: "weather_output.json", type: "FILE", size: 1536, ... },
//   ...
// ]
```

#### axios 写法

```javascript
// 列出任意目录
const { data: items } = await api.get("/api/hdfs/list", {
  params: { path: "/rice/output/2025-05-08" }
});

// 遍历结果
items.forEach(item => {
  if (item.type === "DIRECTORY") {
    console.log(`目录: ${item.name}`);
  } else {
    console.log(`文件: ${item.name} (${item.size} 字节)`);
  }
});
```

#### 返回字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 文件或目录名称 |
| `path` | string | HDFS 完整路径（可用于下一次请求） |
| `type` | string | `"DIRECTORY"` 或 `"FILE"` |
| `size` | number | 文件大小（字节），目录为 0 |
| `modified` | string | 最后修改时间 |

#### 前端实现文件浏览器的思路

用户每点击一个目录，就用该目录的 `path` 字段再请求一次 `/api/hdfs/list`，实现逐层钻入：

```javascript
let currentPath = "/";

async function enterDir(path) {
  currentPath = path;
  const items = await fetch(`${API}/api/hdfs/list?path=${encodeURIComponent(path)}`).then(r => r.json());

  items.forEach(item => {
    if (item.type === "DIRECTORY") {
      // 渲染为可点击的目录，点击后调用 enterDir(item.path)
    } else {
      // 渲染为文件，点击后调用 /api/hdfs/read?path=item.path 读取内容
    }
  });
}

// 页面加载时从根目录开始
enterDir("/");
```

点击文件时读取内容：

```javascript
async function openFile(path) {
  const data = await fetch(`${API}/api/hdfs/read?path=${encodeURIComponent(path)}`).then(r => r.json());
  console.log(data);  // JSON 文件直接得到对象，文本文件在 data.content 中
}
```

### 4.4 典型页面交互流程

```
1. 页面加载
   → GET /api/dates
   → 展示日期选择器 [2025-05-08 ▼]

2. 用户选择日期
   → GET /api/2025-05-08/points
   → 展示站点列表 / 地图标记点

3. 用户点击某个站点
   → GET /api/2025-05-08/point_1
   → 一次拿到全部数据，渲染病害、气象、土壤、产量、决策等卡片
```

---

## 五、常见问题

### Q1：访问接口返回连接被拒绝

- 检查服务是否启动：`ps aux | grep uvicorn`
- 检查防火墙端口是否放通
- 确认使用了 `--host 0.0.0.0`

### Q2：接口返回 404

- 检查 HDFS 中对应路径是否存在：`hdfs dfs -ls /rice/output`
- 检查日期、站点名格式是否正确（如 `2025-05-08`、`point_1`）

### Q3：前端报 CORS 跨域错误

代码中已配置 `allow_origins=["*"]`，正常不会出现此问题。如果仍报错，检查浏览器是否缓存了旧响应，清除缓存重试。

### Q4：读取大文件很慢

`hdfs dfs -cat` 会将整个文件读入内存。如果文件超过 100MB，建议在接口层加文件大小限制或改用流式读取。本项目的 JSON 输出通常很小，无需担心。

### Q5：如何修改 HDFS 根路径

编辑 `read_hdfs.py` 第 10 行：

```python
HDFS_ROOT = "/rice/output"  # 修改为你的实际根路径
```

重启服务即可生效。
