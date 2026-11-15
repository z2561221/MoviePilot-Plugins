const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { createRequire } = require('node:module')
const { pathToFileURL } = require('node:url')

const root = path.resolve(__dirname, '../../../plugins.v3/doubancenter')
const requirePlugin = createRequire(path.join(root, 'package.json'))
const vue = requirePlugin('vue')
global.document = { createElement: () => ({}), head: { appendChild() {} } }
const manifest = JSON.parse(require('node:fs').readFileSync(path.join(root, 'dist/federation.json'), 'utf8'))
const shareScope = { vue: { [vue.version]: { get: async () => () => vue, scope: 'default' } } }
const remotePromise = import(pathToFileURL(path.join(root, manifest.path, 'remoteEntry.js')).href).then(remote => {
  remote.init(shareScope)
  return remote
})
const ok = data => ({ success: true, message: '', data })

test('构建产物的四个联邦入口能使用宿主共享Vue导入', async () => {
  const remote = await remotePromise
  for (const name of ['./Config', './Page', './Dashboard', './AppPage']) {
    const factory = await remote.get(name)
    assert.equal(typeof factory(), 'object', name)
    assert.equal(typeof factory().setup, 'function', name)
  }
})

test('根兼容转发与内容入口保留相同get/init合同', async () => {
  const remote = await remotePromise
  const forwarding = await import(pathToFileURL(path.join(root, 'dist/assets/remoteEntry.js')).href)
  assert.equal(forwarding.get, remote.get)
  assert.equal(forwarding.init, remote.init)
  assert.equal(forwarding.dynamicLoadingCss, remote.dynamicLoadingCss)
})

test('真实仪表模板渲染榜单海报和时间线链接，不访问缺失的实例函数', async () => {
  const remote = await remotePromise
  const factory = await remote.get('./Dashboard')
  const errors = [], warnings = [], attributes = []
  const makeNode = () => ({ children: [] })
  const renderer = vue.createRenderer({
    createElement: makeNode, createText: makeNode, createComment: makeNode,
    insert(node, parent) { node.parent = parent; parent.children.push(node) },
    remove(node) { if (node.parent) node.parent.children = node.parent.children.filter(item => item !== node) },
    setText() {}, setElementText() {},
    patchProp(node, key, previous, value) { if (['href', 'src'].includes(key)) attributes.push({ key, value }) },
    parentNode: node => node.parent, nextSibling: () => null,
  })
  const app = renderer.createApp(factory(), { pluginId: 'DoubanCenter', api: { get: async url => {
    if (url.includes('permissions')) return ok({ can_manage: true })
    if (url.includes('rank_history')) return ok({ movie_weekly: [{ title: 'Synthetic rank', poster: 'https://example.invalid/rank.jpg', tmdbid: 1 }] })
    if (url.includes('folio_data')) return ok({ movie: { timestamp: '2026-11-16 01:00:00', subject_name: 'Synthetic movie', subject_id: '1', type: 'movie', poster_path: 'https://example.invalid/poster.jpg' } })
    return ok({ dashboard_rank_keys: ['movie_weekly'], rank_options: [] })
  } } })
  app.config.errorHandler = error => errors.push(String(error))
  app.config.warnHandler = warning => warnings.push(warning)
  // 只替代Vuetify表面，执行实际构建模板、全部插槽和异步数据更新。
  for (const name of ['VCard', 'VCardItem', 'VCardTitle', 'VCardSubtitle', 'VCardText', 'VAvatar', 'VIcon', 'VBtn', 'VDivider', 'VProgressLinear', 'VAlert', 'VChip', 'VImg', 'VDialog', 'VCardActions']) {
    app.component(name, { setup(props, { slots }) { return () => vue.h('div', {}, Object.values(slots).flatMap(slot => slot())) } })
  }
  try {
    app.mount(makeNode())
    for (let i = 0; i < 8; i++) { await Promise.resolve(); await vue.nextTick() }
    assert.deepEqual(errors, [])
    assert.deepEqual(warnings, [])
    assert(attributes.some(item => item.key === 'href' && item.value === 'https://www.douban.com/doubanapp/dispatch?uri=/movie/1?from=mdouban&open=app'))
    assert(attributes.some(item => item.key === 'src' && item.value === 'https://example.invalid/rank.jpg'))
    assert(attributes.some(item => item.key === 'src' && item.value === 'https://example.invalid/poster.jpg'))
  } finally { app.unmount() }
})
