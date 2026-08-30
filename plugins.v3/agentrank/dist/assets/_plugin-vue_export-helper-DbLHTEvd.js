/**
 * 将后端稳定响应解包为 data，并保留机器错误码。
 */
function isResponseEnvelope(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false
  const keys = Object.keys(payload);
  return (
    keys.length === 3 &&
    keys.every(key => ['success', 'message', 'data'].includes(key)) &&
    ['success', 'message', 'data'].every(key =>
      Object.prototype.hasOwnProperty.call(payload, key),
    )
  )
}

function unwrapResponse(response) {
  const payload = response;
  if (!isResponseEnvelope(payload)) return payload
  if (payload && typeof payload === 'object' && payload.success === false) {
    const error = new Error(payload.message || 'Agent榜单请求失败');
    error.code = 'request_failed';
    throw error
  }
  return payload.data
}

/**
 * 提取 FastAPI 字符串、对象或字段校验数组中的可读错误。
 */
function extractFastApiDetail(detail) {
  const item = Array.isArray(detail)
    ? detail.find(value => value && typeof value === 'object')
    : detail;
  if (typeof item === 'string') return { message: item, code: '' }
  if (!item || typeof item !== 'object') return { message: '', code: '' }
  const message = String(item.message || item.msg || '').trim();
  const location = Array.isArray(item.loc)
    ? item.loc.map(value => String(value)).filter(Boolean).join('.')
    : '';
  return {
    message: location && message ? `${location}: ${message}` : message,
    code: String(item.code || item.type || '').trim(),
  }
}

/**
 * 统一提取 Axios/FastAPI/普通异常中的可读错误。
 */
function normalizeApiError(error, fallback = 'Agent榜单请求失败') {
  const envelope = error?.response?.data;
  const detail = envelope?.data?.detail ?? envelope?.detail;
  const fastApiDetail = extractFastApiDetail(detail);
  const headers = error?.response?.headers || {};
  const machineCode =
    headers['x-agentrank-error-code'] ||
    headers['X-AgentRank-Error-Code'] ||
    '';
  const normalized = new Error(
    envelope?.message || fastApiDetail.message || error?.message || fallback,
  );
  normalized.code = machineCode || fastApiDetail.code || error?.code || 'request_failed';
  return normalized
}

function pluginApiPath(pluginId, path = '') {
  const instanceId = String(pluginId || '').trim();
  if (!instanceId) throw new Error('MoviePilot 插件实例 ID 未就绪')
  const endpoint = String(path || '').replace(/^\/+/, '');
  const basePath = `plugin/${encodeURIComponent(instanceId)}`;
  return endpoint ? `${basePath}/${endpoint}` : basePath
}

/**
 * 调用当前插件实例的 GET 接口，并通过 injected client 自动携带 bearer。
 */
async function getPluginApi(api, pluginId, path, params = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.get(pluginApiPath(pluginId, path), { params }))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

/**
 * 调用当前插件实例的 POST 接口，并通过 injected client 自动携带 bearer。
 */
async function postPluginApi(api, pluginId, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.post(pluginApiPath(pluginId, path), payload))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

/**
 * 通过 MoviePilot 核心配置接口保存并重新加载当前插件实例。
 */
async function savePluginConfig(api, pluginId, payload = {}) {
  if (!api?.put) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    return unwrapResponse(await api.put(pluginApiPath(pluginId), payload))
  } catch (error) {
    throw normalizeApiError(error, '插件配置保存失败')
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginApi as g, postPluginApi as p, savePluginConfig as s };
