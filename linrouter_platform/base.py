from __future__ import annotations

import sys
import webbrowser
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SingleInstanceGuard(ABC):
    """单实例保护抽象基类。"""

    @abstractmethod
    def acquire(self) -> bool:
        """尝试获取单实例锁，返回是否成功。"""
        ...

    @abstractmethod
    def release(self) -> None:
        """释放单实例锁。"""
        ...

    @abstractmethod
    def is_already_running(self) -> bool:
        """返回是否已经存在运行中的实例。"""
        ...


class PlatformBase(ABC):
    """Lin Router 平台能力抽象基类。

    所有与操作系统绑定的能力（路径、开机自启、托盘、剪贴板等）均通过此接口暴露，
    业务代码不再直接导入任何平台特定库。
    """

    APP_NAME: str = "LinRouter"
    BUNDLE_ID: str = "com.linrouter.launcher"

    # ---------- 路径 ----------

    @abstractmethod
    def get_project_root(self) -> Path:
        """返回项目根目录（开发时）或打包产物根目录（运行时）。"""
        ...

    @abstractmethod
    def get_config_path(self, filename: str = "lin-router-config.json") -> Path:
        """返回配置文件的绝对路径。"""
        ...

    @abstractmethod
    def get_log_dir(self) -> Path:
        """返回首选日志目录。"""
        ...

    @abstractmethod
    def get_executable_path(self) -> Path:
        """返回当前可执行文件的绝对路径。"""
        ...

    def get_resource_path(self, *parts: str) -> Path:
        """返回静态资源绝对路径，兼容 PyInstaller 的 _MEIPASS 与开发目录。"""
        if self.is_frozen and hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS).joinpath(*parts)
            if bundled.exists():
                return bundled
            return Path(sys.executable).resolve().parent.joinpath(*parts)
        return self.get_project_root().joinpath(*parts)

    # ---------- 开机自启 ----------

    @abstractmethod
    def set_autostart(self, enabled: bool) -> bool:
        """设置开机自启，返回是否成功。"""
        ...

    @abstractmethod
    def is_autostart_enabled(self) -> bool:
        """查询开机自启是否启用。"""
        ...

    # ---------- 托盘 / 剪贴板 / URL ----------

    def create_tray_icon(self) -> Any:
        """返回 pystray 可用的图标对象，默认使用跨平台动态生成图标。"""
        from .common import generate_tray_icon

        return generate_tray_icon()

    @abstractmethod
    def copy_to_clipboard(self, text: str) -> bool:
        """复制文本到系统剪贴板。"""
        ...

    def open_url(self, url: str) -> None:
        """使用系统默认浏览器打开 URL。"""
        webbrowser.open(url)

    @abstractmethod
    def open_file(self, path: str | Path) -> bool:
        """使用系统默认程序打开本地文件，返回是否成功。"""
        ...

    # ---------- 单实例保护 ----------

    @abstractmethod
    def create_single_instance_guard(self) -> SingleInstanceGuard:
        """创建并返回单实例守卫对象。"""
        ...

    # ---------- 平台判断 ----------

    @property
    def is_frozen(self) -> bool:
        """是否处于 PyInstaller 打包状态。"""
        return getattr(sys, "frozen", False)


class UnsupportedPlatform(PlatformBase):
    """未明确支持平台的兜底实现。

    路径方法返回通用 Unix/XDG 风格路径，保证核心代理服务可在 Linux 等系统启动；
    开机自启、剪贴板、单实例保护等桌面能力调用时抛出 NotImplementedError。
    """

    def get_project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def get_config_path(self, filename: str = "lin-router-config.json") -> Path:
        path = Path.home() / ".config" / self.APP_NAME / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def get_log_dir(self) -> Path:
        path = Path.home() / ".local" / "share" / self.APP_NAME / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_executable_path(self) -> Path:
        return Path(sys.executable).resolve()

    def set_autostart(self, enabled: bool) -> bool:
        raise NotImplementedError("当前平台暂不支持开机自启")

    def is_autostart_enabled(self) -> bool:
        return False

    def copy_to_clipboard(self, text: str) -> bool:
        raise NotImplementedError("当前平台暂不支持剪贴板")

    def open_file(self, path: str | Path) -> bool:
        try:
            webbrowser.open(f"file://{Path(path).resolve().as_posix()}")
            return True
        except Exception:
            return False

    def create_single_instance_guard(self) -> SingleInstanceGuard:
        raise NotImplementedError("当前平台暂不支持单实例保护")
