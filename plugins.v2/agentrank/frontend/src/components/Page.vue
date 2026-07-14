<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAgentRankState } from './useAgentRankState'
import RecommendationActions from './RecommendationActions.vue'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['action', 'switch', 'close'])
const state = useAgentRankState(props.api)

const activeTab = ref('board')
const clearDialog = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success' })
const historyPage = ref(1)
const initialized = ref(false)
const historyPageSize = 10

const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 10) || [])
const archiveEntries = computed(() => state.overview.value?.archive?.entries || [])
const weights = computed(() => state.options.value?.config?.weights || {})
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)))
const statusMetaFor = status => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
}[status] || { text: status || '未知', color: 'default' })
const weightLabels = {
  type_weight: '媒体类型',
  theme_weight: '题材主题',
  actor_weight: '演员偏好',
  director_weight: '导演偏好',
  region_weight: '地区偏好',
  year_weight: '年代偏好',
  rating_weight: '评分质量',
  heat_weight: '热门程度',
  freshness_weight: '新鲜程度',
  similarity_weight: '相似程度',
}

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'weights', title: '权重配置', icon: 'mdi-tune-vertical' },
  { key: 'archive', title: '归档区', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
]

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function weightLabel(key) {
  return weightLabels[key] || key
}

function formatWeight(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

async function initialize() {
  try {
    await state.loadOptions()
    if (state.selectedUser.value) await state.loadUserData()
  } catch (_) {
    // 共享状态承载错误。
  } finally {
    initialized.value = true
  }
}

async function runAction(action, successMessage) {
  try {
    await action()
    snackbar.value = { show: true, message: successMessage, color: 'success' }
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' }
  }
}

async function changeHistoryPage(page) {
  historyPage.value = page
  try { await state.loadHistory(page, historyPageSize) } catch (_) { /* 错误已保存 */ }
}

watch(state.selectedUser, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  historyPage.value = 1
  try { await state.loadUserData(value) } catch (_) { /* 错误已保存 */ }
})

watch(activeTab, async value => {
  if (value === 'history') await changeHistoryPage(1)
})

onMounted(initialize)
</script>

