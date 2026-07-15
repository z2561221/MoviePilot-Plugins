<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAgentRankState } from './useAgentRankState'
import RecommendationActions from './RecommendationActions.vue'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['action', 'switch', 'close'])
const state = useAgentRankState(props.api)

const activeTab = ref('board')
const snackbar = ref({ show: false, message: '', color: 'success' })
const historyPage = ref(1)
const initialized = ref(false)
const historyPageSize = 10

const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 10) || [])
const archiveEntries = computed(() => state.overview.value?.archive?.entries || [])
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)))
const positiveTags = computed(() => state.profile.value?.tags || [])
const negativeTags = computed(() => state.profile.value?.negative_tags || [])
const profileStats = computed(() => [
  { label: '订阅样本', value: state.profile.value?.subscription_count || 0, suffix: '条', icon: 'mdi-database-check-outline' },
  { label: '偏好标签', value: positiveTags.value.length, suffix: '个', icon: 'mdi-heart-outline' },
  { label: '避雷标签', value: negativeTags.value.length, suffix: '个', icon: 'mdi-shield-alert-outline' },
])
const boardMatchTags = computed(() => {
  const counts = new Map()
  recommendations.value.forEach(item => {
    const tags = item.match_tags || []
    tags.forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1))
  })
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
    .slice(0, 10)
    .map(([tag, count]) => ({ tag, count }))
})
const profileRunId = computed(() => String(state.profile.value?.run_id || '').slice(0, 8) || '—')
const detailStats = computed(() => [
  { label: '榜单条目', value: recommendations.value.length, suffix: '部', icon: 'mdi-format-list-numbered' },
  { label: '画像样本', value: state.profile.value?.subscription_count || 0, suffix: '条', icon: 'mdi-account-heart-outline' },
  { label: '忽略归档', value: archiveEntries.value.length, suffix: '部', icon: 'mdi-archive-outline' },
])

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

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'archive', title: '忽略归档', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
]

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return ({ movie: '电影', tv: '剧集', anime: '动漫' })[value] || value || '未知'
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
      <VAvatar color="primary" variant="tonal" size="42" rounded="lg" class="ar-page__brand ms-4 me-3">
        <VIcon icon="mdi-brain" size="24" />
      </VAvatar>
      <div class="ar-page__heading">
        <div class="ar-page__title">Agent榜单中心</div>
        <div class="ar-page__subtitle">推荐结果、用户画像与运行记录</div>
      </div>
      <VSpacer />
      <VSelect
        v-if="state.users.value.length > 1"
        v-model="state.selectedUser.value"
        :items="state.users.value"
        density="compact"
        variant="outlined"
        hide-details
        label="用户"
        class="ar-page__user"
      />
      <VBtn
        icon="mdi-refresh"
        variant="text"
        :loading="state.loading.action === 'refresh' || state.loading.data"
        :disabled="state.isRunning.value"
        aria-label="刷新详情"
        @click="runAction(state.refresh, '榜单刷新已完成')"
      />
      <VBtn icon="mdi-cog-outline" variant="text" aria-label="打开设置" @click="emit('switch')" />
      <VBtn icon="mdi-close" variant="text" aria-label="关闭详情" class="me-2" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="ar-page__summary-bar">
      <div v-for="stat in detailStats" :key="stat.label" class="ar-page__stat">
        <VIcon :icon="stat.icon" color="primary" size="20" />
        <div>
          <div class="ar-page__stat-value">{{ stat.value }}<span>{{ stat.suffix }}</span></div>
          <div class="ar-page__stat-label">{{ stat.label }}</div>
        </div>
      </div>
      <VChip
        :color="state.isRunning.value ? 'primary' : 'success'"
        variant="tonal"
        size="small"
        :prepend-icon="state.isRunning.value ? 'mdi-loading' : 'mdi-check-circle-outline'"
        class="ar-page__runtime-chip"
      >
        {{ state.isRunning.value ? '正在生成' : '运行就绪' }}
      </VChip>
    </div>

    <VTabs v-model="activeTab" color="primary" density="compact" class="ar-page__tabs" show-arrows>
      <VTab v-for="tab in tabs" :key="tab.key" :value="tab.key" class="text-none">
        <VIcon :icon="tab.icon" size="18" class="mr-1" />{{ tab.title }}
      </VTab>
    </VTabs>
    <VDivider />

    <div class="ar-page__content">
      <VAlert v-if="state.error.value" type="error" variant="tonal" class="mb-3">{{ state.error.value.message }}</VAlert>
      <VSkeletonLoader v-if="state.loading.data" type="list-item-avatar-three-line@5" />

      <template v-else>
        <section v-show="activeTab === 'board'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">个性推荐榜单</div>
              <div class="ar-page__section-desc">Agent 根据订阅画像，从发现候选中挑出的 Top 10。</div>
            </div>
            <VChip size="small" color="primary" variant="tonal">{{ recommendations.length }} 部</VChip>
          </div>

          <VEmptyState
            v-if="!recommendations.length"
            icon="mdi-format-list-numbered"
            title="推荐榜单尚未生成"
            text="点击右上角刷新，为当前用户生成 Top 10。"
          />
          <div v-else class="ar-page__ranking">
            <article v-for="item in recommendations" :key="item.candidate_id" class="ar-page__rank-item">
              <div class="ar-page__rank" :class="{ 'ar-page__rank--top': item.rank <= 3 }">{{ item.rank }}</div>
              <div class="ar-page__poster">
                <VImg v-if="item.poster_path" :src="item.poster_path" :alt="`${item.title} 海报`" cover>
                  <template #error><div class="ar-page__poster-error"><VIcon icon="mdi-image-off-outline" size="26" /></div></template>
                </VImg>
                <VIcon v-else icon="mdi-image-off-outline" size="26" />
              </div>
              <div class="ar-page__rank-main">
                <div class="ar-page__title-row">
                  <div class="ar-page__media-title">{{ item.title }}</div>
                  <VChip size="x-small" variant="tonal">{{ mediaTypeLabel(item.media_type) }}</VChip>
                </div>
                <div class="ar-page__meta-row">
                  <span>{{ item.year || '年份未知' }}</span>
                  <span>置信度 {{ item.confidence }}%</span>
                </div>
                <div class="ar-page__rank-copy">
                  <span class="ar-page__copy-label">推荐</span>
                  <span>{{ item.reason || item.summary || '等待 Agent 补充推荐理由' }}</span>
                </div>
                <div class="ar-page__rank-copy ar-page__rank-copy--muted">
                  <span class="ar-page__copy-label">简介</span>
                  <span>{{ item.summary || '暂无简介' }}</span>
                </div>
              </div>
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
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">用户画像</div>
              <div class="ar-page__section-desc">用订阅样本描述偏好、避雷方向与本轮榜单命中。</div>
            </div>
            <VChip size="small" variant="tonal" prepend-icon="mdi-clock-outline">{{ formatTime(state.profile.value?.generated_at) }}</VChip>
          </div>

          <VCard variant="outlined" class="ar-page__section-card">
            <VCardItem class="ar-page__profile-head">
              <template #prepend>
                <VAvatar color="primary" variant="tonal" size="44"><VIcon icon="mdi-account-heart-outline" /></VAvatar>
              </template>
              <VCardTitle class="text-subtitle-1 font-weight-bold">画像摘要</VCardTitle>
              <VCardSubtitle>用户 {{ state.selectedUser.value || '—' }} · 运行 {{ profileRunId }}</VCardSubtitle>
            </VCardItem>
            <VDivider />
            <VCardText class="ar-page__profile-body">
              <div class="ar-page__profile-summary-panel">
                <div class="ar-page__profile-label"><VIcon icon="mdi-text-box-search-outline" size="18" />口味摘要</div>
                <div class="ar-page__profile-summary">{{ state.profile.value?.summary || '尚未生成用户画像' }}</div>
              </div>

              <div class="ar-page__profile-metrics">
                <div v-for="stat in profileStats" :key="stat.label" class="ar-page__profile-metric">
                  <VIcon :icon="stat.icon" color="primary" size="19" />
                  <div><strong>{{ stat.value }}<span>{{ stat.suffix }}</span></strong><small>{{ stat.label }}</small></div>
                </div>
              </div>

              <div class="ar-page__profile-groups">
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label"><VIcon icon="mdi-heart-outline" size="18" />偏好标签</div>
                  <div class="ar-page__chips">
                    <VChip v-for="tag in positiveTags" :key="tag" color="primary" variant="tonal" size="small">{{ tag }}</VChip>
                    <span v-if="!positiveTags.length" class="text-caption text-medium-emphasis">暂无偏好标签</span>
                  </div>
                </div>
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label ar-page__profile-label--negative"><VIcon icon="mdi-shield-alert-outline" size="18" />避雷标签</div>
                  <div class="ar-page__chips">
                    <VChip v-for="tag in negativeTags" :key="tag" color="error" variant="tonal" size="small">{{ tag }}</VChip>
                    <span v-if="!negativeTags.length" class="text-caption text-medium-emphasis">暂无避雷标签</span>
                  </div>
                </div>
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label"><VIcon icon="mdi-target-account" size="18" />本轮命中</div>
                  <div class="ar-page__chips">
                    <VChip v-for="item in boardMatchTags" :key="item.tag" color="info" variant="tonal" size="small">
                      {{ item.tag }}<span v-if="item.count > 1" class="ar-page__tag-count">×{{ item.count }}</span>
                    </VChip>
                    <span v-if="!boardMatchTags.length" class="text-caption text-medium-emphasis">暂无命中标签</span>
                  </div>
                </div>
              </div>
            </VCardText>
          </VCard>
        </section>

        <section v-show="activeTab === 'archive'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">忽略归档</div>
              <div class="ar-page__section-desc">保留被忽略条目的原排名，可随时恢复推荐。</div>
            </div>
            <VChip size="small" variant="tonal">{{ archiveEntries.length }} 部</VChip>
          </div>

          <VEmptyState v-if="!archiveEntries.length" icon="mdi-archive-outline" title="暂无忽略记录" text="榜单中点击忽略后，条目会出现在这里。" />
          <div v-else class="ar-page__archive-list">
            <VCard v-for="entry in archiveEntries" :key="entry.candidate_id" variant="outlined" class="ar-page__archive-card">
              <VCardItem>
                <template #prepend>
                  <div class="ar-page__archive-rank">#{{ entry.original_rank }}</div>
                </template>
                <VCardTitle class="text-subtitle-2 font-weight-bold">{{ entry.recommendation?.title || entry.candidate_id }}</VCardTitle>
                <VCardSubtitle>忽略于 {{ formatTime(entry.archived_at) }}</VCardSubtitle>
                <template #append>
                  <VBtn size="small" variant="tonal" color="primary" class="mr-1" prepend-icon="mdi-backup-restore" @click="runAction(() => state.restore(entry.candidate_id), '推荐已恢复')">恢复</VBtn>
                  <VBtn icon="mdi-delete-outline" size="small" variant="text" color="error" :aria-label="`删除归档 ${entry.candidate_id}`" @click="runAction(() => state.deleteArchive(entry.candidate_id), '归档记录已删除')" />
                </template>
              </VCardItem>
              <VCardText v-if="entry.recommendation?.summary" class="ar-page__archive-summary">{{ entry.recommendation.summary }}</VCardText>
            </VCard>
          </div>
        </section>

        <section v-show="activeTab === 'history'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">运行历史</div>
              <div class="ar-page__section-desc">查看候选数量、Agent 调用与自动订阅结果。</div>
            </div>
            <VChip size="small" variant="tonal">{{ state.historyMeta.value.total || 0 }} 次</VChip>
          </div>

          <VEmptyState v-if="!state.history.value.length" icon="mdi-history" title="暂无运行记录" text="榜单生成后，这里会记录每次执行结果。" />
          <template v-else>
            <VCard variant="outlined" class="ar-page__table-card">
              <div class="ar-page__table-wrap">
                <VTable density="compact" fixed-header height="430">
                  <thead><tr><th>时间</th><th>状态</th><th>候选</th><th>推荐</th><th>Agent</th><th>自动订阅</th><th>失败原因</th></tr></thead>
                  <tbody>
                    <tr v-for="run in state.history.value" :key="`${run.run_id}-${run.finished_at}`">
                      <td class="ar-page__time-cell">{{ formatTime(run.finished_at || run.started_at) }}</td>
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
            </VCard>
            <VPagination v-model="historyPage" :length="historyPages" density="compact" total-visible="7" class="mt-3" @update:model-value="changeHistoryPage" />
          </template>
          <span class="d-none">page_size={{ historyPageSize }}</span>
        </section>
      </template>
    </div>

    <VSnackbar v-model="snackbar.show" :color="snackbar.color">{{ snackbar.message }}</VSnackbar>
  </div>
