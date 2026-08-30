import { reactive, ref } from 'vue'
import { getPluginApi, postPluginApi, toPosterThumbnail } from '../api'
import { sourceDescriptor } from '../source'
import { useRankMediaActions } from '../useRankMediaActions'

const INITIAL_LOAD_TIMEOUT_MS = 8000

const rankNames = {
  coming: '即将上映',
  tv_real_time: '实时热门',
  tv_chinese: '华语口碑',
  tv_global: '全球口碑',
  movie_weekly: '电影口碑',
  bangumi: 'BangumiTV',
  douban_wish: '豆瓣想看',
  unknown: '未归类',
}

const rankIconColors = {
  coming: '#f97316',
  tv_real_time: '#06b6d4',
  tv_chinese: '#eab308',
  tv_global: '#ef4444',
  movie_weekly: '#ec4899',
  bangumi: '#8b5cf6',
  douban_wish: '#10b981',
  unknown: '#94a3b8',
}

export function usePageRuntime({ api, pluginId, nativeSubscribe }) {
  const loading = ref(false)
  const stats = ref(null)
  const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
  const archiveData = ref({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 })
  const archivePage = ref(false)
  const cheatLogs = ref([])
  const pendingObservations = ref([])
  const rankHistory = ref({})
  const configData = ref({})
  const blacklistKeywords = ref([])
  const blacklistEntries = ref([])
  const actionKey = ref('')
  const actionMessage = ref('')
  const actionOk = ref(true)
  const loadError = ref('')
  const dialogItem = ref(null)
  const showDialog = ref(false)
  const dialogResolving = ref(false)
  const dialogResolveError = ref('')
  const dialogResolveToken = ref(0)

  function rankColorOf(key) {
    return rankIconColors[key] || rankIconColors.unknown
  }

  function rankIconStyle(key) {
    return { color: rankColorOf(key) }
  }

  function rankNameOf(key, item = null) {
    if (item?.rank_name) return item.rank_name
    const option = (configData.value?.rank_options || []).find(entry => entry?.value === key)
    return option?.title || rankNames[key] || key
  }

  function rankChipStyle(key) {
    const color = rankColorOf(key)
    return { color, backgroundColor: `${color}1f`, borderColor: `${color}73` }
  }

  function rowKey(prefix, item, index) {
    return `${prefix}:${item?.id || item?.unique || item?.time || item?.tmdbid || item?.title || index}`
  }

  function archiveRecord(item) {
    return item?.record && typeof item.record === 'object' ? item.record : {}
  }

  function archiveSourceName(item) {
    return item?.source_name || item?.source || '归档'
  }

  function archivePoster(item) {
    const record = archiveRecord(item)
    return toPosterThumbnail(item?.poster || record.poster || record.cover)
  }

  function archiveRankKey(item) {
    const record = archiveRecord(item)
    return item?.rank_key || record.rank_key || ''
  }

  function archiveRankName(item) {
    const key = archiveRankKey(item)
    const record = archiveRecord(item)
    return item?.rank_name || record.rank_name || rankNameOf(key, record) || key
  }

  function archiveTime(item) {
    const record = archiveRecord(item)
    return item?.time || record.time || record.first_seen || item?.archived_at || ''
  }

  function archiveTitle(item) {
    const record = archiveRecord(item)
    return item?.title || record.title || '未命名条目'
  }

  function archiveStatus(item) {
    const record = archiveRecord(item)
    return item?.display_status || record.display_status || record.detail || item?.detail || record.reason || item?.reason || archiveSourceName(item)
  }

  function archiveColor(item) {
    const source = item?.source || ''
    const reason = item?.reason || archiveRecord(item).reason || ''
    if (archiveSourceName(item) === '黑名拦截' || reason === '黑名拦截') return 'error'
    if (source === 'subscribe_history') return archiveStatus(item) === '订阅失败' ? 'error' : 'success'
    if (source === 'observation' || source === 'anti_cheat_log') return 'warning'
    return 'primary'
  }

  function archiveIcon(item) {
    const source = item?.source || ''
    const reason = item?.reason || archiveRecord(item).reason || ''
    if (archiveSourceName(item) === '黑名拦截' || reason === '黑名拦截') return 'mdi-block-helper'
    if (source === 'observation') return 'mdi-clock-outline'
    if (source === 'subscribe_history') return 'mdi-filmstrip'
    if (source === 'anti_cheat_log') return 'mdi-eye-check-outline'
    return 'mdi-archive-outline'
  }

  const {
    mediaTypeOf,
    normalizeApiData,
    queryString,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  } = useRankMediaActions({ api, pluginId, rankNameOf })

  async function loadAll() {
    loading.value = true
    loadError.value = ''
    const requests = [
      { label: '订阅统计', path: 'stats', apply: value => { if (value) stats.value = value } },
      {
        label: '订阅历史',
        path: `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`,
        apply: value => { if (value) historyData.value = value },
      },
      { label: '观察日志', path: 'anti_cheat_logs', apply: value => {
        if (value) {
          const logs = Array.isArray(value) ? value : []
          cheatLogs.value = logs.filter(log => !log || !['黑名拦截', '黑名单关键词'].includes(log.reason)).slice(-5)
          blacklistEntries.value = logs.filter(log => log && ['黑名拦截', '黑名单关键词'].includes(log.reason)).slice().reverse().slice(0, 5)
        }
      } },
      { label: '观察队列', path: 'pending_observations', apply: value => { if (value) pendingObservations.value = value } },
      { label: '榜单快照', path: 'rank_history', apply: value => { if (value) rankHistory.value = value } },
      { label: '运行配置', path: 'config', apply: value => {
        if (value) {
          configData.value = value
          blacklistKeywords.value = String(value.blacklist_keywords || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean)
        }
      } },
    ]
    const results = await Promise.allSettled(requests.map(async request => {
      const response = await getPluginApi(api(), pluginId(), request.path, { timeoutMs: INITIAL_LOAD_TIMEOUT_MS })
      if (response?.success === false) throw new Error(response.message || `${request.label}加载失败`)
      request.apply(normalizeApiData(response))
    }))
    const failed = []
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        failed.push(requests[index].label)
        console.error(`[DoubanCenter] ${requests[index].label}加载失败`, result.reason)
      }
    })
    loadError.value = failed.length ? `部分数据加载失败：${failed.join('、')}` : ''
    loading.value = false
  }

  async function loadArchive() {
    loading.value = true
    loadError.value = ''
    try {
      const fetchPage = async page => {
        const response = await getPluginApi(api(), pluginId(), `archive_records?page=${page}&page_size=${archiveData.value.page_size}`, { timeoutMs: INITIAL_LOAD_TIMEOUT_MS })
        if (response?.success === false) throw new Error(response.message || '归档记录加载失败')
        return normalizeApiData(response)
      }
      let data = await fetchPage(archiveData.value.page)
      const lastPage = Math.max(Number(data?.total_pages) || 0, 1)
      if ((Number(data?.page) || 1) > lastPage) data = await fetchPage(lastPage)
      if (data) archiveData.value = data
    } catch (error) {
      loadError.value = '归档记录加载失败'
      console.error('[DoubanCenter] 归档记录加载失败', error)
    } finally {
      loading.value = false
    }
  }

  async function openArchivePage() {
    archivePage.value = true
    await loadArchive()
  }

  function closeArchivePage() {
    archivePage.value = false
  }

  async function goPage(page) {
    if (page < 1 || page > historyData.value.total_pages) return
    historyData.value.page = page
    await loadAll()
  }

  async function goArchivePage(page) {
    if (page < 1 || page > archiveData.value.total_pages || page === archiveData.value.page) return
    archiveData.value.page = page
    await loadArchive()
  }

  async function runDelete(path, body, key, successText) {
    if (actionKey.value) return
    actionKey.value = key
    actionMessage.value = ''
    actionOk.value = true
    try {
      const qs = queryString(body)
      const response = await postPluginApi(api(), pluginId(), qs ? `${path}?${qs}` : path, {})
      actionOk.value = !!response?.success
      actionMessage.value = response?.message || (actionOk.value ? successText : '操作失败')
      if (archivePage.value) await loadArchive()
      else await loadAll()
    } catch (error) {
      actionOk.value = false
      actionMessage.value = error?.message || '操作失败'
    } finally {
      actionKey.value = ''
    }
  }

  async function deleteObservation(item, index) {
    await runDelete('delete_observation', { unique: item?.unique || '', rank_key: item?.rank_key || '', title: item?.title || '' }, rowKey('obs', item, index), '已删除观察条目')
  }

  async function deleteSubscribeHistory(item, index) {
    await runDelete('delete_subscribe_history', {
      time: item?.time || '',
      title: item?.title || '',
      media_source: item?.media_source || '',
      media_id: item?.media_id || '',
      tmdbid: item?.tmdbid || '',
    }, rowKey('sub', item, index), '已删除订阅历史')
  }

  async function deleteAntiCheatLog(item, index) {
    await runDelete('delete_anti_cheat_log', { time: item?.time || '', title: item?.title || '', reason: item?.reason || '' }, rowKey('log', item, index), '已删除观察日志')
  }

  async function restoreArchive(item, index) {
    await runDelete('restore_archive', { archive_id: item?.id || '' }, rowKey('archive-restore', item, index), '已恢复归档记录')
  }

  async function deleteArchive(item, index) {
    await runDelete('delete_archive', { archive_id: item?.id || '' }, rowKey('archive-delete', item, index), '已删除归档记录')
  }

  async function showActionDialog(rk, item) {
    const token = ++dialogResolveToken.value
    dialogItem.value = { rk, item: { ...(item || {}) } }
    dialogResolveError.value = ''
    showDialog.value = true
    if (tmdbIdOf(item)) return
    dialogResolving.value = true
    try {
      const media = await resolveRankMedia(rk, item)
      if (token !== dialogResolveToken.value) return
      dialogItem.value = { rk, item: media }
      if (!tmdbIdOf(media)) dialogResolveError.value = '未找到对应的 TMDB 条目'
    } catch (error) {
      if (token === dialogResolveToken.value) dialogResolveError.value = error?.message || 'TMDB 识别失败'
    } finally {
      if (token === dialogResolveToken.value) dialogResolving.value = false
    }
  }

  function dialogPoster() {
    const item = dialogItem.value?.item || {}
    return toPosterThumbnail(item.poster || item.poster_path || item.cover)
  }

  async function subscribeViaNativeDialog(rk, item) {
    const media = await resolveRankMedia(rk, item)
    await nativeSubscribe()(media)
    actionOk.value = true
    actionMessage.value = '已打开 MP 原生订阅窗口'
  }

  async function subscribeRankItem(rk, item) {
    const response = await requestRankSubscription(rk, item)
    if (!response?.success) throw new Error(response?.message || '订阅失败')
    actionOk.value = true
    actionMessage.value = response?.message || `${item.title || ''} 已添加订阅`
    await loadAll()
  }

  async function doSubscribe() {
    if (!dialogItem.value || dialogResolving.value) return
    const { rk, item } = dialogItem.value
    showDialog.value = false
    actionMessage.value = ''
    actionOk.value = true
    try {
      if (nativeSubscribe()) await subscribeViaNativeDialog(rk, item)
      else await subscribeRankItem(rk, item)
    } catch (error) {
      actionOk.value = false
      actionMessage.value = `订阅失败: ${error?.message || error}`
    }
  }

  function sourceButtonDescriptor() {
    if (!dialogItem.value) return { color: 'primary', icon: 'mdi-link-variant', label: '详情', url: '', appUrl: '' }
    const { rk, item } = dialogItem.value
    return sourceDescriptor(rk, item, configData.value)
  }

  function sourceButtonColor() {
    return sourceButtonDescriptor().color
  }

  function sourceButtonIcon() {
    return sourceButtonDescriptor().icon
  }

  function sourceButtonLabel() {
    return sourceButtonDescriptor().label
  }

  function sourceButtonUrl() {
    return sourceButtonDescriptor().url
  }

  function sourceButtonAppUrl() {
    return sourceButtonDescriptor().appUrl || ''
  }

  function sourceButtonHref() {
    return sourceButtonAppUrl() || sourceButtonUrl()
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

  return reactive({
    loading, stats, historyData, archiveData, archivePage, cheatLogs, pendingObservations,
    rankHistory, blacklistKeywords, blacklistEntries, actionKey, actionMessage, actionOk,
    loadError, dialogItem, showDialog, dialogResolving, dialogResolveError,
    rankColorOf, rankIconStyle, rankNameOf, rankChipStyle, rowKey, archiveSourceName,
    archivePoster, archiveRankKey, archiveRankName, archiveTime, archiveTitle, archiveStatus,
    archiveColor, archiveIcon, loadAll, loadArchive, openArchivePage, closeArchivePage,
    goPage, goArchivePage, deleteObservation, deleteSubscribeHistory, deleteAntiCheatLog,
    restoreArchive, deleteArchive, showActionDialog, dialogPoster, doSubscribe,
    sourceButtonColor, sourceButtonIcon, sourceButtonLabel, sourceButtonUrl, sourceButtonHref,
    openSource, doOpenTmdb, tmdbIdOf, toPosterThumbnail,
  })
}
