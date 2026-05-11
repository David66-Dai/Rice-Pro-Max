# 🌾 智慧农业 — 水稻病虫害智能诊断与监测平台

基于深度学习的**水稻叶害识别**与**虫害检测**综合平台，集成了算法训练、后端 API 服务、前端可视化大屏，实现从"图像采集 → AI 诊断 → 风险评级 → 监测入库 → 决策推演"的全链路智慧农业解决方案。

---

## 📁 项目结构

```
Rice-Pro-Max/
├── README.md                              # 项目总览（本文件）
│
├── 算法开发/                               # 模型训练与算法实验
│   ├── 演示路线图.md                       #   竞赛演示路线图（8~10分钟）
│   ├── 虫害算法开发/                       #   YOLO11x 水稻害虫检测
│   │   ├── train.py                       #     训练脚本
│   │   ├── predict.py                     #     CLI 推理脚本
│   │   ├── gradio_app.py                  #     Gradio 可视化测试页面
│   │   ├── requirements.txt               #     Python 依赖
│   │   ├── data/                          #     数据集
│   │   │   ├── dataset.yaml               #       数据集配置（3 类害虫）
│   │   │   ├── images/train/              #       训练图片
│   │   │   ├── images/val/                #       验证图片
│   │   │   └── labels/train/              #       YOLO 格式标注
│   │   └── Test/                          #     虫害测试图片
│   │       ├── 二化螟.png
│   │       ├── 稻纵卷叶螟.png
│   │       └── 褐飞虱.png
│   │
│   └── 叶害算法开发/                       #   ResNet18 水稻叶片病害分类
│       ├── train.py                       #     训练脚本
│       ├── predict.py                     #     CLI 推理脚本
│       ├── requirements.txt               #     Python 依赖
│       ├── Test/                          #     叶害测试图片
│       └── Original Image/                #     原始数据集（按类别分文件夹）
│           ├── Bacterial Leaf Blight/     #       细菌性叶枯病
│           ├── Brown Spot/                #       褐斑病
│           ├── Healthy Leaf/              #       健康叶片
│           └── Tungro Virus/              #       东格鲁病毒
│
├── API服务/                               # FastAPI 后端服务
│   ├── app.py                             #   主服务入口（含所有 API）
│   ├── requirements.txt                   #   Python 依赖
│   ├── README.md                          #   后端文档
│   ├── model_weights/                     #   模型权重（供 API 加载）
│   │   ├── leaf/best_model.pt             #     叶害分类模型
│   │   └── pest/best.pt                   #     虫害检测模型
│   ├── data/                              #   监测数据持久化
│   │   ├── monitoring_records.csv         #     CSV 记录
│   │   └── monitoring_json/               #     按日期+站点的 JSON
│   ├── 叶害识别测试图片/                    #   叶害测试图片
│   └── 虫害识别测试图片/                    #   虫害测试图片
│
├── 数据处理/                               # 数据入库与清洗流水线
│   ├── scripts/
│   │   └── data_pipeline.py                #   统一流水线（双击自动执行全流程）
│   ├── data/
│   │   ├── weather_hour.csv                #     天气小时原始数据
│   │   └── soil_data.csv                   #     土壤日观测原始数据
│   ├── cols.txt                            #   天气 CSV 列名对照
│   └── requirements.txt                    #   Python 依赖
│
├── 前端开发/                               # Vue 3 前端大屏
│   ├── index.html                         #   入口 HTML
│   ├── package.json                       #   Node 依赖
│   ├── vite.config.js                     #   Vite 配置（含 API 代理）
│   ├── README.md                          #   前端文档
│   ├── chart_data/                        #   图表静态数据
│   │   ├── chart1_total_yield.csv         #     总产量趋势
│   │   ├── chart2_station_avg_yield.csv   #     站点平均产量
│   │   ├── chart3_sunshine.csv            #     日照数据
│   │   ├── chart4_rainfall.csv            #     降雨数据
│   │   └── chart5_temperature.csv         #     温度数据
│   ├── public/                            #   公共静态资源
│   └── src/
│       ├── main.js                        #   应用入口
│       ├── App.vue                        #   主组件（核心业务逻辑）
│       ├── style.css                      #   全局样式
│       ├── api/
│       │   └── agriDiagnosis.js           #   后端 API 调用封装
│       ├── assets/                        #   静态资源（稻田背景图等）
│       └── components/
│           ├── HelloWorld.vue             #   欢迎页组件
│           └── HistoryCharts.vue          #   历史数据图表组件
│
└── AI应用开发/                             # AI应用集成与数据管道
    ├── code/                              #   核心 Python 模块
    │   ├── main.py                        #     主流水线入口（Dify 编排）
    │   ├── main_ys.py                     #     原始版主流水线
    │   ├── disease.py                     #     病虫害数据分析模块
    │   ├── weather.py                     #     气象数据接入模块
    │   ├── soil.py                        #     土壤分析模块
    │   ├── rice_yield.py                  #     水稻产量多因子预测模型
    │   ├── hdfs_put.py                    #     HDFS WebHDFS 上传客户端
    │   └── hive_data.py                   #     Hive 数据加载器
    ├── api/                               #   Dify Workflow API 配置
    │   ├── workflow_api_01.json           #     病虫害分析工作流
    │   ├── workflow_api_02.json           #     气象分析工作流
    │   ├── workflow_api_03.json           #     土壤分析工作流
    │   └── workflow_api_04.json           #     综合分析工作流
    └── 说明文档/                           #   模块使用文档
        ├── data_loader.md                 #     RiceDataLoader 调用说明
        └── hdfs_put.md                    #     HDFS 客户端调用说明
```

