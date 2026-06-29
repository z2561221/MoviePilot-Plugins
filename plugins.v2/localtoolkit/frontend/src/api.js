function unwrap(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) {
    return data.data
  }
  return data
}

export async function apiGet(api, path) {
  if (api?.get) return unwrap(await api.get(path))
  const r = await fetch(`/api/v1/${path}`)
  return unwrap(await r.json())
}

export async function apiPost(api, path, body = {}) {
  if (api?.post) return unwrap(await api.post(path, body))
  const r = await fetch(`/api/v1/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  return unwrap(await r.json())
}
