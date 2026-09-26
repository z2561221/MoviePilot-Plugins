const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { createRequire } = require('node:module')

const root = path.resolve(__dirname, '../../../plugins.v3/doubancenter')
const vue = createRequire(path.join(root, 'package.json'))('vue')

async function loadRuntime() {
  const context = vm.createContext({ console, setTimeout, clearTimeout, AbortController, URLSearchParams })
  const modules = new Map()
  const vueModule = new vm.SyntheticModule(Object.keys(vue), function () {
    for (const [key, value] of Object.entries(vue)) this.setExport(key, value)
  }, { context })
  async function load(file) {
    if (modules.has(file)) return modules.get(file)
    const module = new vm.SourceTextModule(fs.readFileSync(file, 'utf8'), { context, identifier: file })
    modules.set(file, module)
    await module.link(async (specifier, parent) => {
      if (specifier === 'vue') return vueModule
      let target = path.resolve(path.dirname(parent.identifier), specifier)
      if (!path.extname(target)) target += '.js'
      return load(target)
    })
    return module
  }
  const runtime = await load(path.join(root, 'src/components/page/usePageRuntime.js'))
  await runtime.evaluate()
  return { runtime: runtime.namespace, api: modules.get(path.join(root, 'src/components/api.js')).namespace }
}

async function fixture() {
  const { runtime } = await loadRuntime()
  const pending = []
  const scope = vue.effectScope()
  const id = vue.ref('DoubanCenter')
  const client = { get: url => new Promise(resolve => pending.push({ url, resolve })) }
  const page = scope.run(() => runtime.usePageRuntime({ api: () => client, pluginId: () => id.value, nativeSubscribe: () => null }))
  async function tick() { await Promise.resolve(); await Promise.resolve() }
  function settle(batch, pageNumber) {
    for (const request of batch) request.resolve({ success: true, data: request.url.includes('subscribe_history') || request.url.includes('archive_records')
      ? { page: pageNumber, items: [pageNumber], total_pages: 5, page_size: 20 } : null })
  }
  return { page, scope, id, pending, tick, settle }
}

test('旧历史响应不能覆盖后发请求，也不能清除新请求 loading', async () => {
  const f = await fixture()
  try {
    const first = f.page.loadAll(); await f.tick()
    f.page.historyData.page = 2
    const second = f.page.loadAll(); await f.tick()
    f.settle(f.pending.slice(0, 6), 1); await first
    assert.equal(f.page.loading, true)
    f.settle(f.pending.slice(6), 2); await second
    assert.equal(f.page.historyData.page, 2)
    const third = f.page.loadAll(); await f.tick()
    f.page.historyData.page = 3
    const fourth = f.page.loadAll(); await f.tick()
    f.settle(f.pending.slice(18), 3); await fourth
    f.settle(f.pending.slice(12, 18), 2); await third
    assert.equal(f.page.historyData.page, 3)
  } finally { f.scope.stop() }
})

test('归档乱序和离开归档后回包均不回写', async () => {
  const f = await fixture()
  try {
    const first = f.page.openArchivePage(); await f.tick()
    f.page.archiveData.page = 2
    const second = f.page.loadArchive(); await f.tick()
    f.settle(f.pending.slice(1), 2); await second
    f.settle(f.pending.slice(0, 1), 1); await first
    assert.equal(f.page.archiveData.page, 2)
    const third = f.page.loadArchive(); await f.tick()
    f.page.closeArchivePage()
    f.settle(f.pending.slice(2), 4); await third
    assert.equal(f.page.archiveData.page, 2)
  } finally { f.scope.stop() }
})

test('组件销毁与插件实例切换使旧请求失效', async () => {
  for (const dispose of [false, true]) {
    const f = await fixture()
    const run = f.page.loadAll(); await f.tick()
    if (dispose) f.scope.stop()
    else f.id.value = 'DoubanCenterClone'
    f.settle(f.pending, 5); await run
    assert.equal(f.page.historyData.page, 1)
    f.scope.stop()
  }
})

test('原生订阅必须明确受理，拒绝、空回执和异常不能报成功', async () => {
  const { api } = await loadRuntime()
  for (const reply of [{ success: false, message: '无权限' }, undefined, {}]) {
    await assert.rejects(api.openNativeSubscription(async () => reply, {}))
  }
  await assert.rejects(api.openNativeSubscription(async () => { throw new Error('offline') }, {}), /offline/)
  const reply = { success: true }
  assert.equal(await api.openNativeSubscription(async () => reply, {}), reply)
})
