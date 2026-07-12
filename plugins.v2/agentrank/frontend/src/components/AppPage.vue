<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAgentRankState } from './useAgentRankState'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
})
const emit = defineEmits(['action', 'switch'])

const state = useAgentRankState(props.api)
const {
  options,
  users,
  selectedUser,
  overview,
  board,
  profile,
  history,
  loading,
  error,
  isRunning,
} = state

const clearDialog = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success', undo: false })
const lastArchivedId = ref('')
const initialized = ref(false)

const recommendations = computed(() => board.value?.recommendations?.slice(0, 10) || [])
const archiveEntries = computed(() => overview.value?.archive?.entries || [])
const weights = computed(() => options.value?.config?.weights || {})
const generatedAt = computed(() => board.value?.generated_at || overview.value?.latest_run?.finished_at || '')
const boardStatus = computed(() => board.value?.status || 'idle')

const statusMeta = computed(() => {
  const map = {
    idle: { text: '待生成', color: 'default', icon: 'mdi-clock-outline' },
    running: { text: '运行中', color: 'primary', icon: 'mdi-loading mdi-spin' },
    success: { text: '已完成', color: 'success', icon: 'mdi-check-circle-outline' },
    sample_insufficient: { text: '样本不足', color: 'warning', icon: 'mdi-database-alert-outline' },
    candidate_insufficient: { text: '候选不足', color: 'warning', icon: 'mdi-compass-off-outline' },
    recommendation_incomplete: { text: '榜单不足', color: 'warning', icon: 'mdi-format-list-numbered' },
    agent_failed: { text: 'Agent失败', color: 'error', icon: 'mdi-robot-confused-outline' },
    validation_failed: { text: '校验失败', color: 'error', icon: 'mdi-shield-alert-outline' },
    subscription_partial_failed: { text: '部分订阅失败', color: 'warning', icon: 'mdi-alert-circle-outline' },
  }
  return map[boardStatus.value] || { text: boardStatus.value, color: 'info', icon: 'mdi-information-outline' }
})

const stateMessage = computed(() => {
  if (error.value) return error.value.message
  const messages = {
    sample_insufficient: '当前用户需要更多订阅样本，旧榜单不会被覆盖。',
    candidate_insufficient: '当前发现来源没有足够候选，请检查来源设置。',
    recommendation_incomplete: `本轮仅生成 ${recommendations.value.length} 条安全推荐。`,
    agent_failed: '本轮 Agent 调用失败，正在展示上一次成功榜单。',
    validation_failed: '本轮输出未通过安全校验，旧榜单已保留。',
    subscription_partial_failed: '部分自动订阅失败，成功项不受影响。',
  }
  return messages[boardStatus.value] || board.value?.message || ''
})

function formatTime(value) {
  if (!value) return '尚未生成'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return { movie: '电影', tv: '剧集', anime: '动漫' }[value] || '媒体'
}

function sourceLabel(item) {
  const sources = item?.sources || Object.keys(item?.source_ids || {})
  return sources.length ? sources.join(' · ') : 'MP发现'
}

function posterSource(item) {
  return item?.poster_path || ''
}

async function initialize() {
  try {
    await state.loadOptions()
    if (selectedUser.value) await state.loadUserData()
  } catch (_) {
    // 共享状态已保存可见错误。
  } finally {
    initialized.value = true
  }
}

async function refreshBoard() {
  try {
    await state.refresh()
    snackbar.value = { show: true, message: '榜单刷新已完成', color: 'success', undo: false }
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '榜单刷新失败', color: 'error', undo: false }
  }
}

async function subscribeItem(candidateId) {
  try {
    const result = await state.subscribe(candidateId)
    snackbar.value = { show: true, message: result?.message || '订阅操作已完成', color: 'success', undo: false }
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '订阅失败', color: 'error', undo: false }
  }
}

async function archiveItem(candidateId) {
  try {
    await state.archive(candidateId)
    lastArchivedId.value = candidateId
    snackbar.value = { show: true, message: '已忽略该推荐', color: 'success', undo: true }
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '忽略失败', color: 'error', undo: false }
  }
}

async function undoArchive() {
  if (!lastArchivedId.value) return
  try {
    await state.restore(lastArchivedId.value)
    snackbar.value = { show: true, message: '已撤销忽略', color: 'success', undo: false }
    lastArchivedId.value = ''
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '撤销失败', color: 'error', undo: false }
  }
}

async function confirmClearProfile() {
  try {
    await state.clearProfile()
    clearDialog.value = false
    snackbar.value = { show: true, message: '画像与榜单已清除', color: 'success', undo: false }
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '清除画像失败', color: 'error', undo: false }
  }
}

