<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPluginApi, postPluginApi, toPosterThumbnail } from './api'
import { sourceDescriptor, doubanDispatchUrl } from './source'
import { useRankMediaActions } from './useRankMediaActions'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: '' },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
  nativeSubscribe: { type: Function, default: null },
})

const dashboardPluginId = computed(
  () => String(props.pluginId || props.config?.id || 'DoubanCenter').trim() || 'DoubanCenter',
)

const config = ref({})
const rankHistory = ref({})
const folioData = ref({})
const loading = ref(false)
const folioLoading = ref(false)
const refreshing = ref(false)
const subscribeResult = ref('')
const refreshResult = ref('')
const loadError = ref('')
const dialogItem = ref(null)
const showDialog = ref(false)
const dialogResolving = ref(false)
const dialogResolveError = ref('')
const dialogResolveToken = ref(0)
const timelineImageFailed = ref({})

const builtinRankDefs = {
  coming: { name: '即将上映' },
  tv_real_time: { name: '实时热门' },
  tv_chinese: { name: '华语口碑' },
  tv_global: { name: '全球口碑' },
  movie_weekly: { name: '电影口碑' },
  bangumi: { name: 'BangumiTV' },
}
const rankIconColors = {
  coming: '#f97316',
  tv_real_time: '#06b6d4',
  tv_chinese: '#eab308',
  tv_global: '#ef4444',
  movie_weekly: '#ec4899',
  bangumi: '#8b5cf6',
  unknown: '#94a3b8',
}
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
  return option?.title || builtinRankDefs[key]?.name || key
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
  let lastError = null
  for (let attempt = 0; attempt <= TIMELINE_RETRY_DELAYS_MS.length; attempt += 1) {
    if (attempt > 0) {
      await new Promise(resolve => setTimeout(resolve, TIMELINE_RETRY_DELAYS_MS[attempt - 1]))
    }
    try {
      const timeoutMs = attempt === 0 ? INITIAL_LOAD_TIMEOUT_MS : TIMELINE_RETRY_TIMEOUT_MS
      return await requestFolioData(timeoutMs)
    } catch (error) {
      lastError = error
      if (error?.code === 'PLUGIN_API_TIMEOUT' && attempt > 0) break
    }
  }
  throw lastError || new Error('追影时间线加载失败')
}

async function load() {
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

  coreResults.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      if (result.value?.success === false) {
        errors.push(coreRequests[index].label)
        return
      }
      const data = normalizeApiData(result.value)
      if (index === 0) config.value = data || {}
      else rankHistory.value = data || {}
      return
    }
    errors.push(coreRequests[index].label)
    console.error(`[DoubanCenter] ${coreRequests[index].label}加载失败`, result.reason)
  })
  loading.value = false

  const [folioResult] = await folioRequest
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
  refreshing.value = true
  refreshResult.value = ''
  await load()
  try {
    const res = await postPluginApi(props.api, dashboardPluginId.value, 'refresh_rss', {})
    if (res.success) {
      if (res.data) rankHistory.value = res.data
      refreshResult.value = 'RSS 已刷新'
    } else {
      refreshResult.value = res.message || 'RSS 刷新失败'
    }
  } catch (e) {
    refreshResult.value = `刷新失败: ${e}`
  }
  refreshing.value = false
  setTimeout(() => { refreshResult.value = '' }, 3000)
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
    if (token === dialogResolveToken.value) {
      dialogResolveError.value = error?.message || 'TMDB 识别失败'
    }
  } finally {
    if (token === dialogResolveToken.value) dialogResolving.value = false
  }
}

function markTimelineImageFailed(key) {
  timelineImageFailed.value = { ...timelineImageFailed.value, [key]: true }
}

function dialogPoster() {
  const item = dialogItem.value?.item || {}
  return toPosterThumbnail(item.poster || item.poster_path || item.cover)
}

async function subscribeViaNativeDialog(rk, item) {
  const media = await resolveRankMedia(rk, item)
  await props.nativeSubscribe(media)
  subscribeResult.value = '已打开 MP 原生订阅窗口'
}

async function subscribeRankItem(rk, item) {
  const res = await requestRankSubscription(rk, item)
  if (!res?.success) throw new Error(res?.message || '订阅失败')
  subscribeResult.value = res?.message || `${item.title || ''} 已添加订阅`
}

async function doSubscribe() {
  if (!dialogItem.value || dialogResolving.value) return
  const { rk, item } = dialogItem.value
  showDialog.value = false
  subscribeResult.value = ''
  try {
    if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item)
    else await subscribeRankItem(rk, item)
  } catch (e) {
    subscribeResult.value = `订阅失败: ${e?.message || e}`
  }
  setTimeout(() => { subscribeResult.value = '' }, 3000)
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
      currentGroup.items.push({ key: entry.key, subject_name: entry.display_title || entry.subject_name || entry.key, subject_id: entry.subject_id, poster, type: entry.type, season_label: entry.season_label || '' })
    }
  }
  return groups
})

