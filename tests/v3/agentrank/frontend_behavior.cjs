/* Execute the real SFC setup with Vue reactivity and controlled host callbacks. */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { createRequire } = require('node:module')
const frontend = path.resolve(__dirname, '../../..', 'plugins.v3/agentrank/frontend')
const vue = createRequire(path.join(frontend, 'package.json'))('vue')

function component(name, props, exports, extra = {}) {
  const events = [], mounted = [], unmounted = []
  const source = fs.readFileSync(path.join(frontend, 'src/components', name), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
  const scope = vue.effectScope()
  const context = {
    ...vue, structuredClone, console,
    defineProps: () => props, defineEmits: () => (...args) => events.push(args),
    inject: () => null, onMounted: fn => mounted.push(fn),
    onBeforeUnmount: fn => unmounted.push(fn), ...extra,
  }
  vm.createContext(context)
  scope.run(() => vm.runInContext(`${source}\nglobalThis.exposed = {${exports}}`, context))
  return {
    ...context.exposed, events, mounted,
    unmount() { unmounted.forEach(fn => fn()); scope.stop() },
  }
}

async function nativeSubscribe() {
  for (const result of [{success: false, code: 'INVALID_MEDIA'}, {success: false, code: 'PERMISSION_DENIED'}, undefined]) {
    const app = component('RecommendationActions.vue', {
      item: {candidate_id: 'tmdb:movie:1'}, nativeSubscribe: async () => result,
    }, 'handleSubscribe, nativeSubscribeError')
    await app.handleSubscribe()
    assert.equal(app.events.length, 0, 'a rejected request must not create a subscription')
    app.unmount()
  }
  for (const error of [Object.assign(new Error('cancelled'), {code: 'ERR_CANCELED'}), new Error('offline')]) {
    const app = component('RecommendationActions.vue', {
      item: {candidate_id: 'tmdb:movie:1'}, nativeSubscribe: async () => { throw error },
    }, 'handleSubscribe, nativeSubscribeError')
    await app.handleSubscribe()
    assert.equal(app.events.length, 0)
    assert.equal(Boolean(app.nativeSubscribeError.value), error.code !== 'ERR_CANCELED')
    app.unmount()
  }
  for (const callback of [null, async () => ({success: true})]) {
    const app = component('RecommendationActions.vue', {
      item: {candidate_id: 'tmdb:movie:1'}, nativeSubscribe: callback,
    }, 'handleSubscribe')
    await app.handleSubscribe()
    assert.equal(app.events[0][0], callback ? 'native-subscribe-opened' : 'subscribe')
    app.unmount()
  }
}

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return {promise, resolve, reject}
}

async function dashboardLifecycle() {
  for (const fail of [false, true]) {
    const request = deferred(), timers = new Map()
    let nextId = 0, dataRequests = 0
    const state = {
      selectedProfileId: vue.ref('profile-A'), runProgress: vue.ref({active: true}),
      board: vue.ref(null), identities: vue.ref([]), isRunning: vue.ref(true),
      loadRunProgress: () => request.promise,
      loadProfileData: async () => { dataRequests += 1 },
    }
    const app = component('Dashboard.vue', {pluginId: 'AgentRank', config: {}}, 'pollRunProgress', {
      useAgentRankState: () => state,
      window: {setTimeout: fn => {timers.set(++nextId, fn); return nextId}, clearTimeout: id => timers.delete(id)},
    })
    const polling = app.pollRunProgress()
    app.unmount()
    if (fail) request.reject(new Error('offline'))
    else request.resolve({active: false})
    await polling
    assert.equal(timers.size, 0, 'unmount must prevent late responses restarting polling')
    assert.equal(dataRequests, 0, 'unmount must prevent follow-up requests')
  }
  const options = deferred()
  let dataRequests = 0
  const app = component('Dashboard.vue', {config: {}}, 'initialize', {
    useAgentRankState: () => ({loadOptions: () => options.promise, loadProfileData: () => {dataRequests += 1}}),
    window: {clearTimeout() {}},
  })
  const initialized = app.initialize()
  app.unmount(); options.resolve(); await initialized
  assert.equal(dataRequests, 0)
}

