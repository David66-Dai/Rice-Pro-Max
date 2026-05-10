from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import json
import io

app = FastAPI(title="HDFS File Browser API")

HDFS_ROOT = "/rice/output"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────── 底层工具函数 ────────────────────


def hdfs_list_names(path: str) -> List[str]:
    result = subprocess.run(
        ["hdfs", "dfs", "-ls", path],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise FileNotFoundError(result.stderr.strip())
    names = []
    for line in result.stdout.strip().splitlines():
        if line.startswith("Found") or not line.strip():
            continue
        names.append(line.split()[-1].rstrip("/").split("/")[-1])
    return names


def hdfs_list_detail(path: str) -> List[Dict[str, Any]]:
    result = subprocess.run(
        ["hdfs", "dfs", "-ls", path],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise FileNotFoundError(result.stderr.strip())
    entries = []
    for line in result.stdout.strip().splitlines():
        if line.startswith("Found") or not line.strip():
            continue
        parts = line.split()
        full_path = parts[-1]
        entries.append({
            "name": full_path.rstrip("/").split("/")[-1],
            "path": full_path,
            "type": "DIRECTORY" if parts[0].startswith("d") else "FILE",
            "size": int(parts[4]),
            "modified": f"{parts[5]} {parts[6]}",
        })
    return entries


def hdfs_cat(path: str) -> bytes:
    result = subprocess.run(
        ["hdfs", "dfs", "-cat", path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise FileNotFoundError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def hdfs_read_json(path: str) -> dict:
    return json.loads(hdfs_cat(path).decode("utf-8"))


def _not_found(e: Exception):
    raise HTTPException(status_code=404, detail=str(e))


# ──────────────────── 业务快捷接口 ────────────────────


@app.get("/api/dates")
def get_dates():
    """获取所有可用日期"""
    try:
        return hdfs_list_names(HDFS_ROOT)
    except FileNotFoundError as e:
        _not_found(e)


@app.get("/api/{date}/points")
def get_points(date: str):
    """获取某日期下所有站点"""
    try:
        return hdfs_list_names(f"{HDFS_ROOT}/{date}")
    except FileNotFoundError as e:
        _not_found(e)


@app.get("/api/{date}/{point}")
def get_point_all(date: str, point: str):
    """一次性返回某站点下所有 JSON 输出（合并为一个对象）"""
    base = f"{HDFS_ROOT}/{date}/{point}"
    try:
        names = hdfs_list_names(base)
    except FileNotFoundError as e:
        _not_found(e)
    result = {}
    for name in names:
        if not name.endswith(".json"):
            continue
        key = name[:-5] if name.endswith(".json") else name
        try:
            result[key] = hdfs_read_json(f"{base}/{name}")
        except Exception:
            result[key] = None
    return result


@app.get("/api/{date}/{point}/{filename}")
def get_point_file(date: str, point: str, filename: str):
    """读取某站点下的单个文件"""
    path = f"{HDFS_ROOT}/{date}/{point}/{filename}"
    try:
        raw = hdfs_cat(path)
    except FileNotFoundError as e:
        _not_found(e)
    if path.endswith(".json"):
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    text_exts = {".txt", ".csv", ".py", ".log", ".xml", ".yaml", ".yml", ".md"}
    if any(path.endswith(ext) for ext in text_exts):
        return {"content": raw.decode("utf-8", errors="replace")}
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────── 通用浏览接口（保留） ────────────────────


@app.get("/api/hdfs/list")
def list_dir(path: str = Query("/", description="HDFS 目录路径")):
    """列出指定 HDFS 目录下的文件和子目录"""
    try:
        return hdfs_list_detail(path)
    except FileNotFoundError as e:
        _not_found(e)


@app.get("/api/hdfs/read")
def read_file(path: str = Query(..., description="HDFS 文件路径")):
    """读取指定 HDFS 文件内容"""
    try:
        raw = hdfs_cat(path)
    except FileNotFoundError as e:
        _not_found(e)
    if path.endswith(".json"):
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    text_exts = {".txt", ".csv", ".py", ".log", ".xml", ".yaml", ".yml", ".md"}
    if any(path.endswith(ext) for ext in text_exts):
        return {"content": raw.decode("utf-8", errors="replace")}
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={path.split('/')[-1]}"},
    )