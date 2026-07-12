<script setup>
import { computed, onMounted } from 'vue'
import { useAgentRankState } from './useAgentRankState'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
})
const emit = defineEmits(['action'])
const state = useAgentRankState(props.api)

const topItems = computed(() => (state.board.value?.recommendations || []).slice(0, 5))
const status = computed(() => state.board.value?.status || 'idle')
const generatedAt = computed(() => state.board.value?.generated_at || '')

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

onMounted(initialize)
</script>

<template>
  <VCard variant="flat" class="ar-dashboard">
    <VCardItem>
      <template #prepend><VAvatar color="primary" variant="tonal" size="38"><VIcon icon="mdi-brain" /></VAvatar></template>
      <VCardTitle class="text-subtitle-1 font-weight-bold">Agent榜单中心 · Top 5</VCardTitle>
      <VCardSubtitle>{{ formatTime(generatedAt) }} · {{ status }}</VCardSubtitle>
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
          <div class="ar-dashboard__main">
            <div class="font-weight-medium text-truncate">{{ item.title }}</div>
            <div class="text-caption text-medium-emphasis text-truncate">{{ item.summary }}</div>
          </div>
          <VChip size="x-small" color="primary" variant="tonal">{{ item.confidence }}%</VChip>
        </div>
      </div>
    </VCardText>
    <VDivider />
    <VCardActions>
      <VChip size="small" variant="tonal" :color="status === 'success' ? 'success' : 'info'">{{ status }}</VChip>
      <VSpacer />
      <VBtn variant="text" color="primary" prepend-icon="mdi-open-in-new" @click="emit('action', { type: 'open-app-page' })">完整榜单</VBtn>
    </VCardActions>
  </VCard>
</template>

<style scoped>
.ar-dashboard { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 16px; overflow: hidden; }
.ar-dashboard__content { min-height: 260px; }
.ar-dashboard__list { display: flex; flex-direction: column; gap: 7px; }
.ar-dashboard__item { min-height: 44px; display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 9px; align-items: center; padding: 6px 8px; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .75)); border-radius: 8px; }
.ar-dashboard__rank { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .12); font-size: 12px; font-weight: 700; }
.ar-dashboard__main { min-width: 0; }
</style>
