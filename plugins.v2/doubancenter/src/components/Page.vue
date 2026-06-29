<script setup>
import { ref, onMounted } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['close', 'switch'])

const loading = ref(false)
const stats = ref(null)
const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
const archiveData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
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
const dialogItem = ref(null)
const showDialog = ref(false)

const rankColors = {
  coming: 'primary',
  tv_real_time: 'teal',
  tv_chinese: 'orange-darken-1',
  tv_global: 'deep-purple',
  movie_weekly: 'pink',
  bangumi: 'brown',
  unknown: 'grey',
}
const rankNames = {
  coming: '即将上映',
  tv_real_time: '实时热门',
  tv_chinese: '华语口碑',
  tv_global: '全球口碑',
  movie_weekly: '电影口碑',
  bangumi: 'BangumiTV',
  unknown: '未归类',
}

function queryString(params) {
  return Object.entries(params || {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}

function normalizeApiData(value) {
  if (value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, 'success')) return value
  return value?.data && !Array.isArray(value?.data) ? value.data : value
}

function rowKey(prefix, item, index) {
  return `${prefix}:${item?.id || item?.unique || item?.time || item?.tmdbid || item?.title || index}`
}

function mediaIdOf(media) {
  if (media?.tmdb_id) return `tmdb:${media.tmdb_id}`
  if (media?.douban_id) return `douban:${media.douban_id}`
  if (media?.bangumi_id) return `bangumi:${media.bangumi_id}`
  if (media?.media_id && media?.mediaid_prefix) return `${media.mediaid_prefix}:${media.media_id}`
  return ''
}

function bangumiIdOf(rk, item) {
  if (item?.bangumi_id || item?.bangumiid) return item.bangumi_id || item.bangumiid
  if (rk === 'bangumi' && item?.douban_id) return item.douban_id
  const match = String(item?.link || '').match(/(?:bgm\.tv|bangumi\.tv)\/subject\/(\d+)/)
  return match ? match[1] : ''
}

function mediaTypeOf(rk, item) {
  const type = item?.media_type || item?.mtype || item?.type || ''
  if (type === '电影' || type === 'movie') return 'movie'
  if (type === '电视剧' || type === 'tv') return 'tv'
  return rk === 'movie_weekly' ? 'movie' : 'tv'
}

async function resolveRankMedia(rk, item) {
  const mediaType = mediaTypeOf(rk, item)
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  })
  const res = normalizeApiData(await getPluginApi(props.api, `resolve_media?${params}`))
  if (res?.success === false) throw new Error(res?.message || '媒体识别失败')
  const media = res?.data && !Array.isArray(res.data) ? res.data : res
  if (!media || typeof media !== 'object') throw new Error('媒体识别失败')
  const merged = { ...item, ...media }
  merged.title = media.title || media.name || item?.title || item?.name || ''
  merged.name = media.name || media.title || item?.name || item?.title || ''
  merged.year = media.year || item?.year || ''
  merged.type = media.type || (mediaType === 'movie' ? '电影' : '电视剧')
  merged.tmdb_id = media.tmdb_id || media.tmdbid || item?.tmdb_id || item?.tmdbid || null
  merged.tmdbid = media.tmdbid || media.tmdb_id || item?.tmdbid || item?.tmdb_id || null
  merged.douban_id = media.douban_id || media.doubanid || item?.douban_id || item?.doubanid || null
  merged.doubanid = media.doubanid || media.douban_id || item?.doubanid || item?.douban_id || null
  merged.bangumi_id = media.bangumi_id || media.bangumiid || bangumiIdOf(rk, item) || null
  merged.bangumiid = media.bangumiid || media.bangumi_id || bangumiIdOf(rk, item) || null
  if (!merged.mediaid_prefix || !merged.media_id) {
    const mediaId = mediaIdOf(merged)
    if (mediaId) {
      const [prefix, id] = mediaId.split(':')
      merged.mediaid_prefix = merged.mediaid_prefix || prefix
      merged.media_id = merged.media_id || id
    }
  }
  return merged
}

