export function readEnvelopeData(response, fallback = '备份中心请求失败') {
  if (!response || typeof response !== 'object' || !('success' in response)) {
    throw new Error(fallback)
  }
  if (!response.success) {
    throw new Error(response.message || fallback)
  }
  return response.data
}

export function normalizeApiError(error, fallback = '备份中心请求失败') {
  const payload = error?.payload || error?.response?.data
  return new Error(payload?.message || error?.message || fallback)
}

export async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.get(`plugin/BackupCenter/${path}`, {
      feedback: 'silent',
    })
    return readEnvelopeData(response)
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function getPluginConfig(api) {
  if (!api?.get) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    const response = await api.get('plugin/BackupCenter/config', {
      feedback: 'silent',
    })
    return readEnvelopeData(response, '备份中心配置读取失败')
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置读取失败')
  }
}

export async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.post(`plugin/BackupCenter/${path}`, payload, {
      feedback: 'silent',
    })
    return readEnvelopeData(response)
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function savePluginConfig(api, payload = {}) {
  if (!api?.put) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    const response = await api.put('plugin/BackupCenter', payload, {
      feedback: 'silent',
    })
    return readEnvelopeData(response, '备份中心配置保存失败')
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置保存失败')
  }
}

export async function downloadBackup(api, backupId, downloadName = '') {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.get(`plugin/BackupCenter/backups/${backupId}/export`, {
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
    throw normalizeApiError(error, '离线恢复包下载失败')
  }
}
