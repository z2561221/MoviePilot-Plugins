const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const { createRequire } = require('node:module')
const { webcrypto } = require('node:crypto')
const vm = require('node:vm')

const frontend = resolve(__dirname, '../../../plugins.v3/downloadmanagerlocal/frontend')
const requireFrontend = createRequire(resolve(frontend, 'package.json'))
const vue = requireFrontend('vue')
const compiler = requireFrontend('vue/compiler-sfc')
const source = readFileSync(resolve(frontend, 'src/components/AutoDeletePane.vue'), 'utf8')
const parsed = compiler.parse(source)
const clone = value => JSON.parse(JSON.stringify(value))
const defaults = () => ({ enabled: false, schedule_type: 'interval', interval_minutes: 5, cron: '', sample_minutes: 5,
  max_tasks: 20, source_paths: [], exclude_paths: [], notify: false, history_days: 30, rules: [] })
const settle = async () => { await vue.nextTick(); await new Promise(resolve => setImmediate(resolve)) }

function fixture({ get, post, crypto = webcrypto } = {}) {
  const props = vue.reactive({ api: {}, pluginId: 'ScopedInstance', canManage: true, mode: 'config', section: 'basic', active: true })
  const bodies = [], events = [], cleanups = [], reads = [], timers = []
  const getApi = get || ((_api, _id, path) => Promise.resolve(path === 'auto_delete/config'
    ? { settings: defaults(), revision: 1 } : path === 'downloaders'
      ? [{ title: 'QB', value: 'QB', type: 'qbittorrent' }]
      : path.startsWith('auto_delete/history') ? { items: [], total: 0 } : { active: false, state: 'disabled' }))
  const script = parsed.descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const context = { ...vue, URLSearchParams, JSON, Number, Set, Date, console,
    crypto,
    defineProps: () => props, defineEmits: () => (name, data) => events.push({ name, data }), defineExpose: () => {},
    onBeforeUnmount: callback => cleanups.push(callback), setInterval: callback => (timers.push(callback), timers.length), clearInterval: () => {},
    document: { visibilityState: 'visible' }, isApiRequestCancellation: reason => reason?.name === 'AbortError',
    getPluginApi: (...args) => { reads.push(args[2]); return getApi(...args) }, postPluginJsonApi: (_api, id, path, body) => {
      bodies.push({ id, path, body: clone(body) })
      return post ? post(id, path, body) : Promise.resolve({ settings: defaults(), revision: 2, matches: [], items: [], state: 'accepted' })
    },
  }
  vm.createContext(context)
  const scope = vue.effectScope()
  scope.run(() => vm.runInContext(script + '\nglobalThis.view = {settings, revision, saved, dirty, historyLoading, previewResult, busy, error, message, confirmRule, confirmJobs, selectedJobs, confirmEvidence, acceptHistory, addRule, duplicate, numberValue, save, preview, activate, run, stop, load}', context))
  return { props, bodies, events, reads, timers, view: context.view, close: () => { cleanups.forEach(callback => callback()); scope.stop() } }
}

