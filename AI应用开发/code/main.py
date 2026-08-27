from disease import disease
from weather import weather
from soil import soil_analysis
from rice_yield import rice_yield
from hdfs_put import hdfs
from hive_data import RiceDataLoader
import pandas as pd
import json
import re
import requests
from pathlib import Path
from typing import NamedTuple

SCRIPT_DIR = Path(__file__).resolve().parent  # AI应用开发/code/
API_DIR = SCRIPT_DIR.parent / "api"           # AI应用开发/api/
CONF_DIR = SCRIPT_DIR.parent.parent / "conf"  # conf/

with open(CONF_DIR / "config.json", "r", encoding="utf-8") as _f:
    _config = json.load(_f)
HDFS_CFG = _config["hdfs"]
HIVE_CFG = _config["hive"]
DIFY_CFG = _config["dify"]


class PipelineResources(NamedTuple):
    management_df: pd.DataFrame
    weather_df: pd.DataFrame
    soil_df: pd.DataFrame
    yield_df: pd.DataFrame
    disease_api_url: str
    disease_api_key: str
    weather_api_url: str
    weather_api_key: str
    soil_api_url: str
    soil_api_key: str
    final_workflow_api_url: str
    final_workflow_api_key: str


_CODE_FENCE_RE = re.compile(
    r"```(?:json|JSON)?\s*(?P<body>[\s\S]*?)\s*```",
    re.MULTILINE,
)


def _extract_json_candidates(text: str):
    """从原始字符串里抽取可能是 JSON 的候选片段，按优先级依次 yield。"""
    # 1) 去掉 BOM 和首尾空白
    cleaned = text.lstrip("\ufeff").strip()
    yield cleaned

    # 2) Markdown 代码块：```json ... ``` 或 ``` ... ```
    for match in _CODE_FENCE_RE.finditer(cleaned):
        body = match.group("body").strip()
        if body:
            yield body

    # 3) 从第一个 { 或 [ 到最后一个 } 或 ] 的最大片段（兜底抓结构）
    first_obj = cleaned.find("{")
    last_obj = cleaned.rfind("}")
    if first_obj != -1 and last_obj > first_obj:
        yield cleaned[first_obj : last_obj + 1]

    first_arr = cleaned.find("[")
    last_arr = cleaned.rfind("]")
    if first_arr != -1 and last_arr > first_arr:
        yield cleaned[first_arr : last_arr + 1]


def parse_json_like(value):
    """尽量把字符串解析成 JSON 对象，解析失败则原样返回。

    支持的格式：
    - 纯 JSON 字符串（以 { / [ 开头）
    - Markdown 代码块包裹：```json ... ``` / ``` ... ```
    - 前后带说明文字、包含 JSON 片段的混合文本
    - 带 BOM / 首尾空白字符
    """
    import re as _re

    if not isinstance(value, str):
        return value

    def _try_parse(s: str):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # 修复 LLM 输出的未加引号的值：35公斤/亩 → "35公斤/亩"
        try:
            fixed = _re.sub(
                r':\s*(\d+\.?\d*)([^\d\s,}\]"\']+[^\s,}\]]*)',
                r': "\1\2"',
                s,
            )
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        return None

    for candidate in _extract_json_candidates(value):
        if not candidate:
            continue
        if not (candidate.startswith("{") or candidate.startswith("[")):
            continue
        result = _try_parse(candidate)
        if result is not None:
            return result
    return value


