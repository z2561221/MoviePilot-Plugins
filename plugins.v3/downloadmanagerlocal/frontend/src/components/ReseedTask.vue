<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getPluginApi, postPluginJsonApi, isApiRequestCancellation } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  canManage: { type: Boolean, default: false },
})
const task = ref({ status: 'idle', phase: '尚未运行' })
const items = ref([])
const page = ref(1)
const error = ref('')
const requestProblem = ref('')
const submitting = ref(false)
const active = computed(() => ['queued', 'running', 'cancelling'].includes(task.value.status))
const pages = computed(() => Math.max(1, Math.ceil((task.value.result_count || 0) / 50)))
let revision = 0
let pollRevision = 0
let controller
let timer

function reset() {
  revision += 1
  pollRevision += 1
  controller?.abort()
  clearTimeout(timer)
  submitting.value = false
}

async function refresh() {
  const current = revision
  const api = props.api
  const pluginId = props.pluginId
  if (!props.canManage || !api || submitting.value) return
  const poll = ++pollRevision
  controller?.abort()
  controller = new AbortController()
  try {
    const next = await getPluginApi(api, pluginId, 'reseed/status', { signal: controller.signal, feedback: 'silent' })
    if (current !== revision || poll !== pollRevision) return
    if (next.task_id !== task.value.task_id) page.value = 1
    task.value = next
    if (next.task_id && next.result_count) {
      const result = await getPluginApi(api, pluginId, 'reseed/results', {
        params: { task_id: next.task_id, offset: (page.value - 1) * 50, limit: 50 },
        signal: controller.signal, feedback: 'silent',
      })
      if (current !== revision || poll !== pollRevision || task.value.task_id !== result.task_id) return
      items.value = result.items
    } else items.value = []
    error.value = ''
  } catch (reason) {
    if (current === revision && poll === pollRevision && !isApiRequestCancellation(reason)) error.value = reason?.message || '读取辅种进度失败'
  } finally {
    if (current === revision && poll === pollRevision) {
      clearTimeout(timer)
      timer = setTimeout(refresh, active.value ? 2500 : 10000)
    }
  }
}

async function stop() {
  if (!props.canManage || !active.value || submitting.value) return
  const current = revision
  pollRevision += 1
  controller?.abort()
  clearTimeout(timer)
  submitting.value = true
  requestProblem.value = ''
  try {
    const result = await postPluginJsonApi(props.api, props.pluginId, 'reseed/stop', { task_id: task.value.task_id }, { feedback: 'silent' })
    if (current === revision) task.value = result
  } catch (reason) {
    if (current === revision) requestProblem.value = reason?.message || '停止任务失败'
  } finally {
    if (current === revision) {
      submitting.value = false
      await refresh()
    }
  }
}

watch(() => [props.api, props.pluginId, props.canManage], () => {
  reset()
  task.value = { status: 'idle', phase: '尚未运行' }
  items.value = []
  error.value = ''
  requestProblem.value = ''
  page.value = 1
  refresh()
}, { immediate: true })
watch(page, () => { clearTimeout(timer); refresh() })
onBeforeUnmount(reset)
</script>

<template>
  <div class="mt-4">
    <div class="d-flex flex-wrap ga-2 align-center">
      <VBtn v-if="active" variant="text" :disabled="!canManage || submitting" @click="stop">停止</VBtn>
      <span role="status">{{ task.phase }}</span>
    </div>
    <VAlert v-if="requestProblem || error" type="error" variant="tonal" density="compact" class="mt-2">{{ requestProblem || error }}</VAlert>
    <VProgressLinear v-if="active" indeterminate class="mt-3" />
    <div v-if="task.task_id" class="text-body-2 mt-3">
      已扫描 {{ task.scanned }} · 命中 {{ task.matched }} · 已添加 {{ task.added }} · 跳过 {{ task.skipped }} · 失败 {{ task.failed }}
      <div>{{ task.message }}</div>
    </div>
    <VTable v-if="items.length" density="compact" class="mt-3">
      <thead><tr><th>站点</th><th>来源 hash</th><th>处理结果</th></tr></thead>
      <tbody><tr v-for="(item, index) in items" :key="`${task.task_id}-${page}-${index}`">
        <td>{{ item.site || '—' }}</td><td :title="item.source_hash">{{ item.source_hash?.slice(0, 12) || '—' }}</td><td>{{ item.message }}</td>
      </tr></tbody>
    </VTable>
    <VPagination v-if="pages > 1" v-model="page" :length="pages" :total-visible="5" />
  </div>
</template>
