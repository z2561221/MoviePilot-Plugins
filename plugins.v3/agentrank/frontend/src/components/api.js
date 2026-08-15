/**
 * 将后端稳定响应解包为 data，并保留机器错误码。
 */
export function unwrapResponse(response) {
  const payload = response
  if (payload && typeof payload === 'object' && payload.success === false) {
    const error = new Error(payload.message || 'Agent榜单请求失败')
    error.code = 'request_failed'
    throw error
  }
  if (!payload || typeof payload !== 'object' || payload.success !== true) {
    throw new Error('MoviePilot API 返回了无效响应结构')
  }
  return payload.data
}

/**
 * 提取 FastAPI 字符串、对象或字段校验数组中的可读错误。
 */
export function extractFastApiDetail(detail) {
  const item = Array.isArray(detail)
    ? detail.find(value => value && typeof value === 'object')
    : detail
  if (typeof item === 'string') return { message: item, code: '' }
  if (!item || typeof item !== 'object') return { message: '', code: '' }
  const message = String(item.message || item.msg || '').trim()
  const location = Array.isArray(item.loc)
    ? item.loc.map(value => String(value)).filter(Boolean).join('.')
    : ''
  return {
    message: location && message ? `${location}: ${message}` : message,
    code: String(item.code || item.type || '').trim(),
  }
}

/**
 * 统一提取 Axios/FastAPI/普通异常中的可读错误。
 */
export function normalizeApiError(error, fallback = 'Agent榜单请求失败') {
  const envelope = error?.response?.data
  const detail = envelope?.data?.detail ?? envelope?.detail
  const fastApiDetail = extractFastApiDetail(detail)
  const headers = error?.response?.headers || {}
  const machineCode =
    headers['x-agentrank-error-code'] ||
    headers['X-AgentRank-Error-Code'] ||
    ''
  const normalized = new Error(
    envelope?.message || fastApiDetail.message || error?.message || fallback,
  )
  normalized.code = machineCode || fastApiDetail.code || error?.code || 'request_failed'
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
    return unwrapResponse(await api.put('plugin/AgentRank', payload))
  } catch (error) {
    throw normalizeApiError(error, '插件配置保存失败')
  }
}
