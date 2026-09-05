import test from 'node:test'
import assert from 'node:assert/strict'
import { apiGet, apiPost, pluginApiPath } from '../../../plugins.v3/localtoolkit/frontend/src/api.js'

test('构造自定义工具中心实例路径', () => {
  assert.equal(pluginApiPath('LocalToolkitClone', 'local_toolkit/status'), 'plugin/LocalToolkitClone/local_toolkit/status')
})

test('工具中心请求使用注入的实例 ID', async () => {
  const calls = []
  const api = {
    get: async (path) => {
      calls.push(['get', path])
      return { status: 'ok' }
    },
    post: async (path) => {
      calls.push(['post', path])
      return { success: true, message: 'done', data: { ok: true } }
    },
  }

  assert.deepEqual(await apiGet(api, pluginApiPath('LocalToolkitClone', 'local_toolkit/status')), { status: 'ok' })
  assert.deepEqual(await apiPost(api, pluginApiPath('LocalToolkitClone', 'local_toolkit/run/tmdb_cache')), {
    ok: true,
    success: true,
    message: 'done',
  })
  assert.deepEqual(calls, [
    ['get', 'plugin/LocalToolkitClone/local_toolkit/status'],
    ['post', 'plugin/LocalToolkitClone/local_toolkit/run/tmdb_cache'],
  ])
})
