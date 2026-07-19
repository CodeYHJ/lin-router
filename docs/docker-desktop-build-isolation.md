# Docker 与 Desktop 构建隔离实施规范

状态：目录、依赖与构建定义已隔离；根级兼容入口已清理；双向写集 runner 验收中
适用基线：`8ac3fcf` 及其后续兼容提交  
Python：支持 Python 3.12；依赖管理器不作强制要求  
目标读者：负责实施、验证或审查本次重构的 AI/开发者

## 1. 目标

本次重构必须同时实现以下隔离：

1. Docker 最终镜像只包含无头服务运行所需的代码、静态资源和依赖。
2. Desktop 最终产物只包含桌面运行所需的代码、静态资源和依赖。
3. Docker 与 Desktop 可以先后或并行构建，不共用可变虚拟环境、工作目录、缓存目录或产物目录。
4. Desktop 继续复用本地 HTTP server 和业务核心；共享是显式依赖，不是污染。
5. Docker/server 运行路径不能导入、发现或调用桌面平台能力。
6. 保持现有代理、配置、日志、聚合模型、HTTP API 和 Desktop 用户行为不变，明确列出的 Docker 桌面能力移除除外。

当前本地验证基线：Python 3.12 的 Server 环境全量测试通过。测试数量以后可以增长；验收标准是全量通过，不是固定数量。当前开发环境使用 uv 仅是本机运行方式，不是项目依赖标准。

## 2. 非目标

本次不做以下事项：

- 不重写代理转发、候选选择、熔断、WAF、流式协议或日志模型。
- 不切换 Web 框架，不引入 FastAPI、Flask、Django 等新框架。
- 不重做管理 UI，不把 `frontend/` 实验工程替换为正式 UI。
- 不改变配置 JSON 的业务字段及现有迁移语义。
- 不引入 Docker SDK 作为 Python 运行依赖。
- 不要求 Docker 与 Desktop 的所有代码完全无重叠；`core` 和 `server` 是二者都需要的共享代码。
- 不在本次顺便重构与隔离无关的大型业务模块。

## 3. 强制依赖方向

唯一允许的运行时依赖方向如下：

```text
linrouter_desktop ──> linrouter_server ──> linrouter_core
                               │
Docker entrypoint ─────────────┘
```

强制规则：

- `linrouter_core` 不得导入 `linrouter_server`、`linrouter_desktop` 或 `packaging`。
- `linrouter_server` 不得导入 `linrouter_desktop`、`linrouter_platform` 或 `packaging/desktop`。
- `linrouter_desktop` 可以导入 `linrouter_server` 和 `linrouter_core`。
- `packaging/docker` 只能选择和启动 `linrouter_server`。
- `packaging/desktop` 可以打包 `linrouter_desktop`、`linrouter_server`、`linrouter_core`。
- Docker 和 Desktop 的实现不得通过 `sys.platform` 在同一个 composition root 中互相发现；能力必须由入口显式组装。

## 4. 目标目录

为降低迁移风险，本次保留顶层 Python package 布局，不额外引入 `src/`。

```text
lin-router/
├── requirements.txt              # 兼容安装入口
├── requirements/
│   ├── server.txt                # Server/Docker 运行依赖
│   ├── desktop.txt              # Desktop 运行依赖
│   ├── test.txt                  # Server/Core 测试依赖
│   └── package.txt               # Desktop 打包依赖
│
├── linrouter_core/                 # 纯业务核心，二者共享
│   ├── config/
│   ├── contracts/
│   ├── observability/
│   ├── runtime/
│   └── upstream/
│
├── linrouter_server/               # 无头 HTTP server，二者共享
│   ├── __init__.py
│   ├── __main__.py
│   ├── application.py
│   ├── router.py
│   ├── handler.py
│   ├── paths.py
│   ├── settings.py
│   ├── capabilities.py
│   └── static_assets.py
│
├── linrouter_desktop/              # 仅 Desktop
│   ├── __init__.py
│   ├── __main__.py
│   ├── tray.py
│   ├── capabilities.py
│   ├── settings.py
│   └── platform/
│       ├── __init__.py
│       ├── base.py
│       ├── common.py
│       ├── windows.py
│       └── darwin.py
│
├── web/
│   ├── shared/                     # Docker/Desktop 共用管理 UI
│   └── desktop/                    # 仅 Desktop 的启动/托盘设置扩展
│
├── packaging/
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── Dockerfile.dockerignore
│   │   └── entrypoint.sh
│   └── desktop/
│       ├── LinRouter.spec
│       ├── build.sh
│       ├── installer/
│       ├── resources/
│       └── tools/
│
├── tests/
│   ├── core/
│   ├── server/
│   ├── desktop/
│   └── packaging/
│       ├── docker/
│       └── desktop/
│
├── .venvs/                         # gitignored
│   ├── server/
│   └── desktop/
├── build/                          # gitignored
│   ├── docker/
│   └── desktop/
└── dist/                           # gitignored
    ├── docker/
    └── desktop/
```

## 5. 现有文件归属

| 当前路径 | 目标路径/处理方式 |
|---|---|
| `app.py` | 已删除；实现归属 `linrouter_server/`，正式入口为 `python -m linrouter_server` |
| `desktop.py` | 已删除；实现归属 `linrouter_desktop/tray.py`，正式入口为 `python -m linrouter_desktop` |
| `linrouter/__main__.py` | 已删除；不再保留通用 Desktop 兼容 package |
| `linrouter_platform/` | 迁入 `linrouter_desktop/platform/`，完成后删除旧 package |
| `settings_store.py` | 已删除；实现归属 `linrouter_server/settings_store.py`，桌面 schema 归属 `linrouter_desktop/settings.py` |
| `upstream_client.py` | 已删除；实现归属 `linrouter_server/upstream_client.py` |
| `debug_capture.py` | 已删除；实现归属 `linrouter_server/debug_capture.py` |
| `static/` | 公共资源迁入 `web/shared/`，桌面设置逻辑迁入 `web/desktop/` |
| `LinRouter.spec` | 迁入 `packaging/desktop/LinRouter.spec` |
| `scripts/build.sh` | 已删除；Desktop 构建入口归属 `packaging/desktop/build.sh` |
| `scripts/installer/` | 迁入 `packaging/desktop/installer/` |
| 图标生成、签名、release guard | 迁入 `packaging/desktop/tools/` |
| `resources/` | 迁入 `packaging/desktop/resources/` |
| `requirements.txt` | 保留为完整 Desktop 兼容安装入口；新增 `requirements/` 角色清单供 Docker、测试和打包使用 |

Desktop 的源码和冻结入口都通过 owner package 组装，不依赖根级兼容文件：

```python
# python -m linrouter_server
from linrouter_server.__main__ import main

if __name__ == "__main__":
    main()
```

```python
# packaging/desktop/entrypoint.py
from linrouter_desktop.__main__ import main

if __name__ == "__main__":
    main()
```

当前测试和工具必须导入实际 owner package，不再通过 `app`、`desktop`、`settings_store`、`upstream_client` 或 `debug_capture` 兼容模块访问实现。

## 6. 依赖清单与环境隔离

### 6.1 角色化依赖事实源

项目使用标准 requirements 文件，不绑定 uv、pip-tools 或其他依赖管理器：

```text
requirements.txt              -> requirements/desktop.txt
requirements/server.txt       -> certifi、httpx[http2]
requirements/desktop.txt      -> server + pystray、Pillow、平台依赖
requirements/test.txt          -> server + pytest
requirements/package.txt      -> desktop + PyInstaller
```

Docker 只能安装 `requirements/server.txt`；Server 测试只能安装 `requirements/test.txt`；Desktop 打包使用 `requirements/package.txt`。根级 `requirements.txt` 保留完整 Desktop 兼容入口，避免破坏原有 pip 安装命令。

### 6.2 独立虚拟环境

Server 与 Desktop 必须使用不同的环境目录或其他等价隔离机制，避免安装 Desktop 依赖时污染 Server 环境。项目不规定环境创建工具；当前开发环境可以用 uv 创建 `.venvs/server` 和 `.venvs/desktop`，也可以使用标准 `venv`、conda 或其他工具。

Desktop 构建脚本通过 `LINROUTER_DESKTOP_PYTHON` 接收显式解释器；未设置时使用当前激活环境的 `python`。脚本不负责同步、安装或删除依赖。

Docker 在镜像构建阶段创建镜像内部虚拟环境，不挂载或复用宿主机的 Server/Desktop 环境。

## 7. Server 与 Desktop composition root

### 7.1 Server 必须拥有的抽象

`linrouter_server` 定义协议，Desktop 提供实现。协议中不得出现 Windows、macOS、托盘或注册表具体类型。

```python
class RuntimePaths(Protocol):
    def config_path(self, filename: str = "lin-router-config.json") -> Path: ...
    def settings_path(self) -> Path: ...
    def log_dir(self) -> Path: ...
    def shared_resource_path(self, *parts: str) -> Path: ...


class OptionalCapabilities(Protocol):
    def describe(self) -> Mapping[str, Mapping[str, bool]]: ...
    def read_settings(self) -> Mapping[str, object]: ...
    def validate_settings(self, patch: Mapping[str, object]) -> Mapping[str, object]: ...
    def snapshot(self) -> object: ...
    def apply_settings(self, patch: Mapping[str, object]) -> None: ...
    def restore(self, snapshot: object) -> None: ...
```

实际名称可以微调，但所有权和依赖方向不得变化。

### 7.2 Docker/server 组装

`python -m linrouter_server`：

- 使用纯文件系统 `RuntimePaths`。
- 默认监听参数仍由 CLI 提供；Docker entrypoint 显式传入 `0.0.0.0:18400`。
- `OptionalCapabilities` 为 `None`。
- 配置、设置、日志默认落入显式 data 目录；Docker 使用 `/data`。
- 不调用 `get_platform()`，不导入 `linrouter_desktop`。

### 7.3 Desktop 组装

`python -m linrouter_desktop`：

- 创建当前 OS 的 platform adapter。
- 创建 Desktop `RuntimePaths`。
- 创建 Desktop capabilities，并显式传给 `linrouter_server.create_server()`。
- 保持单实例、托盘、浏览器打开、剪贴板、开机自启和启动最小化现有行为。
- Server 内部不能自行再次发现 platform；同一实例由 Desktop composition root 持有。

## 8. 设置与 API 行为

### 8.1 设置所有权

公共 server 设置至少包括：

```text
theme
auto_refresh_logs
debug_mode
upstream_http_client
upstream_http2
upstream_keepalive
debug_capture_enabled
debug_capture_last_body
normalize_tools_order
smart_breaker_enabled
```

Desktop 设置包括：

```text
auto_start
start_minimized
```

公共 `SettingsStore` 接受由 composition root 注入的 schema/defaults：

- Docker 注入公共 schema。
- Desktop 注入公共 schema与 Desktop schema 的组合。
- `auto_start` 的系统真实状态由 Desktop capability 读取；持久化值不能冒充系统状态。

### 8.2 Docker API

Docker/server-only 模式：

- `/api/state` 的 `settings` 不包含 `auto_start` 或 `start_minimized`。
- `capabilities` 可以为空对象；不得伪造 Desktop 可用。
- `/api/settings` 收到 Desktop 字段时返回稳定的 `400` JSON 错误，不允许抛出异常或断开连接。
- 备份导入遇到 Desktop 字段时忽略或拒绝必须统一。为避免静默误导，本规范选择拒绝，并使用与 `/api/settings` 相同的类型化错误。
- Docker 日志中不得出现 `NotImplementedError` 作为正常用户操作结果。

