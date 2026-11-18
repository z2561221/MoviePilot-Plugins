<script setup>
import './history-layout.css'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getPluginApi, postPluginJsonApi, isApiRequestCancellation } from './api'
import HistoryRow from './HistoryRow.vue'
import SyncDeleteDetails from './SyncDeleteDetails.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  form: { type: Object, default: null },
  mode: { type: String, default: 'history' },
  section: { type: String, default: 'basic' },
  canManage: { type: Boolean, default: false },
  initialPendingOnly: { type: Boolean, default: false },
})
const servers = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const enabled = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const retryId = ref('')
const pendingOnly = ref(Boolean(props.initialPendingOnly))
const actionDialog = ref(false)
const actionKind = ref('')
const actionJob = ref(null)
const actionError = ref('')
const expandedMappings = ref({})
const mappingRows = value => String(value || '').split('\n').filter(line => line.trim()).map(line => line.split('#'))
const cloudMappings = computed(() => mappingRows(props.form?.sync_delete_cloud_paths))
const localMappings = computed(() => mappingRows(props.form?.sync_delete_local_paths))
const mappingGroups = computed(() => [
  { field: 'sync_delete_local_paths', title: '本地媒体库', icon: 'mdi-folder-outline', columns: 2, rows: localMappings.value,
    inputs: [{ column: 0, label: 'Emby 媒体目录' }, { column: 1, label: 'MP 本地媒体目录' }] },
  { field: 'sync_delete_cloud_paths', title: 'STRM 媒体库', icon: 'mdi-cloud-outline', columns: 4, rows: cloudMappings.value,
    inputs: [{ column: 0, label: 'Emby STRM 目录' }, { column: 1, label: 'MP STRM 目录' },
      { column: 3, label: '本地整理目录（可选）' }, { column: 2, label: '网盘目录' }] },
])
const sourceRoots = computed(() => String(props.form?.sync_delete_source_paths || '').split('\n').map(line => line.trim()).filter(Boolean))
const mappingTitle = row => String(row[0] || '').trim().split(/[\\/]/).filter(Boolean).at(-1) || '新映射'
function toggleMapping(field, index) {
  expandedMappings.value = { ...expandedMappings.value, [field]: expandedMappings.value[field] === index ? -1 : index }
}
function editMapping(field, index, column, value) {
  const rows = mappingRows(props.form[field])
  rows[index] ||= Array(field === 'sync_delete_cloud_paths' ? 4 : 2).fill('')
  rows[index][column] = String(value || '').replace(/[\r\n]/g, '')
  props.form[field] = rows.map(row => row.join('#')).join('\n')
}
function addMapping(field, columns) {
  const rows = mappingRows(props.form[field])
  rows.push(Array(columns).fill(''))
  props.form[field] = rows.map(row => row.join('#')).join('\n')
  expandedMappings.value = { ...expandedMappings.value, [field]: rows.length - 1 }
}
function removeMapping(field, index) {
  const rows = mappingRows(props.form[field])
  props.form[field] = rows.filter((_, i) => i !== index).map(row => row.join('#')).join('\n')
  const opened = expandedMappings.value[field] ?? -1
  expandedMappings.value = { ...expandedMappings.value, [field]: opened === index ? -1 : opened > index ? opened - 1 : opened }
}
let revision = 0
let loadRevision = 0
let retryRevision = 0
let disposed = false
const pages = computed(() => Math.max(1, Math.ceil(total.value / 15)))
const labels = { queued: '等待执行', running: '处理中', failed: '待处理', completed: '完成', skipped: '无需处理', dismissed: '已忽略', pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' }
const label = state => labels[state] || state
const color = state => ['completed', 'skipped'].includes(state) ? 'success' : state === 'failed' ? 'warning' : state === 'dismissed' ? 'default' : 'info'
const dateText = stamp => stamp ? new Date(stamp * 1000).toLocaleString() : '—'
const current = (ticket, id) => !disposed && revision === ticket && props.pluginId === id

async function load() {
  const ticket = revision
  const request = ++loadRevision
  const id = props.pluginId
  const owns = () => current(ticket, id) && request === loadRevision
  loading.value = true
  error.value = ''
  try {
    if (props.mode === 'config') {
      const result = await getPluginApi(props.api, id, 'sync_delete/options', { feedback: 'silent' })
      if (owns()) servers.value = result?.servers || []
    } else {
      const result = await getPluginApi(props.api, id, `sync_delete/history?page=${page.value}&page_size=15&pending_only=${pendingOnly.value}`, { feedback: 'silent' })
      if (owns()) {
        rows.value = result?.items || []
        total.value = result?.total || 0
        enabled.value = Boolean(result?.enabled)
      }
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '读取失败，请重试'
  } finally {
    if (owns()) loading.value = false
  }
}

async function retry(job) {
  if (!props.canManage || !enabled.value || retryId.value || job.review?.retry_allowed === false) return false
  const ticket = revision
  const request = ++retryRevision
  const id = props.pluginId
  const owns = () => current(ticket, id) && request === retryRevision
  retryId.value = job.id
  error.value = ''
  notice.value = ''
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/retry', { job_id: job.id }, { feedback: 'silent' })
    if (owns() && result?.accepted) {
      notice.value = '已加入执行队列，请刷新查看实际结果。'
      await load()
      return owns()
    }
    if (owns()) error.value = '重试未受理，请刷新记录后再试。'
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '重试未受理'
  } finally {
    if (owns()) retryId.value = ''
  }
  return false
}

function filterHistory() {
  page.value = 1
  void load()
}

function requestAction(kind, job) {
  if (!props.canManage || retryId.value) return
  if (kind !== 'retry' || !enabled.value || job.review?.retry_allowed === false) return
  actionKind.value = kind
  actionJob.value = job
  actionError.value = ''
  actionDialog.value = true
}

async function confirmAction() {
  const job = actionJob.value
  if (!props.canManage || !job || retryId.value) return
  const ticket = revision, id = props.pluginId
  const accepted = await retry(job)
  if (current(ticket, id) && accepted) actionDialog.value = false
  else if (current(ticket, id)) actionError.value = error.value || '重试未受理'
}

async function ignore(job) {
  if (!props.canManage || retryId.value || !job.review?.dismiss_allowed) return
  const ticket = revision, id = props.pluginId
  const request = ++retryRevision
  const owns = () => current(ticket, id) && request === retryRevision
  retryId.value = job.id
  actionKind.value = 'ignore'
  error.value = ''
  notice.value = ''
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/dismiss', {
      job_id: job.id, expected_revision: job.review.revision,
    }, { feedback: 'silent' })
    if (owns()) {
      if (result?.state !== 'dismissed') throw new Error('忽略未确认，请刷新记录')
      notice.value = '已忽略，历史记录保留。'
      await load()
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '忽略失败，请刷新后重试'
  } finally { if (owns()) retryId.value = '' }
}

