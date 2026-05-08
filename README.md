# 🌾 智慧农业 — 水稻病虫害智能诊断与监测平台

基于深度学习的**水稻叶害识别**与**虫害检测**综合平台，集成了算法训练、后端 API 服务、前端可视化大屏，实现从"图像采集 → AI 诊断 → 风险评级 → 监测入库 → 决策推演"的全链路智慧农业解决方案。

---

## 📁 项目结构

```
智慧农业/
├── README.md                          # 项目总览（本文件）
│
├── 算法开发/                           # 模型训练与算法实验
│   ├── 虫害算法开发/                   # YOLO11x 水稻害虫检测
│   │   ├── train.py                   #   训练脚本
│   │   ├── predict.py                 #   CLI 推理脚本
│   │   ├── gradio_app.py              #   Gradio 可视化测试页面
│   │   ├── requirements.txt           #   Python 依赖
│   │   ├── yolo11x.pt                 #   预训练权重（自动下载）
│   │   ├── yolo26n.pt                 #   备用权重
│   │   ├── data/                      #   数据集
│   │   │   ├── dataset.yaml           #     数据集配置（3 类害虫）
│   │   │   ├── images/train/          #     训练图片
│   │   │   ├── images/val/            #     验证图片
│   │   │   └── labels/train/         #     YOLO 格式标注
│   │   └── runs/                      #   训练输出
│   │
│   └── 叶害算法开发/                   # ResNet18 水稻叶片病害分类
│       ├── train.py                   #   训练脚本
│       ├── predict.py                 #   CLI 推理脚本
│       ├── requirements.txt           #   Python 依赖
│       ├── checkpoints/               #   模型检查点
│       │   ├── best_model.pt          #     最佳模型权重
│       │   └── best_model.json        #     模型元信息
│       └── Original Image/            #   原始数据集（按类别分文件夹）
│           ├── Bacterial Leaf Blight/ #     细菌性叶枯病
│           ├── Brown Spot/            #     褐斑病
│           ├── Healthy Leaf/          #     健康叶片
│           └── Tungro Virus/          #     东格鲁病毒
│
├── api_service/                       # FastAPI 后端服务
│   ├── app.py                         #   主服务入口（含所有 API）
│   ├── requirements.txt               #   Python 依赖
│   ├── README.md                      #   后端文档
│   ├── model_weights/                 #   模型权重（供 API 加载）
│   │   ├── leaf/best_model.pt         #     叶害分类模型
│   │   └── pest/best.pt              #     虫害检测模型
│   └── data/                          #   监测数据持久化
│       ├── monitoring_records.csv     #     CSV 记录
│       └── monitoring_json/           #     按日期+站点的 JSON
│
├── rice_pro_max/                      # Vue 3 前端大屏
│   ├── index.html                     #   入口 HTML
│   ├── package.json                   #   Node 依赖
│   ├── vite.config.js                 #   Vite 配置（含 API 代理）
│   ├── README.md                      #   前端文档
│   └── src/
│       ├── main.js                    #   应用入口
│       ├── App.vue                    #   主组件（核心业务逻辑）
│       ├── style.css                  #   全局样式
│       ├── api/
│       │   └── agriDiagnosis.js       #   后端 API 调用封装
│       └── assets/                    #   静态资源
│
├── 虫害识别测试图片/                    # 虫害测试图片
└── 叶害识别测试图片/                    # 叶害测试图片
```

---

## 🧠 核心技术

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| **虫害检测** | YOLO11x + Ultralytics | 目标检测，识别 3 类水稻害虫 |
| **叶害分类** | ResNet18 + PyTorch | 图像分类，识别 4 种叶片状态 |
| **后端 API** | FastAPI + Uvicorn | RESTful 接口，支持图片上传诊断 |
| **数据持久化** | CSV + JSON + MySQL | 三级存储，双写保障 |
| **前端大屏** | Vue 3 + Vite | 交互式稻田监测看板 |
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
cd api_service

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
cd rice_pro_max

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

- **28 个监测站点** 分布在稻田地图上，每个站点可点击查看详情
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

1. **CSV 文件**：`api_service/data/monitoring_records.csv`，追加写入
2. **JSON 文件**：`api_service/data/monitoring_json/{日期}/{站点}.json`，按站点聚合
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

## 🔧 技术架构图

```
┌──────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                       │
│               http://127.0.0.1:5173                  │
│         稻田大屏 / 图像识别 / 环境分析 / 决策推演        │
└────────────────────┬─────────────────────────────────┘
                     │ /api 代理
                     ▼
┌──────────────────────────────────────────────────────┐
│               后端 API (FastAPI)                      │
│               http://127.0.0.1:8080                  │
│   叶害诊断 / 虫害检测 / 监测记录 / 状态查询 / 健康检查   │
└──────┬────────────────────────────────┬──────────────┘
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