推荐错误结构：

```json
{
  "error": {
    "message": "当前运行方式不支持桌面设置：auto_start",
    "type": "invalid_request_error",
    "code": "unsupported_capability"
  }
}
```

### 8.3 Desktop API

Desktop 模式继续支持两个 Desktop 字段。设置写入必须是事务式的：

1. 校验全部字段。
2. 快照文件设置和系统 Desktop 状态。
3. 应用系统副作用。
4. 持久化设置。
5. 任一步失败时恢复二者；如果恢复失败，返回明确错误并记录日志。

不得在 HTTP handler 内直接调用注册表或 LaunchAgent。

## 9. Web 静态资源隔离

当前 `static/js/settings-panel.js` 同时包含公共设置与 Desktop 设置，必须拆分。

`web/shared/`：

- 首页、连接配置、日志、统计、测速、公共设置。
- 不得出现 `auto_start`、`start_minimized`、注册表、LaunchAgent、托盘等字符串或实现。

`web/desktop/`：

- 启动设置区块。
- `auto_start`、`start_minimized` 事件绑定。
- Desktop 提示文案。

`linrouter_server.static_assets` 提供通用资源根和可选扩展脚本机制：

- Docker 只注册 `web/shared`。
- Desktop 注册 `web/shared` 和 `web/desktop`。
- 公共 HTML 可以保留通用扩展占位符，但不能硬编码 Desktop 脚本名。
- Docker build 必须完全不复制 `web/desktop`，不能仅靠 CSS 隐藏。

## 10. Docker 构建

### 10.1 构建上下文

统一从仓库根目录构建：

```bash
docker build -f packaging/docker/Dockerfile -t lin-router:local .
```

`packaging/docker/Dockerfile.dockerignore` 至少排除：

```text
.git
.github
.tmp
.venvs
build
dist
tests
docs
PRD
frontend
linrouter_desktop
linrouter_platform
web/desktop
packaging/desktop
resources
*.spec
*.exe
*.dmg
*.app
lin-router-config.json
lin-router-settings.json
lin-router-logs.jsonl
```

Dockerfile 仍必须白名单 `COPY`，不能依赖 ignore 文件作为唯一边界：

```text
requirements/server.txt
linrouter_core/
linrouter_server/
web/shared/
```

Docker 不复制任何根级兼容模块；Server 实现只从 `linrouter_server/` 和 `linrouter_core/` 白名单路径进入镜像。

### 10.2 镜像要求

- 多阶段构建。
- Python 3.12。
- 构建阶段使用 Python 3.12 的 venv 和 pip 安装 `requirements/server.txt`，不得读取 Desktop、test 或 package 清单。
- 最终阶段不包含 pip 缓存、编译工具、测试、文档或其他不必要的构建材料。
- 使用非 root 用户运行。
- 工作目录固定，例如 `/app`。
- 数据目录固定为 `/data`，配置、设置和日志持久化到该目录。
- 暴露 `18400`。
- entrypoint 启动 `python -m linrouter_server --host 0.0.0.0 --port 18400 --config /data/lin-router-config.json`。
- 提供 `/health` healthcheck。
- 最终镜像中导入 `pystray`、`PIL` 或 `objc` 必须失败。

## 11. Desktop 构建

### 11.1 文件组织

以下内容全部迁入 `packaging/desktop/`：

- PyInstaller spec。
- Windows/macOS build script。
- Inno Setup 和自举安装器。
- 图标、签名、release guard 工具。
- Windows/macOS 资源。

spec 以自身路径推导仓库根目录，不依赖调用者当前工作目录。

### 11.2 输入边界

Desktop spec 只允许收集：

```text
linrouter_core
linrouter_server
linrouter_desktop
web/shared
web/desktop
packaging/desktop/resources/<current-platform>
```

不得收集：

```text
packaging/docker
Dockerfile
Docker entrypoint
Docker SDK
tests
docs
frontend
另一平台不需要的托盘后端
```

### 11.3 输出边界

所有 Desktop PyInstaller 参数必须显式设置：

```text
--workpath build/desktop/<platform>/pyinstaller
--distpath dist/desktop/<platform>
--specpath build/desktop/<platform>/spec（仅动态 spec 时）
```

安装器、ZIP、DMG、签名中间文件也分别进入：

```text
build/desktop/<platform>/installer
dist/desktop/<platform>
```

图标缺失时生成到 `build/desktop/<platform>/resources`，禁止在构建期间写回源码目录。

CI、README、release workflow 必须同步更新到新产物路径，不保留第二份根级 `dist/` 兼容复制，因为复制会重新造成双写和清理歧义。

## 12. 实施顺序

每个阶段必须独立通过全量测试和 `git diff --check` 后才能进入下一阶段。禁止把全部迁移压成单个超大提交。

### Phase 0：增加失败契约

先增加当前会失败的隔离测试：

- Server dependency graph 不得引用 Desktop package。
- Server-only `/api/state` 不得返回 Desktop 设置。
- Server-only 更新 `auto_start` 返回稳定 400，不能断开连接。
- Server-only 真实入口可在只有公共依赖时启动。

本阶段只允许测试失败，不改业务实现。

### Phase 1：建立角色化依赖清单

- 恢复根级 `requirements.txt` 兼容入口。
- 创建 `requirements/server.txt`、`desktop.txt`、`test.txt`、`package.txt`。
- Docker 只安装 Server 清单；Desktop 和测试使用各自角色清单。
- 环境可以由 venv、uv、conda 或其他工具创建，不把工具写入项目强制入口。
- 保持现有代码和运行行为。

Gate：server-only 环境能跑全量现有测试；环境中没有 Desktop 依赖。

### Phase 2：建立 package 目录和兼容入口

- 创建 `linrouter_server`、`linrouter_desktop`。
- 迁移 Desktop tray 与 platform package。
- 迁移 `app.py` 实现到明确 owner；完成后删除根级兼容入口。
- 更新测试导入路径。

Gate：现有 Desktop 启动契约与 HTTP 契约全部通过；依赖方向扫描通过。

### Phase 3：解除 Server 对 Desktop 的运行时依赖

- 引入 `RuntimePaths` 与 `OptionalCapabilities`。
- `create_server` 接收显式组装参数。
- 删除 server 内的 `get_platform()`、`sys.platform` Desktop discovery。
- Desktop composition root 注入真实能力，Docker/server-only 注入 `None`。

Gate：Phase 0 中 server-only 契约转为通过，Desktop 既有契约仍通过。

### Phase 4：拆分设置和静态资源

- 拆公共与 Desktop schema。
- 增加设置事务协调器。
- 拆 `web/shared`、`web/desktop`。
- Docker/server-only 不再暴露或加载 Desktop 设置与资源。

Gate：扫描 `web/shared` 不包含 Desktop 专属标识；备份导入和设置失败回滚测试通过。

### Phase 5：迁移 Desktop packaging

- 移动 spec、build script、installer、resources、tools。
- 显式隔离 Desktop 的解释器、`build/desktop`、`dist/desktop`；解释器通过环境或 `LINROUTER_DESKTOP_PYTHON` 选择。
- 更新 CI、README、release workflow。

Gate：Windows/macOS 对应 CI 打包成功，产物清单符合边界。

### Phase 6：增加 Docker packaging

- 增加 Dockerfile、Dockerfile-specific ignore、entrypoint。
- 使用多阶段和白名单复制。
- 增加非 root、`/data`、端口和 healthcheck。
- 增加 Docker 镜像内容测试和真实 API smoke。

Gate：镜像内容、依赖、运行态和持久化测试全部通过。

### Phase 7：交叉构建验证和清理

- 先 Docker 后 Desktop。
- 先 Desktop 后 Docker。
- 可用时并行运行二者。
- 验证双方只写各自目录。
- 删除旧 package、旧构建入口和过期文档引用；保留根 `requirements.txt` pip 兼容入口。

Gate：工作树除预期产物目录外无构建写入；双方产物互不变化或删除。

## 13. 必需测试

### 13.1 静态边界测试

- AST/文本扫描 `linrouter_server`，禁止导入 `linrouter_desktop`、`linrouter_platform`。
- 扫描 `linrouter_core`，禁止导入 server/Desktop/packaging。
- 扫描 `web/shared`，禁止 Desktop 专属字符串。
- 扫描 Dockerfile，禁止 `COPY .` 和 Desktop 路径。

静态扫描不是唯一验证，但应作为快速失败 gate。

### 13.2 Server-only 测试

在只安装 `requirements/test.txt` 的独立 Server 环境中执行：

```bash
python -m pip install -r requirements/test.txt
python -m pytest -q -p no:cacheprovider
```

并验证：

- `python -m linrouter_server` 可启动。
- `/health` 返回 200。
- `/api/state` 无 Desktop 设置。
- Desktop 设置写入返回 400 JSON。
- `python -c "import pystray"` 失败。
- `python -c "import PIL"` 失败。

### 13.3 Desktop 测试

- Desktop composition root 注册真实/伪造 capabilities。
- 单实例、托盘、打开浏览器和配置路径契约保持不变。
- Desktop 设置更新成功路径和回滚路径均覆盖。
- PyInstaller 分析清单不包含 Docker 文件或不相关平台后端。
- Windows/macOS 产物至少分别在对应 CI runner 构建。

### 13.4 Docker 镜像测试

至少验证：

```bash
docker run --rm lin-router:test python -c "import linrouter_server, linrouter_core"
docker run --rm lin-router:test sh -c "test ! -e /app/linrouter_desktop"
docker run --rm lin-router:test sh -c "test ! -e /app/packaging/desktop"
docker run --rm lin-router:test python -c "import pystray"  # 必须非零退出
docker run --rm lin-router:test python -c "import PIL"      # 必须非零退出
```

启动容器后验证 `/health`、`/api/state`、公共设置更新、数据卷重启持久化以及非 root UID。

### 13.5 构建写集测试

构建前后比较工作树和约定目录：

- Docker 构建不得修改 `build/desktop`、`dist/desktop`、源码资源。
- Desktop 构建不得修改 `build/docker`、`dist/docker`、Docker 上下文文件。
- 任一构建失败不能删除另一方已有产物。
- `--clean` 只能清理当前 target 的明确子目录。

## 14. CI 目标矩阵

| Job | 环境 | 依赖 | 职责 |
|---|---|---|---|
| `verify-server` | Ubuntu + Python 3.12 | base + dev | 全量测试、server-only 和依赖边界 |
| `build-docker` | Ubuntu | base | 构建镜像、内容扫描、HTTP smoke |
| `package-windows` | Windows | base + desktop + package | EXE/ZIP/安装器 |
| `package-macos` | macOS | base + desktop + package | APP/DMG |
| `release` | GitHub Actions | 下载已验证产物 | 只聚合，不重新构建 |

Desktop 支持目标仅为 Windows/macOS；Linux 当前只运行 Docker Server，不执行 Desktop import、托盘或打包测试。未来若重新启用 Linux Desktop，仍必须保持 `pystray` 和 Pillow 延迟导入，并通过 fake capability/platform 测试。

## 15. 完成定义

全部满足才可以宣称完成。下列状态以第 18.12 节的最新复检为准：

