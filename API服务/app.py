from __future__ import annotations

import base64
import csv
import json
import os
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pymysql
import torch
import torch.nn as nn
import uvicorn
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageEnhance
from torchvision import models, transforms
from ultralytics import YOLO

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent
MODEL_ROOT = APP_ROOT / "model_weights"
DATA_ROOT = APP_ROOT / "data"
MONITOR_RECORD_FILE = DATA_ROOT / "monitoring_records.csv"
MONITOR_JSON_ROOT = DATA_ROOT / "monitoring_json"

LEAF_MODEL_PATH = MODEL_ROOT / "leaf" / "best_model.pt"
PEST_MODEL_PATH = MODEL_ROOT / "pest" / "best.pt"

DISPLAY_ZH = {
    "Bacterial Leaf Blight": "细菌性叶枯病",
    "Brown Spot": "褐斑病",
    "Healthy Leaf": "健康叶片",
    "Tungro Virus": "东格鲁病毒",
}

app = FastAPI(title="智慧农业诊断 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_leaf_model: nn.Module | None = None
_leaf_meta: dict[str, Any] | None = None
_pest_model: YOLO | None = None


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sanitize_monitoring_payload(payload: dict[str, Any]) -> dict[str, Any]:
    point = str(payload.get("point", "")).strip()
    date_value = str(payload.get("Date", "")).strip()
    if not point:
        raise HTTPException(status_code=400, detail="point 不能为空")
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date 格式必须为 YYYY-MM-DD") from exc

    return {
        "point": point,
        "Date": date_value,
        "GrowthPeriod": str(payload.get("GrowthPeriod", "")).strip(),
        "GrowthStatus": str(payload.get("GrowthStatus", "")).strip(),
        "BacterialLeafBlightRate": _to_float(payload.get("BacterialLeafBlightRate")),
        "BrownSpotRate": _to_float(payload.get("BrownSpotRate")),
        "TungroVirusRate": _to_float(payload.get("TungroVirusRate")),
        "PestRphNum": _to_int(payload.get("PestRphNum")),
        "PestScsNum": _to_int(payload.get("PestScsNum")),
        "PestCmNum": _to_int(payload.get("PestCmNum")),
    }


def _save_monitoring_record_local(record: dict[str, Any]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "point",
        "Date",
        "GrowthPeriod",
        "GrowthStatus",
        "BacterialLeafBlightRate",
        "BrownSpotRate",
        "TungroVirusRate",
        "PestRphNum",
        "PestScsNum",
        "PestCmNum",
    ]
    file_exists = MONITOR_RECORD_FILE.exists()
    with MONITOR_RECORD_FILE.open("a", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def _json_path_for_monitoring_record(date_value: str, point: str) -> Path:
    return MONITOR_JSON_ROOT / date_value / f"{point}.json"


def _save_monitoring_record_json(record: dict[str, Any]) -> None:
    point = str(record.get("point", "")).strip()
    date_value = str(record.get("Date", "")).strip()
    if not point or not date_value:
        return

    file_path = _json_path_for_monitoring_record(date_value, point)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "point": point,
        "Date": date_value,
        "records": [],
        "mergedInspectItems": [],
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            if isinstance(loaded, dict):
                payload.update(loaded)
        except Exception:
            pass

    records = payload.get("records")
    if not isinstance(records, list):
        records = []
    records.append(record)
    payload["records"] = records
    payload["point"] = point
    payload["Date"] = date_value
    payload["mergedInspectItems"] = _merge_record_items(records)
    payload["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with file_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def _save_monitoring_record_mysql(record: dict[str, Any]) -> None:
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "123456"),
        database=os.getenv("MYSQL_DATABASE", "rice_pro_max"),
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pest_disease_monitoring (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    point VARCHAR(64) NOT NULL,
                    `Date` DATE NOT NULL,
                    GrowthPeriod VARCHAR(64) NOT NULL,
                    GrowthStatus VARCHAR(32) NOT NULL,
                    BacterialLeafBlightRate DECIMAL(6,2) NOT NULL,
                    BrownSpotRate DECIMAL(6,2) NOT NULL,
                    TungroVirusRate DECIMAL(6,2) NOT NULL,
                    PestRphNum INT NOT NULL,
                    PestScsNum INT NOT NULL,
                    PestCmNum INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_point_date (point, `Date`)
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO pest_disease_monitoring (
                    point, `Date`, GrowthPeriod, GrowthStatus,
                    BacterialLeafBlightRate, BrownSpotRate, TungroVirusRate,
                    PestRphNum, PestScsNum, PestCmNum
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record["point"],
                    record["Date"],
                    record["GrowthPeriod"],
                    record["GrowthStatus"],
                    record["BacterialLeafBlightRate"],
                    record["BrownSpotRate"],
                    record["TungroVirusRate"],
                    record["PestRphNum"],
                    record["PestScsNum"],
                    record["PestCmNum"],
                ),
            )
    finally:
        conn.close()


def _leaf_level_from_rates(record: dict[str, Any], field: str) -> str:
    rate = _to_float(record.get(field))
    if rate >= 50:
        return "danger"
    if rate > 0:
        return "warn"
    return "normal"


def _count_level(value: Any) -> str:
    count = _to_int(value)
    if count >= 3:
        return "danger"
    if count >= 1:
        return "warn"
    return "normal"


def _record_to_inspect_items(record: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"key": "leaf_blight", "name": "细菌性叶枯病", "level": _leaf_level_from_rates(record, "BacterialLeafBlightRate")},
        {"key": "leaf_brown_spot", "name": "褐斑病", "level": _leaf_level_from_rates(record, "BrownSpotRate")},
        {"key": "leaf_tungro", "name": "东格鲁病害", "level": _leaf_level_from_rates(record, "TungroVirusRate")},
        {"key": "pest_borer", "name": "二化螟", "level": _count_level(record.get("PestScsNum"))},
        {"key": "pest_planthopper", "name": "褐飞虱", "level": _count_level(record.get("PestRphNum"))},
        {"key": "pest_leafroller", "name": "稻纵卷叶螟", "level": _count_level(record.get("PestCmNum"))},
    ]


def _merge_level(current: str, incoming: str) -> str:
    priority = {"normal": 0, "warn": 1, "danger": 2}
    current_priority = priority.get(current, 0)
    incoming_priority = priority.get(incoming, 0)
    return incoming if incoming_priority > current_priority else current


def _merge_record_items(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    merged = {
        "leaf_blight": {"key": "leaf_blight", "name": "细菌性叶枯病", "level": "normal"},
        "leaf_brown_spot": {"key": "leaf_brown_spot", "name": "褐斑病", "level": "normal"},
        "leaf_tungro": {"key": "leaf_tungro", "name": "东格鲁病害", "level": "normal"},
        "pest_borer": {"key": "pest_borer", "name": "二化螟", "level": "normal"},
        "pest_planthopper": {"key": "pest_planthopper", "name": "褐飞虱", "level": "normal"},
        "pest_leafroller": {"key": "pest_leafroller", "name": "稻纵卷叶螟", "level": "normal"},
    }
    for record in records:
        for item in _record_to_inspect_items(record):
            key = item.get("key")
            if key not in merged:
                continue
            merged[key]["level"] = _merge_level(merged[key]["level"], item.get("level", "normal"))
    return list(merged.values())


def _load_records_from_csv(date_value: str) -> dict[str, list[dict[str, Any]]]:
    if not MONITOR_RECORD_FILE.exists():
        return {}

    records_by_point: dict[str, list[dict[str, Any]]] = {}
    with MONITOR_RECORD_FILE.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            point = str(row.get("point", "")).strip()
            if not point or str(row.get("Date", "")).strip() != date_value:
                continue
            records_by_point.setdefault(point, []).append(row)
    return records_by_point


def _load_records_from_mysql(date_value: str) -> dict[str, list[dict[str, Any]]]:
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "123456"),
        database=os.getenv("MYSQL_DATABASE", "rice_pro_max"),
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT point, `Date`, GrowthPeriod, GrowthStatus,
                       BacterialLeafBlightRate, BrownSpotRate, TungroVirusRate,
                       PestRphNum, PestScsNum, PestCmNum
                FROM pest_disease_monitoring
                WHERE `Date` = %s
                ORDER BY point ASC, id ASC
                """,
                (date_value,),
            )
            rows = cursor.fetchall() or []
            records_by_point: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                point = str(row.get("point", "")).strip()
                if not point:
                    continue
                records_by_point.setdefault(point, []).append(row)
            return records_by_point
    finally:
        conn.close()


def _load_monitoring_records(date_value: str) -> dict[str, list[dict[str, Any]]]:
    try:
        return _load_records_from_mysql(date_value)
    except Exception:
        return _load_records_from_csv(date_value)


def _load_records_from_json(date_value: str) -> dict[str, list[dict[str, Any]]]:
    day_dir = MONITOR_JSON_ROOT / date_value
    if not day_dir.is_dir():
        return {}

    records_by_point: dict[str, list[dict[str, Any]]] = {}
    for json_file in sorted(day_dir.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        point = str(payload.get("point", "")).strip() or json_file.stem
        records = payload.get("records")
        if not isinstance(records, list):
            continue
        valid_records = [item for item in records if isinstance(item, dict)]
        if not valid_records:
            continue
        records_by_point[point] = valid_records
    return records_by_point


def load_leaf_model() -> tuple[nn.Module, dict[str, Any]]:
    global _leaf_model, _leaf_meta
    if _leaf_model is not None and _leaf_meta is not None:
        return _leaf_model, _leaf_meta

    if not LEAF_MODEL_PATH.is_file():
        raise FileNotFoundError(f"叶害模型不存在: {LEAF_MODEL_PATH}")

    ckpt = torch.load(LEAF_MODEL_PATH, map_location=DEVICE, weights_only=False)
    meta = ckpt.get("meta") or {}
    class_names = meta.get("class_names")
    if not class_names:
        raise ValueError("叶害模型缺少 meta.class_names")

    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, int(ckpt.get("num_classes", len(class_names))))
    model.load_state_dict(ckpt["model_state"])
    model.to(DEVICE)
    model.eval()

    _leaf_model = model
    _leaf_meta = meta
    return model, meta


def load_pest_model() -> YOLO:
    global _pest_model
    if _pest_model is not None:
        return _pest_model

    weights = PEST_MODEL_PATH if PEST_MODEL_PATH.is_file() else WORKSPACE_ROOT / "虫害算法开发" / "yolo11x.pt"
    if not weights.is_file():
        raise FileNotFoundError(f"虫害模型不存在: {weights}")

    _pest_model = YOLO(str(weights))
    return _pest_model


def open_upload_image(file_bytes: bytes) -> Image.Image:
    try:
        return Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无效图片文件: {exc}") from exc


def enhance_result_image(image: Image.Image) -> Image.Image:
    # Light enhancement so recognition images look fuller on the frontend.
    image = ImageEnhance.Color(image).enhance(1.15)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    return image


def infer_leaf(file_bytes: bytes) -> dict[str, Any]:
    model, meta = load_leaf_model()
    class_names: list[str] = meta["class_names"]
    healthy_key = meta.get("healthy_folder_name", "Healthy Leaf")

    tfm = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    img = open_upload_image(file_bytes)
    x = tfm(img).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        logits = model(x)
        prob = torch.softmax(logits, dim=1)[0]

    idx = int(prob.argmax().item())
    predicted_class = class_names[idx]
    confidence = float(prob[idx].item())
    return {
        "label": DISPLAY_ZH.get(predicted_class, predicted_class),
        "className": predicted_class,
        "confidence": confidence,
        "hasLeafDamage": predicted_class != healthy_key,
        "probabilities": {class_names[i]: float(prob[i].item()) for i in range(len(class_names))},
    }


def infer_pest(file_bytes: bytes) -> dict[str, Any]:
    model = load_pest_model()
    img = np.array(open_upload_image(file_bytes))
    results = model.predict(source=img, conf=0.25, verbose=False)
    result = results[0]
    names = model.names if isinstance(model.names, dict) else {i: n for i, n in enumerate(model.names)}
    pest_counts = {name: 0 for _, name in sorted(names.items())}
    plotted = result.plot()
    annotated_rgb = Image.fromarray(plotted[:, :, ::-1])
    annotated_rgb = enhance_result_image(annotated_rgb)
    image_buffer = BytesIO()
    annotated_rgb.save(image_buffer, format="JPEG", quality=95, subsampling=0)
    annotated_image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    if result.boxes is None or len(result.boxes) == 0:
        return {
            "label": "未检测到虫害",
            "confidence": 0.0,
            "hasPestDamage": False,
            "detections": [],
            "pestCounts": pest_counts,
            "totalPestCount": 0,
            "annotatedImageBase64": annotated_image_base64,
        }

    cls_ids = [int(v) for v in result.boxes.cls.tolist()]
    confs = [float(v) for v in result.boxes.conf.tolist()]
    cls_counter = Counter(cls_ids)
    for cls_id, count in cls_counter.items():
        pest_counts[names.get(cls_id, str(cls_id))] = int(count)
    detections = [{"label": names.get(cls_id, str(cls_id)), "confidence": conf} for cls_id, conf in zip(cls_ids, confs)]
    top = max(detections, key=lambda item: item["confidence"])
    return {
        "label": top["label"],
        "confidence": top["confidence"],
        "hasPestDamage": True,
        "detections": detections,
        "pestCounts": pest_counts,
        "totalPestCount": len(detections),
        "annotatedImageBase64": annotated_image_base64,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/diagnosis/leaf")
async def diagnosis_leaf(
    file: UploadFile = File(...),
    stationCode: str = Form(default=""),
) -> dict[str, Any]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")
    file_bytes = await file.read()
    try:
        output = infer_leaf(file_bytes)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    output.update({"stationCode": stationCode, "module": "leaf"})
    return output


@app.post("/api/diagnosis/pest")
async def diagnosis_pest(
    file: UploadFile = File(...),
    stationCode: str = Form(default=""),
) -> dict[str, Any]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")
    file_bytes = await file.read()
    try:
        output = infer_pest(file_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    output.update({"stationCode": stationCode, "module": "pest"})
    return output


@app.post("/api/monitoring/record")
def save_monitoring_record(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    record = _sanitize_monitoring_payload(payload)
    _save_monitoring_record_local(record)
    _save_monitoring_record_json(record)
    try:
        _save_monitoring_record_mysql(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MySQL 写入失败: {exc}") from exc
    return {"status": "ok", "savedLocal": True, "savedJSON": True, "savedMySQL": True}


@app.get("/api/monitoring/state")
def get_monitoring_state(date: str) -> dict[str, Any]:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式必须为 YYYY-MM-DD") from exc

    records_by_point = _load_records_from_json(date)
    if not records_by_point:
        records_by_point = _load_monitoring_records(date)
    inspect_map = {point: _merge_record_items(records) for point, records in records_by_point.items()}
    return {"date": date, "stations": inspect_map}


if __name__ == "__main__":
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("app:app", host=api_host, port=api_port, reload=False)
