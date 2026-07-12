<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
})
defineEmits(['action'])

const loading = ref(true)
const status = ref({ state: 'idle', message: '等待加载' })

async function loadStatus() {
  loading.value = true
  try {
    status.value = (await getPluginApi(props.api, 'status')) || status.value
  } catch (error) {
    status.value = { state: 'error', message: error?.message || '状态加载失败' }
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="ar-app-page pa-4">
    <VCard flat class="ar-app-page__card">
      <VCardItem>
        <template #prepend>
          <VAvatar color="primary" variant="tonal" rounded="lg"><VIcon icon="mdi-brain" /></VAvatar>
        </template>
        <VCardTitle>Agent榜单中心</VCardTitle>
        <VCardSubtitle>从 MoviePilot 发现候选中生成个性化 Top 10</VCardSubtitle>
        <template #append>
          <VBtn icon="mdi-refresh" variant="text" :loading="loading" aria-label="刷新榜单状态" @click="loadStatus" />
        </template>
      </VCardItem>
      <VDivider />
      <div class="pa-5">
        <VSkeletonLoader v-if="loading" type="article, article" />
        <template v-else>
          <VAlert type="info" variant="tonal" class="mb-4">{{ status.message }}</VAlert>
          <VEmptyState icon="mdi-format-list-numbered" title="推荐榜单尚未生成" text="完成后端推荐链路后，这里将展示固定单列 Top 10。" />
        </template>
      </div>
    </VCard>
  </div>
</template>

<style scoped>
.ar-app-page { width: 100%; max-width: 1440px; margin: 0 auto; }
.ar-app-page__card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 16px; }
</style>
