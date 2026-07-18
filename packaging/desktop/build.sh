#!/usr/bin/env bash
set -e

# Lin Router 跨平台构建脚本
# 用法：
#   packaging/desktop/build.sh --target win32
#   packaging/desktop/build.sh --target win32 --installer
#   packaging/desktop/build.sh --target win32 --installer --sign
#   packaging/desktop/build.sh --target darwin
#   packaging/desktop/build.sh --target darwin --dmg
# 默认只输出到 dist/desktop/<target>；如需同时复制到桌面，请加 --desktop。
# Windows 签名为显式可选项；--sign 会要求完整签名配置，不会静默降级。

TARGET=""
BUILD_DMG=0
BUILD_INSTALLER=0
SIGN_WINDOWS=0
COPY_TO_DESKTOP=0
APP_VERSION="0.6.3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --dmg)
      BUILD_DMG=1
      shift
      ;;
    --installer)
      BUILD_INSTALLER=1
      shift
      ;;
    --sign)
      SIGN_WINDOWS=1
      shift
      ;;
    --version)
      if [[ -z "${2:-}" ]]; then
        echo "--version 需要指定版本号" >&2
        exit 1
      fi
      APP_VERSION="$2"
      shift 2
      ;;
    --desktop)
      COPY_TO_DESKTOP=1
      shift
      ;;
    *)
      echo "未知选项：$1" >&2
      echo "用法：$0 --target {win32|darwin} [--installer] [--sign] [--dmg] [--desktop] [--version x.y.z]" >&2
      echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "必须指定 --target {win32|darwin}" >&2
  echo "用法：$0 --target {win32|darwin} [--installer] [--sign] [--dmg] [--desktop] [--version x.y.z]" >&2
  echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
  exit 1
fi

if [[ "$BUILD_INSTALLER" == "1" && "$TARGET" != "win32" ]]; then
  echo "--installer 仅支持 --target win32" >&2
  exit 1
fi

if [[ "$SIGN_WINDOWS" == "1" && "$TARGET" != "win32" ]]; then
  echo "--sign 仅支持 --target win32；macOS 签名/公证不在本次发布链范围内" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PACKAGING_DIR="$PROJECT_ROOT/packaging/desktop"
RESOURCES_DIR="$PACKAGING_DIR/resources"
DIST_DIR="$PROJECT_ROOT/dist/desktop/$TARGET"
BUILD_DIR="$PROJECT_ROOT/build/desktop/$TARGET"
INSTALLER_SCRIPT="$PACKAGING_DIR/installer/LinRouter.iss"
SELF_INSTALLER_BUILDER="$PACKAGING_DIR/installer/build_self_installer.py"
RELEASE_GUARD="$PACKAGING_DIR/tools/release_guard.py"
SIGNING_HELPER="$PACKAGING_DIR/tools/sign_windows_artifact.py"

# The project does not require a particular dependency manager.  Callers can
# select the interpreter explicitly (for example, the isolated Desktop
# environment) while a direct invocation uses the currently active Python.
if [[ -n "${LINROUTER_DESKTOP_PYTHON:-}" ]]; then
  PYTHON_BIN="$LINROUTER_DESKTOP_PYTHON"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "找不到 Python；请激活构建环境或设置 LINROUTER_DESKTOP_PYTHON" >&2
  exit 1
fi

if ! "$PYTHON_BIN" --version >/dev/null 2>&1; then
  echo "无法执行 Desktop 构建 Python：$PYTHON_BIN" >&2
  exit 1
fi
echo "Desktop 构建 Python：$PYTHON_BIN"

check_build_dependency() {
  local module="$1"
  if ! "$PYTHON_BIN" -c \
    'import importlib.util, sys; raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) else 1)' \
    "$module"; then
    echo "缺少 Desktop 构建依赖：$module" >&2
    echo "请执行：$PYTHON_BIN -m pip install -r $PROJECT_ROOT/requirements/package.txt" >&2
    exit 1
  fi
}

for build_dependency in PyInstaller PIL pystray; do
  check_build_dependency "$build_dependency"
done

mkdir -p "$DIST_DIR" "$BUILD_DIR"

validate_windows_signing() {
  if [[ "$SIGN_WINDOWS" != "1" ]]; then
    return 0
  fi
  local helper_win
  helper_win="$(to_windows_path "$SIGNING_HELPER")"
  "$PYTHON_BIN" "$helper_win" --validate-only
}

