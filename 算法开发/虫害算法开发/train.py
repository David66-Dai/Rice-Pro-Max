"""
使用 YOLO11x 在自定义水稻害虫数据集上训练。
标注格式：YOLO 检测（每张图对应同名 .txt，每行 class cx cy w h，归一化 0~1）。
"""
from pathlib import Path

from ultralytics import YOLO


def main():
    root = Path(__file__).resolve().parent
    data_yaml = root / "data" / "dataset.yaml"

    if not data_yaml.is_file():
        raise FileNotFoundError(f"未找到数据集配置: {data_yaml}")

    # ========== 🔴 演示点6：YOLO11x 一行训练 ==========
    # 演讲时敲这行 → 展示 Ultralytics 极简 API
    # 对比传统目标检测框架需要手写上百万行代码
    # YOLO11x 自带了 C2f 跨阶段连接、特征金字塔、自动锚框
    model = YOLO("yolo11x.pt")
    model.train(
        data=str(data_yaml),
        epochs=100,
        imgsz=640,
        batch=14,  # 显存不足可改为 4 或 2
        patience=20,
        save=True,
        device=0,  # CPU 用 device="cpu"；多卡如 device=[0,1]
        project=str(root / "runs" / "detect"),
        name="rice_pests_yolo11x",
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
