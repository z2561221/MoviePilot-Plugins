function unwrap(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) {
    return data.data
  }
  return data
}

async function apiGet(api, path) {
  if (api?.get) return unwrap(await api.get(path))
  const r = await fetch(`/api/v1/${path}`);
  return unwrap(await r.json())
}

async function apiPost(api, path, body = {}) {
  if (api?.post) return unwrap(await api.post(path, body))
  const r = await fetch(`/api/v1/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return unwrap(await r.json())
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, apiGet as a, apiPost as b };