watch(selectedUser, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  try { await state.loadUserData(value) } catch (_) { /* 可见错误由共享状态承载 */ }
})

onMounted(initialize)
</script>

<template>
  <div class="ar-app-page">
    <VCard flat class="ar-app-page__card">
      <VToolbar density="comfortable" class="ar-app-page__toolbar">
        <VAvatar color="primary" variant="tonal" rounded="lg" size="40" class="ms-3 me-3">
          <VIcon icon="mdi-brain" />
        </VAvatar>
        <div class="ar-app-page__heading">
          <div class="text-h6">Agent榜单中心</div>
          <div class="text-caption text-medium-emphasis">最近生成：{{ formatTime(generatedAt) }}</div>
        </div>
        <VChip :color="statusMeta.color" variant="tonal" size="small" class="ar-app-page__status ms-3">
          <VIcon :icon="statusMeta.icon" size="16" class="mr-1" />{{ statusMeta.text }}
        </VChip>
        <VSpacer />
        <VSelect v-if="users.length > 1" v-model="selectedUser" :items="users" label="用户" density="compact" variant="outlined" hide-details class="ar-app-page__user" aria-label="切换推荐用户" />
        <VBtn icon="mdi-refresh" variant="text" :loading="loading.action === 'refresh' || loading.data" :disabled="isRunning || !selectedUser" aria-label="刷新榜单" @click="refreshBoard" />
        <VBtn icon="mdi-account-remove-outline" variant="text" color="error" :disabled="!profile?.run_id" aria-label="清除画像" @click="clearDialog = true" />
        <VBtn icon="mdi-cog-outline" variant="text" aria-label="打开设置" @click="emit('switch')" />
      </VToolbar>
      <VDivider />

      <div v-if="loading.options && !initialized" class="ar-app-page__state">
        <VSkeletonLoader type="article, article, article" width="100%" />
      </div>
      <div v-else-if="!users.length" class="ar-app-page__state">
        <VEmptyState icon="mdi-account-alert-outline" title="尚未配置参与用户" text="请先打开设置，选择参与推荐用户和默认用户。">
          <template #actions><VBtn color="primary" variant="tonal" prepend-icon="mdi-cog-outline" @click="emit('switch')">打开设置</VBtn></template>
        </VEmptyState>
      </div>
      <div v-else class="ar-app-page__content">
        <VAlert v-if="stateMessage" :type="['agent_failed', 'validation_failed'].includes(boardStatus) ? 'error' : 'warning'" variant="tonal" class="ar-app-page__alert">{{ stateMessage }}</VAlert>

        <main class="ar-app-page__layout">
          <section class="ar-app-page__ranking" aria-label="Top 10 推荐榜单">
            <div class="ar-app-page__section-head">
              <div>
                <div class="text-subtitle-1 font-weight-bold">个性化 Top 10</div>
                <div class="text-caption text-medium-emphasis">保持 Agent 最终顺序，仅展示通过安全校验的候选</div>
              </div>
              <VChip size="small" variant="outlined">{{ recommendations.length }} / 10</VChip>
            </div>

            <VSkeletonLoader v-if="loading.data" type="list-item-avatar-three-line@5" />
            <VEmptyState v-else-if="!recommendations.length" icon="mdi-format-list-numbered" title="推荐榜单尚未生成" text="点击刷新，Agent 将基于当前用户订阅与 MP 发现候选生成榜单。" />
            <div v-else class="ar-app-page__list">
              <article v-for="item in recommendations" :key="item.candidate_id" class="ar-app-page__item">
                <div class="ar-app-page__rank" :class="{ 'ar-app-page__rank--top': item.rank <= 3 }">{{ item.rank }}</div>
                <div class="ar-app-page__poster">
                  <VImg v-if="posterSource(item)" :src="posterSource(item)" :alt="`${item.title} 海报`" cover />
                  <VIcon v-else icon="mdi-image-off-outline" size="30" />
                </div>
                <div class="ar-app-page__item-main">
                  <div class="ar-app-page__title-row">
                    <div class="ar-app-page__title">{{ item.title }}</div>
                    <VChip size="x-small" variant="tonal">{{ mediaTypeLabel(item.media_type) }}</VChip>
                  </div>
                  <div class="ar-app-page__meta">{{ item.year || '年份未知' }} · {{ sourceLabel(item) }}</div>
                  <div class="ar-app-page__summary">{{ item.summary }}</div>
                  <div class="ar-app-page__tags">
                    <VChip v-for="tag in item.match_tags || []" :key="tag" size="x-small" variant="outlined">{{ tag }}</VChip>
                    <VChip size="x-small" color="primary" variant="tonal">置信度 {{ item.confidence }}%</VChip>
                  </div>
                </div>
                <div class="ar-app-page__item-actions">
                  <VTooltip text="订阅推荐"><template #activator="{ props: tipProps }"><VBtn v-bind="tipProps" icon="mdi-plus-circle-outline" color="primary" variant="tonal" size="small" min-width="40" height="40" :loading="loading.action === 'subscribe'" :aria-label="`订阅 ${item.title}`" @click="subscribeItem(item.candidate_id)" /></template></VTooltip>
                  <VTooltip text="忽略推荐"><template #activator="{ props: tipProps }"><VBtn v-bind="tipProps" icon="mdi-eye-off-outline" variant="text" size="small" min-width="40" height="40" :loading="loading.action === 'archive'" :aria-label="`忽略 ${item.title}`" @click="archiveItem(item.candidate_id)" /></template></VTooltip>
                </div>
              </article>
            </div>
          </section>

          <aside class="ar-app-page__aside">
            <VExpansionPanels multiple variant="accordion" :model-value="[0, 1]">
              <VExpansionPanel>
                <VExpansionPanelTitle><VIcon icon="mdi-account-heart-outline" color="primary" class="mr-2" />画像摘要</VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div class="text-body-2 mb-3">{{ profile?.summary || '尚未生成用户画像' }}</div>
                  <div class="ar-app-page__tags"><VChip v-for="tag in profile?.tags || []" :key="tag" size="small" color="primary" variant="tonal">{{ tag }}</VChip></div>
                  <div class="text-caption text-medium-emphasis mt-3">订阅样本 {{ profile?.subscription_count || 0 }} 条</div>
                </VExpansionPanelText>
              </VExpansionPanel>
              <VExpansionPanel>
                <VExpansionPanelTitle><VIcon icon="mdi-tune-vertical" color="primary" class="mr-2" />权重摘要</VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div v-for="(value, key) in weights" :key="key" class="ar-app-page__weight-row"><span>{{ key.replace('_weight', '') }}</span><VProgressLinear :model-value="Number(value) * 100" color="primary" height="6" rounded /><strong>{{ Number(value).toFixed(1) }}</strong></div>
                  <VBtn block variant="text" color="primary" prepend-icon="mdi-cog-outline" class="mt-2" @click="emit('switch')">进入设置</VBtn>
                </VExpansionPanelText>
              </VExpansionPanel>
              <VExpansionPanel>
                <VExpansionPanelTitle><VIcon icon="mdi-archive-outline" color="primary" class="mr-2" />最近归档</VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div v-if="!archiveEntries.length" class="text-caption text-medium-emphasis">暂无忽略记录</div>
                  <div v-for="entry in archiveEntries.slice(0, 5)" :key="entry.candidate_id" class="ar-app-page__archive-row"><span>{{ entry.recommendation?.title || entry.candidate_id }}</span><VBtn size="small" variant="text" @click="state.restore(entry.candidate_id)">恢复</VBtn></div>
                </VExpansionPanelText>
              </VExpansionPanel>
              <VExpansionPanel>
                <VExpansionPanelTitle><VIcon icon="mdi-history" color="primary" class="mr-2" />运行历史</VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div v-if="!history.length" class="text-caption text-medium-emphasis">暂无运行记录</div>
                  <div v-for="run in history.slice(0, 5)" :key="`${run.run_id}-${run.finished_at}`" class="ar-app-page__history-row"><VChip size="x-small" variant="tonal">{{ run.status }}</VChip><span>{{ formatTime(run.finished_at || run.started_at) }}</span></div>
                </VExpansionPanelText>
              </VExpansionPanel>
            </VExpansionPanels>
          </aside>
        </main>
      </div>
    </VCard>

    <VDialog v-model="clearDialog" max-width="480">
      <VCard>
        <VCardTitle class="d-flex align-center"><VIcon icon="mdi-alert-outline" color="error" class="mr-2" />清除当前画像？</VCardTitle>
        <VCardText>将级联删除当前用户画像与推荐榜单，但不会删除 MoviePilot 原始订阅、已创建订阅任务、归档历史或插件全局配置。</VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="clearDialog = false">取消</VBtn><VBtn color="error" variant="flat" :loading="loading.action === 'profile/clear'" @click="confirmClearProfile">清除画像</VBtn></VCardActions>
      </VCard>
    </VDialog>

    <VSnackbar v-model="snackbar.show" :color="snackbar.color" timeout="5000">
      {{ snackbar.message }}
      <template v-if="snackbar.undo" #actions><VBtn variant="text" @click="undoArchive">撤销</VBtn></template>
    </VSnackbar>
  </div>