</template>

<style scoped>
.ar-page { width: min(1240px, calc(100vw - 32px)); max-width: 100%; height: min(840px, calc(100dvh - 32px)); display: flex; flex-direction: column; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 14px; background: transparent; }
.ar-page__toolbar { flex: 0 0 auto; background: transparent; }
.ar-page :deep(.v-btn--icon) { min-width: 40px; min-height: 40px; }
.ar-page :deep(.v-tabs), .ar-page :deep(.v-table), .ar-page :deep(.v-skeleton-loader), .ar-page :deep(.v-empty-state) { background: transparent; }
.ar-page__table-wrap :deep(.v-table__wrapper > table > thead > tr > th) { background: rgba(var(--v-theme-on-surface), .018) !important; }
.ar-page__brand { flex: 0 0 auto; }
.ar-page__heading { min-width: 0; }
.ar-page__title { font-size: 1.08rem; font-weight: 700; line-height: 1.35; }
.ar-page__subtitle { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; }
.ar-page__user { width: 150px; margin-right: 4px; }
.ar-page__summary-bar { min-height: 68px; display: grid; grid-template-columns: repeat(3, minmax(140px, 1fr)) auto; align-items: center; gap: 10px; padding: 10px 16px; background: transparent; }
.ar-page__stat { min-width: 0; display: flex; align-items: center; gap: 10px; padding: 4px 10px; border-right: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .7)); }
.ar-page__stat-value { font-size: 17px; font-weight: 700; line-height: 1.2; }
.ar-page__stat-value span { margin-left: 2px; color: rgba(var(--v-theme-on-surface), .48); font-size: 11px; font-weight: 500; }
.ar-page__stat-label { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .55); font-size: 11px; }
.ar-page__runtime-chip { margin-inline: 8px; }
.ar-page__tabs { flex: 0 0 auto; min-height: 44px; background: transparent; }
.ar-page__content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 16px 18px 18px; background: transparent; }
.ar-page__pane { min-height: 100%; }
.ar-page__section-head { min-height: 46px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.ar-page__section-title { font-size: 15px; font-weight: 700; }
.ar-page__section-desc { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; line-height: 1.5; }
.ar-page__ranking, .ar-page__archive-list { display: flex; flex-direction: column; gap: 9px; }
.ar-page__rank-item { display: grid; grid-template-columns: 38px 64px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; background: transparent; transition: background .12s, border-color .12s; }
.ar-page__rank-item:hover { border-color: rgba(var(--v-theme-primary), .28); background: rgba(var(--v-theme-primary), .045); }
.ar-page__poster { width: 64px; height: 96px; display: grid; place-items: center; overflow: hidden; border-radius: 7px; color: rgba(var(--v-theme-on-surface), .4); background: rgba(var(--v-theme-on-surface), .05); }
.ar-page__poster :deep(.v-img) { width: 100%; height: 100%; }
.ar-page__poster-error { width: 100%; height: 100%; display: grid; place-items: center; }
.ar-page__rank { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; color: rgba(var(--v-theme-on-surface), .62); background: rgba(var(--v-theme-on-surface), .06); font-size: 13px; font-weight: 700; }
.ar-page__rank--top { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); }
.ar-page__rank-main { min-width: 0; }
.ar-page__title-row { display: flex; align-items: flex-start; gap: 8px; }
.ar-page__media-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 15px; font-weight: 700; }
.ar-page__meta-row { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 3px; color: rgba(var(--v-theme-on-surface), .52); font-size: 11px; }
.ar-page__rank-copy { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 7px; margin-top: 7px; font-size: 12px; line-height: 1.45; }
.ar-page__rank-copy--muted { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .62); }
.ar-page__copy-label { color: rgb(var(--v-theme-primary)); font-size: 11px; font-weight: 600; }
.ar-page__rank-actions { display: flex; align-items: center; overflow-x: auto; padding-bottom: 2px; }
.ar-page__section-card, .ar-page__archive-card, .ar-page__table-card { border-radius: 10px; background: transparent; }
.ar-page__profile-head { padding: 14px 16px; }
.ar-page__profile-body { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(270px, .65fr); gap: 12px; padding: 14px; }
.ar-page__profile-summary-panel, .ar-page__profile-metrics, .ar-page__profile-group { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .72)); border-radius: 9px; background: transparent; }
.ar-page__profile-summary-panel { min-height: 118px; padding: 12px 14px; }
.ar-page__profile-summary { margin-top: 8px; font-size: 14px; line-height: 1.7; }
.ar-page__profile-label { display: flex; align-items: center; gap: 6px; color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.ar-page__profile-label--negative { color: rgb(var(--v-theme-error)); }
.ar-page__profile-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; overflow: hidden; }
.ar-page__profile-metric { min-width: 0; display: flex; align-items: center; gap: 8px; padding: 10px; border-right: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .62)); }
.ar-page__profile-metric:last-child { border-right: 0; }
.ar-page__profile-metric strong { display: block; font-size: 17px; line-height: 1.2; }
.ar-page__profile-metric strong span { margin-left: 2px; color: rgba(var(--v-theme-on-surface), .48); font-size: 10px; font-weight: 500; }
.ar-page__profile-metric small { display: block; margin-top: 2px; color: rgba(var(--v-theme-on-surface), .55); font-size: 10px; white-space: nowrap; }
.ar-page__profile-groups { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.ar-page__profile-group { min-height: 108px; padding: 11px 12px; }
.ar-page__chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.ar-page__tag-count { margin-left: 3px; opacity: .66; font-size: 10px; }
.ar-page__archive-card :deep(.v-card-item) { padding: 12px 14px; }
.ar-page__archive-rank { min-width: 38px; height: 32px; display: grid; place-items: center; border-radius: 8px; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .1); font-size: 12px; font-weight: 700; }
.ar-page__archive-summary { padding-top: 0; color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; }
.ar-page__table-card { overflow: hidden; }
.ar-page__table-wrap { max-width: 100%; overflow-x: auto; }
.ar-page__table-wrap :deep(th) { font-size: 12px; font-weight: 700; }
.ar-page__table-wrap :deep(td) { font-size: 12px; }
.ar-page__time-cell { min-width: 150px; white-space: nowrap; }
.ar-page__error-cell { min-width: 240px; max-width: 360px; white-space: normal; overflow-wrap: anywhere; line-height: 1.45; }
@media (max-width: 900px) {
  .ar-page__summary-bar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ar-page__runtime-chip { grid-column: 1 / -1; justify-self: end; margin-top: -2px; }
  .ar-page__rank-item { grid-template-columns: 34px 60px minmax(0, 1fr); }
  .ar-page__poster { width: 60px; height: 90px; }
  .ar-page__rank-actions { grid-column: 2 / -1; justify-content: flex-end; }
  .ar-page__profile-body { grid-template-columns: 1fr; }
  .ar-page__profile-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ar-page__profile-group:last-child { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .ar-page { width: min(100%, calc(100vw - 12px)); height: min(880px, calc(100dvh - 12px)); }
  .ar-page__toolbar :deep(.v-toolbar__content) { height: auto !important; min-height: 66px; flex-wrap: wrap; overflow: visible; padding-block: 6px; }
  .ar-page__toolbar :deep(.v-spacer) { display: none; }
  .ar-page__brand { order: 1; }
  .ar-page__heading { order: 1; flex: 1 1 180px; }
  .ar-page__toolbar :deep(.v-btn--icon) { order: 2; }
  .ar-page__user { order: 3; width: calc(100% - 24px); margin: 6px 12px; }
  .ar-page__summary-bar { min-height: 60px; gap: 4px; padding: 8px 10px; }
  .ar-page__stat { gap: 6px; padding-inline: 6px; }
  .ar-page__stat :deep(.v-icon) { display: none; }
  .ar-page__runtime-chip { justify-self: stretch; justify-content: center; margin: 2px 4px 0; }
  .ar-page__content { padding: 12px 10px; }
  .ar-page__section-head { min-height: 42px; }
  .ar-page__rank-item { grid-template-columns: 30px 54px minmax(0, 1fr); gap: 8px; padding: 9px; }
  .ar-page__poster { width: 54px; height: 81px; }
  .ar-page__rank { width: 28px; height: 28px; }
  .ar-page__rank-actions { grid-column: 2 / -1; justify-content: flex-end; }
  .ar-page__profile-head :deep(.v-card-item__append) { align-self: flex-start; }
  .ar-page__profile-body { padding: 12px; }
  .ar-page__profile-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ar-page__profile-metric { justify-content: center; padding: 9px 6px; }
  .ar-page__profile-metric :deep(.v-icon) { display: none; }
  .ar-page__profile-groups { grid-template-columns: 1fr; }
  .ar-page__profile-group:last-child { grid-column: auto; }
}
@media (max-width: 430px) {
  .ar-page { width: 100%; height: calc(100dvh - 4px); border-radius: 10px; }
  .ar-page__brand { display: none; }
  .ar-page__heading { flex: 1 1 150px; margin-left: 10px; }
  .ar-page__title { font-size: 1rem; }
  .ar-page__subtitle { display: none; }
  .ar-page__summary-bar { grid-template-columns: repeat(3, 1fr); }
  .ar-page__stat { justify-content: center; text-align: center; }
  .ar-page__stat:last-of-type { border-right: none; }
  .ar-page__content { padding: 10px 8px; }
  .ar-page__rank-item { grid-template-columns: 26px 48px minmax(0, 1fr); gap: 7px; padding-inline: 7px; }
  .ar-page__poster { width: 48px; height: 72px; }
  .ar-page__rank-copy { grid-template-columns: 32px minmax(0, 1fr); }
  .ar-page__profile-head :deep(.v-card-item__prepend) { display: none; }
}
</style>
