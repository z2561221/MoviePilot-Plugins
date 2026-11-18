const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const { createRequire } = require('node:module')

const root = path.resolve(__dirname, '../../../plugins.v3/downloadmanagerlocal')
const packer = import(pathToFileURL(path.join(root, 'frontend/scripts/federationArtifacts.js')).href)
function sandbox() {
  assert(process.env.MP_TEST_ARTIFACTS, 'Set MP_TEST_ARTIFACTS to the task archive')
  return fs.mkdtempSync(path.join(process.env.MP_TEST_ARTIFACTS, 'federation-'))
}
function payload(folder, revision) {
  const files = {
    'remoteEntry.js': `export const init = () => {}; export const dynamicLoadingCss = () => {}; export const get = () => import('./view-${revision}.mjs');\n`,
    [`view-${revision}.mjs`]: `export const value = '${revision}';\n`,
    [`view-${revision}.css`]: '.dm-view { color: blue; }\n',
  }
  fs.mkdirSync(path.join(folder, 'assets'), { recursive: true })
  for (const [name, text] of Object.entries(files)) fs.writeFileSync(path.join(folder, 'assets', name), text)
  return Object.keys(files).map(name => 'assets/' + name)
}

test('same content has stable entry; changing content preserves old entry and dependencies', async () => {
  const { packageFederationAssets } = await packer
  const output = sandbox(), duplicate = sandbox()
  const first = packageFederationAssets(output, payload(output, 'old'))
  assert.deepEqual(first, packageFederationAssets(duplicate, payload(duplicate, 'old').reverse()))
  const oldEntry = path.join(output, 'assets', 'r' + first.revision, 'remoteEntry.js')
  const oldBytes = fs.readFileSync(oldEntry)
  const second = packageFederationAssets(output, payload(output, 'new'))
  assert.notEqual(first.path, second.path)
  assert.deepEqual(fs.readFileSync(oldEntry), oldBytes)
  assert.equal((await (await import(pathToFileURL(oldEntry).href)).get()).value, 'old')
  const nextEntry = path.join(output, 'assets', 'r' + second.revision, 'remoteEntry.js')
  assert.equal((await (await import(pathToFileURL(nextEntry).href)).get()).value, 'new')
  assert(fs.existsSync(path.join(output, 'assets/view-old.mjs')))
  assert(fs.existsSync(path.join(output, 'assets/view-new.mjs')))
})

test('missing dependency does not publish a manifest and unsafe emitted paths are rejected', async () => {
  const { packageFederationAssets } = await packer
  const output = sandbox()
  const names = payload(output, 'bad')
  fs.writeFileSync(path.join(output, 'federation.json'), 'previous manifest')
  fs.writeFileSync(path.join(output, 'assets/view-bad.css'), 'a { background: url(./missing.png); }')
  assert.throws(() => packageFederationAssets(output, names), /Missing federation asset/)
  assert.equal(fs.readFileSync(path.join(output, 'federation.json'), 'utf8'), 'previous manifest')
  assert.throws(() => packageFederationAssets(output, ['assets/../outside.js']), /Invalid federation asset path/)
})

test('shipped Config and Page load through shared Vue and all generated CSS stays in the content directory', async () => {
  const req = createRequire(path.join(root, 'frontend/package.json'))
  const vue = req('vue')
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'dist/federation.json'), 'utf8'))
  const links = [], previous = global.document
  global.document = { createElement: () => ({}), head: { appendChild: node => links.push(node.href) } }
  try {
    const entry = pathToFileURL(path.join(root, manifest.path, 'remoteEntry.js')).href
    const remote = await import(entry)
    remote.init({ vue: { [vue.version]: { get: async () => () => vue, scope: 'default' } } })
    for (const expose of ['./Config', './Page']) {
      const component = (await remote.get(expose))()
      assert.equal(typeof component.setup, 'function', expose)
    }
    const forwarding = await import(pathToFileURL(path.join(root, 'dist/assets/remoteEntry.js')).href)
    assert.equal(forwarding.get, remote.get)
    assert(links.length >= 3)
    for (const href of links) {
      assert(href.startsWith(new URL('./', entry).href), href)
      assert(fs.existsSync(new URL(href)), href)
    }
  } finally { global.document = previous }
})

test('shipped Config and Page mount with populated overview without runtime exceptions or writes', async () => {
  const req = createRequire(path.join(root, 'frontend/package.json'))
  const vue = req('vue')
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'dist/federation.json'), 'utf8'))
  const saved = { document: global.document, window: global.window }
  global.document = { visibilityState: 'visible', createElement: () => ({}), head: { appendChild() {} }, addEventListener() {}, removeEventListener() {} }
  global.window = { setInterval: () => 1, clearInterval() {} }
  const remote = await import(pathToFileURL(path.join(root, manifest.path, 'remoteEntry.js')).href)
  remote.init({ vue: { [vue.version]: { get: async () => () => vue, scope: 'default' } } })
  const uiNames = new Set()
  for (const name of fs.readdirSync(path.join(root, 'frontend/src/components')).filter(name => name.endsWith('.vue'))) {
    for (const match of fs.readFileSync(path.join(root, 'frontend/src/components', name), 'utf8').matchAll(/<(V\w+)\b/g)) uiNames.add(match[1])
  }
  const keys = ['monitor', 'transfer', 'iyuu', 'rename', 'tag', 'seed', 'upload', 'sync_delete', 'auto_delete', 'archive']
  const overview = { cards: {}, modules: keys.map(key => ({ key, title: key, state: 'disabled', pending: 0, metrics: {} })) }
  const writes = []
  const api = { get: async url => {
    if (url === 'user/current') return { is_superuser: true, is_active: true }
    if (url.endsWith('/permissions')) return { can_manage: true }
    if (url.endsWith('/overview')) return overview
    if (url.endsWith('/diagnostics')) return {}
    if (url.endsWith('/upload_limit_status')) return {}
    return []
  }, post: async (...args) => { writes.push(args); throw new Error('Unexpected write') } }
  const node = type => ({ type, children: [], style: {} })
  const renderer = vue.createRenderer({
    createElement: node, createText: node, createComment: node,
    insert(child, parent, anchor) {
      if (child.parent) this.remove(child)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, child)
      child.parent = parent
    },
    remove(child) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = null },
    setText(child, text) { child.text = text }, setElementText(child, text) { child.text = text; child.children = [] },
    patchProp(child, key, old, value) { if (key === 'style' && value) Object.assign(child.style, value) },
    parentNode: child => child.parent, nextSibling: () => null,
  })
  try {
    for (const expose of ['./Config', './Page']) {
      const errors = [], warnings = []
      const app = renderer.createApp((await remote.get(expose))(), { api, pluginId: 'TestInstance', initialConfig: {} })
      app.config.errorHandler = error => errors.push(String(error))
      app.config.warnHandler = warning => warnings.push(warning)
      for (const name of uiNames) app.component(name, { inheritAttrs: false, setup(_props, { attrs, slots }) {
        return () => vue.h(name, attrs, name === 'VDialog' && !attrs.modelValue ? [] : Object.values(slots).flatMap(slot => slot()))
      } })
      try {
        app.mount(node('root'))
        for (let i = 0; i < 10; i++) { await new Promise(resolve => setImmediate(resolve)); await vue.nextTick() }
        assert.deepEqual(errors, [], expose)
        assert.deepEqual(warnings, [], expose)
        assert.deepEqual(writes, [])
      } finally { app.unmount() }
    }
  } finally { Object.assign(global, saved) }
})
