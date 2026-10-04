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

const cases = {native: nativeSubscribe}
cases[process.argv[2]]().catch(error => { console.error(error); process.exitCode = 1 })
