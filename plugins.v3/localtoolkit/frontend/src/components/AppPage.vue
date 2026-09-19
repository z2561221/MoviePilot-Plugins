<script setup>
import { ref, onMounted, computed } from 'vue'
import { apiGet, apiPost, pluginApiPath } from '../api.js'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
})
const emit = defineEmits(['close'])

const status = ref(null)
const history = ref([])
const total = ref(0)
const cleanupPlan = ref({ total: 0, items: [], batch_size: 10 })
const loadingModule = ref('')
const loadingPlanAction = ref('')
const result = ref(null)
const page = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))
const pagedHistory = computed(() => history.value || [])

const modules = computed(() => [
  {
    key: 'library_cleanup',
    title: '清理库存',
    icon: 'mdi-delete-sweep-outline',
    color: 'error',
    action: '执行一周期',
    mode: '周期 + 按需',
    desc: '周期先完整扫描并更新清理计划，再按队列倒序处理一批对象。',
    meta: [
      `周期：${status.value?.modules?.library_cleanup?.enabled ? '开启' : '关闭'}`,
      `自动删除：${status.value?.modules?.library_cleanup?.auto_delete ? '开启' : '关闭'}`,
      `计划队列：${status.value?.modules?.library_cleanup?.plan_count || 0} 部`,
      `每周期：${status.value?.modules?.library_cleanup?.cycle_batch_size || 10} 部`,
    ],
  },
  {
    key: 'check_missing',
    title: '扫描缺集',
    icon: 'mdi-magnify-scan',
    color: 'primary',
    action: '立即扫描',
    mode: '按需单次',
    desc: '扫描配置路径，按已存在季检查缺集，不注册后台周期服务。',
    meta: [
      `路径：${status.value?.modules?.check_missing?.paths || 0} 个`,
      `上次结果：${status.value?.modules?.check_missing?.last_count || 0} 条`,
      '后台周期：无',
    ],
  },
  {
    key: 'tmdb_cache',
    title: '清理TMDB',
    icon: 'mdi-database-refresh-outline',
    color: 'warning',
    action: '立即清理',
    mode: '按需单次',
    desc: '查询并清理 Redis 中的 TMDB 缓存，不注册后台周期服务。',
    meta: [
      `缓存键：${status.value?.modules?.tmdb_cache?.keys || 0}`,
      `大小：${((status.value?.modules?.tmdb_cache?.size_kb || 0) / 1024).toFixed(2)} MB`,
      status.value?.modules?.tmdb_cache?.error ? `错误：${status.value.modules.tmdb_cache.error}` : '后台周期：无',
    ],
  },
])

async function load() {
  try {
    const [currentStatus, hist, plan] = await Promise.all([
      apiGet(props.api, pluginApiPath(props.pluginId, 'local_toolkit/status')),
      apiGet(props.api, pluginApiPath(props.pluginId, `local_toolkit/history?page=${page.value}&page_size=${pageSize}`)),
      apiGet(props.api, pluginApiPath(props.pluginId, 'local_toolkit/cleanup_plan?page=1&page_size=50')),
    ])
    status.value = currentStatus
    history.value = hist.items || []
    total.value = hist.total || 0
    cleanupPlan.value = plan || { total: 0, items: [], batch_size: 10 }
  } catch (e) {
    result.value = { success: false, message: String(e) }
  }
}

async function run(moduleKey) {
  loadingModule.value = moduleKey
  try {
    result.value = await apiPost(props.api, pluginApiPath(props.pluginId, `local_toolkit/run/${moduleKey}`))
  } catch (e) {
    result.value = { success: false, message: String(e) }
  } finally {
    loadingModule.value = ''
    await load()
  }
}

async function scanPlan() {
  loadingPlanAction.value = 'scan'
  try {
    result.value = await apiPost(props.api, pluginApiPath(props.pluginId, 'local_toolkit/cleanup_plan/scan'))
  } catch (e) {
    result.value = { success: false, message: String(e) }
  } finally {
    loadingPlanAction.value = ''
    await load()
  }
}

async function clearPlan() {
  if (!window.confirm('确认清空当前清理计划吗？这不会删除媒体库条目。')) return
  loadingPlanAction.value = 'clear'
  try {
    result.value = await apiPost(props.api, pluginApiPath(props.pluginId, 'local_toolkit/cleanup_plan/clear'))
  } catch (e) {
    result.value = { success: false, message: String(e) }
  } finally {
    loadingPlanAction.value = ''
    await load()
  }
}

function planStatus(item) {
  return item.last_error || '待处理'
}

function planStatusColor(item) {
  return item.last_error ? 'warning' : 'primary'
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    load()
  }
}
function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    load()
  }
}

onMounted(load)
</script>