sign_windows_artifact() {
  if [[ "$SIGN_WINDOWS" != "1" ]]; then
    return 0
  fi
  local artifact="$1"
  local helper_win artifact_win
  helper_win="$(to_windows_path "$SIGNING_HELPER")"
  artifact_win="$(to_windows_path "$artifact")"
  "$PYTHON_BIN" "$helper_win" "$artifact_win"
}

generate_icon() {
  "$PYTHON_BIN" "$PACKAGING_DIR/tools/generate_icon.py" "$1" "$2"
}

copy_to_desktop() {
  local src="$1"
  local name="$(basename "$src")"
  local desktop
  desktop="$("$PYTHON_BIN" -c 'from pathlib import Path; print(Path.home() / "Desktop")')"
  if [[ ! -d "$desktop" ]]; then
    echo "桌面目录不存在：$desktop" >&2
    return 1
  fi
  local dest="$desktop/$name"
  if [[ -e "$dest" ]]; then
    rm -rf "$dest"
  fi
  cp -R "$src" "$dest"
  echo "已复制到桌面：$dest"
}

build_windows_zip() {
  local source_exe="$DIST_DIR/LinRouter_windows.exe"
  local zip_file="$DIST_DIR/LinRouter-v${APP_VERSION}-win-x64.zip"
  if [[ ! -f "$source_exe" ]]; then
    echo "Windows 可执行文件不存在：$source_exe" >&2
    return 1
  fi
  rm -f "$zip_file"
  local source_exe_win zip_file_win
  source_exe_win="$(to_windows_path "$source_exe")"
  zip_file_win="$(to_windows_path "$zip_file")"
  "$PYTHON_BIN" - "$source_exe_win" "$zip_file_win" <<'PY'
from pathlib import Path
import sys
import zipfile
source = Path(sys.argv[1]).resolve()
zip_path = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(source, "LinRouter/LinRouter.exe")
    archive.writestr("LinRouter/README-新手安装说明.txt", "双击 LinRouter.exe 启动；配置和日志保存在 %APPDATA%\LinRouter。\n")
PY
  echo "Windows 绿色包构建完成：$zip_file"
}

run_release_guard() {
  local release_guard_win
  release_guard_win="$(to_windows_path "$RELEASE_GUARD")"
  local converted_paths=()
  local path
  for path in "$@"; do
    converted_paths+=("$(to_windows_path "$path")")
  done
  "$PYTHON_BIN" "$release_guard_win" "${converted_paths[@]}"
}

