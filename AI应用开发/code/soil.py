import requests
import pandas as pd


def soil_analysis(
    target_date: str,
    target_site: str,
    df: pd.DataFrame,
    api_url: str,
    api_key: str,
    session: requests.Session,
) -> tuple[str, str]:
    target_dt = pd.to_datetime(target_date, errors="raise").normalize()

    df_target = df[(df['date'] == target_dt) & (df['point'] == target_site)]
    if df_target.empty:
        raise ValueError(f"未找到土壤数据：{target_site} 在 {target_dt.date()}")
    row = df_target.iloc[0]

    site_id = row['point']
    input_text = (
        f"现农田土壤情况：有机质含量{row['Soil_OM_percent']}%、"
        f"土壤酸碱度pH{row['Soil_pH']}、磷含量{row['Soil_P_ppm']}ppm、"
        f"钾含量{row['Soil_K_ppm']}ppm、电导率{row['Soil_EC_dS_m']}dS/m"
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    request_body = {
        "inputs": {"input": input_text},
        "response_mode": "blocking",
        "user": f"rice_soil_{site_id}",
    }
    resp = session.post(url=api_url, headers=headers, json=request_body)
    if resp.status_code != 200:
        raise Exception(f"Dify API 请求失败: {resp.status_code} {resp.text}")
    outputs = resp.json()['data']['outputs']
    return outputs['output1'], outputs['output2']