- [x] `requirements.txt` 和角色化 `requirements/` 清单已提交。
- [x] server 与 Desktop 使用不同环境目录或等价的依赖隔离方式。
- [x] 目标 package 和 packaging 目录已建立，旧实现文件只剩兼容入口或已删除。
- [x] `linrouter_server` 和 `linrouter_core` 不导入 Desktop。
- [x] Docker API 不暴露 Desktop 设置，错误不会导致连接断开。
- [x] Docker 静态资源不含 Desktop 设置代码。
- [ ] Docker 最终镜像不含 Desktop package、依赖、资源和构建工具（复制清单和依赖契约已通过；运行时镜像内容 smoke 按用户要求暂缓）。
- [x] Desktop 产物清单不收集 Docker 专属文件或依赖。
- [ ] Desktop 当前功能和发布产物保持可用（Windows/macOS 构建已通过，最小运行 smoke 尚未执行）。
- [x] Docker/Desktop 工作目录、缓存、产物目录完全分开。
- [ ] 两种构建方向的写集保护均通过（定义和本地自测已完成，修改后的目标 runner 尚需执行）。
- [ ] 全量测试、静态边界测试、真实 server smoke、镜像 smoke 和平台打包均通过（镜像运行时 smoke 暂缓）。
- [x] README、CI、release workflow 与最终目录和依赖清单一致。
- [x] `git diff --check` 通过，工作树没有非预期构建写入。

## 16. 禁止的捷径

实施 AI 不得采用以下方式假装完成隔离：

- 只增加 `.dockerignore`，Dockerfile 仍使用 `COPY .`。
- Docker 安装完整 `requirements.txt` 后声称平台 marker 已经隔离。
- 在 Docker UI 中只用 CSS 隐藏 Desktop 控件，代码仍被复制进镜像。
- Server 继续调用 `get_platform()`，仅让 Linux fallback 返回 `False`。
- 捕获所有 `NotImplementedError` 后静默忽略。
- Server/Desktop 继续共用 `.venv`、`build/` 根目录或 `dist/` 根目录。
- 构建后把产物再复制回旧 `dist/` 作为长期兼容。
- 同一阶段同时重构无关业务逻辑。
- 只跑专项测试，不跑全量回归和真实入口 smoke。
- 因测试难改而删除原有契约测试。

## 17. 执行 AI 的交付格式

每个 Phase 完成后必须报告：

1. 本阶段修改的边界和文件。
2. 依赖方向是否变化。
3. 执行的 Python/pip 命令及 Python 版本；如果当前环境使用 uv，单独注明其仅为本地工具。
4. 专项测试、全量测试和 smoke 结果。
5. 构建写入了哪些目录。
6. 尚未完成的 Phase 和已知风险。

如果实施过程中发现需要改变本规范中的依赖方向、API 行为、目录所有权或完成定义，必须暂停并请求用户确认；普通文件命名、内部函数拆分和测试组织不属于需要确认的架构变更。

## 18. 2026-07-17 实施复检记录

本节记录当前工作树复检结果。以下阻塞项修复并完成目标环境验证之前，不得宣称本次隔离迁移完成。

### 18.1 已复现的阻塞项

#### B1：`packaging` 顶层包覆盖第三方同名依赖

当前 `packaging/__init__.py` 使仓库根目录下的 `packaging` 成为 Python package，覆盖 PyInstaller 依赖的第三方 `packaging`。

复现命令：

```bash
.venvs/desktop/bin/python -m PyInstaller \
  --noconfirm --clean \
  --workpath /tmp/linrouter-review-build \
  --distpath /tmp/linrouter-review-dist \
  packaging/desktop/LinRouter.spec
```

当前错误：

```text
ModuleNotFoundError: No module named 'packaging.requirements'
```

修复要求：

- `packaging/` 必须只作为构建文件目录，不能覆盖第三方 `packaging`。
- 根级兼容工具不得依赖把 `packaging/` 变成 Python package；应直接执行目标文件或使用不会污染顶层模块名的加载方式。
- 从仓库根目录执行 PyInstaller 时，`import packaging.requirements` 必须解析到虚拟环境中的第三方库。

#### B2：PyInstaller spec 使用未定义的 `__file__`

规避 B1、从仓库外启动 PyInstaller 后，`packaging/desktop/LinRouter.spec` 在计算项目根目录时失败。

当前错误：

```text
NameError: name '__file__' is not defined
```

修复要求：

- 使用 PyInstaller spec 执行上下文明确提供的路径信息，例如 `SPECPATH`，不能假设 `__file__` 存在。
- 必须分别在 Windows 和 macOS runner 上真实执行 spec，不能只做文本或语法扫描。

#### B3：Desktop 打包入口不是稳定的 package composition root

当前 spec 直接分析 `linrouter_desktop/tray.py`。直接执行该文件时，脚本目录进入 `sys.path`，其中的 `linrouter_desktop/platform/` 可能覆盖标准库 `platform`；同时 package 相对导入的执行语义不稳定。

已观察到的直接入口错误包括：

```text
ModuleNotFoundError: No module named 'linrouter_server'
AttributeError: module 'platform' has no attribute 'system'
```

修复要求：

- PyInstaller 应使用稳定的根级/专用 Desktop composition entry，或保证入口全部使用可打包的绝对导入且不会让 `platform/` 覆盖标准库。
- `python -m linrouter_desktop --help`、源码 Desktop 启动和 PyInstaller 冻结入口必须指向同一套组装逻辑。

#### B4：将当前环境 uv 误写为项目强制标准（已重新分类）

原复检把“当前环境使用 uv 控制 Python 版本”误判成“项目必须使用 uv”。这导致 requirements.txt 被删除、uv manifest 被新增、Docker/README/构建入口被绑定到 uv。

重新确认：该问题是迁移范围判断错误，不是项目运行时隔离要求。U1–U7 负责恢复依赖管理器无关的 requirements 和 Python/pip 入口；Server/Desktop 仍然必须使用不同环境或等价依赖隔离方式，但不规定环境创建工具。

#### B5：Docker entrypoint 忽略容器命令，CI smoke 无法执行

当前 `packaging/docker/entrypoint.sh` 无条件启动 `python -m linrouter_server`，没有处理 `"$@"`。因此下面这些命令不会执行用户指定的 `python`、`test` 或 `id`，而会启动服务：

```bash
docker run --rm lin-router:ci id -u
docker run --rm lin-router:ci python -c "import linrouter_server"
docker run --rm lin-router:ci test -e /app/linrouter_desktop
```

这会导致 CI 首个内容检查挂起或得到错误结果。

修复要求：

- entrypoint 在收到显式命令时必须 `exec "$@"`，无参数时才启动默认 Server；或所有检查显式使用正确的 `--entrypoint`。
- 第 13.4 节列出的原样命令必须能够执行并返回稳定退出码。

#### B6：Desktop capability 与 HTTP Server 使用不同 SettingsStore

`LinRouterTray` 先创建一个 `SettingsStore` 并注入 `DesktopCapabilities`，`create_server` 随后又创建另一个 Server SettingsStore。两者指向同一文件但持有不同内存状态。

已复现：调用 `/api/settings` 更新 `start_minimized=true` 后：

```text
API response start_minimized = false
Tray memory start_minimized = missing/false
settings file start_minimized = true
```

修复要求：

- Desktop composition root 必须让 capability、Tray 和 HTTP Server 共享同一个设置状态所有者，或在提交后进行明确且可测试的同步。
- 增加真实 Desktop composition 测试，覆盖 `start_minimized` 更新后的 API 响应、内存状态、落盘状态和回滚路径。

### 18.2 高风险兼容项

#### R1：根级 `static` 符号链接的 Windows 可移植性

当前根级 `static` 是指向 `web/shared` 的符号链接。Windows checkout 在未启用 symlink 或缺少创建权限时，可能把它检出为普通文本文件，导致旧源码入口按 `static/index.html` 查找资源时失败。

验收要求：

- 在标准 Windows GitHub runner 和至少一个默认 Git for Windows 配置下验证源码启动。
- 如不能保证 symlink，应删除对根级 `static` 的运行时依赖，或提供不依赖操作系统 symlink 能力的兼容方案。

#### R2：Docker `/api/state` CI 断言检查层级错误

当前 CI 使用 `assert 'auto_start' not in data`，但 `/api/state` 的设置位于 `data['settings']`。当前真实 Server 行为已人工确认会从嵌套 settings 中移除 `auto_start` 和 `start_minimized`，但 CI 断言本身不能防止该行为回归。

验收要求：

```python
assert "auto_start" not in data["settings"]
assert "start_minimized" not in data["settings"]
```

同时应校验 Desktop 设置写入返回稳定的 400 JSON 和 `unsupported_capability`。

### 18.3 尚未完成的目标环境验证（历史复检快照）

本节保留 2026-07-17 复检时的原始状态，不再代表当前进度；最新目标环境证据和剩余项以第 18.12 节为准。

当前环境没有 Docker、Podman、Buildah、actionlint，也不是 Windows/macOS runner，因此以下项目仍未验证：

- Dockerfile 真实构建、最终镜像清单、非 root UID、healthcheck 和 `/data` 持久化。
- Windows EXE、ZIP、安装器构建及运行。
- macOS APP、DMG 构建及运行。
- GitHub Actions workflow 已通过本地 YAML 语法解析，但 action schema、表达式和 runner 真实行为仍未验证。
- Docker 后 Desktop、Desktop 后 Docker以及可行时并行构建的写集隔离。
- 任一构建失败时不会删除或改变另一方已有产物。

### 18.4 当前已通过但覆盖不足的检查

- `git diff --check` 通过。
- 全量 Python 测试曾达到 `244 passed`。
- 本次复检的隔离、Desktop 启动和设置专项测试为 `14 passed`。
- Server-only `/api/state.settings` 已人工确认不包含 `auto_start`、`start_minimized`。
- 静态扫描确认 `linrouter_server`、`linrouter_core` 没有直接导入 Desktop package。

上述结果不能覆盖真实 Docker/PyInstaller 构建；特别是 B1、B2 已证明“现有测试全绿”不代表 Desktop 可以出包。

### 18.5 本轮处理结果（2026-07-17）

- B1 已处理：删除 `packaging`、`packaging/desktop`、`packaging/desktop/tools` 的 Python `__init__.py`，兼容脚本改为按文件路径加载；`packaging.requirements` 已恢复解析到 Desktop 虚拟环境的第三方依赖。
- B2 已处理：spec 改用 PyInstaller 提供的 `SPECPATH`；Linux 本机已完成一次 PyInstaller 分析、构建和冻结产物 `--help` 验证。
- B3 历史修复曾使用根级 `desktop.py` 兼容入口；RC1 已改为 `packaging/desktop/entrypoint.py`，Windows/macOS runner 仍需按新入口重新验证。
- B4 已重新分类：原结论把当前环境的 uv 使用误写为项目强制标准；后续由 U1–U7 恢复 requirements 和依赖管理器无关入口。
- B5 已处理：Docker entrypoint 现在在收到显式命令时透传 `exec "$@"`，CI `/api/state` 断言也改为检查嵌套 `settings`；真实 Docker runner 仍需执行。
- B6 已处理：`settings_store_instance` 从 Desktop composition root 注入 Server，Tray、capability 和 HTTP Server 可共享同一 Store；新增 API 与落盘状态回归测试。
- R1 已处理代码侧风险：删除根级 `static` 符号链接，运行时和既有前端测试改用 `web/shared`；Windows 源码启动仍需 runner 验证。
- R2 已处理：CI 检查 `data["settings"]` 中的 Desktop 字段，而不是只检查顶层。

