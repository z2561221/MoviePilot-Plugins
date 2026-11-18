function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort()
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
    && typeof response.message === 'string'
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim()
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '')
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

export function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) {
    const error = new Error(response.message || '请求失败')
    error.name = 'PluginApiError'
    error.payload = response
    throw error
  }
  return response.data
}
export function isApiRequestCancellation(reason) {
  if (!reason || typeof reason !== 'object') return false
  return Boolean(reason.__CANCEL__) || reason.code === 'ERR_CANCELED'
    || reason.name === 'AbortError' || reason.name === 'CanceledError'
}
export async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams()
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value)
  })
  const query = params.toString()
  const url = `${pluginPath(pluginId, path)}${query ? `?${query}` : ''}`
  const response = await api.post(url, payload, options)
  return unwrapResponse(response)
}
export async function postPluginJsonApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(pluginPath(pluginId, path), payload, options)
  return unwrapResponse(response)
}
export async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(pluginPath(pluginId, path), options)
  return unwrapResponse(response)
}

const permissionSessions = new WeakMap()

function permissionSession(api) {
  let session = permissionSessions.get(api)
  if (!session) {
    session = { entry: null }
    permissionSessions.set(api, session)
    api.interceptors?.response?.use(value => value, error => {
      if ([401, 403].includes(error?.response?.status)) session.entry = null
      return Promise.reject(error)
    })
  }
  return session
}

export async function getManagementPermission(api, { signal, timeoutMs = 8000, refresh = false } = {}) {
  if (!api?.get) throw new Error('MoviePilot 登录接口未就绪')
  const session = permissionSession(api)
  if (refresh) session.entry = null
  const controller = new AbortController()
  let timer
  let rejectWait
  let entry
  let ownsEntry = false
  const interrupted = new Promise((_resolve, reject) => { rejectWait = reject })
  const cancel = () => {
    const error = new Error('权限核验被中断')
    error.name = 'AbortError'
    rejectWait(error)
    controller.abort()
  }
  try {
    if (signal?.aborted) cancel()
    else signal?.addEventListener('abort', cancel, { once: true })
    timer = setTimeout(() => {
      const error = new Error('权限核验超时，请重新检查。')
      error.name = 'PermissionTimeoutError'
      rejectWait(error)
      controller.abort()
    }, timeoutMs)
    const request = signal?.aborted ? interrupted : api.get('user/current', {
      feedback: 'silent', signal: controller.signal, timeout: timeoutMs,
      transformRequest: [function (data, headers) {
        // Axios此阶段已执行宿主认证拦截器；只比较当前会话，不读取持久登录存储。
        const identity = typeof headers?.get === 'function' ? headers.get('Authorization') : headers?.Authorization || headers?.authorization
        if (!identity) { session.entry = null; return data }
        const scope = String(this.baseURL || '') + '\n' + String(identity)
        const cached = session.entry
        if (cached?.scope === scope) {
          entry = cached
          this.adapter = async config => ({ data: await cached.result, status: 200, statusText: 'OK', headers: {}, config })
        } else {
          let resolve, reject
          const result = new Promise((yes, no) => { resolve = yes; reject = no })
          result.catch(() => {})
          entry = { scope, result, resolve, reject }
          session.entry = entry
          ownsEntry = true
        }
        return data
      }],
    })
    const user = unwrapResponse(await Promise.race([request, interrupted]))
    if (typeof user?.is_superuser !== 'boolean' || typeof user?.is_active !== 'boolean') {
      throw new Error('当前用户接口未返回明确权限')
    }
    if (ownsEntry) entry.resolve({ is_active: user.is_active, is_superuser: user.is_superuser })
    return { can_manage: user.is_active && user.is_superuser }
  } catch (error) {
    if (ownsEntry) {
      entry.reject(error)
      if (session.entry === entry) session.entry = null
    }
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}
