"""
对单张图、文件夹或视频运行害虫检测推理。
"""
import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="水稻害虫 YOLO11x 推理")
    parser.add_argument(
        "source",
        type=str,
        nargs="?",
        default="",
        help="图片/文件夹/视频路径，或摄像头 0；省略则默认 data/images/val",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default="",
        help="训练得到的 best.pt；默认使用 runs/detect/rice_pests_yolo11x/weights/best.pt",
    )
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    parser.add_argument("--save", action="store_true", help="保存可视化结果")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    source = args.source or str(root / "data" / "images" / "val")
    weights = args.weights or str(
        root / "runs" / "detect" / "rice_pests_yolo11x" / "weights" / "best.pt"
    )
    if not Path(weights).is_file():
        print(f"未找到权重 {weights}，改用预训练 yolo11x.pt（未针对害虫微调）")
        weights = "yolo11x.pt"

    # ========== 🔴 演示点9：YOLO 一行推理 ==========
    # 演讲时敲 model.predict() → 只需一行即可完成目标检测
    # conf=0.25 → 滤掉低置信度框，平衡召回率和精确率
    # 返回的 results 包含 boxes（坐标）、cls（类别）、conf（置信度）
    model = YOLO(weights)
    names = model.names if isinstance(model.names, dict) else {i: n for i, n in enumerate(model.names)}
    results = model.predict(
        source=source,
        conf=args.conf,
        save=args.save,
        project=str(root / "runs" / "predict"),
        name="pests",
        exist_ok=True,
    )
    for r in results:
        p = r.path
        if r.boxes is None or len(r.boxes) == 0:
            print(f"{p} — 未检测到目标")
            continue
        cls_ids = [int(x) for x in r.boxes.cls.tolist()]
        confs = r.boxes.conf.tolist()
        labels = [names.get(i, str(i)) for i in cls_ids]
        print(f"{p}")
        for lab, c in zip(labels, confs):
            print(f"  {lab}  {c:.3f}")


if __name__ == "__main__":
    main()
