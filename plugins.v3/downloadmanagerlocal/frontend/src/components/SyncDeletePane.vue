<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getPluginApi, postPluginJsonApi, isApiRequestCancellation } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  form: { type: Object, default: null },
  mode: { type: String, default: 'history' },
})
const servers = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const enabled = ref(false)
const loading = ref(false)
const previewLoading = ref(false)
const error = ref('')
const notice = ref('')
const previewPath = ref('')
const previewPlan = ref(null)
const retryId = ref('')
const mappingMode = ref('text')
const cloudMappings = computed(() => String(props.form?.sync_delete_cloud_paths || '').split('\n').filter(Boolean).map(line => line.split('#')))
const localMappings = computed(() => String(props.form?.sync_delete_local_paths || '').split('\n').filter(Boolean).map(line => line.split('#')))
function editMapping(field, index, column, value) {
  const rows = String(props.form[field] || '').split('\n').filter(Boolean).map(line => line.split('#'))
  rows[index][column] = String(value || '')
  props.form[field] = rows.map(row => row.join('#')).join('\n')
}
function addMapping(field, columns) {
  const rows = String(props.form[field] || '').split('\n').filter(Boolean)
  rows.push(Array(columns).fill('').join('#'))
  props.form[field] = rows.join('\n')
}
function removeMapping(field, index) {
  props.form[field] = String(props.form[field] || '').split('\n').filter(Boolean).filter((_, i) => i !== index).join('\n')
}
let revision = 0
let loadRevision = 0
let previewRevision = 0
let retryRevision = 0
let disposed = false
const pages = computed(() => Math.max(1, Math.ceil(total.value / 15)))
const labels = { queued: '等待执行', running: '处理中', failed: '待处理', completed: '完成', pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' }
const label = state => labels[state] || state
const color = state => state === 'completed' ? 'success' : state === 'failed' ? 'warning' : 'info'
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
      const result = await getPluginApi(props.api, id, `sync_delete/history?page=${page.value}&page_size=15`, { feedback: 'silent' })
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

async function preview() {
  const ticket = revision
  const request = ++previewRevision
  const id = props.pluginId
  const owns = () => current(ticket, id) && request === previewRevision
  previewLoading.value = true
  error.value = ''
  previewPlan.value = null
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/preview', {
      path: previewPath.value.trim(), server: props.form?.sync_delete_servers?.[0] || '',
    }, { feedback: 'silent' })
    if (owns()) previewPlan.value = result?.plan || null
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '无法匹配该路径'
  } finally {
    if (owns()) previewLoading.value = false
  }
}

async function retry(job) {
  if (retryId.value) return
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
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '重试未受理'
  } finally {
    if (owns()) retryId.value = ''
  }
}

watch(() => [props.pluginId, props.mode, props.api], () => {
  revision++
  page.value = 1
  rows.value = []
  servers.value = []
  total.value = 0
  enabled.value = false
  previewPlan.value = null
  previewLoading.value = false
  notice.value = ''
  retryId.value = ''
  load()
}, { immediate: true, flush: 'sync' })
watch(() => [props.form, previewPath.value], () => {
  previewRevision++
  previewLoading.value = false
  previewPlan.value = null
}, { deep: true, flush: 'sync' })
onBeforeUnmount(() => { disposed = true; revision++ })
defineExpose({ refresh: load })
</script>

