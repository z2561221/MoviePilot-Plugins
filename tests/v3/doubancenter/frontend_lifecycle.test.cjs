const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { createRequire } = require('node:module')

const root = path.resolve(__dirname, '../../../plugins.v3/doubancenter')
const requirePlugin = createRequire(path.join(root, 'package.json'))
const vue = requirePlugin('vue')
const compiler = requirePlugin('vue/compiler-sfc')
const ok = data => ({ success: true, message: '', data })
const tick = async () => { await vue.nextTick(); await Promise.resolve(); await Promise.resolve() }

async function load(file) {
  const context = vm.createContext({ console, setTimeout, clearTimeout, AbortController, URLSearchParams, URL })
  const cache = new Map()
  const vueModule = new vm.SyntheticModule(Object.keys(vue), function () {
    for (const [key, value] of Object.entries(vue)) this.setExport(key, value)
  }, { context })
  async function read(file) {
    if (cache.has(file)) return cache.get(file)
    let code = fs.readFileSync(file, 'utf8')
    if (file.endsWith('.vue')) {
      const { descriptor } = compiler.parse(code, { filename: file })
      code = compiler.compileScript(descriptor, { id: 'dc-lifecycle-test' }).content
    }
    const module = new vm.SourceTextModule(code, { context, identifier: file })
    cache.set(file, module)
    await module.link(async (name, parent) => {
      if (name === 'vue') return vueModule
      let target = path.resolve(path.dirname(parent.identifier), name)
      if (!path.extname(target)) target += '.js'
      return read(target)
    })
    return module
  }
  const module = await read(path.join(root, 'src/components', file))
  await module.evaluate()
  return module.namespace
}

async function mount(file, props, { keepAlive = false } = {}) {
  const module = await load(file)
  let state
  const component = { ...module.default, setup(props, context) {
    state = vue.proxyRefs(module.default.setup(props, context))
    return () => null
  } }
  const before = [], after = []
  const register = list => fn => { list.push(fn); return () => list.splice(list.indexOf(fn), 1) }
  const renderer = vue.createRenderer({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null,
  })
  const visible = vue.ref(true)
  const app = renderer.createApp({ render: () => keepAlive
    ? vue.h(vue.KeepAlive, null, { default: () => visible.value ? vue.h(component, props) : null })
    : vue.h(component, props) })
  app.config.globalProperties.$router = { beforeEach: register(before), afterEach: register(after) }
  app.mount({})
  await tick()
  return { state, app, before, after, visible,
    leave: () => [...before].forEach(fn => fn({ path: '/else' }, { path: '/plugin' })),
    finish: failure => Promise.all([...after].map(fn => fn({ path: '/else' }, { path: '/plugin' }, failure))),
  }
}

test('删除旧实例的回执不回写、不刷新新实例且不清除新操作状态', async () => {
  const { usePageRuntime } = await load('page/usePageRuntime.js')
  const id = vue.ref('DoubanCenter'), pending = [], reads = []
  const api = { post: () => new Promise(resolve => pending.push(resolve)), get: url => { reads.push(url); return Promise.resolve(ok(null)) } }
  const scope = vue.effectScope()
  const page = scope.run(() => usePageRuntime({ api: () => api, pluginId: () => id.value, nativeSubscribe: () => null }))
  try {
    const old = page.deleteArchive({ id: 'old' }, 0)
    id.value = 'DoubanCenterClone'
    const next = page.deleteArchive({ id: 'new' }, 1)
    pending[0](ok(null)); await old
    assert.equal(reads.length, 0)
    assert.notEqual(page.actionKey, '')
    assert.equal(page.actionMessage, '')
    pending[1](ok(null)); await next
    assert.equal(reads.length, 6)
    assert.equal(page.actionKey, '')
  } finally { scope.stop() }
})

for (const mode of ['leave', 'unmount', 'switch']) {
  test(`仪表盘识别未返回时 ${mode} 不打开原生订阅`, async () => {
    let resolveMedia, opened = 0
    const props = vue.reactive({ pluginId: 'DoubanCenter', config: {}, nativeSubscribe: async () => { opened++; return { success: true } },
      api: { get: url => url.includes('resolve_media') ? new Promise(r => { resolveMedia = r }) : Promise.resolve(ok({})) } })
    const f = await mount('Dashboard.vue', props)
    try {
      await f.state.showActionDialog('tv_global', { title: 'Old', tmdbid: 1 })
      const request = f.state.doSubscribe()
      await tick()
      if (mode === 'leave') f.leave()
      if (mode === 'unmount') f.app.unmount()
      if (mode === 'switch') { props.pluginId = 'DoubanCenterClone'; await tick() }
      resolveMedia(ok({ title: 'Old', tmdbid: 1 })); await request
      assert.equal(opened, 0)
      assert.equal(f.state.subscribeResult, '')
    } finally { if (mode !== 'unmount') f.app.unmount() }
    assert.equal(f.before.length, 0)
  })
}

test('仪表盘等待读取期间离页，不再发出 RSS 刷新写请求', async () => {
  const pending = []; let posts = 0, defer = false
  const props = vue.reactive({ pluginId: 'DoubanCenter', config: {}, api: {
    get: () => defer ? new Promise(r => pending.push(r)) : Promise.resolve(ok({})),
    post: async () => { posts++; return ok({}) },
  } })
  const f = await mount('Dashboard.vue', props)
  try {
    await tick(); defer = true
    const run = f.state.refreshDashboard(); await tick(); f.leave()
    pending.forEach(resolve => resolve(ok({}))); await run
    assert.equal(posts, 0)
    assert.equal(f.state.refreshing, false)
  } finally { f.app.unmount() }
})

