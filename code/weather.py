import requests
import pandas as pd
import json

COLS = {
    "date": "date",
    "station": "point",
    "sunshine": "sunshineduration",
    "max_temp": "dailymaximumtemperature",
    "min_temp": "dailyminimumtemperature",
    "avg_temp": "dailyaveragetemperature",
    "humidity": "dailyrelativehumidity",
    "precip": "dailyprecipitation",
    "wind": "dailyaveragewind",
    "pressure": "dailyaveragepressure",
}


def weather(
    target_date: str,
    target_site: str,
    df: pd.DataFrame,
    api_url: str,
    api_key: str,
    session: requests.Session,
) -> tuple[str, str]:
    target_dt = pd.to_datetime(target_date, errors="raise").normalize()

    future_df = df[
        (df[COLS["date"]] >= target_dt)
        & (df[COLS["date"]] <= target_dt + pd.Timedelta(days=7))
    ]
    s_df = future_df[future_df[COLS["station"]] == target_site].sort_values(COLS["date"])
    if s_df.empty:
        raise ValueError(f"未找到气象数据：{target_site} 在 {target_dt.date()} 及未来7天")

    today = s_df[s_df[COLS["date"]] == target_dt].iloc[0]
    today_str = (
        f"日照{today[COLS['sunshine']]}h，"
        f"日最高温度{today[COLS['max_temp']]}℃、日最低温度{today[COLS['min_temp']]}℃、日平均温度{today[COLS['avg_temp']]}℃，"
        f"相对湿度{today[COLS['humidity']]}%，降水{today[COLS['precip']]}，"
        f"平均风速{today[COLS['wind']]}m/s，平均气压{today[COLS['pressure']]}hPa"
    )

    future = s_df[s_df[COLS["date"]] != target_dt].head(7)
    future_list = [
        f"{row[COLS['sunshine']]}/{row[COLS['max_temp']]}/{row[COLS['min_temp']]}/{row[COLS['avg_temp']]}/"
        f"{row[COLS['humidity']]}%/{row[COLS['precip']]}/{row[COLS['wind']]}/{row[COLS['pressure']]}"
        for _, row in future.iterrows()
    ]
    future_str = "，".join(future_list)

    input_text = (
        f"当天气象：{today_str}；未来7天每日依次为"
        f"（日照/h,日最高温度,日最低温度,日平均温度,相对湿度,降水,平均风速,平均气压）：{future_str}"
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    request_body = {
        "inputs": {"input": input_text},
        "response_mode": "blocking",
        "user": f"rice_weather_{target_site}",
    }
    resp = session.post(url=api_url, headers=headers, json=request_body)
    if resp.status_code != 200:
        raise Exception(f"Dify API 请求失败: {resp.status_code} {resp.text}")
    payload = resp.json()
    outputs = payload.get("data", {}).get("outputs", {})
    if not isinstance(outputs, dict):
        raise RuntimeError(f"Dify 返回 outputs 不是字典: {type(outputs)}; payload={payload}")

    output1 = outputs.get("output1")
    if output1 is None:
        raise KeyError(f"Dify 返回缺少 output1: outputs={outputs}")

    output2 = outputs.get("output2", output1)
    return str(output1), str(output2)

if __name__ == "__main__":
    target_date = "2025-05-08"
    target_site = "point_1"
    df = pd.read_csv("data/monitor_data.csv")
    with open("api/workflow_api_02.json", "r") as f:
        data = json.load(f)
        api_url = data["base_url"]
        api_key = data["api_key"]
    with requests.Session() as session:
        json = weather(target_date,target_site,df,api_url,api_key,session)
        print(json)