<template>
  <div class="ar-page">
    <VToolbar density="comfortable" class="ar-page__toolbar">
      <VIcon icon="mdi-brain" color="primary" class="ar-page__brand-icon ms-3 me-2" />
      <div class="ar-page__heading">
        <div class="text-h6">Agent榜单中心详情</div>
        <div class="text-caption text-medium-emphasis">推荐、画像、归档与运行记录</div>
      </div>
      <VSpacer />
      <VSelect v-if="state.users.value.length > 1" v-model="state.selectedUser.value" :items="state.users.value" density="compact" variant="outlined" hide-details label="用户" class="ar-page__user" />
      <VBtn icon="mdi-refresh" variant="text" :loading="state.loading.action === 'refresh' || state.loading.data" :disabled="state.isRunning.value" aria-label="刷新详情" @click="runAction(state.refresh, '榜单刷新已完成')" />
      <VBtn icon="mdi-cog-outline" variant="text" aria-label="打开设置" @click="emit('switch')" />
      <VBtn icon="mdi-close" variant="text" aria-label="关闭详情" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <VTabs v-model="activeTab" color="primary" density="compact" class="ar-page__tabs" show-arrows>
      <VTab v-for="tab in tabs" :key="tab.key" :value="tab.key"><VIcon :icon="tab.icon" size="18" class="mr-1" />{{ tab.title }}</VTab>
    </VTabs>
    <VDivider />

    <div class="ar-page__content">
      <VAlert v-if="state.error.value" type="error" variant="tonal" class="mb-3">{{ state.error.value.message }}</VAlert>
      <VSkeletonLoader v-if="state.loading.data" type="article, article" />

      <template v-else>
        <section v-show="activeTab === 'board'" class="ar-page__pane">
          <VEmptyState v-if="!recommendations.length" icon="mdi-format-list-numbered" title="推荐榜单尚未生成" text="点击刷新生成当前用户的 Top 10。" />
          <div v-else class="ar-page__ranking">
            <article v-for="item in recommendations" :key="item.candidate_id" class="ar-page__rank-item">
              <div class="ar-page__rank">{{ item.rank }}</div>
              <div class="ar-page__poster">
                <VImg v-if="item.poster_path" :src="item.poster_path" :alt="`${item.title} 海报`" cover>
                  <template #error><div class="ar-page__poster-error"><VIcon icon="mdi-image-off-outline" size="26" /></div></template>
                </VImg>
                <VIcon v-else icon="mdi-image-off-outline" size="26" />
              </div>
              <div class="ar-page__rank-main">
                <div class="font-weight-bold text-truncate">{{ item.title }}</div>
                <div class="text-caption text-medium-emphasis">{{ item.year || '年份未知' }} · {{ item.media_type }}</div>
                <div class="text-body-2 mt-1">推荐：{{ item.reason || item.summary }}</div>
                <div class="text-body-2 text-medium-emphasis">简介：{{ item.summary }}</div>
              </div>
              <VChip size="x-small" color="primary" variant="tonal">{{ item.confidence }}%</VChip>
              <div class="ar-page__rank-actions">
                <RecommendationActions
                  :item="item"
                  :loading-action="state.loading.action"
                  size="small"
                  @subscribe="candidateId => runAction(() => state.subscribe(candidateId), '订阅操作已完成')"
                  @archive="candidateId => runAction(() => state.archive(candidateId), '已忽略推荐')"
                />
              </div>
            </article>
          </div>
        </section>

        <section v-show="activeTab === 'profile'" class="ar-page__pane">
          <VCard variant="outlined" class="ar-page__section-card">
            <VCardItem>
              <VCardTitle class="text-subtitle-1">画像摘要</VCardTitle>
              <VCardSubtitle>生成于 {{ formatTime(state.profile.value?.generated_at) }}</VCardSubtitle>
              <template #append><VBtn color="error" variant="text" prepend-icon="mdi-account-remove-outline" @click="clearDialog = true">清除画像</VBtn></template>
            </VCardItem>
            <VCardText>
              <div class="text-body-1 mb-4">{{ state.profile.value?.summary || '尚未生成用户画像' }}</div>
              <div class="ar-page__chips"><VChip v-for="tag in state.profile.value?.tags || []" :key="tag" color="primary" variant="tonal" size="small">{{ tag }}</VChip></div>
              <div class="text-caption text-medium-emphasis mt-4">订阅样本 {{ state.profile.value?.subscription_count || 0 }} 条</div>
            </VCardText>
          </VCard>
        </section>

        <section v-show="activeTab === 'weights'" class="ar-page__pane">
          <VAlert type="info" variant="tonal" class="mb-3">权重配置在此只读展示，请进入 Config 修改。</VAlert>
          <div class="ar-page__weights">
            <div v-for="(value, key) in weights" :key="key" class="ar-page__weight"><span>{{ weightLabel(key) }}</span><VProgressLinear :model-value="Number(value) * 100" color="primary" height="8" rounded /><strong>{{ formatWeight(value) }}</strong></div>
          </div>
          <VBtn color="primary" variant="tonal" prepend-icon="mdi-cog-outline" class="mt-4" @click="emit('switch')">进入设置</VBtn>
        </section>

        <section v-show="activeTab === 'archive'" class="ar-page__pane">
          <VEmptyState v-if="!archiveEntries.length" icon="mdi-archive-outline" title="暂无归档" text="忽略的推荐会保留原排名和恢复信息。" />
          <div v-else class="ar-page__archive-list">
            <VCard v-for="entry in archiveEntries" :key="entry.candidate_id" variant="outlined" class="ar-page__archive-card">
              <VCardItem>
                <VCardTitle class="text-subtitle-2">{{ entry.recommendation?.title || entry.candidate_id }}</VCardTitle>
                <VCardSubtitle>原排名 #{{ entry.original_rank }} · {{ formatTime(entry.archived_at) }}</VCardSubtitle>
                <template #append>
                  <VBtn size="small" variant="tonal" color="primary" class="mr-1" @click="runAction(() => state.restore(entry.candidate_id), '推荐已恢复')">恢复</VBtn>
                  <VBtn icon="mdi-delete-outline" size="small" variant="text" color="error" :aria-label="`删除归档 ${entry.candidate_id}`" @click="runAction(() => state.deleteArchive(entry.candidate_id), '归档记录已删除')" />
                </template>
              </VCardItem>
            </VCard>
          </div>
        </section>

        <section v-show="activeTab === 'history'" class="ar-page__pane">
          <div class="ar-page__table-wrap">
            <VTable density="compact" fixed-header height="420">
              <thead><tr><th>时间</th><th>状态</th><th>候选</th><th>推荐</th><th>Agent</th><th>自动订阅</th><th>失败原因</th></tr></thead>
              <tbody>
                <tr v-for="run in state.history.value" :key="`${run.run_id}-${run.finished_at}`">
                  <td>{{ formatTime(run.finished_at || run.started_at) }}</td>
              <td><VChip size="x-small" :color="statusMetaFor(run.status).color" variant="tonal">{{ statusMetaFor(run.status).text }}</VChip></td>
                  <td>{{ run.metrics?.candidate_count ?? '—' }}</td>
                  <td>{{ run.metrics?.final_count ?? '—' }}</td>
                  <td>{{ run.metrics?.agent_calls ?? '—' }} 次</td>
                  <td>{{ run.metrics?.subscription_success_count ?? 0 }}</td>
                  <td class="ar-page__error-cell">{{ run.errors?.join('；') || run.message || '—' }}</td>
                </tr>
              </tbody>
            </VTable>
          </div>
          <VPagination v-model="historyPage" :length="historyPages" density="compact" total-visible="7" class="mt-3" @update:model-value="changeHistoryPage" />
          <span class="d-none">page_size={{ historyPageSize }}</span>
        </section>
      </template>
    </div>

    <VDialog v-model="clearDialog" max-width="480">
      <VCard>
        <VCardTitle>清除当前画像？</VCardTitle>
        <VCardText>会级联删除当前画像和榜单，但不会删除 MoviePilot 订阅、订阅任务、归档或全局配置。</VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="clearDialog = false">取消</VBtn><VBtn color="error" variant="flat" @click="runAction(async () => { await state.clearProfile(); clearDialog = false }, '画像与榜单已清除')">清除画像</VBtn></VCardActions>
      </VCard>
    </VDialog>
    <VSnackbar v-model="snackbar.show" :color="snackbar.color">{{ snackbar.message }}</VSnackbar>
  </div>
