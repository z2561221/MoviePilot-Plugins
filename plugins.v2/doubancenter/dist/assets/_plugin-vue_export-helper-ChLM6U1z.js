function unwrapResponse(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

function toPosterThumbnail(url) {
  return String(url || '').replace(/\/(?:original|w500)\//, '/w200/')
}

const SLOW_REQUEST_MS = 1500;

function timeoutError(path, timeoutMs) {
  const error = new Error(`请求超时（${Math.ceil(timeoutMs / 1000)} 秒）：${path}`);
  error.code = 'PLUGIN_API_TIMEOUT';
  return error
}

async function getWithTimeout(api, url, path, timeoutMs) {
  if (!timeoutMs) return api.get(url)

  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  let timeoutId;
  const request = Promise.resolve().then(() => api.get(url, controller ? { signal: controller.signal } : undefined));
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      controller?.abort();
      reject(timeoutError(path, timeoutMs));
    }, timeoutMs);
  });

  try {
    return await Promise.race([request, timeout])
  } finally {
    clearTimeout(timeoutId);
  }
}

async function getPluginApi(api, path, options = {}) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || 0);
  const startedAt = Date.now();
  try {
    const response = await getWithTimeout(api, `plugin/DoubanCenter/${path}`, path, timeoutMs);
    return unwrapResponse(response)
  } finally {
    const elapsedMs = Date.now() - startedAt;
    if (timeoutMs && elapsedMs >= SLOW_REQUEST_MS) {
      console.warn(`[DoubanCenter] GET ${path} ${elapsedMs}ms`);
    }
  }
}

async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return unwrapResponse(await api.post(`plugin/DoubanCenter/${path}`, payload))
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginApi as g, postPluginApi as p, toPosterThumbnail as t };
