function unwrap(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) {
    return data.data
  }
  return data
}

export async function apiGet(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrap(await api.get(path))
}

export async function apiPost(api, path, body = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  return unwrap(await api.post(path, body))
}