本轮结果：Server 全量测试 `246 passed`，Desktop/隔离专项测试 `29 passed`，Python/JavaScript/Shell 语法检查和 `git diff --check` 通过。Docker、Windows、macOS 目标环境验证仍是完成前置条件。

### 18.6 迁移问题任务拆分（待安排）

本节只记录本次 Docker/Desktop 隔离迁移新引入的问题，以及为达到隔离目标但尚未完成的迁移项。原 `main` 已存在的“备份导入非事务性”和 `SettingsStore.update()` 保存失败后不回滚内存，不归类为迁移缺陷；如果下列任务的完整验收依赖修复这些历史问题，应另建历史缺陷任务并显式建立依赖关系。

本节保留为初始拆分记录；其最新状态以 18.8、18.10、18.11 和 18.12 为准。

#### M1：为 Server/Desktop 注入不同的设置 schema

- 类型：迁移引入的隔离缺陷。
- 优先级：P0。
- 现状：Server 的默认设置虽然已经移除 `auto_start`、`start_minimized`，但 `SettingsStore.load()` 仍无条件合并设置文件中的任意字段；`linrouter_desktop/settings.py` 中的 `DESKTOP_SETTINGS` 尚未注入 Store。
- 目标：公共 Store 只保存其 schema 允许的字段；Server composition 使用公共 schema，Desktop composition 使用“公共 + Desktop”schema。
- 修改范围：`linrouter_server/settings_store.py`、`linrouter_desktop/settings.py`、Server/Desktop composition root 及对应测试。
- 验收标准：
  - Server 读取包含 Desktop 历史字段的旧设置文件后，`to_dict()`、`/api/settings`、`/api/state` 均不包含 Desktop 字段。
  - Server 后续保存不会再次写出 Desktop 字段。
  - Desktop 仍能读取、更新并保存 `auto_start`、`start_minimized`。
  - Server 与 Desktop 不通过互相导入 package 来获得 schema。

#### M2：修复 Server 备份的 Desktop 字段泄漏和自导入失败

- 类型：迁移引入的行为缺陷。
- 优先级：P0。
- 依赖：M1。
- 现状：`/api/state` 会隐藏 Desktop 字段，但 `/api/backup/export` 直接导出 Store 原始内容；当旧设置文件含 Desktop 字段时，Server 可能导出包含 Desktop 设置的备份，随后又因 `unsupported_capability` 拒绝导入自己导出的备份。
- 目标：备份导出和导入使用当前 composition 的设置 schema，保证 Server 备份只含 Server 设置，并满足同一运行方式的导出/导入闭环。
- 修改范围：备份 export/import 组装逻辑、设置视图/序列化边界及 API 测试。
- 验收标准：
  - Server 从旧设置文件启动后导出的备份不含 `auto_start`、`start_minimized`。
  - Server 可以成功导入自己导出的备份。
  - 外部备份显式携带 Desktop 字段时，Server 仍返回稳定的 `400` JSON，错误码为 `unsupported_capability`，且不会发生连接中断。
  - Desktop 备份仍可保留并恢复 Desktop 设置。
- 边界说明：备份导入跨配置与设置的完整事务回滚是原 `main` 历史缺陷，不在本任务中顺带重构；如验收要求失败后所有配置均不变化，应先建立独立历史缺陷任务。

#### M3：修复 Docker `/data` 持久化卷权限

- 类型：迁移新增 Docker 实现问题。
- 优先级：P0。
- 现状：镜像以 UID `10001` 运行，但 README 和 CI 使用宿主机 bind mount；Docker 创建或宿主机已有的目录可能不允许 UID `10001` 写入。
- 目标：默认文档和 CI 使用对非 root 容器稳定可写的持久化方式。
- 修改范围：README Docker 命令、`.github/workflows/ci.yml`；如需改变镜像目录初始化，再修改 Dockerfile/entrypoint。
- 验收标准：
  - 容器保持 UID `10001`，首次启动可在 `/data` 创建配置、设置和日志。
  - 停止并删除容器后，使用同一 volume 重启可以读取先前写入的数据。
  - README 默认命令可直接执行，不依赖用户手工 `chmod 777`。
  - 优先使用 named volume；如保留 bind mount，必须明确创建目录和所有权策略，并在 CI 中真实验证。

#### M4：使 Docker healthcheck 与运行端口一致

- 类型：迁移新增 Docker 实现问题。
- 优先级：P1。
- 现状：运行端口可由 `LINROUTER_PORT` 配置，但 Dockerfile healthcheck 固定访问 `18400`。
- 目标：覆盖端口配置后，服务监听端口、端口映射和 healthcheck 使用一致值；或者明确取消端口可配置能力并统一文档。
- 修改范围：`packaging/docker/Dockerfile`、entrypoint/环境变量约定、README 和 Docker smoke。
- 验收标准：默认端口和至少一个非默认端口分别启动成功，容器最终状态均为 `healthy`。

#### M5：修复 Desktop 直接打包命令的输出目录隔离

- 类型：迁移遗漏；根目录输出行为在原 `main` 已存在，但不再满足本次隔离目标。
- 优先级：P1。
- 现状：README 中直接调用 PyInstaller 的命令未指定 `--workpath` 和 `--distpath`，会写入仓库根级 `build/`、`dist/`。
- 目标：所有受支持的 Desktop 打包入口都只写入 Desktop 专属缓存和产物目录。
- 修改范围：README、Desktop build script/spec 调用约定及构建写集契约测试。
- 验收标准：
  - 文档中的直接命令或其替代命令明确使用 Desktop 专属 `workpath`/`distpath`。
  - 从干净工作树执行 Desktop 构建后，不产生根级 `build/`，也不写入 Docker 专属目录。
  - 失败构建不会删除或改变已有 Docker 产物。

#### M6：补齐 Docker 隔离与持久化 CI

- 类型：迁移验证缺口。
- 优先级：P1。
- 依赖：M1、M2、M3、M4。
- 现状：当前 Docker CI 只覆盖镜像内容、health 和 `/api/state` 的部分检查，未覆盖公共设置写入、Desktop 设置拒绝、重启持久化和构建写集。
- 目标：让 CI 能发现 Server/Desktop 设置串入、非 root 写入失败、持久化失效和构建互相污染。
- 验收标准：CI 至少覆盖：
  - 公共设置写入成功并在重启后保留。
  - Desktop 设置写入返回 `400 unsupported_capability`。
  - Server 备份不含 Desktop 字段并可自导入。
  - 镜像不含 Desktop package、资源、依赖和 Desktop packaging 工具。
  - Docker 构建前后的 Desktop 产物 hash 不变，且工作树没有非预期写入。

#### M7：补齐 Desktop 独立验证矩阵与失败回滚测试

- 类型：迁移验证缺口。
- 优先级：P1。
- 现状：Linux Desktop 暂不支持，不建立 Linux `verify-desktop`；macOS preview 已补入 PR/手动触发的 CI，Desktop 设置仍只覆盖成功路径，缺少平台副作用失败、文件保存失败和 rollback 失败测试。
- 目标：在无需显示服务的环境验证 Desktop 组合边界，并在目标平台尽早发现打包问题。
- 修改范围：`.github/workflows/ci.yml`、`.github/workflows/package.yml`、Desktop capability/composition 测试。
- 验收标准：
  - Windows PR 构建继续通过；macOS 有可手动或 PR 触发的非发布验证路径。
  - Linux 仅验证 Docker Server，不得把 Linux Desktop 构建或测试列为支持目标。
  - 新增平台副作用失败、设置文件保存失败、回滚失败三类测试，并明确预期错误响应和状态。
- 依赖提示：设置文件保存失败后的 Store 内存回滚属于原 `main` 历史缺陷；该测试若要求内存恢复，需依赖相应历史缺陷任务。

#### M8：执行双向构建顺序和目标平台验收

- 类型：迁移完成前的阻塞验证。
- 优先级：P0（发布前）。
- 依赖：M3 至 M7。
- 现状：当前环境没有 Docker，也不是 Windows/macOS runner；真实镜像、目标平台产物和双向构建写集尚未验证。
- 目标：用真实工具链证明两种构建互不读取、覆盖或删除对方的依赖环境、缓存和产物。
- 验收标准：
  - Docker build → Desktop build 通过，Docker 产物 hash 不变。
  - Desktop build → Docker build 通过，Desktop 产物 hash 不变。
  - 可行时并行构建通过，双方写集没有重叠。
  - Windows EXE/ZIP/安装器与 macOS APP/DMG 在各自 runner 构建成功并完成最小运行 smoke。
  - Docker 真实构建、非 root 运行、healthcheck、API 和持久化 smoke 全部通过。

#### M9：提交迁移新增文件并做最终交付检查

- 类型：迁移交付阻塞项。
- 优先级：P0（合并前）。
- 依赖：M1 至 M8。
- 现状：角色化 `requirements/`、新 package、packaging、Web 和隔离测试等关键迁移文件仍为 untracked；只存在于当前工作树的结果无法由其他环境复现。
- 目标：确认迁移新增、移动和删除的文件集合完整，避免漏提交或混入构建产物。
- 验收标准：
  - `git status` 中所有迁移相关文件均有明确归属；构建缓存、虚拟环境和临时产物保持 ignored/untracked 且不提交。
  - requirements 解析/依赖边界检查、全量测试、隔离测试、语法检查和 `git diff --check` 通过。
  - 文档、README、CI、release workflow 与实际目录和命令一致。
  - 完成定义第 15 节逐项复核并记录未能在本机完成的目标环境证据。

建议处理顺序：`M1 → M2 → M3/M4/M5 → M6/M7 → M8 → M9`。M3、M4、M5 在资源允许时可并行，但在安排实施前仍应先确认历史事务缺陷是否另行立项，避免把其修复范围隐式混入 M2 或 M7。

### 18.7 原 `main` 已存在的问题（只记录，暂不处理）

本节记录复检期间确认在原 `main`（对照提交 `52813a3`）中已经存在的问题。它们不归因于本次 Docker/Desktop 隔离迁移，当前状态统一为 `暂缓处理`，本轮不得实施修复。

后续执行 M1 至 M9 时必须遵守以下边界：

- 不得以“顺便修复”为由重构配置和设置事务。
- 如果迁移任务的测试直接触发历史问题，应保留失败证据并建立依赖，不得降低迁移验收标准或静默吞掉错误。
- 只有用户明确安排历史问题后，才可以把下列条目转为实施任务。

#### H1：`SettingsStore.update()` 保存失败后内存状态不回滚

- 状态：暂缓处理。
- 来源：原 `main` 已存在。
- 严重度：高。
- 现状：`update()` 先把候选设置赋给 `self._settings`，随后调用 `save()`；如果创建目录、写临时文件或替换文件失败，异常会向上抛出，但内存仍保留未落盘的新值。
- 已确认现象：模拟 `save()` 抛出异常后，调用方收到失败，`to_dict()` 却仍返回更新后的值，造成内存与磁盘不一致。
- 潜在影响：后续 API 响应和运行态可能使用未持久化设置；进程重启后又恢复为旧值。
- 未来修复方向（仅备注）：先生成候选值并完成原子写入，写入成功后再替换内存；或在失败时可靠恢复内存快照。
- 未来验收点：分别模拟目录创建、临时文件写入和 `replace()` 失败，内存与磁盘均保持更新前状态。

#### H2：普通设置更新中的平台副作用与文件保存不是同一事务

