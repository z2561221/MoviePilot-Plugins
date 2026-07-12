<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
})
const loading = ref(true)
const status = ref({})

async function loadStatus() {
  loading.value = true
  try {
    status.value = (await getPluginApi(props.api, 'status')) || {}
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <VCard variant="flat" class="ar-dashboard">
    <VCardItem>
      <VCardTitle class="text-subtitle-1 font-weight-bold">Agent榜单中心</VCardTitle>
      <VCardSubtitle>个性化推荐 Top 5</VCardSubtitle>
      <template #append>
        <VBtn
          icon="mdi-refresh"
          variant="text"
          size="small"
          :disabled="!allowRefresh"
          :loading="loading"
          aria-label="刷新仪表板"
          @click="loadStatus"
        />
      </template>
    </VCardItem>
    <VDivider />
    <VCardText>
      <VSkeletonLoader v-if="loading" type="list-item-three-line" />
      <VAlert v-else type="info" variant="tonal">{{ status.message || '推荐榜单尚未生成' }}</VAlert>
    </VCardText>
  </VCard>
</template>

<style scoped>
.ar-dashboard { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 16px; }
</style>
