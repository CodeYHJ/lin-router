# Lin Router v0.6 前端工程

Vue 3/Vite/Pinia 前端重构隔离工程。它在开发期通过 Vite 代理调用既有 Python 服务，**不修改也不覆盖仓库根目录 `static/`**；旧静态前端仍是 v0.5.6 回滚资产。

## 运行

```bash
# 终端 1：从仓库根目录启动既有服务（可使用隔离配置与端口）
python app.py --port 18400

# 终端 2：启动 Vue 开发服务器
npm --prefix frontend run dev

# 生产构建（产物仅生成到 frontend/dist）
npm --prefix frontend run build
```

## 首批范围

- Hash 路由：`#/dashboard`、`#/connections`
- 主布局、连接组侧栏、首页空状态/概览
- 连接组新建与编辑主路径（`GET /api/state`、`POST/PUT /api/groups/:id`）
- API 调用统一收敛在 `src/api/`，字段转换收敛在 `src/adapters/`

## 冻结边界

- 不修改 Python 后端、`/api/*` 与 `/v1/*` 契约。
- 不在开发期覆盖 `static/`，不修改 PyInstaller 打包资源。
- 模型编辑、模型测试、聚合、日志、设置等暂未迁移；保留给后续页面批次。

## 目录

```text
src/
├── adapters/      # 后端字段 → 页面模型
├── api/           # 既有 REST 契约适配
├── components/    # 可复用 UI
├── layouts/       # 全局应用框架
├── router/        # Hash 路由
├── stores/        # Pinia 状态
└── views/         # 页面
```
