import assert from 'node:assert/strict'
import { apiGet, apiPost, isStandardEnvelope, unwrapResponse } from '../../../plugins.v3/localtoolkit/frontend/src/api.js'

const bare = { enabled: true, modules: { tmdb_cache: { keys: 3 } } }
const standard = { success: true, message: '', data: { total: 2 } }
const custom = { success: true, message: '', data: { total: 2 }, meta: { source: 'plugin' } }

assert.equal(isStandardEnvelope(standard), true)
assert.equal(isStandardEnvelope(custom), false)
assert.deepEqual(unwrapResponse(bare), bare)
assert.deepEqual(unwrapResponse(custom), custom)
assert.deepEqual(unwrapResponse(standard), standard.data)
assert.throws(
  () => unwrapResponse({ success: false, message: 'failed', data: null }),
  /failed/,
)

const api = {
  async get(path) {
    return path === 'bare' ? bare : standard
  },
  async post(path) {
    return path === 'bare' ? bare : standard
  },
}

assert.deepEqual(await apiGet(api, 'bare'), bare)
assert.deepEqual(await apiGet(api, 'standard'), standard.data)
assert.deepEqual(await apiPost(api, 'bare'), bare)
assert.deepEqual(await apiPost(api, 'standard'), {
  ...standard.data,
  success: true,
  message: '',
})

console.log('LOCALTOOLKIT_FRONTEND_API_CONTRACT_OK')
