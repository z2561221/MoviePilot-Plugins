<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })

const config = ref({})
const rankHistory = ref({})
const folioData = ref({})
const loading = ref(false)
const refreshing = ref(false)
const subscribeResult = ref('')
const refreshResult = ref('')

const rankDefs = {
  coming: { name: '即将上映' },
  tv_real_time: { name: '实时热门' },
  tv_chinese: { name: '华语口碑' },
  tv_global: { name: '全球口碑' },
  movie_weekly: { name: '电影口碑' },
  bangumi: { name: 'BangumiTV' },
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

async function subscribe(rankKey, item) {
  if (!item) return
  subscribeResult.value = ''
  try {
    const params = `tmdb_id=${item.tmdbid}&media_type=tv&title=${encodeURIComponent(item.title)}&year=${item.year || ''}`
    const res = await getPluginApi(props.api, `subscribe?${params}`)
    subscribeResult.value = res.success ? `${item.title} 已订阅` : `${item.title}: ${res.message}`
  } catch (e) {
    subscribeResult.value = `订阅失败: ${e}`
  }
  setTimeout(() => { subscribeResult.value = '' }, 3000)
}

const timelineGroups = computed(() => {
  const data = folioData.value || {}
  const limitMonth = config.value?.folio_pc_month || 3
  const limitNum = config.value?.folio_pc_num || 50
  const entries = Object.entries(data)
    .filter(([_, v]) => v && typeof v === 'object' && v.timestamp)
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
      <VCardSubtitle>点击榜单条目可直接订阅</VCardSubtitle>
      <template #append>
        <VBtn variant="text" size="x-small" prepend-icon="mdi-refresh" class="text-none" :loading="refreshing" @click="refreshRss">刷新</VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="pa-3">
      <VProgressCircular v-if="loading" indeterminate color="primary" class="d-block mx-auto my-6" />
      <VAlert v-if="subscribeResult" :type="subscribeResult.includes('已订阅') ? 'success' : 'error'" variant="tonal" class="mb-2" :text="subscribeResult" density="compact" closable />
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
              <div v-for="(item, i) in (rankHistory[rk] || []).slice(0, 5)" :key="i" class="dc-rank-row" :title="item.title" @click="subscribe(rk, item)">
                <VAvatar size="16" class="mr-1 flex-shrink-0"><VImg v-if="item.poster" :src="item.poster" /><VIcon v-else icon="mdi-filmstrip" size="10" /></VAvatar>
                <span class="dc-rank-name">{{ item.title }}</span>
                <span class="dc-rank-num">
                  <template v-if="rk === 'coming' && item.wish_count">{{ item.wish_count }}</template>
                  <template v-else>{{ item.year || '' }}</template>
                </span>
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
@media (max-width: 960px) { .dc-rank-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 600px) { .dc-rank-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
