<script setup>
import { computed, onMounted, ref } from 'vue'
import { apiGet, apiPost, pluginApiPath } from '../api.js'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
})
const emit = defineEmits(['close', 'switch'])

const activeTab = ref('overview')
const status = ref(null)
const cleanupPlan = ref({ total: 0, page: 1, page_size: 15, total_pages: 1, items: [], batch_size: 10 })
const cleanupPlanPage = ref(1)
const cleanupPlanPageSize = 15
const history = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 15
const loading = ref(false)
const loadingAction = ref('')
const error = ref('')
const actionMessage = ref('')
const actionOk = ref(false)

const tabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'cleanup_plan', title: '清理计划', icon: 'mdi-playlist-check' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
]

const historyTotalPages = computed(() => Math.max(1, Math.ceil((historyTotal.value || 0) / historyPageSize)))
const cleanupPlanTotalPages = computed(() => Math.max(1, Number(cleanupPlan.value?.total_pages || Math.ceil((cleanupPlan.value?.total || 0) / cleanupPlanPageSize))))
const cleanupStatus = computed(() => status.value?.modules?.library_cleanup || {})
const batchSize = computed(() => Number(cleanupPlan.value?.batch_size || cleanupStatus.value?.cycle_batch_size || 10))
const overviewCards = computed(() => [
  {
    title: '周期状态',
    value: cleanupStatus.value.enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.cron ? `周期 ${cleanupStatus.value.cron}` : '未设置清理周期',
    icon: 'mdi-calendar-clock-outline',
    color: cleanupStatus.value.enabled ? 'success' : 'default',
  },
  {
    title: '清理计划',
    value: `${cleanupPlan.value.total || 0} 部`,
    detail: cleanupStatus.value.auto_delete ? '自动删除已开启' : '仅扫描入队，不自动删除',
    icon: 'mdi-playlist-check',
    color: cleanupPlan.value.total ? 'warning' : 'primary',
  },
  {
    title: '本周期数量',
    value: `${batchSize.value} 部`,
    detail: `冷却 ${cleanupPlan.value.cooldown_minutes || cleanupStatus.value.cooldown_minutes || 0} 分钟`,
    icon: 'mdi-counter',
    color: 'primary',
  },
  {
    title: '下次执行',
    value: cleanupPlan.value.next_cycle_at ? '冷却中' : '等待周期',
    detail: cleanupPlan.value.next_cycle_at || '当前没有冷却中的周期',
    icon: 'mdi-timer-sand-outline',
    color: cleanupPlan.value.next_cycle_at ? 'info' : 'default',
  },
])
const attentionItems = computed(() => {
  const items = []
  if (cleanupStatus.value.last_error) {
    items.push({ icon: 'mdi-alert-circle-outline', color: 'error', title: '最近运行异常', detail: cleanupStatus.value.last_error })
  }
  if (cleanupPlan.value.total) {
    items.push({ icon: 'mdi-playlist-check', color: 'warning', title: '计划待处理', detail: `${cleanupPlan.value.total} 部对象等待清理` })
  }
  if (cleanupPlan.value.next_cycle_at) {
    items.push({ icon: 'mdi-timer-sand-outline', color: 'info', title: '周期冷却中', detail: `下次可执行：${cleanupPlan.value.next_cycle_at}` })
  }
  return items
})

function apiPath(path) {
  return pluginApiPath(props.pluginId, path)
}

async function loadStatus() {
  status.value = await apiGet(props.api, apiPath('local_toolkit/status'))
}

async function loadPlan() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/cleanup_plan?page=${cleanupPlanPage.value}&page_size=${cleanupPlanPageSize}`))
  cleanupPlan.value = data || { total: 0, page: 1, page_size: cleanupPlanPageSize, total_pages: 1, items: [], batch_size: 10 }
  cleanupPlanPage.value = Number(cleanupPlan.value.page || cleanupPlanPage.value)
}

async function loadOverview() {
  await Promise.all([loadStatus(), loadPlan()])
}

async function loadHistory() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/history?page=${historyPage.value}&page_size=${historyPageSize}`))
  history.value = data?.items || []
  historyTotal.value = data?.total || 0
}

