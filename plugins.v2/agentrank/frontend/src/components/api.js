/**
 * 将后端稳定响应解包为 data，并保留机器错误码。
 */
export function unwrapResponse(response) {
  const payload = response?.data ?? response
  if (payload && typeof payload === 'object' && payload.success === false) {
    const error = new Error(payload.error?.message || 'Agent榜单请求失败')
    error.code = payload.error?.code || 'request_failed'
    throw error
  }
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data
  return payload
}

/**
 * 统一提取 Axios/FastAPI/普通异常中的可读错误。
 */
export function normalizeApiError(error, fallback = 'Agent榜单请求失败') {
  const detail = error?.response?.data?.detail
  const contract = detail?.error || error?.response?.data?.error
  const normalized = new Error(contract?.message || error?.message || fallback)
  normalized.code = contract?.code || error?.code || 'request_failed'
  return normalized
}

/**
 * 调用 AgentRank GET 接口，并通过 injected client 自动携带 bearer。
 */
export async function getPluginApi(api, path, params = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.get('plugin/AgentRank/' + path, { params }))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

/**
 * 调用 AgentRank POST 接口，并通过 injected client 自动携带 bearer。
 */
export async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.post('plugin/AgentRank/' + path, payload))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

/**
 * 通过 MoviePilot 核心配置接口保存并重新加载 AgentRank。
 */
export async function savePluginConfig(api, payload = {}) {
  if (!api?.put) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    const response = await api.put('plugin/AgentRank', payload)
    const data = response?.data ?? response
    if (data?.success === false) throw new Error(data?.message || '插件配置保存失败')
    return data
  } catch (error) {
    throw normalizeApiError(error, '插件配置保存失败')
  }
}
