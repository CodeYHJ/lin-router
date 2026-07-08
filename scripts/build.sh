#!/usr/bin/env bash
set -e

# Lin Router 跨平台构建脚本
# 用法：
#   scripts/build.sh --target win32
#   scripts/build.sh --target darwin
#   scripts/build.sh --target darwin --dmg
# 默认只输出到 dist/；如需同时复制到桌面，请加 --desktop。

TARGET=""
BUILD_DMG=0
COPY_TO_DESKTOP=0

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
    --desktop)
      COPY_TO_DESKTOP=1
      shift
      ;;
    *)
      echo "未知选项：$1" >&2
      echo "用法：$0 --target {win32|darwin} [--dmg] [--desktop]" >&2
      echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "必须指定 --target {win32|darwin}" >&2
  echo "用法：$0 --target {win32|darwin} [--dmg] [--desktop]" >&2
  echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$PROJECT_ROOT/resources"
DIST_DIR="$PROJECT_ROOT/dist"

generate_icon() {
  python "$PROJECT_ROOT/scripts/generate_icon.py" "$1" "$2"
}

copy_to_desktop() {
  local src="$1"
  local name="$(basename "$src")"
  local desktop
  desktop="$(python -c 'from pathlib import Path; print(Path.home() / "Desktop")')"
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

case "$TARGET" in
  win32)
    ICON_PATH="$RESOURCES_DIR/win32/LinRouter.ico"
    if [[ ! -f "$ICON_PATH" ]]; then
      echo "生成 Windows 图标..."
      generate_icon win32 "$ICON_PATH"
    fi
    python -m PyInstaller --noconfirm --clean "$PROJECT_ROOT/LinRouter.spec"
    # 若旧产物仍存在，先尝试删除以避免 mv 失败
    rm -f "$DIST_DIR/LinRouter_windows.exe"
    mv "$DIST_DIR/LinRouter.exe" "$DIST_DIR/LinRouter_windows.exe"
    echo "Windows 构建完成：$DIST_DIR/LinRouter_windows.exe"
    if [[ "$COPY_TO_DESKTOP" == "1" ]]; then
      copy_to_desktop "$DIST_DIR/LinRouter_windows.exe" || exit 1
    fi
    ;;

  darwin)
    ICON_PATH="$RESOURCES_DIR/darwin/LinRouter.icns"
    if [[ ! -f "$ICON_PATH" ]]; then
      echo "生成 macOS 图标..."
      generate_icon darwin "$ICON_PATH"
    fi
    python -m PyInstaller --noconfirm --clean "$PROJECT_ROOT/LinRouter.spec"
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
    echo "用法：$0 --target {win32|darwin} [--dmg] [--desktop]" >&2
    echo "注意：--desktop 显式指定后才会复制产物到桌面" >&2
    exit 1
    ;;
esac
