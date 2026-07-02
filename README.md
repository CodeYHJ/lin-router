# Lin Router

本地 OpenAI 兼容路由器，为 Hermes、Codex++ 和通用 OpenAI 客户端提供统一入口。

现已支持 **Windows** 与 **macOS** 跨平台运行，核心代理逻辑完全复用，仅托盘、开机自启、路径等系统能力做平台适配。

## 快速启动

### 桌面端

```bash
# 方式 1：直接运行源码
python desktop.py

# 方式 2：以模块方式启动（与 desktop.py 等价）
python -m linrouter

# 启动后仅驻留托盘/状态栏，不自动打开浏览器
python desktop.py --tray
python -m linrouter --tray
```

### Windows 产物

```text
dist\LinRouter_windows.exe
```

### macOS 产物

```text
dist/LinRouter.app
```

将 `LinRouter.app` 拖入 `/Applications`，首次启动请使用 **右键 → 打开**（未签名 App 会被 Gatekeeper 拦截）。

### 命令行模式

```bash
python app.py
```

默认地址：

```text
http://127.0.0.1:18400
http://127.0.0.1:18400/v1
```

客户端填写页面里生成的 `lr-...` Key，服务端会按 Key 绑定到对应连接组；也可以使用全局 Key `lin-router`，Lin Router 会在所有连接组中按顺序挑选第一个可用模型。

## 桌面端行为

启动后程序会驻留在系统托盘（Windows）或菜单栏（macOS）：

- 左键/单击图标：打开管理面板
- 右键图标：打开主页 / 查看日志 / 编辑配置 / 复制地址 / 复制全局 Key / 开机自启 / 启动最小化 / 退出
- 开机自启：
  - Windows：写入 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  - macOS：写入 `~/Library/LaunchAgents/com.linrouter.launcher.plist` 并通过 `launchctl` 加载
- 启动最小化：启动后不自动打开浏览器，仅显示托盘/状态栏图标
- 单实例保护：重复启动会自动打开已有实例的管理面板
- macOS 下不显示 Dock 图标，体验与 Windows "最小化到托盘" 等价

## 平台数据路径

| 文件 | Windows | macOS |
|------|---------|-------|
| 配置文件 | 项目根目录 / 可执行文件同级父目录 `lin-router-config.json` | `~/Library/Application Support/LinRouter/lin-router-config.json` |
| 设置文件 | 配置文件同级目录 `lin-router-settings.json` | 配置文件同级目录 `lin-router-settings.json` |
| 请求日志 | 配置文件同级目录 `lin-router-logs.jsonl` | `~/.lin-router/lin-router-logs.jsonl` |

## 主要能力

- 连接组管理：火山方舟 / 中转站 / 通用 OpenAI 代理
- 自动调度模型 `lin-router-auto`
- 全局 Key `lin-router`：跨所有连接组自动挑选第一个可用模型
- 连接组级自动冷却：仅中转站启用
- 自动获取上游模型
- 最近请求日志、详情展开、筛选与 CSV 导出
- 代理测试
- 复制 Hermes 配置
- 复制连接组
- 跨平台系统托盘 / 状态栏、开机自启、启动最小化

## 模式说明

### 火山方舟

- 连接组填写：组名、Base URL、Ark API Key
- 模型填写：显示名称、EP ID

### 中转站

- 连接组填写：组名、Base URL
- 模型填写：显示名称、上游模型、价格组对应 API Key、价格组
- 仅中转站可开启 WAF 兼容
- 可设置自动冷却分钟数

### 通用 OpenAI 代理

- 连接组填写：组名、Base URL、上游 API Key
- 模型可映射到上游模型名，客户端未显式指定模型时按本地配置透传

## Hermes / Codex++

Hermes 推荐配置：

```text
Base URL: http://127.0.0.1:18400/v1
API Key: 对应连接组的 lr-... key
Model: lin-router-auto
```

Codex++ 也走同样的本地入口，建议单独建连接组，并保持请求语义尽量原样透传。

## 预览 / 调试

前端和正式服务共用同一份配置文件，便于调试：

```bash
python app.py --port 18409 --config lin-router-config.json
```

也可以直接双击 `start-preview-18409.bat`（Windows）。

## 跨平台构建

使用统一构建脚本产出 Windows `.exe` 或 macOS `.app`/`.dmg`：

```bash
# Windows
scripts/build.sh --target win32
# -> dist/LinRouter_windows.exe

# macOS
scripts/build.sh --target darwin
# -> dist/LinRouter.app

# macOS + DMG
scripts/build.sh --target darwin --dmg
# -> dist/LinRouter.app + dist/LinRouter.dmg
```

构建前脚本会自动生成对应平台的应用图标（`.ico` / `.icns`）。若直接调用 PyInstaller，spec 文件也会尝试自动生成图标；macOS 上需要 `iconutil` 工具。

```bash
python -m PyInstaller --noconfirm LinRouter.spec
```

## 配置文件

- 正式配置：`lin-router-config.json`
- 模板配置：`lin-router-config.example.json`

真实配置已加入 `.gitignore`，不要提交真实 API Key。