def load_dify_workflow_run_config(config_path: str) -> tuple[str, str]:
    """加载 Dify workflow run 配置。"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    base_url = config["base_url"].strip().rstrip("/")
    return f"{base_url}/workflows/run", config["api_key"].strip()


def load_resources(
    hive_host       : str,
    hive_user       : str,
    hive_database   : str,
    hive_port       : int = 10000
) -> PipelineResources:
    """统一加载所有数据资源：Hive 数据 + Dify API 配置。"""
    # 初始化 Hive 数据加载器
    hive = RiceDataLoader(
        host=hive_host,
        port=hive_port,
        user=hive_user,
        database=hive_database,
    )

    # 连接测试：不通则直接终止，避免后续全部报错
    if hive.ping != 200:
        raise ConnectionError(
            f"Hive 连接失败！请检查 host={hive_host}, port={hive_port}, "
            f"user={hive_user}, database={hive_database}"
        )

    def _dify_url_key(name: str) -> tuple[str, str]:
        c = DIFY_CFG[name]
        return f"{c['base_url'].strip().rstrip('/')}/workflows/run", c["api_key"].strip()

    weather_api_url, weather_api_key = _dify_url_key("weather")
    soil_api_url, soil_api_key = _dify_url_key("soil")
    disease_api_url, disease_api_key = _dify_url_key("disease")
    final_api_url, final_api_key = _dify_url_key("final")
    return PipelineResources(
        management_df=hive.load_disease(),       # 从 Hive 读取病虫害数据
        weather_df=hive.load_weather(),          # 从 Hive 读取气象数据
        soil_df=hive.load_soil(),                # 从 Hive 读取土壤数据
        yield_df=hive.load_yield(),              # 从 Hive 读取产量基线数据
        disease_api_url=disease_api_url,
        disease_api_key=disease_api_key,
        weather_api_url=weather_api_url,
        weather_api_key=weather_api_key,
        soil_api_url=soil_api_url,
        soil_api_key=soil_api_key,
        final_workflow_api_url=final_api_url,
        final_workflow_api_key=final_api_key,
    )


def build_inputs(
    target_date: str,
    station_num: int,
    resources: PipelineResources,
    session: requests.Session,
) -> tuple[str, str, str, str]:
    target_site = f"point_{station_num}"
    input1 = disease(
        TARGET_DATE=target_date,
        TARGET_SITE=target_site,
        management_df=resources.management_df,
        api_url=resources.disease_api_url,
        api_key=resources.disease_api_key,
        session=session,
    )
    input2 = weather(
        target_date=target_date,
        target_site=target_site,
        df=resources.weather_df,
        api_url=resources.weather_api_url,
        api_key=resources.weather_api_key,
        session=session,
    )
    input3 = soil_analysis(
        target_date=target_date,
        target_site=target_site,
        df=resources.soil_df,
        api_url=resources.soil_api_url,
        api_key=resources.soil_api_key,
        session=session,
    )
    input4 = rice_yield(
        current_point=target_site,
        target_date=target_date,
        yield_df=resources.yield_df,
        management_df=resources.management_df,   # 病害 / 虫害 / 长势修正
        soil_df=resources.soil_df,               # 土壤修正
        weather_df=resources.weather_df,         # 近 7 天气象修正
    )
    return input1, input2, input3, input4


def run_final_workflow(
    input1: str,
    input2: str,
    input3: str,
    input4: str,
    api_url: str,
    api_key: str,
    session: requests.Session,
) -> tuple[str, str, str]:
    # 构造Dify请求信息
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    request_body = {
        "inputs": {
            "input1": input1,
            "input2": input2,
            "input3": input3,
            "input4": input4
        },
        "response_mode": "blocking",  # 同步阻塞模式，等待执行完成
        "user": "rice_disease_001"     # 固定用户标识
    }

    # 4. 发送POST请求并解析响应数据
    response = session.post(url=api_url, headers=headers, json=request_body)
    if response.status_code != 200:
        raise Exception(f"Dify API 请求失败: {response.status_code} {response.text}")
    response_data = response.json()
    workflow_outputs = response_data['data']['outputs']  # 提取输出结果
    main_output1 = workflow_outputs['output1']
    main_output2 = workflow_outputs["output2"]
    main_output3 = workflow_outputs["output3"]
    return main_output1, main_output2, main_output3

if __name__ == "__main__":
    TARGET_DATE = "2025-05-08" # 目标日期
    HDFS_PATH = f"{HDFS_CFG['output_path']}/{TARGET_DATE}"

    resources = load_resources(
        hive_host=HIVE_CFG["host"],
        hive_user=HIVE_CFG["user"],
        hive_database=HIVE_CFG["database"],
        hive_port=HIVE_CFG["port"]
    )
    print("[conn] hive连接成功，数据资源加载完成")
    hdfs_client = hdfs(namenode_host=HDFS_CFG["host"], namenode_port=HDFS_CFG["port"], user=HDFS_CFG["user"])
    
    with requests.Session() as session:
        hdfs_client.mkdirs(HDFS_PATH)
        for station_num in range(1, 26):
            print(f"[start]开始处理站点{station_num}")
            input1, input2, input3, input4 = build_inputs(
                target_date=TARGET_DATE,
                station_num=station_num,
                resources=resources,
                session=session,
            )
            disease_output = parse_json_like(input1[0])
            weather_output = parse_json_like(input2[0])
            soil_output = parse_json_like(input3[0])
            yield_output = {"yield_output": input4}
            print(f"[info] 开始推演决策")
            output1, output2, output3 = run_final_workflow(
                input1[1],
                input2[1],
                input3[1],
                input4,
                api_url=resources.final_workflow_api_url,
                api_key=resources.final_workflow_api_key,
                session=session,
            )
            print(f"[info] 推演决策完成,正在将结果保存到hdfs")
            main_output = {
                "output1": parse_json_like(output1),
                "output2": parse_json_like(output2),
                "output3": parse_json_like(output3)
            }
            all_output = {
                "disease_output": disease_output,
                "weather_output": weather_output,
                "soil_output": soil_output,
                "yield_output": yield_output,
                "main_output": main_output,
            }
            hdfs_client.upload_json(
                all_output,
                f"{HDFS_PATH}/point_{station_num}/all.json",
            )
            print(f"[info] 保存结果到hdfs成功")
            print(f"[done] 站点{station_num}处理完成")