onMounted(load)
</script>

<template>
  <VCard class="dc-card" variant="flat">
    <VCardItem>
      <template #prepend><VAvatar color="primary" variant="tonal" rounded="lg"><VIcon icon="mdi-book-open-page-variant-outline" /></VAvatar></template>
      <VCardTitle>豆瓣中心</VCardTitle>
      <VCardSubtitle>点击榜单条目可选择来源、TMDB 或订阅</VCardSubtitle>
      <template #append>
        <VBtn variant="text" size="x-small" prepend-icon="mdi-refresh" class="text-none" :loading="refreshing" @click="refreshDashboard">刷新</VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VProgressLinear v-if="loading || folioLoading" indeterminate color="primary" height="2" />
    <VCardText class="pa-3">
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact" class="mb-2 dc-load-alert">
        <div class="dc-load-alert__content">
          <span>{{ loadError }}</span>
          <VBtn variant="text" size="x-small" prepend-icon="mdi-refresh" class="text-none" :loading="loading || folioLoading" @click="load">重试</VBtn>
        </div>
      </VAlert>
      <VAlert v-if="subscribeResult" :type="subscribeResult.includes('失败') ? 'error' : 'success'" variant="tonal" class="mb-2" :text="subscribeResult" density="compact" closable />
      <VAlert v-if="refreshResult" :type="refreshResult.includes('已刷新') ? 'success' : 'error'" variant="tonal" class="mb-2" :text="refreshResult" density="compact" closable />

      <div v-if="timelineGroups.length" class="mb-3">
        <div class="dc-rank-grid">
          <div class="dc-rank-cell dc-tl-cell" style="grid-column: 1 / -1">
            <div class="dc-rank-head"><VIcon icon="mdi-timeline-clock-outline" size="14" class="mr-1" color="primary" />追影时间线</div>
            <div class="dc-rank-body">
              <div class="dc-timeline-scroll">
                <div class="dc-timeline-months">
                  <div v-for="group in timelineGroups" :key="group.monthKey" class="dc-timeline-month">
                    <div class="text-caption text-medium-emphasis mb-1" style="font-size: 11px">{{ group.label }} <VChip size="x-small" color="primary" variant="tonal">{{ group.items.length }}</VChip></div>
                    <div class="dc-timeline-posters">
                      <a
                        v-for="item in group.items"
                        :key="item.key"
                        :href="doubanDispatchUrl(item.subject_id, item.type)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="dc-poster"
                        :title="item.subject_name"
                      >
                        <VImg v-if="item.poster && !timelineImageFailed[item.key]" :src="item.poster" width="60" height="90" cover class="rounded" @error="markTimelineImageFailed(item.key)" />
                        <div v-else class="dc-ph"><VIcon icon="mdi-filmstrip" size="14" /></div>
                        <span v-if="item.season_label" class="dc-folio-season">{{ item.season_label }}</span>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="config.dashboard_rank_keys && config.dashboard_rank_keys.length">
        <div class="dc-rank-grid">
          <div v-for="rk in config.dashboard_rank_keys.slice(0, 6)" :key="rk" class="dc-rank-cell">
            <div class="dc-rank-head"><VIcon icon="mdi-format-list-numbered" size="15" :style="rankIconStyle(rk)" class="mr-1" /><span>{{ rankNameOf(rk, rankHistory[rk]?.[0]) }}</span></div>
            <div class="dc-rank-body">
              <div v-for="(item, i) in (rankHistory[rk] || []).slice(0, 5)" :key="i" class="dc-rank-row" :title="item.title" @click="showActionDialog(rk, item)">
                <VAvatar rounded="sm" class="dc-rank-poster"><VImg v-if="item.poster" :src="toPosterThumbnail(item.poster)" cover /><VIcon v-else icon="mdi-filmstrip" size="13" /></VAvatar>
                <span class="dc-rank-title">{{ item.title }}</span>
                <span v-if="rk === 'coming' && item.wish_count" class="dc-rank-wish">{{ item.wish_count }}</span>
              </div>
              <div v-if="!(rankHistory[rk] || []).length" class="text-center text-medium-emphasis py-2 text-caption">暂无数据</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading && !folioLoading && !config.dashboard_rank_keys?.length && !timelineGroups.length" class="text-center text-medium-emphasis py-4 text-caption">
        请在配置页「仪表显示」中选择要显示的榜单
      </div>
    </VCardText>
    <VDialog v-model="showDialog" max-width="420">
      <VCard rounded="lg" class="dc-action-dialog">
        <VCardItem class="pa-3">
          <template #prepend>
            <VAvatar size="36" rounded="md" class="mr-2">
              <VImg v-if="dialogPoster()" :src="dialogPoster()" />
              <VIcon v-else icon="mdi-filmstrip" />
            </VAvatar>
          </template>
          <VCardTitle class="text-body-1 font-weight-bold pa-0">{{ dialogItem?.item?.title || '' }}</VCardTitle>
          <VCardSubtitle class="text-caption pa-0">{{ dialogItem?.rk ? rankNameOf(dialogItem.rk, dialogItem.item) : '' }}</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VAlert v-if="dialogResolveError" type="warning" variant="tonal" density="compact" class="mx-3 mt-3" :text="dialogResolveError" />
        <VCardActions class="pa-3 pt-2 dc-dialog-actions">
          <VBtn variant="tonal" color="primary" prepend-icon="mdi-plus-circle-outline" class="dc-dialog-action text-none" :disabled="dialogResolving" @click="doSubscribe">订阅</VBtn>
          <VBtn variant="tonal" prepend-icon="mdi-movie-open-outline" class="dc-dialog-action dc-dialog-action--tmdb text-none" :loading="dialogResolving" :disabled="dialogResolving || !tmdbIdOf(dialogItem?.item)" @click="doOpenTmdb">TMDB</VBtn>
          <VBtn :href="sourceButtonHref() || undefined" target="_blank" rel="noopener noreferrer" variant="tonal" :color="sourceButtonColor()" :prepend-icon="sourceButtonIcon()" :disabled="!sourceButtonUrl()" class="dc-dialog-action text-none" @click="openSource">{{ sourceButtonLabel() }}</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VCard>