watch(() => [props.pluginId, props.mode, props.api], () => {
  revision++
  page.value = 1
  rows.value = []
  servers.value = []
  total.value = 0
  enabled.value = false
  expandedMappings.value = {}
  notice.value = ''
  retryId.value = ''
  pendingOnly.value = Boolean(props.initialPendingOnly)
  actionDialog.value = false
  actionJob.value = null
  actionError.value = ''
  load()
}, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { disposed = true; revision++ })
defineExpose({ refresh: load, busy: computed(() => Boolean(retryId.value)) })
</script>

<template>
  <div class="dm-sync" :class="{ 'dm-history-surface': mode === 'history' }">
    <VAlert v-if="error" type="warning" variant="tonal" density="compact" class="mb-3">{{ error }}</VAlert>
    <VAlert v-if="notice" type="info" variant="tonal" density="compact" class="mb-3">{{ notice }}</VAlert>
    <template v-if="mode === 'config' && form">
      <section v-if="section === 'basic'" data-config-section="basic">
        <div class="dm-sync-heading">
          <div><strong>同步删除</strong><div class="text-caption text-medium-emphasis">在 Emby 删除本地媒体或 STRM 后，清理关联文件、种子和整理记录。</div></div>
          <VSwitch v-model="form.sync_delete_enabled" color="success" inset hide-details label="启用" />
        </div>
        <VSelect v-model="form.sync_delete_servers" :items="servers" multiple chips closable-chips label="Emby 服务器" density="compact" variant="outlined" hide-details class="my-4" />
        <VSwitch v-model="form.sync_delete_notify" color="info" inset hide-details label="发送结果通知" />
        <VAlert type="info" variant="tonal" density="compact" class="mt-3">使用现有神医深度删除通知。合集还有其它集数时，种子暂停保留。</VAlert>
      </section>
      <section v-if="section === 'filter'" data-config-section="filter">
        <div class="text-caption text-medium-emphasis">路径映射决定哪些媒体库目录能对应到本机或网盘文件；这里只保存对应关系，不直接执行删除。</div>
        <section v-for="group in mappingGroups" :key="group.field" class="dm-sync-group">
          <div class="dm-sync-group-head">
            <div class="dm-sync-group-title"><VIcon :icon="group.icon" size="19" /><h3>{{ group.title }}</h3><span class="dm-sync-count">{{ group.rows.length }}</span></div>
            <VBtn size="small" variant="text" color="primary" prepend-icon="mdi-plus" :aria-label="`添加${group.title}映射`" @click="addMapping(group.field, group.columns)">添加映射</VBtn>
          </div>
          <div v-if="!group.rows.length" class="dm-sync-empty">尚未配置{{ group.title }}映射</div>
          <div v-else class="dm-sync-mapping-list">
            <details v-for="(row, index) in group.rows" :key="index" class="dm-sync-mapping" :open="expandedMappings[group.field] === index">
              <summary class="dm-sync-mapping-summary" @click.prevent="toggleMapping(group.field, index)">
                <span class="dm-sync-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="dm-sync-mapping-label"><strong :title="mappingTitle(row)">{{ mappingTitle(row) }}</strong><span :title="row[0]">{{ row[0] || '填写目录，建立路径对应关系' }}</span></span>
                <VIcon class="dm-sync-chevron" icon="mdi-chevron-down" size="20" />
              </summary>
              <div v-if="expandedMappings[group.field] === index" class="dm-sync-mapping-editor">
                <VTextarea v-for="input in group.inputs" :key="input.column" :model-value="row[input.column] || ''" :label="input.label" class="dm-sync-directory" rows="2" auto-grow density="compact" variant="outlined" hide-details spellcheck="false" @update:model-value="editMapping(group.field, index, input.column, $event)" />
                <div class="dm-sync-editor-footer"><VBtn size="small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="removeMapping(group.field, index)">移除此映射</VBtn></div>
              </div>
            </details>
          </div>
        </section>
      </section>
      <section v-if="section === 'advanced'" data-config-section="advanced">
        <div class="dm-sync-heading mb-3"><strong>高级选项 · 删除范围与动作</strong></div>
        <div class="dm-sync-switches">
          <VSwitch v-model="form.sync_delete_cloud" color="error" inset hide-details label="删除网盘文件" />
          <VSwitch v-model="form.sync_delete_source" color="error" inset hide-details label="删除下载源文件" />
          <VSwitch v-model="form.sync_delete_torrents" color="error" inset hide-details label="移除源种、转种和辅种" />
          <VSwitch v-model="form.sync_delete_records" color="warning" inset hide-details label="清理整理记录" />
        </div>
        <div class="text-caption text-medium-emphasis mt-2">删除下载源文件时，同时清理明确映射的本地整理副本。</div>
        <details open class="my-4">
          <summary>允许删除范围<span v-if="sourceRoots.length">（{{ sourceRoots.length }} 个源目录）</span><span v-else-if="form.sync_delete_source || form.sync_delete_torrents" class="text-warning">（请填写源目录）</span></summary>
          <div class="text-caption text-medium-emphasis mt-3">源文件和种子仅在允许的目录内处理，保护目录中的文件保留。</div>
          <VTextarea v-model="form.sync_delete_source_paths" label="允许删除的下载源目录" rows="3" auto-grow density="compact" variant="outlined" hide-details class="my-4" placeholder="填写 MP 容器内的真实下载目录，一行一个" />
          <VTextarea v-model="form.sync_delete_source_aliases" label="历史源路径映射（可选）" rows="3" auto-grow density="compact" variant="outlined" hide-details class="my-4" placeholder="历史目录#当前 MP 容器目录，一行一条" />
          <div class="text-caption text-medium-emphasis">目录迁移后，用此映射识别旧下载记录。当前目录须在允许范围内；仍被新下载引用的文件保留。</div>
          <VTextarea v-model="form.sync_delete_exclude_paths" label="保护目录（可选）" rows="2" density="compact" variant="outlined" hide-details class="my-4" placeholder="一行一个路径，匹配到的文件保留" />
        </details>
      </section>
    </template>
    <template v-else>
      <div class="dm-history-toolbar">
        <div><h3 class="dm-history-title">同步删除历史<span class="dm-history-count">共 {{ total }} 条</span></h3><div class="dm-history-entry-meta">{{ enabled ? '同步删除已启用' : '同步删除未启用' }}</div></div>
        <div class="dm-sync-history-tools dm-history-tools">
          <VSwitch v-model="pendingOnly" label="仅待处理" density="compact" hide-details inset @update:model-value="filterHistory" />
          <VBtn variant="text" icon="mdi-refresh" :loading="loading" aria-label="刷新同步删除历史" @click="load" />
        </div>
      </div>
      <VProgressLinear v-if="loading" indeterminate color="primary" class="mb-3" />
      <div v-if="!rows.length && !loading" class="dm-history-empty">{{ pendingOnly ? '暂无待处理记录，可关闭筛选查看历史。' : '暂无同步删除记录' }}</div>
      <HistoryRow v-for="job in rows" :key="props.pluginId + ':' + job.id" :data-sync-record="job.id"
        :time="dateText(job.updated_at)" :name="job.event?.name || job.event?.paths?.[0] || '媒体删除'"
        :status="label(job.state)" :color="color(job.state)">
        <div v-if="job.error" :class="job.state === 'dismissed' ? 'text-medium-emphasis' : 'text-warning'">{{ job.state === 'dismissed' ? '原失败原因：' : '' }}{{ job.error }}</div>
        <div v-if="job.state === 'skipped'" class="text-medium-emphasis">{{ job.plan?.skip_reason }}</div>
        <SyncDeleteDetails :data-sync-detail="job.id" :job="job" />
        <div v-if="job.state === 'failed'" class="mt-3">
          <div v-if="job.review?.retry_reason" class="text-caption text-medium-emphasis">无法重试：{{ job.review.retry_reason }}</div>
          <div v-if="job.review?.dismiss_reason" class="text-caption text-medium-emphasis">{{ job.review.dismiss_reason }}</div>
          <div v-if="job.review?.dismiss_allowed" class="text-caption text-medium-emphasis">忽略后不再提醒，历史保留。</div>
          <div class="dm-sync-actions dm-history-actions">
            <VBtn color="warning" variant="tonal" size="x-small" :loading="retryId === job.id && actionKind === 'retry'" :disabled="!props.canManage || !enabled || Boolean(retryId) || job.review?.retry_allowed === false" @click="requestAction('retry', job)">核验后重试</VBtn>
            <VBtn v-if="job.review?.dismiss_allowed" variant="text" size="x-small" :loading="retryId === job.id && actionKind === 'ignore'" :disabled="!props.canManage || Boolean(retryId)" @click="ignore(job)">忽略</VBtn>
          </div>
        </div>
      </HistoryRow>
      <div v-if="pages > 1" class="dm-history-pagination"><VPagination v-model="page" :length="pages" :total-visible="5" density="compact" @update:model-value="load" /><span class="dm-history-count">共 {{ total }} 条</span></div>
      <VDialog v-model="actionDialog" max-width="560" :persistent="Boolean(retryId)">
        <VCard>
          <VCardTitle>确认重新执行</VCardTitle>
          <VCardText>
            <div class="font-weight-medium mb-3">{{ actionJob?.event?.name || '媒体删除' }}</div>
            <div>将按这条记录原有范围重新核验，并可能继续删除文件、移除种子或清理记录。请先确认关联明细及失败原因已经处理。</div>
            <VAlert v-if="actionError" type="warning" variant="tonal" class="mt-3">{{ actionError }}</VAlert>
          </VCardText>
          <VCardActions><VSpacer /><VBtn :disabled="Boolean(retryId)" @click="actionDialog = false">取消</VBtn>
            <VBtn color="error" :loading="Boolean(retryId)" :disabled="!props.canManage || Boolean(retryId)" @click="confirmAction">确认重试</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>
    </template>
  </div>
