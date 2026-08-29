<script setup>
import { onMounted } from 'vue'
import PageActionDialog from './page/PageActionDialog.vue'
import PageContent from './page/PageContent.vue'
import { usePageRuntime } from './page/usePageRuntime'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DoubanCenter' },
  nativeSubscribe: { type: Function, default: null },
  appPage: { type: Boolean, default: false },
  showSettings: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'switch'])

const page = usePageRuntime({
  api: () => props.api,
  pluginId: () => props.pluginId,
  nativeSubscribe: () => props.nativeSubscribe,
})

onMounted(page.loadAll)
</script>

<template>
  <VCard flat class="dc-page" :class="{ 'dc-page--app': props.appPage, 'dc-page--archive': page.archivePage }">
    <VToolbar density="comfortable" class="dc-page-toolbar">
      <VAvatar color="primary" variant="tonal" rounded="lg" class="ms-3 me-2 dc-page-avatar" style="display: flex !important; width: 32px; height: 32px; min-width: 32px;"><VIcon icon="mdi-book-open-page-variant-outline" /></VAvatar>
      <div class="dc-page-heading">
        <div class="text-h6">{{ page.archivePage ? '豆瓣中心 · 归档记录' : '豆瓣中心 · 运行详情' }}</div>
        <div class="text-caption text-medium-emphasis">{{ page.archivePage ? '删除进入归档，支持恢复或彻底删除' : '榜单刷新 -> 黑名筛选 -> 观察队列 -> 订阅记录' }}</div>
      </div>
      <VSpacer />
      <div class="dc-page-toolbar-actions">
        <VBtn variant="text" size="small" class="text-none dc-toolbar-action" title="刷新" aria-label="刷新" :loading="page.loading" @click="page.archivePage ? page.loadArchive() : page.loadAll()">
          <VIcon icon="mdi-refresh" size="18" class="dc-toolbar-icon" /><span class="dc-toolbar-label">刷新</span>
        </VBtn>
        <VBtn variant="text" size="small" class="text-none dc-toolbar-action" :title="page.archivePage ? '返回' : '归档'" :aria-label="page.archivePage ? '返回' : '归档'" :color="page.archivePage ? 'primary' : undefined" @click="page.archivePage ? page.closeArchivePage() : page.openArchivePage()">
          <VIcon :icon="page.archivePage ? 'mdi-arrow-left' : 'mdi-archive-outline'" size="18" class="dc-toolbar-icon" /><span class="dc-toolbar-label">{{ page.archivePage ? '返回' : '归档' }}</span>
        </VBtn>
        <VBtn v-if="props.showSettings || !props.appPage" variant="text" size="small" class="text-none dc-toolbar-action" title="设置" aria-label="设置" @click="emit('switch')">
          <VIcon icon="mdi-cog-outline" size="18" class="dc-toolbar-icon" /><span class="dc-toolbar-label">设置</span>
        </VBtn>
        <VBtn v-if="!props.appPage" icon variant="text" size="small" class="dc-toolbar-action" title="关闭" aria-label="关闭" @click="emit('close')"><VIcon icon="mdi-close" size="18" class="dc-toolbar-icon" /></VBtn>
      </div>
    </VToolbar>
    <VDivider />
    <VProgressLinear v-if="page.loading" indeterminate color="primary" height="2" />
    <VCardText class="pa-3 dc-flow">
      <VAlert v-if="page.loadError" type="warning" variant="tonal" density="compact" class="dc-load-alert">
        <div class="dc-load-alert__content"><span>{{ page.loadError }}</span><VBtn variant="text" size="x-small" prepend-icon="mdi-refresh" class="text-none" :loading="page.loading" @click="page.archivePage ? page.loadArchive() : page.loadAll()">重试</VBtn></div>
      </VAlert>
      <div v-if="page.actionMessage" class="dc-action-message" :class="page.actionOk ? 'text-success' : 'text-error'">{{ page.actionMessage }}</div>
      <PageContent :page="page" />
    </VCardText>
    <PageActionDialog :page="page" />
  </VCard>
</template>

<style scoped>
.dc-page { width: 100%; border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.dc-page--app { min-height: calc(100dvh - 104px); border-radius: 14px; }
.dc-page--archive { height: clamp(640px, calc(100dvh - 48px), 860px); max-height: calc(100dvh - 16px); display: flex; flex-direction: column; }
.dc-page--app.dc-page--archive { height: calc(100dvh - 104px); max-height: none; min-height: 0; }
.dc-page-toolbar { background: rgb(var(--v-theme-surface)); padding-right: 8px; }
.dc-page-heading { min-width: 0; }
.dc-page-toolbar-actions { display: flex; align-items: center; flex: 0 0 auto; gap: 2px; }
.dc-toolbar-icon { flex: 0 0 auto; }
.dc-toolbar-label { white-space: nowrap; }
.dc-page-heading .text-h6, .dc-page-heading .text-caption { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-flow { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.dc-page--archive .dc-flow { flex: 1 1 auto; min-height: 0; overflow-y: auto; align-content: start; }
.dc-action-message { grid-column: 1 / -1; border: 1px solid currentColor; border-radius: 8px; padding: 7px 10px; margin-bottom: 0; font-size: 12px; background: rgba(var(--v-theme-on-surface), .018); }
.dc-load-alert { grid-column: 1 / -1; }
.dc-load-alert__content { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; font-size: 12px; }
.dc-load-alert__content span { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .dc-page-toolbar { min-height: 56px; padding-inline: 4px; }
  .dc-page-avatar { display: flex !important; flex: 0 0 32px; width: 32px !important; height: 32px !important; min-width: 32px; margin-inline: 4px !important; }
  .dc-page-heading { flex: 1 1 auto; max-width: none; }
  .dc-page-heading .text-h6 { font-size: 15px !important; }
  .dc-page-heading .text-caption { display: none; }
  .dc-page-toolbar-actions { gap: 0; }
  .dc-toolbar-action { flex: 0 0 34px; min-width: 34px !important; width: 34px; padding-inline: 0 !important; }
  .dc-toolbar-label { display: none; }
  .dc-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 360px) {
  .dc-flow { grid-template-columns: 1fr; }
}
</style>
