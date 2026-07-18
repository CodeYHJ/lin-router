"""U1 全局框架与导航收口的静态契约。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_public_component_layer_loads_before_page_styles():
    index_html = read("web/shared/index.html")
    base_css = read("web/shared/css/base.css")
    components_css = read("web/shared/css/components.css")

    assert index_html.index('css/base.css') < index_html.index('css/components.css')
    assert index_html.index('css/components.css') < index_html.index('css/layout.css')
    assert "--border-color: var(--border)" in base_css
    assert "--radius-overlay: 10px" in base_css
    assert "--space-1: 4px" in base_css
    assert ".btn-primary" in components_css
    assert ".status-tag" in components_css
    assert ".form-card" in components_css


def test_navigation_exposes_keyboard_and_state_semantics():
    app_js = read("web/shared/js/app.js")
    tabs_js = read("web/shared/js/tabs.js")
    tree_js = read("web/shared/js/tree.js")

    assert "tablist" in tabs_js
    assert 'aria-controls="tab-panel-${t.id}"' in tabs_js
    assert "onKeydown(event)" in tabs_js
    assert "ArrowRight" in tabs_js
    assert "ArrowLeft" in tabs_js
    assert "服务运行中" in app_js
    assert 'aria-label="复制兼容 OpenAI 的接口地址' in app_js
    assert "setAttribute('role', 'tree')" in tree_js
    assert "data-tree-key" in tree_js
    assert "statusLabel(status)" in tree_js
    assert "onTreeKeydown(event, node, root)" in tree_js
    assert "root.scrollTop = scrollTop" in tree_js
    assert "focus({ preventScroll: true })" in tree_js


def test_feedback_layers_have_focus_and_live_region_contracts():
    modal_js = read("web/shared/js/modal.js")
    settings_js = read("web/shared/js/settings-panel.js")
    toast_js = read("web/shared/js/toast.js")

    assert "_activeCleanup" in modal_js
    assert 'role="dialog"' in modal_js
    assert 'aria-modal="true"' in modal_js
    assert "document.removeEventListener('keydown', onKeydown)" in modal_js
    assert "previousFocus.focus({ preventScroll: true })" in modal_js
    assert "bindFocusTrap(panel)" in settings_js
    assert "document.removeEventListener('keydown', this._keyHandler)" in settings_js
    assert "aria-live" in toast_js
    assert "role', type === 'error' ? 'alert' : 'status'" in toast_js


def test_u1_does_not_touch_runtime_dirty_patch_contract():
    runtime_js = read("web/shared/js/config-tab-runtime.js")

    assert "controller.render()" not in runtime_js
    assert "panel.innerHTML" not in runtime_js
    assert "controller.onRuntimeStateUpdate()" in runtime_js