<template>
  <div class="toolkit-page pa-4">
    <VToolbar density="comfortable" class="toolkit-toolbar mb-4">
      <VIcon icon="mdi-tools" color="primary" class="ms-4 me-3" />
      <div class="toolbar-copy">
        <div class="text-h6">工具中心</div>
        <div class="text-caption text-medium-emphasis toolbar-subtitle">清理库存保留周期运行；扫描缺集与清理 TMDB 改为按需单次执行。</div>
        <!--
        <VCardTitle class="text-h6">工具中心</VCardTitle>
        <VCardSubtitle>清理库存保留周期运行；扫描缺集与清理TMDB改为按需单次执行。</VCardSubtitle>
        <template #append>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" @click="load">刷新</VBtn>
          <VBtn size="small" variant="text" icon="mdi-close" @click="emit('close')" class="ml-1" />
        </template>
      </VCardItem>
    </VCard>

        -->
      </div>
      <VSpacer />
      <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" class="text-none me-1" @click="load">刷新</VBtn>
      <VBtn size="small" variant="text" icon="mdi-close" @click="emit('close')" />
    </VToolbar>

    <VAlert v-if="result" :type="result.success !== false ? 'success' : 'error'" variant="tonal" class="mb-4" :text="result.message || result.summary || JSON.stringify(result)" />

    <VRow class="mb-4">
      <VCol v-for="item in modules" :key="item.key" cols="12" md="4">
        <VCard class="module-card" :color="item.color" variant="tonal">
          <VCardText>
            <div class="d-flex align-center mb-2">
              <VIcon :icon="item.icon" size="24" class="mr-2" />
              <div>
                <div class="text-h6">{{ item.title }}</div>
                <VChip size="x-small" :color="item.color" variant="flat">{{ item.mode }}</VChip>
              </div>
            </div>
            <div class="module-desc">{{ item.desc }}</div>
            <div class="mt-3">
              <div v-for="m in item.meta" :key="m" class="module-meta">{{ m }}</div>
            </div>
            <VBtn class="mt-4" block :color="item.color" variant="flat" :prepend-icon="item.icon" :loading="loadingModule === item.key" @click="run(item.key)">
              {{ item.action }}
            </VBtn>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VCard class="plan-card mb-4" variant="flat">
      <VCardItem>
        <VCardTitle>清理计划</VCardTitle>
        <VCardSubtitle>
          扫描先入队，执行时按队列倒序处理，每周期最多 {{ cleanupPlan.batch_size || 10 }} 部；当前 {{ cleanupPlan.total || 0 }} 部。
        </VCardSubtitle>
        <template #append>
          <div class="plan-actions">
            <VBtn size="small" variant="tonal" prepend-icon="mdi-playlist-plus" :loading="loadingPlanAction === 'scan'" @click="scanPlan">生成计划</VBtn>
            <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="loadingModule === 'library_cleanup'" @click="run('library_cleanup')">执行一周期</VBtn>
            <VBtn size="small" color="warning" variant="text" prepend-icon="mdi-playlist-remove" :disabled="!cleanupPlan.total" :loading="loadingPlanAction === 'clear'" @click="clearPlan">清空计划</VBtn>
          </div>
        </template>
      </VCardItem>
      <VDivider />
      <VAlert v-if="cleanupPlan.next_cycle_at" type="info" variant="tonal" density="compact" class="ma-4 mb-2" :text="`下次可执行：${cleanupPlan.next_cycle_at}；冷却 ${cleanupPlan.cooldown_minutes || 0} 分钟。`" />
      <div class="plan-mobile">
        <div v-for="(item, i) in cleanupPlan.items" :key="`plan-mobile-${item.queue_key || i}`" class="plan-mobile-item">
          <div class="plan-mobile-main">
            <div class="plan-mobile-title">{{ item.title || item.code || item.movie_id || '未知对象' }}</div>
            <VChip size="x-small" :color="planStatusColor(item)" variant="tonal">{{ planStatus(item) }}</VChip>
          </div>
          <div class="plan-mobile-meta">
            <span>{{ item.library_name || item.server || '未标记媒体库' }}</span>
            <span>尝试 {{ item.attempts || 0 }} 次</span>
          </div>
        </div>
        <div v-if="!cleanupPlan.items?.length" class="text-center text-medium-emphasis py-6">暂无待处理对象</div>
      </div>
      <VTable class="plan-table" density="compact">
        <thead><tr><th>#</th><th>对象</th><th>媒体库</th><th>尝试</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="(item, i) in cleanupPlan.items" :key="item.queue_key || i">
            <td>{{ i + 1 }}</td>
            <td>{{ item.title || item.code || item.movie_id || '未知对象' }}</td>
            <td>{{ item.library_name || item.server || '未标记媒体库' }}</td>
            <td>{{ item.attempts || 0 }}</td>
            <td><VChip size="x-small" :color="planStatusColor(item)" variant="tonal">{{ planStatus(item) }}</VChip></td>
          </tr>
          <tr v-if="!cleanupPlan.items?.length"><td colspan="5" class="text-center text-medium-emphasis py-6">暂无待处理对象</td></tr>
        </tbody>
      </VTable>
    </VCard>

    <VCard class="history-card" variant="flat">
      <VCardItem>
        <VCardTitle>运行历史</VCardTitle>
        <VCardSubtitle>每页 10 条，共 {{ total || 0 }} 条记录。</VCardSubtitle>
        <template #append>
          <div class="d-flex align-center">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="page <= 1" @click="prevPage" class="mr-1" />
            <span class="text-caption mx-1">{{ page }} / {{ totalPages }}</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="page >= totalPages" @click="nextPage" />
          </div>
        </template>
      </VCardItem>
      <VDivider />
      <div class="history-mobile">
        <div v-for="(h, i) in pagedHistory" :key="`mobile-${(page - 1) * pageSize + i}`" class="history-mobile-item">
          <div class="history-mobile-main">
            <div class="history-mobile-title">{{ h.module_name }}</div>
            <VChip size="x-small" :color="h.status === 'success' ? 'success' : 'error'" variant="tonal">{{ h.status }}</VChip>
          </div>
          <div class="history-mobile-summary">{{ h.summary }}</div>
          <div class="history-mobile-meta">
            <span>{{ h.time }}</span>
            <span>{{ h.duration }}s</span>
          </div>
        </div>
        <div v-if="!pagedHistory.length" class="text-center text-medium-emphasis py-6">暂无运行历史</div>
      </div>
      <VTable class="history-table" density="compact">
        <thead><tr><th>时间</th><th>模块</th><th>状态</th><th>摘要</th><th>耗时</th></tr></thead>
        <tbody>
          <tr v-for="(h, i) in pagedHistory" :key="(page - 1) * pageSize + i">
            <td>{{ h.time }}</td>
            <td>{{ h.module_name }}</td>
            <td><VChip size="x-small" :color="h.status === 'success' ? 'success' : 'error'" variant="tonal">{{ h.status }}</VChip></td>
            <td>{{ h.summary }}</td>
            <td>{{ h.duration }}s</td>
          </tr>
          <tr v-if="!pagedHistory.length"><td colspan="5" class="text-center text-medium-emphasis py-6">暂无运行历史</td></tr>
        </tbody>
      </VTable>
    </VCard>
  </div>