async function configDraft() {
  const request = deferred()
  const props = vue.reactive({api: {get() {}}, initialConfig: {cron: 'server-old'}, pluginId: 'AgentRank'})
  const app = component('Config.vue', props, 'form, loadRuntime, applyConfig', {
    getPluginApi: () => request.promise, postPluginApi() {},
  })
  const loading = app.loadRuntime()
  app.form.cron = 'unsaved-draft'
  app.form.emby_library_ids = {home: ['user-selection']}
  request.resolve({config: {cron: 'server-old', history_limit: 33}, emby_identities: []})
  await loading
  assert.equal(app.form.cron, 'unsaved-draft')
  assert.equal(app.form.emby_library_ids.home[0], 'user-selection')
  assert.equal(app.form.history_limit, 33, 'untouched fields should refresh')
  app.applyConfig({cron: 'unsaved-draft', history_limit: 33, emby_library_ids: {home: ['user-selection']}})
  app.applyConfig({cron: 'new-server-value', history_limit: 35, emby_library_ids: {home: ['user-selection']}})
  assert.equal(app.form.cron, 'new-server-value', 'saved drafts should become refreshable')
  app.unmount()

  const late = deferred()
  const otherProps = vue.reactive({api: {get() {}}, initialConfig: {cron: 'before-save'}})
  const other = component('Config.vue', otherProps, 'form, loadRuntime, loading', {getPluginApi: () => late.promise})
  const oldLoad = other.loadRuntime()
  otherProps.initialConfig = {cron: 'confirmed-save'}
  await vue.nextTick()
  late.resolve({config: {cron: 'outdated'}})
  await oldLoad
  assert.equal(other.form.cron, 'confirmed-save', 'old requests must not replace newer props')
  assert.equal(other.loading.value, false)
  other.unmount()
}

function stateHarness(get, post = async () => ({})) {
  const source = fs.readFileSync(path.join(frontend, 'src/components/useAgentRankState.js'), 'utf8')
    .replace(/^import .*$/gm, '').replace('export function useAgentRankState', 'function useAgentRankState')
    .replace('    operations,', '    operations, recordedExposureKeys, pendingFeedbackRequests,')
  const scope = vue.effectScope()
  const context = {...vue, console, getPluginApi: get, postPluginApi: post}
  vm.createContext(context)
  const state = scope.run(() => {
    vm.runInContext(`${source}\nglobalThis.state = useAgentRankState({}, 'AgentRank')`, context)
    return context.state
  })
  state.selectedProfileId.value = 'profile-A'
  return {...state, unmount: () => scope.stop()}
}

async function cacheBounds() {
  let requests = 0
  const state = stateHarness(async (_api, _id, _path, params) => ({candidate_id: params.candidate_id}),
    async () => { requests += 1; return {} })
  for (let index = 0; index < 2000; index += 1) {
    await state.loadAnalysis(`candidate-${index}`, `analysis-${index}`)
  }
  assert.equal(Object.keys(state.analyses).length, 32)
  assert.equal(Object.keys(state.operations).length, 128)
  assert.equal(state.currentAnalysis('candidate-0'), null)
  assert.equal(state.currentAnalysis('candidate-1999').candidate_id, 'candidate-1999')
  for (let index = 0; index < 2000; index += 1) {
    state.board.value = {run_id: `run-${index}`, revision: 1}
    await state.recordBoardExposure([])
  }
  assert.equal(state.recordedExposureKeys.size, 128)
  assert.equal(Object.keys(state.operations).length, 128)
  await state.recordBoardExposure([])
  assert.equal(requests, 2000, 'the current board exposure must remain deduplicated')
  state.selectedProfileId.value = 'profile-B'
  assert.equal(Object.keys(state.analyses).length, 0)
  assert.equal(Object.keys(state.operations).length, 0)
  assert.equal(state.recordedExposureKeys.size, 0)
  state.unmount()
}

async function cacheLifecycle() {
  for (const unmount of [false, true]) {
    const response = deferred()
    const state = stateHarness(() => response.promise)
    const pending = state.loadAnalysis('old-candidate', 'old-analysis')
    if (unmount) state.unmount()
    else state.selectedProfileId.value = 'profile-B'
    response.resolve({candidate_id: 'old-candidate'})
    await pending
    assert.equal(Object.keys(state.analyses).length, 0)
    assert.equal(Object.keys(state.operations).length, 0)
    if (!unmount) state.unmount()
  }
  const held = deferred()
  const state = stateHarness((_api, _id, _path, params) => params.candidate_id === 'held'
    ? held.promise : Promise.resolve({candidate_id: params.candidate_id}))
  const pending = state.loadAnalysis('held', 'held-analysis')
  for (let index = 0; index < 256; index += 1) await state.loadAnalysis(`item-${index}`, 'analysis')
  assert.equal(state.operations['analysis:held'].loading, true, 'active requests must survive eviction')
  held.resolve({candidate_id: 'held'})
  await pending
  assert.equal(state.currentAnalysis('held').candidate_id, 'held')
  state.unmount()
  assert.equal(Object.keys(state.operations).length, 0)
  assert.equal(Object.keys(state.analyses).length, 0)
  assert.equal(await state.loadAnalysis('after-stop', 'analysis'), null)
}

const cases = {native: nativeSubscribe, dashboard: dashboardLifecycle, config: configDraft,
  cache: cacheBounds, cacheLifecycle}
cases[process.argv[2]]().catch(error => { console.error(error); process.exitCode = 1 })
