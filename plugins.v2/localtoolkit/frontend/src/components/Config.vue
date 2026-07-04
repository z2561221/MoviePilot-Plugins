<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { apiGet } from '../api.js'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const defaults = {
  enabled: false,
  tmdb_cache: { notify: true, auto_clear: false, threshold_mb: 50 },
  check_missing: { notify: true, scan_paths: '', skip_empty: true },
  library_cleanup: {
    enabled: false,
    cron: '9 0 * * *',
    notify: true,
    days_threshold: 30,
    selected_server: '',
    selected_library: '',
    selected_user: '',
    filter_played: 'played',
    filter_favorite: 'unfav',
    auto_delete: false,
    auto_delete_delay: 60,
    dry_run: false,
    auto_delete_max_count: 20,
  },
}

const form = reactive(JSON.parse(JSON.stringify(defaults)))
const activeMain = ref('overview')
const activeSub = ref('basic')
const loadingOptions = ref(false)
const optionError = ref('')
const cleanupOptions = reactive({ servers: [], libraries: [], users: [] })

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '统一管理三个本地维护模块。', color: 'primary' },
  { key: 'library_cleanup', title: '清理库存', icon: 'mdi-delete-sweep-outline', desc: '唯一保留周期运行的模块，可按 Cron 自动巡检与删除。', color: 'error' },
  { key: 'check_missing', title: '扫描缺集', icon: 'mdi-magnify-scan', desc: '按需单次扫描媒体目录，检查已存在季的缺集。', color: 'primary' },
  { key: 'tmdb_cache', title: '清理TMDB', icon: 'mdi-database-refresh-outline', desc: '按需单次查询与清理 Redis 中的 TMDB 缓存。', color: 'warning' },
]

