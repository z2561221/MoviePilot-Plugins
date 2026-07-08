<script setup>
import { ref, onMounted, computed } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({ api: { type: [Object, Function], default: null } })
const emit = defineEmits(['close', 'switch'])

const activeTab = ref('history')
const diagnostics = ref(null)
const records = ref([])
const archiveRecords = ref([])
const total = ref(0)
const archiveTotal = ref(0)
const page = ref(1)
const archivePage = ref(1)
const pageSize = 15
const loading = ref(false)
const retrying = ref(false)
const retryingHash = ref('')
const restoringHash = ref('')
const deletingHash = ref('')
const error = ref('')
const actionMsg = ref('')
const actionOk = ref(false)

const tabs = [
  { key: 'history', title: '命名历史', icon: 'mdi-history' },
  { key: 'archive', title: '归档记录', icon: 'mdi-archive-outline' },
  { key: 'diagnostics', title: '运行诊断', icon: 'mdi-stethoscope' },
]

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))
const archiveTotalPages = computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / pageSize)))
const diagnosticsCards = computed(() => {
  const items = Array.isArray(diagnostics.value?.checks) ? diagnostics.value.checks : []
  return items.map(item => ({
    ...item,
    statusText: item.status === 'ok' ? '正常' : item.status === 'warn' ? '关注' : '未启用',
    icon: item.status === 'ok'
      ? 'mdi-check-circle-outline'
      : item.status === 'warn'
        ? 'mdi-alert-circle-outline'
        : 'mdi-minus-circle-outline',
  }))
})
const diagnosticsOkCount = computed(() => diagnosticsCards.value.filter(item => item.status === 'ok').length)
const diagnosticsAttentionCount = computed(() => diagnosticsCards.value.length - diagnosticsOkCount.value)

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

async function loadArchive() {
  loading.value = true
  error.value = ''
  try {
    const resp = await getPluginApi(props.api, `rename_archive?page=${archivePage.value}&page_size=${pageSize}`)
    archiveRecords.value = Array.isArray(resp?.items) ? resp.items : []
    archiveTotal.value = resp?.total || 0
  } catch (e) {
    error.value = e?.message || '归档加载失败'
  } finally {
    loading.value = false
  }
}

async function loadDiagnostics() {
  loading.value = true
  error.value = ''
  try {
    const resp = await getPluginApi(props.api, 'diagnostics')
    if (resp?.code && resp.code !== 0) {
      error.value = resp?.msg || '诊断失败'
      return
    }
    diagnostics.value = resp
  } catch (e) {
    error.value = e?.message || '诊断失败'
  } finally {
    loading.value = false
  }
}

async function selectTab(key) {
  activeTab.value = key
  await refreshActive()
}

