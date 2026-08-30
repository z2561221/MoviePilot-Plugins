function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort()
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim()
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '')
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

export function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}
export async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams()
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value)
  })
  const query = params.toString()
  const url = `${pluginPath(pluginId, path)}${query ? `?${query}` : ''}`
  const response = await api.post(url, payload, options)
  return unwrapResponse(response)
}
export async function postPluginJsonApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(pluginPath(pluginId, path), payload, options)
  return unwrapResponse(response)
}
export async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(pluginPath(pluginId, path), options)
  return unwrapResponse(response)
}