test('actual rule pane, cron editor and both overview consumers compile', () => {
  for (const name of ['AutoDeletePane', 'AutoDeleteCron', 'SyncDeleteDetails', 'SyncDeletePane', 'Config', 'Page']) {
    const descriptor = compiler.parse(readFileSync(resolve(frontend, `src/components/${name}.vue`), 'utf8')).descriptor
    const script = compiler.compileScript(descriptor, { id: name })
    const result = compiler.compileTemplate({ source: descriptor.template.content, filename: name, id: name, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  }
})

test('numeric zero remains an explicit threshold and blank becomes null', async () => {
  const instance = fixture()
  try {
    await settle()
    instance.view.addRule()
    const [rule] = instance.view.settings.value.rules
    assert.equal(rule.mode, 'debug')
    assert.equal(rule.enabled, false)
    instance.view.numberValue(rule, 'upload_kib_max', 0)
    assert.equal(rule.conditions.upload_kib_max, 0)
    instance.view.numberValue(rule, 'upload_kib_max', '')
    assert.equal(rule.conditions.upload_kib_max, null)
  } finally { instance.close() }
})

test('seed time supports half an hour without converting the stored unit', async () => {
  const instance = fixture()
  try {
    await settle()
    const rule = { conditions: { seed_hours_min: 168 } }
    assert(source.includes("['seed_hours_min', '最少做种小时']"))
    assert.equal(rule.conditions.seed_hours_min, 168)
    instance.view.numberValue(rule, 'seed_hours_min', 0.5)
    assert.equal(rule.conditions.seed_hours_min, 0.5)
  } finally { instance.close() }
})

test('with only getRandomValues, new and copied rules stay disabled drafts until saved', async () => {
  const original = { id: 'existing-rule', name: '现有规则', revision: 4, enabled: true, mode: 'delete', action: 'torrent', conditions: {} }
  let stored = { settings: { ...defaults(), rules: [original] }, revision: 1 }
  const get = async (_api, _id, path) => path === 'auto_delete/config' ? stored : path === 'downloaders' ? [] : {}
  const crypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) }
  const instance = fixture({ crypto, get, post: (_id, _path, body) => (stored = { settings: clone(body.settings), revision: 2 }) })
  try {
    await settle()
    instance.view.addRule()
    instance.view.addRule()
    instance.view.duplicate(instance.view.settings.value.rules[0])
    const [existing, ...created] = instance.view.settings.value.rules
    assert.deepEqual(clone(existing), original)
    assert.equal(created.length, 3)
    assert.equal(created[2].name, '现有规则 副本')
    const ids = Array.from(created, rule => rule.id)
    assert.equal(new Set(ids).size, 3)
    for (const rule of created) {
      assert.match(rule.id, /^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$/)
      assert.equal(rule.revision, 1)
      assert.equal(rule.mode, 'debug')
      assert.equal(rule.enabled, false)
    }
    assert.equal(instance.bodies.length, 0)
    assert.equal(await instance.view.save(), true)
    assert.equal(instance.bodies.length, 1)
    assert.equal(instance.bodies[0].path, 'auto_delete/config')
    assert.deepEqual(instance.bodies[0].body.settings.rules.map(rule => rule.id), [original.id, ...ids])

    const reloaded = fixture({ crypto, get })
    try {
      await settle()
      assert.deepEqual(Array.from(reloaded.view.settings.value.rules, rule => rule.id), [original.id, ...ids])
    } finally { reloaded.close() }
  } finally { instance.close() }
})

test('collision retries check both saved rules and unsaved drafts', async () => {
  const originalId = '00000000000040008000000000000000'
  const draws = [0, 1, 0, 1, 2]
  const instance = fixture({ crypto: { getRandomValues: bytes => bytes.fill(draws.shift()) },
    get: async (_api, _id, path) => path === 'auto_delete/config'
      ? { settings: { ...defaults(), rules: [{ id: originalId }] }, revision: 1 } : path === 'downloaders' ? [] : {} })
  try {
    await settle()
    instance.view.addRule()
    instance.view.duplicate(instance.view.settings.value.rules[1])
    assert.deepEqual(draws, [])
    assert.deepEqual(Array.from(instance.view.settings.value.rules, rule => rule.id), [
      originalId, '01010101010141018101010101010101', '02020202020242028202020202020202',
    ])
    assert.equal(instance.view.error.value, '')
    assert.equal(instance.bodies.length, 0)
  } finally { instance.close() }
})

test('unavailable randomness or repeated collisions show an error without adding a rule', async () => {
  const failure = '无法生成规则编号，未添加规则'
  const original = { id: '00000000000040008000000000000000', name: '现有规则' }
  let attempts = 0
  for (const crypto of [null, {}, { getRandomValues: () => { throw new Error('randomness unavailable') } },
    { getRandomValues: bytes => { assert(++attempts <= 5); return bytes.fill(0) } }]) {
    const instance = fixture({ crypto, get: async (_api, _id, path) => path === 'auto_delete/config'
      ? { settings: { ...defaults(), rules: [original] }, revision: 1 } : path === 'downloaders' ? [] : {} })
    try {
      await settle()
      instance.view.addRule()
      assert.equal(instance.view.error.value, failure)
      attempts = 0
      instance.view.duplicate(instance.view.settings.value.rules[0])
      assert.equal(instance.view.error.value, failure)
      assert.deepEqual(clone(instance.view.settings.value.rules), [original])
      assert.equal(instance.view.dirty.value, false)
      assert.equal(instance.bodies.length, 0)
    } finally { instance.close() }
  }
  assert.equal(attempts, 5)
})

test('configuration loads status and rules without querying execution history', async () => {
  const instance = fixture()
  try {
    await settle()
    assert(instance.reads.some(path => path === 'auto_delete/config'))
    assert(instance.reads.some(path => path === 'downloaders'))
    assert(instance.reads.some(path => path === 'auto_delete/status'))
    assert.equal(instance.reads.some(path => path.startsWith('auto_delete/history')), false)

    instance.props.mode = 'history'
    await settle()
    assert(instance.reads.some(path => path.startsWith('auto_delete/history')))
  } finally { instance.close() }
})

