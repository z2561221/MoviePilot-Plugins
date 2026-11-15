import { useManagementPermissions } from '../useManagementPermissions'
import { rankNames, rankIconColors } from '../rankDisplay'
import { ref, computed, onMounted } from 'vue'
import { getPluginApi, postPluginApi, toPosterThumbnail, openNativeSubscription } from '../api'
import { sourceDescriptor, doubanDispatchUrl } from '../source'
import { useRankMediaActions } from '../useRankMediaActions'
import { useRankDialog } from '../useRankDialog'
import { useRequestScope } from '../useRequestScope'


export function useDashboardRuntime(props) {
  const dashboardPluginId = computed(
    () => String(props.pluginId || props.config?.id || 'DoubanCenter').trim() || 'DoubanCenter',
  )

  const { canManage, permissionError } = useManagementPermissions(() => props.api, () => dashboardPluginId.value)

  const config = ref({})
  const rankHistory = ref({})
  const folioData = ref({})
  const loading = ref(false)
  const folioLoading = ref(false)
  const refreshing = ref(false)
  const subscribeResult = ref('')
  const refreshResult = ref('')
  const loadError = ref('')
  const { dialogItem, showDialog, dialogResolving, dialogResolveError, dialogResolveToken, showActionDialog } = useRankDialog({
    requestScope: () => requestScope,
    resolveRankMedia: (...args) => resolveRankMedia(...args),
    tmdbIdOf: item => tmdbIdOf(item),
  })

  const timelineImageFailed = ref({})
  let loadEpoch = 0
  let rankEpoch = 0
  let refreshEpoch = 0
  let subscribeEpoch = 0
  const requestScope = useRequestScope(() => dashboardPluginId.value, () => {
    loadEpoch += 1
    refreshEpoch += 1
    subscribeEpoch += 1
    dialogResolveToken.value += 1
    loading.value = false
    folioLoading.value = false
    refreshing.value = false
    dialogResolving.value = false
    showDialog.value = false
    subscribeResult.value = ''
    refreshResult.value = ''
  })

  const TIMELINE_MONTH_LIMIT = 3
  const TIMELINE_ITEM_LIMIT = 50
  const INITIAL_LOAD_TIMEOUT_MS = 8000
  const TIMELINE_RETRY_DELAYS_MS = [800, 2500]
  const TIMELINE_RETRY_TIMEOUT_MS = 12000

  function rankColorOf(key) {
    return rankIconColors[key] || rankIconColors.unknown
  }

  function rankIconStyle(key) {
    return { color: rankColorOf(key) }
  }

  function rankNameOf(key, item = null) {
    if (item?.rank_name) return item.rank_name
    const option = (config.value?.rank_options || []).find(entry => entry?.value === key)
    return option?.title || rankNames[key] || key
  }

  const {
    mediaTypeOf,
    normalizeApiData,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  } = useRankMediaActions({
    api: () => props.api,
    pluginId: () => dashboardPluginId.value,
    rankNameOf,
  })

  async function requestFolioData(timeoutMs) {
    const response = await getPluginApi(props.api, dashboardPluginId.value, 'folio_data', { timeoutMs })
    if (response?.success === false) throw new Error(response.message || '追影时间线加载失败')
    return response
  }

  async function loadFolioData() {
    const owner = requestScope.capture()
    const epoch = loadEpoch
    const current = () => owner() && epoch === loadEpoch
    let lastError = null
    for (let attempt = 0; attempt <= TIMELINE_RETRY_DELAYS_MS.length; attempt += 1) {
      if (!current()) return null
      if (attempt > 0) {
        if (!await requestScope.wait(TIMELINE_RETRY_DELAYS_MS[attempt - 1]) || !current()) return null
      }
      try {
        const timeoutMs = attempt === 0 ? INITIAL_LOAD_TIMEOUT_MS : TIMELINE_RETRY_TIMEOUT_MS
        return await requestFolioData(timeoutMs)
      } catch (error) {
        if (!current()) return null
        lastError = error
        if (error?.code === 'PLUGIN_API_TIMEOUT' && attempt > 0) break
      }
    }
    throw lastError || new Error('追影时间线加载失败')
  }

  async function load() {
    if (!requestScope.isActive()) return
    const owner = requestScope.capture()
    const epoch = ++loadEpoch
    const rankRequestEpoch = rankEpoch
    const current = () => owner() && epoch === loadEpoch
    loading.value = true
    folioLoading.value = true
    loadError.value = ''
    const errors = []
    const folioRequest = Promise.allSettled([loadFolioData()])
    const coreRequests = [
      { label: '仪表配置', run: getPluginApi(props.api, dashboardPluginId.value, 'config', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS }) },
      { label: '榜单快照', run: getPluginApi(props.api, dashboardPluginId.value, 'rank_history', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS }) },
    ]
    const coreResults = await Promise.allSettled(coreRequests.map(item => item.run))
    if (!current()) return

    coreResults.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        if (result.value?.success === false) {
          errors.push(coreRequests[index].label)
          return
        }
        const data = normalizeApiData(result.value)
        if (index === 0) config.value = data || {}
        else if (rankRequestEpoch === rankEpoch) rankHistory.value = data || {}
        return
      }
      errors.push(coreRequests[index].label)
      console.error(`[DoubanCenter] ${coreRequests[index].label}加载失败`, result.reason)
    })
    loading.value = false

    const [folioResult] = await folioRequest
    if (!current()) return
    if (folioResult.status === 'fulfilled') {
      if (folioResult.value?.success === false) {
        errors.push('追影时间线')
        } else {
          folioData.value = normalizeApiData(folioResult.value) || {}
          timelineImageFailed.value = {}
        }
    } else {
      errors.push('追影时间线')
      console.error('[DoubanCenter] 追影时间线加载失败', folioResult.reason)
    }
    folioLoading.value = false
    loadError.value = errors.length ? `部分数据加载失败：${errors.join('、')}` : ''
  }

  async function refreshDashboard() {
    if (refreshing.value || !requestScope.isActive()) return
    const owner = requestScope.capture()
    const epoch = ++refreshEpoch
    const current = () => owner() && epoch === refreshEpoch
    refreshing.value = true
    refreshResult.value = ''
    try {
      const res = await postPluginApi(props.api, dashboardPluginId.value, 'refresh_rss', {})
      if (!current()) return
      if (res.success) {
        rankEpoch += 1
        if (res.data) rankHistory.value = res.data
        refreshResult.value = 'RSS 已刷新'
      } else {
        refreshResult.value = res.message || 'RSS 刷新失败'
      }
    } catch (e) {
      if (!current()) return
      refreshResult.value = `刷新失败: ${e}`
    }
    refreshing.value = false
    requestScope.later(() => { if (current()) refreshResult.value = '' }, 3000)
  }


  function markTimelineImageFailed(key) {
    timelineImageFailed.value = { ...timelineImageFailed.value, [key]: true }
  }

  function dialogPoster() {
    const item = dialogItem.value?.item || {}
    return toPosterThumbnail(item.poster || item.poster_path || item.cover)
  }

  async function subscribeViaNativeDialog(rk, item, current) {
    const open = props.nativeSubscribe
    const media = await resolveRankMedia(rk, item)
    if (!current()) return
    await openNativeSubscription(open, media)
    if (!current()) return
    subscribeResult.value = '已打开 MP 原生订阅窗口'
  }

  async function subscribeRankItem(rk, item, current) {
    const res = await requestRankSubscription(rk, item)
    if (!current()) return
    if (!res?.success) throw new Error(res?.message || '订阅失败')
    subscribeResult.value = res?.message || `${item.title || ''} 已添加订阅`
  }

  async function doSubscribe() {
    if (!dialogItem.value || dialogResolving.value) return
    if (!requestScope.isActive()) return
    const owner = requestScope.capture()
    const epoch = ++subscribeEpoch
    const current = () => owner() && epoch === subscribeEpoch
    const { rk, item } = dialogItem.value
    showDialog.value = false
    subscribeResult.value = ''
    try {
      if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item, current)
      else await subscribeRankItem(rk, item, current)
    } catch (e) {
      if (!current()) return
      subscribeResult.value = `订阅失败: ${e?.message || e}`
    }
    if (current()) requestScope.later(() => { if (current()) subscribeResult.value = '' }, 3000)
  }

  function sourceButtonColor() {
    if (!dialogItem.value) return 'primary'
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, config.value).color
  }

  function sourceButtonIcon() {
    if (!dialogItem.value) return 'mdi-link-variant'
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, config.value).icon
  }

  function sourceButtonLabel() {
    if (!dialogItem.value) return '详情'
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, config.value).label
  }

  function sourceButtonUrl() {
    if (!dialogItem.value) return ''
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, config.value).url
  }

  function sourceButtonAppUrl() {
    if (!dialogItem.value) return ''
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, config.value).appUrl || ''
  }

  function sourceButtonHref() {
    const webUrl = sourceButtonUrl()
    return sourceButtonAppUrl() || webUrl
  }

  function openSource(event) {
    const appUrl = sourceButtonAppUrl()
    if (!appUrl) {
      showDialog.value = false
      return
    }
    event?.preventDefault?.()
    showDialog.value = false
    window.open(appUrl, '_blank')
  }

  function doOpenTmdb() {
    if (!dialogItem.value) return
    const { rk, item } = dialogItem.value
    const tmdbId = tmdbIdOf(item)
    if (!tmdbId) return
    const mediaType = mediaTypeOf(rk, item)
    const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`
    showDialog.value = false
    window.open(url, '_blank')
  }

  const timelineGroups = computed(() => {
    const data = folioData.value || {}
    const limitMonth = TIMELINE_MONTH_LIMIT
    const limitNum = TIMELINE_ITEM_LIMIT
    const entries = Object.entries(data)
      .filter(([, v]) => v && typeof v === 'object' && v.timestamp)
      .map(([key, val]) => ({ key, ...val }))
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    const groups = []
    let currentGroup = null
    for (const entry of entries) {
      const d = new Date(entry.timestamp)
      const monthKey = `${d.getFullYear()}-${d.getMonth() + 1}`
      if (!currentGroup || currentGroup.monthKey !== monthKey) {
        if (groups.length >= limitMonth) break
        currentGroup = { monthKey, year: d.getFullYear(), month: d.getMonth() + 1, label: `${d.getFullYear()}年${d.getMonth() + 1}月`, items: [] }
        groups.push(currentGroup)
      }
      if (currentGroup.items.length < limitNum) {
        const poster = toPosterThumbnail(entry.poster_path)
        currentGroup.items.push({ key: entry.key, subject_name: entry.display_title || entry.subject_name || entry.key, subject_id: entry.subject_id, poster, type: entry.type })
      }
    }
    return groups
  })

  onMounted(load)

  return {
    rankColorOf,
    rankIconStyle,
    rankNameOf,
    requestFolioData,
    loadFolioData,
    load,
    refreshDashboard,
    showActionDialog,
    markTimelineImageFailed,
    dialogPoster,
    subscribeViaNativeDialog,
    subscribeRankItem,
    doSubscribe,
    sourceButtonColor,
    sourceButtonIcon,
    sourceButtonLabel,
    sourceButtonUrl,
    sourceButtonAppUrl,
    sourceButtonHref,
    openSource,
    doOpenTmdb,
    dashboardPluginId,
    config,
    rankHistory,
    folioData,
    loading,
    folioLoading,
    refreshing,
    subscribeResult,
    refreshResult,
    loadError,
    dialogItem,
    showDialog,
    dialogResolving,
    dialogResolveError,
    dialogResolveToken,
    timelineImageFailed,
    loadEpoch,
    rankEpoch,
    refreshEpoch,
    subscribeEpoch,
    requestScope,
    TIMELINE_MONTH_LIMIT,
    TIMELINE_ITEM_LIMIT,
    INITIAL_LOAD_TIMEOUT_MS,
    TIMELINE_RETRY_DELAYS_MS,
    TIMELINE_RETRY_TIMEOUT_MS,
    timelineGroups,
    canManage,
    permissionError,
    mediaTypeOf,
    normalizeApiData,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  }
}
