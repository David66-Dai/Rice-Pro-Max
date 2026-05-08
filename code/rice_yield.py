"""水稻产量多因子修正预测模型。

核心思想：以历史训练好的产量基线（pre_rice_yield.csv）为锚点，
基于实测的「病害 / 虫害 / 土壤 / 气象 / 生长状态」5 个因子做乘法修正：

    predicted_yield = base_yield × f_disease × f_pest × f_soil × f_weather × f_growth

每个因子 ∈ [0.4, 1.2]，最适条件 ≈ 1.0，越恶劣越小于 1。所有阈值常量
集中在文件顶部，便于后续基于试验数据 / 文献调参。

向后兼容：只传 yield_df 时退化为"直接返回基线"的旧行为。
"""

from typing import Optional

import pandas as pd


# ============================================================================
# 农学经验常量（可根据当地试验数据进一步标定）
# ============================================================================
OPTIMAL_TEMP        = 26.0     # 水稻日均最适温度 ℃
OPTIMAL_PH          = 6.5      # 最适土壤 pH
OPTIMAL_OM_PERCENT  = 3.0      # 适中有机质百分比 %
OPTIMAL_P_PPM       = 15.0     # 适中速效磷 ppm
OPTIMAL_K_PPM       = 200.0    # 适中速效钾 ppm
OPTIMAL_EC          = 1.0      # 健康电导率上限 dS/m（盐胁迫起点）
OPTIMAL_DAILY_SUN   = 6.0      # 适中日照 h/天
OPTIMAL_WEEKLY_RAIN = 50.0     # 适中近 7 日累计降水 mm

