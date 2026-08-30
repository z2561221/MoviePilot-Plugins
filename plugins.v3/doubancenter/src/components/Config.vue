<script setup>
import { onMounted } from 'vue'
import ConfigDashboardPane from './config/ConfigDashboardPane.vue'
import ConfigFolioPane from './config/ConfigFolioPane.vue'
import ConfigOverviewPane from './config/ConfigOverviewPane.vue'
import ConfigRankPane from './config/ConfigRankPane.vue'
import { useConfigForm } from './config/useConfigForm'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DoubanCenter' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const config = useConfigForm({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: () => props.initialConfig,
  emit,
})

onMounted(config.loadOverview)
</script>

<template>
  <div class="dc-config">
    <VCard flat class="dc-card">
      <VCardItem class="dc-header">
        <template #prepend><VAvatar color="primary" variant="tonal" size="44" rounded="lg" class="dc-header-avatar"><VIcon icon="mdi-book-open-page-variant-outline" size="24" /></VAvatar></template>
        <VCardTitle class="text-h6 dc-header-title">豆瓣中心</VCardTitle>
        <VCardSubtitle class="text-caption dc-header-subtitle">{{ config.currentMain.desc }}</VCardSubtitle>
        <template #append><VSwitch v-model="config.form.enabled" color="success" hide-details inset class="dc-enable-switch" :label="config.form.enabled ? '已启用' : '已停用'" /></template>
      </VCardItem>
      <VDivider />
      <div class="dc-body">
        <nav class="dc-nav">
          <VList density="comfortable" nav class="py-2 dc-nav-list">
            <VListItem v-for="item in config.mainTabs" :key="item.key" :active="config.activeMain === item.key" color="primary" rounded="lg" class="dc-nav-item" @click="config.selectMain(item.key)">
              <template #prepend><VIcon :icon="item.icon" class="dc-nav-icon" /></template>
              <VListItemTitle class="dc-nav-title">{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="dc-content">
          <div class="dc-subtabs">
            <button v-for="sub in config.currentSubs" :key="sub.key" type="button" class="dc-subtab" :class="{ 'dc-subtab--active': config.activeSub === sub.key }" @click="config.activeSub = sub.key"><VIcon :icon="sub.icon" size="18" class="mr-1" />{{ sub.title }}</button>
          </div>
          <VDivider />
          <div class="dc-window" :class="{ 'dc-window--overview': config.activeMain === 'overview' }">
            <ConfigOverviewPane v-show="config.activeSub === 'overview'" :config="config" />
            <ConfigRankPane :config="config" />
            <ConfigFolioPane :config="config" />
            <ConfigDashboardPane :config="config" />
          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dc-actions"><VSpacer /><VBtn variant="text" class="dc-action-btn" @click="emit('close')">取消</VBtn><VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" class="dc-action-btn dc-action-btn--save" @click="config.saveConfig">保存配置</VBtn></VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.dc-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.dc-card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; border-radius: 14px; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dc-header { padding: 14px 18px; }
.dc-header-subtitle { max-width: min(560px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-body { flex: 1 1 auto; min-height: 0; display: flex; }
.dc-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.dc-nav-item { margin: 2px 8px; }
.dc-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.dc-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.dc-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), .7); background: transparent; border: none; cursor: pointer; transition: background .15s, color .15s; white-space: nowrap; }
.dc-subtab:hover { background: rgba(var(--v-theme-primary), .08); color: rgb(var(--v-theme-primary)); }
.dc-subtab--active { background: rgba(var(--v-theme-primary), .14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.dc-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.dc-window--overview { overflow-y: hidden; }
.dc-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .dc-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .dc-card { height: min(860px, calc(100dvh - 16px)); }
  .dc-header-subtitle { max-width: 100%; }
  .dc-body { flex-direction: column; }
  .dc-nav { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .dc-nav::-webkit-scrollbar { display: none; }
  .dc-nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .dc-nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }
  .dc-nav-item :deep(.v-list-item-title) { white-space: nowrap; }
  .dc-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; scrollbar-width: none; padding: 6px 12px; }
  .dc-subtabs::-webkit-scrollbar { display: none; }
  .dc-subtab { flex: 0 0 auto; padding: 6px 12px; }
  .dc-actions { min-height: 44px; padding: 6px 10px; gap: 6px; }
  .dc-action-btn { min-height: 32px; font-size: 13px; }
  .dc-window--overview { overflow-y: auto; }
}
@media (max-height: 760px) {
  .dc-window--overview { overflow-y: auto; }
}
</style>
