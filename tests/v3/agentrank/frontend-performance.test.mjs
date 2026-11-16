/* Exercise the actual shared state with Vue scopes and controlled host API calls. */
import assert from 'node:assert/strict'
import test from 'node:test'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { useAgentRankState } from '../../../plugins.v3/agentrank/frontend/src/components/useAgentRankState.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(__dirname, '../../../plugins.v3/agentrank/frontend')
const requireFrontend = createRequire(path.join(frontend, 'package.json'))
const vue = requireFrontend('vue')

function harness() {
  const requests = []
  let version = 1
  let feedbackKind = ''
  const api = {
    async get(url, { params }) {
      const route = url.split('/').slice(2).join('/')
      requests.push({route, params})
      if (route === 'config/options') return {
        emby_identities: [{profile_id: 'profile-A', username: 'Alice'}],
        default_profile_id: 'profile-A', config: {agent_display_name: 'Review'},
      }
      const board = {
        profile_id: 'profile-A', run_id: `run-${version}`, revision: 1,
        recommendations: [{candidate_id: 'candidate', feedback_kind: feedbackKind}],
      }
      if (route === 'board') return board
      if (route === 'overview') return {profile_id: 'profile-A', board, profile: {tags: ['keep']}, history: []}
      throw new Error(`unexpected request ${route}`)
    },
    async post(url, payload) {
      if (url.endsWith('/feedback')) {
        feedbackKind = payload.kind === 'neutral' ? '' : payload.kind
        return {board_changed: false, board_revision: 1, event: {kind: payload.kind}}
      }
      version += 1
      return {changed: true}
    },
  }
  const scopes = []
  function state(boardOnly, pluginId = 'AgentRank') {
    const scope = vue.effectScope()
    scopes.push(scope)
    return scope.run(() => useAgentRankState(api, pluginId, {boardOnly}))
  }
  return {api, requests, state, stop: () => scopes.forEach(scope => scope.stop())}
}

test('dashboard uses lightweight options and board without requesting overview', async () => {
  const app = harness()
  try {
    const state = app.state(true)
    await state.loadOptions()
    await state.loadProfileData()
    assert.deepEqual(app.requests.map(item => item.route), ['config/options', 'board'])
    assert.equal(app.requests[0].params.discover, false)
    assert.equal(state.board.value.run_id, 'run-1')
    assert.deepEqual(state.profile.value.tags, [])
    assert.equal(state.overview.value, null)
  } finally { app.stop() }
})

test('board and overview caches stay distinct and mutations invalidate both', async () => {
  const app = harness()
  try {
    const dashboard = app.state(true), page = app.state(false)
    await Promise.all([dashboard.loadOptions(), page.loadOptions()])
    assert.equal(app.requests.filter(item => item.route === 'config/options').length, 1)
    await Promise.all([dashboard.loadProfileData(), page.loadProfileData()])
    assert.equal(page.profile.value.tags[0], 'keep')
    assert.equal(app.requests.filter(item => item.route === 'board').length, 1)
    assert.equal(app.requests.filter(item => item.route === 'overview').length, 1)
    await dashboard.subscribe('candidate')
    assert.equal(app.requests.at(-1).route, 'board')
    assert.equal(dashboard.board.value.run_id, 'run-2')
    await page.loadProfileData()
    // Expired cache renders immediately and refreshes in the background.
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(page.board.value.run_id, 'run-2')
    assert.equal(app.requests.filter(item => item.route === 'overview').length, 2)
    const clone = app.state(true, 'AgentRankClone')
    await clone.loadOptions()
    await clone.loadProfileData()
    assert.equal(app.requests.filter(item => item.route === 'config/options').length, 2)
  } finally { app.stop() }
})

test('concurrent dashboard readers share the same pending board request', async () => {
  const app = harness()
  try {
    const first = app.state(true), second = app.state(true)
    await Promise.all([first.loadOptions(), second.loadOptions()])
    await Promise.all([first.loadProfileData(), second.loadProfileData()])
    assert.equal(app.requests.filter(item => item.route === 'board').length, 1)
  } finally { app.stop() }
})

test('local feedback invalidates both views without an immediate overview reload', async () => {
  for (const fromDashboard of [true, false]) {
    const app = harness()
    try {
      const dashboard = app.state(true), page = app.state(false)
      await Promise.all([dashboard.loadOptions(), page.loadOptions()])
      await Promise.all([dashboard.loadProfileData(), page.loadProfileData()])
      const initiator = fromDashboard ? dashboard : page
      const other = fromDashboard ? page : dashboard
      const before = app.requests.length
      await initiator.reactToRecommendation('like', 'candidate')
      assert.equal(app.requests.length, before)
      assert.equal(initiator.board.value.recommendations[0].feedback_kind, 'like')
      await other.loadProfileData()
      await new Promise(resolve => setImmediate(resolve))
      assert.equal(other.board.value.recommendations[0].feedback_kind, 'like')
      assert.equal(app.requests.length, before + 1)
    } finally { app.stop() }
  }
})

test('an overview response started before feedback cannot repopulate stale cache', {timeout: 3000}, async () => {
  const app = harness()
  let release
  try {
    const dashboard = app.state(true), page = app.state(false)
    await Promise.all([dashboard.loadOptions(), page.loadOptions()])
    await Promise.all([dashboard.loadProfileData(), page.loadProfileData()])
    const get = app.api.get.bind(app.api)
    const held = new Promise(resolve => { release = resolve })
    let delayed = false
    app.api.get = async (url, options) => {
      const value = await get(url, options)
      if (url.endsWith('/overview') && !delayed) {
        delayed = true
        await held
      }
      return value
    }
    const pending = page.loadProfileData('profile-A', {force: true})
    await new Promise(resolve => setImmediate(resolve))
    await dashboard.reactToRecommendation('like', 'candidate')
    release()
    await pending
    assert.equal(page.board.value.recommendations[0].feedback_kind, 'like')
    assert.equal(app.requests.filter(item => item.route === 'overview').length, 3)
  } finally { release?.(); app.stop() }
})