</template>

<style scoped>
.ar-page { width: min(1280px, calc(100vw - 24px)); max-width: 100%; height: min(820px, calc(100dvh - 24px)); display: flex; flex-direction: column; overflow: hidden; overflow-x: hidden; }
.ar-page__toolbar { flex: 0 0 auto; background: rgb(var(--v-theme-surface)); }
.ar-page :deep(.v-btn--icon) { min-width: 40px; min-height: 40px; }
.ar-page__heading { min-width: 0; }
.ar-page__user { width: 150px; }
.ar-page__tabs { flex: 0 0 auto; }
.ar-page__content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 16px; }
.ar-page__pane { min-height: 100%; }
.ar-page__ranking, .ar-page__archive-list { display: flex; flex-direction: column; gap: 9px; }
.ar-page__rank-item { min-height: 76px; display: grid; grid-template-columns: 34px 54px minmax(0, 1fr) auto auto; gap: 12px; align-items: center; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.ar-page__poster { width: 54px; height: 78px; display: grid; place-items: center; overflow: hidden; border-radius: 5px; color: rgba(var(--v-theme-on-surface), .4); background: rgba(var(--v-theme-on-surface), .05); }
.ar-page__poster :deep(.v-img) { width: 100%; height: 100%; }
.ar-page__poster-error { width: 100%; height: 100%; display: grid; place-items: center; }
.ar-page__rank { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); font-weight: 700; }
.ar-page__rank-main { min-width: 0; }
.ar-page__rank-actions { display: flex; overflow-x: auto; padding-bottom: 2px; }
.ar-page__section-card, .ar-page__archive-card { border-radius: 8px; }
.ar-page__chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ar-page__weights { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 20px; }
.ar-page__weight { display: grid; grid-template-columns: 140px minmax(0, 1fr) 42px; gap: 10px; align-items: center; font-size: 12px; }
.ar-page__table-wrap { max-width: 100%; overflow-x: auto; }
.ar-page__error-cell { min-width: 260px; max-width: 380px; white-space: normal; overflow-wrap: anywhere; line-height: 1.45; }
@media (max-width: 760px) {
  .ar-page { width: min(100%, calc(100vw - 12px)); height: min(860px, calc(100dvh - 12px)); }
  .ar-page__toolbar :deep(.v-toolbar__content) { height: auto !important; min-height: 64px; flex-wrap: wrap; overflow: visible; padding-block: 6px; }
  .ar-page__toolbar :deep(.v-spacer) { display: none; }
  .ar-page__heading { order: 1; flex: 1 1 180px; }
  .ar-page__toolbar :deep(.v-btn--icon) { order: 2; }
  .ar-page__user { order: 3; width: calc(100% - 24px); margin: 6px 12px; }
  .ar-page__content { padding: 10px; }
  .ar-page__rank-item { grid-template-columns: 30px 54px minmax(0, 1fr); gap: 8px; }
  .ar-page__rank-actions { grid-column: 2 / -1; justify-content: flex-end; }
  .ar-page__weights { grid-template-columns: 1fr; }
  .ar-page__weight { grid-template-columns: 120px minmax(0, 1fr) 42px; }
}
@media (max-width: 390px) {
  .ar-page { width: 100%; height: calc(100dvh - 4px); }
  .ar-page__brand-icon { display: none; }
  .ar-page__heading { flex: 1 1 150px; margin-left: 10px; }
  .ar-page__heading .text-h6 { font-size: 1rem !important; }
  .ar-page__user { width: calc(100% - 16px); margin-inline: 8px; }
  .ar-page__content { padding: 8px; }
  .ar-page__rank-item { padding-inline: 8px; grid-template-columns: 26px 48px minmax(0, 1fr); }
  .ar-page__poster { width: 48px; height: 70px; }
  .ar-page__weight { grid-template-columns: 104px minmax(0, 1fr) 42px; gap: 6px; }
}
</style>