- 状态：暂缓处理。
- 来源：原 `main` 已存在。
- 严重度：高。
- 现状：原 `main` 的 `/api/settings` 在处理 `auto_start` 时先修改操作系统自启动状态，再调用 `SettingsStore.update()` 保存设置；任一步骤失败时没有完整的双向回滚协议。
- 潜在影响：注册表/LaunchAgent 等平台状态可能已经改变，但设置文件保存失败；反向顺序也不能单独解决平台操作失败后的文件一致性。
- 与迁移的关系：迁移新增的 Desktop capability snapshot/restore 试图覆盖该场景，但完整事务仍受 H1 约束；该事实不改变其“原 `main` 历史问题”的归属。
- 未来修复方向（仅备注）：为平台副作用和 SettingsStore 定义明确的 prepare/apply/restore 边界，并保留原始异常及 rollback 失败信息。
- 未来验收点：覆盖平台 apply 失败、设置保存失败、平台 restore 失败以及保存失败后重启四条路径。

#### H3：备份导入先提交配置，后续设置失败时不会恢复配置

- 状态：暂缓处理。
- 来源：原 `main` 已存在。
- 严重度：阻塞级数据一致性问题。
- 现状：`import_backup_payload()` 会先替换 groups、models、aggregate models、members 并立即保存配置；返回后 HTTP 层才应用平台设置和保存用户设置。因此后半段失败时，导入调用虽然失败，配置内存和配置文件却已经变成备份内容。
- 已确认现象：使用会在设置更新时报错的 Store 导入备份，在当前迁移分支的错误封装下接口返回 `400 settings_update_failed`，但 groups 和落盘配置已从旧值变成新值；原 `main` 已具有相同的“配置先提交”顺序。
- 潜在影响：用户看到“导入失败”后仍发生部分数据覆盖，重试或重启也不能自动恢复。
- 未来修复方向（仅备注）：把备份解析/校验与提交分离；在提交前同时取得配置、设置和平台状态快照，任一提交失败时按明确顺序恢复并报告 rollback 结果。
- 未来验收点：配置保存、平台 apply、设置保存及各恢复步骤分别注入失败，接口失败后所有可恢复状态均与导入前一致。

#### H4：SettingsStore 缺少持久化字段白名单

- 状态：暂缓处理。
- 来源：原 `main` 已存在的设计缺口；本次迁移使其演变成 M1/M2 的隔离问题。
- 严重度：中。
- 现状：`load()` 会把设置 JSON 中的任意键合并进内存，`save()` 和备份导出随后可能继续传播这些未知字段；原 `main` 没有按运行方式注入 schema 的概念。
- 潜在影响：拼写错误、废弃字段或外部写入字段会长期残留，API/备份的实际字段集合无法完全由默认设置和允许列表决定。
- 与迁移的边界：M1/M2 只修复 Server/Desktop schema 隔离和备份闭环所需部分，不代表自动完成所有未知字段迁移、告警和兼容策略。
- 未来修复方向（仅备注）：建立版本化设置 schema、未知字段处理策略和显式迁移步骤；需要先决定未知字段是丢弃、隔离保存还是发出诊断。
- 未来验收点：覆盖未知字段、废弃字段迁移、损坏 JSON、未来版本字段和降级运行场景。

历史问题未来建议顺序：`H1 → H2 → H3 → H4`，但该顺序仅供后续立项参考，不表示已经授权实施。

### 18.8 迁移任务处理进度（2026-07-18）

本轮按“先处理迁移问题，历史问题暂缓”的范围执行，未修改 H1–H4。
本节保留迁移早期的处理快照；其中涉及 CI/workflow 的描述不代表本轮已执行或验证 GitHub Actions，当前以 18.9、18.10 和 18.11 的最新状态为准。

#### 已处理

- M1：`SettingsStore` 支持 composition 注入的 `extra_defaults`，Server 只接受 Server schema，Desktop composition 注入 Desktop schema；读取旧设置和保存后均不会让 Server 继续传播 Desktop/未知字段。
- M2：Server 备份使用过滤后的 Store 视图；增加 Server 备份导出、自导入和 Desktop 字段 `400 unsupported_capability` 契约测试。Desktop 仍通过 Desktop schema保留 Desktop 设置。
- M3：README 和 Docker CI 改用 named volume，避免 UID `10001` 对宿主机 bind mount 目录的权限不确定性；CI 增加同一 volume 重启后的设置持久化检查。
- M4：Docker healthcheck 改为读取 `LINROUTER_PORT`，不再固定请求 `18400`。
- M5：README 的直接 PyInstaller 命令显式使用 `build/desktop/direct` 和 `dist/desktop/direct`，不再写入根级默认输出目录。
- M6：Docker CI 增加公共设置写入、Desktop 设置拒绝、Server 状态字段和备份相关的 smoke 覆盖；CI 统一使用明确的 Python/pip 依赖入口，避免入口脚本路径导致源码导入失败（真实 runner 仍暂缓）。
- M7（部分）：按当前范围移除 Linux Desktop `verify_desktop` job；新增 PR/手动触发的 macOS preview build job。Windows/macOS 是 Desktop 支持目标，Linux 只运行 Docker Server。平台副作用失败、文件保存失败和 rollback 失败矩阵仍待补齐。

本地验证结果：

- Server 环境全量测试：`251 passed`。
- 隔离/备份专项测试：`16 passed`。
- requirements 依赖边界、Python/JavaScript/Shell 语法检查通过。
- `git diff --check` 通过。

#### 仍需 GitHub/目标环境验证

- Dockerfile 的真实构建、非 root `/data` 写入、动态 healthcheck、named volume 重启和完整 API smoke；本机没有 Docker，不将其标记为本地通过。
- Linux Desktop 不在当前支持范围；不得把 Ubuntu runner 上的 Desktop 测试结果作为支持声明。
- Windows EXE/ZIP/安装器以及 macOS APP/DMG 的真实构建和最小运行 smoke。
- Desktop 平台副作用失败、文件保存失败和 rollback 失败的完整测试矩阵。
- Docker → Desktop、Desktop → Docker 以及可行时并行构建的 hash/写集隔离。

因此 M7 仍为部分完成，M8、M9 继续待处理；当前不能宣称第 15 节完成定义已经全部满足。

### 18.9 当前本地处理任务（GitHub Actions 暂缓）

用户已明确：所有依赖 GitHub Actions 修改、执行或 runner 结果的验证暂时不处理。本节只安排本地可以完成和确认的迁移修复；不得借此处理 H1–H4 历史问题。

本节保留为本地任务初始拆分记录；其最新状态以 18.10 和 18.11 为准。

#### L1：修复 Dockerfile healthcheck 指令语法

- 类型：已确认的 Dockerfile 阻塞缺陷。
- 优先级：P0。
- 现状：`HEALTHCHECK` 使用 `CMD-SHELL`。Dockerfile 的 healthcheck 指令应使用 `CMD command` 或 `CMD ["executable", ...]`；当前形式不能作为有效的 Dockerfile healthcheck 契约。
- 修改范围：`packaging/docker/Dockerfile`、`tests/test_build_isolation_contract.py`。
- 实施要求：
  - 保留从 `LINROUTER_PORT` 读取端口的行为。
  - 优先使用 exec form，由 Python 直接读取环境变量，避免依赖 shell 展开和复杂引号。
  - 隔离测试不得再断言 `CMD-SHELL` 存在，应断言合法的 `HEALTHCHECK ... CMD` 形式及动态端口读取逻辑。
- 本地验收：Dockerfile 静态契约、Shell/Python 语法、隔离专项测试通过。
- 暂缓验收：真实 `docker build`、容器 `healthy` 状态和非默认端口运行，等待 GitHub Actions/具备 Docker 的环境恢复后执行。

#### L2：从 Docker 复制集移除 Desktop 专属运行时代码

- 类型：已确认的隔离边界缺陷。
- 优先级：P0。
- 现状：Dockerfile 虽未复制 `linrouter_desktop`、Desktop 依赖和资源，但会完整复制 `linrouter_server`、`linrouter_core`；其中仍存在 Desktop 专属字段、方法、路由和资源注入逻辑，包括：
  - `_DESKTOP_SETTING_KEYS`、`auto_start`、`start_minimized` 和 `_desktop_capabilities()`。
  - `/desktop/` 静态资源分支与 `desktop_resource_root`。
  - `desktop/js/settings-startup.js` 注入。
  - ServerPlatform 上的 autostart、clipboard、single-instance 负能力方法。
  - legacy `get_platform()` / `_platform()` Desktop fallback。
- 目标：Docker 最终复制的 Server/Core 源码只包含公共 Server 行为和通用可选能力协议，不包含 Desktop 名称、Desktop 设置字段或 Desktop 平台方法；Desktop 适配和 Desktop 字段所有权全部留在 `linrouter_desktop`。
- 修改范围：`linrouter_core/runtime/http_api_runtime.py`、`linrouter_core/runtime/app_runtime.py`、`linrouter_server/application.py`、`linrouter_server/paths.py`、`linrouter_desktop/` composition/capability 适配及相关测试。
- 实施要求：
  - 建立真正通用的 OptionalCapabilities/optional resources 边界，协议名称和方法中不得出现 Windows、macOS、Desktop、托盘、注册表等具体概念。
  - Server 公共 settings schema 是 `/api/settings` 的唯一基础字段来源。
  - Server 收到非公共设置字段时返回稳定的 `400 unsupported_capability`；不得为了识别 Desktop 字段而在 Server/Core 中保留 Desktop 字段表。
  - Desktop composition 注入扩展 schema、能力实现、设置读取/提交和 Desktop 资源；Server 不进行平台发现。
  - 删除 legacy sentinel 对 `handler._platform().set_autostart()` 的调用路径；兼容测试改为使用显式注入，不保留生产代码反向兼容分支。
  - Desktop 仍可读取、更新和备份 `auto_start`、`start_minimized`，Server 的状态、设置和备份均不包含这些字段。
- 本地验收：
  - 对 Dockerfile 实际复制的 `linrouter_server`、`linrouter_core`、`web/shared` 做源码扫描，不出现 Desktop 专属标识和平台方法。
  - Server/Core AST 依赖扫描继续无 `linrouter_desktop`、旧 `linrouter_platform` 或 Desktop packaging 导入。
  - Server 设置、备份自导入、Desktop composition 和 Desktop 资源注入专项测试通过。

#### L3：加强本地隔离契约，避免测试把缺陷固化

- 类型：测试覆盖缺口。
- 优先级：P1。
- 依赖：L1、L2。
- 现状：当前隔离测试只禁止 Server/Core 直接 import Desktop package，无法发现复制源码内仍包含 Desktop 专属逻辑；同时错误地要求 Dockerfile 出现 `CMD-SHELL`。
- 修改范围：`tests/test_build_isolation_contract.py`，必要时拆出独立的 source/image manifest contract 测试。
- 验收标准：
  - 检查 Dockerfile-specific ignore 文件确实排除 Desktop package、Desktop Web、Desktop packaging、平台资源和本地虚拟环境。
  - 检查 Dockerfile 只显式 `COPY` Server/Core/公共 Web/entrypoint。
  - 对 Docker 复制集做 Desktop 专属标识扫描，并提供最小、明确的允许列表；不得用宽泛排除掩盖新泄漏。
  - 检查 Desktop spec 的 datas/hidden imports 不含 `packaging/docker`、Dockerfile、entrypoint 或 Docker 专属资源。
  - 检查 Server 环境无 Pillow/pystray，Desktop 环境具备 Desktop 依赖。
  - healthcheck 契约检查合法指令形式和 `LINROUTER_PORT`，不依赖字符串误判。

