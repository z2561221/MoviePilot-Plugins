<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { apiGet, pluginApiPath } from '../api.js'
import { migrateCleanupConfig } from '../cleanupConfig.js'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
})
const emit = defineEmits(['save', 'close', 'switch'])

const defaults = {
  enabled: false,
  tmdb_cache: { notify: true, auto_clear: false, threshold_mb: 50 },
  check_missing: { notify: true, scan_paths: '', skip_empty: true },
  library_cleanup: {
    scan_enabled: false,
    scan_cron: '9 0 * * *',
    scan_notify: true,
    cleanup_enabled: false,
    cleanup_cron: '0 * * * *',
    cleanup_notify: true,
    days_threshold: 20,
    selected_server: '',
    selected_library: '',
    selected_user: '',
    filter_played: 'played',
    filter_favorite: 'unfav',
    filter_played_2: 'unplayed',
    filter_favorite_2: 'unfav',
    days_threshold_2: 40,
    auto_delete: false,
    auto_delete_delay: 60,
    dry_run: false,
    auto_delete_max_count: 10,
    cycle_cooldown_minutes: 60,
  },
}

const form = reactive(JSON.parse(JSON.stringify(defaults)))
const activeMain = ref('overview')
const activeSub = ref('overview')
const loadingOptions = ref(false)
const optionError = ref('')
const cleanupOptions = reactive({ servers: [], libraries: [], users: [] })
let optionsRequestId = 0

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '统一管理三个本地维护模块。', color: 'primary' },
  { key: 'library_cleanup', title: '清理库存', icon: 'mdi-delete-sweep-outline', desc: '扫描与清理独立调度，共用清理计划。', color: 'error' },
  { key: 'check_missing', title: '扫描缺集', icon: 'mdi-magnify-scan', desc: '按需单次扫描媒体目录，检查已存在季的缺集。', color: 'primary' },
  { key: 'tmdb_cache', title: '清理TMDB', icon: 'mdi-database-refresh-outline', desc: '按需单次查询与清理 Redis 中的 TMDB 缓存。', color: 'warning' },
]

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  library_cleanup: [
    { key: 'basic', title: '基础设置', icon: 'mdi-timer-cog-outline' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-outline' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-alert-outline' },
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
  merge(form, { ...(value || {}), library_cleanup: migrateCleanupConfig(value?.library_cleanup) })
  delete form.tmdb_cache.cron
  delete form.check_missing.cron
}, { immediate: true, deep: true })

async function loadOptions() {
  const requestId = ++optionsRequestId
  loadingOptions.value = true
  optionError.value = ''
  try {
    const params = new URLSearchParams({
      selected_server: form.library_cleanup.selected_server || '',
      selected_user: form.library_cleanup.selected_user || '',
    })
    const res = await apiGet(props.api, pluginApiPath(props.pluginId, `local_toolkit/options?${params.toString()}`))
    if (requestId !== optionsRequestId) return
    const data = res?.library_cleanup || res || {}
    cleanupOptions.servers = data.servers || []
    cleanupOptions.libraries = data.libraries || []
    cleanupOptions.users = data.users || []
    optionError.value = data.error || ''
  } catch (e) {
    if (requestId !== optionsRequestId) return
    optionError.value = String(e)
  } finally {
    if (requestId === optionsRequestId) loadingOptions.value = false
  }
}

function selectMain(key) {
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || 'overview'
  if (key === 'library_cleanup') loadOptions()
}

