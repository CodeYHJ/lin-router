from __future__ import annotations

import sys

from linrouter_desktop.platform.darwin import DarwinPlatform
from linrouter_desktop.platform.windows import WindowsPlatform


def test_windows_development_autostart_uses_desktop_module_entrypoint() -> None:
    command = WindowsPlatform()._autostart_command()

    assert command == f'"{sys.executable}" "-m" "linrouter_desktop" "--tray"'
    assert "desktop.py" not in command


def test_macos_development_autostart_uses_desktop_module_entrypoint() -> None:
    arguments = DarwinPlatform()._program_arguments()

    assert arguments == [sys.executable, "-m", "linrouter_desktop", "--tray"]
    assert all("desktop.py" not in argument for argument in arguments)
