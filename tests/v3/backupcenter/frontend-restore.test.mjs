import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const frontend = new URL('../../../plugins.v3/backupcenter/frontend/', import.meta.url)
const vue = createRequire(new URL('package.json', frontend))('vue')
const source = readFileSync(new URL('src/components/Page.vue', frontend), 'utf8')
  .split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function preview(backupId) {
  return {
    online_restore_allowed: true,
    manifest: { backup_id: backupId, scope: { plugin_settings: true } },
  }
}

function fixture(postResult = null) {
  const requests = [], posts = [], unmount = []
  const props = vue.shallowReactive({ api: {}, pluginId: 'BackupCenter' })
  const scope = vue.effectScope()
  const context = vm.createContext({
    ...vue, console,
    defineProps: () => props, defineEmits: () => () => {},
    onMounted: () => {}, onBeforeUnmount: fn => unmount.push(fn),
    getPluginApi: (_api, _pluginId, path) => {
      if (!path.endsWith('/preview')) return Promise.resolve({})
      const pending = deferred()
      requests.push({ ...pending, path })
      return pending.promise
    },
    postPluginApi: async (_api, pluginId, path, payload) => {
      posts.push({ pluginId, path, payload })
      return postResult || { emergency_backup_id: 'lab-only' }
    },
  })
  scope.run(() => vm.runInContext(`${source}\nglobalThis.state = {
    prepareRestore, restoreLogical, preview, selectedBackupId, restoreDialog,
    restoreForm, actionLoading, feedback,
  }`, context))
  return {
    ...context.state, props, requests, posts,
    unmount() { unmount.forEach(fn => fn()); scope.stop() },
  }
}

test('an earlier preview cannot open a confirmation for the pending selection', async () => {
  const page = fixture()
  const first = page.prepareRestore('backup-A')
  const second = page.prepareRestore('backup-B')
  page.requests[0].resolve(preview('backup-A'))
  await first
  assert.equal(page.preview.value, null)
  assert.equal(page.restoreDialog.value, false)
  assert.equal(page.actionLoading.value, 'preview:backup-B')
  await page.restoreLogical()
  assert.equal(page.posts.length, 0)
  page.requests[1].resolve(preview('backup-B'))
  await second
  assert.equal(page.preview.value.manifest.backup_id, 'backup-B')
  page.unmount()
})

test('late success or failure cannot replace a newer preview or its form', async () => {
  for (const fail of [false, true]) {
    const page = fixture()
    const first = page.prepareRestore('backup-A')
    const second = page.prepareRestore('backup-B')
    page.requests[1].resolve(preview('backup-B'))
    await second
    page.restoreForm.pluginIds = ['LabPlugin']
    page.restoreForm.selection.pluginSettings = true
    if (fail) page.requests[0].reject(new Error('old request failed'))
    else page.requests[0].resolve(preview('backup-A'))
    await first
    assert.equal(page.preview.value.manifest.backup_id, 'backup-B')
    assert.equal(page.restoreForm.selection.pluginSettings, true)
    assert.equal(page.feedback.show, false)
    await page.restoreLogical()
    assert.equal(page.posts[0].payload.backup_id, 'backup-B')
    page.unmount()
  }
})

test('changing the backup, plugin instance or API invalidates an accepted preview', async () => {
  for (const change of [
    page => { page.selectedBackupId.value = 'backup-B' },
    page => { page.props.pluginId = 'BackupCenterClone' },
    page => { page.props.api = {} },
  ]) {
    const page = fixture()
    const pending = page.prepareRestore('backup-A')
    page.requests[0].resolve(preview('backup-A'))
    await pending
    page.restoreForm.pluginIds = ['LabPlugin']
    page.restoreForm.selection.pluginSettings = true
    change(page)
    assert.equal(page.preview.value, null)
    assert.equal(page.restoreDialog.value, false)
    await page.restoreLogical()
    assert.equal(page.posts.length, 0)
    page.unmount()
  }
})

test('unmounted preview callbacks cannot reopen the restore dialog', async () => {
  const page = fixture()
  const pending = page.prepareRestore('backup-A')
  page.unmount()
  page.requests[0].resolve(preview('backup-A'))
  await pending
  assert.equal(page.preview.value, null)
  assert.equal(page.restoreDialog.value, false)
  await page.restoreLogical()
  assert.equal(page.posts.length, 0)
})

test('a mismatched manifest is rejected before confirmation', async () => {
  const page = fixture()
  const pending = page.prepareRestore('backup-A')
  page.requests[0].resolve(preview('backup-B'))
  await pending
  assert.equal(page.preview.value, null)
  assert.equal(page.restoreDialog.value, false)
  assert.equal(page.feedback.color, 'error')
  page.unmount()
})

test('an in-flight restore cannot submit twice or start another preview', async () => {
  const response = deferred()
  const page = fixture(response.promise)
  const pending = page.prepareRestore('backup-A')
  page.requests[0].resolve(preview('backup-A'))
  await pending
  page.restoreForm.pluginIds = ['LabPlugin']
  page.restoreForm.selection.pluginSettings = true
  const restoring = page.restoreLogical()
  await page.restoreLogical()
  await page.prepareRestore('backup-B')
  assert.equal(page.posts.length, 1)
  assert.equal(page.requests.length, 1)
  assert.equal(page.posts[0].payload.backup_id, 'backup-A')
  response.resolve({ emergency_backup_id: 'lab-only' })
  await restoring
  page.unmount()
})