</template>

<style scoped>
.toolkit-page { background: linear-gradient(180deg, rgba(var(--v-theme-primary), .04), transparent 220px); }
.toolkit-toolbar, .plan-card, .history-card { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.toolkit-toolbar { background: rgb(var(--v-theme-surface)); }
.toolbar-copy { min-width: 0; }
.toolbar-subtitle { max-width: min(720px, 58vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.module-card { border-radius: 16px; min-height: 245px; height: 100%; }
.module-desc { font-size: 13px; line-height: 1.55; color: rgba(var(--v-theme-on-surface), .72); min-height: 42px; }
.module-meta { font-size: 12px; line-height: 1.7; color: rgba(var(--v-theme-on-surface), .68); }
.plan-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.plan-mobile { display: none; }
.plan-table th { font-weight: 700; }
.history-mobile { display: none; }
th { font-weight: 700; }
@media (max-width: 600px) {
  .plan-actions { justify-content: flex-start; margin-top: 8px; }
  .plan-table { display: none; }
  .plan-mobile { display: block; }
  .plan-mobile-item { padding: 12px 16px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
  .plan-mobile-item:last-child { border-bottom: 0; }
  .plan-mobile-main { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .plan-mobile-title { min-width: 0; font-size: 14px; font-weight: 700; overflow-wrap: anywhere; }
  .plan-mobile-meta { display: flex; justify-content: space-between; gap: 12px; margin-top: 8px; font-size: 12px; color: rgba(var(--v-theme-on-surface), .58); }
  .history-table { display: none; }
  .history-mobile { display: block; }
  .history-mobile-item { padding: 12px 16px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
  .history-mobile-item:last-child { border-bottom: 0; }
  .history-mobile-main { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .history-mobile-title { min-width: 0; font-size: 14px; font-weight: 700; overflow-wrap: anywhere; }
  .history-mobile-summary { margin-top: 6px; font-size: 13px; line-height: 1.5; color: rgba(var(--v-theme-on-surface), .76); overflow-wrap: anywhere; }
  .history-mobile-meta { display: flex; justify-content: space-between; gap: 12px; margin-top: 8px; font-size: 12px; color: rgba(var(--v-theme-on-surface), .58); }
}
</style>
