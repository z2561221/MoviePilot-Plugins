<script setup>
import './form-layout.css'
import './history-layout.css'
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { getPluginApi, postPluginJsonApi, isApiRequestCancellation } from './api'
import HistoryRow from './HistoryRow.vue'
import AutoDeleteCron from './AutoDeleteCron.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null }, pluginId: { type: String, required: true }, canManage: Boolean,
  mode: { type: String, default: 'history' }, section: { type: String, default: 'basic' },
  active: { type: Boolean, default: true },
  downloaderRequest: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'show-advanced'])
const confirmationHeading = ref(null)
async function showRuleConfirmation() {
  emit('show-advanced')
  await nextTick()
  confirmationHeading.value?.focus?.()
}
const settings = ref(null)
const revision = ref(0)
const saved = ref('')
const downloaders = ref([])
const downloadersReady = ref(false)
const status = ref({})
const records = ref([])
const total = ref(0)
const page = ref(1)
const filterState = ref('')
const filterRule = ref('')
const filterDownloader = ref('')
const previewResult = ref(null)
const busy = ref('')
const message = ref('')
const error = ref('')
const confirmRule = ref(null)
const confirmJobs = ref([])
const confirmPage = ref(1)
const confirmTotal = ref(0)
const confirmEvidence = ref({})
const selectedJobs = ref([])
const acceptHistory = ref(false)
const detail = ref(null)
const historyLoading = ref(false)
let context = 0
let loadRevision = 0
let disposed = false
let timer = null
let polling = false
const dirty = computed(() => settings.value && JSON.stringify(settings.value) !== saved.value)
const needsSourcePaths = computed(() => settings.value?.rules.some(rule => rule.enabled && rule.action === 'data'))
const missingSourcePaths = computed(() => needsSourcePaths.value && !settings.value.source_paths.length)
const sourcePathMessage = '请填写「允许删除的下载目录」。选择删除下载数据时，至少需要一个 MP 容器内的下载目录。'
const ruleIdMessage = '无法生成规则编号，未添加规则'
const regexFields = [
  ['name_include', '种子名称包含正则'], ['name_exclude', '种子名称排除正则'],
  ['path_include', '保存路径包含正则'], ['path_exclude', '保存路径排除正则'],
  ['tracker_include', 'Tracker 包含正则'], ['tracker_exclude', 'Tracker 排除正则'],
  ['tracker_error', 'Tracker 状态/报错正则'], ['category', '分类正则'],
  ['tag_include', '标签包含正则'], ['tag_exclude', '标签排除正则'],
]
const numberFields = [['ratio_min', '最小分享率'], ['ratio_max', '最大分享率'], ['seed_hours_min', '最少做种小时'],
  ['added_hours_min', '最少添加小时'], ['size_gib_min', '最小体积 GiB'], ['size_gib_max', '最大体积 GiB'], ['upload_kib_max', '最大上传 KiB/s']]
const stateItems = [{ title: '全部结果', value: '' }, { title: '已暂停', value: 'paused' }, { title: '等待正式处理', value: 'approved' },
  { title: '待复核', value: 'review' }, { title: '已移除种子', value: 'removed' }, { title: '已删除种子及数据', value: 'deleted' }, { title: '已解除保护', value: 'released' }]
