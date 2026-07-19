# Lin Router v0.5.6 Release Checklist

## Build Gate

- [ ] `python -m pytest tests -q` passes.
- [ ] `python -m py_compile app.py` passes.
- [ ] `node --check` passes for changed frontend files.
- [ ] `git diff --check` passes.
- [ ] Build with `bash scripts/build.sh --target win32 --installer`.
- [ ] Run `python scripts/release_guard.py dist/LinRouter-v0.5.6-win-x64.zip dist/LinRouter-Setup-v0.5.6-win-x64.exe`.
- [ ] Silently install the setup package and confirm `LinRouter.exe` and `uninstall.cmd` exist.

## First-use Flow

- [ ] With an empty config, Dashboard shows "还没有连接组" and both add/import actions.
- [ ] CodeOK only appears on the empty Dashboard and opens as a third-party link in a new window.
- [ ] New connection group defaults to relay; Base URL and API Key validation identify the exact missing field.
- [ ] A saved group presents model fetch and manual add without automatically calling the upstream service.
- [ ] A model can be quick-tested with "请回复：连接成功" without editing JSON.
- [ ] Only a real successful test/request presents the client Base URL, route key, and verified model.
- [ ] Route key is clearly described as a Lin Router client key, never as an upstream API Key.
- [ ] Relay, Ark, proxy, WAF, aggregate routing, aliases, and stream lifecycle regression tests pass.
