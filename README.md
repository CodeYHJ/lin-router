# lin-router

本地 OpenAI 兼容路由器，用于给 Hermes、Codex++ 等客户端提供一个稳定入口。

## 启动

桌面端双击：

```text
dist\LinRouter.exe
```

命令行启动：

```bash
python app.py
```

默认地址：

```text
http://127.0.0.1:18400
```

客户端 Base URL：

```text
http://127.0.0.1:18400/v1
```

客户端 API Key 使用页面里对应连接组生成的 `lr-...` key。服务端会严格按 key 判断要调用哪个连接组。

## 三种上游模式

火山方舟：

- 连接组填写：组名、Base URL、Ark API Key
- 模型填写：模型名称、EP ID

中转站：

- 连接组填写：组名、Base URL
- 模型通道填写：模型名称、上游模型名、该价格组对应的 API Key、价格组名称

通用 OpenAI 代理：

- 连接组填写：组名、Base URL、上游 API Key
- 模型可以配置本地名称到上游模型名的映射
- 客户端指定未配置的具体模型时，会按原模型名透传给上游

`lin-router-auto` 是统一的自动调度模型名。实际调度范围由客户端传入的连接组 key 决定。

Hermes / Codex++ 接入统一填写：

```text
Base URL: http://127.0.0.1:18400/v1
API Key: 页面里对应连接组的 lr-... key
Model: lin-router-auto
```

上游请求会使用 Lin Router 生成的干净请求头，不会透传 `x-stainless-*` 等容易触发部分中转站拦截的 SDK 头。

## 调试预览

如果要查看源码前端效果，可以用调试端口启动同一份正式配置：

```bash
python app.py --port 18409 --config lin-router-config.json
```

这样不会占用正式的 `18400`，但会读取和写入同一份 `lin-router-config.json`。也可以直接双击 `start-preview-18409.bat`。

## 打包

```bash
python -m PyInstaller --noconfirm LinRouter.spec
```

产物：

```text
dist\LinRouter.exe
```

前端页面放在 `static/index.html`，打包配置会把 `static` 一起带进 exe。

## Git 安全

真实配置文件 `lin-router-config.json` 已被 `.gitignore` 忽略，不要提交真实 API Key。仓库中只保留 `lin-router-config.example.json` 模板。