<template>
  <div class="dm-sync">
    <VAlert v-if="error" type="warning" variant="tonal" density="compact" class="mb-3">{{ error }}</VAlert>
    <VAlert v-if="notice" type="info" variant="tonal" density="compact" class="mb-3">{{ notice }}</VAlert>
    <template v-if="mode === 'config' && form">
      <div class="dm-sync-heading">
        <div><strong>同步删除</strong><div class="text-caption text-medium-emphasis">在 Emby 删除媒体后，联动网盘、源文件、整理记录和关联种子。</div></div>
        <VSwitch v-model="form.sync_delete_enabled" color="success" inset hide-details label="启用" />
      </div>
      <VSelect v-model="form.sync_delete_servers" :items="servers" multiple chips label="Emby 服务器" density="compact" variant="outlined" hide-details class="my-4" />
      <VAlert type="info" variant="tonal" density="compact" class="mb-4">使用现有神医深度删除通知。合集仅删除部分文件时，关联种子保持暂停，其余集数保留。相同目录请只启用一个同步删除功能。</VAlert>
      <div class="dm-sync-switches">
        <VSwitch v-model="form.sync_delete_cloud" color="success" inset hide-details label="删除网盘文件" />
        <VSwitch v-model="form.sync_delete_source" color="success" inset hide-details label="删除下载源文件" />
        <VSwitch v-model="form.sync_delete_torrents" color="success" inset hide-details label="移除源种、转种和辅种" />
        <VSwitch v-model="form.sync_delete_records" color="success" inset hide-details label="清理整理记录" />
        <VSwitch v-model="form.sync_delete_notify" color="success" inset hide-details label="发送结果通知" />
      </div>
      <VBtnToggle v-model="mappingMode" mandatory density="compact" color="primary" class="my-4"><VBtn value="text" size="small">批量填写</VBtn><VBtn value="fields" size="small">分列填写</VBtn></VBtnToggle>
      <VTextarea v-if="mappingMode === 'text'" v-model="form.sync_delete_local_paths" label="本地媒体库路径映射" rows="2" auto-grow density="compact" variant="outlined" hide-details class="my-4" placeholder="Emby路径#MP媒体库路径（一行一条）" />
      <div v-else class="my-4">
        <strong>本地媒体库路径映射</strong>
        <div v-for="(row, index) in localMappings" :key="index" class="dm-sync-mapping mt-3">
          <VTextField :model-value="row[0]" label="Emby 路径" density="compact" variant="outlined" hide-details @update:model-value="editMapping('sync_delete_local_paths', index, 0, $event)" />
          <VTextField :model-value="row[1]" label="MP 媒体库路径" density="compact" variant="outlined" hide-details @update:model-value="editMapping('sync_delete_local_paths', index, 1, $event)" />
          <VBtn icon="mdi-close" size="small" variant="text" aria-label="移除此映射" @click="removeMapping('sync_delete_local_paths', index)" />
        </div>
        <VBtn size="small" variant="text" prepend-icon="mdi-plus" class="mt-2" @click="addMapping('sync_delete_local_paths', 2)">添加本地映射</VBtn>
      </div>
      <VSelect v-model="form.sync_delete_storage" :items="['115网盘Plus']" label="网盘存储" density="compact" variant="outlined" hide-details />
      <VTextarea v-if="mappingMode === 'text'" v-model="form.sync_delete_cloud_paths" label="网盘媒体库路径映射" rows="3" auto-grow density="compact" variant="outlined" hide-details class="my-4" placeholder="Emby路径#MP本地STRM路径#网盘目录（一行一条）" />
      <div v-else class="my-4">
        <strong>网盘媒体库路径映射</strong>
        <div v-for="(row, index) in cloudMappings" :key="index" class="dm-sync-mapping dm-sync-mapping-cloud mt-3">
          <VTextField :model-value="row[0]" label="Emby 路径" density="compact" variant="outlined" hide-details @update:model-value="editMapping('sync_delete_cloud_paths', index, 0, $event)" />
          <VTextField :model-value="row[1]" label="MP STRM 路径" density="compact" variant="outlined" hide-details @update:model-value="editMapping('sync_delete_cloud_paths', index, 1, $event)" />
          <VTextField :model-value="row[2]" label="网盘目录" density="compact" variant="outlined" hide-details @update:model-value="editMapping('sync_delete_cloud_paths', index, 2, $event)" />
          <VBtn icon="mdi-close" size="small" variant="text" aria-label="移除此映射" @click="removeMapping('sync_delete_cloud_paths', index)" />
        </div>
        <VBtn size="small" variant="text" prepend-icon="mdi-plus" class="mt-2" @click="addMapping('sync_delete_cloud_paths', 3)">添加网盘映射</VBtn>
      </div>
      <VTextarea v-model="form.sync_delete_source_paths" label="允许删除的下载源目录" rows="3" auto-grow density="compact" variant="outlined" hide-details class="my-4" placeholder="填写 MP 容器内的真实下载目录，一行一个" />
      <VTextarea v-model="form.sync_delete_exclude_paths" label="保护目录（可选）" rows="2" density="compact" variant="outlined" hide-details class="my-4" placeholder="一行一个路径，匹配到的文件保留" />
      <VSwitch v-model="form.sync_delete_force_cloud" color="warning" inset hide-details label="没有整理记录时，也按映射删除网盘文件" />
      <div class="text-caption text-medium-emphasis mb-3">仍需唯一确认网盘实体；不会凭片名猜测下载器任务。</div>
      <VSwitch v-model="form.sync_delete_library_deleted" color="warning" inset hide-details label="同时处理普通 Emby 删除通知" />
      <VDivider class="my-4" />
      <strong>匹配预览</strong>
      <div class="text-caption text-medium-emphasis mb-3">先保存配置，再填写 Emby 中某个媒体文件的完整路径。预览只读取关联，不执行清理。</div>
      <VTextField v-model="previewPath" label="Emby 媒体路径" density="compact" variant="outlined" hide-details />
      <VBtn class="mt-3" color="primary" variant="tonal" prepend-icon="mdi-eye-outline" :loading="previewLoading" :disabled="!previewPath.trim()" @click="preview">预览关联</VBtn>
      <div v-if="previewPlan" class="dm-sync-preview mt-4">
        <div class="mb-2">网盘文件 {{ previewPlan.cloud_files.length }} · 源文件 {{ previewPlan.source_files.length }} · 关联种子 {{ previewPlan.tasks.length }} · 整理记录 {{ previewPlan.records.length }}</div>
        <div v-for="file in [...previewPlan.cloud_files, ...previewPlan.source_files]" :key="`${file.storage}:${file.path}`" class="dm-sync-path">{{ file.storage }} · {{ file.path }}</div>
        <div v-for="task in previewPlan.tasks" :key="`${task.downloader}:${task.id}`" class="dm-sync-path">{{ task.downloader }} · {{ task.id }} · {{ task.action === 'remove' ? '移除任务' : `暂停，保留 ${task.remaining} 个媒体文件` }}</div>
      </div>
    </template>
    <template v-else>
      <div class="dm-sync-heading mb-3">
        <div><strong>同步删除历史</strong><div class="text-caption text-medium-emphasis">{{ enabled ? '同步删除已启用' : '同步删除未启用' }} · 共 {{ total }} 条</div></div>
        <VBtn variant="text" icon="mdi-refresh" :loading="loading" aria-label="刷新同步删除历史" @click="load" />
      </div>
      <VProgressLinear v-if="loading" indeterminate color="primary" class="mb-3" />
      <div v-if="!rows.length && !loading" class="text-medium-emphasis pa-6 text-center">暂无同步删除记录</div>
      <VCard v-for="job in rows" :key="job.id" variant="outlined" class="dm-sync-job mb-3">
        <VCardText>
          <div class="dm-sync-heading">
            <strong>{{ job.event?.name || job.event?.paths?.[0] || '媒体删除' }}</strong>
            <VChip :color="color(job.state)" size="small" variant="tonal">{{ label(job.state) }}</VChip>
          </div>
          <div class="text-caption text-medium-emphasis mt-1">{{ dateText(job.updated_at) }}</div>
          <div v-if="job.error" class="text-warning mt-2">{{ job.error }}</div>
          <details class="mt-3">
            <summary>查看关联明细</summary>
            <div v-for="file in [...(job.plan?.cloud_files || []), ...(job.plan?.source_files || [])]" :key="`${file.storage}:${file.path}`" class="dm-sync-path mt-2">{{ label(file.status) }} · {{ file.storage }} · {{ file.path }}</div>
            <div v-for="task in job.plan?.tasks || []" :key="`${task.downloader}:${task.id}`" class="dm-sync-path mt-2">{{ label(task.status) }} · {{ task.downloader }} · {{ task.id }}</div>
            <div class="text-caption mt-2">整理记录已处理 {{ job.records_done?.length || 0 }} / {{ job.plan?.records?.length || 0 }}</div>
          </details>
          <VBtn v-if="job.state === 'failed'" class="mt-3" color="warning" variant="tonal" size="small" :loading="retryId === job.id" :disabled="!enabled || Boolean(retryId)" @click="retry(job)">核验后重试</VBtn>
        </VCardText>
      </VCard>
      <VPagination v-if="pages > 1" v-model="page" :length="pages" :total-visible="5" density="compact" @update:model-value="load" />
    </template>
  </div>
</template>

<style scoped>
.dm-sync { background: transparent; min-width: 0; }
.dm-sync-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dm-sync-switches { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 16px; }
.dm-sync-job { background: transparent !important; }
.dm-sync-path { overflow-wrap: anywhere; font-size: 12px; }
.dm-sync-preview { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 12px; }
.dm-sync summary { cursor: pointer; }
.dm-sync-mapping { display: grid; grid-template-columns: 1fr 1fr auto; align-items: center; gap: 8px; }
.dm-sync-mapping-cloud { grid-template-columns: 1fr 1fr 1fr auto; }
@media (max-width: 760px) { .dm-sync-mapping, .dm-sync-mapping-cloud { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .dm-sync-switches { grid-template-columns: 1fr; } }
</style>
