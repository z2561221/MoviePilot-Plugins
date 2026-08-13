function unwrapResponse(response) {
  const payload = response?.data ?? response;
  if (payload && typeof payload === 'object' && payload.success === false) {
    const error = new Error(payload.error?.message || '备份中心请求失败');
    error.code = payload.error?.code || 'request_failed';
    throw error
  }
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data
  return payload
}

function normalizeApiError(error, fallback = '备份中心请求失败') {
  const detail = error?.response?.data?.detail;
  const contract = detail?.error || error?.response?.data?.error;
  const validation = Array.isArray(detail) ? detail[0] : detail;
  const normalized = new Error(
    contract?.message || validation?.msg || error?.message || fallback,
  );
  normalized.code = contract?.code || validation?.type || error?.code || 'request_failed';
  return normalized
}

async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.get(`plugin/BackupCenter/${path}`))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

async function getPluginConfig(api) {
  if (!api?.get) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    return unwrapResponse(await api.get('plugin/BackupCenter/config'))
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置读取失败')
  }
}

async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    return unwrapResponse(await api.post(`plugin/BackupCenter/${path}`, payload))
  } catch (error) {
    throw normalizeApiError(error)
  }
}

async function savePluginConfig(api, payload = {}) {
  if (!api?.put) throw new Error('MoviePilot 配置 API 未就绪')
  try {
    return unwrapResponse(await api.put('plugin/BackupCenter', payload))
  } catch (error) {
    throw normalizeApiError(error, '备份中心配置保存失败')
  }
}

async function downloadBackup(api, backupId, downloadName = '') {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  try {
    const response = await api.get(`plugin/BackupCenter/backups/${backupId}/export`, {
      responseType: 'blob',
    });
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data ?? response]);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    const safeName = String(downloadName || '')
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    anchor.download = `${safeName || `BackupCenter-${backupId}`}.zip`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    throw normalizeApiError(error, '离线恢复包下载失败')
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginApi as a, downloadBackup as d, getPluginConfig as g, postPluginApi as p, savePluginConfig as s };
