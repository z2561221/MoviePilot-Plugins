export function unwrapResponse(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

export async function getPluginApi(api, path) {
  if (api?.get) {
    return unwrapResponse(await api.get(`plugin/DoubanCenter/${path}`))
  }
  const response = await fetch(`/api/v1/plugin/DoubanCenter/${path}`)
  return unwrapResponse(await response.json())
}

export async function postPluginApi(api, path, payload = {}) {
  if (api?.post) {
    return unwrapResponse(await api.post(`plugin/DoubanCenter/${path}`, payload))
  }
  const response = await fetch(`/api/v1/plugin/DoubanCenter/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrapResponse(await response.json())
}
