<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiGet, apiPost, pluginApiPath, recheckCleanupPlan } from '../api.js'
import { fitPlanPage, PLAN_ROW_HEIGHT, PLAN_HEADER_HEIGHT, PLAN_MOBILE_ROW_HEIGHT } from '../cleanupPlanLayout.js'
import { planConditionSummary } from '../planCondition.js'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
})
const emit = defineEmits(['close', 'switch'])

const activeTab = ref('overview')
const status = ref(null)
const cleanupPlan = ref({ total: 0, page: 1, page_size: 15, total_pages: 1, items: [], batch_size: 10 })
const cleanupPlanPage = ref(1)
const cleanupPlanPageSize = ref(15)
const planListElement = ref(null)
const planLoading = ref(false)
const planDetailsOpen = ref(false)
const planDetails = ref(null)
const recheckResultsOpen = ref(false)
let planLoadSequence = 0
let planResizeObserver = null
let planResizeFrame = 0
const history = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 15
const loading = ref(false)
const loadingAction = ref('')
const error = ref('')
const actionMessage = ref('')
const actionOk = ref(false)
const recheckResults = ref([])
let pageActive = true
onBeforeUnmount(() => {
  pageActive = false
  planResizeObserver?.disconnect()
  if (planResizeFrame) cancelAnimationFrame(planResizeFrame)
})

watch(planListElement, (element) => {
  planResizeObserver?.disconnect()
  if (planResizeFrame) cancelAnimationFrame(planResizeFrame)
  if (!element) return
  const resize = () => {
    if (planResizeFrame) cancelAnimationFrame(planResizeFrame)
    planResizeFrame = requestAnimationFrame(() => {
      if (!pageActive || activeTab.value !== 'cleanup_plan' || !element.clientHeight) return
      const next = fitPlanPage(element.clientHeight, window.matchMedia('(max-width: 760px)').matches,
        cleanupPlanPage.value, cleanupPlanPageSize.value)
      if (next.pageSize === cleanupPlanPageSize.value) return
      cleanupPlanPageSize.value = next.pageSize
      cleanupPlanPage.value = next.page
      loadPlan().catch((err) => { if (pageActive) error.value = String(err) })
    })
  }
  planResizeObserver = new ResizeObserver(resize)
  planResizeObserver.observe(element)
  resize()
})

const tabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'cleanup_plan', title: '清理计划', icon: 'mdi-playlist-check' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
]