async function loadAll() {
  loading.value = true
  try {
    const [s, h, c, p, r, cfg, a] = await Promise.all([
      getPluginApi(props.api, 'stats'),
      getPluginApi(props.api, `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`),
      getPluginApi(props.api, 'anti_cheat_logs'),
      getPluginApi(props.api, 'pending_observations'),
      getPluginApi(props.api, 'rank_history'),
      getPluginApi(props.api, 'config'),
      getPluginApi(props.api, `archive_records?page=${archiveData.value.page}&page_size=${archiveData.value.page_size}`),
    ])
    if (s) stats.value = s
    if (h) historyData.value = h
    if (c) {
      const logs = Array.isArray(c) ? c : []
      cheatLogs.value = logs.filter(log => !log || log.reason !== '黑名单关键词').slice(-5)
      blacklistEntries.value = logs.filter(log => log && log.reason === '黑名单关键词').slice().reverse().slice(0, 5)
    }
    if (p) pendingObservations.value = p
    if (r) rankHistory.value = r
    if (cfg) {
      configData.value = cfg
      blacklistKeywords.value = String(cfg.blacklist_keywords || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean)
    }
    if (a) archiveData.value = a
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function goPage(p) {
  if (p < 1 || p > historyData.value.total_pages) return
  historyData.value.page = p
  await loadAll()
}

async function loadArchive() {
  const data = await getPluginApi(props.api, `archive_records?page=${archiveData.value.page}&page_size=${archiveData.value.page_size}`)
  if (data) archiveData.value = data
}

async function openArchivePage() {
  archivePage.value = true
  await loadArchive()
}

function closeArchivePage() {
  archivePage.value = false
}

async function runDelete(path, body, key, successText) {
  if (actionKey.value) return
  actionKey.value = key
  actionMessage.value = ''
  actionOk.value = true
  try {
    const qs = queryString(body)
    const res = await postPluginApi(props.api, qs ? `${path}?${qs}` : path, {})
    actionOk.value = !!(res && res.success)
    actionMessage.value = (res && res.message) || (actionOk.value ? successText : '操作失败')
    await loadAll()
  } catch (e) {
    actionOk.value = false
    actionMessage.value = e?.message || '操作失败'
  } finally {
    actionKey.value = ''
  }
}

async function deleteObservation(item, index) {
  await runDelete('delete_observation', { unique: item?.unique || '', rank_key: item?.rank_key || '', title: item?.title || '' }, rowKey('obs', item, index), '已删除观察条目')
}

async function deleteSubscribeHistory(item, index) {
  await runDelete('delete_subscribe_history', { time: item?.time || '', title: item?.title || '', tmdbid: item?.tmdbid || '' }, rowKey('sub', item, index), '已删除订阅历史')
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

function showActionDialog(rk, item) {
  dialogItem.value = { rk, item }
  showDialog.value = true
}

async function subscribeViaNativeDialog(rk, item) {
  const media = await resolveRankMedia(rk, item)
  await props.nativeSubscribe(media)
  actionOk.value = true
  actionMessage.value = '已打开 MP 原生订阅窗口'
}

async function subscribeRankItem(rk, item) {
  const mediaType = mediaTypeOf(rk, item)
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  })
  const res = await postPluginApi(props.api, `subscribe?${params}`, {})
  if (!res?.success) throw new Error(res?.message || '订阅失败')
  actionOk.value = true
  actionMessage.value = res?.message || `${item.title || ''} 已添加订阅`
  await loadAll()
}

async function doSubscribe() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value
  showDialog.value = false
  actionMessage.value = ''
  actionOk.value = true
  try {
    if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item)
    else await subscribeRankItem(rk, item)
  } catch (e) {
    actionOk.value = false
    actionMessage.value = `订阅失败: ${e?.message || e}`
  }
}

