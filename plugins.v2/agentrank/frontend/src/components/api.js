/**
 * 解包 MoviePilot API 响应。
 */
export function unwrapResponse(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

/**
 * 调用 AgentRank GET 接口。
 */
export async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrapResponse(await api.get('plugin/AgentRank/' + path))
}

/**
 * 调用 AgentRank POST 接口。
 */
export async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrapResponse(await api.post('plugin/AgentRank/' + path, payload))
}
