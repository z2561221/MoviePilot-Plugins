/**
 * 将后端稳定响应解包为 data，并保留机器错误码。
 */
function unwrapResponse(response) {
  const payload = response?.data ?? response;
  if (payload && typeof payload === 'object' && payload.success === false) {
    const error = new Error(payload.error?.message || 'Agent榜单请求失败');
    error.code = payload.error?.code || 'request_failed';
    throw error
  }
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data
  return payload
}

/**
 * 统一提取 Axios/FastAPI/普通异常中的可读错误。
 */
function normalizeApiError(error, fallback = 'Agent榜单请求失败') {
  const detail = error?.response?.data?.detail;
  const contract = detail?.error || error?.response?.data?.error;
  const normalized = new Error(contract?.message || error?.message || fallback);
  normalized.code = contract?.code || error?.code || 'request_failed';
  return normalized
}

/**
 * 调用 AgentRank GET 接口，并通过 injected client 自动携带 bearer。
 */
async function getPluginApi(api, path, params = {}) {
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
async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.post('plugin/AgentRank/' + path, payload))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginApi as g, postPluginApi as p };
