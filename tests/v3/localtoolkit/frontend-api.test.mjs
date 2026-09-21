import test from 'node:test'
import assert from 'node:assert/strict'
import { apiGet, apiPost, pluginApiPath, recheckCleanupPlan } from '../../../plugins.v3/localtoolkit/frontend/src/api.js'
import { migrateCleanupConfig } from '../../../plugins.v3/localtoolkit/frontend/src/cleanupConfig.js'

test('旧周期与关闭的通知迁移为两组独立字段', () => {
  const old = { enabled: true, cron: '9 1 * * *', notify: false, auto_delete_max_count: 12 }
  const migrated = migrateCleanupConfig(old)
  for (const prefix of ['scan', 'cleanup']) {
    assert.equal(migrated[`${prefix}_enabled`], true)
    assert.equal(migrated[`${prefix}_cron`], '9 1 * * *')
    assert.equal(migrated[`${prefix}_notify`], false)
  }
  assert.equal(migrated.auto_delete_max_count, 12)
  assert.equal(old.notify, false)
  assert.equal('notify' in migrated, false)
})

test('已经保存的新配置优先于旧字段且空周期不被重置', () => {
  const config = migrateCleanupConfig({ enabled: true, notify: true, cron: '0 * * * *',
    scan_enabled: false, scan_cron: '', cleanup_notify: false })
  assert.equal(config.scan_enabled, false)
  assert.equal(config.scan_cron, '')
  assert.equal(config.cleanup_notify, false)
})

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

test('重新核验使用分身与完整条目身份，部分失败保留成功明细', async () => {
  const calls = []
  const results = [{ queue_key: 'server:a', state: 'eligible' }, { queue_key: 'server:b', state: 'unknown' }]
  const api = { post: async (path, body) => {
    calls.push([path, body])
    return { success: false, message: '部分条目需处理', data: { results, restored_count: 1 } }
  } }
  const response = await recheckCleanupPlan(api, 'LocalToolkitClone', 'server:a')
  assert.equal(response.success, false)
  assert.equal(response.restored_count, 1)
  assert.deepEqual(response.results, results)
  await recheckCleanupPlan(api, 'LocalToolkitClone')
  assert.deepEqual(calls, [
    ['plugin/LocalToolkitClone/local_toolkit/cleanup_plan/recheck', { queue_key: 'server:a' }],
    ['plugin/LocalToolkitClone/local_toolkit/cleanup_plan/recheck', {}],
  ])
})

test('核验请求失败不制造成功回执或自动重试', async () => {
  let count = 0
  const api = { post: async () => { count++; throw new Error('network unavailable') } }
  await assert.rejects(recheckCleanupPlan(api, 'LocalToolkitClone', 'server:a'), /network unavailable/)
  assert.equal(count, 1)
})