watch(
  () => [form.library_cleanup.selected_server, form.library_cleanup.selected_user],
  ([server, user], [previousServer, previousUser]) => {
    if (server !== previousServer) {
      form.library_cleanup.selected_library = ''
      cleanupOptions.libraries = []
      cleanupOptions.users = []
      if (form.library_cleanup.selected_user) {
        form.library_cleanup.selected_user = ''
        return
      }
      loadOptions()
      return
    }
    if (user !== previousUser) {
      form.library_cleanup.selected_library = ''
      cleanupOptions.libraries = []
      loadOptions()
    }
  },
)

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
          <VList density="comfortable" nav class="plugin-nav-list py-2">
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

          <div class="plugin-window" :class="{ 'plugin-window--overview': activeMain === 'overview' }">
            <div v-show="activeMain === 'overview' && activeSub === 'overview'" class="plugin-pane">
              <div class="plugin-section-title">运行总览</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VCard variant="tonal" color="error" class="status-card">
                    <VCardText>
                      <div class="text-subtitle-1 font-weight-bold">清理库存</div>
                      <div class="plugin-hint">周期扫描：{{ form.library_cleanup.scan_enabled && form.enabled ? form.library_cleanup.scan_cron || '未设置周期' : '关闭' }}</div>
                      <div class="plugin-hint">周期清理：{{ form.library_cleanup.cleanup_enabled && form.enabled ? form.library_cleanup.cleanup_cron || '未设置周期' : '关闭' }}</div>
                      <div class="plugin-hint">清理冷却：{{ form.library_cleanup.cycle_cooldown_minutes }} 分钟</div>
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
              <VAlert class="mt-4" type="info" variant="tonal" text="清理库存分别控制周期扫描与周期清理；插件总开关关闭时，两项定时服务都停止。详情页可手动生成计划或执行一批清理。" />
            </div>

            <div v-show="activeMain === 'library_cleanup'" class="plugin-pane">
              <div v-if="activeSub === 'basic'">
                <div class="plugin-section-title text-error">清理库存基础设置</div>
                <VAlert type="info" variant="tonal" class="mb-4" text="扫描只更新清理计划；立即清理一批仅读取已有计划，删除前逐项复核当前条件。两个周期互斥执行，空计划或冷却中不会重复推送。" />
                <section class="schedule-block schedule-block--scan">
                  <div class="schedule-block__header">
                    <div>
                      <div class="schedule-block__title"><VIcon icon="mdi-magnify-scan" size="18" />周期扫描</div>
                      <div class="plugin-hint">扫描媒体库并更新计划；计划有新增或失效移出时才发送通知。</div>
                    </div>
                    <VSwitch v-model="form.library_cleanup.scan_enabled" color="primary" inset label="启用" hide-details />
                  </div>
                  <VRow class="schedule-block__controls">
                    <VCol cols="12" md="7">
                      <VCronField v-model="form.library_cleanup.scan_cron" label="扫描周期" hint="使用可视化周期选择器" persistent-hint density="compact" variant="outlined" hide-details="auto" :disabled="!form.enabled || !form.library_cleanup.scan_enabled" />
                    </VCol>
                    <VCol cols="12" md="5" class="d-flex align-center">
                      <VSwitch v-model="form.library_cleanup.scan_notify" color="info" inset label="计划变更通知" hide-details :disabled="!form.library_cleanup.scan_enabled" />
                    </VCol>
                  </VRow>
                </section>
                <section class="schedule-block schedule-block--cleanup">
                  <div class="schedule-block__header">
                    <div>
                      <div class="schedule-block__title"><VIcon icon="mdi-delete-sweep-outline" size="18" />周期清理</div>
                      <div class="plugin-hint">只处理已有计划；立即清理一批与周期清理共用冷却、批次数量和复核规则。</div>
                    </div>
                    <VSwitch v-model="form.library_cleanup.cleanup_enabled" color="error" inset label="启用" hide-details />
                  </div>
                  <VRow class="schedule-block__controls">
                    <VCol cols="12" md="7">
                      <VCronField v-model="form.library_cleanup.cleanup_cron" label="清理周期" hint="使用可视化周期选择器" persistent-hint density="compact" variant="outlined" hide-details="auto" :disabled="!form.enabled || !form.library_cleanup.cleanup_enabled" />
                    </VCol>
                    <VCol cols="12" md="5" class="d-flex align-center">
                      <VSwitch v-model="form.library_cleanup.cleanup_notify" color="info" inset label="清理结果通知" hide-details :disabled="!form.library_cleanup.cleanup_enabled" />
                    </VCol>
                    <VCol cols="12" sm="6" md="4">
                      <VTextField v-model.number="form.library_cleanup.cycle_cooldown_minutes" class="schedule-number-field" label="清理冷却（分钟）" type="number" min="0" max="10080" density="compact" variant="outlined" hide-details />
                    </VCol>
                    <VCol cols="12" sm="6" md="4">
                      <VTextField v-model.number="form.library_cleanup.auto_delete_max_count" class="schedule-number-field" label="每周期删除数量" type="number" min="1" density="compact" variant="outlined" hide-details />
                    </VCol>
                  </VRow>
                </section>
                <div class="plugin-hint schedule-note">Telegram 会在本批原消息中更新进度，其他渠道只接收最终结果。</div>
              </div>

              <div v-if="activeSub === 'filter'">
                <div class="plugin-section-title text-error">筛选条件</div>
                <VRow>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_server" label="媒体服务器" :items="serverItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_user" label="用户" :items="userItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12" md="4"><VSelect v-model="form.library_cleanup.selected_library" label="媒体库" :items="libraryItems" :loading="loadingOptions" density="compact" variant="outlined" clearable hide-details /></VCol>
                  <VCol cols="12"><div class="condition-title">条件一</div></VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_favorite" label="收藏状态" :items="[{ title: '全部', value: 'all' }, { title: '已收藏', value: 'fav' }, { title: '未收藏', value: 'unfav' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_played" label="看过状态" :items="[{ title: '全部', value: 'all' }, { title: '已看过', value: 'played' }, { title: '未看过', value: 'unplayed' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.days_threshold" label="创建时间阈值（天）" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12"><div class="condition-title condition-title--second">条件二</div></VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_favorite_2" label="收藏状态" :items="[{ title: '全部', value: 'all' }, { title: '已收藏', value: 'fav' }, { title: '未收藏', value: 'unfav' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VSelect v-model="form.library_cleanup.filter_played_2" label="看过状态" :items="[{ title: '全部', value: 'all' }, { title: '已看过', value: 'played' }, { title: '未看过', value: 'unplayed' }]" density="compact" variant="outlined" hide-details />
                  </VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.days_threshold_2" label="创建时间阈值（天）" type="number" min="1" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol v-if="optionError" cols="12"><VAlert type="warning" variant="tonal" density="compact" :text="`媒体服务器选项加载异常：${optionError}`" /></VCol>
                </VRow>
              </div>

              <div v-if="activeSub === 'advanced'">
                <div class="plugin-section-title text-error">高级选项</div>
                <VAlert type="error" variant="tonal" class="mb-4" text="自动删除会直接删除 Emby 条目；每周期按上方数量处理，失败或无法核验的对象会留在计划中等待下周期重试。" />
                <VRow>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.auto_delete" color="error" label="自动删除" hide-details /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.library_cleanup.dry_run" color="warning" label="演练模式" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.library_cleanup.auto_delete_delay" label="删除间隔（秒）" type="number" min="0" density="compact" variant="outlined" hide-details /></VCol>
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
.plugin-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.plugin-card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; overflow: hidden; border-radius: 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.plugin-header { padding: 14px 18px; }
.plugin-header :deep(.v-card-subtitle) { max-width: min(560px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plugin-body { flex: 1 1 auto; min-height: 0; display: flex; }
.plugin-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.plugin-nav-list { width: 100%; }
.plugin-nav-item { margin: 2px 8px; }
.plugin-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.plugin-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.plugin-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), .7); background: transparent; border: none; cursor: pointer; transition: background .15s, color .15s; }
.plugin-subtab:hover { background: rgba(var(--v-theme-primary), .08); color: rgb(var(--v-theme-primary)); }
.plugin-subtab--active { background: rgba(var(--v-theme-primary), .14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.plugin-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.plugin-window--overview { overflow-y: hidden; }
.plugin-pane { padding: 18px 20px; }
.plugin-section-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; color: rgb(var(--v-theme-primary)); }
.condition-title { font-size: 13px; font-weight: 700; color: rgba(var(--v-theme-on-surface), .78); margin-top: 6px; }
.condition-title--second { margin-top: 4px; }
.plugin-hint { font-size: 12px; line-height: 1.6; color: rgba(var(--v-theme-on-surface), .68); margin-top: 2px; }
.status-card { border-radius: 14px; min-height: 132px; }
.schedule-block { border: 1px solid rgba(var(--v-border-color), .16); border-radius: 10px; padding: 14px 16px 4px; }
.schedule-block + .schedule-block { margin-top: 12px; }
.schedule-block--scan { border-left: 3px solid rgb(var(--v-theme-primary)); }
.schedule-block--cleanup { border-left: 3px solid rgb(var(--v-theme-error)); }
.schedule-block__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.schedule-block__title { display: flex; align-items: center; gap: 7px; font-size: 14px; font-weight: 700; color: rgba(var(--v-theme-on-surface), .86); }
.schedule-block__controls { margin-top: 4px; }
.schedule-number-field { max-width: 180px; }
.schedule-note { margin: 10px 2px 0; }
.plugin-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .plugin-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .plugin-card { height: min(860px, calc(100dvh - 16px)); }
  .plugin-header :deep(.v-card-subtitle) { max-width: 100%; }
  .plugin-body { flex-direction: column; }
  .plugin-nav {
    width: 100%;
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }
  .plugin-nav::-webkit-scrollbar { display: none; }
  .plugin-nav-list {
    display: flex;
    flex-wrap: nowrap;
    gap: 6px;
    min-width: max-content;
    padding: 8px 12px !important;
  }
  .plugin-nav-item {
    flex: 0 0 auto;
    min-width: 96px;
    margin: 0;
    padding-inline: 10px;
  }
  .plugin-nav-item :deep(.v-list-item-title) { white-space: nowrap; }
  .plugin-subtabs {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    padding: 6px 12px;
  }
  .plugin-subtabs::-webkit-scrollbar { display: none; }
  .plugin-subtab {
    flex: 0 0 auto;
    padding: 6px 12px;
    white-space: nowrap;
  }
  .plugin-window--overview { overflow-y: auto; }
}
@media (max-height: 760px) {
  .plugin-window--overview { overflow-y: auto; }
}
</style>
