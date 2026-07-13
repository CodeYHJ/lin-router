export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const headers = new Headers(options.headers || {})
  if (!isFormData && options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, { ...options, headers })
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const message = typeof payload === 'object'
      ? payload?.message || payload?.error?.message || payload?.error || `请求失败（${response.status}）`
      : payload || `请求失败（${response.status}）`
    throw new ApiError(String(message), response.status, payload)
  }

  return payload
}
