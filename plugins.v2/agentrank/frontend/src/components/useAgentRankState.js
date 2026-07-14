import { computed, reactive, ref } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const OPTIONS_CACHE_TTL_MS = 5 * 60 * 1000
const USER_CACHE_TTL_MS = 60 * 1000
const cacheByApi = new WeakMap()
const fallbackCache = createSharedCache()

function createSharedCache() {
  return {
    options: null,
    optionsUpdatedAt: 0,
    optionsRequest: null,
    users: new Map(),
  }
}

function sharedCacheFor(api) {
  if (!api || !['object', 'function'].includes(typeof api)) return fallbackCache
  if (!cacheByApi.has(api)) cacheByApi.set(api, createSharedCache())
  return cacheByApi.get(api)
}

function isFresh(updatedAt, ttl) {
  return updatedAt > 0 && Date.now() - updatedAt < ttl
}

function emptyBoard(username) {
  return {
    username,
    run_id: '',
    status: 'idle',
    recommendations: [],
    generated_at: '',
    message: '尚未生成榜单',
  }
}

function emptyProfile(username) {
  return {
    username,
    summary: '',
    tags: [],
    negative_tags: [],
    subscription_count: 0,
    run_id: '',
    generated_at: '',
  }
}

/**
 * 统一管理 AgentRank 用户选择、只读数据与变更动作。
 */
export function useAgentRankState(api) {
  const sharedCache = sharedCacheFor(api)
  const options = ref({ users: [], available_users: [], default_user: '', config: {} })
  const selectedUser = ref('')
  const overview = ref(null)
  const board = ref(null)
  const profile = ref(null)
  const history = ref([])
  const historyMeta = ref({ total: 0, page: 1, page_size: 15 })
  const loading = reactive({ options: false, data: false, action: '' })
  const error = ref(null)
  const feedback = ref(null)

  const users = computed(() => options.value.users || [])
  const isRunning = computed(() => board.value?.status === 'running' || loading.action === 'refresh')

  function applyOptions(value) {
    options.value = value || options.value
    const candidates = options.value.users || []
    if (!candidates.includes(selectedUser.value)) {
      selectedUser.value = options.value.default_user || candidates[0] || ''
    }
    return options.value
  }

  function fetchOptions() {
    if (!sharedCache.optionsRequest) {
      sharedCache.optionsRequest = getPluginApi(api, 'config/options')
        .then(value => {
          sharedCache.options = value
          sharedCache.optionsUpdatedAt = Date.now()
          return value
        })
        .finally(() => { sharedCache.optionsRequest = null })
    }
    return sharedCache.optionsRequest
  }

  async function loadOptions({ force = false } = {}) {
    const cached = sharedCache.options
    if (cached) {
      applyOptions(cached)
      if (!force) {
        if (!isFresh(sharedCache.optionsUpdatedAt, OPTIONS_CACHE_TTL_MS)) {
          void fetchOptions().then(applyOptions).catch(() => {})
        }
        return cached
      }
    }
    loading.options = !cached
    error.value = null
    try {
      return applyOptions(await fetchOptions())
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.options = false
    }
  }

  function userCacheEntry(username) {
    if (!sharedCache.users.has(username)) {
      sharedCache.users.set(username, { value: null, updatedAt: 0, request: null })
    }
    return sharedCache.users.get(username)
  }

  function applyUserData(data, username) {
    const overviewData = data || { username }
    const recentHistory = Array.isArray(overviewData.history)
      ? overviewData.history
      : overviewData.latest_run ? [overviewData.latest_run] : []
    overview.value = overviewData
    board.value = overviewData.board || emptyBoard(username)
    profile.value = overviewData.profile || emptyProfile(username)
    history.value = recentHistory
    historyMeta.value = {
      total: Number(overviewData.history_total ?? recentHistory.length),
      page: 1,
      page_size: 15,
    }
    return overviewData
  }

  function fetchUserData(username, entry) {
    if (!entry.request) {
      entry.request = getPluginApi(api, 'overview', { username })
        .then(value => {
          entry.value = value
          entry.updatedAt = Date.now()
          return value
        })
        .finally(() => { entry.request = null })
    }
    return entry.request
  }

  async function loadUserData(username = selectedUser.value, { force = false } = {}) {
    if (!username) return null
    const entry = userCacheEntry(username)
    const cached = entry.value
    if (cached) {
      applyUserData(cached, username)
      if (!force) {
        if (!isFresh(entry.updatedAt, USER_CACHE_TTL_MS)) {
          void fetchUserData(username, entry)
            .then(value => {
              if (selectedUser.value === username) applyUserData(value, username)
            })
            .catch(() => {})
        }
        return cached
      }
    }
    loading.data = !cached
    error.value = null
    try {
      return applyUserData(await fetchUserData(username, entry), username)
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.data = false
    }
  }

  async function loadHistory(page = 1, pageSize = 15) {
    if (!selectedUser.value) return []
    const result = await getPluginApi(api, 'run-history', {
      username: selectedUser.value,
      page,
      page_size: pageSize,
    })
    history.value = result?.items || []
    historyMeta.value = {
      total: result?.total || 0,
      page: result?.page || page,
      page_size: result?.page_size || pageSize,
    }
    return history.value
  }

  async function runAction(path, payload, label) {
    if (loading.action) return null
    loading.action = path
    error.value = null
    feedback.value = null
    try {
      const result = await postPluginApi(api, path, payload)
      feedback.value = { ok: true, message: `${label}已完成`, result }
      return result
    } catch (err) {
      error.value = err
      feedback.value = { ok: false, message: err?.message || `${label}失败` }
      throw err
    } finally {
      loading.action = ''
    }
  }

  async function refresh() {
    const result = await runAction('refresh', { username: selectedUser.value }, '刷新')
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  async function archive(candidateId) {
    const result = await runAction(
      'archive',
      { username: selectedUser.value, candidate_id: candidateId },
      '忽略',
    )
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  async function restore(candidateId) {
    const result = await runAction(
      'restore',
      { username: selectedUser.value, candidate_id: candidateId },
      '恢复',
    )
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  async function deleteArchive(candidateId) {
    const result = await runAction(
      'archive/delete',
      { username: selectedUser.value, candidate_id: candidateId },
      '删除归档',
    )
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  async function clearProfile() {
    const result = await runAction(
      'profile/clear',
      { username: selectedUser.value, confirm: true },
      '清除画像',
    )
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  async function subscribe(candidateId) {
    const result = await runAction(
      'subscribe',
      { username: selectedUser.value, candidate_id: candidateId },
      '订阅',
    )
    await loadUserData(selectedUser.value, { force: true })
    return result
  }

  return {
    options,
    users,
    selectedUser,
    overview,
    board,
    profile,
    history,
    historyMeta,
    loading,
    error,
    feedback,
    isRunning,
    loadOptions,
    loadUserData,
    loadHistory,
    refresh,
    archive,
    restore,
    deleteArchive,
    clearProfile,
    subscribe,
  }
}