</template>

<style scoped>
.ar-app-page { width: 100%; max-width: 1440px; margin: 0 auto; padding: 16px; overflow-x: hidden; }
.ar-app-page__card { min-height: calc(100dvh - 96px); border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 16px; overflow: hidden; }
.ar-app-page__toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
.ar-app-page :deep(.v-btn--icon) { min-width: 40px; min-height: 40px; }
.ar-app-page__heading { min-width: 180px; }
.ar-app-page__user { max-width: 180px; min-width: 140px; margin-right: 4px; }
.ar-app-page__content { padding: 16px; }
.ar-app-page__alert { margin-bottom: 14px; }
.ar-app-page__layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 360px); gap: 16px; align-items: start; }
.ar-app-page__ranking, .ar-app-page__aside { min-width: 0; }
.ar-app-page__section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.ar-app-page__list { display: flex; flex-direction: column; gap: 10px; }
.ar-app-page__item { display: grid; grid-template-columns: 42px 92px minmax(0, 1fr) auto; gap: 14px; align-items: center; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; background: rgb(var(--v-theme-surface)); }
.ar-app-page__rank { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: rgba(var(--v-theme-on-surface), .06); font-size: 14px; font-weight: 700; }
.ar-app-page__rank--top { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); }
.ar-app-page__poster { width: 92px; height: 138px; display: grid; place-items: center; overflow: hidden; border-radius: 8px; color: rgba(var(--v-theme-on-surface), .4); background: rgba(var(--v-theme-on-surface), .05); }
.ar-app-page__poster :deep(.v-img) { width: 100%; height: 100%; }
.ar-app-page__item-main { min-width: 0; }
.ar-app-page__title-row { display: flex; align-items: flex-start; gap: 8px; }
.ar-app-page__title { min-width: 0; display: -webkit-box; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-size: 16px; font-weight: 700; line-height: 1.35; }
.ar-app-page__meta { margin-top: 5px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ar-app-page__summary { margin-top: 10px; font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ar-app-page__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.ar-app-page__item-actions { display: flex; flex-direction: column; gap: 6px; }
.ar-app-page__aside { position: sticky; top: 80px; }
.ar-app-page__weight-row { display: grid; grid-template-columns: 76px minmax(0, 1fr) 28px; gap: 8px; align-items: center; margin-bottom: 9px; font-size: 12px; }
.ar-app-page__archive-row, .ar-app-page__history-row { min-height: 40px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .6)); font-size: 12px; }
.ar-app-page__state { min-height: 480px; display: flex; align-items: center; justify-content: center; padding: 24px; }
@media (max-width: 960px) { .ar-app-page__layout { grid-template-columns: minmax(0, 1fr); } .ar-app-page__aside { position: static; } }
@media (max-width: 760px) {
  .ar-app-page { padding: 8px; }
  .ar-app-page__card { min-height: calc(100dvh - 72px); border-radius: 12px; }
  .ar-app-page__toolbar { min-height: 64px; }
  .ar-app-page__toolbar :deep(.v-toolbar__content) { min-height: 64px; height: auto !important; flex-wrap: wrap; overflow: visible; padding-block: 6px; }
  .ar-app-page__toolbar :deep(.v-spacer) { display: none; }
  .ar-app-page__heading { order: 1; flex: 1 1 180px; }
  .ar-app-page__toolbar :deep(.v-btn--icon) { order: 2; }
  .ar-app-page__status { order: 3; }
  .ar-app-page__user { order: 4; flex: 1 1 100%; max-width: none; margin: 6px 12px 0; }
  .ar-app-page__content { padding: 10px; }
  .ar-app-page__item { grid-template-columns: 30px 64px minmax(0, 1fr); gap: 9px; padding: 9px; align-items: start; }
  .ar-app-page__rank { width: 28px; height: 28px; font-size: 12px; }
  .ar-app-page__poster { width: 64px; height: 96px; }
  .ar-app-page__item-actions { grid-column: 2 / -1; flex-direction: row; justify-content: flex-end; }
  .ar-app-page__title { font-size: 14px; }
  .ar-app-page__summary { margin-top: 6px; font-size: 13px; }
  .ar-app-page__meta { white-space: normal; }
  .ar-app-page__section-head { align-items: flex-start; }
}
@media (max-width: 390px) {
  .ar-app-page { padding: 4px; }
  .ar-app-page__toolbar :deep(.v-avatar) { display: none; }
  .ar-app-page__heading { min-width: 0; flex: 1 1 150px; margin-left: 12px; }
  .ar-app-page__status { order: 7; margin: 6px 12px 0 !important; }
  .ar-app-page__user { margin-inline: 8px; }
  .ar-app-page__content { padding: 8px; }
  .ar-app-page__item { grid-template-columns: 26px 56px minmax(0, 1fr); gap: 7px; padding: 8px; }
  .ar-app-page__poster { width: 56px; height: 84px; }
}
</style>