</template>

<style scoped>
.dc-card { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; max-width: 100%; }
.dc-load-alert__content { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; font-size: 12px; }
.dc-load-alert__content span { min-width: 0; overflow-wrap: anywhere; }
.dc-poster { position: relative; text-decoration: none; transition: transform .15s; display: block; border-radius: 4px; overflow: hidden; }
.dc-folio-season { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0, 0, 0, .72); color: #fff; text-align: center; font-size: 10px; line-height: 18px; pointer-events: none; }
.dc-poster:hover { transform: translateY(-2px); }
.dc-ph { width: 60px; height: 90px; display: flex; align-items: center; justify-content: center; background: rgba(var(--v-theme-on-surface), .05); color: rgba(var(--v-theme-on-surface), .25); border-radius: 4px; }
.dc-rank-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; width: 100%; max-width: 100%; min-width: 0; overflow-x: hidden; }
.dc-rank-cell { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .5)); border-radius: 8px; padding: 5px; min-width: 0; max-width: 100%; }
.dc-tl-cell { overflow: hidden; max-width: 100%; }
.dc-rank-head { display: flex; align-items: center; font-size: 12px; font-weight: 600; margin-bottom: 3px; padding-bottom: 3px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .3)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dc-rank-body { display: flex; flex-direction: column; gap: 1px; min-width: 0; max-width: 100%; }
.dc-timeline-scroll { width: 100%; max-width: 100%; min-width: 0; overflow-x: auto; overflow-y: hidden; overscroll-behavior-x: contain; overscroll-behavior-y: auto; touch-action: pan-x; scrollbar-width: none; -ms-overflow-style: none; }
.dc-timeline-scroll::-webkit-scrollbar { display: none; }
.dc-timeline-months { display: flex; flex-wrap: nowrap; gap: 8px; width: max-content; min-width: 100%; }
.dc-timeline-month { flex: 0 0 auto; min-width: 0; }
.dc-timeline-posters { display: flex; flex-wrap: nowrap; gap: 3px; }
.dc-rank-row { display: flex; align-items: center; gap: 3px; min-height: 40px; padding: 2px 3px; border-radius: 4px; cursor: pointer; font-size: 12px; line-height: 1.4; transition: background .12s; overflow: hidden; }
.dc-rank-row:hover { background: rgba(var(--v-theme-primary), .07); }
.dc-rank-poster { flex: 0 0 24px !important; width: 24px !important; height: 36px !important; min-width: 24px; min-height: 36px; aspect-ratio: 2 / 3; border-radius: 3px !important; background: rgba(var(--v-theme-on-surface), .08); overflow: hidden; }
.dc-rank-title { display: -webkit-box; flex: 1 1 auto; min-width: 0; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal; overflow-wrap: anywhere; }
.dc-rank-num { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .45); font-size: 11px; white-space: nowrap; }
.dc-rank-wish { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .45); font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
.dc-dialog-action { flex: 1 1 0; min-width: 0; height: 36px; }
.dc-dialog-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.dc-dialog-action--tmdb {
  color: #0288d1 !important;
  color: color-mix(in srgb, #0288d1 78%, rgb(var(--v-theme-on-surface)) 22%) !important;
}
@media (max-width: 960px) { .dc-rank-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 600px) {
  .dc-card :deep(.v-card-item) { padding: 10px 12px; }
  .dc-card :deep(.v-card-subtitle) { display: none; }
  .dc-rank-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .dc-rank-cell { padding: 6px; }
  .dc-action-dialog { width: min(420px, calc(100vw - 24px)); max-width: calc(100vw - 24px); }
}
@media (max-width: 360px) { .dc-rank-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
