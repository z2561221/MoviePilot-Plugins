export function unwrapResponse(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

export async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  return unwrapResponse(await api.get(`plugin/DoubanCenter/${path}`))
}

export async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return unwrapResponse(await api.post(`plugin/DoubanCenter/${path}`, payload))
}