const historyTotalPages = computed(() => Math.max(1, Math.ceil((historyTotal.value || 0) / historyPageSize)))
const cleanupPlanTotalPages = computed(() => Math.max(1, Number(cleanupPlan.value?.total_pages || Math.ceil((cleanupPlan.value?.total || 0) / cleanupPlanPageSize.value))))
const cleanupStatus = computed(() => status.value?.modules?.library_cleanup || {})
const batchSize = computed(() => Number(cleanupPlan.value?.batch_size || cleanupStatus.value?.cycle_batch_size || 10))
function formatPlanTime(value) {
  if (!value) return '尚未扫描'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
const overviewCards = computed(() => [
  {
    title: '周期扫描',
    value: status.value?.enabled && cleanupStatus.value.scan_enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.scan_cron ? `周期 ${cleanupStatus.value.scan_cron}` : '未设置扫描周期',
    icon: 'mdi-magnify-scan',
    color: status.value?.enabled && cleanupStatus.value.scan_enabled ? 'success' : 'default',
  },
  {
    title: '周期清理',
    value: status.value?.enabled && cleanupStatus.value.cleanup_enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.cleanup_cron ? `周期 ${cleanupStatus.value.cleanup_cron}` : '未设置清理周期',
    icon: 'mdi-calendar-clock-outline',
    color: status.value?.enabled && cleanupStatus.value.cleanup_enabled ? 'success' : 'default',
  },
  {
    title: '清理计划',
    value: `${cleanupPlan.value.total || 0} 部`,
    detail: `最近扫描：${formatPlanTime(cleanupPlan.value.last_scan_at)}`,
    icon: 'mdi-playlist-check',
    color: cleanupPlan.value.total ? 'warning' : 'primary',
  },
  {
    title: '本周期数量',
    value: `${batchSize.value} 部`,
    detail: !cleanupStatus.value.auto_delete ? '自动删除未开启' : cleanupPlan.value.next_cycle_at
      ? `冷却至 ${formatPlanTime(cleanupPlan.value.next_cycle_at)}`
      : `清理冷却 ${cleanupPlan.value.cooldown_minutes ?? cleanupStatus.value.cooldown_minutes ?? 0} 分钟`,
    icon: 'mdi-counter',
    color: 'primary',
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
    items.push({ icon: 'mdi-timer-sand-outline', color: 'info', title: '周期冷却中', detail: `冷却结束：${formatPlanTime(cleanupPlan.value.next_cycle_at)}` })
  }
  return items
})

function apiPath(path) {
  return pluginApiPath(props.pluginId, path)
}

async function loadStatus() {
  const data = await apiGet(props.api, apiPath('local_toolkit/status'))
  if (pageActive) status.value = data
}

async function loadPlan() {
  const sequence = ++planLoadSequence
  planLoading.value = true
  try {
    const data = await apiGet(props.api, apiPath(`local_toolkit/cleanup_plan?page=${cleanupPlanPage.value}&page_size=${cleanupPlanPageSize.value}`))
    if (!pageActive || sequence !== planLoadSequence) return
    cleanupPlan.value = data || { total: 0, page: 1, page_size: cleanupPlanPageSize.value, total_pages: 1, items: [], batch_size: 10 }
    cleanupPlanPage.value = Number(cleanupPlan.value.page || cleanupPlanPage.value)
  } catch (err) {
    if (pageActive && sequence === planLoadSequence) throw err
  } finally {
    if (pageActive && sequence === planLoadSequence) planLoading.value = false
  }
}

async function loadOverview() {
  await Promise.all([loadStatus(), loadPlan()])
}

async function loadHistory() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/history?page=${historyPage.value}&page_size=${historyPageSize}`))
  if (!pageActive) return
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
  if (loadingAction.value) return
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
  if (loadingAction.value) return
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
  if (loadingAction.value) return
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

function showPlanDetails(item) {
  planDetails.value = item
  planDetailsOpen.value = true
}

async function recheckPlan(item = null) {
  if (loadingAction.value) return
  loadingAction.value = item ? `recheck:${item.queue_key}` : 'recheck'
  actionMessage.value = ''
  recheckResults.value = []
  try {
    const response = await recheckCleanupPlan(props.api, props.pluginId, item?.queue_key ?? null)
    if (!pageActive) return
    actionOk.value = response?.success !== false
    actionMessage.value = response?.message || response?.summary || '核验完成'
    recheckResults.value = response?.results || []
    try {
      await refreshAfterAction()
    } catch {
      if (pageActive) actionMessage.value += ' 列表刷新失败，请手动刷新；上方核验结果已保留。'
    }
  } catch (err) {
    if (!pageActive) return
    actionOk.value = false
    actionMessage.value = `${String(err)}；请先刷新计划确认状态，再决定是否重新核验。`
  } finally {
    if (pageActive) loadingAction.value = ''
  }
}

function planRecoveryHint(item) {
  return item.recovery_hint || '点击重新核验查看当前状态及处理办法'
}

function historyStatus(item) {
  return item.status === 'success' ? '成功' : item.status === 'failed' ? '失败' : item.status === 'skipped' ? '跳过' : item.status || '未知'
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
  loadPlan().catch((err) => { if (pageActive) error.value = String(err) })
}

function nextCleanupPlanPage() {
  if (cleanupPlanPage.value >= cleanupPlanTotalPages.value) return
  cleanupPlanPage.value += 1
  loadPlan().catch((err) => { if (pageActive) error.value = String(err) })
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

      <main class="lt-main" :class="{ 'lt-main--plan': activeTab === 'cleanup_plan' }">
        <VAlert v-if="actionMessage" :type="actionOk ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMessage }}</VAlert>
        <VAlert v-if="error" type="error" variant="tonal" class="mb-3" density="compact">{{ error }}</VAlert>
        <div v-if="loading" class="lt-state"><VProgressCircular indeterminate color="primary" /></div>

        <section v-else-if="activeTab === 'overview'" class="lt-pane">
          <div class="lt-section-heading">
            <div>
              <div class="lt-section-title">运行总览</div>
              <div class="text-caption text-medium-emphasis">清理库存按“扫描、入队、按序执行、复核”运行，其他工具保持按需执行。</div>
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
                <div class="text-caption text-medium-emphasis">扫描和清理使用独立周期；扫描更新计划，清理只处理已有计划中的本批对象。</div>
              </div>
              <VChip size="small" color="primary" variant="tonal">每周期 {{ batchSize }} 部</VChip>
            </div>
            <div class="lt-flow-grid mt-3">
              <div v-for="(step, index) in [
                { icon: 'mdi-magnify-scan', title: '周期扫描', detail: '独立扫描周期，仅读取媒体库' },
                { icon: 'mdi-playlist-plus', title: '更新计划', detail: '新增入队，失效移出，失败保留原计划' },
                { icon: 'mdi-format-list-numbered', title: '周期清理', detail: `按序取最多 ${batchSize} 部，逐项复核条件` },
                { icon: 'mdi-check-decagram-outline', title: '删除复核', detail: '确认移除后出队，异常对象保留重试' },
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
              <div><div class="lt-section-title">快速操作</div><div class="text-caption text-medium-emphasis">生成计划会扫描；立即清理只处理已有计划。</div></div>
              <VBtn size="small" variant="text" prepend-icon="mdi-format-list-bulleted" class="text-none" @click="selectTab('cleanup_plan')">查看计划</VBtn>
            </div>
            <div class="lt-action-row mt-3">
              <VBtn color="primary" variant="tonal" prepend-icon="mdi-playlist-plus" :loading="loadingAction === 'scan_plan'" @click="scanPlan">生成计划</VBtn>
              <VBtn color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="loadingAction === 'library_cleanup'" @click="runModule('library_cleanup')">立即清理</VBtn>
              <VBtn color="primary" variant="tonal" prepend-icon="mdi-magnify-scan" :loading="loadingAction === 'check_missing'" @click="runModule('check_missing')">扫描缺集</VBtn>
              <VBtn color="warning" variant="tonal" prepend-icon="mdi-database-refresh-outline" :loading="loadingAction === 'tmdb_cache'" @click="runModule('tmdb_cache')">清TMDB</VBtn>
            </div>
          </section>
        </section>

        <section v-else-if="activeTab === 'cleanup_plan'" class="lt-pane lt-pane--plan">
          <div class="lt-section-heading">
            <div class="lt-section-title text-no-wrap">清理计划</div>
            <div class="lt-action-row lt-action-row--right">
              <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-refresh" :disabled="!!loadingAction || !cleanupPlan.error_count" :loading="loadingAction === 'recheck'" @click="recheckPlan()">核验异常（{{ cleanupPlan.error_count || 0 }}）</VBtn>
              <VBtn size="small" variant="tonal" prepend-icon="mdi-playlist-plus" :loading="loadingAction === 'scan_plan'" @click="scanPlan">生成计划</VBtn>
              <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="loadingAction === 'library_cleanup'" @click="runModule('library_cleanup')">立即清理</VBtn>
              <VBtn size="small" color="warning" variant="text" prepend-icon="mdi-playlist-remove" :disabled="!cleanupPlan.total" :loading="loadingAction === 'clear_plan'" @click="clearPlan">清空计划</VBtn>
            </div>
          </div>

          <div class="lt-plan-summary lt-plan-summary--compact">
            <span>待处理 <strong>{{ cleanupPlan.total || 0 }}</strong> 部</span>
            <span>每批 <strong>{{ batchSize }}</strong> 部</span>
            <span>冷却 {{ cleanupPlan.cooldown_minutes ?? cleanupStatus.cooldown_minutes ?? 0 }} 分钟</span>
            <span>{{ cleanupPlan.next_cycle_at ? `冷却至 ${formatPlanTime(cleanupPlan.next_cycle_at)}` : '可执行' }}</span>
            <VBtn v-if="recheckResults.length" size="x-small" variant="text" color="primary" @click="recheckResultsOpen = true">查看核验结果</VBtn>
          </div>
          <div ref="planListElement" class="lt-plan-list" :aria-busy="planLoading" :class="{ 'lt-plan-list--loading': planLoading }" :style="{ '--lt-plan-row-height': `${PLAN_ROW_HEIGHT}px`, '--lt-plan-header-height': `${PLAN_HEADER_HEIGHT}px`, '--lt-plan-mobile-row-height': `${PLAN_MOBILE_ROW_HEIGHT}px` }">
            <VTable class="lt-table lt-plan-table" density="compact">
              <colgroup><col style="width: 34px"><col><col style="width: 100px"><col style="width: 150px"><col style="width: 44px"><col style="width: 68px"><col style="width: 68px"></colgroup>
              <thead><tr><th>#</th><th>对象</th><th>入库日期</th><th>满足条件</th><th>尝试</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="(item, index) in cleanupPlan.items" :key="item.queue_key || index">
                  <td>{{ (cleanupPlanPage - 1) * cleanupPlanPageSize + index + 1 }}</td>
                  <td :title="item.title || item.code || item.movie_id">{{ item.title || item.code || item.movie_id || '未知对象' }}</td>
                  <td>{{ item.date_created ? item.date_created.slice(0, 10) : '未知' }}</td>
                  <td :title="planConditionSummary(item)">{{ planConditionSummary(item) }}</td>
                  <td>{{ item.attempts || 0 }}</td>
                  <td :class="item.last_error ? 'text-warning' : 'text-primary'" :title="planStatus(item)">{{ item.last_error ? '待核验' : '待处理' }}</td>
                  <td class="lt-plan-actions">
                    <VBtn size="x-small" variant="text" icon="mdi-information-outline" title="查看状态与处理办法" aria-label="查看状态与处理办法" @click="showPlanDetails(item)" />
                    <VBtn size="x-small" variant="text" color="primary" icon="mdi-refresh" title="重新核验（不删除媒体）" aria-label="重新核验" :disabled="!!loadingAction" :loading="loadingAction === `recheck:${item.queue_key}`" @click="recheckPlan(item)" />
                  </td>
                </tr>
                <tr v-if="!cleanupPlan.items?.length"><td colspan="7" class="text-center text-medium-emphasis">暂无待处理对象</td></tr>
              </tbody>
            </VTable>
            <div class="lt-plan-mobile">
              <article v-for="(item, index) in cleanupPlan.items" :key="`mobile-${item.queue_key || index}`" class="lt-plan-mobile-row">
                <div class="lt-plan-mobile-copy">
                  <div class="lt-plan-mobile-title">{{ item.title || item.code || item.movie_id || '未知对象' }}</div>
                  <div class="text-caption text-medium-emphasis">{{ item.date_created ? item.date_created.slice(0, 10) : '日期未知' }} · {{ planConditionSummary(item) }} · {{ item.attempts || 0 }} 次</div>
                </div>
                <span class="text-caption text-no-wrap" :class="item.last_error ? 'text-warning' : 'text-primary'">{{ item.last_error ? '待核验' : '待处理' }}</span>
                <VBtn size="x-small" variant="text" icon="mdi-information-outline" aria-label="查看状态与处理办法" @click="showPlanDetails(item)" />
                <VBtn size="x-small" variant="text" color="primary" icon="mdi-refresh" aria-label="重新核验" :disabled="!!loadingAction" :loading="loadingAction === `recheck:${item.queue_key}`" @click="recheckPlan(item)" />
              </article>
              <div v-if="!cleanupPlan.items?.length" class="lt-empty">暂无待处理对象</div>
            </div>
          </div>
          <div class="lt-pagination lt-plan-pagination">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" aria-label="上一页" :disabled="planLoading || cleanupPlanPage <= 1" @click="prevCleanupPlanPage" />
            <span>{{ cleanupPlanPage }} / {{ cleanupPlanTotalPages }} · 共 {{ cleanupPlan.total || 0 }} 部 · 每页 {{ cleanupPlanPageSize }} 条</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" aria-label="下一页" :disabled="planLoading || cleanupPlanPage >= cleanupPlanTotalPages" @click="nextCleanupPlanPage" />
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
    <VDialog v-model="planDetailsOpen" max-width="620" scrollable>
      <VCard v-if="planDetails" title="条目详情">
        <VCardText class="lt-break-text">
          <div class="text-subtitle-1 mb-3">{{ planDetails.title || planDetails.code || planDetails.movie_id }}</div>
          <dl class="lt-plan-details">
            <dt>媒体库</dt><dd>{{ planDetails.library_name || planDetails.server }}</dd>
            <dt>入库日期</dt><dd>{{ planDetails.date_created ? formatPlanTime(planDetails.date_created) : '未知' }}</dd>
            <dt>清理尝试</dt><dd>{{ planDetails.attempts || 0 }} 次</dd>
            <dt>当前状态</dt><dd>{{ planStatus(planDetails) }}</dd>
            <dt v-if="planDetails.last_error">处理办法</dt><dd v-if="planDetails.last_error">{{ planRecoveryHint(planDetails) }}</dd>
            <dt>最近核验</dt><dd>{{ planDetails.last_recheck_at ? formatPlanTime(planDetails.last_recheck_at) : '尚未核验' }}</dd>
          </dl>
          <div class="text-caption text-medium-emphasis mt-4">重新核验只查询媒体状态，不删除媒体。批量每次最多核验 10 部异常条目。</div>
        </VCardText>
        <VCardActions><VSpacer /><VBtn @click="planDetailsOpen = false">关闭</VBtn></VCardActions>
      </VCard>
    </VDialog>
    <VDialog v-model="recheckResultsOpen" max-width="680" scrollable>
      <VCard title="核验结果">
        <VCardText class="lt-recheck-results">
          <div v-for="result in recheckResults" :key="result.queue_key" class="lt-record">
            <strong>{{ result.title }}</strong><div class="mt-1">{{ result.reason }}</div>
            <div class="text-caption text-medium-emphasis mt-1">{{ result.action }}</div>
          </div>
        </VCardText>
        <VCardActions><VSpacer /><VBtn @click="recheckResultsOpen = false">关闭</VBtn></VCardActions>
      </VCard>
    </VDialog>
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
.lt-main--plan { display: flex; flex-direction: column; overflow: hidden; }
.lt-main--plan > :not(.lt-pane--plan) { flex-shrink: 0; }
.lt-pane--plan { display: flex; flex: 1 1 auto; flex-direction: column; min-height: 0; }
.lt-pane--plan > :not(.lt-plan-list) { flex-shrink: 0; }
.lt-plan-summary--compact { display: flex; flex-wrap: wrap; align-items: center; column-gap: 16px; row-gap: 4px; margin: 8px 0; }
.lt-plan-summary--compact strong { font-size: 12px; }
.lt-plan-list { flex: 1 1 0; min-height: 0; overflow: hidden; }
.lt-plan-list--loading { opacity: .55; pointer-events: none; }
.lt-plan-table { min-width: 0; --v-table-row-height: var(--lt-plan-row-height); --v-table-header-height: var(--lt-plan-header-height); }
.lt-plan-table :deep(.v-table__wrapper) { overflow: hidden; }
.lt-plan-table :deep(table) { width: 100%; table-layout: fixed; }
.lt-plan-table :deep(th), .lt-plan-table :deep(td) { padding: 0 6px !important; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.lt-plan-table :deep(td) { height: var(--lt-plan-row-height) !important; }
.lt-plan-table :deep(th) { height: var(--lt-plan-header-height) !important; }
.lt-plan-table :deep(.lt-plan-actions) { padding: 0 !important; }
.lt-pane--plan .lt-plan-pagination { padding: 6px 0 0; min-height: 34px; }
.lt-plan-mobile { display: none; }
.lt-plan-mobile-row { display: flex; align-items: center; gap: 4px; height: var(--lt-plan-mobile-row-height); box-sizing: border-box; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.lt-plan-mobile-copy { flex: 1; min-width: 0; }
.lt-plan-mobile-copy > div { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lt-plan-mobile-title { font-size: 13px; font-weight: 600; }
.lt-plan-details { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 10px 12px; }
.lt-plan-details dt { color: rgba(var(--v-theme-on-surface), .6); }
.lt-plan-details dd { margin: 0; }
.lt-recheck-results { display: grid; gap: 6px; overflow-wrap: anywhere; }
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
  .lt-plan-table { display: none; }
  .lt-plan-mobile { display: block; }
  .lt-mobile-list { display: grid; gap: 8px; }
  .lt-toolbar-title { font-size: 16px; }
}
@media (max-width: 420px) { .lt-stat-grid, .lt-flow-grid, .lt-plan-summary { grid-template-columns: 1fr; } }
</style>
