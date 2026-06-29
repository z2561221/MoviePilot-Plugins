function unwrapResponse(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

async function getPluginApi(api, path) {
  if (!api?.get) {
    throw new Error('DoubanCenter requires injected api prop')
  }
  return unwrapResponse(await api.get(`plugin/DoubanCenter/${path}`))
}

async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) {
    throw new Error('DoubanCenter requires injected api prop')
  }
  return unwrapResponse(await api.post(`plugin/DoubanCenter/${path}`, payload))
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginApi as g, postPluginApi as p };
