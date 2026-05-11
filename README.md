# 🌾 智慧农业 — 水稻病虫害智能诊断与监测平台

基于深度学习的**水稻叶害识别**与**虫害检测**综合平台，集成了算法训练、后端 API 服务、前端可视化大屏、AI 工作流管道，实现从"图像采集 → AI 诊断 → 风险评级 → 监测入库 → 决策推演"的全链路智慧农业解决方案。

---

## 📁 项目结构

```
Rice-Pro-Max/
├── README.md                              # 项目总览
├── conf/                                  # 配置文件（密码/密钥，Git 忽略）
│   ├── config.json                        #   后端统一配置
│   └── frontend.json                      #   前端 HDFS 地址
│
├── 算法开发/                               # 模型训练与算法实验
│   ├── 演示路线图.md                       #   竞赛演示路线图（8~10 分钟）
│   ├── 虫害算法开发/                       #   YOLO11x 水稻害虫检测（3 类）
│   │   ├── train.py                       #     训练脚本
│   │   ├── predict.py                     #     CLI 推理脚本
│   │   ├── gradio_app.py                  #     Gradio Web 演示
│   │   ├── data/dataset.yaml              #     数据集配置
│   │   └── Test/                          #     测试图片
│   └── 叶害算法开发/                       #   ResNet18 叶片病害分类（4 类）
│       ├── train.py                       #     训练脚本（迁移学习）
│       ├── predict.py                     #     CLI 推理脚本
│       └── Original Image/                #     原始数据集（按类别分文件夹）
│
├── API服务/                               # FastAPI 后端服务
│   ├── app.py                             #   主服务（模型推理 + 监测 API + 站点数据）
│   ├── requirements.txt                   #   Python 依赖
│   ├── model_weights/                     #   模型权重
│   │   ├── leaf/best_model.pt             #     叶害分类
│   │   └── pest/best.pt                   #     虫害检测
│   ├── data/                              #   监测数据持久化
│   ├── readhdfs/                          #   HDFS 浏览器服务（部署在 Hadoop 节点）
│   │   ├── read_hdfs.py                   #     FastAPI 服务
│   │   └── README.md                      #     部署文档
│   ├── 叶害识别测试图片/                    #
│   └── 虫害识别测试图片/                    #
│
├── 前端开发/                               # Vue 3 前端大屏
│   ├── index.html                         #   入口
│   ├── vite.config.js                     #   Vite 配置（代理 + @conf alias）
│   ├── src/
│   │   ├── App.vue                        #   主组件（全部业务逻辑）
│   │   ├── api/agriDiagnosis.js           #   API 封装（诊断/HDFS/站点/监测）
│   │   └── components/
│   │       ├── HelloWorld.vue             #   欢迎页
│   │       └── HistoryCharts.vue          #   ECharts 历史图表
│   ├── chart_data/                        #   图表静态数据
│   └── public/                            #   静态资源
│
├── 数据处理/                               # 数据入库与清洗
│   ├── scripts/data_pipeline.py           #   统一流水线（天气→土壤→清洗）
│   ├── data/                              #   原始 CSV 数据
│   └── cols.txt                           #   列名对照
│
└── AI应用开发/                             # Dify 工作流管道
    ├── code/                              #   核心 Python 模块
    │   ├── main.py                        #     主流水线（Hive→Dify→HDFS）
    │   ├── main_ys.py                     #     原始版流水线
    │   ├── disease.py                     #     病虫害分析
    │   ├── weather.py                     #     气象分析
    │   ├── soil.py                        #     土壤分析
    │   ├── rice_yield.py                  #     产量多因子预测
    │   ├── hdfs_put.py                    #     WebHDFS 客户端
    │   └── hive_data.py                   #     Hive 数据加载器
    ├── api/                               #   Dify 工作流密钥（Git 忽略）
    ├── 示例json/                           #   HDFS 输出示例
    └── 说明文档/                           #   模块文档
```

---

## 🧠 技术栈

