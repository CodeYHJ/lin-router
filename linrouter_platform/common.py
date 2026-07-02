from __future__ import annotations

from typing import Any


def generate_tray_icon() -> Any:
    """用 Pillow 生成一个 64x64 的 LR 图标（绿色圆角白字）。

    该图标在 Windows 与 macOS 上共用，不依赖外部图标文件。
    """
    from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 绿色圆角背景
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=12, fill=(34, 197, 94, 255))

    # 文字 LR
    try:
        font = ImageFont.truetype("segoeui.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    text = "LR"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img