---

## 🧠 核心技术

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| **虫害检测** | YOLO11x + Ultralytics | 目标检测，识别 3 类水稻害虫（二化螟/稻纵卷叶螟/褐飞虱） |
| **叶害分类** | ResNet18 + PyTorch | 图像分类，识别 4 种叶片状态（迁移学习） |
| **后端 API** | FastAPI + Uvicorn | RESTful 接口，支持图片上传诊断与监测记录管理 |
| **前端大屏** | Vue 3 + Vite | 交互式稻田监测看板，28 站点可视化 |
| **数据管道** | Dify Workflow | 多工作流编排：病虫害→气象→土壤→综合分析 |
| **产量预测** | 多因子乘法修正模型 | 基于病害/虫害/土壤/气象/生长 5 因子动态预测 |
| **数据加载** | SQLAlchemy + PyHive | 从 Hive 数据仓库统一读取气象/病虫害/土壤/产量表 |
| **数据存储** | WebHDFS REST API | JSON 结果上传至 HDFS 分布式文件系统 |
| **数据持久化** | CSV + JSON + MySQL | 三级存储，双写保障 |
| **推理加速** | CUDA / CPU | 自动检测 GPU 可用性 |

---

## 🔍 识别能力

### 虫害检测（3 类）

| 类别 ID | 中文名 | 学名/俗称 |
|---------|--------|-----------|
| 0 | 二化螟 | Striped Stem Borer |
| 1 | 稻纵卷叶螟 | Rice Leaf Roller |
| 2 | 褐飞虱 | Brown Planthopper |

### 叶害分类（4 类）

| 英文类别 | 中文名 | 风险等级 |
|----------|--------|----------|
| Bacterial Leaf Blight | 细菌性叶枯病 | 🔴 严重 (danger) |
| Brown Spot | 褐斑病 | 🟡 预警 (warn) |
| Healthy Leaf | 健康叶片 | 🟢 正常 (normal) |
| Tungro Virus | 东格鲁病毒 | 🔴 严重 (danger) |

---

## 🚀 快速启动

### 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 18
- **CUDA**（可选，用于 GPU 加速）
- **MySQL**（可选，用于数据库持久化）

### 1. 启动后端 API 服务

```bash
cd API服务

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认监听 0.0.0.0:8080）
python app.py
```

API 服务启动后，可通过以下端点访问：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/diagnosis/leaf` | POST | 叶害识别（上传图片） |
| `/api/diagnosis/pest` | POST | 虫害检测（上传图片） |
| `/api/monitoring/record` | POST | 提交监测记录 |
| `/api/monitoring/state` | GET | 查询某日监测状态 |

### 2. 启动前端大屏

```bash
cd 前端开发

# 安装依赖
npm install

# 启动开发服务器（默认 http://127.0.0.1:5173）
npm run dev

# 生产构建
npm run build
```

前端通过 Vite 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8080`。

