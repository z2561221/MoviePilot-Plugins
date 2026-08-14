/** 校验 MoviePilot V3 插件客户端返回的统一响应。 */
function requireEnvelope(response) {
  if (
    !response
    || typeof response !== 'object'
    || typeof response.success !== 'boolean'
    || typeof response.message !== 'string'
    || !Object.prototype.hasOwnProperty.call(response, 'data')
  ) {
    throw new Error('MoviePilot 插件 API 响应格式无效')
  }
  return response
}

/** 读取普通查询接口的业务数据。 */
export async function apiGet(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = requireEnvelope(await api.get(path, { feedback: 'silent' }))
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}

/** 读取操作接口并保留业务成功状态与消息。 */
export async function apiPost(api, path, body = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = requireEnvelope(await api.post(path, body, { feedback: 'silent' }))
  const data = response.data && typeof response.data === 'object' && !Array.isArray(response.data)
    ? response.data
    : {}
  return {
    ...data,
    success: response.success,
    message: response.message || data.message || data.summary || '',
  }
}
