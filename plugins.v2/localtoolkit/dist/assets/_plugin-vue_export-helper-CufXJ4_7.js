function unwrap(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) {
    return data.data
  }
  return data
}

async function apiGet(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrap(await api.get(path))
}

async function apiPost(api, path, body = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrap(await api.post(path, body))
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, apiGet as a, apiPost as b };
