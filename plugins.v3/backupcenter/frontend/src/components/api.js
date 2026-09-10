const RESPONSE_ENVELOPE_KEYS = ['data', 'message', 'success']

function resolvePluginId(pluginId, fallback = 'BackupCenter') {
  const value = String(pluginId || '').trim()
  return value || fallback
}

export function pluginApiPath(pluginId, path) {
  const suffix = String(path || '')
  return `plugin/${encodeURIComponent(resolvePluginId(pluginId))}${suffix ? `/${suffix}` : ''}`
}

export function isResponseEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort()
  return keys.length === RESPONSE_ENVELOPE_KEYS.length
    && keys.every((key, index) => key === RESPONSE_ENVELOPE_KEYS[index])
}

export function readEnvelopeData(response, fallback = '备份中心请求失败') {
  if (!isResponseEnvelope(response)) return response
  if (!response.success) {
    throw new Error(response.message || fallback)
  }
  return response.data
}

export function normalizeApiError(error, fallback = '备份中心请求失败') {
  const payload = error?.payload || error?.response?.data
  return new Error(payload?.message || error?.message || fallback)
}

export async function getPluginApi(api, pluginId, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.get(pluginApiPath(pluginId, path), {
      feedback: 'silent',
    })
    return readEnvelopeData(response)
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function getPluginConfig(api, pluginId) {
  if (!api?.get) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    const response = await api.get(pluginApiPath(pluginId, 'config'), {
      feedback: 'silent',
    })
    return readEnvelopeData(response, '备份中心配置读取失败')
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置读取失败')
  }
}

export async function postPluginApi(api, pluginId, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.post(pluginApiPath(pluginId, path), payload, {
      feedback: 'silent',
    })
    return readEnvelopeData(response)
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function savePluginConfig(api, pluginId, payload = {}) {
  if (!api?.put) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    const response = await api.put(pluginApiPath(pluginId, ''), payload, {
      feedback: 'silent',
    })
    return readEnvelopeData(response, '备份中心配置保存失败')
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置保存失败')
  }
}

export async function downloadBackup(api, pluginId, backupId, downloadName = '') {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.get(pluginApiPath(pluginId, `backups/${backupId}/export`), {
      responseType: 'blob',
      feedback: 'silent',
    })
    const blob = response instanceof Blob ? response : new Blob([response])
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    const safeName = String(downloadName || '')
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    anchor.download = `${safeName || `BackupCenter-${backupId}`}.zip`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    throw normalizeApiError(error, '备份包下载失败')
  }
}
