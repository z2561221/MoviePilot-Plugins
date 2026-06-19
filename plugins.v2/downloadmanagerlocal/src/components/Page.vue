<script setup>
import { ref, onMounted, computed } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['close', 'switch'])

const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 15
const activeTab = ref('history')
const loading = ref(true)
const retrying = ref(false)
const retryingHash = ref('')
const diagnostics = ref(null)
const diagnosticsLoading = ref(false)
const diagnosticsError = ref('')
const error = ref('')
const actionMsg = ref('')
const actionOk = ref(false)

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

async function loadDiagnostics() {
  activeTab.value = 'diagnostics'
  diagnosticsLoading.value = true
  diagnosticsError.value = ''
  try {
    const resp = await getPluginApi(props.api, 'diagnostics')
    if (resp?.code && resp.code !== 0) {
      diagnosticsError.value = resp?.msg || '诊断失败'
      return
    }
    diagnostics.value = resp
  } catch (e) {
    diagnosticsError.value = e?.message || '诊断失败'
  } finally {
    diagnosticsLoading.value = false
  }
}

function checkColor(status) {
  if (status === 'ok') return 'success'
  if (status === 'warn') return 'warning'
  return 'default'
}

async function doRecovery(hash) {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postPluginApi(props.api, 'recovery_torrent', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败'
  }
}

async function doDelete(hash) {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_history', { hash })
    actionOk.value = resp?.code === 0
    actionMsg.value = resp?.msg || '已删除'
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionMsg.value = e?.message || '删除失败'
  }
}

async function doRetryRenames() {
  actionMsg.value = ''
  actionOk.value = false
  retrying.value = true
  try {
    const resp = await postPluginApi(props.api, 'retry_renames', {})
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '补刀失败'
  } finally {
    retrying.value = false
  }
}

async function doRetryRename(hash) {
  actionMsg.value = ''
  actionOk.value = false
  retryingHash.value = hash
  try {
    const resp = await postPluginApi(props.api, 'retry_rename', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await loadHistory()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '补刀失败'
  } finally {
    retryingHash.value = ''
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
      <div class="text-h6">下载管理</div>
      <VSpacer />
      <VBtn value="history" :variant="activeTab === 'history' ? 'tonal' : 'text'" size="small" class="text-none me-1" @click="activeTab = 'history'">重命名历史</VBtn>
      <VBtn value="diagnostics" :variant="activeTab === 'diagnostics' ? 'tonal' : 'text'" size="small" class="text-none me-2" @click="loadDiagnostics">诊断</VBtn>
      <VBtn v-if="activeTab === 'history'" variant="tonal" size="small" prepend-icon="mdi-auto-fix" class="text-none me-2" @click="doRetryRenames" :loading="retrying">补刀</VBtn>
      <VBtn v-if="activeTab === 'history'" variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-2" @click="loadHistory" :loading="loading">刷新</VBtn>
      <VBtn v-else variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-2" @click="loadDiagnostics" :loading="diagnosticsLoading">刷新诊断</VBtn>
      <VBtn variant="text" prepend-icon="mdi-cog-outline" class="text-none" @click="emit('switch')">设置</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />
    <div v-if="activeTab === 'history'" class="pa-3">
      <VAlert v-if="actionMsg" :type="actionOk ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMsg }}</VAlert>
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
                <VBtn size="x-small" variant="tonal" color="primary" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash">补刀</VBtn>
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
    <div v-else class="pa-3">
      <VAlert v-if="diagnosticsError" type="error" variant="tonal" class="mb-3" density="compact">{{ diagnosticsError }}</VAlert>
      <VProgressCircular v-if="diagnosticsLoading" indeterminate color="primary" class="d-block mx-auto my-8" />
      <div v-else-if="diagnostics" class="dm-diagnostics">
        <div class="dm-stat-grid mb-3">
          <div class="dm-stat">
            <div class="text-caption text-medium-emphasis">版本</div>
            <div class="text-subtitle-2">{{ diagnostics?.plugin?.version }}</div>
          </div>
          <div class="dm-stat">
            <div class="text-caption text-medium-emphasis">源下载器</div>
            <div class="text-subtitle-2">{{ diagnostics?.downloaders?.from?.name || '未配置' }}</div>
            <VChip size="x-small" :color="diagnostics?.downloaders?.from?.available ? 'success' : 'warning'" variant="tonal">{{ diagnostics?.downloaders?.from?.message }}</VChip>
          </div>
          <div class="dm-stat">
            <div class="text-caption text-medium-emphasis">目标下载器</div>
            <div class="text-subtitle-2">{{ diagnostics?.downloaders?.to?.name || '未配置' }}</div>
            <VChip size="x-small" :color="diagnostics?.downloaders?.to?.available ? 'success' : 'warning'" variant="tonal">{{ diagnostics?.downloaders?.to?.message }}</VChip>
          </div>
          <div class="dm-stat">
            <div class="text-caption text-medium-emphasis">重命名历史</div>
            <div class="text-subtitle-2">{{ diagnostics?.rename_history?.total }} 条</div>
            <div class="text-caption">失败 {{ diagnostics?.rename_history?.failed }} · 脏名 {{ diagnostics?.rename_history?.dirty }}</div>
          </div>
        </div>

        <div class="dm-checks mb-3">
          <div v-for="item in diagnostics.checks" :key="item.label" class="dm-check-row">
            <div class="text-body-2">{{ item.label }}</div>
            <div class="d-flex align-center ga-2">
              <span class="text-caption text-medium-emphasis">{{ item.detail }}</span>
              <VChip size="x-small" :color="checkColor(item.status)" variant="tonal">{{ item.status }}</VChip>
            </div>
          </div>
        </div>

        <div>
          <div class="text-subtitle-2 mb-2">最近失败</div>
          <div v-if="!diagnostics?.rename_history?.recent_failures?.length" class="text-caption text-medium-emphasis py-2">暂无失败记录</div>
          <VTable v-else density="compact" class="dm-table">
            <thead>
              <tr>
                <th class="text-caption">时间</th>
                <th class="text-caption">名称</th>
                <th class="text-caption">原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in diagnostics.rename_history.recent_failures" :key="item.hash">
                <td class="text-caption text-no-wrap">{{ item.time }}</td>
                <td class="text-caption" style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="item.name">{{ item.name }}</td>
                <td class="text-caption">{{ item.reason }}</td>
              </tr>
            </tbody>
          </VTable>
        </div>
      </div>
      <div v-else class="text-center text-medium-emphasis py-8">
        <VIcon icon="mdi-stethoscope" size="48" color="grey-lighten-1" class="mb-2" />
        <div>点击刷新诊断</div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.dm-toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
.dm-table :deep(th) { font-weight: 600 !important; }
.dm-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-stat { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; padding: 10px; min-height: 76px; }
.dm-checks { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; overflow: hidden; }
.dm-check-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 10px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dm-check-row:last-child { border-bottom: 0; }
@media (max-width: 760px) {
  .dm-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-check-row { align-items: flex-start; flex-direction: column; }
}
</style>