async function refreshActive() {
  loading.value = true
  error.value = ''
  try {
    if (activeTab.value === 'overview') await loadOverview()
    else if (activeTab.value === 'cleanup_plan') await Promise.all([loadStatus(), loadPlan()])
    else await loadHistory()
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

async function selectTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key
  await refreshActive()
}

async function refreshAfterAction() {
  await Promise.all([loadStatus(), loadPlan()])
  if (activeTab.value === 'history') await loadHistory()
}

async function runModule(moduleKey) {
  loadingAction.value = moduleKey
  actionMessage.value = ''
  try {
    const response = await apiPost(props.api, apiPath(`local_toolkit/run/${moduleKey}`))
    actionOk.value = response?.success !== false
    actionMessage.value = response?.message || response?.summary || '运行完成'
  } catch (err) {
    actionOk.value = false
    actionMessage.value = String(err)
  } finally {
    loadingAction.value = ''
    await refreshAfterAction()
  }
}

async function scanPlan() {
  loadingAction.value = 'scan_plan'
  actionMessage.value = ''
  try {
    const response = await apiPost(props.api, apiPath('local_toolkit/cleanup_plan/scan'))
    actionOk.value = response?.success !== false
    actionMessage.value = response?.message || response?.summary || '清理计划已更新'
  } catch (err) {
    actionOk.value = false
    actionMessage.value = String(err)
  } finally {
    loadingAction.value = ''
    await refreshAfterAction()
  }
}

async function clearPlan() {
  if (!window.confirm('确认清空当前清理计划吗？这不会删除媒体库条目。')) return
  loadingAction.value = 'clear_plan'
  actionMessage.value = ''
  try {
    const response = await apiPost(props.api, apiPath('local_toolkit/cleanup_plan/clear'))
    actionOk.value = response?.success !== false
    actionMessage.value = response?.message || response?.summary || '清理计划已清空'
  } catch (err) {
    actionOk.value = false
    actionMessage.value = String(err)
  } finally {
    loadingAction.value = ''
    await refreshAfterAction()
  }
}

function planStatus(item) {
  return item.last_error || '待处理'
}

function planStatusColor(item) {
  return item.last_error ? 'warning' : 'primary'
}

function historyStatus(item) {
  return item.status === 'success' ? '成功' : item.status === 'failed' ? '失败' : item.status || '未知'
}

function historyStatusColor(item) {
  return item.status === 'success' ? 'success' : item.status === 'failed' ? 'error' : 'default'
}

function prevHistoryPage() {
  if (historyPage.value <= 1) return
  historyPage.value -= 1
  loadHistory()
}

function nextHistoryPage() {
  if (historyPage.value >= historyTotalPages.value) return
  historyPage.value += 1
  loadHistory()
}

function prevCleanupPlanPage() {
  if (cleanupPlanPage.value <= 1) return
  cleanupPlanPage.value -= 1
  loadPlan()
}

function nextCleanupPlanPage() {
  if (cleanupPlanPage.value >= cleanupPlanTotalPages.value) return
  cleanupPlanPage.value += 1
  loadPlan()
}

onMounted(loadOverview)
</script>

<template>
  <div class="lt-page">
    <VToolbar density="comfortable" class="lt-toolbar">
      <VIcon icon="mdi-tools" class="ms-3 me-2" color="primary" />
      <div class="lt-toolbar-title">工具中心</div>
      <VSpacer />
      <VBtn variant="text" size="small" prepend-icon="mdi-refresh" class="text-none me-2" @click="refreshActive" :loading="loading">刷新</VBtn>
      <VBtn variant="text" size="small" prepend-icon="mdi-cog-outline" class="text-none me-2" @click="emit('switch')">设置</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="lt-layout">
      <nav class="lt-side">
        <VList density="compact" nav class="lt-side-list py-2">
          <VListItem v-for="tab in tabs" :key="tab.key" :active="activeTab === tab.key" color="primary" rounded="lg" class="lt-side-item" @click="selectTab(tab.key)">
            <template #prepend><VIcon :icon="tab.icon" /></template>
            <VListItemTitle>{{ tab.title }}</VListItemTitle>
          </VListItem>
        </VList>
      </nav>

      <main class="lt-main">
        <VAlert v-if="actionMessage" :type="actionOk ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMessage }}</VAlert>
        <VAlert v-if="error" type="error" variant="tonal" class="mb-3" density="compact">{{ error }}</VAlert>
        <div v-if="loading" class="lt-state"><VProgressCircular indeterminate color="primary" /></div>

        <section v-else-if="activeTab === 'overview'" class="lt-pane">
          <div class="lt-section-heading">
            <div>
              <div class="lt-section-title">运行总览</div>
              <div class="text-caption text-medium-emphasis">清理库存按“扫描、入队、倒序执行、复核”运行，其他工具保持按需执行。</div>
            </div>
          </div>

          <div class="lt-stat-grid mt-3">
            <div v-for="card in overviewCards" :key="card.title" class="lt-stat" :class="`lt-stat--${card.color}`">
              <VAvatar :color="card.color" variant="tonal" size="32" rounded="lg"><VIcon :icon="card.icon" size="18" /></VAvatar>
              <div class="lt-stat-content">
                <div class="lt-stat-label">{{ card.title }}</div>
                <div class="lt-stat-value">{{ card.value }}</div>
                <div class="lt-stat-detail">{{ card.detail }}</div>
              </div>
            </div>
          </div>

          <section class="lt-panel mt-3">
            <div class="lt-section-heading">
              <div>
                <div class="lt-section-title">运行链路</div>
                <div class="text-caption text-medium-emphasis">周期任务必须先完成扫描，删除阶段只消费持久化计划。</div>
              </div>
              <VChip size="small" color="primary" variant="tonal">每周期 {{ batchSize }} 部</VChip>
            </div>
            <div class="lt-flow-grid mt-3">
              <div v-for="(step, index) in [
                { icon: 'mdi-magnify-scan', title: '完整扫描', detail: '按当前筛选条件读取媒体库' },
                { icon: 'mdi-playlist-plus', title: '持久化入队', detail: '按服务器与条目 ID 去重' },
                { icon: 'mdi-sort-numeric-descending', title: '倒序执行', detail: `按设置数量处理 ${batchSize} 部` },
                { icon: 'mdi-check-decagram-outline', title: '删除复核', detail: '成功移除，异常对象留队重试' },
              ]" :key="step.title" class="lt-flow-step">
                <div class="lt-flow-index">{{ index + 1 }}</div>
                <VIcon :icon="step.icon" color="primary" size="22" />
                <div class="lt-flow-copy"><strong>{{ step.title }}</strong><span>{{ step.detail }}</span></div>
              </div>
            </div>
          </section>

          <section v-if="attentionItems.length" class="lt-attention-panel mt-3">
            <div class="lt-section-heading">
              <div>
                <div class="lt-section-title">需要关注</div>
                <div class="text-caption text-medium-emphasis">队列状态和异常会集中显示在这里。</div>
              </div>
              <VChip color="warning" size="small" variant="tonal">{{ attentionItems.length }} 项</VChip>
            </div>
            <div class="lt-attention-list mt-3">
              <div v-for="item in attentionItems" :key="`${item.title}-${item.detail}`" class="lt-attention-item">
                <VIcon :icon="item.icon" :color="item.color" size="19" />
                <div class="min-w-0"><strong>{{ item.title }}</strong><div class="text-caption text-medium-emphasis lt-break-text">{{ item.detail }}</div></div>
              </div>
            </div>
          </section>

          <section class="lt-panel mt-3">
            <div class="lt-section-heading">
              <div><div class="lt-section-title">快速操作</div><div class="text-caption text-medium-emphasis">清理计划操作不会跳过扫描阶段。</div></div>
              <VBtn size="small" variant="text" prepend-icon="mdi-format-list-bulleted" class="text-none" @click="selectTab('cleanup_plan')">查看计划</VBtn>
            </div>
            <div class="lt-action-row mt-3">
              <VBtn color="primary" variant="tonal" prepend-icon="mdi-playlist-plus" :loading="loadingAction === 'scan_plan'" @click="scanPlan">生成清理计划</VBtn>
              <VBtn color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="loadingAction === 'library_cleanup'" @click="runModule('library_cleanup')">执行一周期</VBtn>
              <VBtn color="primary" variant="text" prepend-icon="mdi-magnify-scan" :loading="loadingAction === 'check_missing'" @click="runModule('check_missing')">扫描缺集</VBtn>
              <VBtn color="warning" variant="text" prepend-icon="mdi-database-refresh-outline" :loading="loadingAction === 'tmdb_cache'" @click="runModule('tmdb_cache')">清理 TMDB</VBtn>
            </div>
          </section>
        </section>

        <section v-else-if="activeTab === 'cleanup_plan'" class="lt-pane">
          <div class="lt-section-heading">
            <div><div class="lt-section-title">清理计划</div><div class="text-caption text-medium-emphasis">扫描完成后进入队列，执行阶段按倒序消费；数量取设置页配置。</div></div>
            <div class="lt-action-row lt-action-row--right">
              <VBtn size="small" variant="tonal" prepend-icon="mdi-playlist-plus" :loading="loadingAction === 'scan_plan'" @click="scanPlan">生成计划</VBtn>
              <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="loadingAction === 'library_cleanup'" @click="runModule('library_cleanup')">执行一周期</VBtn>
              <VBtn size="small" color="warning" variant="text" prepend-icon="mdi-playlist-remove" :disabled="!cleanupPlan.total" :loading="loadingAction === 'clear_plan'" @click="clearPlan">清空计划</VBtn>
            </div>
          </div>

          <div class="lt-plan-summary mt-3">
            <div><span>待处理对象</span><strong>{{ cleanupPlan.total || 0 }} 部</strong></div>
            <div><span>本周期数量</span><strong>{{ batchSize }} 部</strong></div>
            <div><span>冷却</span><strong>{{ cleanupPlan.cooldown_minutes || cleanupStatus.cooldown_minutes || 0 }} 分钟</strong></div>
            <div><span>下次执行</span><strong>{{ cleanupPlan.next_cycle_at || '等待周期' }}</strong></div>
          </div>
          <VAlert v-if="cleanupPlan.next_cycle_at" type="info" variant="tonal" density="compact" class="mt-3">当前处于周期冷却，下次可执行：{{ cleanupPlan.next_cycle_at }}</VAlert>

          <div class="lt-table-wrap mt-3">
            <VTable class="lt-table" density="compact">
              <thead><tr><th>#</th><th>对象</th><th>媒体库</th><th>入库日期</th><th>尝试</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="(item, index) in cleanupPlan.items" :key="item.queue_key || index">
                  <td>{{ index + 1 }}</td>
                  <td class="lt-ellipsis" :title="item.title || item.code || item.movie_id">{{ item.title || item.code || item.movie_id || '未知对象' }}</td>
                  <td>{{ item.library_name || item.server || '未标记媒体库' }}</td>
                  <td>{{ item.date_created ? item.date_created.slice(0, 10) : '未知' }}</td>
                  <td>{{ item.attempts || 0 }}</td>
                  <td><VChip size="x-small" :color="planStatusColor(item)" variant="tonal">{{ planStatus(item) }}</VChip></td>
                </tr>
                <tr v-if="!cleanupPlan.items?.length"><td colspan="6" class="text-center text-medium-emphasis py-8">暂无待处理对象</td></tr>
              </tbody>
            </VTable>
          </div>
          <div class="lt-mobile-list">
            <article v-for="(item, index) in cleanupPlan.items" :key="`mobile-${item.queue_key || index}`" class="lt-record">
              <div class="lt-record-head"><strong>{{ item.title || item.code || item.movie_id || '未知对象' }}</strong><VChip size="x-small" :color="planStatusColor(item)" variant="tonal">{{ planStatus(item) }}</VChip></div>
              <div class="lt-record-meta"><span>媒体库</span><b>{{ item.library_name || item.server || '未标记媒体库' }}</b><span>入库</span><b>{{ item.date_created ? item.date_created.slice(0, 10) : '未知' }}</b><span>尝试</span><b>{{ item.attempts || 0 }}</b></div>
            </article>
            <div v-if="!cleanupPlan.items?.length" class="lt-empty">暂无待处理对象</div>
          </div>
          <div v-if="cleanupPlanTotalPages > 1" class="lt-pagination">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="cleanupPlanPage <= 1" @click="prevCleanupPlanPage" />
            <span>{{ cleanupPlanPage }} / {{ cleanupPlanTotalPages }}（共 {{ cleanupPlan.total || 0 }} 部）</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="cleanupPlanPage >= cleanupPlanTotalPages" @click="nextCleanupPlanPage" />
          </div>
        </section>

        <section v-else class="lt-pane">
          <div class="lt-section-heading">
            <div><div class="lt-section-title">运行历史</div><div class="text-caption text-medium-emphasis">保留最近 30 条模块运行记录，按后端分页查看。</div></div>
            <VChip size="small" variant="tonal">共 {{ historyTotal || 0 }} 条</VChip>
          </div>
          <div class="lt-table-wrap mt-3">
            <VTable class="lt-table" density="compact">
              <thead><tr><th>时间</th><th>模块</th><th>状态</th><th>摘要</th><th>耗时</th></tr></thead>
              <tbody>
                <tr v-for="(item, index) in history" :key="`${item.time}-${index}`">
                  <td class="text-no-wrap">{{ item.time }}</td>
                  <td>{{ item.module_name }}</td>
                  <td><VChip size="x-small" :color="historyStatusColor(item)" variant="tonal">{{ historyStatus(item) }}</VChip></td>
                  <td class="lt-ellipsis" :title="item.summary">{{ item.summary }}</td>
                  <td>{{ item.duration }}s</td>
                </tr>
                <tr v-if="!history.length"><td colspan="5" class="text-center text-medium-emphasis py-8">暂无运行历史</td></tr>
              </tbody>
            </VTable>
          </div>
          <div class="lt-mobile-list">
            <article v-for="(item, index) in history" :key="`mobile-history-${item.time}-${index}`" class="lt-record">
              <div class="lt-record-head"><strong>{{ item.module_name }}</strong><VChip size="x-small" :color="historyStatusColor(item)" variant="tonal">{{ historyStatus(item) }}</VChip></div>
              <div class="lt-record-meta"><span>时间</span><b>{{ item.time }}</b><span>耗时</span><b>{{ item.duration }}s</b></div>
              <div class="lt-record-summary">{{ item.summary }}</div>
            </article>
            <div v-if="!history.length" class="lt-empty">暂无运行历史</div>
          </div>
          <div v-if="historyTotal > historyPageSize" class="lt-pagination">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="historyPage <= 1" @click="prevHistoryPage" />
            <span>{{ historyPage }} / {{ historyTotalPages }}</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="historyPage >= historyTotalPages" @click="nextHistoryPage" />
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.lt-page { height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; overflow: hidden; }
.lt-toolbar { position: sticky; top: 0; z-index: 10; background: transparent; }
.lt-toolbar-title { font-size: 18px; font-weight: 600; }
.lt-layout { flex: 1 1 auto; min-height: 0; display: flex; }
.lt-side { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.lt-side-list { width: 100%; }
.lt-side-item { margin: 2px 8px; }
.lt-main { flex: 1 1 auto; min-width: 0; min-height: 0; padding: 12px; overflow-y: auto; }
.lt-pane { min-width: 0; min-height: 100%; }
.lt-state { min-height: 360px; display: flex; align-items: center; justify-content: center; }
.lt-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.lt-section-title { color: rgb(var(--v-theme-primary)); font-size: 15px; font-weight: 700; }
.lt-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.lt-stat { min-width: 0; display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 10px; padding: 11px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 9px; background: rgba(var(--v-theme-on-surface), .018); }
.lt-stat--warning { border-color: rgba(var(--v-theme-warning), .34); background: rgba(var(--v-theme-warning), .065); }
.lt-stat--error { border-color: rgba(var(--v-theme-error), .4); background: rgba(var(--v-theme-error), .075); }
.lt-stat--success { border-color: rgba(var(--v-theme-success), .3); background: rgba(var(--v-theme-success), .06); }
.lt-stat--info { border-color: rgba(var(--v-theme-info), .3); background: rgba(var(--v-theme-info), .06); }
.lt-stat-content { min-width: 0; }
.lt-stat-label { color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; }
.lt-stat-value { margin-top: 2px; overflow-wrap: anywhere; color: rgba(var(--v-theme-on-surface), .92); font-size: 18px; font-weight: 750; line-height: 1.25; }
.lt-stat-detail { margin-top: 3px; overflow-wrap: anywhere; color: rgba(var(--v-theme-on-surface), .55); font-size: 11px; line-height: 1.35; }
.lt-panel, .lt-attention-panel { padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 9px; background: rgba(var(--v-theme-on-surface), .018); }
.lt-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.lt-flow-step { min-width: 0; display: grid; grid-template-columns: 24px 22px minmax(0, 1fr); gap: 8px; align-items: start; padding: 10px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); }
.lt-flow-index { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .12); font-size: 11px; font-weight: 700; }
.lt-flow-copy { min-width: 0; display: grid; gap: 3px; }
.lt-flow-copy strong { font-size: 13px; }
.lt-flow-copy span { color: rgba(var(--v-theme-on-surface), .6); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; }
.lt-attention-panel { border-color: rgba(var(--v-theme-warning), .3); background: rgba(var(--v-theme-warning), .045); }
.lt-attention-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.lt-attention-item { min-width: 0; display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; padding: 9px 10px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), .025); }
.lt-attention-item strong { font-size: 13px; }
.lt-break-text { overflow-wrap: anywhere; }
.lt-action-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.lt-action-row--right { justify-content: flex-end; }
.lt-plan-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.lt-plan-summary > div { min-width: 0; display: grid; gap: 4px; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.lt-plan-summary span { color: rgba(var(--v-theme-on-surface), .6); font-size: 12px; }
.lt-plan-summary strong { overflow-wrap: anywhere; font-size: 15px; }
.lt-table-wrap { width: 100%; overflow-x: auto; }
.lt-table { min-width: 720px; background: transparent; }
.lt-table :deep(th) { font-weight: 700 !important; }
.lt-ellipsis { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lt-mobile-list { display: none; }
.lt-record { min-width: 0; padding: 11px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); }
.lt-record-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.lt-record-head strong { min-width: 0; overflow-wrap: anywhere; font-size: 13px; }
.lt-record-meta { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 5px 8px; margin-top: 9px; font-size: 12px; }
.lt-record-meta span { color: rgba(var(--v-theme-on-surface), .52); }
.lt-record-meta b { min-width: 0; overflow-wrap: anywhere; color: rgba(var(--v-theme-on-surface), .78); font-weight: 500; }
.lt-record-summary { margin-top: 9px; color: rgba(var(--v-theme-on-surface), .76); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
.lt-empty { padding: 40px 12px; color: rgba(var(--v-theme-on-surface), .58); text-align: center; }
.lt-pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 14px; color: rgba(var(--v-theme-on-surface), .68); font-size: 12px; }
@media (max-width: 1100px) { .lt-stat-grid, .lt-flow-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
  .lt-page { height: min(860px, calc(100dvh - 16px)); }
  .lt-layout { flex-direction: column; }
  .lt-side { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .lt-side::-webkit-scrollbar { display: none; }
  .lt-side-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .lt-side-item { flex: 0 0 auto; min-width: 108px; margin: 0; padding-inline: 10px; }
  .lt-side-item :deep(.v-list-item-title) { white-space: nowrap; }
  .lt-main { padding: 10px; }
  .lt-section-heading { align-items: stretch; flex-direction: column; }
  .lt-action-row--right { justify-content: flex-start; }
  .lt-stat-grid, .lt-flow-grid, .lt-plan-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .lt-attention-list { grid-template-columns: 1fr; }
  .lt-table-wrap { display: none; }
  .lt-mobile-list { display: grid; gap: 8px; }
  .lt-toolbar-title { font-size: 16px; }
}
@media (max-width: 420px) { .lt-stat-grid, .lt-flow-grid, .lt-plan-summary { grid-template-columns: 1fr; } }
</style>
