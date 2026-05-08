from numpy import int64
import requests
import pandas as pd

def disease(
    TARGET_DATE: str,
    TARGET_SITE: str,
    management_df: pd.DataFrame,
    api_url: str,
    api_key: str,
    session: requests.Session,
) -> tuple[str, str]:
    # 只做计算与调用；数据与 Dify 配置由上层统一加载传入。
    df = management_df.copy()
    # 日期列转换为datetime格式
    df['Date'] = pd.to_datetime(df['Date'], errors="coerce").dt.normalize()
    # 新增叶害总覆盖率和虫害总数量
    # 叶害覆盖率包含白叶枯、褐斑、东格鲁三项指标
    df['Leaf_Damage_Coverage'] = df[['BacterialLeafBlightRate', 'BrownSpotRate', 'TungroVirusRate']].sum(axis=1)
    # 虫害数量包含稻飞虱、二化螟、稻纵卷叶螟
    # 这里修正了字段名为PestCmNum
    df['Bug_Quantity'] = df[['PestRphNum', 'PestScsNum', 'PestCmNum']].sum(axis=1).fillna(0).astype(int64)

    # 2. 统一日期：允许传入 "YYYY-MM-DD" 或 "YYYY/MM/DD"
    target_date = pd.to_datetime(TARGET_DATE, errors="raise").normalize()
    # formatted_date = TARGET_DATE.replace("/", "")  # 日期斜杠转空（适配文件名）

    # 筛选目标日期 + 目标站点的唯一数据行
    df_target = df[(df['Date'] == target_date) & (df['point'] == TARGET_SITE)].copy()
    if df_target.empty:
        raise ValueError(f"未找到病虫害数据：{TARGET_SITE} 在 {target_date.date()}")
    row = df_target.iloc[0]

    # 4. 提取当前站点数据
    site_id = row['point']
    growth_period = row['GrowthPeriod']
    blight_rate = row['BacterialLeafBlightRate']
    spot_rate = row['BrownSpotRate']
    virus_rate = row['TungroVirusRate']
    rph_num = row['PestRphNum']
    scs_num = row['PestScsNum']
    cm_num = row['PestCmNum']

    # 5. 计算四个关键指标
    # 筛选当前站点的所有数据（按站点分组）
    df_site = df[df['point'] == site_id].copy()

    # 指标1：叶害变化趋势
    prev_day = target_date - pd.Timedelta(days=1)
    prev_day_leaf = df_site[df_site['Date'] == prev_day]['Leaf_Damage_Coverage'].values
    current_leaf = row['Leaf_Damage_Coverage']
    if len(prev_day_leaf) == 0:
        leaf_trend = "无历史数据"
    else:
        leaf_diff = current_leaf - prev_day_leaf[0]
        leaf_trend = "恶化" if leaf_diff > 0 else ("改善" if leaf_diff < 0 else "稳定")

    # 指标2：虫害变化趋势
    prev_day_bug = df_site[df_site['Date'] == prev_day]['Bug_Quantity'].values
    current_bug = row['Bug_Quantity']
    if len(prev_day_bug) == 0:
        bug_trend = "无历史数据"
    else:
        bug_diff = current_bug - prev_day_bug[0]
        bug_trend = "恶化" if bug_diff > 0 else ("改善" if bug_diff < 0 else "稳定")

    # 指标3：7日叶害相对覆盖率
    seven_days_ago = target_date - pd.Timedelta(days=7)
    df_leaf_7d = df_site[(df_site['Date'] >= seven_days_ago) & (df_site['Date'] < target_date)]
    leaf_7d_sum = df_leaf_7d['Leaf_Damage_Coverage'].sum()
    leaf_7d_coverage = f"{round((current_leaf / leaf_7d_sum) * 100, 2)}%" if leaf_7d_sum != 0 else "无参考数据"

    # 指标4：7日虫害相对覆盖率
    df_bug_7d = df_site[(df_site['Date'] >= seven_days_ago) & (df_site['Date'] < target_date)]
    bug_7d_sum = df_bug_7d['Bug_Quantity'].sum()
    bug_7d_coverage = f"{round((current_bug / bug_7d_sum) * 100, 2)}%" if bug_7d_sum != 0 else "无参考数据"

    input_text = (
        f"现农田生长阶段为{growth_period}，其叶害情况：白叶枯病覆盖率为{blight_rate}，"
        f"褐斑病覆盖率为{spot_rate}，东格鲁病毒覆盖率为{virus_rate}；虫害情况："
        f"稻飞虱数量为{rph_num}只，二化螟数量为{scs_num}只，稻纵卷叶螟数量为{cm_num}只。"
        f"当前叶害变化趋势为{leaf_trend}，虫害变化趋势为{bug_trend}，"
        f"7日叶害相对覆盖率为{leaf_7d_coverage}，7日虫害相对数量占比为{bug_7d_coverage}。"
    )

    # 6. 调用DiFy，获取output1和output2并打印输出
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    request_body = {
        "inputs": {"input": input_text},
        "response_mode": "blocking",
        "user": f"rice_disease_{site_id}"
    }
    response = session.post(url=api_url, headers=headers, json=request_body)
    if response.status_code != 200:
        raise Exception(f"Dify API 请求失败: {response.status_code} {response.text}")
    response_data = response.json()
    outputs = response_data.get("data", {}).get("outputs", {})
    if not isinstance(outputs, dict):
        raise RuntimeError(f"Dify 返回 outputs 不是字典: {type(outputs)}; payload={response_data}")

    output1 = outputs.get("output1")
    if output1 is None:
        raise KeyError(f"Dify 返回缺少 output1: outputs={outputs}")

    # 有些工作流可能只返回 output1，不一定有 output2
    output2 = outputs.get("output2", output1)
    return str(output1), str(output2)
    