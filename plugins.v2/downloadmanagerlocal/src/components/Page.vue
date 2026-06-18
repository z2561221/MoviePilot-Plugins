<script setup>
import { ref, onMounted, computed } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['close', 'switch'])

const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 15
const loading = ref(true)
const error = ref('')
const actionMsg = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    const resp = await getPluginApi(props.api, `rename_history?page=${page.value}&page_size=${pageSize}`)
    records.value = Array.isArray(resp?.items) ? resp.items : []
    total.value = resp?.total || 0
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function doRecovery(hash) {
  actionMsg.value = ''
  try {
    const resp = await postPluginApi(props.api, 'recovery_torrent', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败')
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败'
  }
}

async function doDelete(hash) {
  actionMsg.value = ''
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_history', { hash })
    actionMsg.value = resp?.msg || '已删除'
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionMsg.value = e?.message || '删除失败'
  }
}

function prevPage() {
  if (page.value > 1) { page.value--; loadHistory() }
}
function nextPage() {
  if (page.value < totalPages.value) { page.value++; loadHistory() }
}

onMounted(loadHistory)
</script>
<template>
  <div class="dm-page">
    <VToolbar density="comfortable" class="dm-toolbar">
      <VIcon icon="mdi-rename-box" class="ms-3 me-2" color="primary" />
      <div class="text-h6">下载管理 · 重命名历史</div>
      <VSpacer />
      <VBtn variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-2" @click="loadHistory" :loading="loading">刷新</VBtn>
      <VBtn variant="text" prepend-icon="mdi-cog-outline" class="text-none" @click="emit('switch')">设置</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />
    <div class="pa-3">
      <VAlert v-if="actionMsg" :type="actionMsg.includes('成功') || actionMsg.includes('已') ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMsg }}</VAlert>
      <VAlert v-if="error" type="error" variant="tonal" class="mb-3" density="compact">{{ error }}</VAlert>

      <VProgressCircular v-if="loading" indeterminate color="primary" class="d-block mx-auto my-8" />

      <div v-else-if="records.length === 0" class="text-center text-medium-emphasis py-8">
        <VIcon icon="mdi-history" size="48" color="grey-lighten-1" class="mb-2" />
        <div>暂无重命名记录</div>
      </div>

      <VTable v-else density="compact" class="dm-table">
        <thead>
          <tr>
            <th class="text-caption">时间</th>
            <th class="text-caption">原始名称</th>
            <th class="text-caption">重命名后</th>
            <th class="text-caption">状态</th>
            <th class="text-caption">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.hash">
            <td class="text-caption text-no-wrap">{{ r.time }}</td>
            <td class="text-caption" style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="r.original_name">{{ r.original_name }}</td>
            <td class="text-caption" style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="r.after_name">{{ r.after_name }}</td>
            <td>
              <VChip size="x-small" :color="r.success ? 'success' : 'error'" variant="tonal">{{ r.success ? '成功' : (r.reason || '失败') }}</VChip>
            </td>
            <td>
              <div class="d-flex ga-1">
                <VBtn v-if="r.success" size="x-small" variant="tonal" color="warning" @click="doRecovery(r.hash)">恢复</VBtn>
                <VBtn size="x-small" variant="text" color="error" @click="doDelete(r.hash)">删除</VBtn>
              </div>
            </td>
          </tr>
        </tbody>
      </VTable>

      <div v-if="total > pageSize" class="d-flex align-center justify-center pa-3">
        <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="page <= 1" @click="prevPage" class="mr-2" />
        <span class="text-caption mx-1">{{ page }} / {{ totalPages }}（共 {{ total }} 条）</span>
        <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="page >= totalPages" @click="nextPage" class="ml-2" />
      </div>
    </div>
  </div>
</template>
<style scoped>
.dm-toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
.dm-table :deep(th) { font-weight: 600 !important; }
</style>
