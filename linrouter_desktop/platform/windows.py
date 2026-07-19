from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .base import PlatformBase, SingleInstanceGuard


class WindowsSingleInstanceGuard(SingleInstanceGuard):
    """Windows 命名互斥量单实例保护。"""

    MUTEX_NAME = "Local\\LinRouterSingleInstance"
    ERROR_ALREADY_EXISTS = 183

    def __init__(self) -> None:
        self._handle: Optional[int] = None
        self._already_running = False

    def acquire(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._handle = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if last_error == self.ERROR_ALREADY_EXISTS:
            self._already_running = True
            return False
        return True

    def release(self) -> None:
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def is_already_running(self) -> bool:
        return self._already_running


class WindowsPlatform(PlatformBase):
    """Windows 平台实现。"""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    AUTO_START_NAME = "LinRouter"

    def get_project_root(self) -> Path:
        if self.is_frozen:
            # PyInstaller 打包后 exe 位于安装目录的 dist/ 子目录，资源根目录是其父目录。
            return Path(sys.executable).resolve().parent.parent
        return Path(__file__).resolve().parents[2]

    def get_user_data_dir(self) -> Path:
        """返回 Windows 用户数据目录，供安装包用户在无本地配置时兜底使用。"""
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        path = base / self.APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _local_data_dir(self) -> Path:
        """返回开发者优先使用的数据目录。打包后为 exe 父级目录，开发时为项目根目录。"""
        return self.get_project_root()

    def get_config_path(self, filename: str = "lin-router-config.json") -> Path:
        local_path = self._local_data_dir() / filename
        if local_path.exists():
            return local_path
        if self.is_frozen:
            return self.get_user_data_dir() / filename
        return local_path

    def get_log_dir(self) -> Path:
        local_dir = self._local_data_dir()
        if (local_dir / "lin-router-logs.jsonl").exists() or (local_dir / "lin-router-config.json").exists():
            return local_dir
        if self.is_frozen:
            return self.get_user_data_dir()
        # 开发模式保持与现有 Windows 行为一致：日志放在配置文件所在目录。
        return self.get_config_path().parent

    def get_executable_path(self) -> Path:
        return Path(sys.executable).resolve()

    # ---------- 开机自启 ----------

    def _autostart_command(self) -> str:
        if self.is_frozen:
            args = [str(self.get_executable_path()), "--tray"]
        else:
            args = [sys.executable, "-m", "linrouter_desktop", "--tray"]
        return " ".join(f'"{arg}"' for arg in args)

    def set_autostart(self, enabled: bool) -> bool:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_WRITE) as key:
                if enabled:
                    winreg.SetValueEx(
                        key,
                        self.AUTO_START_NAME,
                        0,
                        winreg.REG_SZ,
                        self._autostart_command(),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, self.AUTO_START_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    def is_autostart_enabled(self) -> bool:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, self.AUTO_START_NAME)
                return True
        except (FileNotFoundError, OSError):
            return False

    # ---------- 剪贴板 ----------

    def copy_to_clipboard(self, text: str) -> bool:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            cf_unicode_text = 13
            gmem_moveable = 0x0002
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
            if not handle:
                return False
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return False
            ctypes.memmove(locked, data, len(data))
            kernel32.GlobalUnlock(handle)
            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                user32.SetClipboardData(cf_unicode_text, handle)
                user32.CloseClipboard()
                return True
        except Exception:
            pass
        return False

    def open_file(self, path: str | Path) -> bool:
        """使用系统默认程序打开本地文件。"""
        try:
            os.startfile(str(path))
            return True
        except Exception:
            return False

    # ---------- 单实例保护 ----------

    def create_single_instance_guard(self) -> SingleInstanceGuard:
        return WindowsSingleInstanceGuard()