test('仪表盘切换到已有 TMDB 的条目不遗留识别锁', async () => {
  let resolveMedia
  const f = await mount('Dashboard.vue', vue.reactive({ pluginId: 'DoubanCenter', api: {
    get: url => url.includes('resolve_media') ? new Promise(r => { resolveMedia = r }) : Promise.resolve(ok({})),
  } }))
  try {
    const first = f.state.showActionDialog('bangumi', { title: 'A' }); await tick()
    f.state.showDialog = false
    await f.state.showActionDialog('tv_global', { title: 'B', tmdbid: 2 })
    resolveMedia(ok({ title: 'A', tmdbid: 1 })); await first
    assert.equal(f.state.dialogResolving, false)
    assert.equal(f.state.dialogItem.item.title, 'B')
  } finally { f.app.unmount() }
})

test('侧栏设置旧响应不能带入新实例，旧保存回执不能关闭新状态', async () => {
  let read, write
  const props = vue.reactive({ pluginId: 'DoubanCenter', api: {
    get: () => new Promise(r => { read = r }), put: () => new Promise(r => { write = r }),
  } })
  const f = await mount('AppPage.vue', props)
  try {
    const opening = f.state.openSettings(); props.pluginId = 'Clone'; await tick()
    read(ok({ secret: 'old-config' })); await opening
    assert.equal(f.state.settingsDialog, false)
    assert.equal(f.state.settingsConfig.secret, undefined)
    const saving = f.state.saveSettings({ enabled: true }); f.leave()
    write(ok(null)); await saving
    assert.equal(f.state.pageKey, 0)
    assert.equal(f.state.snackbar.show, false)
  } finally { f.app.unmount() }
})

test('特别篇季号 0 同时进入识别与订阅请求', async () => {
  const { useRankMediaActions } = await load('useRankMediaActions.js')
  const requests = []
  const api = { get: async url => { requests.push(url); return ok({ title: 'Special', season: 0 }) }, post: async url => { requests.push(url); return ok({}) } }
  const actions = useRankMediaActions({ api, pluginId: 'DoubanCenter', rankNameOf: () => 'TV' })
  await actions.resolveRankMedia('tv_global', { title: 'Special', season: 0 })
  await actions.requestRankSubscription('tv_global', { title: 'Special', season: 0 })
  assert.equal(requests.length, 2)
  assert.ok(requests.every(url => /[?&]season=0(?:&|$)/.test(url)))
})

for (const failure of [undefined, { type: 'aborted' }]) {
  test(`导航${failure ? '取消' : '成功复用'}后恢复新请求，旧回执仍然失效`, async () => {
    const reads = []
    const f = await mount('AppPage.vue', vue.reactive({ pluginId: 'DoubanCenter',
      api: { get: () => new Promise(resolve => reads.push(resolve)) },
    }))
    try {
      const old = f.state.openSettings()
      f.leave(); await f.finish(failure)
      const current = f.state.openSettings()
      assert.equal(reads.length, 2)
      reads[0](ok({ name: 'old' })); await old
      assert.equal(f.state.loadingSettings, true)
      assert.equal(f.state.settingsDialog, false)
      reads[1](ok({ name: 'current' })); await current
      assert.equal(f.state.settingsConfig.name, 'current')
      assert.equal(f.state.loadingSettings, false)
    } finally { f.app.unmount() }
  })
}

test('KeepAlive 失活后其他导航不能复活旧组件，重新激活允许新读取', async () => {
  let reads = 0
  const f = await mount('AppPage.vue', vue.reactive({ pluginId: 'DoubanCenter',
    api: { get: async () => { reads++; return ok({}) } },
  }), { keepAlive: true })
  try {
    f.leave(); f.visible.value = false; await tick(); await f.finish()
    await f.finish({ type: 'aborted' })
    await f.state.openSettings()
    assert.equal(reads, 0)
    f.visible.value = true; await tick()
    await f.state.openSettings()
    assert.equal(reads, 1)
  } finally { f.app.unmount() }
  assert.equal(f.before.length, 0)
  assert.equal(f.after.length, 0)
})

test('请求归属失效时清理等待与延迟反馈，旧代次不因恢复而复活', async () => {
  const { useRequestScope } = await load('useRequestScope.js')
  const scope = vue.effectScope(), id = vue.ref('DoubanCenter')
  const requests = scope.run(() => useRequestScope(() => id.value))
  let callbacks = 0
  const old = requests.capture()
  const waiting = requests.wait(60000)
  requests.later(() => { callbacks++ }, 60000)
  requests.pause()
  assert.equal(await waiting, false)
  requests.resume(); await tick()
  assert.equal(old(), false)
  assert.equal(requests.capture()(), true)
  assert.equal(callbacks, 0)
  scope.stop(); requests.resume()
  assert.equal(requests.isActive(), false)
})

test('配置总览旧实例响应不得覆盖新实例或清除新 loading', async () => {
  const { useConfigForm } = await load('config/useConfigForm.js')
  const scope = vue.effectScope(), id = vue.ref('DoubanCenter'), pending = []
  const config = scope.run(() => useConfigForm({ api: () => ({ get: () => new Promise(r => pending.push(r)) }),
    pluginId: () => id.value, initialConfig: () => ({}), emit() {},
  }))
  try {
    const old = config.loadOverview()
    id.value = 'Clone'
    const current = config.loadOverview()
    pending[0](ok({ cards: ['old'] })); await old
    assert.equal(config.loadingOverview, true)
    pending[1](ok({ cards: ['current'] })); await current
    assert.equal(config.overview.cards[0], 'current')
    assert.equal(config.loadingOverview, false)
  } finally { scope.stop() }
})
