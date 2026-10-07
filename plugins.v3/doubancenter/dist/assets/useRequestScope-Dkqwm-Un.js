import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

function toPosterThumbnail(url) {
  const value = String(url || '').trim();
  if (!value) return ''

  const thumbnail = value.replace(/\/(?:original|w500)\//, '/w200/');
  if (/^https?:\/\/[^/]*doubanio\.com\//i.test(thumbnail)) {
    return `api/v1/system/img/0?imgurl=${encodeURIComponent(thumbnail)}&cache=true`
  }
  return thumbnail
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

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim();
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '');
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || 0);
  const startedAt = Date.now();
  try {
    const response = await getWithTimeout(api, pluginPath(pluginId, path), path, timeoutMs);
    return response
  } finally {
    const elapsedMs = Date.now() - startedAt;
    if (timeoutMs && elapsedMs >= SLOW_REQUEST_MS) {
      console.warn(`[DoubanCenter] GET ${path} ${elapsedMs}ms`);
    }
  }
}

async function postPluginApi(api, pluginId, path, payload = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return await api.post(pluginPath(pluginId, path), payload)
}

async function getPluginConfig(api, pluginId) {
  if (!api?.get) throw new Error('缺少 MoviePilot 配置 API')
  const response = await api.get(pluginPath(pluginId));
  if (response?.success === false) throw new Error(response?.message || '插件配置读取失败')
  return response?.data ?? response
}

async function savePluginConfig(api, pluginId, payload = {}) {
  if (!api?.put) throw new Error('缺少 MoviePilot 配置 API')
  const response = await api.put(pluginPath(pluginId), payload);
  if (response?.success === false) throw new Error(response?.message || '插件配置保存失败')
  return response?.data ?? response
}

async function openNativeSubscription(nativeSubscribe, media) {
  const result = await nativeSubscribe(media);
  if (result?.success !== true) {
    throw new Error(result?.message || '未能打开 MP 原生订阅窗口')
  }
  return result
}

const {getCurrentInstance,nextTick,onActivated,onBeforeUnmount,onDeactivated,onScopeDispose,watch} = await importShared('vue');


// 请求归属覆盖实例切换、路由离开、KeepAlive 失活和卸载。
function useRequestScope(owner, onInvalidate = () => {}) {
  let active = true;
  let available = true;
  let disposed = false;
  let navigation = 0;
  let epoch = 0;
  const timers = new Map();
  function invalidate() {
    epoch += 1;
    for (const [timer, finish] of timers) {
      clearTimeout(timer);
      finish(false);
    }
    timers.clear();
    onInvalidate();
  }
  function pause() { active = false; invalidate(); }
  function resume() { if (available && !disposed) active = true; }
  function deactivate() { available = false; pause(); }
  function capture() {
    const generation = epoch;
    const id = owner();
    return () => active && generation === epoch && id === owner()
  }
  function wait(ms) {
    if (!active) return Promise.resolve(false)
    return new Promise(resolve => {
      const timer = setTimeout(() => { timers.delete(timer); resolve(true); }, ms);
      timers.set(timer, resolve);
    })
  }
  function later(callback, ms) {
    const current = capture();
    void wait(ms).then(finished => { if (finished && current()) callback(); });
  }
  watch(owner, invalidate, { flush: 'sync' });
  const instance = getCurrentInstance();
  const cleanups = [];
  if (instance) {
    onBeforeUnmount(deactivate);
    onDeactivated(deactivate);
    onActivated(() => { available = true; resume(); });
    // 使用宿主已有 router 的公开守卫，避免引入第二份 vue-router。
    const router = instance.proxy?.$router;
    if (router?.beforeEach) cleanups.push(router.beforeEach((to, from) => {
      if (to.path !== from.path) { navigation += 1; pause(); }
    }));
    if (router?.afterEach) cleanups.push(router.afterEach(async () => {
      const currentNavigation = navigation;
      // 导航结束后等待卸载/失活钩子；仍显示的复用组件和取消导航才能恢复。
      await nextTick();
      if (currentNavigation === navigation) resume();
    }));
  }
  onScopeDispose(() => {
    disposed = true;
    deactivate();
    for (const cleanup of cleanups) cleanup?.();
  });
  return { capture, invalidate, pause, resume, wait, later, isActive: () => active }
}

export { _export_sfc as _, getPluginApi as a, getPluginConfig as g, openNativeSubscription as o, postPluginApi as p, savePluginConfig as s, toPosterThumbnail as t, useRequestScope as u };
