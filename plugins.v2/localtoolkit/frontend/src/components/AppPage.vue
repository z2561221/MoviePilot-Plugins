<script setup>
import { ref, onMounted, computed } from 'vue'
import { apiGet, apiPost } from '../api.js'

const props = defineProps({ api: { type: Object, default: () => ({}) } })

const status = ref(null)
const history = ref([])
const loadingModule = ref('')
const result = ref(null)
const page = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.max(1, Math.ceil((history.value?.length || 0) / pageSize)))
const pagedHistory = computed(() => {
  if (!history.value?.length) return []
  const start = (page.value - 1) * pageSize
  return history.value.slice(start, start + pageSize)
})

const modules = computed(() => [
  {
    key: 'library_cleanup',
    title: '清理库存',
    icon: 'mdi-delete-sweep-outline',
    color: 'error',
    action: '立即执行',
    mode: '周期 + 按需',
    desc: '唯一支持后台周期运行的模块，手动执行也会遵循自动删除策略。',
    meta: [
      `周期：${status.value?.modules?.library_cleanup?.enabled ? '开启' : '关闭'}`,
      `自动删除：${status.value?.modules?.library_cleanup?.auto_delete ? '开启' : '关闭'}`,
      `Cron：${status.value?.modules?.library_cleanup?.cron || '未设置'}`,
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
    status.value = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/status')
    history.value = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/history')
    page.value = 1
  } catch (e) {
    result.value = { success: false, message: String(e) }
  }
}

async function run(moduleKey) {
  loadingModule.value = moduleKey
  try {
    result.value = await apiPost(props.api, `plugin/LocalToolkit/local_toolkit/run/${moduleKey}`)
  } catch (e) {
    result.value = { success: false, message: String(e) }
  } finally {
    loadingModule.value = ''
    await load()
  }
}

function prevPage() { if (page.value > 1) page.value-- }
function nextPage() { if (page.value < totalPages.value) page.value++ }

onMounted(load)
</script>

<template>
  <div class="toolkit-page pa-4">
    <VCard class="hero mb-4" variant="flat">
      <VCardItem>
        <template #prepend>
          <VAvatar color="teal" variant="tonal" rounded="lg" size="48"><VIcon icon="mdi-tools" size="28" /></VAvatar>
        </template>
        <VCardTitle class="text-h6">工具中心</VCardTitle>
        <VCardSubtitle>清理库存保留周期运行；扫描缺集与清理TMDB改为按需单次执行。</VCardSubtitle>
        <template #append>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" @click="load">刷新</VBtn>
          <VBtn size="small" variant="text" icon="mdi-close" @click="emit('close')" class="ml-1" />
        </template>
      </VCardItem>
    </VCard>

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

    <VCard class="history-card" variant="flat">
      <VCardItem>
        <VCardTitle>运行历史</VCardTitle>
        <VCardSubtitle>每页 10 条，共 {{ history?.length || 0 }} 条记录。</VCardSubtitle>
        <template #append>
          <div class="d-flex align-center">
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-left" :disabled="page <= 1" @click="prevPage" class="mr-1" />
            <span class="text-caption mx-1">{{ page }} / {{ totalPages }}</span>
            <VBtn size="x-small" variant="tonal" icon="mdi-chevron-right" :disabled="page >= totalPages" @click="nextPage" />
          </div>
        </template>
      </VCardItem>
      <VDivider />
      <VTable density="compact">
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
.hero, .history-card { border-radius: 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow: hidden; }
.module-card { border-radius: 16px; min-height: 245px; height: 100%; }
.module-desc { font-size: 13px; line-height: 1.55; color: rgba(var(--v-theme-on-surface), .72); min-height: 42px; }
.module-meta { font-size: 12px; line-height: 1.7; color: rgba(var(--v-theme-on-surface), .68); }
th { font-weight: 700; }
</style>
