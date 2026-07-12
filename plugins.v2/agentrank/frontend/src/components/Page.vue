<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['action', 'switch', 'close'])
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
  <div class="ar-page">
    <VToolbar density="comfortable" class="ar-page__toolbar">
      <VIcon icon="mdi-brain" color="primary" class="ms-3 me-2" />
      <div class="text-h6">Agent榜单中心详情</div>
      <VSpacer />
      <VBtn icon="mdi-refresh" variant="text" :loading="loading" aria-label="刷新详情" @click="loadStatus" />
      <VBtn icon="mdi-cog-outline" variant="text" aria-label="打开设置" @click="emit('switch')" />
      <VBtn icon="mdi-close" variant="text" aria-label="关闭详情" @click="emit('close')" />
    </VToolbar>
    <VDivider />
    <div class="pa-5">
      <VSkeletonLoader v-if="loading" type="article" />
      <VAlert v-else type="info" variant="tonal">{{ status.message || '详情骨架已就绪' }}</VAlert>
    </div>
  </div>
</template>

<style scoped>
.ar-page { min-height: 420px; }
.ar-page__toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
</style>
