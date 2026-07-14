<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAgentRankState } from './useAgentRankState'
import RecommendationActions from './RecommendationActions.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
})
const state = useAgentRankState(props.api)
const snackbar = ref({ show: false, message: '', color: 'success' })

const topItems = computed(() => (state.board.value?.recommendations || []).slice(0, 5))
const fullBoardHref = computed(() => {
  const pluginId = String(props.config?.id || 'AgentRank').trim() || 'AgentRank'
  return `#/plugin-app/${encodeURIComponent(pluginId)}/main`
})
const status = computed(() => state.board.value?.status || 'idle')
const generatedAt = computed(() => state.board.value?.generated_at || '')
const statusMeta = computed(() => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
}[status.value] || { text: status.value, color: 'info' }))

function formatTime(value) {
  if (!value) return '尚未生成'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function initialize() {
  try {
    await state.loadOptions()
    if (props.config?.default_user && state.users.value.includes(props.config.default_user)) {
      state.selectedUser.value = props.config.default_user
    }
    if (state.selectedUser.value) await state.loadUserData()
  } catch (_) { /* 卡片内显示共享错误 */ }
}

async function refreshBoard() {
  try { await state.refresh() } catch (_) { /* 卡片内显示共享错误 */ }
}

async function runItemAction(action, successMessage) {
  try {
    await action()
    snackbar.value = { show: true, message: successMessage, color: 'success' }
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' }
  }
}

function openFullBoard() {
  window.location.hash = fullBoardHref.value.slice(1)
}

onMounted(initialize)
</script>

<template>
  <VCard variant="flat" class="ar-dashboard">
    <VCardItem>
      <template #prepend><VAvatar color="primary" variant="tonal" size="38"><VIcon icon="mdi-brain" /></VAvatar></template>
      <VCardTitle class="text-subtitle-1 font-weight-bold">Agent榜单中心 · Top 5</VCardTitle>
      <VCardSubtitle>{{ formatTime(generatedAt) }} · {{ statusMeta.text }}</VCardSubtitle>
      <template #append>
        <VBtn icon="mdi-refresh" variant="text" size="small" :disabled="!allowRefresh || state.isRunning.value" :loading="state.loading.action === 'refresh' || state.loading.data" aria-label="刷新仪表板" @click="refreshBoard" />
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="ar-dashboard__content">
      <VSkeletonLoader v-if="state.loading.data" type="list-item-three-line@3" />
      <VAlert v-else-if="state.error.value" type="error" variant="tonal">{{ state.error.value.message }}</VAlert>
      <VEmptyState v-else-if="!topItems.length" icon="mdi-format-list-numbered" title="推荐榜单尚未生成" text="打开完整榜单或点击刷新开始生成。" />
      <div v-else class="ar-dashboard__list">
          <div v-for="item in topItems" :key="item.candidate_id" class="ar-dashboard__item">
          <div class="ar-dashboard__rank">{{ item.rank }}</div>
          <div class="ar-dashboard__poster">
            <VImg v-if="item.poster_path" :src="item.poster_path" :alt="`${item.title} 海报`" cover>
              <template #error><div class="ar-dashboard__poster-error"><VIcon icon="mdi-image-off-outline" size="18" /></div></template>
            </VImg>
            <VIcon v-else icon="mdi-image-off-outline" size="18" />
          </div>
          <div class="ar-dashboard__main">
            <div class="font-weight-medium text-truncate">{{ item.title }}</div>
            <div class="text-caption text-truncate">推荐：{{ item.reason || item.summary }}</div>
            <div class="text-caption text-medium-emphasis text-truncate">简介：{{ item.summary }}</div>
          </div>
          <VChip size="x-small" color="primary" variant="tonal">{{ item.confidence }}%</VChip>
          <RecommendationActions
            :item="item"
            :loading-action="state.loading.action"
            @subscribe="candidateId => runItemAction(() => state.subscribe(candidateId), '订阅操作已完成')"
            @archive="candidateId => runItemAction(() => state.archive(candidateId), '已忽略推荐')"
          />
        </div>
      </div>
    </VCardText>
    <VDivider />
    <VCardActions>
      <VChip size="small" variant="tonal" :color="statusMeta.color">{{ statusMeta.text }}</VChip>
      <VSpacer />
      <VBtn variant="text" color="primary" prepend-icon="mdi-open-in-new" @click="openFullBoard">完整榜单</VBtn>
    </VCardActions>
    <VSnackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000">{{ snackbar.message }}</VSnackbar>
  </VCard>
</template>

<style scoped>
.ar-dashboard { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.ar-dashboard :deep(.v-btn--icon) { min-width: 40px; min-height: 40px; }
.ar-dashboard__content { min-height: 260px; }
.ar-dashboard__list { display: flex; flex-direction: column; gap: 7px; }
.ar-dashboard__item { min-height: 76px; display: grid; grid-template-columns: 28px 44px minmax(0, 1fr) auto auto; gap: 9px; align-items: center; padding: 6px 8px; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .75)); border-radius: 8px; overflow-x: auto; }
.ar-dashboard__rank { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .12); font-size: 12px; font-weight: 700; }
.ar-dashboard__poster { width: 44px; height: 64px; display: grid; place-items: center; overflow: hidden; border-radius: 4px; color: rgba(var(--v-theme-on-surface), .4); background: rgba(var(--v-theme-on-surface), .05); }
.ar-dashboard__poster :deep(.v-img) { width: 100%; height: 100%; }
.ar-dashboard__poster-error { width: 100%; height: 100%; display: grid; place-items: center; }
.ar-dashboard__main { min-width: 0; }
</style>
