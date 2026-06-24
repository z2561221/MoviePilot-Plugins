function unwrap(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) return data.data
  return data
}
async function getPluginApi(api, path) {
  if (api?.get) return unwrap(await api.get(`plugin/DoubanCenterNew2/${path}`))
  const r = await fetch(`/api/v1/plugin/DoubanCenterNew2/${path}`);
  return unwrap(await r.json())
}
async function postPluginApi(api, path, body = {}) {
  if (api?.post) return unwrap(await api.post(`plugin/DoubanCenterNew2/${path}`, body))
  const r = await fetch(`/api/v1/plugin/DoubanCenterNew2/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return unwrap(await r.json())
}

export { getPluginApi as g, postPluginApi as p };
