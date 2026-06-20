function unwrap(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) return data.data
  return data
}
function unwrapAction(response) {
  return response?.data ?? response
}
async function getPluginApi(api, path) {
  if (api?.get) return unwrap(await api.get(`plugin/DoubanCenter/${path}`))
  const r = await fetch(`/api/v1/plugin/DoubanCenter/${path}`);
  return unwrap(await r.json())
}
async function postPluginApi(api, path, body = {}) {
  if (api?.post) return unwrapAction(await api.post(`plugin/DoubanCenter/${path}`, body))
  const r = await fetch(`/api/v1/plugin/DoubanCenter/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return unwrapAction(await r.json())
}

export { getPluginApi as g, postPluginApi as p };