async function refreshActive() {
  if (activeTab.value === 'history') return loadHistory()
  if (activeTab.value === 'archive') return loadArchive()
  return loadDiagnostics()
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
    if (resp?.code === 0) await refreshActive()
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

async function restoreArchive(hash) {
  actionMsg.value = ''
  actionOk.value = false
  restoringHash.value = hash
  try {
    const resp = await postPluginApi(props.api, 'restore_rename_archive', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已恢复' : '恢复失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await loadArchive()
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败'
  } finally {
    restoringHash.value = ''
  }
}

async function deleteArchive(hash) {
  actionMsg.value = ''
  actionOk.value = false
  deletingHash.value = hash
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_archive', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已删除' : '删除失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await loadArchive()
  } catch (e) {
    actionMsg.value = e?.message || '删除失败'
  } finally {
    deletingHash.value = ''
  }
}

function prevPage() {
  if (page.value > 1) { page.value--; loadHistory() }
}
function nextPage() {
  if (page.value < totalPages.value) { page.value++; loadHistory() }
}
function prevArchivePage() {
  if (archivePage.value > 1) { archivePage.value--; loadArchive() }
}
function nextArchivePage() {
  if (archivePage.value < archiveTotalPages.value) { archivePage.value++; loadArchive() }
}

onMounted(loadHistory)
</script>

<template>
  <div class="dm-page">
    <VToolbar density="comfortable" class="dm-toolbar">
      <VIcon icon="mdi-download" class="ms-3 me-2" color="primary" />
      <div class="text-h6">下载中心</div>
      <VSpacer />
      <VBtn variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-2" @click="refreshActive" :loading="loading">刷新</VBtn>
      <VBtn variant="text" prepend-icon="mdi-cog-outline" class="text-none" @click="emit('switch')">设置</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="dm-layout">
      <nav class="dm-side">
        <VList density="compact" nav class="dm-side-list py-2">
          <VListItem v-for="tab in tabs" :key="tab.key" :active="activeTab === tab.key" color="primary" rounded="lg" class="dm-side-item" @click="selectTab(tab.key)">
            <template #prepend><VIcon :icon="tab.icon" /></template>
            <VListItemTitle>{{ tab.title }}</VListItemTitle>
          </VListItem>
        </VList>
      </nav>

      <main class="dm-main">
        <VAlert v-if="actionMsg" :type="actionOk ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMsg }}</VAlert>
        <VAlert v-if="error" type="error" variant="tonal" class="mb-3" density="compact">{{ error }}</VAlert>
        <div v-if="loading" class="dm-state">
          <VProgressCircular indeterminate color="primary" />
        </div>

        <section v-else-if="activeTab === 'history'" class="dm-pane">
          <div class="d-flex align-center mb-3">
            <div class="text-subtitle-2">命名历史</div>
            <VSpacer />
            <VBtn variant="tonal" size="small" prepend-icon="mdi-auto-fix" class="text-none" @click="doRetryRenames" :loading="retrying">补刀</VBtn>
          </div>
          <div v-if="records.length === 0" class="dm-state text-center text-medium-emphasis">
            <VIcon icon="mdi-history" size="48" color="grey-lighten-1" class="mb-2" />
            <div>暂无命名记录</div>
          </div>
          <template v-else>
            <div class="dm-table-scroll dm-desktop-table">
              <VTable density="compact" class="dm-table">
              <thead>
                <tr>
                  <th class="text-caption">时间</th>
                  <th class="text-caption">原始名称</th>
                  <th class="text-caption">命名后</th>
                  <th class="text-caption">状态</th>
                  <th class="text-caption">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in records" :key="r.hash">
                  <td class="text-caption text-no-wrap">{{ r.time }}</td>
                  <td class="text-caption dm-ellipsis" :title="r.original_name">{{ r.original_name }}</td>
                  <td class="text-caption dm-ellipsis" :title="r.after_name">{{ r.after_name }}</td>
                  <td><VChip size="x-small" :color="r.success ? 'success' : 'error'" variant="tonal">{{ r.success ? '成功' : (r.reason || '失败') }}</VChip></td>
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
            </div>
            <div class="dm-mobile-list dm-history-list">
              <article v-for="r in records" :key="r.hash" class="dm-record-card dm-history-card">
                <div class="dm-record-head">
                  <div class="dm-record-title" :title="r.after_name || r.original_name">{{ r.after_name || r.original_name || r.hash }}</div>
                  <VChip size="x-small" :color="r.success ? 'success' : 'error'" variant="tonal">{{ r.success ? '成功' : (r.reason || '失败') }}</VChip>
                </div>
                <div class="dm-record-meta">
                  <div class="dm-record-row">
                    <span class="dm-record-label">时间</span>
                    <span class="dm-record-value">{{ r.time || '-' }}</span>
                  </div>
                  <div class="dm-record-row">
                    <span class="dm-record-label">原始</span>
                    <span class="dm-record-value" :title="r.original_name">{{ r.original_name || '-' }}</span>
                  </div>
                  <div class="dm-record-row">
                    <span class="dm-record-label">命名后</span>
                    <span class="dm-record-value" :title="r.after_name">{{ r.after_name || '-' }}</span>
                  </div>
                </div>
                <div class="dm-record-actions">
                  <VBtn size="x-small" variant="tonal" color="primary" prepend-icon="mdi-auto-fix" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash">补刀</VBtn>
                  <VBtn v-if="r.success" size="x-small" variant="tonal" color="warning" prepend-icon="mdi-undo" @click="doRecovery(r.hash)">恢复</VBtn>
                  <VBtn size="x-small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="doDelete(r.hash)">删除</VBtn>
                </div>
              </article>
            </div>
          </template>
          <div v-if="total > pageSize" class="d-flex align-center justify-center pa-3">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="page <= 1" @click="prevPage" class="mr-2" />
            <span class="text-caption mx-1">{{ page }} / {{ totalPages }}（共 {{ total }} 条）</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="page >= totalPages" @click="nextPage" class="ml-2" />
          </div>
        </section>

        <section v-else-if="activeTab === 'archive'" class="dm-pane">
          <div class="text-subtitle-2 mb-3">归档记录</div>
          <div v-if="archiveRecords.length === 0" class="dm-state text-center text-medium-emphasis">
            <VIcon icon="mdi-archive-outline" size="48" color="grey-lighten-1" class="mb-2" />
            <div>暂无归档记录</div>
          </div>
          <template v-else>
            <div class="dm-table-scroll dm-desktop-table">
              <VTable density="compact" class="dm-table">
              <thead>
                <tr>
                  <th class="text-caption">归档时间</th>
                  <th class="text-caption">名称</th>
                  <th class="text-caption">分类</th>
                  <th class="text-caption">次数</th>
                  <th class="text-caption">原因</th>
                  <th class="text-caption">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in archiveRecords" :key="r.hash">
                  <td class="text-caption text-no-wrap">{{ r.archived_at || r.last_failed_at }}</td>
                  <td class="text-caption dm-ellipsis" :title="r.name">{{ r.name || r.hash }}</td>
                  <td><VChip size="x-small" color="warning" variant="tonal">{{ r.category_label || r.category }}</VChip></td>
                  <td class="text-caption">{{ r.fail_count }}</td>
                  <td class="text-caption dm-ellipsis" :title="r.archive_reason || r.reason">{{ r.archive_reason || r.reason }}</td>
                  <td>
                    <div class="d-flex ga-1">
                      <VBtn size="x-small" variant="tonal" color="primary" @click="restoreArchive(r.hash)" :loading="restoringHash === r.hash">恢复</VBtn>
                      <VBtn size="x-small" variant="text" color="error" @click="deleteArchive(r.hash)" :loading="deletingHash === r.hash">删除</VBtn>
                    </div>
                  </td>
                </tr>
              </tbody>
              </VTable>
            </div>
            <div class="dm-mobile-list dm-archive-list">
              <article v-for="r in archiveRecords" :key="r.hash" class="dm-record-card dm-archive-card">
                <div class="dm-record-head">
                  <div class="dm-record-title" :title="r.name || r.hash">{{ r.name || r.hash }}</div>
                  <VChip size="x-small" color="warning" variant="tonal">{{ r.category_label || r.category }}</VChip>
                </div>
                <div class="dm-record-meta">
                  <div class="dm-record-row">
                    <span class="dm-record-label">归档</span>
                    <span class="dm-record-value">{{ r.archived_at || r.last_failed_at || '-' }}</span>
                  </div>
                  <div class="dm-record-row">
                    <span class="dm-record-label">次数</span>
                    <span class="dm-record-value">{{ r.fail_count || 0 }}</span>
                  </div>
                  <div class="dm-record-row">
                    <span class="dm-record-label">原因</span>
                    <span class="dm-record-value" :title="r.archive_reason || r.reason">{{ r.archive_reason || r.reason || '-' }}</span>
                  </div>
                </div>
                <div class="dm-record-actions">
                  <VBtn size="x-small" variant="tonal" color="primary" prepend-icon="mdi-archive-arrow-up-outline" @click="restoreArchive(r.hash)" :loading="restoringHash === r.hash">恢复</VBtn>
                  <VBtn size="x-small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="deleteArchive(r.hash)" :loading="deletingHash === r.hash">删除</VBtn>
                </div>
              </article>
            </div>
          </template>
          <div v-if="archiveTotal > pageSize" class="d-flex align-center justify-center pa-3">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="archivePage <= 1" @click="prevArchivePage" class="mr-2" />
            <span class="text-caption mx-1">{{ archivePage }} / {{ archiveTotalPages }}（共 {{ archiveTotal }} 条）</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="archivePage >= archiveTotalPages" @click="nextArchivePage" class="ml-2" />
          </div>
        </section>

        <section v-else class="dm-pane">
          <div v-if="diagnostics" class="dm-diagnostics">
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
                <div class="text-caption text-medium-emphasis">补刀归档</div>
                <div class="text-subtitle-2">{{ diagnostics?.rename_archive?.archived || 0 }} 条</div>
                <div class="text-caption">连续失败 {{ diagnostics?.rename_archive?.active_failed || 0 }} · 阈值 {{ diagnostics?.rename_archive?.threshold || 3 }}</div>
              </div>
            </div>

            <div class="dm-diagnostics-panel mb-3">
              <div class="dm-diagnostics-head">
                <div class="dm-diagnostics-title">
                  <span class="dm-diagnostics-icon"><VIcon icon="mdi-stethoscope" size="20" /></span>
                  <span>运行诊断</span>
                </div>
                <div class="dm-diagnostics-score">
                  <strong>{{ diagnosticsOkCount }} / {{ diagnosticsCards.length }}</strong>
                  <span>正常</span>
                  <span v-if="diagnosticsAttentionCount">· {{ diagnosticsAttentionCount }} 项关注</span>
                </div>
              </div>
              <div class="dm-diagnostics-grid">
                <div v-for="item in diagnosticsCards" :key="item.label" class="dm-diagnostic-card" :class="`dm-diagnostic-card--${item.status || 'off'}`">
                  <div class="dm-diagnostic-state">
                    <VIcon :icon="item.icon" size="22" />
                  </div>
                  <div class="dm-diagnostic-content">
                    <div class="dm-diagnostic-name">{{ item.label }}</div>
                    <div class="dm-diagnostic-value">{{ item.detail }}</div>
                    <div class="dm-diagnostic-note">{{ item.statusText }}</div>
                  </div>
                </div>
              </div>
              <div class="dm-diagnostics-footer">
                <span>按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。</span>
                <span v-if="diagnosticsAttentionCount" class="dm-diagnostics-attention">关注项不阻断运行</span>
              </div>
            </div>

            <div>
              <div class="text-subtitle-2 mb-2">最近失败</div>
              <div v-if="!diagnostics?.rename_history?.recent_failures?.length" class="text-caption text-medium-emphasis py-2">暂无失败记录</div>
              <div v-else class="dm-table-scroll">
                <VTable density="compact" class="dm-table">
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
                    <td class="text-caption dm-ellipsis" :title="item.name">{{ item.name }}</td>
                    <td class="text-caption">{{ item.reason }}</td>
                  </tr>
                </tbody>
                </VTable>
              </div>
            </div>
          </div>
          <div v-else class="dm-state text-center text-medium-emphasis">
            <VIcon icon="mdi-stethoscope" size="48" color="grey-lighten-1" class="mb-2" />
            <div>点击刷新诊断</div>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.dm-page {
  height: clamp(760px, calc(100dvh - 48px), 860px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dm-toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
.dm-layout { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-side { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-side-list { width: 100%; }
.dm-side-item { margin: 2px 8px; }
.dm-main { flex: 1 1 auto; min-width: 0; min-height: 0; padding: 12px; overflow-y: auto; }
.dm-pane { min-width: 0; min-height: 100%; }
.dm-state { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.dm-table-scroll { width: 100%; overflow-x: auto; overflow-y: hidden; }
.dm-table { min-width: 720px; }
.dm-table :deep(th) { font-weight: 600 !important; }
.dm-ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dm-mobile-list { display: none; }
.dm-record-card {
  min-width: 0;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 10px;
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.dm-record-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.dm-record-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 700;
  color: rgba(var(--v-theme-on-surface), 0.88);
}
.dm-record-meta {
  display: grid;
  gap: 7px;
  margin-top: 10px;
}
.dm-record-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}
.dm-record-label {
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 12px;
  white-space: nowrap;
}
.dm-record-value {
  min-width: 0;
  overflow-wrap: anywhere;
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-size: 12px;
  line-height: 1.45;
}
.dm-record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.dm-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-stat { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px; min-width: 0; }
.dm-diagnostics-panel {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.dm-diagnostics-head {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.dm-diagnostics-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 14px;
  font-weight: 700;
}
.dm-diagnostics-icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 8px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
}
.dm-diagnostics-score {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.dm-diagnostics-score strong {
  color: rgba(var(--v-theme-on-surface), 0.92);
  font-size: 15px;
}
.dm-diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}
.dm-diagnostic-card {
  min-height: 96px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.025);
}
.dm-diagnostic-card--ok {
  background: linear-gradient(135deg, rgba(var(--v-theme-success), 0.08), rgba(var(--v-theme-on-surface), 0.025) 54%);
}
.dm-diagnostic-card--warn {
  border-color: rgba(var(--v-theme-warning), 0.28);
  background: linear-gradient(135deg, rgba(var(--v-theme-warning), 0.12), rgba(var(--v-theme-on-surface), 0.025) 54%);
}
.dm-diagnostic-state {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  background: rgba(var(--v-theme-on-surface), 0.055);
}
.dm-diagnostic-card--ok .dm-diagnostic-state {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.14);
}
.dm-diagnostic-card--warn .dm-diagnostic-state {
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.16);
}
.dm-diagnostic-content {
  min-width: 0;
}
.dm-diagnostic-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
}
.dm-diagnostic-value {
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-size: 13px;
  font-weight: 600;
}
.dm-diagnostic-note {
  margin-top: 5px;
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 12px;
  line-height: 1.35;
}
.dm-diagnostics-footer {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
}
.dm-diagnostics-attention {
  color: rgb(var(--v-theme-warning));
  white-space: nowrap;
}
@media (max-width: 1100px) {
  .dm-diagnostics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .dm-page { height: min(860px, calc(100dvh - 16px)); }
  .dm-layout { flex-direction: column; }
  .dm-side {
    width: 100%;
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }
  .dm-side::-webkit-scrollbar { display: none; }
  .dm-side-list {
    display: flex;
    flex-wrap: nowrap;
    gap: 6px;
    min-width: max-content;
    padding: 8px 12px !important;
  }
  .dm-side-item {
    flex: 0 0 auto;
    min-width: 96px;
    margin: 0;
    padding-inline: 10px;
  }
  .dm-side-item :deep(.v-list-item-title) { white-space: nowrap; }
  .dm-main { padding: 10px; }
  .dm-desktop-table { display: none; }
  .dm-mobile-list { display: grid; gap: 10px; }
  .dm-record-title {
    white-space: normal;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
  .dm-record-actions :deep(.v-btn) {
    flex: 1 1 72px;
    max-width: 128px;
  }
  .dm-stat-grid { grid-template-columns: 1fr; }
  .dm-diagnostics-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .dm-diagnostics-score {
    white-space: normal;
  }
  .dm-diagnostics-grid {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 10px;
  }
  .dm-diagnostic-card {
    min-height: 86px;
  }
  .dm-diagnostics-footer {
    align-items: flex-start;
    flex-direction: column;
  }
  .dm-diagnostics-attention {
    white-space: normal;
  }
}
</style>
