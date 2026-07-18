const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    this.container?.setAttribute('aria-live', 'polite');
    this.container?.setAttribute('aria-atomic', 'false');
  },

  show(message, type = 'info', duration = 3000) {
    if (!this.container) this.init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const typeLabel = { success: '成功', warning: '提示', error: '失败', info: '信息' }[type] || '信息';
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = `<span class="toast-type">${typeLabel}</span><span class="toast-message"></span>`;
    el.querySelector('.toast-message').textContent = message;
    this.container.appendChild(el);

    if (duration > 0) {
      setTimeout(() => {
        el.classList.add('fade-out');
        setTimeout(() => el.remove(), 200);
      }, duration);
    }
  },

  success(msg) { this.show(msg, 'success'); },
  warning(msg) { this.show(msg, 'warning'); },
  error(msg) { this.show(msg, 'error'); },
  info(msg) { this.show(msg, 'info'); }
};
