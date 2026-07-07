const Modal = {
  /**
   * 显示二次确认弹窗
   * @param {Object} options
   * @param {string} options.title 弹窗标题
   * @param {string} options.message 弹窗内容（支持 HTML）
   * @param {string} [options.cancelText='取消']
   * @param {string} [options.confirmText='确定']
   * @param {string} [options.confirmClass='btn-primary']
   * @returns {Promise<boolean>} 点击确定返回 true，取消/关闭返回 false
   */
  confirm({ title = '确认', message = '', cancelText = '取消', confirmText = '确定', confirmClass = 'btn-primary', allowHtml = false, disableConfirm = false, wide = false }) {
    return new Promise(resolve => {
      let overlay = document.getElementById('modal-overlay');
      if (overlay) overlay.remove();
      overlay = document.createElement('div');
      overlay.id = 'modal-overlay';
      overlay.className = 'modal-overlay hidden';
      document.body.appendChild(overlay);

      const bodyHtml = allowHtml ? message : Utils.escapeHtml(message);
      const dialogClass = wide ? 'modal-dialog modal-wide' : 'modal-dialog';
      overlay.innerHTML = `
        <div class="${dialogClass}">
          <div class="modal-header">
            <h3>${Utils.escapeHtml(title)}</h3>
            <button type="button" class="modal-close" data-action="cancel">×</button>
          </div>
          <div class="modal-body">${bodyHtml}</div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" data-action="cancel">${Utils.escapeHtml(cancelText)}</button>
            <button type="button" class="${confirmClass}" data-action="confirm" ${disableConfirm ? 'disabled' : ''}>${Utils.escapeHtml(confirmText)}</button>
          </div>
        </div>
      `;

      const cleanup = (result) => {
        overlay.classList.add('hidden');
        overlay.innerHTML = '';
        resolve(result);
      };

      const onClick = e => {
        const action = e.target.dataset.action;
        if (action === 'confirm') cleanup(true);
        if (action === 'cancel') cleanup(false);
      };

      overlay.addEventListener('click', onClick);
      overlay.addEventListener('click', e => {
        if (e.target === overlay) cleanup(false);
      });
      document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
          document.removeEventListener('keydown', escHandler);
          cleanup(false);
        }
      });

      overlay.classList.remove('hidden');
    });
  },

  /**
   * 显示自定义表单弹窗
   * @param {Object} options
   * @param {string} options.title 弹窗标题
   * @param {string} options.html 表单 HTML（需包含 input/select/textarea 等，且元素需有 id）
   * @param {Function} [options.validate] 校验函数，接收表单值对象，返回错误信息或 null
   * @param {Function} [options.onRender] 弹窗渲染后回调，接收 overlay DOM，可用于绑定动态事件
   * @param {string} [options.cancelText='取消']
   * @param {string} [options.confirmText='确定']
   * @param {string} [options.confirmClass='btn-primary']
   * @param {boolean} [options.wide=false]
   * @returns {Promise<Object|null>} 点击确定返回表单值对象，取消/关闭返回 null
   */
  form({ title = '填写信息', html = '', validate = null, onRender = null, cancelText = '取消', confirmText = '确定', confirmClass = 'btn-primary', wide = false }) {
    return new Promise(resolve => {
      let overlay = document.getElementById('modal-overlay');
      if (overlay) overlay.remove();
      overlay = document.createElement('div');
      overlay.id = 'modal-overlay';
      overlay.className = 'modal-overlay hidden';
      document.body.appendChild(overlay);

      const dialogClass = wide ? 'modal-dialog modal-wide' : 'modal-dialog';
      overlay.innerHTML = `
        <div class="${dialogClass}">
          <div class="modal-header">
            <h3>${Utils.escapeHtml(title)}</h3>
            <button type="button" class="modal-close" data-action="cancel">×</button>
          </div>
          <div class="modal-body modal-form-body">${html}</div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" data-action="cancel">${Utils.escapeHtml(cancelText)}</button>
            <button type="button" class="${confirmClass}" data-action="confirm">${Utils.escapeHtml(confirmText)}</button>
          </div>
        </div>
      `;

      const getValues = () => {
        const values = {};
        overlay.querySelectorAll('input, select, textarea').forEach(el => {
          if (!el.id) return;
          if (el.type === 'checkbox' || el.type === 'radio') values[el.id] = el.checked;
          else values[el.id] = el.value;
        });
        return values;
      };

      const cleanup = (result) => {
        overlay.classList.add('hidden');
        overlay.innerHTML = '';
        resolve(result);
      };

      const onClick = e => {
        const action = e.target.dataset.action;
        if (action === 'cancel') cleanup(null);
        if (action === 'confirm') {
          const values = getValues();
          if (validate) {
            const err = validate(values);
            if (err) {
              Toast.error(err);
              return;
            }
          }
          cleanup(values);
        }
      };

      overlay.addEventListener('click', onClick);
      overlay.addEventListener('click', e => {
        if (e.target === overlay) cleanup(null);
      });
      document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
          document.removeEventListener('keydown', escHandler);
          cleanup(null);
        }
      });

      overlay.classList.remove('hidden');
      if (typeof onRender === 'function') {
        try { onRender(overlay); } catch (_) {}
      }
    });
  }
};
