/** @typedef {'ark'|'relay'|'proxy'} ProviderType */

const providerLabels = {
  ark: '火山方舟',
  relay: '中转站',
  proxy: '通用 OpenAI 代理',
}

export function toConnectionGroup(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '未命名连接组',
    providerType: raw.provider_type || 'relay',
    providerLabel: providerLabels[raw.provider_type] || raw.provider_type || '中转站',
    baseUrl: raw.base_url || '',
    routeKey: raw.route_key || '',
    modelCount: 0,
    raw,
  }
}

export function toConnectionModel(raw = {}) {
  return {
    id: raw.id || '',
    groupId: raw.group_id || '',
    name: raw.name || '未命名模型',
    upstreamModel: raw.upstream_model || raw.ep_id || '',
    usable: raw.usable !== false,
    raw,
  }
}

export function toGroupPayload(form, existing = {}) {
  const providerType = form.providerType || 'relay'
  const isNewGroup = !existing.id
  // PUT 是完整配置更新：保留本批 UI 尚未迁移的高级字段和已有密钥。
  // 用户重新填写当前 provider 的密钥时，才覆盖该值。
  return {
    ...existing,
    name: form.name.trim(),
    provider_type: providerType,
    base_url: form.baseUrl.trim(),
    ark_api_key: providerType === 'ark'
      ? (form.apiKey.trim() || existing.ark_api_key || '')
      : '',
    api_key: providerType === 'proxy'
      ? (form.apiKey.trim() || existing.api_key || '')
      : '',
    auto_model_name: existing.auto_model_name || '',
    auto_model_cooldown_minutes: existing.auto_model_cooldown_minutes ?? 5,
    stream_idle_timeout: existing.stream_idle_timeout ?? 120,
    reasoning_support: existing.reasoning_support || 'unknown',
    waf_compatible: existing.waf_compatible === true,
    waf_client_mode: existing.waf_client_mode || 'always',
    waf_accept_policy: existing.waf_accept_policy || 'default',
    ...(isNewGroup ? {} : { id: existing.id, route_key: existing.route_key }),
  }
}
