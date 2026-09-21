import test from 'node:test'
import assert from 'node:assert/strict'
import { apiGet, apiPost, pluginApiPath, recheckCleanupPlan } from '../../../plugins.v3/localtoolkit/frontend/src/api.js'
import { migrateCleanupConfig } from '../../../plugins.v3/localtoolkit/frontend/src/cleanupConfig.js'
import { fitPlanPage, PLAN_ROW_HEIGHT, PLAN_HEADER_HEIGHT, PLAN_MOBILE_ROW_HEIGHT } from '../../../plugins.v3/localtoolkit/frontend/src/cleanupPlanLayout.js'
import { planConditionSummary } from '../../../plugins.v3/localtoolkit/frontend/src/planCondition.js'

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

test('列表页数按实际高度容纳完整行，桌面预留表头且最多十五条', () => {
  for (const height of [120, 240, 390, 480, 700]) {
    for (const mobile of [false, true]) {
      const { pageSize } = fitPlanPage(height, mobile)
      const occupied = pageSize * (mobile ? PLAN_MOBILE_ROW_HEIGHT : PLAN_ROW_HEIGHT) + (mobile ? 0 : PLAN_HEADER_HEIGHT)
      assert.ok(occupied <= height)
      assert.ok(pageSize >= 1 && pageSize <= 15)
    }
  }
  assert.equal(fitPlanPage(392, false).pageSize, 10)
  assert.equal(fitPlanPage(392, true).pageSize, 6)
  assert.equal(fitPlanPage(2000, false).pageSize, 15)
  assert.equal(fitPlanPage(0, false).pageSize, 1)
  assert.equal(fitPlanPage(Number.NaN, true).pageSize, 1)
})

test('缩放或切换移动布局后保留原首条所在页，不跳回第一页或跳过记录', () => {
  const firstIndex = 30
  for (const mobile of [false, true]) {
    const { page, pageSize } = fitPlanPage(300, mobile, 3, 15)
    assert.ok((page - 1) * pageSize <= firstIndex)
    assert.ok(page * pageSize > firstIndex)
  }
})

test('清理计划条件列显示播放与收藏快照，未知值不伪装成满足', () => {
  assert.equal(planConditionSummary({ played: true, favorite: false }), '已看过 · 未收藏')
  assert.equal(planConditionSummary({ played: false, favorite: true }), '未看过 · 已收藏')
  assert.equal(planConditionSummary({ played: null, favorite: undefined }), '观看未知 · 收藏未知')
})
