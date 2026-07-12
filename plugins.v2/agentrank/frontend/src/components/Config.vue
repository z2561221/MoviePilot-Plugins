<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const defaults = {
  enabled: false,
  schedule_enabled: false,
  cron: '0 8 * * *',
  notify: true,
}
const form = reactive({ ...defaults })
const activeMain = ref('overview')

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical' },
  { key: 'filter', title: '条件筛选', icon: 'mdi-filter-outline' },
  { key: 'board', title: '榜单列表', icon: 'mdi-format-list-numbered' },
  { key: 'advanced', title: '高级选项', icon: 'mdi-shield-cog-outline' },
]
const currentTitle = computed(
  () => mainTabs.find(item => item.key === activeMain.value)?.title || '运行总览',
)

watch(
  () => props.initialConfig,
  value => Object.assign(form, defaults, value || {}),
  { immediate: true, deep: true },
)

function saveConfig() {
  emit('save', { ...form })
}
</script>

<template>
  <div class="ar-config">
    <VCard flat class="ar-config__card">
      <VCardItem class="ar-config__header">
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-brain" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">Agent榜单中心</VCardTitle>
        <VCardSubtitle>配置用户画像、发现来源与推荐行为</VCardSubtitle>
        <template #append>
          <VSwitch v-model="form.enabled" color="success" hide-details inset label="启用插件" />
        </template>
      </VCardItem>
      <VDivider />
      <div class="ar-config__body">
        <nav class="ar-config__nav">
          <VList density="comfortable" nav class="ar-config__nav-list py-2">
            <VListItem
              v-for="item in mainTabs"
              :key="item.key"
              :active="activeMain === item.key"
              color="primary"
              rounded="lg"
              class="ar-config__nav-item"
              @click="activeMain = item.key"
            >
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="ar-config__content">
          <div class="ar-config__subtabs">
            <button class="ar-config__subtab ar-config__subtab--active" type="button">
              {{ currentTitle }}
            </button>
          </div>
          <VDivider />
          <div class="ar-config__window" :class="{ 'ar-config__window--overview': activeMain === 'overview' }">
            <div v-if="activeMain === 'overview'" class="ar-config__pane">
              <div class="text-subtitle-2 text-primary mb-3">运行链路</div>
              <VAlert type="info" variant="tonal" icon="mdi-transit-connection-variant">
                读取订阅 → 拉取发现候选 → Agent画像排序 → 校验并更新榜单
              </VAlert>
              <div class="text-subtitle-2 mt-5 mb-2">当前状态</div>
              <VChip color="info" variant="tonal">骨架已就绪</VChip>
            </div>
            <div v-else-if="activeMain === 'basic'" class="ar-config__pane">
              <div class="text-subtitle-2 text-primary mb-3">基础设置</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VSwitch v-model="form.schedule_enabled" color="success" label="周期运行" hide-details inset />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.cron" label="运行周期" density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="6">
                  <VSwitch v-model="form.notify" color="info" label="发送通知" hide-details inset />
                </VCol>
              </VRow>
            </div>
            <div v-else class="ar-config__pane">
              <VAlert type="info" variant="tonal">该配置区将在对应实施阶段完成。</VAlert>
            </div>
          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="ar-config__actions">
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">
          保存配置
        </VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.ar-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.ar-config__card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; overflow: hidden; border-radius: 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.ar-config__header { padding: 14px 18px; }
.ar-config__body { flex: 1 1 auto; min-height: 0; display: flex; }
.ar-config__nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.ar-config__nav-list { width: 100%; }
.ar-config__nav-item { margin: 2px 8px; }
.ar-config__content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.ar-config__subtabs { display: flex; padding: 8px 12px; }
.ar-config__subtab { padding: 6px 14px; border: 0; border-radius: 8px; background: transparent; color: rgba(var(--v-theme-on-surface), .7); white-space: nowrap; }
.ar-config__subtab--active { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); font-weight: 600; }
.ar-config__window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.ar-config__window--overview { overflow-y: hidden; }
.ar-config__pane { padding: 18px 20px; }
.ar-config__actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .ar-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .ar-config__card { height: min(860px, calc(100dvh - 16px)); }
  .ar-config__body { flex-direction: column; }
  .ar-config__nav { width: 100%; flex: 0 0 auto; border-right: 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; }
  .ar-config__nav-list { display: flex; flex-wrap: nowrap; min-width: max-content; padding: 8px 12px !important; }
  .ar-config__nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; }
  .ar-config__window--overview { overflow-y: auto; }
}
</style>
