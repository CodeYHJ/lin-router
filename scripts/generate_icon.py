#!/usr/bin/env python3
"""为 Lin Router 生成平台专属应用图标。

用法：
    python scripts/generate_icon.py win32 resources/win32/LinRouter.ico
    python scripts/generate_icon.py darwin resources/darwin/LinRouter.icns
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def make_base(size: int):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(1, size // 5)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(34, 197, 94, 255))

    try:
        font = ImageFont.truetype("segoeui.ttf", max(10, size // 2 - 4))
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


def generate_win32(out_path: Path) -> None:
    sizes = [16, 32, 48, 256]
    images = [make_base(s) for s in sizes]
    images[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def generate_darwin(out_path: Path) -> None:
    size_map = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    with tempfile.TemporaryDirectory(prefix="linrouter_iconset_") as tmp:
        iconset_dir = Path(tmp) / "LinRouter.iconset"
        iconset_dir.mkdir()
        for filename, size in size_map.items():
            make_base(size).save(iconset_dir / filename)
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir)], check=True)
        generated = Path(tmp) / "LinRouter.icns"
        generated.rename(out_path)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    target, out = sys.argv[1], Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    if target == "win32":
        generate_win32(out)
    elif target == "darwin":
        generate_darwin(out)
    else:
        print(f"Unsupported target: {target}", file=sys.stderr)
        return 1
    print(f"Generated icon: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
