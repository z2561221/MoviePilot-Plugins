<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
})

const config = ref({})
const rankHistory = ref({})
const folioData = ref({})
const loading = ref(false)
const refreshing = ref(false)
const subscribeResult = ref('')
const refreshResult = ref('')
const dialogItem = ref(null)
const showDialog = ref(false)

const rankDefs = {
  coming: { name: '即将上映' },
  tv_real_time: { name: '实时热门' },
  tv_chinese: { name: '华语口碑' },
  tv_global: { name: '全球口碑' },
  movie_weekly: { name: '电影口碑' },
  bangumi: { name: 'BangumiTV' },
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

async function load() {
  loading.value = true
  try {
    config.value = await getPluginApi(props.api, 'config') || {}
    rankHistory.value = await getPluginApi(props.api, 'rank_history') || {}
    folioData.value = await getPluginApi(props.api, 'folio_data') || {}
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

async function refreshRss() {
  refreshing.value = true
  refreshResult.value = ''
  try {
    const res = await postPluginApi(props.api, 'refresh_rss', {})
    if (res.success) {
      if (res.data) rankHistory.value = res.data
      else rankHistory.value = await getPluginApi(props.api, 'rank_history') || {}
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

function showActionDialog(rk, item) {
  dialogItem.value = { rk, item }
  showDialog.value = true
}

async function subscribeViaNativeDialog(rk, item) {
  const media = await resolveRankMedia(rk, item)
  await props.nativeSubscribe(media)
  subscribeResult.value = '已打开 MP 原生订阅窗口'
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
  subscribeResult.value = res?.message || `${item.title || ''} 已添加订阅`
}

async function doSubscribe() {
  if (!dialogItem.value) return
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

const timelineGroups = computed(() => {
  const data = folioData.value || {}
  const limitMonth = config.value?.folio_pc_month || 3
  const limitNum = config.value?.folio_pc_num || 50
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
      const poster = (entry.poster_path || '').replace('/original/', '/w200/')
      currentGroup.items.push({ key: entry.key, subject_name: entry.subject_name || entry.key, subject_id: entry.subject_id, poster, type: entry.type })
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
        <VBtn variant="text" size="x-small" prepend-icon="mdi-refresh" class="text-none" :loading="refreshing" @click="refreshRss">刷新</VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="pa-3">
      <VProgressCircular v-if="loading" indeterminate color="primary" class="d-block mx-auto my-6" />
      <VAlert v-if="subscribeResult" :type="subscribeResult.includes('失败') ? 'error' : 'success'" variant="tonal" class="mb-2" :text="subscribeResult" density="compact" closable />
      <VAlert v-if="refreshResult" :type="refreshResult.includes('已刷新') ? 'success' : 'error'" variant="tonal" class="mb-2" :text="refreshResult" density="compact" closable />

      <div v-if="timelineGroups.length" class="mb-3">
        <div class="dc-rank-grid">
          <div class="dc-rank-cell dc-tl-cell" style="grid-column: 1 / -1">
            <div class="dc-rank-head"><VIcon icon="mdi-timeline-clock-outline" size="14" class="mr-1" color="primary" />追影时间线</div>
            <div class="dc-rank-body">
              <div class="d-flex flex-wrap" style="gap: 8px">
                <div v-for="group in timelineGroups" :key="group.monthKey" class="flex-shrink-0">
                  <div class="text-caption text-medium-emphasis mb-1" style="font-size: 11px">{{ group.label }} <VChip size="x-small" color="primary" variant="tonal">{{ group.items.length }}</VChip></div>
                  <div class="d-flex flex-wrap" style="gap: 3px">
                    <a
                      v-for="item in group.items"
                      :key="item.key"
                      :href="`https://www.douban.com/doubanapp/dispatch?uri=/movie/${item.subject_id}?from=mdouban&open=app`"
                      target="_blank"
                      class="dc-poster"
                      :title="item.subject_name"
                    >
                      <VImg v-if="item.poster" :src="item.poster" width="60" height="90" cover class="rounded" />
                      <div v-else class="dc-ph"><VIcon icon="mdi-filmstrip" size="14" /></div>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="config.dashboard_rank_keys && config.dashboard_rank_keys.length">
        <div class="dc-rank-grid">
          <div v-for="rk in config.dashboard_rank_keys" :key="rk" class="dc-rank-cell">
            <div class="dc-rank-head">{{ rankDefs[rk]?.name || rk }}</div>
            <div class="dc-rank-body">
              <div v-for="(item, i) in (rankHistory[rk] || []).slice(0, 5)" :key="i" class="dc-rank-row" :title="item.title" @click="showActionDialog(rk, item)">
                <VAvatar size="16" class="mr-1 flex-shrink-0"><VImg v-if="item.poster" :src="item.poster" /><VIcon v-else icon="mdi-filmstrip" size="10" /></VAvatar>
                <span class="dc-rank-name">{{ item.title }}</span>
                <span v-if="rk === 'coming' && item.wish_count" class="dc-rank-wish">{{ item.wish_count }}</span>
                <span v-else class="dc-rank-num">{{ item.year || '' }}</span>
              </div>
              <div v-if="!(rankHistory[rk] || []).length" class="text-center text-medium-emphasis py-2 text-caption">暂无数据</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading && !config.dashboard_rank_keys?.length && !timelineGroups.length" class="text-center text-medium-emphasis py-4 text-caption">
        请在配置页「仪表显示」中选择要显示的榜单
      </div>
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
.dc-card { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.dc-poster { text-decoration: none; transition: transform .15s; display: block; border-radius: 4px; overflow: hidden; }
.dc-poster:hover { transform: translateY(-2px); }
.dc-ph { width: 60px; height: 90px; display: flex; align-items: center; justify-content: center; background: rgba(var(--v-theme-on-surface), .05); color: rgba(var(--v-theme-on-surface), .25); border-radius: 4px; }
.dc-rank-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.dc-rank-cell { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .5)); border-radius: 8px; padding: 5px; min-width: 0; }
.dc-rank-head { font-size: 12px; font-weight: 600; margin-bottom: 3px; padding-bottom: 3px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .3)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dc-rank-body { display: flex; flex-direction: column; gap: 1px; }
.dc-rank-row { display: flex; align-items: center; gap: 3px; padding: 2px 3px; border-radius: 4px; cursor: pointer; font-size: 12px; line-height: 1.4; transition: background .12s; overflow: hidden; }
.dc-rank-row:hover { background: rgba(var(--v-theme-primary), .07); }
.dc-rank-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-rank-num { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .45); font-size: 11px; white-space: nowrap; }
.dc-rank-wish { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .5); font-size: 11px; white-space: nowrap; }
@media (max-width: 960px) { .dc-rank-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 600px) { .dc-rank-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