find_inno_compiler() {
  if [[ "${LINROUTER_FORCE_SELF_INSTALLER:-}" == "1" ]]; then
    return 1
  fi

  if command -v iscc >/dev/null 2>&1; then
    command -v iscc
    return 0
  fi

  local candidates=(
    "/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
    "/c/Program Files/Inno Setup 6/ISCC.exe"
    "C:/Program Files (x86)/Inno Setup 6/ISCC.exe"
    "C:/Program Files/Inno Setup 6/ISCC.exe"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

to_windows_path() {
  local path="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -aw "$path"
  else
    echo "$path"
  fi
}

build_windows_installer() {
  local source_exe="$DIST_DIR/LinRouter_windows.exe"
  if [[ ! -f "$source_exe" ]]; then
    echo "Windows 可执行文件不存在：$source_exe" >&2
    return 1
  fi

  local output_file="$DIST_DIR/LinRouter-Setup-v${APP_VERSION}-win-x64.exe"
  rm -f "$output_file"

  local iscc_path
  if [[ -f "$INSTALLER_SCRIPT" ]] && iscc_path="$(find_inno_compiler)"; then
    local installer_script_win source_exe_win dist_dir_win
    installer_script_win="$(to_windows_path "$INSTALLER_SCRIPT")"
    source_exe_win="$(to_windows_path "$source_exe")"
    dist_dir_win="$(to_windows_path "$DIST_DIR")"
    "$iscc_path" \
      "/DAppVersion=$APP_VERSION" \
      "/DAppSourceExe=$source_exe_win" \
      "/DAppOutputDir=$dist_dir_win" \
      "$installer_script_win"
  else
    local self_installer_builder_win source_exe_win output_file_win project_root_win
    self_installer_builder_win="$(to_windows_path "$SELF_INSTALLER_BUILDER")"
    source_exe_win="$(to_windows_path "$source_exe")"
    output_file_win="$(to_windows_path "$output_file")"
    project_root_win="$(to_windows_path "$PROJECT_ROOT")"
    "$PYTHON_BIN" "$self_installer_builder_win" \
      --source-exe "$source_exe_win" \
      --output "$output_file_win" \
      --project-root "$project_root_win"
  fi

  echo "Windows 安装包构建完成：$output_file"
  sign_windows_artifact "$output_file"
  if [[ "$COPY_TO_DESKTOP" == "1" ]]; then
    copy_to_desktop "$output_file" || exit 1
  fi
}

case "$TARGET" in
  win32)
    validate_windows_signing
    ICON_PATH="$BUILD_DIR/resources/win32/LinRouter.ico"
    if [[ ! -f "$RESOURCES_DIR/win32/LinRouter.ico" && ! -f "$ICON_PATH" ]]; then
      echo "生成 Windows 图标..."
      generate_icon win32 "$ICON_PATH"
    fi
    spec_file="$(to_windows_path "$PACKAGING_DIR/LinRouter.spec")"
    "$PYTHON_BIN" -m PyInstaller --noconfirm --clean \
      --workpath "$(to_windows_path "$BUILD_DIR/pyinstaller")" \
      --distpath "$(to_windows_path "$DIST_DIR")" \
      "$spec_file"
    # 若旧产物仍存在，先尝试删除以避免 mv 失败
    rm -f "$DIST_DIR/LinRouter_windows.exe"
    mv "$DIST_DIR/LinRouter.exe" "$DIST_DIR/LinRouter_windows.exe"
    echo "Windows 构建完成：$DIST_DIR/LinRouter_windows.exe"
    # 必须先签 payload；自举安装器随后会把这个已签名 EXE 嵌入安装包。
    sign_windows_artifact "$DIST_DIR/LinRouter_windows.exe"
    if [[ "$BUILD_INSTALLER" == "1" ]]; then
      build_windows_zip
      build_windows_installer
      run_release_guard "$DIST_DIR/LinRouter-v${APP_VERSION}-win-x64.zip" "$DIST_DIR/LinRouter-Setup-v${APP_VERSION}-win-x64.exe"
      if [[ "$COPY_TO_DESKTOP" == "1" ]]; then
        copy_to_desktop "$DIST_DIR/LinRouter-v${APP_VERSION}-win-x64.zip" || exit 1
        copy_to_desktop "$DIST_DIR/LinRouter-Setup-v${APP_VERSION}-win-x64.exe" || exit 1
      fi
    elif [[ "$COPY_TO_DESKTOP" == "1" ]]; then
      copy_to_desktop "$DIST_DIR/LinRouter_windows.exe" || exit 1
    fi
    ;;

  darwin)
    ICON_PATH="$BUILD_DIR/resources/darwin/LinRouter.icns"
    if [[ ! -f "$RESOURCES_DIR/darwin/LinRouter.icns" && ! -f "$ICON_PATH" ]]; then
      echo "生成 macOS 图标..."
      generate_icon darwin "$ICON_PATH"
    fi
    "$PYTHON_BIN" -m PyInstaller --noconfirm --clean \
      --workpath "$BUILD_DIR/pyinstaller" \
      --distpath "$DIST_DIR" \
      "$PACKAGING_DIR/LinRouter.spec"
    echo "macOS 构建完成：$DIST_DIR/LinRouter.app"
    if [[ "$BUILD_DMG" == "1" ]]; then
      DMG_PATH="$DIST_DIR/LinRouter.dmg"
      APP_PATH="$DIST_DIR/LinRouter.app"
      if command -v create-dmg >/dev/null 2>&1; then
        create-dmg \
          --volname "LinRouter" \
          --window-pos 200 120 \
          --window-size 800 400 \
          --icon-size 100 \
          --app-drop-link 600 185 \
          "$DMG_PATH" \
          "$APP_PATH"
      else
        hdiutil create -srcfolder "$APP_PATH" -volname "LinRouter" -fs HFS+ -format UDZO "$DMG_PATH"
      fi
      echo "macOS DMG 构建完成：$DMG_PATH"
      if [[ "$COPY_TO_DESKTOP" == "1" ]]; then
        copy_to_desktop "$DMG_PATH" || exit 1
      fi
    elif [[ "$COPY_TO_DESKTOP" == "1" ]]; then
      copy_to_desktop "$DIST_DIR/LinRouter.app" || exit 1
    fi
    ;;

  *)
    echo "不支持的目标平台：$TARGET" >&2
    echo "用法：$0 --target {win32|darwin} [--installer] [--sign] [--dmg] [--desktop] [--version x.y.z]" >&2
    echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
    exit 1
    ;;
esac