# 生长状态人工标注 → 修正系数
GROWTH_STATUS_MAP = {
    "良好": 1.00,
    "一般": 0.95,
    "较差": 0.85,
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ============================================================================
# 五个修正因子（每个独立可调参 / 可单测）
# ============================================================================
def _disease_factor(blight, spot, virus) -> float:
    """叶害修正：三种叶害覆盖率累加 → 光合面积损失 → 减产。

    总覆盖率 100% 时约减产 60%（系数 0.40），15% 时约 0.91，常态 < 0.05 几乎不影响。
    """
    total = float(blight or 0) + float(spot or 0) + float(virus or 0)
    return _clamp(1.0 - total * 0.6, 0.4, 1.0)


def _pest_factor(rph, scs, cm) -> float:
    """虫害修正：三虫总数 → 啃食穗茎 → 影响结实率。

    经验阈值：总虫 800 只时减到 0.50；100 只时约 0.875。
    """
    total = float(rph or 0) + float(scs or 0) + float(cm or 0)
    return _clamp(1.0 - total / 800.0, 0.5, 1.0)


def _soil_factor(om, ph, p, k, ec) -> float:
    """土壤修正：pH偏离 × 有机质 × N-P-K × 盐胁迫。

    - pH 每偏离最适 ±1 单位减约 10%
    - 有机质相对最适 3% 线性缩放
    - 钾权重比磷高（水稻是喜钾作物）
    - 电导率高于 1 dS/m 起进入盐胁迫，开根号弱化
    """
    if ph is None or om is None:
        return 1.0
    f_ph = _clamp(1.0 - abs(float(ph) - OPTIMAL_PH) * 0.1, 0.6, 1.0)
    f_om = _clamp(float(om) / OPTIMAL_OM_PERCENT, 0.6, 1.2)
    f_p  = _clamp(float(p or OPTIMAL_P_PPM) / OPTIMAL_P_PPM, 0.7, 1.1)
    f_k  = _clamp(float(k or OPTIMAL_K_PPM) / OPTIMAL_K_PPM, 0.7, 1.1)
    f_pk = f_p * 0.4 + f_k * 0.6           # 钾权重更高
    f_ec = _clamp(1.0 - max(0.0, float(ec or 0) - OPTIMAL_EC) * 0.2, 0.5, 1.0)
    return f_ph * f_om * f_pk * (f_ec ** 0.5)


def _weather_factor(weather_window: pd.DataFrame) -> float:
    """气象修正：近 7 天的温度 / 日照 / 降水综合。

    - 温度每偏离最适 26℃ 1℃ 减 2%
    - 日照相对每天 6h 线性缩放
    - 降水相对 7 天 50mm 线性缩放
    """
    if weather_window is None or weather_window.empty:
        return 1.0
    avg_t = weather_window['dailyaveragetemperature'].mean()
    sun_d = weather_window['sunshineduration'].mean()
    rain  = weather_window['dailyprecipitation'].sum()

    f_t    = _clamp(1.0 - abs(float(avg_t) - OPTIMAL_TEMP) * 0.02, 0.6, 1.1)
    f_sun  = _clamp(float(sun_d) / OPTIMAL_DAILY_SUN, 0.7, 1.1)
    f_rain = _clamp(float(rain)  / OPTIMAL_WEEKLY_RAIN, 0.7, 1.1)
    return f_t * f_sun * f_rain


def _growth_factor(growth_status) -> float:
    """长势修正：人工标注的综合健康度。"""
    if growth_status is None:
        return 1.0
    return GROWTH_STATUS_MAP.get(str(growth_status).strip(), 0.9)


# ============================================================================
# 对外主函数（保持返回值格式 "预测产量：xx.xx kg/亩" 不变）
# ============================================================================
def rice_yield(
    current_point: str,
    target_date: str,
    yield_df: pd.DataFrame,
    management_df: Optional[pd.DataFrame] = None,
    soil_df: Optional[pd.DataFrame] = None,
    weather_df: Optional[pd.DataFrame] = None,
) -> str:
    """基于多因子修正模型预测水稻产量。

    Args:
        current_point: 站点编号，如 "point_1"
        target_date:   目标日期 "YYYY-MM-DD"，如 "2025-05-08"
        yield_df:      历史基线产量表（pre_rice_yield.csv），必填
        management_df: 病虫害 + 长势数据（可选，不传则跳过病害/虫害/长势修正）
        soil_df:       土壤数据（可选，不传则跳过土壤修正）
        weather_df:    日尺度气象数据（可选，不传则跳过气象修正）

    Returns:
        "预测产量：XX.XX kg/亩"（格式与原版严格一致，下游 Dify 工作流不受影响）
    """
    # ── 1. 基线产量：当年 firstcrop 列 ──────────────────
    year = target_date.split('-')[0]
    col = f"{year}firstcrop"
    if col not in yield_df.columns:
        raise ValueError(f"产量列不存在：{col}")
    matched = yield_df[yield_df['point'] == current_point]
    if matched.empty:
        raise ValueError(f"未找到站点产量数据：{current_point}")
    base_yield = float(matched[col].iloc[0])

    # 三个可选 df 都不传 → 退化为旧版直接返回基线（向后兼容）
    if management_df is None and soil_df is None and weather_df is None:
        return f"预测产量：{base_yield:.2f} kg/亩"

    target_dt = pd.to_datetime(target_date).normalize()

    # ── 2. 病害 / 虫害 / 长势修正（来自 management_df）──────
    f_disease = f_pest = f_growth = 1.0
    if management_df is not None:
        m = management_df.copy()
        m['Date'] = pd.to_datetime(m['Date'], errors="coerce").dt.normalize()
        row = m[(m['Date'] == target_dt) & (m['point'] == current_point)]
        if not row.empty:
            r = row.iloc[0]
            f_disease = _disease_factor(
                r.get('BacterialLeafBlightRate'),
                r.get('BrownSpotRate'),
                r.get('TungroVirusRate'),
            )
            f_pest = _pest_factor(
                r.get('PestRphNum'),
                r.get('PestScsNum'),
                r.get('PestCmNum'),
            )
            f_growth = _growth_factor(r.get('GrowthStatus'))

    # ── 3. 土壤修正（来自 soil_df）─────────────────────────
    f_soil = 1.0
    if soil_df is not None:
        s = soil_df.copy()
        s['date'] = pd.to_datetime(s['date'], errors="coerce").dt.normalize()
        row = s[(s['date'] == target_dt) & (s['point'] == current_point)]
        if not row.empty:
            r = row.iloc[0]
            f_soil = _soil_factor(
                r.get('Soil_OM_percent'),
                r.get('Soil_pH'),
                r.get('Soil_P_ppm'),
                r.get('Soil_K_ppm'),
                r.get('Soil_EC_dS_m'),
            )

    # ── 4. 气象修正（近 7 天，来自 weather_df）────────────
    f_weather = 1.0
    if weather_df is not None:
        w = weather_df.copy()
        w['date'] = pd.to_datetime(w['date'], errors="coerce").dt.normalize()
        window = w[
            (w['point'] == current_point)
            & (w['date'] >= target_dt - pd.Timedelta(days=7))
            & (w['date'] <= target_dt)
        ]
        f_weather = _weather_factor(window)

    # ── 5. 综合预测：基线 × 5 个因子 ──────────────────────
    predicted = base_yield * f_disease * f_pest * f_soil * f_weather * f_growth
    return f"预测产量：{predicted:.2f} kg/亩"