function doOpenSource() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value
  showDialog.value = false
  const link = item?.link || ''
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) {
    if (link) window.open(link, '_blank')
    return
  }
  const subjectId = item?.douban_id || item?.doubanid || ''
  if (subjectId) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${subjectId}?from=mdouban&open=app`, '_blank')
    return
  }
  const match = link.match(/subject\/(\d+)/)
  if (match && (link.includes('douban.com') || link.includes('doubanapp'))) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${match[1]}?from=mdouban&open=app`, '_blank')
    return
  }
  if (link) window.open(link, '_blank')
}

function sourceButtonColor() {
  if (!dialogItem.value) return 'primary'
  const { rk, item } = dialogItem.value
  const link = String(item?.link || '')
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) return '#F838A0'
  if (link.includes('douban') || item?.douban_id || item?.doubanid) return '#08B810'
  return 'primary'
}

function doOpenTmdb() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value
  const tmdbId = item?.tmdbid || item?.tmdb_id || ''
  if (!tmdbId) return
  const mediaType = mediaTypeOf(rk, item)
  const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`
  showDialog.value = false
  window.open(url, '_blank')
}

onMounted(loadAll)
</script>

<template>
  <VCard flat class="dc-page">
    <VCardItem class="dc-page-header">
      <template #prepend>
        <VAvatar color="primary" variant="tonal" rounded="lg"><VIcon icon="mdi-book-open-page-variant-outline" /></VAvatar>
      </template>
      <VCardTitle>{{ archivePage ? '豆瓣中心 · 归档记录' : '豆瓣中心 · 运行详情' }}</VCardTitle>
      <VCardSubtitle>{{ archivePage ? '删除进入归档，支持恢复或彻底删除' : '榜单刷新 -> 黑名筛选 -> 观察队列 -> 订阅记录' }}</VCardSubtitle>
      <template #append>
        <VBtn variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-1" :loading="loading" @click="archivePage ? loadArchive() : loadAll()">刷新</VBtn>
        <VBtn variant="text" size="small" :prepend-icon="archivePage ? 'mdi-arrow-left' : 'mdi-archive-outline'" class="text-none me-1" :color="archivePage ? 'primary' : undefined" @click="archivePage ? closeArchivePage() : openArchivePage()">{{ archivePage ? '返回' : '归档' }}</VBtn>
        <VBtn variant="text" size="small" prepend-icon="mdi-cog-outline" class="text-none me-1" @click="emit('switch')">设置</VBtn>
        <VBtn icon="mdi-close" variant="text" size="small" @click="emit('close')" />
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="pa-3 dc-flow">
      <VProgressCircular v-if="loading" indeterminate color="primary" class="d-block mx-auto my-6" />
      <div v-if="actionMessage" class="dc-action-message" :class="actionOk ? 'text-success' : 'text-error'">{{ actionMessage }}</div>

      <template v-if="!loading && archivePage">
        <div class="dc-section">
          <div class="dc-section-title mb-2">归档记录 <span class="text-caption font-weight-regular text-medium-emphasis">（共 {{ archiveData.total || 0 }} 条）</span></div>
          <div v-if="archiveData.items && archiveData.items.length" class="dc-history-list">
            <div v-for="(item, i) in archiveData.items" :key="item.id || i" class="dc-history-row dc-status-row">
              <VAvatar size="28" class="mr-2 flex-shrink-0" color="primary" variant="tonal"><VIcon icon="mdi-archive-outline" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ item.title || '未命名条目' }}</div>
                <div class="dc-history-meta">
                  <VChip size="x-small" color="primary" variant="tonal" class="mr-1">{{ item.source_name || item.source || '归档' }}</VChip>
                  <span class="text-caption text-medium-emphasis">{{ item.archived_at ? item.archived_at.split(' ')[0] : '' }}</span>
                </div>
              </div>
              <VBtn icon="mdi-restore" variant="text" size="x-small" color="primary" class="dc-row-action" :loading="actionKey === rowKey('archive-restore', item, i)" @click="restoreArchive(item, i)" />
              <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="actionKey === rowKey('archive-delete', item, i)" @click="deleteArchive(item, i)" />
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无归档记录</div>
        </div>
      </template>

      <template v-else-if="!loading">
        <div v-if="stats" class="dc-section">
          <div class="dc-section-title mb-2">订阅统计</div>
          <div class="dc-stats-grid">
            <div class="dc-stat-card">
              <div class="dc-stat-value">{{ stats.total || 0 }}</div>
              <div class="dc-stat-label">总订阅数</div>
            </div>
            <div class="dc-stat-card">
              <div class="dc-stat-value">{{ stats.month_new || 0 }}</div>
              <div class="dc-stat-label">本月新增</div>
            </div>
            <div v-for="(count, key) in stats.rank_dist" :key="key" class="dc-stat-card">
              <div class="dc-stat-value" :style="{ color: `rgb(var(--v-theme-${rankColors[key] || 'primary'}))` }">{{ count }}</div>
              <div class="dc-stat-label">{{ rankNames[key] || key }}</div>
            </div>
          </div>
        </div>

        <div v-if="rankHistory && Object.keys(rankHistory).length" class="dc-section">
          <div class="dc-section-title mb-2">榜单快照 <span class="text-caption font-weight-regular text-medium-emphasis">（点击条目订阅或打开来源）</span></div>
          <div class="dc-rank-grid">
            <div v-for="[key, items] in Object.entries(rankHistory)" :key="key" class="dc-rank-card">
              <div class="dc-rank-head"><VIcon icon="mdi-format-list-numbered" size="15" :color="rankColors[key] || 'primary'" class="mr-1" /><span>{{ rankNames[key] || key }}</span></div>
              <template v-if="items && items.length">
                <div v-for="(item, i) in items.slice(0, 5)" :key="`${key}-${i}`" class="dc-rank-row" title="订阅 / 打开详情" @click="showActionDialog(key, item)">
                  <VAvatar size="20" rounded="sm" class="dc-rank-poster"><VImg v-if="item.poster" :src="item.poster" cover /><VIcon v-else icon="mdi-filmstrip" size="13" /></VAvatar>
                  <span class="dc-rank-title">{{ item.title || '' }}</span>
                  <span v-if="key === 'coming' && item.wish_count" class="dc-rank-wish">{{ item.wish_count }}</span>
                </div>
              </template>
              <div v-else class="dc-rank-empty">暂无榜单数据</div>
            </div>
          </div>
        </div>

        <div class="dc-section">
          <div class="dc-section-title mb-2 dc-title-with-chips">
            黑名拦截
            <span class="text-caption font-weight-regular text-medium-emphasis">（关键词 {{ blacklistKeywords.length }} 个，最近命中 {{ blacklistEntries.length }} 条）</span>
            <VChip v-for="(word, i) in blacklistKeywords" :key="`${word}-${i}`" size="x-small" color="error" variant="tonal" class="dc-blacklist-chip">{{ word }}</VChip>
          </div>
          <div v-if="blacklistEntries && blacklistEntries.length" class="dc-history-list">
            <div v-for="(item, i) in blacklistEntries" :key="i" class="dc-history-row dc-status-row">
              <VAvatar size="28" class="mr-2 flex-shrink-0" color="error" variant="tonal"><VIcon icon="mdi-block-helper" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ item.title || '未命名条目' }}</div>
                <div class="dc-history-meta"><span class="text-caption text-medium-emphasis">{{ item.time || '' }}</span></div>
              </div>
              <VChip size="x-small" color="error" variant="tonal" class="dc-row-status">{{ item.detail || item.reason || '黑名单关键词' }}</VChip>
              <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="actionKey === rowKey('log', item, i)" @click="deleteAntiCheatLog(item, i)" />
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无被黑名单筛选的条目</div>
        </div>

        <div class="dc-section">
          <div class="dc-section-title mb-2">观察队列 <span class="text-caption font-weight-regular text-medium-emphasis">（待自动订阅 {{ pendingObservations.length }} 条）</span></div>
          <div v-if="pendingObservations && pendingObservations.length" class="dc-history-list">
            <div v-for="(item, i) in pendingObservations" :key="i" class="dc-history-row dc-status-row dc-history-row--clickable" @click="showActionDialog(item.rank_key, item)">
              <VAvatar size="28" class="mr-2 flex-shrink-0" color="warning" variant="tonal"><VIcon icon="mdi-clock-outline" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ item.title }}</div>
                <div class="dc-history-meta">
                  <VChip size="x-small" :color="rankColors[item.rank_key] || 'primary'" variant="tonal" class="mr-1">{{ item.rank_name }}</VChip>
                  <span class="text-caption text-medium-emphasis">观察 {{ item.elapsed_days || 0 }} / {{ item.observe_days || 0 }} 天</span>
                </div>
              </div>
              <VChip size="x-small" color="warning" variant="tonal" class="dc-row-status">剩余 {{ item.remaining_days || 0 }} 天</VChip>
              <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="actionKey === rowKey('obs', item, i)" @click.stop="deleteObservation(item, i)" />
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无观察期条目</div>
        </div>

        <div class="dc-section">
          <div class="dc-section-title mb-2">订阅历史 <span class="text-caption font-weight-regular text-medium-emphasis">（共 {{ historyData.total }} 条）</span></div>
          <div v-if="historyData.items && historyData.items.length" class="dc-history-list">
            <div v-for="(item, i) in historyData.items" :key="i" class="dc-history-row dc-status-row">
              <VAvatar size="28" class="mr-2 flex-shrink-0"><VImg v-if="item.poster" :src="item.poster" /><VIcon v-else icon="mdi-filmstrip" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ item.title }}</div>
                <div class="dc-history-meta">
                  <VChip size="x-small" :color="rankColors[item.rank_key] || 'primary'" variant="tonal" class="mr-1">{{ item.rank_name }}</VChip>
                  <span class="text-caption text-medium-emphasis">{{ item.time ? item.time.split(' ')[0] : '' }}</span>
                </div>
              </div>
              <VChip size="x-small" :color="item.status === 'failed' ? 'error' : 'success'" variant="tonal" class="dc-row-status">{{ item.status === 'failed' ? '订阅失败' : '订阅成功' }}</VChip>
              <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="actionKey === rowKey('sub', item, i)" @click="deleteSubscribeHistory(item, i)" />
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无订阅记录</div>
          <div v-if="historyData.total_pages > 1" class="d-flex justify-center mt-2">
            <VBtn variant="text" size="x-small" :disabled="historyData.page <= 1" class="mx-1" @click="goPage(historyData.page - 1)">上一页</VBtn>
            <span class="d-flex align-center mx-2 text-caption text-medium-emphasis">{{ historyData.page }} / {{ historyData.total_pages }}</span>
            <VBtn variant="text" size="x-small" :disabled="historyData.page >= historyData.total_pages" class="mx-1" @click="goPage(historyData.page + 1)">下一页</VBtn>
          </div>
        </div>

        <div class="dc-section">
          <div class="dc-section-title mb-2">观察日志 <span class="text-caption font-weight-regular text-medium-emphasis">（最近 {{ cheatLogs.length }} 条）</span></div>
          <div v-if="cheatLogs && cheatLogs.length" class="dc-history-list">
            <div v-for="(log, i) in cheatLogs.slice().reverse()" :key="i" class="dc-history-row dc-status-row">
              <VAvatar size="28" class="mr-2 flex-shrink-0"><VImg v-if="log.poster" :src="log.poster" /><VIcon v-else icon="mdi-filmstrip" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ log.title }}</div>
                <div class="dc-history-meta">
                  <VChip size="x-small" :color="rankColors[log.rank_key] || 'primary'" variant="tonal" class="mr-1">{{ log.rank_name || log.rank_key || '观察日志' }}</VChip>
                  <span class="text-caption text-medium-emphasis">{{ log.time ? log.time.split(' ')[0] : '' }}</span>
                </div>
              </div>
              <VChip size="x-small" color="warning" variant="tonal" class="dc-row-status">{{ log.reason || '观察日志' }}</VChip>
              <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="actionKey === rowKey('log', log, i)" @click="deleteAntiCheatLog(log, i)" />
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无观察日志</div>
        </div>
      </template>
    </VCardText>
    <VDialog v-model="showDialog" max-width="360">
      <VCard>
        <VCardTitle class="text-subtitle-1">{{ dialogItem?.item?.title || '选择操作' }}</VCardTitle>
        <VCardText class="text-caption text-medium-emphasis">{{ dialogItem?.item?.year || '' }}</VCardText>
        <VCardActions>
          <VBtn :color="sourceButtonColor()" variant="text" @click="doOpenSource">来源</VBtn>
          <VBtn color="primary" variant="text" :disabled="!(dialogItem?.item?.tmdbid || dialogItem?.item?.tmdb_id)" @click="doOpenTmdb">TMDB</VBtn>
          <VSpacer />
          <VBtn color="success" variant="flat" @click="doSubscribe">订阅</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VCard>
</template>

<style scoped>
.dc-page { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.dc-page-header { padding: 12px 16px; }
.dc-flow { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 8px; }
.dc-section { grid-column: span 6; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .6)); border-radius: 8px; padding: 10px; min-width: 0; }
.dc-section--stats, .dc-section--history, .dc-section--logs { grid-column: span 12; }
.dc-section-title { font-size: 14px; font-weight: 600; color: rgb(var(--v-theme-primary)); }
.dc-title-with-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.dc-blacklist-chip { max-width: 120px; }
.dc-action-message { grid-column: 1 / -1; font-size: 13px; font-weight: 600; padding: 4px 2px; }
.dc-stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 6px; }
.dc-stat-card { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .5)); border-radius: 8px; padding: 8px; text-align: center; }
.dc-stat-value { font-size: 18px; font-weight: 700; color: rgb(var(--v-theme-primary)); }
.dc-stat-label { font-size: 11px; color: rgba(var(--v-theme-on-surface), .5); margin-top: 2px; }
.dc-rank-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.dc-rank-card { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .6)); border-radius: 8px; padding: 6px; min-width: 0; }
.dc-rank-head { display: flex; align-items: center; font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.dc-rank-row { display: flex; align-items: center; gap: 4px; padding: 3px 4px; border-radius: 4px; cursor: pointer; font-size: 12px; min-width: 0; }
.dc-rank-row:hover { background: rgba(var(--v-theme-primary), .07); }
.dc-rank-poster { flex: 0 0 20px; width: 20px; height: 28px; border-radius: 3px; background: rgba(var(--v-theme-on-surface), .08); overflow: hidden; }
.dc-rank-title { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-rank-wish { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .5); font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
.dc-rank-empty { text-align: center; color: rgba(var(--v-theme-on-surface), .55); font-size: 12px; padding: 8px 0; }
.dc-history-list { display: flex; flex-direction: column; gap: 2px; }
.dc-history-row { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; column-gap: 6px; padding: 5px 6px; border-radius: 6px; transition: background .12s; }
.dc-status-row { grid-template-columns: auto minmax(0, 1fr) auto auto; }
.dc-history-row--clickable { cursor: pointer; }
.dc-history-row:hover { background: rgba(var(--v-theme-primary), .04); }
.dc-history-info { min-width: 0; }
.dc-history-title { font-size: 13px; font-weight: 500; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-history-meta { display: flex; align-items: center; gap: 4px; margin-top: 1px; min-width: 0; overflow: hidden; }
.dc-row-status { max-width: 160px; }
.dc-row-action { flex: 0 0 auto; }
@media (max-width: 760px) {
  .dc-flow { grid-template-columns: 1fr; }
  .dc-section { grid-column: 1 / -1; padding: 10px; }
  .dc-rank-grid { grid-template-columns: repeat(6, 150px); overflow-x: auto; padding-bottom: 2px; }
  .dc-history-row { grid-template-columns: auto minmax(0, 1fr) auto; column-gap: 4px; padding: 4px 6px; }
  .dc-status-row { grid-template-columns: auto minmax(0, 1fr) auto auto; }
  .dc-row-status { max-width: 96px; }
}
</style>