#### L4：执行本地回归和交付前静态复检

- 类型：本地验收任务。
- 优先级：P1。
- 依赖：L1–L3。
- 执行项：
  - `python -m pip check`，以及 requirements 角色清单和依赖边界检查。
  - Server 环境全量 `python -m pytest -q -p no:cacheprovider`。
  - 隔离、设置、备份、Desktop composition 专项测试。
  - Python compileall、JavaScript `node --check`、Shell `bash -n`。
  - Server/Core AST 依赖扫描、公共 Web Desktop 标识扫描、Docker/Desktop manifest 静态扫描。
  - `python -m linrouter_server --help` 源码入口 smoke。
  - 确认不存在根级 `.venv`、根级 `static` symlink、根级 `build/`/`dist/` 非预期输出。
  - `git diff --check` 和迁移文件归属复核。
- 完成条件：本地检查全部通过，且只剩本节明确暂缓的 GitHub/目标环境项目与 H1–H4 历史问题。

#### 暂缓项（本轮不得处理）

- `.github/workflows/ci.yml`、`.github/workflows/package.yml` 的修改、YAML 修复和 actionlint。
- GitHub Actions 上的 Docker build/smoke、Windows/macOS build、产物上传和 release 流程。
- Docker named volume、非 root UID、动态 healthcheck 的真实容器验证。
- Windows EXE/ZIP/安装器与 macOS APP/DMG 的真实构建和运行。
- Docker → Desktop、Desktop → Docker、并行构建的目标 runner 验证。
- H1–H4 原 `main` 历史问题。

本节记录时已知的 GitHub Actions 问题：`ci.yml` 的 Docker smoke 多行 `python -c` 存在 YAML block 缩进错误。该问题后续已在 U5 中改为缩进合法的 heredoc，并完成本地 YAML 解析验证。

建议本地处理顺序：`L1 → L2 → L3 → L4`。完成 L4 后只能声明“本地迁移检查通过”，不能声明整个第 15 节完成；GitHub/目标环境验证恢复后再继续 M6–M9 的剩余验收。

### 18.10 本地任务处理结果（2026-07-18）

#### 已完成

- L1：healthcheck 改为合法的 `HEALTHCHECK ... CMD [...]` exec form，Python 在容器内读取 `LINROUTER_PORT`；隔离测试已删除对 `CMD-SHELL` 的错误断言。
- L2：Server/Core 改为通用 optional capability/resource 注入边界，移除 Docker 复制集中的 Desktop 字段、Desktop 路由、平台负能力、Desktop script 注入和 legacy platform fallback。Desktop 由 composition root 注入扩展 schema、能力、资源前缀和运行时脚本。
- L3：新增 Dockerfile-specific ignore、Desktop spec Docker 文件排除和 Server/Core 源码 Desktop token 扫描；Server 收到不在当前 Store schema 中的设置时统一返回 `400 unsupported_capability`。
- L4：依赖边界、全量测试、专项测试、Python/JavaScript/Shell 语法、Server/Core AST 依赖、源码标识和输出目录复检均已执行。
- U3 纠偏：Desktop 构建脚本现在使用 `LINROUTER_DESKTOP_PYTHON` 或当前环境中的 `python`/`python3`，不再依赖 uv 或强制固定某个虚拟环境路径。

#### 本地验证结果

- Server 环境全量测试：`265 passed`。
- 隔离/备份/Desktop composition/依赖、workflow 及入口隔离专项测试：`24 passed`。
- requirements 依赖边界检查、compileall、JavaScript `node --check`、Shell `bash -n`、`git diff --check` 通过。
- `linrouter_server`、`linrouter_core` 源码未发现 Desktop、Desktop 设置、旧平台 package 或 pystray 标识。
- Docker context ignore 排除 Desktop package、Desktop Web、Desktop packaging、平台资源和本地虚拟环境；Desktop spec 不收集 Docker 文件。
- Server 环境无 Pillow/pystray，Desktop 环境具备对应依赖；根级 `.venv`、`static` symlink 和非预期根级构建输出不存在。

#### 仍然暂缓

- GitHub Actions runner 执行；workflow 依赖入口和 YAML block 已在 U5 中修复并通过本地静态验证，但尚未获得 GitHub runner 结果。
- 真实 Docker build、非 root volume、healthcheck 状态和容器 API smoke。
- Windows/macOS 真实打包与运行、双向构建顺序和并行写集验证。
- H1–H4 原 `main` 历史问题。

当前状态：L1–L4、U1–U9 的本地实现和静态验证已完成；GitHub runner、真实 Docker 和目标平台验收仍暂缓。迁移整体仍不能宣称第 15 节完成，因为目标环境证据和历史问题尚未处理。

### 18.11 uv 适用范围纠偏任务（本轮执行记录，2026-07-18）

#### 用户确认与覆盖关系

用户已明确：`uv` 只是当前开发/验证环境用于控制 Python 版本和本地虚拟环境的工具，不是本项目必须采用的依赖管理标准。

因此，本节结论覆盖本文前面所有把 `uv`、`uv.lock`、`.python-version`、`UV_PROJECT_ENVIRONMENT` 或 `uv sync` 写成项目强制契约的条款。相关旧条款只保留为问题形成过程的历史记录，不得继续作为实现或验收依据。

纠偏后必须遵守以下原则：

- 项目依赖事实源恢复为通用 `requirements.txt`/分层 requirements，能够由标准 `python -m pip` 消费。
- 不提交仅服务当前环境的 `.python-version`、`uv.lock` 或 uv 专用配置。
- 当前环境仍可使用 uv 创建、维护 `.venvs/server` 和 `.venvs/desktop`，但这只是本地选择，不写入项目强制入口。
- Python 3.12 继续作为当前支持和 CI/Docker 目标；该要求原本就存在，不因撤回 uv 标准化而改变。
- Docker、Desktop 的源码、依赖集合、构建缓存和产物仍必须隔离；不得以撤回 uv 为理由恢复 `COPY .`、完整依赖安装或根级共享构建输出。
- 已完成的 Server/Desktop package、Web、settings、capability 和 packaging 目录拆分继续保留。
- GitHub Actions workflow 定义已改为通用 Python/pip 入口，并修复已知 YAML block；真实 runner 执行仍暂缓，不能宣称 Actions 已通过。

U1–U9 的本地实现和静态验证均已完成；其中 U5 仅缺 GitHub runner 真实执行证据。

#### U1：恢复通用依赖事实源并按运行角色拆分（已完成）

- 类型：纠正迁移过度标准化。
- 优先级：P0。
- 修改范围：恢复根级 `requirements.txt`；新增 `requirements/server.txt`、`requirements/desktop.txt`、`requirements/test.txt`、`requirements/package.txt`；移除本次新增的 `pyproject.toml`、`uv.lock`、`.python-version` 项目交付要求。
- 依赖关系建议：
  - 根 `requirements.txt` 转发到 `requirements/desktop.txt`，保持原 `main` 的完整运行依赖安装兼容。
  - `server.txt` 只包含 `certifi`、`httpx[http2]` 等 Server/Core 运行依赖。
  - `desktop.txt` 引用 `server.txt`，再增加 pystray、Pillow、macOS 条件 pyobjc。
  - `test.txt` 引用 `server.txt`，再增加 pytest；Server 测试环境不得因此安装 Desktop 依赖。
  - `package.txt` 引用 `desktop.txt`，再增加 PyInstaller。
- 验收标准：
  - requirements 文件可以被标准 pip 解析，不出现 uv 专用语法。
  - Server 依赖集合无 Pillow、pystray、pyobjc、PyInstaller。
  - Desktop/package 依赖集合包含对应 Desktop 和打包依赖。
  - 当前 `.venvs/server`、`.venvs/desktop` 只作为本地环境保留，不删除、不提交。

#### U2：Docker 依赖安装移除 uv，保留 Server-only 镜像边界（已完成）

- 类型：Docker 构建入口纠偏。
- 优先级：P0。
- 依赖：U1。
- 修改范围：`packaging/docker/Dockerfile`、`packaging/docker/Dockerfile.dockerignore`、Docker manifest 契约测试。
- 实施要求：
  - dependencies stage 使用 Python 3.12 和标准 `python -m venv`/`python -m pip`。
  - Dockerfile 只复制安装 `requirements/server.txt` 所需文件，不复制 Desktop/test/package 依赖清单。
  - 保留多阶段、白名单 COPY、非 root UID、`/data`、entrypoint、动态 healthcheck。
  - 最终镜像不包含 pip 缓存、requirements 构建材料、uv、Desktop package、Desktop 依赖或 Desktop packaging。
- 本地验收：Dockerfile 语法/manifest 静态契约通过；真实 Docker build 和容器 smoke 继续按既定范围暂缓。

#### U3：Desktop 构建脚本改为依赖管理器无关（已完成）

- 类型：Desktop 构建入口纠偏。
- 优先级：P0。
- 修改范围：`packaging/desktop/build.sh`、根级 `scripts/build.sh` 兼容入口及相关契约测试。
- 实施要求：
  - 删除 `UV_PROJECT_ENVIRONMENT`、`.venvs/desktop` 和 `uv run` 强制检查。
  - 支持通过 `LINROUTER_DESKTOP_PYTHON` 显式传入 Python；未指定时使用当前 `python`。
  - 图标、签名、ZIP、安装器、release guard、PyInstaller 全部使用同一个已选择解释器。
  - 构建脚本不负责安装、同步或删除依赖；缺少 PyInstaller/Pillow/pystray 时应给出指向 `requirements/package.txt` 的明确错误。
  - 保留 `build/desktop/<target>`、`dist/desktop/<target>` 写集隔离。
- 验收标准：脚本中无 uv 项目契约；Shell 语法和解释器选择契约通过；不得在本轮执行 Linux Desktop 打包来冒充目标平台验证。

#### U4：源码启动、预览和 README 撤回 uv 强制入口（已完成）

- 类型：用户入口与文档纠偏。
- 优先级：P1。
- 依赖：U1、U3。
- 修改范围：`README.md`、`scripts/server/start-preview-18409.bat`。
- 实施要求：
  - 快速启动、Server、Desktop、预览、直接 PyInstaller、签名构建命令改为标准 Python/pip 或当前已激活环境。
  - README 明确允许任意虚拟环境管理器；如保留 uv 示例，必须标注为可选本地示例且不能成为唯一入口。
  - Windows preview 支持通过 `LINROUTER_SERVER_PYTHON` 指定解释器，未指定时使用 PATH 中的 `python`；不得探测固定虚拟环境目录，也不得主动调用 `uv sync`/`uv run`。
  - 继续使用新的 package、Web、packaging 和产物路径，不恢复旧根级实现或输出目录。
- 验收标准：无 uv 时文档中的主流程仍可执行；uv 用户仍可用自己创建的虚拟环境调用同一 Python/pip 入口。

#### U5：workflow 定义移除 uv 耦合（定义已完成，runner 验证暂缓）

- 类型：GitHub Actions 定义对齐。
- 优先级：P1。
- 依赖：U1、U3。
- 当前状态：workflow 定义和 YAML 修复已完成；GitHub runner 执行仍暂缓。
- 修改范围：`.github/workflows/ci.yml`、`.github/workflows/package.yml`。
- 预期调整：
  - 删除 `astral-sh/setup-uv`、`UV_PROJECT_ENVIRONMENT`、`uv sync`、`uv run`。
  - 恢复 `actions/setup-python` 的 pip cache 和 `python -m pip`。
  - verify job 安装 `requirements/test.txt`；Windows/macOS build 安装 `requirements/package.txt`。
  - 保留当前新目录、Desktop 目标矩阵、Docker job 和产物路径。