const pages = computed(() => Math.max(1, Math.ceil(total.value / 15)))
const protectedStates = new Set(['paused', 'review', 'approved'])
const getApi = path => getPluginApi(props.api, props.pluginId, path, { feedback: 'silent' })
const postApi = (path, body = {}) => postPluginJsonApi(props.api, props.pluginId, path, body, { feedback: 'silent' })
function copy(value) { return JSON.parse(JSON.stringify(value)) }
function timeText(value) { return value ? new Date(value * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '暂无记录' }
function stateText(value) { return stateItems.find(item => item.value === value)?.title || ({ prepared: '准备中', removing: '移除中', deleting: '删除文件中', absent: '原任务已不存在' })[value] || value }
function recordColor(value) { return value === 'review' ? 'warning' : ['removed', 'deleted', 'released', 'absent'].includes(value) ? 'success' : 'info' }
function owns(revisionAtStart) { return !disposed && revisionAtStart === context }
function formatError(reason) {
  const payload = reason?.payload ?? reason?.response?.data
  const issues = Array.isArray(payload?.data) ? payload.data : payload?.detail
  if (Array.isArray(issues)) {
    const messages = issues.map(issue => {
      const message = issue?.message || issue?.msg
      if (!message) return ''
      const path = (issue.location || issue.loc || []).filter(part => !['body', 'settings'].includes(part)).join('.')
      const detail = message.replace(/^Value error,\s*/i, '')
      return path ? `${path}：${detail}` : detail
    }).filter(Boolean)
    if (messages.length) return messages.join('；')
  }
  return (typeof issues === 'string' && issues) || payload?.message || reason?.message || '请求失败'
}

async function load({ all = false } = {}) {
  const current = context
  const request = ++loadRevision
  if (props.mode === 'history') historyLoading.value = true
  const query = new URLSearchParams({ page: String(page.value), page_size: '15', state: filterState.value, rule_id: filterRule.value, downloader: filterDownloader.value })
  const tasks = [getApi('auto_delete/status').then(value => {
    if (owns(current) && request === loadRevision) status.value = value
  })]
  if (props.mode === 'history') tasks.push(getApi(`auto_delete/history?${query}`).then(value => {
    if (!owns(current) || request !== loadRevision) return
    records.value = value.items || []
    total.value = value.total || 0
  }))
  if (all) {
    tasks.push(getApi('auto_delete/config').then(value => {
      if (!owns(current) || dirty.value || request !== loadRevision && settings.value) return
      settings.value = copy(value.settings)
      saved.value = JSON.stringify(settings.value)
      revision.value = value.revision
    }))
    tasks.push((props.downloaderRequest || getApi('downloaders')).then(value => {
      if (owns(current)) {
        downloaders.value = (value || []).filter(item => ['qbittorrent', 'transmission'].includes(item.type))
        downloadersReady.value = true
      }
    }))
  }
  const results = await Promise.allSettled(tasks)
  if (!owns(current) || request !== loadRevision) return
  const failed = results.find(item => item.status === 'rejected' && !isApiRequestCancellation(item.reason))
  if (failed) error.value = formatError(failed.reason)
  historyLoading.value = false
}

async function action(name, callback) {
  if (busy.value || !props.canManage) return false
  const current = context
  busy.value = name
  error.value = ''
  message.value = ''
  try {
    await callback(current)
    if (owns(current)) await load()
    return owns(current)
  } catch (reason) {
    if (owns(current) && !isApiRequestCancellation(reason)) {
      error.value = formatError(reason)
      if (reason?.payload?.data?.items?.length) await load()
    }
    return false
  } finally { if (owns(current)) busy.value = '' }
}

function createRuleId() {
  const usedIds = new Set(settings.value.rules.map(rule => rule.id))
  const bytes = new Uint8Array(16)
  for (let attempt = 0; attempt < 5; attempt++) {
    try { globalThis.crypto.getRandomValues(bytes) } catch { return null }
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const id = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
    if (!usedIds.has(id)) return id
  }
  return null
}
function appendRule(makeRule) {
  const id = createRuleId()
  if (!id) { error.value = ruleIdMessage; return }
  settings.value.rules.push(makeRule(id))
  if (error.value === ruleIdMessage) error.value = ''
}
function newRule(id) {
  return { id, name: '新规则', revision: 1, enabled: false, mode: 'debug', action: 'torrent',
    downloaders: [], ignore_case: true, consecutive: 2, conditions: Object.fromEntries([...regexFields.map(([key]) => [key, '']), ...numberFields.map(([key]) => [key, null])]) }
}
function addRule() { appendRule(newRule) }
function duplicate(rule) {
  appendRule(id => ({ ...copy(rule), id, name: `${rule.name} 副本`, revision: 1, mode: 'debug', enabled: false }))
}
function numberValue(rule, key, value) {
  rule.conditions[key] = value === '' || value === null ? null : Number(value)
}
function setPaths(key, value) { settings.value[key] = String(value || '').split('\n').map(item => item.trim()).filter(Boolean) }
function checkedDraft() {
  if (missingSourcePaths.value) throw new Error(sourcePathMessage)
  for (const rule of settings.value.rules) {
    for (const [key, label] of numberFields) {
      const value = rule.conditions[key]
      if (value !== null && value !== undefined && (!Number.isFinite(value) || value < 0)) throw new Error(`${rule.name}：${label} 必须是非负数或留空`)
    }
  }
  return copy(settings.value)
}
function publishSettings(response) {
  settings.value = copy(response.settings)
  revision.value = response.revision
  saved.value = JSON.stringify(settings.value)
  emit('saved', { ...Object.fromEntries(Object.entries(settings.value).map(([key, value]) => ['auto_delete_' + key, copy(value)])), auto_delete_config_revision: response.revision })
}
async function save() {
  const expected = revision.value
  return action('save', async current => {
    const draft = checkedDraft()
    const response = await postApi('auto_delete/config', { expected_revision: expected, settings: draft })
    if (!owns(current)) return
    if (JSON.stringify(settings.value) === JSON.stringify(draft)) publishSettings(response)
    else {
      revision.value = response.revision
      saved.value = JSON.stringify(response.settings)
      emit('saved', { ...Object.fromEntries(Object.entries(response.settings).map(([key, value]) => ['auto_delete_' + key, copy(value)])), auto_delete_config_revision: response.revision })
    }
    previewResult.value = null
    message.value = '设置已保存。修改关键条件后，相关规则自动回到暂停调试。'
  })
}
async function preview() {
  await action('preview', async current => {
    const draft = checkedDraft()
    const response = await postApi('auto_delete/preview', { settings: draft })
    if (owns(current) && JSON.stringify(settings.value) === JSON.stringify(draft)) previewResult.value = response
  })
}
async function run() { await action('run', async current => { const response = await postApi('auto_delete/run'); if (owns(current)) message.value = response.message || '扫描已受理，请查看执行记录。' }) }
async function stop() { await action('stop', async current => { const response = await postApi('auto_delete/stop'); if (owns(current)) { publishSettings(response); message.value = '自动删除已停止，原有暂停保护继续保留。' } }) }
async function beginConfirm(rule) {
  if (dirty.value) { error.value = '请先保存规则，再确认当前生效配置。'; return }
  await action('confirm-load', async current => {
    const response = await getApi(`auto_delete/history?page=1&page_size=100&state=paused,review&rule_id=${encodeURIComponent(rule.id)}`)
    if (!owns(current)) return
    confirmRule.value = rule
    confirmPage.value = 1
    confirmTotal.value = response.total || 0
    confirmJobs.value = (response.items || []).filter(item => ['paused', 'approved'].includes(item.stage) && !item.interfered && !item.files?.some(file => file.deleted))
    confirmEvidence.value = Object.fromEntries(confirmJobs.value.map(item => [item.id, item.evidence_fingerprint]))
    selectedJobs.value = []
    acceptHistory.value = false
  })
}
async function loadConfirmPage(value) {
  confirmPage.value = value
  const ruleId = confirmRule.value?.id
  if (!ruleId) return
  await action('confirm-load', async current => {
    const response = await getApi(`auto_delete/history?page=${value}&page_size=100&state=paused,review&rule_id=${encodeURIComponent(ruleId)}`)
    if (!owns(current) || confirmRule.value?.id !== ruleId || confirmPage.value !== value) return
    confirmTotal.value = response.total || 0
    confirmJobs.value = (response.items || []).filter(item => ['paused', 'approved'].includes(item.stage) && !item.interfered && !item.files?.some(file => file.deleted))
    confirmEvidence.value = { ...confirmEvidence.value, ...Object.fromEntries(confirmJobs.value.map(item => [item.id, item.evidence_fingerprint])) }
  })
}
async function activate() {
  const body = { expected_revision: revision.value, rule_id: confirmRule.value.id, job_ids: [...selectedJobs.value],
    evidence_versions: Object.fromEntries(selectedJobs.value.map(id => [id, confirmEvidence.value[id]])),
    accept_history: acceptHistory.value }
  await action('activate', async current => {
    const response = await postApi('auto_delete/activate', body)
    if (owns(current)) { publishSettings(response); confirmRule.value = null; message.value = '规则正式启用。所选暂停任务等下一轮或手动运行处理。' }
  })
}
async function release(record, restore) {
  await action('release', async current => {
    await postApi('auto_delete/release', { job_ids: [record.id], restore })
    if (owns(current)) message.value = restore ? '已按原运行状态处理恢复；原本暂停的任务保持暂停。' : '已解除本任务保护，任务继续保持原状态。'
  })
}
watch(() => [props.pluginId, props.api, props.mode], async () => {
  context++
  status.value = {}
  downloaders.value = []
  downloadersReady.value = false
  settings.value = null
  previewResult.value = null
  error.value = ''
  busy.value = ''
  confirmRule.value = null
  detail.value = null
  records.value = []
  total.value = 0
  page.value = 1
  filterState.value = ''
  filterRule.value = ''
  filterDownloader.value = ''
  await load({ all: true })
}, { immediate: true })
watch(() => [filterState.value, filterRule.value, filterDownloader.value], () => {
  if (props.mode !== 'history') return
  if (page.value !== 1) page.value = 1
  else load()
})
watch(page, () => { if (props.mode === 'history') load() })
watch(() => props.active, active => { if (!active) { confirmRule.value = null; detail.value = null } })
watch(settings, () => {
  previewResult.value = null
  if (error.value === sourcePathMessage && !missingSourcePaths.value) error.value = ''
}, { deep: true })
timer = setInterval(async () => {
  if (disposed || !props.active || busy.value || polling || document.visibilityState !== 'visible') return
  polling = true
  try { await load() } finally { polling = false }
}, 30000)
onBeforeUnmount(() => { disposed = true; context++; clearInterval(timer) })
defineExpose({ refresh: () => load(), save, dirty, busy, error, missingSourcePaths })
</script>

<template>
  <section class="dm-auto-delete">
    <div v-if="mode === 'history' || section === 'basic'" class="dm-auto-toolbar">
      <strong>自动删除 · {{ status.debug_rules || 0 }} 条调试 / {{ status.delete_rules || 0 }} 条正式规则</strong>
      <VBtn size="small" variant="text" prepend-icon="mdi-refresh" @click="load()">刷新</VBtn>
      <VBtn :disabled="!canManage || !status.active || Boolean(busy) || dirty" size="small" color="primary" variant="tonal" @click="run">立即运行一次</VBtn>
      <VBtn :disabled="!canManage || !status.enabled || Boolean(busy)" size="small" color="warning" @click="stop">一键停止</VBtn>
    </div>
    <div v-if="mode === 'history' || section === 'basic'" class="text-caption text-medium-emphasis my-3">最近扫描 {{ timeText(status.last_scan) }} · 下次运行 {{ timeText(status.next_run) }} · 保护 {{ status.protected || 0 }} · 待复核 {{ status.pending || 0 }}</div>
    <VAlert v-if="['running','accepted'].includes(status.state) || status.once_pending" type="info" density="compact" variant="tonal" class="mb-3">扫描{{ status.once_pending ? '等待执行' : '正在进行' }} · {{ status.stage }} · 任务 {{ status.run_id }}</VAlert>
    <VAlert v-for="item in status.errors || []" :key="item" type="warning" density="compact" variant="tonal" class="mb-2">{{ item }}</VAlert>
    <div v-if="(mode === 'history' || section === 'advanced') && Object.keys(status.capabilities || {}).length" class="text-caption text-medium-emphasis mb-3">
      <div v-for="(capability, name) in status.capabilities" :key="name">{{ name }} · 做种时间 {{ capability.seed_seconds === null ? '尚未确认' : capability.seed_seconds ? '可用' : '部分缺失' }} · 分类 {{ capability.category === null ? '尚未确认' : capability.category ? '可用' : '不可用或部分缺失' }} · Tracker {{ capability.trackers === null ? '尚未查询' : capability.trackers ? '可用' : '不可用或部分缺失' }}</div>
    </div>
    <VAlert v-if="error || status.error" type="error" variant="tonal" class="mb-3">{{ error || status.error }}</VAlert>
    <VAlert v-if="message" type="info" variant="tonal" class="mb-3">{{ message }}</VAlert>
    <VProgressLinear v-if="!settings && !error" color="primary" indeterminate class="mb-3" />
    <template v-if="mode === 'config' && settings">
      <section v-if="section === 'basic'" data-config-section="basic">
        <h3 class="dm-auto-section-title">基础设置</h3>
        <VAlert type="info" variant="tonal" density="compact" class="mb-3" title="从暂停调试转为正式删种">
          保存规则并成功完成一次调试扫描后，到「高级选项 → 规则处置与确认」，展开规则，点「确认并正式启用」。
          <VBtn size="small" variant="tonal" color="primary" class="mt-2 d-flex" @click="showRuleConfirmation">前往规则处置与确认</VBtn>
        </VAlert>
        <p class="text-caption text-medium-emphasis mb-3">调试与正式共用扫描周期。手动运行保留原定时，执行记录可在详情页查看。</p>
        <VRow class="dm-form-grid">
          <VCol cols="12" md="6" class="dm-form-field"><VSwitch v-model="settings.enabled" :disabled="!canManage" label="启用自动删除模块" hide-details color="success" inset /></VCol>
          <VCol cols="12" md="6" class="dm-form-field"><VSwitch v-model="settings.notify" :disabled="!canManage" label="发送结果通知" hide-details color="info" inset /></VCol>
          <VCol cols="12" md="6" class="dm-form-field"><VSelect v-model="settings.schedule_type" :disabled="!canManage" label="运行方式" :items="[{title:'固定间隔',value:'interval'},{title:'Cron 定时',value:'cron'}]" density="compact" variant="outlined" hide-details /></VCol>
          <VCol v-if="settings.schedule_type === 'interval'" cols="12" md="6" class="dm-form-field"><VTextField v-model.number="settings.interval_minutes" :disabled="!canManage" label="扫描间隔（分钟）" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol>
          <VCol v-else cols="12" md="6" class="dm-form-field"><AutoDeleteCron v-model="settings.cron" :disabled="!canManage" /></VCol>
        </VRow>
      </section>
      <section v-if="section === 'advanced'" data-config-section="advanced">
        <h3 class="dm-auto-section-title">高级选项</h3>
        <VRow class="dm-form-grid">
          <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model.number="settings.max_tasks" :disabled="!canManage" label="每轮最多处置任务" type="number" min="1" max="1000" density="compact" variant="outlined" hide-details /></VCol>
          <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model.number="settings.sample_minutes" :disabled="!canManage || settings.schedule_type === 'interval'" label="Cron 有效采样间隔（分钟）" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol>
        </VRow>
        <p class="text-caption text-medium-emphasis mt-2">固定间隔模式跟随扫描间隔；手动连点不会增加有效采样次数。</p>
        <h3 ref="confirmationHeading" tabindex="-1" class="dm-auto-section-title mt-4">规则处置与确认</h3>
        <VAlert v-if="!settings.rules.length" type="info" variant="tonal" density="compact">请先在条件筛选中添加规则。</VAlert>
        <VExpansionPanels multiple>
          <VExpansionPanel v-for="rule in settings.rules" :key="rule.id">
            <VExpansionPanelTitle>{{ rule.name }} <VChip size="x-small" class="ml-2" :color="rule.mode === 'delete' ? 'warning' : 'info'">{{ rule.enabled ? rule.mode === 'delete' ? '正式删种' : '暂停调试' : '停用' }}</VChip></VExpansionPanelTitle>
            <VExpansionPanelText>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field"><VSelect v-model="rule.action" :disabled="!canManage" label="正式删除动作" :items="[{title:'仅删种，保留数据',value:'torrent'},{title:'删除种子及下载数据',value:'data'}]" density="compact" variant="outlined"
                  :error-messages="rule.enabled && rule.action === 'data' && missingSourcePaths ? '请在下方「删除数据范围」填写允许目录' : ''" hide-details="auto" /></VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model.number="rule.consecutive" :disabled="!canManage" label="连续有效采样次数" type="number" min="1" max="20" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
              <p class="text-caption text-medium-emphasis mt-2">上传低速和 Tracker 故障按有效采样次数判定。先保存并检查详情页中的暂停前依据，再确认正式启用。</p>
              <div class="dm-auto-toolbar mt-3">
                <VBtn v-if="rule.mode === 'delete'" :disabled="!canManage || Boolean(busy)" color="info" variant="tonal" size="small" @click="rule.mode = 'debug'">切回暂停调试 · 保存后生效</VBtn>
                <VBtn :disabled="!canManage || !rule.enabled || dirty || Boolean(busy)" color="warning" variant="tonal" size="small" @click="beginConfirm(rule)">{{ rule.mode === 'delete' ? '确认暂停清单' : '确认并正式启用' }}</VBtn>
              </div>
            </VExpansionPanelText>
          </VExpansionPanel>
        </VExpansionPanels>
        <h3 class="dm-auto-section-title mt-4">删除数据范围</h3>
        <VAlert type="warning" variant="tonal" density="compact" class="mb-3">只有选择“删除种子及下载数据”的规则会删除文件。允许目录、路径映射或规则关键条件变化后，需要重新调试确认。</VAlert>
        <VRow class="dm-form-grid">
          <VCol cols="12" md="6" class="dm-form-field"><VTextarea :model-value="settings.source_paths.join('\n')" @update:model-value="setPaths('source_paths', $event)" :disabled="!canManage" label="允许删除的下载目录" :required="needsSourcePaths" :error-messages="missingSourcePaths ? sourcePathMessage : ''" rows="3" auto-grow density="compact" variant="outlined" hide-details="auto" /></VCol>
          <VCol cols="12" md="6" class="dm-form-field"><VTextarea :model-value="settings.exclude_paths.join('\n')" @update:model-value="setPaths('exclude_paths', $event)" :disabled="!canManage" label="保护目录" rows="3" auto-grow density="compact" variant="outlined" hide-details /></VCol>
        </VRow>
        <p class="text-caption text-medium-emphasis mt-2">一行一个 MP 容器内绝对目录；删除数据时必须配置允许目录。</p>
        <h3 class="dm-auto-section-title mt-4">历史保留</h3>
        <VRow class="dm-form-grid dm-form-grid--single-number"><VCol cols="12" md="6" class="dm-form-field"><VTextField v-model.number="settings.history_days" :disabled="!canManage" label="已结束记录保留天数" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol></VRow>
        <p class="text-caption text-medium-emphasis mt-2">待复核记录与活动保护不按日期清除；执行记录只在详情页显示。</p>
      </section>
      <section v-if="section === 'filter'" data-config-section="filter">
      <div class="dm-auto-toolbar mb-2"><strong>自动删种规则</strong><VBtn :disabled="!canManage" size="small" prepend-icon="mdi-plus" @click="addRule">添加规则</VBtn></div>
      <VAlert v-if="!settings.rules.length" type="info" variant="tonal" density="compact">尚未创建规则。新增规则默认停用、暂停调试。</VAlert>
      <VExpansionPanels multiple>
        <VExpansionPanel v-for="(rule, index) in settings.rules" :key="rule.id">
          <VExpansionPanelTitle>{{ rule.name }} <VChip size="x-small" class="ml-2" :color="rule.mode === 'delete' ? 'warning' : 'info'">{{ rule.enabled ? rule.mode === 'delete' ? '正式删种' : '暂停调试' : '停用' }}</VChip></VExpansionPanelTitle>
          <VExpansionPanelText>
            <VRow class="dm-form-grid dm-form-grid--three"><VCol cols="12" md="8" class="dm-form-field dm-form-field--wide"><VTextField v-model="rule.name" :disabled="!canManage" label="规则名称" density="compact" variant="outlined" hide-details /></VCol>
              <VCol cols="12" md="4" class="dm-form-field"><VSwitch v-model="rule.enabled" :disabled="!canManage" label="启用规则" hide-details color="success" inset /></VCol>
              <VCol cols="12" md="8" class="dm-form-field dm-form-field--wide"><VSelect v-model="rule.downloaders" :disabled="!canManage || !downloadersReady" label="作用下载器 · 可选一个或多个" :items="downloaders" multiple chips closable-chips clearable density="compact" variant="outlined" hide-details /></VCol>
              <VCol cols="12" md="4" class="dm-form-field"><VSwitch v-model="rule.ignore_case" :disabled="!canManage" label="忽略大小写" hide-details color="info" inset /></VCol></VRow>
            <div class="dm-auto-section-title mt-4">正则条件 · 排除优先</div><VRow class="dm-form-grid">
              <VCol v-for="[key, label] in regexFields" :key="key" cols="12" md="6" class="dm-form-field"><VTextField v-model="rule.conditions[key]" :disabled="!canManage" :label="label" density="compact" variant="outlined" hide-details /></VCol>
            </VRow>
            <div class="dm-auto-section-title mt-4">数值达标条件</div><VRow class="dm-form-grid dm-form-grid--three">
              <VCol v-for="[key, label] in numberFields" :key="key" cols="12" sm="6" md="4" class="dm-form-field"><VTextField :model-value="rule.conditions[key]" @update:model-value="numberValue(rule, key, $event)" :disabled="!canManage" :label="label" type="number" min="0" step="any" density="compact" variant="outlined" hide-details /></VCol>
            </VRow>
            <p class="text-caption text-medium-emphasis mt-2">留空不限，零为有效阈值。暂停后的零上传速度不作为新的低速证据。</p>
            <div class="dm-auto-toolbar mt-3"><VBtn :disabled="!canManage" size="small" variant="text" @click="duplicate(rule)">复制</VBtn><VBtn :disabled="!canManage || index === 0" size="small" variant="text" @click="[settings.rules[index - 1], settings.rules[index]] = [rule, settings.rules[index - 1]]">上移</VBtn><VBtn :disabled="!canManage" size="small" color="error" variant="text" @click="settings.rules.splice(index, 1)">删除规则</VBtn></div>
          </VExpansionPanelText>
        </VExpansionPanel>
      </VExpansionPanels>
      <p v-if="settings.rules.length" class="text-caption text-medium-emphasis mt-3">删除动作、连续采样次数和正式启用在高级选项中设置；预览只验证当前匹配条件。</p>
      </section>
      <div v-if="section === 'filter' || dirty" class="dm-auto-toolbar my-3">
        <VBtn v-if="section === 'filter'" :disabled="!canManage || Boolean(busy)" :loading="busy === 'preview'" color="info" variant="tonal" @click="preview">仅预览命中</VBtn>
        <span v-if="dirty" class="text-caption">有未保存的修改</span>
      </div>
      <section v-if="section === 'filter'">
      <VAlert v-if="previewResult" type="info" variant="tonal" class="mb-3">本次只读预览：扫描 {{ previewResult.summary?.scanned || 0 }}，条件匹配 {{ previewResult.matches_total || 0 }} 个任务。{{ previewResult.truncated ? '明细仅展示前 500 个候选。' : '' }}预览不暂停、不删除，也不增加连续计数。</VAlert>
      <VAlert v-for="item in previewResult?.errors || []" :key="item" type="warning" variant="tonal" class="mb-2">{{ item }}</VAlert>
      <div v-for="item in (previewResult?.matches || []).filter(row => row.rules.some(rule => rule.status !== 'no_match'))" :key="item.snapshot.downloader + item.snapshot.hash" class="dm-auto-preview mb-2">
        <strong>{{ item.snapshot.downloader }} · {{ item.snapshot.name }}</strong><div class="text-caption">{{ item.snapshot.save_path }} · 添加 {{ timeText(item.snapshot.added_at) }}</div>
        <div v-for="rule in item.rules.filter(rule => rule.status !== 'no_match')" :key="rule.rule_id" class="text-caption mt-1">{{ rule.rule_name }} · {{ rule.status === 'match' ? '条件匹配' : '无法判断' }} · 有效采样 {{ item.samples[rule.rule_id] || 0 }}/{{ item.required_samples[rule.rule_id] || 1 }}：{{ rule.reasons.join('；') }}</div>
        <div v-if="item.protected" class="text-caption text-warning">任务已有保护，正式规则不会越过它。</div><div v-if="item.limit_interference?.length" class="text-caption text-warning">受本插件上传限速影响，低速规则跳过自动处置。</div>
      </div>
      </section>
    </template>
    <section v-if="mode === 'history'" data-execution-history class="dm-history-surface">
    <div class="dm-history-toolbar mt-4"><h3 class="dm-history-title">执行记录<span class="dm-history-count">共 {{ total }} 条</span></h3>
    <div class="dm-history-tools">
      <VSelect v-model="filterState" :items="stateItems" density="compact" variant="outlined" hide-details label="结果" class="dm-auto-filter" />
      <VSelect v-model="filterRule" :items="[{title:'全部规则',value:''}, ...(settings?.rules || []).map(rule => ({title:rule.name,value:rule.id}))]" density="compact" variant="outlined" hide-details label="规则" class="dm-auto-filter" />
      <VSelect v-model="filterDownloader" :items="[{title:'全部下载器',value:''}, ...downloaders]" density="compact" variant="outlined" hide-details label="下载器" class="dm-auto-filter" />
    </div>
    </div>
    <VProgressLinear v-if="historyLoading" color="primary" indeterminate />
    <div v-if="!records.length" class="dm-history-empty">{{ historyLoading ? '正在读取执行记录…' : error ? '执行记录读取失败，请刷新重试' : '暂无执行记录' }}</div>
    <div v-else>
      <HistoryRow v-for="record in records" :key="props.pluginId + ':' + record.id"
        :time="timeText(record.created_at)" :name="record.name || record.torrent_hash"
        :status="stateText(record.state)" :color="recordColor(record.state)">
        <div>规则 · {{ record.rule_name || '—' }}</div>
        <div>下载器 · {{ record.downloader || '—' }}</div>
        <div v-if="record.error" class="text-error">{{ record.error }}</div>
        <div class="dm-history-actions">
          <VBtn size="x-small" variant="text" @click="detail = record">依据</VBtn>
          <template v-if="protectedStates.has(record.state)">
            <VBtn :disabled="!canManage || Boolean(busy)" size="x-small" color="warning" variant="tonal" @click="release(record, false)">解除保护</VBtn>
            <VBtn :disabled="!canManage || Boolean(busy)" size="x-small" color="primary" variant="tonal" @click="release(record, true)">恢复原状态</VBtn>
          </template>
        </div>
      </HistoryRow>
    </div>
    <div v-if="pages > 1" class="dm-history-pagination"><VPagination v-model="page" :length="pages" :total-visible="5" density="compact" /><span class="dm-history-count">共 {{ total }} 条</span></div>
    </section>
    <VDialog :model-value="Boolean(confirmRule)" @update:model-value="value => { if (!value) confirmRule = null }" max-width="720" scrollable><VCard><VCardTitle>确认正式启用 · {{ confirmRule?.name }}</VCardTitle><VCardText>
      <VAlert v-if="error" type="error" variant="tonal" class="mb-3">{{ error }}</VAlert>
      <p>确认已保存规则后，未来命中任务会自动执行 {{ confirmRule?.action === 'data' ? '删除种子及下载数据' : '仅删种、保留数据' }}。此按钮只保存确认，实际处置等下一个周期或手动运行。</p>
      <p class="text-caption">已有暂停任务可单独勾选。未选任务继续受保护；勾选表示接受暂停前的指标，不把当前零上传速度作为低速依据。</p>
      <div v-for="record in confirmJobs" :key="record.id"><VCheckbox v-model="selectedJobs" :value="record.id" :label="`${record.name} · ${timeText(record.created_at)}`" hide-details /><div class="text-caption ml-8 mb-2">{{ record.evidence.join('；') }}</div></div>
      <VPagination v-if="confirmTotal > 100" :model-value="confirmPage" :length="Math.ceil(confirmTotal / 100)" :disabled="Boolean(busy)" density="compact" @update:model-value="loadConfirmPage" />
      <VCheckbox v-if="selectedJobs.length" v-model="acceptHistory" label="我已核对所选任务的暂停前采样证据，并接受这批历史命中依据" />
      <VAlert v-if="!confirmJobs.length" type="info" variant="tonal" density="compact">本页没有可选暂停任务；只启用后续规则。零命中不等于已有实际命中样本。</VAlert>
    </VCardText><VCardActions><VSpacer /><VBtn @click="confirmRule = null">取消</VBtn><VBtn :disabled="!canManage || Boolean(busy) || (selectedJobs.length > 0 && !acceptHistory)" color="warning" @click="activate">确认正式启用</VBtn></VCardActions></VCard></VDialog>
    <VDialog :model-value="Boolean(detail)" @update:model-value="value => { if (!value) detail = null }" max-width="720" scrollable><VCard><VCardTitle>命中依据 · {{ detail?.name }}</VCardTitle><VCardText><div v-for="reason in detail?.evidence || []" :key="reason" class="mb-1">{{ reason }}</div><div class="text-caption mt-3">采样 {{ timeText(detail?.created_at) }} · {{ detail?.downloader }} · {{ detail?.torrent_hash }}</div><div class="text-caption">保存路径 {{ detail?.snapshot?.save_path }}</div><VAlert v-if="detail?.error" type="warning" variant="tonal" class="mt-3">{{ detail.error }}</VAlert></VCardText><VCardActions><VSpacer /><VBtn @click="detail = null">关闭</VBtn></VCardActions></VCard></VDialog>
  </section>
</template>

<style scoped>
.dm-auto-delete { min-width: 0; background: transparent; }
.dm-auto-section-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: rgb(var(--v-theme-primary)); }
.dm-auto-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.dm-auto-preview { padding: 12px; border: 1px solid rgba(var(--v-theme-on-surface), .12); border-radius: 8px; overflow-wrap: anywhere; }
.dm-auto-filter { max-width: 240px; min-width: 180px; }
.dm-auto-delete :deep(.v-expansion-panel) { background: transparent; }
</style>
