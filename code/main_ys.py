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
from typing import NamedTuple


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
    if not isinstance(value, str):
        return value

    for candidate in _extract_json_candidates(value):
        if not candidate:
            continue
        if not (candidate.startswith("{") or candidate.startswith("[")):
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
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
    ###  初始化 Hive 数据加载器（演示）
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
    ### 

    weather_api_url, weather_api_key = load_dify_workflow_run_config("api/workflow_api_02.json")
    soil_api_url, soil_api_key = load_dify_workflow_run_config("api/workflow_api_03.json")
    disease_api_url, disease_api_key = load_dify_workflow_run_config("api/workflow_api_01.json")
    final_api_url, final_api_key = load_dify_workflow_run_config("api/workflow_api_04.json")
    return PipelineResources(
        management_df=hive.load_disease(),       # 从 Hive 读取病虫害数据（演示）
        weather_df=hive.load_weather(),          # 从 Hive 读取气象数据（演示）
        soil_df=hive.load_soil(),                # 从 Hive 读取土壤数据（演示）
        yield_df=hive.load_yield(),              # 从 Hive 读取产量基线数据（演示）
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
) -> tuple[str, str]:
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
    return main_output1, main_output2

if __name__ == "__main__":
    ### 全局配置参数（不做演示）
    TARGET_DATE = "2025-05-08" # 目标日期   
    HDFS_HOST = "192.168.157.130"
    HIVE_HOST = "192.168.157.130"
    HDFS_PORT = 9870
    HIVE_PORT = 10000
    HDFS_USER = "root"
    HIVE_USER = "root"
    HIVE_DATABASE = "farm"
    HDFS_PATH = f"/rice/output/{TARGET_DATE}"

    ### 导入资源、创建hdfs实例（演示）
    resources = load_resources(
        hive_host=HIVE_HOST,
        hive_user=HIVE_USER,
        hive_database=HIVE_DATABASE,
        hive_port=HIVE_PORT
    )
    print("[info] hive连接成功，数据资源加载完成")
    hdfs_client = hdfs(namenode_host=HDFS_HOST, namenode_port=HDFS_PORT, user=HDFS_USER)
    ###

    ### 使用 Session 复用 HTTP 连接，减少重复握手开销（演示）
    with requests.Session() as session:
        
        ### 创建HDFS目录（演示）
        hdfs_client.mkdirs(HDFS_PATH)
        ###
        
        for station_num in range(1, 31):
            print(f"=========================开始处理站点{station_num}=========================")
            
            ### 构建输入(获取虫害、气象、土壤、产量的Dify返回值)（演示）
            input1, input2, input3, input4 = build_inputs(
                target_date=TARGET_DATE,
                station_num=station_num,
                resources=resources,
                session=session,
            )
            ###

            disease_output = parse_json_like(input1[0])
            weather_output = parse_json_like(input2[0])
            soil_output = parse_json_like(input3[0])
            yield_output = {"yield_output": input4}
            
            ### 上传HDFS（演示）
            hdfs_client.upload_json(
                disease_output,
                f"{HDFS_PATH}/point_{station_num}/disease_output.json",
            )
            print("[info] 保存疾病输出到hdfs成功")
            hdfs_client.upload_json(
                weather_output,
                f"{HDFS_PATH}/point_{station_num}/weather_output.json",
            )
            print("[info] 保存气象输出到hdfs成功")
            hdfs_client.upload_json(
                soil_output,
                f"{HDFS_PATH}/point_{station_num}/soil_output.json",
            )
            print("[info] 保存土壤输出到hdfs成功")
            hdfs_client.upload_json(
                yield_output,
                f"{HDFS_PATH}/point_{station_num}/yield_output.json",
            )
            print("[info] 保存产量输出到hdfs成功")
            ###

            print(f"=========================开始推演决策=========================")
            output1, output2 = run_final_workflow(
                input1[1],
                input2[1],
                input3[1],
                input4,
                api_url=resources.final_workflow_api_url,
                api_key=resources.final_workflow_api_key,
                session=session,
            )
            print(f"=========================推演决策完成,正在将结果保存到hdfs=========================")
            main_output = {
                "output1": parse_json_like(output1),
                "output2": parse_json_like(output2)
            }
            hdfs_client.upload_json(
                main_output,
                f"{HDFS_PATH}/point_{station_num}/main_output.json",
            )
            print(f"[info] 保存推演决策结果到hdfs成功")
            print(f"=========================站点{station_num}处理完成=========================")