- 本轮结果：`ci.yml`、`package.yml` 已删除 `setup-uv`、`UV_PROJECT_ENVIRONMENT`、`uv sync`、`uv run`，改用 `actions/setup-python` 的 pip cache、`python -m pip`、`requirements/test.txt` 和 `requirements/package.txt`；Docker smoke 多行 Python 改为 YAML block 内的 heredoc。Node 20 action 已升级为 Node 24 对应版本：`checkout@v6`、`setup-python@v6`、`upload-artifact@v7`、`download-artifact@v8`、`action-gh-release@v3`。Release workflow 的 `Verify tagged source` job 按当前要求保留完整注释，`build` 暂时只依赖 `resolve`；`resolve` 会先检查 tag 是否包含当前 requirements、packaging 和 package 布局，避免 Windows/macOS 在缓存阶段分别失败。新增独立 `docker-build.yml`，仅执行 Dockerfile 真实 build 和镜像 inspect，不运行容器或 Desktop build；该 workflow 尚待 GitHub runner 执行。三份 workflow 已通过本地 YAML 解析和契约测试。

#### U6：重写依赖和构建隔离契约测试（本轮完成）

- 类型：测试纠偏。
- 优先级：P1。
- 依赖：U1–U3、U5 的最终 workflow 入口。
- 修改范围：`tests/test_build_isolation_contract.py`，必要时新增 manager-neutral requirements contract 测试。
- 验收标准：
  - 禁止把 `UV_PROJECT_ENVIRONMENT`、`.venvs/desktop`、uv lock 写成项目必需条件。
  - 检查 Dockerfile 只使用 Server requirements，且未复制/安装 Desktop/test/package requirements。
  - 检查 Desktop build 使用一个通用的显式/当前 Python，不在脚本内安装或同步依赖。
  - 检查 Server requirements 不含 Desktop/打包依赖，Desktop/package requirements 的继承关系正确。
  - 保留现有 Server/Core 反向依赖、Desktop token、Docker COPY、Desktop spec、healthcheck 和输出目录契约。

#### U7：全面修订本文档中的 uv 错误契约和任务状态（本轮完成）

- 类型：规范纠偏。
- 优先级：P0。
- 依赖：U1–U6 的最终文件名和入口约定；可以先起草，最终在 U6 后收口。
- 修改范围：本文第 1、4、5、6、10、12、13、15、17、18 节以及所有 uv、manifest、完成状态引用。
- 必须调整：
  - 元数据改为“Python 3.12；依赖管理器无关；当前本地环境可使用 uv”。
  - 目标树使用 `requirements/`，删除提交 `.python-version`、`pyproject.toml`、`uv.lock` 的要求。
  - Phase 1 改为角色化 requirements；Phase 7 不再删除根 `requirements.txt`。
  - Docker、测试、完成定义、交付格式全部改为 manager-neutral。
  - B4 标记为由错误前提产生并已撤销，不能继续要求 uv 环境路径。
  - M9、L4、18.10 的 manifest/lock 验收改为 requirements 和通用 Python 验收。
  - 清理“任务统一待处理”与后续“已完成”并存的状态歧义，以最新状态为唯一事实源。
- 验收标准：除明确标注为“可选的当前环境验证记录”外，全文不再把 uv 当作项目标准或完成条件。

#### U8：使用当前本地环境执行 manager-neutral 回归（已完成）

- 类型：本地验收。
- 优先级：P1。
- 依赖：U1–U7；GitHub runner 验收仍排除在本地完成条件外。
- 执行项：
  - 使用现有 `.venvs/server/bin/python` 运行全量测试、compileall、Server CLI smoke 和 `pip check`。
  - 使用现有 `.venvs/desktop/bin/python` 检查 Desktop/package 依赖可导入，不执行 Linux Desktop 目标产物打包。
  - JavaScript `node --check`、Shell `bash -n`、Server/Core AST/标识扫描、Docker/Desktop manifest 扫描。
  - 确认根级 `.venv`、`static`、`build/`、`dist/` 无非预期输出。
  - `git diff --check` 和除明确暂缓的 GitHub Actions 定义外，项目入口、Docker、Desktop、README、requirements 与本文档的 uv 强制引用扫描。
- 本轮结果：全量测试 `265 passed`；隔离、依赖、workflow 与入口契约专项测试 `24 passed`；三份 workflow YAML 解析、compileall、JavaScript `node --check`、Shell `bash -n`、Server/Core 依赖和标识扫描、Docker/Desktop manifest 扫描、Server CLI smoke、`git diff --check` 均通过。当前 uv 环境未提供 `pip` 模块，使用当前环境的 `uv pip check` 验证 Server/Desktop 依赖均无冲突；这只是本地工具验证记录，不改变项目依赖管理器无关原则。
- 完成条件：本地回归全部通过，剩余事项只有 GitHub runner、真实 Docker、Windows/macOS 和 H1–H4 明确暂缓项。

#### U9：交付复核与 commit message 重写（已完成，未提交）

- 类型：最终交付任务。
- 优先级：P0（提交前）。
- 依赖：U1–U8；交付说明必须显式列出尚未取得 GitHub runner 证据。
- 验收标准：
  - `git status` 中新的 requirements、package、Web、packaging、测试和文档归属完整，无 `.python-version`、`uv.lock`、本地 venv 或构建产物待提交。
  - commit message 描述“按 Server/Desktop 拆分依赖和构建边界”，不得再写“使用 uv 替换 requirements”或把 uv 列为项目标准。
  - 未经用户明确要求不得执行 `git add`、`git commit` 或推送。

本轮建议 commit message（仅生成，不提交）：`refactor: isolate server and desktop dependencies and builds`。

#### 建议分配与执行顺序

```text
U1
├── U2
├── U3 ──> U4
└── U5（定义完成，runner 验证暂缓）

U1 + U2 + U3 ──> U6
U1–U6 ─────────> U7
U1–U4 + U6 + U7 ──> U8 ──> U9
```

为避免多个 AI 同时修改同一文件，建议按不重叠文件集合分配：

- 依赖/Docker 执行者：U1、U2。
- Desktop/本地入口执行者：U3、U4。
- 测试/规范执行者：U6、U7；应在 U1–U4 文件名和接口稳定后开始收口。
- 主审查者：U8、U9，并负责记录 U5 尚缺 GitHub runner 证据。

### 18.12 构建边界验收收口（2026-07-18）

本节是当前最新状态，覆盖 18.3、18.8、18.10 和 18.11 中已经过时的“尚未执行 GitHub runner/Docker build”描述。

#### 已取得的目标构建证据

- 用户已确认 tag `v0.6.4` 对应的 Windows/macOS GitHub Actions 构建通过；这证明当前 Desktop requirements、PyInstaller spec、目标平台资源以及 EXE/ZIP/安装器、APP/DMG 构建入口可在目标 runner 执行。尚未取得产物最小运行 smoke 证据。
- 用户已确认提交 `3f6b467` 中新增的独立 `docker-build.yml` 执行通过；该 workflow 只执行真实 Dockerfile build 和 image inspect，不启动容器，因此只能证明镜像可构建，不能替代镜像内容与运行时 smoke。
- 上述证据来自本轮用户确认；文档不虚构 workflow run URL、run ID 或未实际执行的检查。

#### 本轮新增的双向写集保护

- 新增 `scripts/ci/verify_build_isolation.py`：对受保护目录进行逐文件 SHA-256 快照，记录目录、文件、符号链接和缺失状态；另一构建结束后内容、文件集合或路径类型发生任何变化都会失败。
- `docker-build.yml` 在构建镜像前为 `build/desktop`、`dist/desktop` 放置既有产物哨兵并建立快照；Docker build/image inspect 之后无条件复核，证明 Docker 构建不能覆盖或删除 Desktop 既有输出。
- Windows/macOS preview 与 release package job 在 Desktop 构建前为 `build/docker`、`dist/docker` 放置哨兵，同时快照 `packaging/docker`；Desktop 构建后无条件复核，证明 Desktop 构建不能覆盖、删除 Docker 输出或修改 Docker 上下文。
- 双向保护分别在真实支持目标上执行，不在 Linux 强行执行 Desktop 打包。由于 GitHub 托管 Windows/macOS 与 Docker runner 不共享同一 Docker daemon，“顺序构建”的验收采用等价的既有产物/上下文不变式，而不是把不受支持的 Linux Desktop 构建冒充目标平台证据。
- 快照工具的正常路径和篡改失败路径已由本地契约测试覆盖；修改后的三个 workflow 仍需各执行一次，才能勾选第 15 节“双向构建方向的写集保护均通过”。并行构建不作为当前合并阻塞项，因为双方工作目录、依赖环境和 runner 均独立。

#### Docker 运行时 smoke 的执行顺序

- 按用户要求，Docker 运行时 smoke 必须在目录、依赖、复制清单和双向写集保护全部确认后执行。
- 因此 `ci.yml` 的 `build_docker_smoke` job 当前使用显式 `if: ${{ false }}` 暂停。独立 `docker-build.yml` 仍只执行 build、inspect 和 Desktop 输出保护，不执行 `docker run`。
- 待修改后的 Windows preview、macOS preview/release 和 Docker build 写集保护通过后，再单独移除该 gate，执行镜像内容、非 root UID、healthcheck、API、非默认端口和 named volume 持久化 smoke。

#### 当前剩余项

1. 提交当前写集保护改动后，在 GitHub Actions 重新执行 Windows、macOS 和独立 Docker build，确认两种方向的保护均通过。
2. 第 1 项通过后才启用 Docker 运行时 smoke；本轮不得提前执行。
3. Windows/macOS 产物最小运行 smoke 仍属于发布前证据，不影响目录、依赖和构建写集边界的代码完成状态。
4. H1–H4 是原 `main` 历史缺陷，继续暂缓且不计入本次隔离迁移代码缺陷。

#### 本轮最终本地复核

- 全量测试：`268 passed`。
- 构建/依赖/边界专项测试：`27 passed`。
- 三份 GitHub Actions workflow 均通过 YAML 解析；Python compileall、JavaScript `node --check`、Shell `bash -n`、Server CLI smoke 和 `git diff --check` 通过。
- Server 环境未安装 Pillow、pystray、PyInstaller；Desktop 环境可发现/导入对应打包依赖，两个环境的依赖一致性检查均通过。
- Server/Core 反向导入和 Desktop 标识扫描通过；不存在已跟踪的虚拟环境、缓存或构建产物，也没有根级 `.venv`、`build`、`dist`、`static`。
- 本轮没有执行 Docker `run`、healthcheck、API、volume 或非 root 运行时 smoke，符合先完成双向构建边界再测试容器运行时的顺序要求。

### 18.13 根目录兼容入口收口任务（当前实施记录）

#### 已确认决策