### 3. 模型训练（可选）

**虫害检测训练：**

```bash
cd 算法开发/虫害算法开发

# 安装依赖
pip install -r requirements.txt

# 开始训练（使用 YOLO11x 预训练权重）
python train.py
```

**叶害分类训练：**

```bash
cd 算法开发/叶害算法开发

# 安装依赖
pip install -r requirements.txt

# 开始训练（使用 ResNet18 ImageNet 预训练权重）
python train.py --epochs 30 --batch-size 16
```

### 4. 虫害检测 Gradio 演示

```bash
cd 算法开发/虫害算法开发
python gradio_app.py
# 浏览器打开 http://127.0.0.1:7860
```

---

## 📊 前端功能

### 稻田监测大屏

- **25 个监测站点** 分布在稻田地图上，每个站点可点击查看详情
- **站点状态指示灯**：🟢 正常 / 🟡 预警 / 🔴 严重
- **北京时间实时显示**

### 图像识别

- **叶害识别**：上传水稻叶片图片，AI 自动诊断病害类型
- **虫害检测**：上传田间图片，YOLO 模型标注害虫位置和数量
- 识别结果自动与当前站点绑定，更新风险等级

### 环境分析

- **作物健康指数**：综合气温、湿度、日照、风速的加权评分
- **土壤活性指数**：综合水分、酸碱度、有机质、电导率的加权评分
- 风险惩罚机制：病虫害越严重，指数越低

### 决策推演

- **预计产量**：结合环境因子、生长阶段、病虫害胁迫动态计算
- **恢复产量**：模拟采取防治措施后的预期恢复产量
- **生长阶段**：基于日历和温度动态推算（育秧返青期 → 成熟期）
- **防治方案**：
  - **方案 A（虫害压制）**：虫口密度复核 → 定点喷施 → 复测 → 环境清理
  - **方案 B（病害抑制）**：病斑抽样 → 分区施药 → 水肥管控 → 复判

### 巡检记录

- 按日期查看历史巡检数据
- 6 个巡检项独立追踪：3 个叶害 + 3 个虫害
- **累计不覆盖**：同一天多次识别叠加保留历史最高风险
- 数据自动同步到后端持久化存储

---

## 🗄️ 数据持久化

系统采用三级存储策略：

1. **CSV 文件**：`API服务/data/monitoring_records.csv`，追加写入
2. **JSON 文件**：`API服务/data/monitoring_json/{日期}/{站点}.json`，按站点聚合
3. **MySQL 数据库**（可选）：自动建表 `pest_disease_monitoring`，通过环境变量配置连接

### MySQL 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYSQL_HOST` | `127.0.0.1` | 数据库地址 |
| `MYSQL_PORT` | `3306` | 数据库端口 |
| `MYSQL_USER` | `root` | 数据库用户 |
| `MYSQL_PASSWORD` | `123456` | 数据库密码 |
| `MYSQL_DATABASE` | `rice_pro_max` | 数据库名称 |

---

## 📈 风险判定算法

### 叶害风险

| 病害 | 阈值 ≥ 50% | 阈值 > 0% | 未检出 |
|------|:----------:|:---------:|:------:|
| 细菌性叶枯病 | 🔴 danger | 🟡 warn | 🟢 normal |
| 东格鲁病毒 | 🔴 danger | 🟡 warn | 🟢 normal |
| 褐斑病 | 🔴 danger | 🟡 warn | 🟢 normal |

### 虫害风险

| 虫口数量 | 风险等级 |
|----------|----------|
| ≥ 3 只 | 🔴 danger |
| 1-2 只 | 🟡 warn |
| 0 只 | 🟢 normal |

### 站点综合评级

取该站点所有巡检项中的**最高风险等级**：`danger > warn > normal`

---

## 🔗 AI应用集成 — Dify 工作流管道

`AI应用开发/code/` 目录包含一套完整的 **Dify 多工作流编排管道**，实现从原始数据到分析结果的自动化处理链路。

### 工作流执行流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Workflow │───▶│ Workflow │───▶│ Workflow │───▶│ Workflow │
│   01     │    │   02     │    │   03     │    │   04     │
│ 病虫害分析 │    │ 气象分析  │    │ 土壤分析  │    │ 综合分析  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │               │               │
      ▼               ▼               ▼               ▼
  disease.py      weather.py      soil.py        main.py
  (病害/虫害)      (日照/温湿度)    (有机质/pH)     (汇总+产量预测)