test('hidden configuration section preserves an unsaved draft through refresh', async () => {
  const instance = fixture()
  try {
    await settle()
    instance.view.settings.value.interval_minutes = 17
    instance.props.active = false
    const readsBeforeHide = instance.reads.length
    await instance.timers[0]()
    assert.equal(instance.reads.length, readsBeforeHide)
    instance.props.active = true
    instance.props.section = 'advanced'
    await instance.view.load({ all: true })
    assert.equal(instance.view.settings.value.interval_minutes, 17)
    assert.equal(instance.view.dirty.value, true)
    assert.equal(instance.reads.some(path => path.startsWith('auto_delete/history')), false)
  } finally { instance.close() }
})

test('saving reports failure to the parent instead of emitting an accepted configuration', async () => {
  const instance = fixture({ post: () => Promise.reject(new Error('规则保存失败')) })
  try {
    await settle()
    instance.view.settings.value.interval_minutes = 17
    assert.equal(await instance.view.save(), false)
    assert.equal(instance.view.dirty.value, true)
    assert.equal(instance.events.length, 0)
  } finally { instance.close() }
})

test('stale preview cannot overwrite an edited draft', async () => {
  let finishPreview
  const instance = fixture({ post: (_id, path) => path === 'auto_delete/preview'
    ? new Promise(resolve => { finishPreview = resolve }) : Promise.resolve({}) })
  try {
    await settle()
    const request = instance.view.preview()
    await settle()
    instance.view.settings.value.interval_minutes = 30
    finishPreview({ state: 'preview', matches: [{ snapshot: { name: 'old draft' } }] })
    await request
    assert.equal(instance.view.previewResult.value, null)
    assert.equal(instance.bodies[0].path, 'auto_delete/preview')
    assert.equal(instance.bodies.length, 1)
  } finally { instance.close() }
})

test('confirmation sends reviewed identities and performs only an activation request', async () => {
  const instance = fixture()
  try {
    await settle()
    instance.view.confirmRule.value = { id: 'rule' }
    instance.view.selectedJobs.value = ['job']
    instance.view.confirmEvidence.value = { job: 'evidence-sha' }
    instance.view.acceptHistory.value = true
    await instance.view.activate()
    assert.equal(instance.bodies[0].id, 'ScopedInstance')
    assert.equal(instance.bodies[0].path, 'auto_delete/activate')
    assert.deepEqual(instance.bodies[0].body.evidence_versions, { job: 'evidence-sha' })
    assert.equal(instance.bodies[0].body.accept_history, true)
    assert.equal(instance.bodies.length, 1)
    assert.equal(instance.events[0].data.auto_delete_config_revision, 2)
  } finally { instance.close() }
})

test('management permission prevents preview and control calls', async () => {
  const instance = fixture()
  try {
    await settle()
    instance.props.canManage = false
    await instance.view.preview()
    await instance.view.run()
    await instance.view.stop()
    assert.equal(instance.bodies.length, 0)
  } finally { instance.close() }
})

test('late instance config cannot grant old settings to a new instance', async () => {
  const pending = []
  const instance = fixture({ get: (_api, id, path) => path === 'auto_delete/config'
    ? new Promise(resolve => pending.push({ id, resolve })) : Promise.resolve(path === 'downloaders' ? [] : { items: [], total: 0 }) })
  try {
    await settle()
    instance.props.pluginId = 'OtherInstance'
    await settle()
    pending[0].resolve({ settings: { ...defaults(), interval_minutes: 999 }, revision: 99 })
    await settle()
    assert.equal(instance.view.settings.value, null)
    pending[1].resolve({ settings: { ...defaults(), interval_minutes: 10 }, revision: 3 })
    await settle()
    assert.equal(instance.view.settings.value.interval_minutes, 10)
    assert.equal(instance.view.revision.value, 3)
  } finally { instance.close() }
})


test('a status failure leaves rules editable and a slow save preserves later rule edits', async () => {
  let finish
  const instance = fixture({ get: async (_api, _id, path) => {
    if (path === 'auto_delete/status') throw new Error('状态读取失败')
    if (path === 'auto_delete/config') return {settings: defaults(), revision: 1}
    return []
  }, post: (_id, _path, body) => new Promise(resolve => {
    finish = () => resolve({settings: body.settings, revision: 2})
  }) })
  try {
    await settle()
    instance.view.settings.value.interval_minutes = 12
    const saving = instance.view.save()
    await settle()
    instance.view.settings.value.interval_minutes = 18
    finish()
    await saving
    assert.equal(instance.view.settings.value.interval_minutes, 18)
    assert.equal(instance.view.revision.value, 2)
    assert.equal(instance.view.dirty.value, true)
  } finally { instance.close() }
})
