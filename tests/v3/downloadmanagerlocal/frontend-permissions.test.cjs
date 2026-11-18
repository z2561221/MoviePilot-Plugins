const { test } = require('node:test')
const assert = require('node:assert/strict')
const { createRequire } = require('node:module')
const { resolve } = require('node:path')
const frontend = resolve(__dirname, '../../../plugins.v3/downloadmanagerlocal/frontend')
const requireFrontend = createRequire(resolve(frontend, 'package.json'))
const { getManagementPermission } = requireFrontend('./src/components/api.js')

test('native current-user request uses the injected callable client and requires both actual account flags', async () => {
  for (const [active, admin, expected] of [[true, true, true], [true, false, false], [false, true, false]]) {
    const requests = []
    const api = () => { throw new Error('Client must use get') }
    api.get = async (path, options) => {
      requests.push({ path, options })
      return { success: true, message: '', data: { name: 'fixture', is_active: active, is_superuser: admin } }
    }
    assert.deepEqual(await getManagementPermission(api), { can_manage: expected })
    assert.equal(requests.length, 1)
    assert.equal(requests[0].path, 'user/current')
    assert.equal(requests[0].options.timeout, 8000)
    assert.equal(requests[0].options.feedback, 'silent')
    assert.equal(requests[0].options.signal.aborted, false)
  }
})

test('a permanently pending client times out and cancels transport instead of waiting forever', async () => {
  let signal
  const api = { get: (_path, options) => { signal = options.signal; return new Promise(() => {}) } }
  await assert.rejects(getManagementPermission(api, { timeoutMs: 15 }), { name: 'PermissionTimeoutError' })
  assert.equal(signal.aborted, true)
})

test('superseded or disposed request ends even when the client ignores cancellation', async () => {
  const controller = new AbortController()
  let signal
  const work = getManagementPermission({ get: (_path, options) => {
    signal = options.signal
    return new Promise(() => {})
  } }, { signal: controller.signal })
  controller.abort()
  await assert.rejects(work, { name: 'AbortError' })
  assert.equal(signal.aborted, true)
  let requests = 0
  await assert.rejects(getManagementPermission({ get: () => { requests++; return Promise.resolve({}) } },
    { signal: controller.signal }), { name: 'AbortError' })
  assert.equal(requests, 0)
})

test('malformed identity and rejected responses do not confer management permission', async () => {
  for (const result of [{}, { is_superuser: 'true', is_active: true }, { is_superuser: true },
    { success: false, message: '登录无效', data: {} }]) {
    await assert.rejects(getManagementPermission({ get: async () => result }))
  }
  await assert.rejects(getManagementPermission({ get: async () => { throw new Error('network failure') } }), /network failure/)
})

function authenticatedClient() {
  const state = { identity: 'session-a', user: { is_active: true, is_superuser: true }, requests: 0, failureHandlers: [], pending: null }
  const api = { interceptors: { response: { use: (_success, failure) => state.failureHandlers.push(failure) } },
    get: async (path, options) => {
      const config = { baseURL: '/api/v1/', ...options }
      const headers = { get: name => name === 'Authorization' ? state.identity : undefined }
      for (const transform of config.transformRequest || []) transform.call(config, undefined, headers)
      if (config.adapter) return (await config.adapter(config)).data
      state.requests++
      if (state.pending) return await state.pending
      return structuredClone(state.user)
    },
  }
  return { api, state }
}

test('one verified login result serves later opens; identity change and explicit refresh query again', async () => {
  const { api, state } = authenticatedClient()
  assert.deepEqual(await getManagementPermission(api), { can_manage: true })
  for (let i = 0; i < 5; i++) assert.deepEqual(await getManagementPermission(api), { can_manage: true })
  assert.equal(state.requests, 1)
  state.identity = 'session-b'
  state.user.is_superuser = false
  assert.deepEqual(await getManagementPermission(api), { can_manage: false })
  assert.equal(state.requests, 2)
  state.user.is_superuser = true
  assert.deepEqual(await getManagementPermission(api, { refresh: true }), { can_manage: true })
  assert.equal(state.requests, 3)
  state.identity = ''
  state.user.is_active = false
  assert.deepEqual(await getManagementPermission(api), { can_manage: false })
  state.identity = 'session-a'
  state.user.is_active = true
  assert.deepEqual(await getManagementPermission(api), { can_manage: true })
  assert.equal(state.requests, 5)
})

test('concurrent views share a pending identity check and a forbidden response invalidates its cache', async () => {
  const { api, state } = authenticatedClient()
  let finish
  state.pending = new Promise(resolve => { finish = resolve })
  const first = getManagementPermission(api), second = getManagementPermission(api)
  assert.equal(state.requests, 1)
  finish({ is_active: true, is_superuser: true })
  assert.deepEqual(await first, { can_manage: true })
  assert.deepEqual(await second, { can_manage: true })
  assert.equal(state.failureHandlers.length, 1)
  await assert.rejects(state.failureHandlers[0]({ response: { status: 403 } }))
  state.pending = null
  state.user.is_superuser = false
  assert.deepEqual(await getManagementPermission(api), { can_manage: false })
  assert.equal(state.requests, 2)
})

test('a failed session check is never retained as a successful cache entry', async () => {
  const { api, state } = authenticatedClient()
  state.pending = new Promise(() => {})
  await assert.rejects(getManagementPermission(api, { timeoutMs: 15 }), { name: 'PermissionTimeoutError' })
  state.pending = null
  assert.deepEqual(await getManagementPermission(api), { can_manage: true })
  assert.equal(state.requests, 2)
})
