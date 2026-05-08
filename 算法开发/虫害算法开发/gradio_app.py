"""
Gradio 网页：上传水稻田间图，测试害虫检测（YOLO）。

运行（在项目根目录）:
  python gradio_app.py
浏览器打开终端里提示的地址（默认 http://127.0.0.1:7860）
"""
from __future__ import annotations

from pathlib import Path

import cv2
import gradio as gr
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = ROOT / "runs" / "detect" / "rice_pests_yolo11x" / "weights" / "best.pt"

_model: YOLO | None = None


def get_model() -> YOLO:
    global _model
    if _model is None:
        w = str(DEFAULT_WEIGHTS) if DEFAULT_WEIGHTS.is_file() else "yolo11x.pt"
        if not DEFAULT_WEIGHTS.is_file():
            print(f"未找到 {DEFAULT_WEIGHTS}，使用预训练 {w}")
        _model = YOLO(w)
    return _model


def run_detect(image: np.ndarray | None, conf: float, imgsz: int) -> tuple[np.ndarray | None, str]:
    if image is None:
        return None, "请上传一张图片。"

    # Gradio 传入一般为 RGB
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    model = get_model()
    results = model.predict(
        source=image,
        conf=float(conf),
        imgsz=int(imgsz),
        verbose=False,
        save=False,
    )
    r = results[0]
    names = r.names if isinstance(r.names, dict) else {i: n for i, n in enumerate(r.names)}

    plot_bgr = r.plot()
    out_rgb = cv2.cvtColor(plot_bgr, cv2.COLOR_BGR2RGB)

    lines = ["| 类别 | 置信度 | 中心x | 中心y |", "| --- | --- | --- | --- |"]
    if r.boxes is None or len(r.boxes) == 0:
        return out_rgb, "未检测到害虫。\n\n" + "\n".join(lines) + "\n| — | — | — | — |"

    for b in r.boxes:
        cid = int(b.cls[0])
        cf = float(b.conf[0])
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        lab = names.get(cid, str(cid))
        lines.append(f"| {lab} | {cf:.3f} | {cx:.0f} | {cy:.0f} |")

    md = f"**检出 {len(r.boxes)} 个目标**\n\n" + "\n".join(lines)
    return out_rgb, md


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="水稻害虫检测测试") as demo:
        gr.Markdown(
            "## 水稻害虫检测（YOLO 测试）\n"
            "上传图片，查看检测框与类别。默认权重：`runs/detect/rice_pests_yolo11x/weights/best.pt`"
        )
        with gr.Row():
            with gr.Column():
                inp = gr.Image(type="numpy", label="上传图像", height=400)
                conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度阈值")
                imgsz = gr.Slider(320, 1280, value=640, step=32, label="推理边长 imgsz")
                btn = gr.Button("检测", variant="primary")
            with gr.Column():
                out_img = gr.Image(type="numpy", label="检测结果")
                out_txt = gr.Markdown(label="明细")

        btn.click(fn=run_detect, inputs=[inp, conf, imgsz], outputs=[out_img, out_txt])

    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="0.0.0.0", server_port=7860, share=False)