| 模块 | 技术 | 说明 |
|------|------|------|
| 虫害检测 | YOLO11x + Ultralytics | 3 类害虫目标检测 |
| 叶害分类 | ResNet18 + PyTorch | 4 类叶片图像分类（迁移学习） |
| 后端 API | FastAPI + Uvicorn | 模型推理、监测记录、站点实时/历史数据 |
| 前端大屏 | Vue 3 + Vite + ECharts | 25 站点交互式监测看板 |
| HDFS 数据读取 | FastAPI（独立部署） | 部署于 Hadoop 节点，通过 `hdfs dfs` 读取 |
| 数据管道 | Dify Workflow | 病虫害→气象→土壤→综合分析 四工作流编排 |
| 产量预测 | 多因子乘法修正 | 基线 × f(病害) × f(虫害) × f(土壤) × f(气象) × f(生长) |
| 数据仓库 | Hive（PyHive + SQLAlchemy） | 气象/病虫害/土壤/产量数据统一加载 |
| 数据存储 | WebHDFS REST API | 管道结果上传至 HDFS |
| 数据持久化 | MySQL + CSV + JSON | 三级存储 |
| 配置管理 | JSON 配置文件 | `conf/config.json` 统一管理所有密码和密钥 |

---

## 🔍 识别能力

### 虫害检测（3 类）

| ID | 中文名 | 学名 |
|----|--------|------|
| 0 | 二化螟 | Striped Stem Borer |
| 1 | 稻纵卷叶螟 | Rice Leaf Roller |
| 2 | 褐飞虱 | Brown Planthopper |

### 叶害分类（4 类）

| 英文类别 | 中文名 | 风险 |
|----------|--------|------|
| Bacterial Leaf Blight | 细菌性叶枯病 | 🔴 严重 |
| Brown Spot | 褐斑病 | 🟡 预警 |
| Healthy Leaf | 健康叶片 | 🟢 正常 |
| Tungro Virus | 东格鲁病毒 | 🔴 严重 |

---

## 🚀 快速启动

### 前提

- Python ≥ 3.10，Node.js ≥ 18
- 复制 `conf/config.json.example` 为 `conf/config.json` 并填入实际配置

### 1. 后端 API

```bash
cd API服务
pip install -r requirements.txt
python app.py          # 默认 http://0.0.0.0:8080
```

### 2. 前端大屏

```bash
cd 前端开发
npm install
npm run dev            # 默认 http://127.0.0.1:5173
```

Vite 自动代理 `/api` → `http://127.0.0.1:8080`，前端直连 `192.168.157.130:8000` 读取 HDFS。

### 3. 数据处理

```bash
cd 数据处理/scripts
python data_pipeline.py           # 自动执行全部步骤
python data_pipeline.py weather   # 仅天气
python data_pipeline.py soil      # 仅土壤
```

### 4. AI 管道

```bash
cd AI应用开发/code
python main.py        # 运行完整 Dify 工作流管道
```

### 5. 模型训练（可选）

```bash
cd 算法开发/叶害算法开发
python train.py --epochs 30 --batch-size 16

cd 算法开发/虫害算法开发
python train.py
```

---

## 🔌 API 端点

### 诊断服务（app.py）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/diagnosis/leaf` | POST | 叶害识别（上传图片） |
| `/api/diagnosis/pest` | POST | 虫害检测（上传图片） |
| `/api/monitoring/record` | POST | 提交监测记录 |
| `/api/monitoring/state` | GET | 查询某日全部站点巡检状态 |
| `/api/station/{code}/realtime` | GET | 站点实时气象+土壤数据 |
| `/api/station/{code}/history` | GET | 站点全年月度聚合历史数据 |

### HDFS 浏览器（read_hdfs.py，部署于 Hadoop 节点 :8000）

| 端点 | 说明 |
|------|------|
| `/api/dates` | 列出所有可用日期 |
| `/api/{date}/points` | 列出某日期下的站点 |
| `/api/{date}/{point}/all.json` | **推荐**——读取单站点全部结果（1 次 HDFS 操作） |
| `/api/{date}/{point}/{filename}` | 读取单个 JSON 文件 |
| `/api/hdfs/list?path=` | 通用 HDFS 目录浏览 |

---

## 📊 前端功能

### 监测大屏

- **25 个站点** 分布在水稻背景图上，站点颜色反映风险等级（绿/黄/红）
- 年/月/日三级时间线，北京时间实时显示
- 站点详情：编号、运行状态、最后上报时间

### 图像识别

- 上传叶片 → ResNet18 诊断病害类型
- 上传虫害图 → YOLO 检测并标注害虫位置和数量
- 识别结果自动绑定当前站点，更新风险等级，同步到后端三级存储

