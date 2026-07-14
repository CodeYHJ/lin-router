const Tabs = {
  current: 'dashboard',
  tabs: [
    { id: 'dashboard', label: '首页' },
    { id: 'config', label: '配置管理' },
    { id: 'logs', label: '请求日志' },
    { id: 'test', label: '测试请求' },
    { id: 'stats', label: '统计' }
  ],

  init() {
    const bar = document.getElementById('tabbar');
    bar.setAttribute('role', 'tablist');
    bar.setAttribute('aria-label', '工作区域');
    bar.innerHTML = this.tabs.map(t => `
      <button type="button" class="tab-btn ${t.id === this.current ? 'active' : ''}" id="tab-${t.id}" role="tab" data-tab="${t.id}"
        aria-controls="tab-panel-${t.id}" aria-selected="${t.id === this.current}" tabindex="${t.id === this.current ? '0' : '-1'}">
        ${t.label}
      </button>
    `).join('');

    bar.addEventListener('click', e => {
      const btn = e.target.closest('.tab-btn');
      if (!btn) return;
      this.switch(btn.dataset.tab);
    });
    bar.addEventListener('keydown', e => this.onKeydown(e));

    this.renderPanels();
  },

  switch(tabId) {
    if (this.current === tabId) return;
    if (this.current === 'config') ConfigTab.dispose();
    this.current = tabId;
    document.querySelectorAll('.tab-btn').forEach(b => {
      const active = b.dataset.tab === tabId;
      b.classList.toggle('active', active);
      b.setAttribute('aria-selected', String(active));
      b.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.tab === tabId));

    if (tabId === 'logs') LogsTab.refresh();
    if (tabId === 'dashboard') DashboardTab.refresh();
    if (tabId === 'stats') StatsTab.refresh();
    if (tabId === 'test') TestTab.onShow();
    if (tabId === 'config') ConfigTab.onShow();
  },

  renderPanels() {
    const content = document.getElementById('tab-content');
    content.innerHTML = this.tabs.map(t => `
      <div class="tab-panel ${t.id === this.current ? 'active' : ''}" id="tab-panel-${t.id}" role="tabpanel" data-tab="${t.id}" aria-labelledby="tab-${t.id}" tabindex="0">
        <div class="tab-panel-inner" id="panel-${t.id}"></div>
      </div>
    `).join('');
  },

  onKeydown(event) {
    const currentButton = event.target.closest('.tab-btn');
    if (!currentButton) return;
    const buttons = [...document.querySelectorAll('.tab-btn')];
    const currentIndex = buttons.indexOf(currentButton);
    if (currentIndex < 0) return;

    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % buttons.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = buttons.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextButton = buttons[nextIndex];
    nextButton.focus();
    this.switch(nextButton.dataset.tab);
  }
};
