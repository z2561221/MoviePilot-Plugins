function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort()
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
}

export function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}
export async function postPluginApi(api, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams()
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value)
  })
  const query = params.toString()
  const url = `plugin/DownloadManagerLocal/${path}${query ? `?${query}` : ''}`
  const response = await api.post(url, payload, options)
  return unwrapResponse(response)
}
export async function postPluginJsonApi(api, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(`plugin/DownloadManagerLocal/${path}`, payload, options)
  return unwrapResponse(response)
}
export async function getPluginApi(api, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(`plugin/DownloadManagerLocal/${path}`, options)
  return unwrapResponse(response)
}
