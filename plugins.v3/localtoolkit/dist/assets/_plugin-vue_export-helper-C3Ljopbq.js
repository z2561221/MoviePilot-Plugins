const STANDARD_RESPONSE_KEYS = new Set(['data', 'message', 'success']);

/** 判断响应是否为严格三字段的 MoviePilot 标准 envelope。 */
function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response);
  return keys.length === STANDARD_RESPONSE_KEYS.size
    && keys.every(key => STANDARD_RESPONSE_KEYS.has(key))
    && typeof response.success === 'boolean'
    && typeof response.message === 'string'
    && Object.prototype.hasOwnProperty.call(response, 'data')
}

/** 读取响应的业务数据，非标准 payload 原样透传。 */
function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}

/** 读取普通查询接口的业务数据。 */
async function apiGet(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrapResponse(await api.get(path, { feedback: 'silent' }))
}

/** 读取操作接口并保留业务成功状态与消息。 */
async function apiPost(api, path, body = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(path, body, { feedback: 'silent' });
  if (!isStandardEnvelope(response)) return response
  const data = response.data && typeof response.data === 'object' && !Array.isArray(response.data)
    ? response.data
    : {};
  return {
    ...data,
    success: response.success,
    message: response.message || data.message || data.summary || '',
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, apiGet as a, apiPost as b };
