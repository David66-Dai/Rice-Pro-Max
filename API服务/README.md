# API Service

该目录用于存放前端识别功能对应的后端 API。

## 目录结构

- API 服务：`D:\智慧农业\api_service`
- 权重目录：`D:\智慧农业\api_service\model_weights`
  - 叶害：`model_weights/leaf/best_model.pt`
  - 虫害：`model_weights/pest/best.pt`

## 作用

- 加载叶害训练模型：`model_weights/leaf/best_model.pt`
- 加载虫害训练模型：`model_weights/pest/best.pt`
- 对外提供接口：
  - `POST /api/diagnosis/leaf`
  - `POST /api/diagnosis/pest`
  - `POST /api/monitoring/record`
  - `GET /api/health`

## 启动

```bash
cd D:\智慧农业\api_service
python -m pip install -r requirements.txt
python app.py
```

默认监听：`0.0.0.0:8080`

前端已通过 Vite 代理转发 `/api` 到该地址，无需改前端请求地址。

## 病虫害监测记录入库

`POST /api/monitoring/record` 接收以下字段并执行双写：

- 本地落盘：`api_service/data/monitoring_records.csv`
- 按“日期+站点”单独 JSON：`api_service/data/monitoring_json/{YYYY-MM-DD}/{ST-xxx}.json`
- MySQL 入库：`pest_disease_monitoring` 表（自动建表）

字段：

- `point`
- `Date`（`YYYY-MM-DD`）
- `GrowthPeriod`
- `GrowthStatus`
- `BacterialLeafBlightRate`
- `BrownSpotRate`
- `TungroVirusRate`
- `PestRphNum`
- `PestScsNum`
- `PestCmNum`

### 巡检状态持久化口径（累计不覆盖）

`GET /api/monitoring/state` 在读取某日数据时，按“站点 + 日期”聚合该日全部记录，对六个巡检项分别取最高风险级别：

- 风险优先级：`danger > warn > normal`
- 三个叶害（细菌性叶枯病、褐斑病、东格鲁病害）独立累计
- 三个虫害（二化螟、褐飞虱、稻纵卷叶螟）独立累计

这意味着同一天内多次识别会叠加保留历史最高风险，不会因后一次识别未命中而把前一次结果降级。

## 按站点 JSON 持久化与前端读取

- 每次 `POST /api/monitoring/record` 成功时，都会把该条记录追加到对应文件：
  - `api_service/data/monitoring_json/{YYYY-MM-DD}/{ST-xxx}.json`
- 单个 JSON 文件包含：
  - `point`、`Date`
  - `records`（当天该站点全部识别记录）
  - `mergedInspectItems`（六个巡检项累计后的最高风险结果）
  - `updatedAt`
- 前端继续调用 `GET /api/monitoring/state?date=YYYY-MM-DD`，后端会优先读取这些 JSON 文件进行聚合返回；JSON 缺失时再回退到 MySQL/CSV。

MySQL 连接可通过环境变量配置：

- `MYSQL_HOST`（默认 `127.0.0.1`）
- `MYSQL_PORT`（默认 `3306`）
- `MYSQL_USER`（默认 `root`）
- `MYSQL_PASSWORD`（默认空）
- `MYSQL_DATABASE`（默认 `smart_agri`）

## 请求参数

- `file`: 图片文件（multipart/form-data）
- `stationCode`: 站点编码（可选）

## 返回示例

```json
{
  "label": "细菌性叶枯病",
  "confidence": 0.93,
  "module": "leaf",
  "stationCode": "ST-008"
}
```

## 正常 / 警告 / 严重判定算法

前端会把每个巡检项（病害或虫害）判定为 `normal`、`warn`、`danger`，界面分别显示为“正常 / 预警（警告）/ 严重”。

### 1) 叶害判定

- 初始状态：`leaf_blight`、`leaf_brown_spot`、`leaf_tungro` 都先置为 `normal`。
- 若识别结果为健康叶（`hasLeafDamage=false`），保持 `normal`。
- 若识别到病害，则按病种映射风险等级：
  - 细菌性叶枯病（`Bacterial Leaf Blight` / `细菌性叶枯病`）=> `danger`（严重）
  - 东格鲁病毒（`Tungro Virus` / `东格鲁病毒`）=> `danger`（严重）
  - 褐斑病（`Brown Spot` / `褐斑病`）=> `warn`（预警/警告）
  - 未命中的病害类型默认 `warn`（预警/警告）

### 2) 虫害判定

虫害按单类虫口数量阈值判定（`二化螟`、`稻纵卷叶螟`、`褐飞虱` 分别独立计算）：

- `count >= 3` => `danger`（严重）
- `1 <= count < 3` => `warn`（预警/警告）
- `count = 0` => `normal`（正常）

### 3) 站点综合等级判定

站点综合风险等级取该站点所有巡检项中的最高等级：

- 优先级：`danger > warn > normal`
- 只要任一项为 `danger`，站点即为严重；否则若任一项为 `warn`，站点为预警/警告；其余为正常。

## 环境分析指数算法（前端当前实现）

以下算法当前在前端 `rice_pro_max/src/App.vue` 中计算，用于“环境分析”面板的两个指数展示。  
如果后端后续需要统一口径，可按同一规则迁移到 API 层。

### 通用评分函数

单指标评分采用“最适区间 + 容忍区间”：

- 输入：`value`, `idealMin`, `idealMax`, `toleranceMin`, `toleranceMax`
- 规则：
  - `value < toleranceMin` 或 `value > toleranceMax`，得分 `20`
  - `idealMin <= value <= idealMax`，得分 `100`
  - 在容忍区间内但不在最适区间，按线性插值在 `[20, 100]` 之间计算

可表示为：