const subTabs = {
  overview: [{ key: 'basic', title: '模块职责', icon: 'mdi-clipboard-check-outline' }],
  library_cleanup: [
    { key: 'basic', title: '基础设置', icon: 'mdi-timer-cog-outline' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-outline' },
    { key: 'danger', title: '高级选项', icon: 'mdi-alert-outline' },
  ],
  check_missing: [{ key: 'basic', title: '按需扫描', icon: 'mdi-folder-search-outline' }],
  tmdb_cache: [{ key: 'basic', title: '按需清理', icon: 'mdi-database-cog-outline' }],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const pathCount = computed(() => (form.check_missing.scan_paths || '').split('\n').map(i => i.trim()).filter(Boolean).length)
const serverItems = computed(() => cleanupOptions.servers?.length ? cleanupOptions.servers : fallbackItem(form.library_cleanup.selected_server))
const libraryItems = computed(() => cleanupOptions.libraries?.length ? cleanupOptions.libraries : fallbackItem(form.library_cleanup.selected_library))
const userItems = computed(() => cleanupOptions.users?.length ? cleanupOptions.users : fallbackItem(form.library_cleanup.selected_user))

function fallbackItem(value) {
  return value ? [{ title: value, value }] : []
}

function merge(target, source, path = '') {
  Object.entries(source || {}).forEach(([key, value]) => {
    const nextPath = path ? `${path}.${key}` : key
    if ((nextPath === 'tmdb_cache.cron') || (nextPath === 'check_missing.cron')) return
    if (value && typeof value === 'object' && !Array.isArray(value) && target[key]) merge(target[key], value, nextPath)
    else target[key] = value
  })
}

watch(() => props.initialConfig, value => {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, JSON.parse(JSON.stringify(defaults)))
  merge(form, value || {})
  delete form.tmdb_cache.cron
  delete form.check_missing.cron
}, { immediate: true, deep: true })

async function loadOptions() {
  loadingOptions.value = true
  optionError.value = ''
  try {
    const res = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/options')
    const data = res?.library_cleanup || res || {}
    cleanupOptions.servers = data.servers || []
    cleanupOptions.libraries = data.libraries || []
    cleanupOptions.users = data.users || []
    optionError.value = data.error || ''
  } catch (e) {
    optionError.value = String(e)
  } finally {
    loadingOptions.value = false
  }
}

function selectMain(key) {
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || 'basic'
  if (key === 'library_cleanup') loadOptions()
}

watch(() => form.library_cleanup.selected_server, (next, prev) => {
  if (next !== prev && prev !== undefined) {
    cleanupOptions.libraries = []
    cleanupOptions.users = []
    loadOptions()
  }
})

onMounted(loadOptions)

function saveConfig() {
  const payload = JSON.parse(JSON.stringify(form))
  delete payload.tmdb_cache.cron
  delete payload.check_missing.cron
  emit('save', payload)
}
</script>

<template>
  <div class="plugin-config">
    <VCard flat class="plugin-card">
      <VCardItem class="plugin-header">
        <template #prepend>
          <VAvatar :color="currentMain.color" variant="tonal" size="46" rounded="lg">
            <VIcon :icon="currentMain.icon" size="26" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">工具中心</VCardTitle>
        <VCardSubtitle class="text-caption">{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch v-model="form.enabled" color="success" hide-details inset :label="form.enabled ? '已启用' : '已停用'" />
        </template>
      </VCardItem>

      <VDivider />

      <div class="plugin-body">
        <nav class="plugin-nav">
          <VList density="comfortable" nav class="py-2">
            <VListItem v-for="item in mainTabs" :key="item.key" :active="activeMain === item.key" :color="item.color" rounded="lg" class="plugin-nav-item" @click="selectMain(item.key)">
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>

        <section class="plugin-content">
          <div class="plugin-subtabs">
            <button v-for="sub in currentSubs" :key="sub.key" type="button" class="plugin-subtab" :class="{ 'plugin-subtab--active': activeSub === sub.key }" @click="activeSub = sub.key">
              <VIcon :icon="sub.icon" size="18" class="mr-1" />{{ sub.title }}
            </button>
          </div>
          <VDivider />

          <div class="plugin-window">
            <div v-show="activeMain === 'overview'" class="plugin-pane">
              <div class="plugin-section-title">模块职责</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VCard variant="tonal" color="error" class="status-card">
                    <VCardText>
                      <div class="text-subtitle-1 font-weight-bold">清理库存</div>
                      <div class="plugin-hint">周期运行：{{ form.library_cleanup.enabled && form.enabled ? '开启' : '关闭' }}</div>
                      <div class="plugin-hint">Cron：{{ form.library_cleanup.cron || '未设置' }}</div>
                      <div class="plugin-hint">自动删除：{{ form.library_cleanup.auto_delete ? '开启' : '关闭' }}</div>
                    </VCardText>
                  </VCard>
                </VCol>
                <VCol cols="12" md="4">
                  <VCard variant="tonal" color="primary" class="status-card">
                    <VCardText>
                      <div class="text-subtitle-1 font-weight-bold">扫描缺集</div>
                      <div class="plugin-hint">运行方式：按需单次</div>
                      <div class="plugin-hint">扫描路径：{{ pathCount }} 个</div>
                      <div class="plugin-hint">在详情页点击「立即扫描」运行</div>
                    </VCardText>
                  </VCard>
                </VCol>
                <VCol cols="12" md="4">
                  <VCard variant="tonal" color="warning" class="status-card">
                    <VCardText>
                      <div class="text-subtitle-1 font-weight-bold">TMDB 缓存</div>
                      <div class="plugin-hint">运行方式：按需单次</div>
                      <div class="plugin-hint">阈值：{{ form.tmdb_cache.threshold_mb }} MB</div>
                      <div class="plugin-hint">在详情页点击「立即清理」运行</div>
                    </VCardText>
                  </VCard>
                </VCol>
              </VRow>
              <VAlert class="mt-4" type="info" variant="tonal" text="详情页提供三个模块的一键立即执行按钮；配置页只负责保存参数。只有清理库存会在插件启用且模块启用时按 Cron 周期运行。" />
            </div>

            <div v-show="activeMain === 'library_cleanup'" class="plugin-pane">
              <div v-if="activeSub === 'basic'">
                <div class="plugin-section-title text-error">清理库存基础设置</div>
                <VAlert type="warning" variant="tonal" class="mb-4" text="清理库存是唯一周期运行模块。若开启自动删除，请务必确认筛选范围和删除策略。" />
                <VRow>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.enabled" color="error" label="启用周期清理库存" hide-details /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.notify" color="info" label="运行通知" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model="form.library_cleanup.cron" label="Cron 周期" placeholder="9 0 * * *" density="compact" variant="outlined" hide-details /></VCol>
                </VRow>
              </div>

              <div v-if="activeSub === 'filter'">
                <div class="plugin-section-title text-error">筛选条件</div>
                <VRow>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_server" label="媒体服务器" :items="serverItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_library" label="媒体库" :items="libraryItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_user" label="用户" :items="userItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_favorite" label="收藏状态" :items="[{ title: '全部', value: 'all' }, { title: '已收藏', value: 'fav' }, { title: '未收藏', value: 'unfav' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_played" label="看过状态" :items="[{ title: '全部', value: 'all' }, { title: '已看过', value: 'played' }, { title: '未看过', value: 'unplayed' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.days_threshold" label="创建时间阈值（天）" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol v-if="optionError" cols="12"><VAlert type="warning" variant="tonal" density="compact" :text="`媒体服务器选项加载异常：${optionError}`" /></VCol>
                </VRow>
              </div>

              <div v-if="activeSub === 'danger'">
                <div class="plugin-section-title text-error">高级选项</div>
                <VAlert type="error" variant="tonal" class="mb-4" text="自动删除会直接删除 Emby 条目。按钮手动执行清理库存时也会遵循这里的自动删除配置。" />
                <VRow>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.auto_delete" color="error" label="自动删除" hide-details /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.dry_run" color="warning" label="演练模式" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.auto_delete_delay" label="删除间隔（秒）" type="number" min="0" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.auto_delete_max_count" label="单次删除上限" type="number" min="0" density="compact" variant="outlined" hide-details /></VCol>
                </VRow>
              </div>
            </div>

            <div v-show="activeMain === 'check_missing'" class="plugin-pane">
              <div class="plugin-section-title">扫描缺集按需扫描</div>
              <VAlert type="info" variant="tonal" class="mb-4" text="扫描缺集不再提供 Cron 周期配置，只在详情页点击“立即扫描”时运行。空文件夹可按规则跳过。" />
              <VRow>
                <VCol cols="12" md="4"><VSwitch v-model="form.check_missing.notify" color="info" label="运行通知" hide-details /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.check_missing.skip_empty" color="success" label="跳过空文件夹" hide-details /></VCol>
                <VCol cols="12"><VTextarea v-model="form.check_missing.scan_paths" label="扫描路径（一行一个）" rows="6" auto-grow density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
            </div>

            <div v-show="activeMain === 'tmdb_cache'" class="plugin-pane">
              <div class="plugin-section-title text-warning">TMDB 缓存按需清理</div>
              <VAlert type="warning" variant="tonal" class="mb-4" text="清理TMDB不再提供 Cron 周期配置，只在详情页点击“立即清理”时运行。可选择按阈值判断是否真正删除。" />
              <VRow>
                <VCol cols="12" md="4"><VSwitch v-model="form.tmdb_cache.notify" color="info" label="运行通知" hide-details /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.tmdb_cache.auto_clear" color="warning" label="按阈值清理" hide-details /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.tmdb_cache.threshold_mb" label="阈值 MB" type="number" min="0" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
            </div>
          </div>
        </section>
      </div>

      <VDivider />
      <VCardActions class="plugin-actions">
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.plugin-config { padding: 8px; }
.plugin-card { border-radius: 14px; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.plugin-header { padding: 14px 18px; }
.plugin-body { display: flex; min-height: 540px; }
.plugin-nav { width: 176px; flex: 0 0 176px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.plugin-nav-item { margin: 2px 8px; }
.plugin-content { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
.plugin-subtabs { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.plugin-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), .7); background: transparent; border: none; cursor: pointer; transition: background .15s, color .15s; }
.plugin-subtab:hover { background: rgba(var(--v-theme-primary), .08); color: rgb(var(--v-theme-primary)); }
.plugin-subtab--active { background: rgba(var(--v-theme-primary), .14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.plugin-window { flex: 1 1 auto; }
.plugin-pane { padding: 18px 20px; }
.plugin-section-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; color: rgb(var(--v-theme-primary)); }
.plugin-hint { font-size: 12px; line-height: 1.6; color: rgba(var(--v-theme-on-surface), .68); margin-top: 2px; }
.status-card { border-radius: 14px; min-height: 132px; }
.plugin-actions { padding: 10px 18px; }
@media (max-width: 760px) { .plugin-body { flex-direction: column; } .plugin-nav { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); } }
</style>
