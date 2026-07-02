from __future__ import annotations

import argparse
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from app import DEFAULT_CONFIG_FILE, DEFAULT_PUBLIC_API_KEY, DEFAULT_START_PORT, create_server
from linrouter_platform import get_platform
from settings_store import SettingsStore

HOST = "127.0.0.1"
APP_TITLE = "Lin Router"

def create_tray_icon() -> Any:
    """返回托盘图标，使用跨平台动态生成实现。"""
    return get_platform().create_tray_icon()


def copy_to_clipboard(text: str) -> bool:
    """把文本写入系统剪贴板。"""
    return get_platform().copy_to_clipboard(text)


def focus_existing_instance(port: int) -> bool:
    """尝试打开已有实例的管理页面。"""
    try:
        url = f"http://{HOST}:{port}"
        urllib.request.urlopen(url, timeout=1.0)
        webbrowser.open(url)
        return True
    except Exception:
        return False


class LinRouterTray:
    def __init__(self, tray_mode: bool = False, config_path: Optional[Path] = None) -> None:
        self.tray_mode = tray_mode
        self.server: Optional[Any] = None
        self.server_thread: Optional[threading.Thread] = None
        self.port = DEFAULT_START_PORT
        self.ui_url = f"http://{HOST}:{self.port}"
        self.base_url = f"{self.ui_url}/v1"
        self.config_path = config_path or self.resolve_config_path()
        self.settings_store = SettingsStore(self.config_path)
        self.tray_icon: Optional[Any] = None
        self.log_file: Optional[Path] = None
        self._stop_event = threading.Event()

    def resolve_config_path(self) -> Path:
        # 使用平台抽象层返回配置文件路径，避免直接处理 sys.executable / __file__
        return get_platform().get_config_path(DEFAULT_CONFIG_FILE)

    def start_server(self) -> bool:
        try:
            from app import create_server
            self.server, self.port, self.config_path = create_server(HOST, DEFAULT_START_PORT, self.config_path)
            self.log_file = self.server.router.log_file
        except Exception as exc:
            print(f"启动失败：{exc}")
            return False
        self.ui_url = f"http://{HOST}:{self.port}"
        self.base_url = f"{self.ui_url}/v1"
        self.server_thread = threading.Thread(target=self.server.serve_forever, name="LinRouterServer", daemon=True)
        self.server_thread.start()
        # 从配置中读取 settings，并与平台真实自启状态同步
        self._sync_settings_with_platform()
        return True

    def stop_server(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
        self._stop_event.set()

    def _sync_settings_with_platform(self) -> None:
        # 以平台真实的开机自启状态为准，回写独立 settings 文件
        self.settings_store.update({"auto_start": get_platform().is_autostart_enabled()})

    def open_ui(self) -> None:
        webbrowser.open(self.ui_url)

    def _build_menu(self, icon, menu_item):
        from pystray import Menu, MenuItem

        auto_start_enabled = get_platform().is_autostart_enabled()
        # 启动最小化由配置文件里的 settings.start_minimized 决定
        start_minimized = self._load_start_minimized()

        def toggle_auto_start(item):
            new_state = not get_platform().is_autostart_enabled()
            if get_platform().set_autostart(new_state):
                # 回写配置文件
                self._update_config_setting("auto_start", new_state)
                self._refresh_menu()
            else:
                # 失败时弹一个极简提示：通过打开 UI 让用户看到
                copy_to_clipboard("开机自启设置失败，请以管理员身份运行 Lin Router")

        def toggle_start_minimized(item):
            new_state = not self._load_start_minimized()
            self._update_config_setting("start_minimized", new_state)
            self._refresh_menu()

        def open_log_file(item):
            if self.log_file:
                get_platform().open_file(self.log_file)

        def open_config_file(item):
            get_platform().open_file(self.config_path)

        return Menu(
            MenuItem("打开主页", lambda icon, item: self.open_ui()),
            MenuItem("查看日志", open_log_file),
            MenuItem("编辑配置", open_config_file),
            Menu.SEPARATOR,
            MenuItem("复制本地地址", lambda icon, item: copy_to_clipboard(self.ui_url)),
            MenuItem("复制 Base URL", lambda icon, item: copy_to_clipboard(self.base_url)),
            MenuItem(f"复制全局 Key（{DEFAULT_PUBLIC_API_KEY}）", lambda icon, item: copy_to_clipboard(DEFAULT_PUBLIC_API_KEY)),
            Menu.SEPARATOR,
            MenuItem("开机自启", toggle_auto_start, checked=lambda item: get_platform().is_autostart_enabled()),
            MenuItem("启动后最小化到托盘/状态栏", toggle_start_minimized, checked=lambda item: self._load_start_minimized()),
            Menu.SEPARATOR,
            MenuItem("退出", lambda icon, item: self._exit(icon)),
        )

    def _refresh_menu(self) -> None:
        if self.tray_icon:
            self.tray_icon.menu = self._build_menu(self.tray_icon, None)
            self.tray_icon.update_menu()

    def _exit(self, icon) -> None:
        self.stop_server()
        icon.stop()

    def _load_start_minimized(self) -> bool:
        return bool(self.settings_store.get("start_minimized", False))

    def _update_config_setting(self, key: str, value: Any) -> None:
        self.settings_store.update({key: value})

    def run(self) -> None:
        from pystray import Icon

        if not self.start_server():
            return

        # 非托盘模式启动时打开浏览器；托盘模式或 start_minimized 时不打开
        open_browser = not self.tray_mode and not self._load_start_minimized()

        icon_image = create_tray_icon()
        self.tray_icon = Icon(
            "LinRouter",
            icon_image,
            f"{APP_TITLE} ({HOST}:{self.port})",
            menu=self._build_menu(None, None),
        )

        # 左键点击打开面板
        self.tray_icon.on_clicked = lambda icon, button, time: self.open_ui()

        if open_browser:
            threading.Thread(target=self._open_ui_after_delay, daemon=True).start()

        self.tray_icon.run()

    def _open_ui_after_delay(self) -> None:
        time.sleep(0.5)
        self.open_ui()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lin Router desktop tray")
    parser.add_argument("--tray", action="store_true", help="启动后最小化到系统托盘，不自动打开浏览器")
    # 默认不指定 --config，由 resolve_config_path 固定到项目根目录，避免跟随当前工作目录
    parser.add_argument("--config", default=None, help="配置文件路径（默认使用项目根目录 lin-router-config.json）")
    args = parser.parse_args()

    # 单实例保护
    guard = get_platform().create_single_instance_guard()
    if not guard.acquire():
        # 已有实例在运行，尝试打开其管理页面后退出
        focus_existing_instance(DEFAULT_START_PORT)
        sys.exit(0)

    try:
        config_path = Path(args.config) if args.config else None
        app = LinRouterTray(tray_mode=args.tray, config_path=config_path)
        app.run()
    finally:
        guard.release()


if __name__ == "__main__":
    main()
