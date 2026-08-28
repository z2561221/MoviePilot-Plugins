export function unwrapResponse(response) {
  return response
}

export function toPosterThumbnail(url) {
  const value = String(url || '').trim()
  if (!value) return ''

  const thumbnail = value.replace(/\/(?:original|w500)\//, '/w200/')
  if (/^https?:\/\/[^/]*doubanio\.com\//i.test(thumbnail)) {
    return `api/v1/system/img/0?imgurl=${encodeURIComponent(thumbnail)}&cache=true`
  }
  return thumbnail
}

const SLOW_REQUEST_MS = 1500

function timeoutError(path, timeoutMs) {
  const error = new Error(`请求超时（${Math.ceil(timeoutMs / 1000)} 秒）：${path}`)
  error.code = 'PLUGIN_API_TIMEOUT'
  return error
}

async function getWithTimeout(api, url, path, timeoutMs) {
  if (!timeoutMs) return api.get(url)

  const controller = typeof AbortController === 'function' ? new AbortController() : null
  let timeoutId
  const request = Promise.resolve().then(() => api.get(url, controller ? { signal: controller.signal } : undefined))
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      controller?.abort()
      reject(timeoutError(path, timeoutMs))
    }, timeoutMs)
  })

  try {
    return await Promise.race([request, timeout])
  } finally {
    clearTimeout(timeoutId)
  }
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim()
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '')
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

export async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || 0)
  const startedAt = Date.now()
  try {
    const response = await getWithTimeout(api, pluginPath(pluginId, path), path, timeoutMs)
    return response
  } finally {
    const elapsedMs = Date.now() - startedAt
    if (timeoutMs && elapsedMs >= SLOW_REQUEST_MS) {
      console.warn(`[DoubanCenter] GET ${path} ${elapsedMs}ms`)
    }
  }
}

export async function postPluginApi(api, pluginId, path, payload = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return await api.post(pluginPath(pluginId, path), payload)
}

export async function getPluginConfig(api, pluginId) {
  if (!api?.get) throw new Error('缺少 MoviePilot 配置 API')
  const response = await api.get(pluginPath(pluginId))
  if (response?.success === false) throw new Error(response?.message || '插件配置读取失败')
  return response?.data ?? response
}

export async function savePluginConfig(api, pluginId, payload = {}) {
  if (!api?.put) throw new Error('缺少 MoviePilot 配置 API')
  const response = await api.put(pluginPath(pluginId), payload)
  if (response?.success === false) throw new Error(response?.message || '插件配置保存失败')
  return response?.data ?? response
}
