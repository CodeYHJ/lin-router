import { request } from './http'

// v0.6 冻结的管理 API 适配层：页面不得直接调用 fetch。
export const linRouterApi = {
  getState: () => request('/api/state'),
  getSettings: () => request('/api/settings'),
  createGroup: (payload) => request('/api/groups', { method: 'POST', body: JSON.stringify(payload) }),
  saveGroup: (id, payload) => request(`/api/groups/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteGroup: (id) => request(`/api/groups/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  createModel: (payload) => request('/api/models', { method: 'POST', body: JSON.stringify(payload) }),
  saveModel: (id, payload) => request(`/api/models/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteModel: (id) => request(`/api/models/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  fetchUpstreamModels: (groupId, apiKey) => request('/api/models/fetch-upstream', {
    method: 'POST',
    body: JSON.stringify({ group_id: groupId, api_key: apiKey }),
  }),
}
