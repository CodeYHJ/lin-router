const TestTab = {
  lastResponse: '',
  history: JSON.parse(localStorage.getItem('lin-router-test-history') || '[]'),

  saveHistory() {
    localStorage.setItem('lin-router-test-history', JSON.stringify(this.history.slice(0, 10)));
  },

  onShow() {
    const panel = document.getElementById('panel-test');
    if (!panel) return;
    this.render();
    this.syncSelection();
  },

  render() {
    const panel = document.getElementById('panel-test');
    const hasGroups = Boolean(Store.state.groups?.length);
    panel.innerHTML = `
      <h2>测试模型</h2>
      ${!hasGroups ? `
        <div class="empty-state test-empty-state">
          <h2>暂时没有可测试的模型</h2>
          <p class="empty-subtitle">先添加连接组和模型，再用最小请求验证是否可用于客户端接入。</p>
          <div class="empty-actions"><button type="button" class="btn-primary" data-test-action="new-group">添加连接组</button></div>
        </div>` : `
        <section class="form-card test-quick-card">
          <h3>快速测试</h3>
          <p class="test-quick-hint">使用当前真实路由发送最小请求，无需编辑路径或 JSON。</p>
          <div class="form-row">
            <label>连接组</label>
            <select id="test-group">${this.renderGroupOptions()}</select>
          </div>
          <div class="form-row">
            <label>模型</label>
            <select id="test-model"></select>
          </div>
          <div class="form-row">
            <label>测试内容</label>
            <input id="test-prompt" value="请回复：连接成功">
          </div>
          <div class="form-actions">
            <button type="button" id="test-quick-send" class="btn-primary">开始测试</button>
          </div>
        </section>
        <section class="form-card response-card">
          <h3>测试结果</h3>
          <div class="response-status" id="test-status">等待测试。</div>
          <div class="test-result-actions" id="test-result-actions"></div>
          <pre class="response-body" id="test-response"></pre>
        </section>
        <details class="form-card test-advanced-card">
          <summary>自定义请求</summary>
          <div class="test-advanced-body">
            <div class="test-layout">
              <div class="test-col">
                <section>
                  <p class="test-quick-hint">需要调试模板、路径、请求体或流式行为时再展开此区域。</p>
            <div class="form-row">
              <label>模板</label>
              <select id="test-template">
                <option value="auto">自动调度</option>
                <option value="chat">普通聊天</option>
                <option value="model">指定模型</option>
                <option value="stream">流式请求</option>
                <option value="non-stream">非流式测试</option>
                <option value="tool-call">工具调用</option>
              </select>
            </div>
            <div class="form-row">
              <label>模型</label>
              <select id="test-model"></select>
            </div>
            <div class="form-row">
              <label>路径</label>
              <input id="test-path" value="/v1/chat/completions">
            </div>
            <div class="form-row" style="align-items:flex-start">
              <label>请求体</label>
              <textarea id="test-body" rows="10">{ "messages": [{"role":"user","content":"hello"}], "temperature": 0.2 }</textarea>
            </div>
            <div class="form-actions">
              <button type="button" id="test-send" class="btn-secondary">发送自定义请求</button>
            </div>
                </section>
              </div>
            </div>
          </div>
        </details>
        <section class="form-card test-history">
          <h3>最近请求（可一键重放）</h3>
          ${this.history.length ? `
            <div class="history-list">
              ${this.history.map((h, i) => `
                <div class="history-item" data-idx="${i}">
                  <span class="history-time">${Utils.escapeHtml(h.time)}</span>
                  <span class="history-model">${Utils.escapeHtml(h.model)}</span>
                  <span class="history-path">${Utils.escapeHtml(h.path)}</span>
                  <button type="button" class="btn-secondary btn-sm" data-action="replay" data-idx="${i}">重放</button>
                </div>
              `).join('')}
            </div>
          ` : '<div class="empty-tip">暂无历史记录</div>'}
        </section>`}
    `;
    if (!hasGroups) {
      panel.querySelector('[data-test-action="new-group"]')?.addEventListener('click', () => App.createGroup());
      return;
    }
    this.attachEvents(panel);
    this.renderModelOptions();
    this.applyTemplate();
  },

  renderGroupOptions() {
    const selected = Store.selected.type === 'group' ? Store.selected.id : (Store.state.groups?.[0]?.id || '');
    return Store.state.groups?.map(g =>
      `<option value="${g.id}" ${g.id === selected ? 'selected' : ''}>${Utils.escapeHtml(g.name)}</option>`
    ).join('') || '';
  },

  syncSelection() {
    const templateSel = document.getElementById('test-template');
    if (Store.selected.type === 'group') {
      const sel = document.getElementById('test-group');
      if (sel) sel.value = Store.selected.id;
    } else if (Store.selected.type === 'model') {
      const model = Store.getModel(Store.selected.id);
      const sel = document.getElementById('test-group');
      if (sel && model) sel.value = model.group_id;
      // 选中具体模型时切换到指定模型模板，方便直接测试
      if (templateSel && model) templateSel.value = 'model';
    }
    this.renderModelOptions();
    this.applyTemplate();
    document.getElementById('test-prompt')?.focus();
  },

  renderModelOptions() {
    const groupId = document.getElementById('test-group')?.value;
    const group = Store.getGroup(groupId);
    const models = group ? Store.getModelsByGroup(group.id) : [];
    const autoName = group?.auto_model_name || Store.state.auto_model_name || 'lin-router-auto';
    const selected = document.getElementById('test-model')?.value;

    const html = [
      ...models.map(m => `<option value="${Utils.escapeHtml(m.name)}" ${m.name === selected ? 'selected' : ''}>${Utils.escapeHtml(this.modelLabel(m))}</option>`),
      `<option value="${Utils.escapeHtml(autoName)}">${Utils.escapeHtml(autoName)} - 自动调度</option>`
    ].join('');

    const select = document.getElementById('test-model');
    if (select) {
      select.innerHTML = html;
      if (Store.selected.type === 'model') {
        const model = Store.getModel(Store.selected.id);
        if (model && [...select.options].some(o => o.value === model.name)) select.value = model.name;
      }
      const quickButton = document.getElementById('test-quick-send');
      if (quickButton) quickButton.disabled = models.length === 0;
    }
  },

  modelLabel(m) {
    const group = Store.getGroup(m.group_id);
    const upstream = m.upstream_model || m.ep_id;
    if (group?.provider_type === 'relay') return `${m.name} - ${upstream || '中转站'}`;
    if (group?.provider_type === 'proxy') return `${m.name} - ${upstream || '通用代理'}`;
    return `${m.name} - ${m.ep_id}`;
  },

  applyTemplate() {
    const template = document.getElementById('test-template')?.value || 'auto';
    const model = document.getElementById('test-model')?.value;
    const bodyEl = document.getElementById('test-body');
    if (!bodyEl) return;
    const base = { messages: [{ role: 'user', content: 'hello' }], temperature: 0.2 };
    if (template === 'auto' || template === 'chat') {
      bodyEl.value = JSON.stringify(base, null, 2);
    } else if (template === 'model') {
      bodyEl.value = JSON.stringify({ ...base, model }, null, 2);
    } else if (template === 'stream') {
      bodyEl.value = JSON.stringify({ ...base, model, stream: true }, null, 2);
    } else if (template === 'non-stream') {
      bodyEl.value = JSON.stringify({ ...base, model, stream: false }, null, 2);
    } else if (template === 'tool-call') {
      bodyEl.value = JSON.stringify({
        ...base,
        model,
        tools: [{
          type: 'function',
          function: { name: 'get_weather', description: '获取指定城市天气', parameters: { type: 'object', properties: { city: { type: 'string' } }, required: ['city'] } }
        }],
        messages: [{ role: 'user', content: '北京今天天气怎么样' }]
      }, null, 2);
    }
  },

  async send() {
    const btn = document.getElementById('test-send');
    const statusEl = document.getElementById('test-status');
    const respEl = document.getElementById('test-response');
    const groupId = document.getElementById('test-group').value;
    const group = Store.getGroup(groupId);
    const path = document.getElementById('test-path').value;
    const bodyText = document.getElementById('test-body').value;
    const selectedModel = document.getElementById('test-model').value;

    btn.disabled = true;
    btn.textContent = '发送中...';
    try {
      const payload = JSON.parse(bodyText);
      const autoName = group?.auto_model_name || Store.state.auto_model_name || 'lin-router-auto';
      if (selectedModel && selectedModel !== autoName) payload.model = selectedModel;

      const startedAt = performance.now();
      const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${group?.route_key || ''}` };
      if (group?.provider_type === 'relay' && group?.waf_compatible) {
        headers['X-LinRouter-Test'] = 'relay-waf';
      }
      const resp = await fetch(path, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const text = await resp.text();
      const elapsed = Math.round(performance.now() - startedAt);
      const isWafBlocked = resp.status === 403 && /your request was blocked|waf blocked|blocked by waf|风控/i.test(text);
      let wafHint = '';
      if (isWafBlocked) {
        if (group?.provider_type === 'relay' && group?.waf_compatible) {
          wafHint = '\n\n【WAF 拦截提示】上游中转站返回 403：Your request was blocked。该连接组已开启 WAF，可能是中转站账号、渠道权限、频率限制或服务商风控导致，请检查中转站后台。';
        } else {
          wafHint = '\n\n【WAF 拦截提示】上游中转站返回 403：Your request was blocked。该连接组未开启 WAF 兼容，建议开启「仅中转站 WAF 兼容」后重试。';
        }
      }
      this.showTestResult(resp.status, text + wafHint, elapsed, group, selectedModel);
      this.lastResponse = text;

      this.recordHistory({ groupId, group, model: selectedModel || autoName, path, body: bodyText, template: document.getElementById('test-template')?.value || 'auto' });

      await Store.load();
    } catch (err) {
      statusEl.textContent = '测试请求未能发出';
      respEl.textContent = Utils.redactSensitive(String(err));
    } finally {
      btn.disabled = false;
      btn.textContent = '发送测试';
    }
  },

  async sendQuick() {
    const button = document.getElementById('test-quick-send');
    const groupId = document.getElementById('test-group')?.value || '';
    const group = Store.getGroup(groupId);
    const model = document.getElementById('test-model')?.value || '';
    const prompt = document.getElementById('test-prompt')?.value.trim() || '请回复：连接成功';
    if (!group || !model) return Toast.warning('请先添加模型后再测试');
    button.disabled = true;
    button.textContent = '测试中...';
    try {
      const startedAt = performance.now();
      const response = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${group.route_key || ''}` },
        body: JSON.stringify({ model, messages: [{ role: 'user', content: prompt }], temperature: 0, stream: false }),
      });
      const text = await response.text();
      const elapsed = Math.round(performance.now() - startedAt);
      this.showTestResult(response.status, text, elapsed, group, model);
      this.recordHistory({ groupId, group, model, path: '/v1/chat/completions', body: JSON.stringify({ model, messages: [{ role: 'user', content: prompt }], temperature: 0, stream: false }, null, 2), template: 'quick' });
      await Store.load();
    } catch (err) {
      const status = document.getElementById('test-status');
      const response = document.getElementById('test-response');
      if (status) status.textContent = '测试失败：无法连接到本地路由服务';
      if (response) response.textContent = Utils.redactSensitive(String(err));
    } finally {
      button.disabled = false;
      button.textContent = '开始测试';
    }
  },

  showTestResult(status, text, elapsed, group, modelName) {
    const statusEl = document.getElementById('test-status');
    const responseEl = document.getElementById('test-response');
    const actions = document.getElementById('test-result-actions');
    const success = Number(status) >= 200 && Number(status) < 300;
    const conclusion = success
      ? '测试成功，可用于客户端接入。'
      : this.testFailureConclusion(status, text);
    if (statusEl) statusEl.textContent = `${conclusion}（HTTP ${status}，${(elapsed / 1000).toFixed(2)} 秒）`;
    if (responseEl) responseEl.textContent = this.formatResponse(Utils.redactSensitive(text));
    if (actions) {
      actions.innerHTML = success ? '<button type="button" class="btn-primary btn-sm" id="test-copy-client">复制客户端配置</button>' : '<button type="button" class="btn-secondary btn-sm" id="test-view-logs">查看请求日志</button>';
      actions.querySelector('#test-copy-client')?.addEventListener('click', () => this.copyClientConfig(group, modelName));
      actions.querySelector('#test-view-logs')?.addEventListener('click', () => Tabs.switch('logs'));
    }
  },

  testFailureConclusion(status, text) {
    if ([401, 403].includes(Number(status))) return '测试失败：请检查 API Key、权限或中转站兼容设置。';
    if (Number(status) === 404) return '测试失败：当前模型名或上游模型映射不可用。';
    if (/timeout|timed out|网络|network/i.test(String(text || ''))) return '测试失败：暂时无法连接上游，请检查 Base URL 后重试。';
    return '测试失败：请求未得到可用响应，可查看日志中的技术详情。';
  },

  copyClientConfig(group, modelName) {
    const text = `Base URL: ${window.location.origin}/v1\nAPI Key: ${group?.route_key || ''}\nModel: ${modelName || ''}`;
    Utils.copy(text).then(ok => ok ? Toast.success('客户端配置已复制') : Toast.error('复制失败'));
  },

  recordHistory({ groupId, group, model, path, body, template }) {
    this.history.unshift({ time: new Date().toLocaleString(), group_id: groupId, group_name: group?.name || '', model, path, body, template });
    this.history = this.history.slice(0, 10);
    this.saveHistory();
    this.renderHistory();
  },

  renderHistory() {
    const container = document.querySelector('.test-history');
    if (!container) return;
    container.innerHTML = `
      <h3>最近请求（可一键重放）</h3>
      ${this.history.length ? `
        <div class="history-list">
          ${this.history.map((h, i) => `
            <div class="history-item" data-idx="${i}">
              <span class="history-time">${Utils.escapeHtml(h.time)}</span>
              <span class="history-model">${Utils.escapeHtml(h.model)}</span>
              <span class="history-path">${Utils.escapeHtml(h.path)}</span>
              <button type="button" class="btn-secondary btn-sm" data-action="replay" data-idx="${i}">重放</button>
            </div>
          `).join('')}
        </div>
      ` : '<div class="empty-tip">暂无历史记录</div>'}
    `;
    container.querySelectorAll('[data-action="replay"]').forEach(btn => {
      btn.addEventListener('click', e => this.replay(Number(e.target.dataset.idx)));
    });
  },

  replay(idx) {
    const h = this.history[idx];
    if (!h) return;
    document.getElementById('test-group').value = h.group_id;
    this.renderModelOptions();
    if (h.model) {
      const modelSel = document.getElementById('test-model');
      if ([...modelSel.options].some(o => o.value === h.model)) modelSel.value = h.model;
    }
    document.getElementById('test-path').value = h.path;
    document.getElementById('test-body').value = h.body;
    document.getElementById('test-template').value = h.template || 'auto';
    Toast.info('已重放历史请求');
  },

  formatResponse(text) {
    try { return JSON.stringify(JSON.parse(text), null, 2); }
    catch { return text; }
  },

  attachEvents(panel) {
    panel.querySelector('#test-group')?.addEventListener('change', () => { this.renderModelOptions(); this.applyTemplate(); });
    panel.querySelector('#test-template')?.addEventListener('change', () => this.applyTemplate());
    panel.querySelector('#test-model')?.addEventListener('change', () => { if (['model', 'stream', 'non-stream'].includes(document.getElementById('test-template').value)) this.applyTemplate(); });
    panel.querySelector('#test-send')?.addEventListener('click', () => this.send());
    panel.querySelector('#test-quick-send')?.addEventListener('click', () => this.sendQuick());
    panel.querySelectorAll('[data-action="replay"]').forEach(btn => {
      btn.addEventListener('click', e => this.replay(Number(e.target.dataset.idx)));
    });
  }
};
