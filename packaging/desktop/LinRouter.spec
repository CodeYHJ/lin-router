# -*- mode: python ; coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path

# 平台相关配置
is_win32 = sys.platform.startswith('win32')
is_darwin = sys.platform.startswith('darwin')

# pystray 的官方 PyInstaller hook 会无条件收集所有平台后端。这里显式排除
# 当前目标平台不会执行的后端，避免 Windows 包携带 macOS/Linux 依赖，反之亦然。
if is_win32:
    pystray_submodules = [
        "pystray._base",
        "pystray._util",
        "pystray._util.win32",
        "pystray._win32",
    ]
    pystray_excludes = [
        "pystray._appindicator",
        "pystray._darwin",
        "pystray._gtk",
        "pystray._xorg",
        "pystray._util.gtk",
        "pystray._util.notify_dbus",
    ]
elif is_darwin:
    pystray_submodules = ["pystray._base", "pystray._darwin"]
    pystray_excludes = [
        "pystray._appindicator",
        "pystray._gtk",
        "pystray._win32",
        "pystray._xorg",
        "pystray._util.gtk",
        "pystray._util.notify_dbus",
        "pystray._util.win32",
    ]
else:
    pystray_submodules = []
    pystray_excludes = []


def _ensure_icon(target: str, ext: str) -> str | None:
    """缺少源码图标时生成到当前 Desktop build 目录，不回写源码。"""
    icon_path = DESKTOP_ROOT / "resources" / target / f"LinRouter.{ext}"
    if not icon_path.exists():
        icon_path = PROJECT_ROOT / "build" / "desktop" / target / "resources" / f"LinRouter.{ext}"
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [sys.executable, str(DESKTOP_ROOT / "tools" / "generate_icon.py"), target, str(icon_path)],
                check=True,
            )
        except Exception:
            # 生成失败（例如 macOS 下缺少 iconutil）时回退到无图标构建
            return None
    return str(icon_path)


# PyInstaller executes spec files in a dedicated namespace and exposes
# ``SPECPATH``; ``__file__`` is intentionally not guaranteed to exist there.
DESKTOP_ROOT = Path(SPECPATH).resolve()
PROJECT_ROOT = DESKTOP_ROOT.parents[1]
datas = [
    (str(PROJECT_ROOT / "web" / "shared"), "static"),
    (str(PROJECT_ROOT / "web" / "desktop"), "desktop"),
]
if is_win32:
    datas.append((str(DESKTOP_ROOT / "resources" / "win32"), "resources/win32"))
elif is_darwin:
    datas.append((str(DESKTOP_ROOT / "resources" / "darwin"), "resources/darwin"))
icon = None
info_plist = None
argv_emulation = False

if is_win32:
    icon = _ensure_icon('win32', 'ico')
elif is_darwin:
    icon = _ensure_icon('darwin', 'icns')
    info_plist = {'LSUIElement': True}
    argv_emulation = True

hiddenimports = [
    "linrouter_server.settings_store",
    "linrouter_server.upstream_client",
    "linrouter_server.debug_capture",
    "certifi",
    "httpx",
    "h2",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
] + pystray_submodules

a = Analysis(
    # Keep the executable entry inside the Desktop packaging boundary. The
    # entrypoint forwards to linrouter_desktop without relying on a root facade.
    [str(DESKTOP_ROOT / "entrypoint.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # numpy 仅被 Pillow 的 TYPE_CHECKING 分支引用；AVIF 与托盘 ICO/PNG 无关。
    excludes=["numpy", "PIL.AvifImagePlugin", "PIL._avif"] + pystray_excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_args = [pyz, a.scripts, a.binaries, a.datas, []]
exe_kwargs = dict(
    name='LinRouter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=argv_emulation,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if icon:
    exe_kwargs['icon'] = icon

exe = EXE(*exe_args, **exe_kwargs)

if is_darwin:
    app = BUNDLE(
        exe,
        name='LinRouter.app',
        icon=icon,
        bundle_identifier='com.linrouter.launcher',
        info_plist=info_plist,
    )