- 左侧过低区间（`toleranceMin <= value < idealMin`）  
  `score = 20 + (value - toleranceMin) / (idealMin - toleranceMin) * 80`
- 右侧过高区间（`idealMax < value <= toleranceMax`）  
  `score = 20 + (toleranceMax - value) / (toleranceMax - idealMax) * 80`

最终可四舍五入为整数分，并限制在 `0~100`。

### 风险惩罚项

站点综合风险等级（`normal/warn/danger`）会引入惩罚：

- `normal` => `0`
- `warn` => `10`
- `danger` => `22`

### 1) 作物健康指数（Crop Health Index）

先计算气象加权得分：

- 空气温度 `avgAirTemp`：权重 `0.30`，最适 `[24, 32]`，容忍 `[18, 38]`
- 相对湿度 `relativeHumidity`：权重 `0.30`，最适 `[65, 85]`，容忍 `[45, 95]`
- 日照时长 `sunshineHours`：权重 `0.20`，最适 `[4, 8]`，容忍 `[2, 11]`
- 平均风速 `avgWindSpeed`：权重 `0.20`，最适 `[0.8, 2.5]`，容忍 `[0.2, 5]`

加权平均：

`climateScore = Σ(score_i * weight_i) / Σ(weight_i)`

再扣除风险惩罚：

`cropHealthIndex = clamp(round(climateScore - riskPenalty), 0, 100)`

### 2) 土壤活性指数（Soil Activity Index）

先计算土壤加权得分：

- 土壤水分 `moisture`：权重 `0.35`，最适 `[35, 70]`，容忍 `[20, 90]`
- 土壤酸碱度 `soilAcidity`：权重 `0.25`，最适 `[5.8, 6.8]`，容忍 `[5.0, 7.8]`
- 土壤有机质 `soilOrganicMatter`：权重 `0.20`，最适 `[3.5, 6.0]`，容忍 `[2.0, 8.5]`
- 土壤电导率 `soilConductivity`：权重 `0.20`，最适 `[0.6, 1.4]`，容忍 `[0.2, 2.4]`

加权平均：

`soilScore = Σ(score_i * weight_i) / Σ(weight_i)`

风险惩罚按较低强度计入（`0.4` 倍）：

`soilActivityIndex = clamp(round(soilScore - riskPenalty * 0.4), 0, 100)`

## 决策推演动态算法（预计产量 / 恢复产量 / 生长阶段）

以下规则已在前端 `rice_pro_max/src/App.vue` 落地为动态计算，替代原先按站点编号线性拼接的演示值。

### 1) 生长阶段（GrowthPeriod）

按“日期 + 温度修正”推导生育期：

- 月份基础阶段映射：
  - 1~2月：`育秧返青期`
  - 3~4月：`分蘖期`
  - 5~6月：`拔节孕穗期`
  - 7月：`抽穗扬花期`
  - 8~9月：`灌浆结实期`
  - 10~11月：`成熟期`
  - 12月：`育秧返青期`
- 温度修正：
  - 若 `avgAirTemp >= 31` 且当月日期 `>= 15`，阶段前推 1 档
  - 若 `avgAirTemp <= 22` 且当月日期 `<= 15`，阶段后退 1 档

> 说明：这是在缺少播栽日期、品种和积温数据时的可运行近似方案；后续可升级为“播栽日期 + GDD 有效积温”。

### 2) 预计产量（Expected Yield）

采用“潜力产量 × 环境因子 × 生育期因子 × 病虫害保护因子”：

1. 潜力产量（kg/亩）：

`Y_potential = clamp(450 + 18*soilOrganicMatter + 1.2*(soilPhosphorus-30) + 0.18*(soilPotassium-180), 420, 680)`

2. 环境因子（0~1）：

- `cropHealthIndex`、`soilActivityIndex` 先归一化到 `[0,1]`
- `K_env = 0.55 * norm(cropHealthIndex) + 0.45 * norm(soilActivityIndex)`

3. 生育期因子（示例配置）：

- 育秧返青期 `0.86`
- 分蘖期 `0.92`
- 拔节孕穗期 `0.97`
- 抽穗扬花期 `1.00`
- 灌浆结实期 `1.02`
- 成熟期 `1.01`

4. 病虫害保护因子：

- 叶害压力（每项）：
  - `danger += 0.22`
  - `warn += 0.10`
- 虫害压力（每项）：
  - `danger += 0.24`
  - `warn += 0.11`
- 站点综合风险附加压力：
  - `danger += 0.12`
  - `warn += 0.06`
- 汇总压力：

`stress = clamp(0.55 * diseaseStress + 0.45 * pestStress + riskStress, 0, 0.58)`

`K_protect = 1 - stress`

5. 预计产量：

`ExpectedYield = Y_potential * K_env * StageFactor * K_protect`

### 3) 恢复产量（Recovery Yield）

恢复产量为“执行防治后情景”的重算产量：

- 叶害压力下降：`diseaseStress * 0.62`
- 虫害压力下降：`pestStress * 0.56`
- 风险附加压力下降：`riskStress * 0.70`
- 改善后压力：

`improvedStress = clamp(0.55 * improvedDiseaseStress + 0.45 * improvedPestStress + improvedRiskStress, 0, 0.42)`

`K_protect_improved = 1 - improvedStress`

`RecoveryYield = Y_potential * K_env * StageFactor * K_protect_improved`

最终对展示结果做边界约束：

- `ExpectedYield` 限制在 `220~680 kg/亩`
- `RecoveryYield` 限制在 `[ExpectedYield, 700] kg/亩`

---

说明：上述阈值与权重是当前业务规则参数，后续可按不同作物、生育期（如分蘖期、抽穗期）做动态配置。
