function unwrapResponse(response) {
  if (!response || typeof response !== 'object' || typeof response.success !== 'boolean') {
    throw new Error('MoviePilot V3 API 响应格式无效')
  }
  if (!response.success) throw new Error(response.message || '请求失败')
  return response.data
}
async function postPluginApi(api, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams();
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value);
  });
  const query = params.toString();
  const url = `plugin/DownloadManagerLocal/${path}${query ? `?${query}` : ''}`;
  const response = await api.post(url, payload, options);
  return unwrapResponse(response)
}
async function postPluginJsonApi(api, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(`plugin/DownloadManagerLocal/${path}`, payload, options);
  return unwrapResponse(response)
}
async function getPluginApi(api, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(`plugin/DownloadManagerLocal/${path}`, options);
  return unwrapResponse(response)
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, postPluginApi as a, getPluginApi as g, postPluginJsonApi as p };
