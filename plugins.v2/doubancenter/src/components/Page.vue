<script setup>
import { ref, onMounted } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['close', 'switch'])

const loading = ref(false)
const stats = ref(null)
const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
const cheatLogs = ref([])

async function loadAll() {
  loading.value = true
  try {
    const [s, h, c] = await Promise.all([
      getPluginApi(props.api, 'stats'),
      getPluginApi(props.api, `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`),
      getPluginApi(props.api, 'anti_cheat_logs'),
    ])
    if (s) stats.value = s
    if (h) historyData.value = h
    if (c) cheatLogs.value = c
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

async function goPage(p) {
  if (p < 1 || p > historyData.value.total_pages) return
  historyData.value.page = p
  await loadAll()
}

const rankColors = {
  coming: 'primary',
  tv_real_time: 'teal',
  tv_chinese: 'orange-darken-1',
  tv_global: 'deep-purple',
  movie_weekly: 'pink',
  bangumi: 'brown',
}

onMounted(loadAll)
</script>

<template>
  <VCard flat class="dc-page">
    <VCardItem class="dc-page-header">
      <template #prepend><VAvatar color="primary" variant="tonal" rounded="lg"><VIcon icon="mdi-book-open-page-variant-outline" /></VAvatar></template>
      <VCardTitle>豆瓣中心 · 订阅记录</VCardTitle>
      <VCardSubtitle>榜单订阅历史与统计</VCardSubtitle>
      <template #append>
        <VBtn variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-1" :loading="loading" @click="loadAll">刷新</VBtn>
        <VBtn variant="text" size="small" prepend-icon="mdi-cog-outline" class="text-none me-1" @click="emit('switch')">设置</VBtn>
        <VBtn icon="mdi-close" variant="text" size="small" @click="emit('close')" />
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="pa-3">
      <VProgressCircular v-if="loading" indeterminate color="primary" class="d-block mx-auto my-6" />

      <template v-if="!loading">
        <div v-if="stats" class="mb-4">
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
              <div class="dc-stat-label">{{ ({ coming: '即将上映', tv_real_time: '实时热门', tv_chinese: '华语口碑', tv_global: '全球口碑', movie_weekly: '电影口碑', bangumi: 'BangumiTV' })[key] || key }}</div>
            </div>
          </div>
        </div>

        <div class="mb-4">
          <div class="dc-section-title mb-2">订阅历史 <span class="text-caption font-weight-regular text-medium-emphasis">（共 {{ historyData.total }} 条）</span></div>
          <div v-if="historyData.items && historyData.items.length" class="dc-history-list">
            <div v-for="(item, i) in historyData.items" :key="i" class="dc-history-row">
              <VAvatar size="28" class="mr-2 flex-shrink-0"><VImg v-if="item.poster" :src="item.poster" /><VIcon v-else icon="mdi-filmstrip" size="14" /></VAvatar>
              <div class="dc-history-info">
                <div class="dc-history-title">{{ item.title }}</div>
                <div class="dc-history-meta">
                  <VChip size="x-small" :color="rankColors[item.rank_key] || 'primary'" variant="tonal" class="mr-1">{{ item.rank_name }}</VChip>
                  <span class="text-caption text-medium-emphasis">{{ item.time ? item.time.split(' ')[0] : '' }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis py-4 text-caption">暂无订阅记录</div>

          <div v-if="historyData.total_pages > 1" class="d-flex justify-center mt-2">
            <VBtn variant="text" size="x-small" :disabled="historyData.page <= 1" class="mx-1" @click="goPage(historyData.page - 1)">上一页</VBtn>
            <span class="d-flex align-center mx-2 text-caption text-medium-emphasis">{{ historyData.page }} / {{ historyData.total_pages }}</span>
            <VBtn variant="text" size="x-small" :disabled="historyData.page >= historyData.total_pages" class="mx-1" @click="goPage(historyData.page + 1)">下一页</VBtn>
          </div>
        </div>

        <div v-if="cheatLogs && cheatLogs.length">
          <div class="dc-section-title mb-2">防刷榜日志 <span class="text-caption font-weight-regular text-medium-emphasis">（最近 {{ cheatLogs.length }} 条）</span></div>
          <div class="dc-cheat-list">
            <div v-for="(log, i) in cheatLogs.slice().reverse()" :key="i" class="dc-cheat-row">
              <VIcon size="14" color="warning" class="mr-1">mdi-shield-off-outline</VIcon>
              <span class="dc-cheat-title">{{ log.title }}</span>
              <VChip size="x-small" color="warning" variant="tonal" class="mx-1">{{ log.reason }}</VChip>
              <span class="text-caption text-medium-emphasis">{{ log.time ? log.time.split(' ')[0] : '' }}</span>
            </div>
          </div>
        </div>
      </template>
    </VCardText>
  </VCard>
</template>

<style scoped>
.dc-page { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.dc-page-header { padding: 12px 16px; }
.dc-section-title { font-size: 14px; font-weight: 600; color: rgb(var(--v-theme-primary)); }
.dc-stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 6px; }
.dc-stat-card { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .5)); border-radius: 8px; padding: 8px; text-align: center; }
.dc-stat-value { font-size: 18px; font-weight: 700; color: rgb(var(--v-theme-primary)); }
.dc-stat-label { font-size: 11px; color: rgba(var(--v-theme-on-surface), .5); margin-top: 2px; }
.dc-history-list { display: flex; flex-direction: column; gap: 2px; }
.dc-history-row { display: flex; align-items: center; padding: 4px 6px; border-radius: 6px; transition: background .12s; }
.dc-history-row:hover { background: rgba(var(--v-theme-primary), .04); }
.dc-history-info { flex: 1; min-width: 0; }
.dc-history-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-history-meta { display: flex; align-items: center; gap: 4px; margin-top: 1px; }
.dc-cheat-list { display: flex; flex-direction: column; gap: 2px; }
.dc-cheat-row { display: flex; align-items: center; padding: 3px 6px; border-radius: 6px; font-size: 12px; }
.dc-cheat-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
