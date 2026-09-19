<script setup>
import { ref, onMounted } from 'vue'
import { apiGet, pluginApiPath } from '../api.js'
const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
  allowRefresh: { type: Boolean, default: false },
})
const status = ref(null)
const loading = ref(false)
async function load() {
  loading.value = true
  try {
    status.value = await apiGet(props.api, pluginApiPath(props.pluginId, 'local_toolkit/status'))
  } catch(e) {
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <VCard class="toolkit-dashboard" variant="flat">
    <VCardItem>
      <template #prepend><VAvatar color="teal" variant="tonal" rounded="lg"><VIcon icon="mdi-tools" /></VAvatar></template>
      <VCardTitle>工具中心</VCardTitle>
      <VCardSubtitle>清理库存 / 扫描缺集 / 清理TMDB</VCardSubtitle>
      <template #append>
        <VBtn v-if="allowRefresh" icon="mdi-refresh" variant="text" size="small" :loading="loading" @click="load" />
      </template>
    </VCardItem>
    <VCardText>
      <div class="dash-row"><span>周期扫描</span><strong>{{ status?.enabled && status?.modules?.library_cleanup?.scan_enabled ? '开启' : '关闭' }}</strong></div>
      <div class="dash-row"><span>周期清理</span><strong>{{ status?.enabled && status?.modules?.library_cleanup?.cleanup_enabled ? '开启' : '关闭' }}</strong></div>
      <div class="dash-row"><span>清理计划</span><strong>{{ status?.modules?.library_cleanup?.plan_count || 0 }} 部</strong></div>
      <div class="dash-row"><span>查漏路径</span><strong>{{ status?.modules?.check_missing?.paths || 0 }} 个</strong></div>
      <div class="dash-row"><span>TMDB缓存</span><strong>{{ status?.modules?.tmdb_cache?.keys || 0 }} 键</strong></div>
    </VCardText>
  </VCard>
</template>
<style scoped>
.toolkit-dashboard{border-radius:16px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));overflow:hidden}.dash-row{display:flex;align-items:center;justify-content:space-between;font-size:13px;line-height:1.9;color:rgba(var(--v-theme-on-surface),.75)}.dash-row strong{color:rgb(var(--v-theme-primary))}
</style>
