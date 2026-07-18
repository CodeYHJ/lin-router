from __future__ import annotations

import sys
from typing import Any

from .base import PlatformBase, UnsupportedPlatform

if sys.platform.startswith("win32"):
    from .windows import WindowsPlatform as _Platform
elif sys.platform.startswith("darwin"):
    from .darwin import DarwinPlatform as _Platform
else:
    # 非支持平台（如 Linux）：使用兜底实现，核心服务可运行，桌面能力明确报错
    _Platform = UnsupportedPlatform

_platform: PlatformBase = _Platform()


def get_platform() -> PlatformBase:
    """返回当前平台的平台实现单例。"""
    return _platform


# 便捷导出，保持调用方简洁
__all__ = ["get_platform", "PlatformBase"]