```

### 核心模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| **病虫害分析** | `disease.py` | 叶害覆盖率计算（白叶枯/褐斑/东格鲁）+ 虫害数量统计（稻飞虱/二化螟/稻纵卷叶螟） |
| **气象接入** | `weather.py` | 日均温度/湿度/日照/降水/风速/气压多维度气象数据处理 |
| **土壤分析** | `soil.py` | 有机质/pH/磷/钾/电导率综合土壤肥力评估 |
| **产量预测** | `rice_yield.py` | 五因子乘法修正模型：产量 = 基线产量 × f(病害) × f(虫害) × f(土壤) × f(气象) × f(生长) |
| **HDFS 上传** | `hdfs_put.py` | 基于 WebHDFS REST API，支持建目录、上传 JSON、上传文件 |
| **Hive 加载** | `hive_data.py` | 通过 SQLAlchemy + PyHive 从 Hive 统一读取气象/病虫害/土壤/产量数据 |
| **主管道** | `main.py` | Dify 工作流编排入口，串联全部子模块并汇总结果 |
| **原始管道** | `main_ys.py` | 原始版主管道（不依赖 Dify 工作流，直接调用各模块） |

### 产量预测模型

$$Y_{pred} = Y_{base} \times f_{disease} \times f_{pest} \times f_{soil} \times f_{weather} \times f_{growth}$$

每个修正因子 $f \in [0.4, 1.2]$，最优条件趋近 1.0：

| 因子 | 参考最优值 | 影响机制 |
|------|-----------|----------|
| 日均温度 | 26°C | 偏离最适温度则产量下降 |
| 土壤 pH | 6.5 | 过酸/过碱限制养分吸收 |
| 有机质 | 3.0% | 有机质越高土壤肥力越强 |
| 日照时长 | 6 h/天 | 光合作用基础保障 |
| 周降水量 | 50 mm | 水分胁迫影响灌浆 |

### Hive 数据加载

```python
from AI应用开发.code.hive_data import RiceDataLoader

loader = RiceDataLoader(host="hive-server", port=10000, user="hive", database="rice_db")
weather_df = loader.load_weather()    # 小时气象 → 日尺度聚合
disease_df = loader.load_disease()    # 病虫害监测数据
soil_df    = loader.load_soil()       # 土壤理化指标
yield_df   = loader.load_yield()      # 产量基线数据
```

### HDFS 结果上传

```python
from AI应用开发.code.hdfs_put import hdfs

