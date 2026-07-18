/* Desktop-only settings extension. This file is never copied into Docker. */
(() => {
  const originalRender = SettingsPanel.render;
  const startup = s => `
          <section class="settings-section">
            <h3>启动</h3>
            <label class="settings-row">
              <span>开机自启</span>
              <input id="setting-auto-start" type="checkbox" ${s.auto_start ? 'checked' : ''}>
            </label>
            <label class="settings-row">
              <span>启动后最小化到托盘/状态栏</span>
              <input id="setting-start-minimized" type="checkbox" ${s.start_minimized ? 'checked' : ''}>
            </label>
            <div class="settings-hint">开机自启会写入系统启动项（Windows：注册表；macOS：LaunchAgent）；被系统安全软件拦截属于正常情况。</div>
          </section>`;

  SettingsPanel.render = function() {
    const html = originalRender.call(this);
    return html.replace('<h3>外观</h3>', `${startup(Store.state.settings || {})}\n          <h3>外观</h3>`);
  };

  const originalAttachEvents = SettingsPanel.attachEvents;
  SettingsPanel.attachEvents = function(panel) {
    originalAttachEvents.call(this, panel);
    panel.querySelector('#setting-auto-start')?.addEventListener('change', event => this.updateCheckboxSetting(event, 'auto_start'));
    panel.querySelector('#setting-start-minimized')?.addEventListener('change', event => this.updateCheckboxSetting(event, 'start_minimized'));
  };

  const originalRefresh = SettingsPanel.refreshOpenPanelControls;
  SettingsPanel.refreshOpenPanelControls = function() {
    originalRefresh.call(this);
    const panel = document.getElementById('settings-panel');
    if (!panel) return;
    const settings = Store.state.settings || {};
    const autoStart = panel.querySelector('#setting-auto-start');
    const startMinimized = panel.querySelector('#setting-start-minimized');
    if (autoStart) autoStart.checked = !!settings.auto_start;
    if (startMinimized) startMinimized.checked = !!settings.start_minimized;
  };
})();