- 根目录清晰优先于继续保留旧 Python 文件导入兼容。
- Server 正式源码入口统一为 `python -m linrouter_server`；Desktop 正式源码入口统一为 `python -m linrouter_desktop`。
- PyInstaller 使用 `packaging/desktop` 自己拥有的入口，不再通过根级 `desktop.py` 间接启动。
- 允许删除旧的 `python app.py`、`python desktop.py`、`python -m linrouter` 以及 `import app` 等根级模块兼容能力。
- 根级 `requirements.txt` 是标准 pip 兼容安装入口，不属于待删除代码；`README.md`、`.gitignore`、`lin-router-config.example.json` 也继续保留。旧路线文档归档到 `docs/archive/product/`。
- RC1–RC6 未重做 `frontend/` 实验工程；后续目录复检仅更新其失效 README。旧 `PRD/` 已归档到 `docs/archive/prd/`。
- Docker 运行时 smoke 继续遵守 18.12 的 gate，本任务不得提前启用。

#### RC1：建立正式 Desktop 与打包入口

- 状态：已完成本地实现，待目标 runner 重建确认。
- 优先级：P0。
- 目标：在删除根级 `desktop.py` 和通用 `linrouter/` 兼容 package 前，先提供全部受支持调用方的新入口。
- 修改范围：
  - 保持 `linrouter_desktop/__main__.py` 为源码 Desktop composition root。
  - 新增 `packaging/desktop/entrypoint.py`，只负责导入并调用 `linrouter_desktop` 的 `main`。
  - `packaging/desktop/LinRouter.spec` 改为分析上述 Desktop packaging 入口，不再引用 `PROJECT_ROOT / "desktop.py"`。
- 验收标准：
  - `python -m linrouter_desktop --help` 正常。
  - spec 不引用根级 `desktop.py`、`linrouter/__main__.py` 或 Docker 文件。
  - packaging 入口不包含托盘、Server 或平台业务实现，只做显式转发。
  - Windows/macOS 目标 runner 必须重新构建；本地静态测试不能替代 PyInstaller 目标平台验证。

#### RC2：迁移根级 Python 模块的调用方

- 状态：已完成本地实现。
- 优先级：P0。
- 依赖：RC1。
- 目标：生产代码、测试和当前工具不再导入根级兼容模块。
- 导入映射：

  | 旧模块 | 新 owner |
  |---|---|
  | `app` | 公共 Server API 使用 `linrouter_server`；内部契约按实际 owner 使用 `linrouter_server.application` 或 `linrouter_core` |
  | `desktop` | `linrouter_desktop.tray` 或 `linrouter_desktop.__main__` |
  | `debug_capture` | `linrouter_server.debug_capture` |
  | `settings_store` | `linrouter_server.settings_store` |
  | `upstream_client` | `linrouter_server.upstream_client` |

- 实施约束：
  - 测试 monkeypatch 必须指向生产代码实际读取的 owner module，不能为了测试方便重新引入 facade。
  - 冻结测试中的 `git show <历史提交>:app.py` 是历史基线读取，可以保留；读取当前实现时必须改为实际 owner 文件。
  - 不在本任务重写 Router、HTTP handler、上游请求、设置存储或 Desktop 行为。
- 验收标准：除明确的历史 `git show`/归档文字外，生产代码、当前测试、packaging 和 workflow 中不存在根级旧模块导入。

#### RC3：迁移 Windows Server preview 脚本

- 状态：已完成本地实现。
- 优先级：P1。
- 目标：根目录不再放置平台启动脚本，同时保留 Windows 本地 Server preview 能力。
- 修改范围：
  - 将 `start-preview-18409.bat` 移入 `scripts/server/start-preview-18409.bat`。
  - 脚本从自身目录显式解析仓库根目录，再从仓库根使用 `lin-router-config.json`。
  - 保持 `LINROUTER_SERVER_PYTHON` 或 PATH `python` 的 manager-neutral 解释器选择。
  - 更新 README 和入口契约测试中的路径。
- 验收标准：脚本不引用 `.venvs`、uv 或根级 `app.py`，最终命令仍为 `python -m linrouter_server`。

#### RC4：删除根级兼容代码

- 状态：已完成本地实现。
- 优先级：P0。
- 依赖：RC1、RC2、RC3。
- 删除范围：

  ```text
  app.py
  desktop.py
  debug_capture.py
  settings_store.py
  upstream_client.py
  linrouter/__init__.py
  linrouter/__main__.py
  start-preview-18409.bat（由 RC3 的新路径替代）
  ```

- 验收标准：
  - 删除后不存在为旧导入路径重新建立的 symlink、动态 `sys.modules` alias 或根级转发文件。
  - Server、Desktop、Docker 和 packaging 均从 owner package 启动。
  - 根目录不产生新的 Python 入口、Shell/BAT 启动脚本或构建产物。

#### RC5：更新当前文档和根目录边界契约

- 状态：已完成本地实现。
- 优先级：P1。
- 依赖：RC1 至 RC4。
- 修改范围：README、本文档当前规范段落、构建隔离契约测试和依赖契约测试。
- 处理原则：
  - README 删除 `python desktop.py`、根级 BAT 和旧模块说明，只展示正式入口。
  - 本文第 4、5、7、10、12、13、15 节撤销“保留根级 facade/通用 linrouter package”的旧规范，以本节为最新决策。
  - `docs/archive/release-checklists/` 中的历史版本清单可以保留当时路径，但不能作为当前构建命令来源。
  - 新增根目录白名单契约，防止已删除的 facade 或平台脚本重新出现。
- 当前允许的根级普通文件：

  ```text
  .gitignore
  README.md
  requirements.txt
  lin-router-config.example.json
  ```

  Git 元数据和明确的一级 owner 目录不按普通文件白名单处理；本地 ignored 缓存也不得提交。

#### RC6：本地与目标平台验收

- 状态：本地验收已完成，Windows/macOS 目标 runner 待重建。
- 优先级：P0（提交前）。
- 依赖：RC1 至 RC5。
- 本地验收：
  - 全量测试、入口/打包/依赖/边界专项测试全部通过。
  - `python -m linrouter_server --help` 和 `python -m linrouter_desktop --help` 通过。
  - Python compileall、JavaScript `node --check`、Shell `bash -n`、workflow YAML 解析和 `git diff --check` 通过。
  - `rg`/AST 扫描确认生产代码和当前测试没有旧根级模块导入。
  - Git 跟踪文件中不存在根级 Python 文件、根级 BAT/Shell 启动脚本、虚拟环境、缓存或构建产物。
- 目标平台验收：
  - Windows preview/release 构建使用新的 packaging 入口通过。
  - macOS preview/release 构建使用新的 packaging 入口通过。
  - Docker build 定义和复制清单保持不变，且双向写集保护继续通过。
- 本任务完成不自动解除 Docker runtime smoke gate；仍需先取得 18.12 要求的目标 runner 写集证据。

#### RC1–RC6 当前结果

- 根目录普通文件已收敛为 `.gitignore`、`README.md`、`requirements.txt` 和 `lin-router-config.example.json`；旧 Python facade、`linrouter/` package、根级路线文档和 preview BAT 已删除、归档或移动。
- `packaging/desktop/entrypoint.py` 可直接执行，`python -m linrouter_desktop`、`python -m linrouter_server` 和 PyInstaller entrypoint 的 `--help` 均通过。
- 全量测试：`275 passed`；最新入口/依赖/仓库布局专项测试：`34 passed`。
- Python compileall、JavaScript `node --check`、Shell `bash -n`、Server/Desktop 依赖检查和 `git diff --check` 通过。
- 仍待 Windows/macOS 使用新 PyInstaller 入口重新构建，以及修改后的 Docker/Desktop 写集 workflow 在目标 runner 上通过；Docker runtime smoke 继续保持暂停。

#### 依赖顺序与交付边界

```text
RC1 ──> RC2
  │       │
  └───────┼──> RC4 ──> RC5 ──> RC6
          │
RC3 ──────┘
```

- 建议实施顺序：`RC1 → RC2/RC3 → RC4 → RC5 → RC6`。
- RC1–RC5 应作为同一兼容入口清理变更交付，避免出现文档已切换但旧入口仍存在，或旧入口已删除但 spec/测试尚未迁移的中间状态。
- 未经用户明确要求不得提交、推送、创建 tag 或启用 Docker 运行时 smoke。

### 18.14 仓库布局与入口完整性复检（2026-07-19）

#### 已确认并修复的缺陷

1. Windows/macOS 开发模式开机自启仍引用已删除的根级 `desktop.py`。现统一使用当前解释器执行 `-m linrouter_desktop --tray`；新增两个平台命令回归测试，冻结产物继续使用自身可执行文件。
2. release tag 的 `required_paths` 未包含新建的 `packaging/desktop/entrypoint.py`。现已加入 tag 前置校验，并由 workflow 契约测试固定；旧 tag 会在进入 Windows/macOS matrix 前给出缺文件错误。
3. 根目录边界测试直接扫描物理文件，会把 `.gitignore` 已排除的本地配置、日志等运行文件误判为交付污染。现改为检查“已跟踪 + 未忽略的未跟踪文件”，同时过滤工作树中已经删除的 tracked 路径，并验证 `lin-router-config.json` 确实受 ignore 规则覆盖。
4. `frontend/README.md` 仍使用已删除的 `python app.py` 和根级 `static/`。现改为 `python -m linrouter_server` 与正式资源目录 `web/shared/`，并增加组件文档入口/资源契约。

#### docs 与 scripts 归属收口

- `docs/` 顶层只保留当前规范、`docs/README.md` 索引和 `archive/`。
- v0.6 后端冻结记录归档到 `docs/archive/backend-v0.6/`，旧 PRD、产品路线和发布清单分别归入 `docs/archive/prd/`、`docs/archive/product/`、`docs/archive/release-checklists/`。
- 根级 `ROADMAP.md` 和 `PRD/` 已移入归档；旧路线文档中的失效任务包链接改为明确归档说明。
- `scripts/` 顶层只保留 `README.md`；CI 工具归属 `scripts/ci/`，Server 诊断/预览工具归属 `scripts/server/`。
- 已删除 `scripts/build.sh`、`generate_icon.py`、`release_guard.py`、`sign_windows_artifact.py` 四个 Desktop 兼容转发；当前调用方统一使用 `packaging/desktop/` owner 路径。
- 新增仓库布局和本地 Markdown 链接契约，防止历史文档、兼容脚本或失效链接重新散回顶层。

#### 当前验证结果

- 全量测试 `275 passed`；入口、依赖、平台自启动、仓库布局专项测试 `34 passed`。
- 三份 workflow YAML 解析、Python compileall、JavaScript `node --check`、Shell `bash -n`、Server/Desktop/PyInstaller entrypoint `--help`、依赖一致性和 `git diff --check` 均通过。
- 当前生产代码和测试没有根级旧模块导入，当前文档没有失效的本地 Markdown 链接。

#### 仍不完整或需要目标环境确认的流程

1. Windows/macOS 尚未使用新的 `packaging/desktop/entrypoint.py` 完成目标 runner 重建和产物最小运行 smoke。
2. Windows 注册表与 macOS LaunchAgent 的真实开机自启写入尚未在目标平台执行；本地只验证了命令/参数构造。
3. 移动后的 `scripts/server/start-preview-18409.bat` 尚未在 Windows 实机执行。
4. 修改后的 Windows、macOS、Docker 写集 workflow 尚未取得新的 GitHub Actions run 结果；此前用户已说明 workflow 没有触发。
5. Docker runtime smoke 仍按既定 gate 暂停；在上述写集和目标入口验证通过前不得解除 `if: ${{ false }}`。

上述五项是目标环境证据缺口，不是当前已复现的本地代码失败。历史归档文档中的旧命令只描述对应旧版本，不能作为当前执行入口。
