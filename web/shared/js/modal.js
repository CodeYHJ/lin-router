const Modal = {
  _activeCleanup: null,

  /**
   * 统一管理确认与表单弹窗的焦点、Escape 和关闭后焦点回归。
   * 保持 confirm/form 的 Promise 契约，调用方无需改动。
   */
  _open({ title, bodyHtml, bodyClass = '', cancelText, confirmText, confirmClass, wide, cancelValue, onConfirm, onRender, initialSelector }) {
    return new Promise(resolve => {
      this._activeCleanup?.();
      const previousFocus = document.activeElement;
      const overlay = document.createElement('div');
      overlay.id = 'modal-overlay';
      overlay.className = 'modal-overlay hidden';
      document.body.appendChild(overlay);

      const dialogClass = wide ? 'modal-dialog modal-wide' : 'modal-dialog';
      overlay.innerHTML = `
        <div class="${dialogClass}" role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-description" tabindex="-1">
          <div class="modal-header">
            <h3 id="modal-title">${Utils.escapeHtml(title)}</h3>
            <button type="button" class="modal-close" data-action="cancel" aria-label="关闭弹窗">×</button>
          </div>
          <div class="modal-body ${bodyClass}" id="modal-description">${bodyHtml}</div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" data-action="cancel">${Utils.escapeHtml(cancelText)}</button>
            <button type="button" class="${confirmClass}" data-action="confirm">${Utils.escapeHtml(confirmText)}</button>
          </div>
        </div>
      `;

      const dialog = overlay.querySelector('[role="dialog"]');
      let settled = false;
      const cleanup = result => {
        if (settled) return;
        settled = true;
        document.removeEventListener('keydown', onKeydown);
        overlay.remove();
        if (this._activeCleanup === cancelActiveDialog) this._activeCleanup = null;
        if (previousFocus?.isConnected && typeof previousFocus.focus === 'function') {
          previousFocus.focus({ preventScroll: true });
        }
        resolve(result);
      };
      const cancelActiveDialog = () => cleanup(cancelValue);

      const onKeydown = event => {
        if (event.key === 'Escape') {
          event.preventDefault();
          cleanup(cancelValue);
          return;
        }
        if (event.key !== 'Tab') return;
        const focusable = [...dialog.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')];
        if (!focusable.length) {
          event.preventDefault();
          dialog.focus();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      };

      overlay.addEventListener('click', event => {
        if (event.target === overlay) {
          cleanup(cancelValue);
          return;
        }
        const actionButton = event.target.closest('.modal-header [data-action], .modal-footer [data-action]');
        const action = actionButton?.dataset.action;
        if (action === 'cancel') cleanup(cancelValue);
        if (action === 'confirm') {
          const result = onConfirm?.();
          if (!result || result.accepted === false) return;
          cleanup(result.value);
        }
      });
      document.addEventListener('keydown', onKeydown);
      this._activeCleanup = cancelActiveDialog;

      overlay.classList.remove('hidden');
      if (typeof onRender === 'function') {
        try { onRender(overlay); } catch (_) {}
      }
      // 表单优先落到首个可编辑控件；确认框落到可执行的确认按钮。
      setTimeout(() => {
        if (!overlay.isConnected) return;
        const focusTarget = dialog.querySelector(initialSelector) || dialog.querySelector('[data-action="confirm"]:not(:disabled)') || dialog.querySelector('[data-action="cancel"]');
        focusTarget?.focus();
      }, 0);
    });
  },

  /**
   * 显示二次确认弹窗。
   * @returns {Promise<boolean>} 点击确定返回 true，取消/关闭返回 false。
   */
  confirm({ title = '确认', message = '', cancelText = '取消', confirmText = '确定', confirmClass = 'btn-primary', allowHtml = false, disableConfirm = false, wide = false }) {
    const bodyHtml = allowHtml ? message : Utils.escapeHtml(message);
    return this._open({
      title,
      bodyHtml,
      cancelText,
      confirmText,
      confirmClass,
      wide,
      cancelValue: false,
      initialSelector: disableConfirm ? '[data-action="cancel"]' : '[data-action="confirm"]',
      onConfirm: () => ({ accepted: !disableConfirm, value: true }),
      onRender: overlay => {
        const confirmButton = overlay.querySelector('[data-action="confirm"]');
        if (confirmButton) confirmButton.disabled = disableConfirm;
      }
    });
  },

  /**
   * 显示自定义表单弹窗。
   * @returns {Promise<Object|null>} 点击确定返回表单值对象，取消/关闭返回 null。
   */
  form({ title = '填写信息', html = '', validate = null, onRender = null, cancelText = '取消', confirmText = '确定', confirmClass = 'btn-primary', wide = false }) {
    return this._open({
      title,
      bodyHtml: html,
      bodyClass: 'modal-form-body',
      cancelText,
      confirmText,
      confirmClass,
      wide,
      cancelValue: null,
      initialSelector: '.modal-form-body input:not(:disabled), .modal-form-body select:not(:disabled), .modal-form-body textarea:not(:disabled)',
      onConfirm: () => {
        const values = {};
        document.getElementById('modal-overlay')?.querySelectorAll('input, select, textarea').forEach(el => {
          if (!el.id) return;
          values[el.id] = el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value;
        });
        const error = validate?.(values);
        if (error) {
          Toast.error(error);
          return { accepted: false };
        }
        return { accepted: true, value: values };
      },
      onRender
    });
  }
};
