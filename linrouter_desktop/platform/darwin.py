from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

from .base import PlatformBase, SingleInstanceGuard


class DarwinSingleInstanceGuard(SingleInstanceGuard):
    """macOS 文件锁单实例保护。"""

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: Optional[int] = None
        self._already_running = False

    def acquire(self) -> bool:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(self._fd, 0)
            os.write(self._fd, str(os.getpid()).encode("utf-8"))
            return True
        except (IOError, OSError):
            self._already_running = True
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
                self._fd = None
            return False

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        try:
            if self._lock_path.exists():
                self._lock_path.unlink()
        except Exception:
            pass

    def is_already_running(self) -> bool:
        return self._already_running


class DarwinPlatform(PlatformBase):
    """macOS 平台实现。"""

    @property
    def _app_support_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / self.APP_NAME

    @property
    def _lin_router_dir(self) -> Path:
        return Path.home() / ".lin-router"

    @property
    def _launch_agents_dir(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents"

    @property
    def _plist_path(self) -> Path:
        return self._launch_agents_dir / f"{self.BUNDLE_ID}.plist"

    def get_project_root(self) -> Path:
        if self.is_frozen:
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

    def get_config_path(self, filename: str = "lin-router-config.json") -> Path:
        path = self._app_support_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def get_log_dir(self) -> Path:
        path = self._lin_router_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_executable_path(self) -> Path:
        return Path(sys.executable).resolve()

    # ---------- 开机自启 ----------

    def _launchctl_domain(self) -> str:
        return f"gui/{os.getuid()}"

    def _program_arguments(self) -> list[str]:
        if self.is_frozen:
            return [str(self.get_executable_path()), "--tray"]
        return [sys.executable, "-m", "linrouter_desktop", "--tray"]

    def set_autostart(self, enabled: bool) -> bool:
        try:
            self._launch_agents_dir.mkdir(parents=True, exist_ok=True)
            self._lin_router_dir.mkdir(parents=True, exist_ok=True)
            if enabled:
                plist = {
                    "Label": self.BUNDLE_ID,
                    "ProgramArguments": self._program_arguments(),
                    "RunAtLoad": True,
                    "KeepAlive": True,
                    "StandardOutPath": str(self._lin_router_dir / "launchd-stdout.log"),
                    "StandardErrorPath": str(self._lin_router_dir / "launchd-stderr.log"),
                }
                with self._plist_path.open("wb") as fp:
                    plistlib.dump(plist, fp)
                subprocess.run(
                    ["launchctl", "bootstrap", self._launchctl_domain(), str(self._plist_path)],
                    check=True,
                )
            else:
                try:
                    subprocess.run(
                        ["launchctl", "bootout", self._launchctl_domain(), self.BUNDLE_ID],
                        check=True,
                    )
                except subprocess.CalledProcessError:
                    # 可能服务未加载，忽略
                    pass
                if self._plist_path.exists():
                    self._plist_path.unlink()
            return True
        except Exception:
            return False

    def is_autostart_enabled(self) -> bool:
        if not self._plist_path.exists():
            return False
        try:
            with self._plist_path.open("rb") as fp:
                plist = plistlib.load(fp)
            return bool(plist.get("Label") == self.BUNDLE_ID and plist.get("RunAtLoad"))
        except Exception:
            return False

    # ---------- 剪贴板 ----------

    def copy_to_clipboard(self, text: str) -> bool:
        try:
            subprocess.run(["pbcopy"], input=text, text=True, check=True)
            return True
        except Exception:
            return False

    def open_file(self, path: str | Path) -> bool:
        """使用系统默认程序打开本地文件。"""
        try:
            subprocess.run(["open", str(path)], check=True)
            return True
        except Exception:
            return False

    # ---------- 单实例保护 ----------

    def create_single_instance_guard(self) -> SingleInstanceGuard:
        return DarwinSingleInstanceGuard(self._lin_router_dir / "lin-router.lock")