client = hdfs(namenode_host="namenode-host", namenode_port=9870, user="hdfs")
client.mkdirs("/user/danglong/output/site_01")
client.upload_json("/user/danglong/output/site_01/result.json", data)
```

---

## 🔧 技术架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                               │
│                   http://127.0.0.1:5173                          │
│             稻田大屏 / 图像识别 / 环境分析 / 决策推演                │
└────────────────────────┬─────────────────────────────────────────┘
                         │ /api 代理
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   后端 API (FastAPI)                              │
│                   http://127.0.0.1:8080                          │
│       叶害诊断 / 虫害检测 / 监测记录 / 状态查询 / 健康检查           │
└──────┬────────────────────────────────┬──────────────────────────┘
       │                                │
       ▼                                ▼
┌──────────────┐              ┌──────────────────┐
│   AI 模型     │              │   数据持久化       │
│              │              │                  │
│ ResNet18     │              │ CSV 文件          │
│ (叶害分类)    │              │ JSON 文件         │
│              │              │ MySQL 数据库      │
│ YOLO11x      │              │                  │
│ (虫害检测)    │              │                  │
└──────────────┘              └──────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  AI应用集成 — Dify 工作流管道                       │
│                                                                  │
│  Workflow 01 ──▶ Workflow 02 ──▶ Workflow 03 ──▶ Workflow 04    │
│   (病虫害)        (气象)          (土壤)          (综合分析)       │
│      │               │               │               │          │
│      ▼               ▼               ▼               ▼          │
│  disease.py     weather.py       soil.py         main.py        │
│                                        │                         │
│                    ┌───────────────────┼───────────────┐         │
│                    ▼                   ▼               ▼         │
│             ┌──────────┐     ┌──────────────┐  ┌──────────┐     │
│             │   Hive   │     │  rice_yield  │  │   HDFS   │     │
│             │ 数据仓库  │     │  产量预测模型  │  │ 结果存储  │     │
│             └──────────┘     └──────────────┘  └──────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📝 许可

本项目仅用于智慧农业研究与示范目的。

---

## 👨‍💻 开发说明

- 虫害检测基于 [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) 框架
- 叶害分类基于 [PyTorch](https://pytorch.org/) 和 [TorchVision](https://pytorch.org/vision/) 的 ResNet18
- 前端基于 [Vue 3](https://vuejs.org/) + [Vite](https://vitejs.dev/)
- 后端基于 [FastAPI](https://fastapi.tiangolo.com/)
- 工作流编排基于 [Dify](https://dify.ai/) 平台
- 数据仓库连接基于 [PyHive](https://github.com/dropbox/PyHive) + SQLAlchemy
- 分布式存储基于 WebHDFS REST API
- 算法竞赛演示路线图详见 `算法开发/演示路线图.md`

---

## 📋 更新日志

### 2026-05-11

**后端 API — MySQL 实时数据查询**

- 新增 `GET /api/station/{station_code}/realtime?date=YYYY-MM-DD` 端点，实时查询 `station_weather_daily` + `station_soil_daily` 两张表，返回气象 + 土壤组合数据
- 新增 `GET /api/station/{station_code}/history?year=YYYY` 端点，返回全年 12 个月的月度聚合平均值
- `_resolve_station_ids` 自动映射前端站点编码（`ST-001`）到 MySQL 多种格式（`point_1` / `1` 等）

**前端大屏 — 真实 MySQL 数据驱动**

- 10 个指标卡片（日照/风速/降水/温湿度/有机质/pH/磷/钾/电导率）从硬编码公式改为实时 MySQL 数据
- 无数据时统一显示 `--`，加载中显示半透明占位
- 作物健康指数、土壤活性指数、决策推演优先使用 MySQL 真实值，无数据时回退到公式估算
- 历史图表分析（日照/降水/气温）从静态硬编码改为按站点+年份查询 MySQL
- 前端 API 层新增 `fetchStationRealtime` 和 `fetchStationHistory` 函数

**数据处理 — 脚本合并优化**

- 4 个独立脚本（天气入库/土壤入库/日照修复/风速降水修复）合并为统一的 `数据流水线/data_pipeline.py`
- 消除 4 处重复的 `mysql_connect`、argparse、建表 SQL，抽取为共享函数
- 双击或直接 `python data_pipeline.py` 无参数运行自动执行全部步骤（天气 → 土壤 → 清洗）
- 子命令（`weather` / `soil` / `cleanup` / `all`）仍保留供单独调用
- 移除旧的 4 个独立脚本文件

### 2026-05-10

**前端大屏 — HDFS 数据集成**

- 新增 `fetchHdfsPointData` 直连 readhdfs 服务，按日期+站点读取 `all.json`
- `parseJsonLike` 增加 Dify 输出容错：自动修复 LLM 生成的未加引号值（如 `35公斤/亩` → `"35公斤/亩"`）
- 三个详情弹窗（田间巡检/环境分析/决策推演）优先展示 HDFS 真实数据
- 详情弹窗放大至 550px，底部新增"查看防治建议"按钮，弹出完整建议内容
- 方案 A/B 弹窗改为可折叠阶段下拉框，展开后显示每个病虫害的化学/农业/人工操作
- 决策推演模块预计产量、恢复产量优先从 HDFS 读取，无数据时显示 `--`
- 切换站点/日期时立即清空旧数据，请求竞态保护防止数据错乱
- 前端直连 `192.168.157.130:8000`，不经过本地代理

**数据管道 — 路径修复与性能优化**

- `main.py` / `main_ys.py` 路径改为基于 `__file__` 的绝对路径，解决 VSCode 执行目录不一致问题
- `parse_json_like` 增加 LLM 输出修复，容错非标准 JSON 值
- HDFS 写入从 5 个单独 JSON 合并为 1 个 `all.json`，读写次数从 6 次降为 1 次
- 新增 `output3`（方案B）提取与存储