</template>

<style scoped>
.dm-sync { background: transparent; min-width: 0; }
.dm-sync-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dm-sync-history-tools, .dm-sync-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.dm-sync-switches { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px 24px; align-items: start; }
.dm-sync-path { overflow-wrap: anywhere; font-size: 12px; }
.dm-sync summary { cursor: pointer; }
.dm-sync-group { margin-top: 22px; min-width: 0; }
.dm-sync-group-head, .dm-sync-group-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.dm-sync-group-head { justify-content: space-between; margin-bottom: 10px; }
.dm-sync-group-title > .v-icon { color: rgba(var(--v-theme-on-surface), .6); }
.dm-sync-group-title h3 { margin: 0; font-size: 14px; font-weight: 600; }
.dm-sync-count { min-width: 22px; padding: 1px 6px; border-radius: 6px; background: rgba(var(--v-theme-on-surface), .06); color: rgba(var(--v-theme-on-surface), .6); font-size: 11px; text-align: center; }
.dm-sync-empty { padding: 14px; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 9px; text-align: center; color: rgba(var(--v-theme-on-surface), .48); font-size: 12px; }
.dm-sync-mapping-list { display: grid; gap: 8px; }
.dm-sync-mapping { min-width: 0; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; }
.dm-sync-mapping[open] { border-color: rgba(var(--v-theme-primary), .35); }
.dm-sync-mapping-summary { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 10px; list-style: none; transition: background .15s; }
.dm-sync-mapping-summary:hover { background: rgba(var(--v-theme-on-surface), .025); }
.dm-sync-mapping-summary:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; }
.dm-sync-mapping-summary::-webkit-details-marker { display: none; }
.dm-sync-index { flex: 0 0 28px; width: 28px; height: 28px; display: grid; place-items: center; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .07); border-radius: 7px; font-size: 11px; font-variant-numeric: tabular-nums; }
.dm-sync-mapping-label { display: grid; min-width: 0; flex: 1; gap: 3px; }
.dm-sync-mapping-label strong { font-size: 13px; font-weight: 500; }
.dm-sync-mapping-label > span { font-size: 11px; color: rgba(var(--v-theme-on-surface), .5); }
.dm-sync-mapping-label > * { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dm-sync-chevron { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .45); transition: transform .15s; }
.dm-sync-mapping[open] > summary .dm-sync-chevron { transform: rotate(180deg); }
.dm-sync-mapping-editor { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; padding: 18px 16px 10px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dm-sync-directory { min-width: 0; }
.dm-sync-directory :deep(textarea) { overflow-wrap: anywhere; font-size: 13px; line-height: 1.6; }
.dm-sync-editor-footer { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
@media (max-width: 480px) { .dm-sync-mapping-summary { padding: 11px; gap: 9px; } .dm-sync-mapping-editor { padding-inline: 12px; } }
@media (max-width: 760px) { .dm-sync-switches { grid-template-columns: 1fr; gap: 16px; } }
</style>
