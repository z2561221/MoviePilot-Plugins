import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getPluginApi,
  getPluginConfig,
  pluginApiPath,
  postPluginApi,
  savePluginConfig,
} from '../../../plugins.v3/backupcenter/frontend/src/components/api.js'

test('构造自定义备份中心实例路径', () => {
  assert.equal(pluginApiPath('BackupCenterClone', 'overview'), 'plugin/BackupCenterClone/overview')
  assert.equal(pluginApiPath('BackupCenterClone', ''), 'plugin/BackupCenterClone')
})

test('所有备份中心 API 使用注入的实例 ID', async () => {
  const calls = []
  const api = {
    get: async (path) => {
      calls.push(['get', path])
      return { success: true, message: '', data: { ok: true } }
    },
    post: async (path) => {
      calls.push(['post', path])
      return { success: true, message: '', data: { ok: true } }
    },
    put: async (path) => {
      calls.push(['put', path])
      return { success: true, message: '', data: { ok: true } }
    },
  }

  await getPluginApi(api, 'BackupCenterClone', 'overview')
  await getPluginConfig(api, 'BackupCenterClone')
  await postPluginApi(api, 'BackupCenterClone', 'run')
  await savePluginConfig(api, 'BackupCenterClone', {})

  assert.deepEqual(calls.map(([, path]) => path), [
    'plugin/BackupCenterClone/overview',
    'plugin/BackupCenterClone/config',
    'plugin/BackupCenterClone/run',
    'plugin/BackupCenterClone',
  ])
})
