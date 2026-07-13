# Lin Router v0.6.0 发布检查清单

## 构建门禁

- [ ] `python -m pytest tests -q` 通过。
- [ ] `python -m py_compile app.py` 通过。
- [ ] 修改过的前端文件均通过 `node --check`。
- [ ] `git diff --check` 通过。
- [ ] 执行 `bash scripts/build.sh --target win32 --installer` 构建发布包。
- [ ] 执行 `python scripts/release_guard.py dist/LinRouter-v0.6.0-win-x64.zip dist/LinRouter-Setup-v0.6.0-win-x64.exe`。
- [ ] 静默安装后确认存在 `LinRouter.exe` 与 `uninstall.cmd`。

## 首次使用流程

- [ ] 空配置时，Dashboard 显示“还没有连接组”，并提供添加和导入入口。
- [ ] 新建连接组默认选择中转站；Base URL 与 API Key 校验能指出具体缺失字段。
- [ ] 已保存的连接组提供获取模型和手动添加模型，不会自动请求上游。
- [ ] 只有真实测试或请求成功后，才展示客户端 Base URL、路由 Key 和已验证模型。
- [ ] 路由 Key 被明确说明为 Lin Router 客户端 Key，而不是上游 API Key。

## P0 并发流与终态收口

- [ ] WAF Header 兼容不会启用串行保护；同一中转站候选的两个流可并发执行，不出现 `waf_lock_timeout` 或候选忙 fallback。
- [ ] 连接组高级配置默认“允许并发”；只有显式选择“串行保护”时，才会出现 `serial_protection_timeout`，且不写入 cooldown。
- [ ] Dashboard 同时展示两个独立的流式请求，并在各自收口后独立移除。
- [ ] `response.completed`、`response.failed`、`response.incomplete`、`[DONE]` 和 EOF 均记录可验证的流生命周期，包括 `stream_finalized=true`、`lifecycle` 与 `completion_signal`。
- [ ] 收到协议终态后在上游 TCP 连接关闭前完成收口；终态遗漏或异常不能阻塞另一个并发请求。