### 田间巡检 → 环境分析 → 决策推演（右侧三大模块）

- **巡检面板**：6 项指标独立追踪（3 叶害 + 3 虫害），累计不覆盖
- **环境面板**：作物健康指数 + 土壤活性指数，加权评分 + 风险惩罚
- **决策面板**：预计产量 / 恢复产量 / 生长阶段 / 方案 A&B
- **详情弹窗**：点击"详情"查看 HDFS 真实数据（Dify 工作流分析结果）
- **防治建议**：详情弹窗内点击按钮，弹出完整防治建议报告
- **方案弹窗**：可折叠阶段下拉框，展开显示每个病虫害的化学/农业/人工具体操作

### 历史图表

- 5 张 ECharts 图表：总产量趋势、站点排名、日照、降水、气温

---

## 📈 风险判定

| 类型 | danger（严重） | warn（预警） | normal（正常） |
|------|:----------:|:---------:|:------:|
| 叶害覆盖率 | ≥ 50% | > 0% | 0% |
| 虫害数量 | ≥ 3 只 | 1-2 只 | 0 只 |

站点综合评级 = 所有巡检项中最高风险等级。

---

## 🔗 数据流架构

```
┌──────────────────────────────────────────────┐
│              前端 Vue 3 (:5173)               │
│  大屏 / 识别 / 巡检 / 环境 / 决策 / 历史图表    │
└──────┬───────────────────────┬───────────────┘
       │ /api (Vite 代理)       │ 直连 :8000
       ▼                        ▼
┌──────────────┐     ┌──────────────────┐
│  FastAPI     │     │  readhdfs 服务    │
│  (:8080)     │     │  (Hadoop 节点)    │
│              │     │  hdfs dfs -cat   │
│  模型推理    │     └────────┬─────────┘
│  监测记录    │              │
│  站点数据    │              ▼
└──┬───┬───┬──┘     ┌──────────────┐
   │   │   │        │    HDFS      │
   ▼   ▼   ▼        │ /rice/output │
┌────┐ ┌──┐ ┌────┐  └──────────────┘
│CVS │ │  │ │    │
│JSON│ │  │ │    │        ┌──────────────────┐
│    │ │  │ │    │        │  AI 管道 (main.py) │
│    │ │  │ │    │        │  Hive → Dify →    │
│    │ │  │ │    │        │  4 Workflow → HDFS │
└────┘ └──┘ └────┘        └──────────────────┘
```

---

## 👨‍💻 配置说明

所有密码和密钥集中在 `conf/config.json`，该目录已加入 `.gitignore`：

```json
{
  "mysql": { "host": "...", "port": 3306, "user": "...", "password": "...", "database": "..." },
  "hdfs":  { "host": "...", "port": 9870, "user": "...", "output_path": "/rice/output" },
  "hive":  { "host": "...", "port": 10000, "user": "...", "database": "..." },
  "dify":  { "disease": { "base_url": "...", "api_key": "..." }, ... }
}
```

前端配置 `conf/frontend.json`：

```json
{ "hdfs_api_base": "http://192.168.157.130:8000" }
```

---

## 📋 更新日志

### 2026-05-11

- 配置外置：所有密码与密钥迁移至 `conf/config.json`，`conf/` 加入 `.gitignore`
- 新增 `/api/station/{code}/realtime` 和 `/api/station/{code}/history` 端点（MySQL 实时/历史数据）
- MySQL 不可用时优雅降级，返回空数据而非 500
- 前端 10 个指标卡片、健康指数、决策推演优先使用 MySQL 真实值
- `parse_json_like` 容错 Dify LLM 输出的非标准 JSON（未加引号的值自动修复）
- 历史图表从静态硬编码改为按站点+年份查询

### 2026-05-10

- 前端集成 HDFS 数据：详情弹窗 + 防治建议子弹窗 + 可折叠方案阶段
- 决策推演产量从 HDFS 读取，切换站点即时清空 + 请求竞态保护
- 管道优化：5 个 JSON 合并为 `all.json`，读写从 6 次降为 1 次
- 管道新增 output3（方案B）提取
- 路径修复：`__file__` 绝对路径，解决 VSCode 执行目录不一致
