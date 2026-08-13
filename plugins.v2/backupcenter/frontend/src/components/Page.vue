<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { downloadBackup, getPluginApi, postPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  showClose: { type: Boolean, default: true },
  showSettings: { type: Boolean, default: false },
  show_switch: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'switch'])

const activeTab = ref('overview')
const loading = ref(false)
const actionLoading = ref('')
const overview = ref({ backups: [], installed_plugin_ids: [], plugin_options: [] })
const selectedBackupId = ref('')
const preview = ref(null)
const guide = ref(null)
const createDialog = ref(false)
const restoreDialog = ref(false)
const guideDialog = ref(false)
const feedback = reactive({ show: false, message: '', color: 'success' })
const createForm = reactive({
  target: 'moviepilot',
  pluginId: '',
  pluginSelection: {
    configuration: false,
    data: false,
  },
  moviepilotSelection: {
    mp_settings: false,
    app_env: false,
    plugin_settings: false,
    cookies: false,
    plugin_data: false,
    plugin_files: false,
    database: false,
  },
})
const restoreForm = reactive({
  password: '',
  pluginIds: [],
  selection: {
    mpSettings: false,
    pluginSettings: false,
    pluginData: false,
  },
})

const tabs = [
  { key: 'overview', title: '备份总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'backups', title: '备份记录', icon: 'mdi-archive-outline' },
  { key: 'restore', title: '恢复中心', icon: 'mdi-database-arrow-left-outline' },
]
const settingsShortcutVisible = computed(() => props.showSettings || props.show_switch)
const backups = computed(() => overview.value?.backups || [])
const backupOptions = computed(() => backups.value.map(item => ({
  title: backupOptionTitle(item),
  value: item.backup_id,
})))
const selectedBackup = computed(() => (
  backups.value.find(item => item.backup_id === selectedBackupId.value) || null
))
const selectedBackupLabel = computed(() => (
  selectedBackup.value ? backupDisplayName(selectedBackup.value) : selectedBackupId.value
))
const createPluginOptions = computed(() => {
  const options = overview.value?.plugin_options || []
  if (options.length) return options
  return (overview.value?.installed_plugin_ids || []).map(value => ({ title: value, value }))
})
const pluginTitleById = computed(() => new Map(
  createPluginOptions.value.map(item => [item.value, item.title]),
))
const restorePluginOptions = computed(() => (
  (preview.value?.manifest?.selected_plugins || []).length
    ? preview.value.manifest.selected_plugins.map(item => ({
      title: item.name || pluginTitleById.value.get(item.id) || item.id,
      value: item.id,
    }))
    : (preview.value?.manifest?.selected_plugin_ids || []).map(value => ({
      title: pluginTitleById.value.get(value) || value,
      value,
    }))
))
const createSelection = computed(() => (
  createForm.target === 'plugin' ? createForm.pluginSelection : createForm.moviepilotSelection
))
const createScopeCount = computed(() => Object.values(createSelection.value).filter(Boolean).length)
const createReady = computed(() => (
  createScopeCount.value > 0
  && (createForm.target === 'moviepilot' || Boolean(createForm.pluginId))
))
const restoreScopeCount = computed(() => Object.values(restoreForm.selection).filter(Boolean).length)
const restoreNeedsPlugins = computed(() => (
  restoreForm.selection.pluginSettings || restoreForm.selection.pluginData
))
const restoreAvailable = computed(() => {
  const scope = preview.value?.manifest?.scope || {}
  return {
    mpSettings: Boolean(scope.mp_settings),
    pluginSettings: Boolean(scope.plugin_settings),
    pluginData: Boolean(scope.plugin_data || scope.plugin_files),
  }
})
const restoreReady = computed(() => (
  Boolean(preview.value?.online_restore_allowed)
  && restoreScopeCount.value > 0
  && (!restoreNeedsPlugins.value || restoreForm.pluginIds.length > 0)
))

function notify(message, color = 'success') {
  feedback.show = true
  feedback.message = message
  feedback.color = color
}

function formatDate(value) {
  if (!value) return '未知时间'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN')
}

function formatSize(bytes) {
  const size = Number(bytes || 0)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function backupKindLabel(kind) {
  return {
    automatic: '自动备份',
    emergency: '恢复前应急备份',
    manual: '手动备份',
  }[kind] || '备份'
}

function backupDisplayName(item = {}) {
  const explicitName = String(item.display_name || '').trim()
  return explicitName || `${backupKindLabel(item.backup_kind)} · ${formatDate(item.created_at)}`
}

function backupOptionTitle(item = {}) {
  return backupDisplayName(item)
}

function backupDownloadName(item = {}) {
  return backupDisplayName(item)
}

function scopeLabels(scope = {}) {
  const labels = {
    mp_settings: 'MP 设置',
    plugin_settings: '插件设置',
    plugin_data: '插件数据',
    plugin_files: '插件文件和缓存',
    app_env: '环境变量',
    cookies: '登录 Cookie',
    database: '整个数据库',
  }
  return Object.entries(scope).filter(([, enabled]) => enabled).map(([key]) => labels[key])
}

async function loadOverview() {
  loading.value = true
  try {
    overview.value = await getPluginApi(props.api, 'overview') || {}
    if (!selectedBackupId.value && backups.value.length) {
      selectedBackupId.value = backups.value[0].backup_id
    }
  } catch (error) {
    notify(error.message || '备份概览加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.target = 'moviepilot'
  createForm.pluginId = ''
  Object.keys(createForm.pluginSelection).forEach(key => { createForm.pluginSelection[key] = false })
  Object.keys(createForm.moviepilotSelection).forEach(key => { createForm.moviepilotSelection[key] = false })
  createDialog.value = true
}

async function createBackup() {
  if (!createScopeCount.value) {
    notify(createForm.target === 'plugin' ? '至少选择配置或数据中的一项' : '至少选择一项备份内容', 'warning')
    return
  }
  if (createForm.target === 'plugin' && !createForm.pluginId) {
    notify('请选择一个插件', 'warning')
    return
  }
  actionLoading.value = 'create'
  try {
    const result = await postPluginApi(props.api, 'backups', {
      target: createForm.target,
      plugin_ids: createForm.target === 'plugin' ? [createForm.pluginId] : [],
      selection: { ...createSelection.value },
    })
    createDialog.value = false
    selectedBackupId.value = result.backup_id
    notify(result.encrypted ? '加密备份已创建，可校验并下载离线恢复包' : '未加密备份已创建，可校验并下载离线恢复包')
    await loadOverview()
  } catch (error) {
    notify(error.message || '创建备份失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function verifyBackup(backupId) {
  actionLoading.value = `verify:${backupId}`
  try {
    const result = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/verify`)
    notify(`校验通过，共验证 ${result.verified_files?.length || 0} 个文件`)
  } catch (error) {
    notify(error.message || '备份校验失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function deleteBackup(backupId) {
  const item = backups.value.find(backup => backup.backup_id === backupId)
  if (!window.confirm(`确认删除“${backupDisplayName(item)}”？此操作不可撤销。`)) return
  actionLoading.value = `delete:${backupId}`
  try {
    await postPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/delete`)
    if (selectedBackupId.value === backupId) selectedBackupId.value = ''
    notify('备份已删除')
    await loadOverview()
  } catch (error) {
    notify(error.message || '备份删除失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function exportBackup(backupId) {
  actionLoading.value = `export:${backupId}`
  try {
    const item = backups.value.find(backup => backup.backup_id === backupId)
    await downloadBackup(
      props.api,
      encodeURIComponent(backupId),
      backupDownloadName(item || { backup_id: backupId }),
    )
    notify('离线恢复包下载已开始')
  } catch (error) {
    notify(error.message || '离线恢复包下载失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function showGuide(backupId) {
  actionLoading.value = `guide:${backupId}`
  try {
    guide.value = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/guide`)
    selectedBackupId.value = backupId
    guideDialog.value = true
  } catch (error) {
    notify(error.message || '恢复教程读取失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function prepareRestore(backupId) {
  selectedBackupId.value = backupId
  actionLoading.value = `preview:${backupId}`
  try {
    preview.value = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/preview`)
    restoreForm.password = ''
    restoreForm.pluginIds = []
    Object.keys(restoreForm.selection).forEach(key => { restoreForm.selection[key] = false })
    restoreDialog.value = true
  } catch (error) {
    notify(error.message || '恢复预检失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

async function restoreLogical() {
  if (!preview.value?.online_restore_allowed) {
    notify('源与目标 MoviePilot 主版本不一致，在线恢复已阻断', 'error')
    return
  }
  if (!restoreScopeCount.value) {
    notify('至少选择一项在线恢复内容', 'warning')
    return
  }
  actionLoading.value = 'restore'
  try {
    const scope = preview.value?.manifest?.scope || {}
    const hasPluginSelection = restoreForm.pluginIds.length > 0
    const result = await postPluginApi(props.api, 'restore/logical', {
      backup_id: selectedBackupId.value,
      password: restoreForm.password,
      plugin_ids: restoreForm.pluginIds,
      selection: {
        mp_settings: restoreForm.selection.mpSettings && Boolean(scope.mp_settings),
        plugin_settings: restoreForm.selection.pluginSettings && hasPluginSelection && Boolean(scope.plugin_settings),
        plugin_data: restoreForm.selection.pluginData && hasPluginSelection && Boolean(scope.plugin_data),
        plugin_files: restoreForm.selection.pluginData && hasPluginSelection && Boolean(scope.plugin_files),
      },
    })
    restoreDialog.value = false
    const reloaded = result.reloaded?.length
      ? `；已重载：${result.reloaded.join('、')}`
      : ''
    const reload = result.reload_required?.length
      ? `；重载失败，请检查：${result.reload_required.join('、')}`
      : ''
    notify(`选择性恢复完成，应急备份 ${result.emergency_backup_id}${reloaded}${reload}`, result.reload_required?.length ? 'warning' : 'success')
    await loadOverview()
  } catch (error) {
    notify(error.message || '选择性恢复失败', 'error')
  } finally {
    actionLoading.value = ''
  }
}

onMounted(loadOverview)
</script>

<template>
  <div class="bc-page">
    <VToolbar density="comfortable" class="bc-toolbar">
      <VIcon icon="mdi-shield-sync-outline" class="ms-3 me-2" color="primary" />
      <div class="bc-toolbar-copy">
        <div class="text-h6">备份中心</div>
        <div class="text-caption text-medium-emphasis bc-toolbar-subtitle">
          可选加密备份、选择性恢复与停机整库恢复指引
        </div>
      </div>
      <VSpacer />
      <VBtn v-if="settingsShortcutVisible" icon="mdi-cog-outline" variant="text" aria-label="打开配置" @click="emit('switch')">
        <VTooltip activator="parent">打开配置</VTooltip>
      </VBtn>
      <VBtn icon="mdi-refresh" variant="text" aria-label="刷新" :loading="loading" @click="loadOverview">
        <VTooltip activator="parent">刷新</VTooltip>
      </VBtn>
      <VBtn v-if="showClose" icon="mdi-close" variant="text" aria-label="关闭" @click="emit('close')">
        <VTooltip activator="parent">关闭</VTooltip>
      </VBtn>
    </VToolbar>
    <VDivider />

    <div class="bc-tabs" role="tablist" aria-label="备份中心视图">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="bc-tab"
        :class="{ 'bc-tab--active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <VIcon :icon="tab.icon" size="18" />
        <span>{{ tab.title }}</span>
      </button>
    </div>
    <VDivider />

    <main class="bc-content">
      <div v-if="loading && !backups.length" class="bc-state">
        <VProgressCircular indeterminate color="primary" />
      </div>

      <template v-else-if="activeTab === 'overview'">
        <section class="bc-stat-grid">
          <div class="bc-stat">
            <VIcon icon="mdi-archive-check-outline" color="primary" size="24" />
            <div><strong>{{ overview.backup_count || 0 }}</strong><span>本地备份</span></div>
          </div>
          <div class="bc-stat">
            <VIcon icon="mdi-database-outline" color="info" size="24" />
            <div><strong>{{ overview.database_type || '未知' }}</strong><span>当前数据库</span></div>
          </div>
          <div class="bc-stat">
          <VIcon :icon="overview.encryption_active ? 'mdi-lock-check-outline' : 'mdi-lock-open-outline'" :color="overview.encryption_active ? 'success' : 'warning'" size="24" />
          <div><strong>{{ overview.encryption_active ? '已加密' : '未加密' }}</strong><span>新建备份格式</span></div>
          </div>
        </section>

        <section class="bc-band">
          <div class="bc-band-heading">
            <div>
              <div class="text-subtitle-1 font-weight-bold">恢复路径</div>
              <div class="bc-muted">不同数据按风险进入独立恢复路径。</div>
            </div>
            <VBtn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreate">
              新建备份
            </VBtn>
          </div>
          <div class="bc-route-grid">
            <div class="bc-route">
              <VIcon icon="mdi-cloud-sync-outline" color="success" size="26" />
              <div>
                <div class="bc-route-title">在线选择性恢复</div>
                <div class="bc-muted">配置和数据。恢复前自动创建应急备份。</div>
              </div>
            </div>
            <div class="bc-route">
              <VIcon icon="mdi-power-plug-off-outline" color="warning" size="26" />
              <div>
                <div class="bc-route-title">离线整库恢复</div>
                <div class="bc-muted">SQLite 或 PostgreSQL 完整快照。必须停机并按包内教程操作。</div>
              </div>
            </div>
          </div>
        </section>

        <section class="bc-band">
          <div class="bc-band-heading">
            <div>
              <div class="text-subtitle-1 font-weight-bold">最近备份</div>
              <div class="bc-muted">先校验，再下载或进入恢复预检。</div>
            </div>
            <VBtn variant="text" append-icon="mdi-arrow-right" @click="activeTab = 'backups'">全部记录</VBtn>
          </div>
          <div v-if="!backups.length" class="bc-empty">
            <VIcon icon="mdi-archive-off-outline" size="34" />
            <span>尚无备份记录</span>
          </div>
          <div v-else class="bc-backup-list">
            <article v-for="item in backups.slice(0, 3)" :key="item.backup_id" class="bc-backup-row">
              <div class="bc-backup-main">
                <div class="bc-backup-title">{{ backupDisplayName(item) }}</div>
                <div class="bc-backup-meta">{{ formatSize(item.package_size) }} · {{ item.backup_id }}</div>
              </div>
              <VChip size="small" :color="item.database?.included ? 'warning' : 'success'" variant="tonal">
                {{ item.database?.included ? '含整库快照' : '逻辑备份' }}
              </VChip>
              <div class="bc-row-actions">
                <VBtn icon="mdi-check-decagram-outline" size="small" variant="text" :loading="actionLoading === `verify:${item.backup_id}`" @click="verifyBackup(item.backup_id)"><VTooltip activator="parent">校验</VTooltip></VBtn>
                <VBtn icon="mdi-download-outline" size="small" variant="text" :loading="actionLoading === `export:${item.backup_id}`" @click="exportBackup(item.backup_id)"><VTooltip activator="parent">下载离线包</VTooltip></VBtn>
                <VBtn icon="mdi-database-arrow-left-outline" size="small" variant="text" @click="prepareRestore(item.backup_id)"><VTooltip activator="parent">恢复预检</VTooltip></VBtn>
                <VBtn icon="mdi-delete-outline" size="small" variant="text" color="error" :loading="actionLoading === `delete:${item.backup_id}`" @click="deleteBackup(item.backup_id)"><VTooltip activator="parent">删除备份</VTooltip></VBtn>
              </div>
            </article>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'backups'">
        <section class="bc-band bc-band--top">
          <div class="bc-band-heading">
            <div>
              <div class="text-subtitle-1 font-weight-bold">备份记录</div>
              <div class="bc-muted">每个离线包都包含明文教程、校验清单、工具，以及普通 ZIP 或加密负载。</div>
            </div>
            <VBtn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreate">新建备份</VBtn>
          </div>
          <div v-if="!backups.length" class="bc-empty">暂无备份记录</div>
          <div v-else class="bc-record-grid">
            <VCard v-for="item in backups" :key="item.backup_id" variant="outlined" class="bc-record-card">
              <VCardItem>
                <VCardTitle class="bc-record-title">{{ backupDisplayName(item) }}</VCardTitle>
                <VCardSubtitle>{{ item.backup_id }}</VCardSubtitle>
                <template #append>
                  <VChip size="small" :color="item.database?.included ? 'warning' : 'success'" variant="tonal">
                    {{ item.database?.included ? item.database.type : '逻辑' }}
                  </VChip>
                </template>
              </VCardItem>
              <VCardText>
                <div class="bc-chip-list">
                  <VChip v-for="label in scopeLabels(item.scope)" :key="label" size="x-small" variant="tonal">{{ label }}</VChip>
                </div>
                <div class="bc-record-facts">
                  <span>{{ item.selected_plugin_ids?.length || 0 }} 个插件</span>
                  <span>{{ formatSize(item.package_size) }}</span>
                  <span>{{ backupKindLabel(item.backup_kind) }}</span>
                  <span>{{ item.encrypted ? 'AES-256-GCM' : '未加密' }}</span>
                </div>
              </VCardText>
              <VDivider />
              <VCardActions>
                <VBtn size="small" variant="text" prepend-icon="mdi-check-decagram-outline" :loading="actionLoading === `verify:${item.backup_id}`" @click="verifyBackup(item.backup_id)">校验</VBtn>
                <VBtn size="small" variant="text" prepend-icon="mdi-book-open-page-variant-outline" :loading="actionLoading === `guide:${item.backup_id}`" @click="showGuide(item.backup_id)">教程</VBtn>
                <VBtn size="small" variant="text" color="error" prepend-icon="mdi-delete-outline" :loading="actionLoading === `delete:${item.backup_id}`" @click="deleteBackup(item.backup_id)">删除</VBtn>
                <VSpacer />
                <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-download-outline" :loading="actionLoading === `export:${item.backup_id}`" @click="exportBackup(item.backup_id)">下载</VBtn>
              </VCardActions>
            </VCard>
          </div>
        </section>
      </template>

      <template v-else>
        <section class="bc-band bc-band--top">
          <div class="bc-band-heading">
            <div>
              <div class="text-subtitle-1 font-weight-bold">恢复中心</div>
              <div class="bc-muted">一次选择一份备份；恢复内容可以只选一项，也可以按需多选。</div>
            </div>
          </div>
          <VSelect
            v-model="selectedBackupId"
            :items="backupOptions"
            item-title="title"
            item-value="value"
            label="选择一份备份"
            density="compact"
            variant="outlined"
            hide-details
            class="bc-backup-select"
          />
          <div v-if="selectedBackup" class="bc-restore-paths">
            <div class="bc-restore-path">
              <div class="bc-restore-icon bc-restore-icon--online"><VIcon icon="mdi-cloud-sync-outline" /></div>
              <div class="bc-restore-copy">
                <div class="bc-route-title">在线选择性恢复</div>
                <div class="bc-muted">恢复配置或数据。不会替换整个数据库。</div>
                <VBtn class="mt-3" color="primary" variant="tonal" prepend-icon="mdi-file-search-outline" :loading="actionLoading === `preview:${selectedBackupId}`" @click="prepareRestore(selectedBackupId)">开始预检</VBtn>
              </div>
            </div>
            <div class="bc-restore-path">
              <div class="bc-restore-icon bc-restore-icon--offline"><VIcon icon="mdi-power-plug-off-outline" /></div>
              <div class="bc-restore-copy">
                <div class="bc-route-title">离线整库恢复</div>
                <div class="bc-muted">{{ selectedBackup.database?.included ? `包含 ${selectedBackup.database.type} 快照，必须停机恢复。` : '此备份未包含完整数据库快照。' }}</div>
                <div class="d-flex flex-wrap ga-2 mt-3">
                  <VBtn variant="outlined" prepend-icon="mdi-book-open-page-variant-outline" @click="showGuide(selectedBackupId)">查看教程</VBtn>
                  <VBtn color="warning" variant="tonal" prepend-icon="mdi-download-outline" @click="exportBackup(selectedBackupId)">下载离线包</VBtn>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="bc-empty">请选择一份备份</div>
        </section>
      </template>
    </main>

    <VDialog v-model="createDialog" max-width="760" :persistent="actionLoading === 'create'">
      <VCard class="bc-dialog-card">
        <VCardItem>
          <template #prepend><VIcon icon="mdi-archive-lock-outline" color="primary" size="26" /></template>
          <VCardTitle>新建备份</VCardTitle>
          <VCardSubtitle>{{ overview.encryption_active ? '将使用配置页保存的口令加密。' : '当前未设置口令，将生成普通 ZIP。' }}</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="bc-dialog-scroll">
          <div class="bc-section-label">备份对象</div>
          <VBtnToggle v-model="createForm.target" mandatory density="compact" color="primary" variant="outlined" divided class="mb-4">
            <VBtn value="moviepilot" prepend-icon="mdi-movie-open-cog-outline">MoviePilot</VBtn>
            <VBtn value="plugin" prepend-icon="mdi-puzzle-outline">插件</VBtn>
          </VBtnToggle>
          <template v-if="createForm.target === 'plugin'">
            <div class="bc-muted mb-2">每份手动备份只打包一个插件，包名会使用插件中文名。</div>
          <VSelect
            v-model="createForm.pluginId"
            :items="createPluginOptions"
            item-title="title"
            item-value="value"
            label="选择一个插件"
            density="compact"
            variant="outlined"
            hide-details
            class="mb-5"
          />
          </template>
          <div class="bc-section-label">备份内容 · 已选 {{ createScopeCount }} 项</div>
          <div class="bc-muted bc-scope-explain">默认全部不选，只保存你明确勾选的内容。</div>
          <div v-if="createForm.target === 'plugin'" class="bc-scope-groups">
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">配置</div>
              <VCheckbox v-model="createForm.pluginSelection.configuration" label="插件设置" density="compact" hide-details />
              <div class="bc-muted px-2 pb-2">插件在 MoviePilot 中保存的配置。</div>
            </section>
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">数据</div>
              <VCheckbox v-model="createForm.pluginSelection.data" label="插件数据" density="compact" hide-details />
              <div class="bc-muted px-2 pb-2">插件保存的数据、文件和缓存。</div>
            </section>
          </div>
          <div v-else class="bc-scope-groups">
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">配置</div>
              <VCheckbox v-model="createForm.moviepilotSelection.mp_settings" label="MoviePilot 设置" density="compact" hide-details />
              <VCheckbox v-model="createForm.moviepilotSelection.app_env" label="环境变量（app.env）" density="compact" hide-details />
              <VCheckbox v-model="createForm.moviepilotSelection.plugin_settings" label="插件设置" density="compact" hide-details />
              <VCheckbox v-model="createForm.moviepilotSelection.cookies" label="登录 Cookie" density="compact" hide-details />
            </section>
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">数据</div>
              <VCheckbox v-model="createForm.moviepilotSelection.plugin_data" label="插件保存的数据（PluginData）" density="compact" hide-details />
              <VCheckbox v-model="createForm.moviepilotSelection.plugin_files" label="插件文件和缓存" density="compact" hide-details />
              <VCheckbox v-model="createForm.moviepilotSelection.database" label="整个数据库" density="compact" hide-details />
              <div class="bc-muted px-2 pb-2">完整数据库只能停机后按包内教程恢复。</div>
            </section>
          </div>
          <VAlert :type="overview.encryption_active ? 'info' : 'warning'" variant="tonal" density="compact" class="mt-4">
            {{ overview.encryption_active ? '这份备份会使用配置页保存的口令加密。' : '这份备份不会加密，请妥善保管下载文件。' }}
          </VAlert>
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="createDialog = false">取消</VBtn>
          <VBtn color="primary" variant="flat" prepend-icon="mdi-archive-plus-outline" :disabled="!createReady" :loading="actionLoading === 'create'" @click="createBackup">创建备份</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="restoreDialog" max-width="820" :persistent="actionLoading === 'restore'">
      <VCard class="bc-dialog-card">
        <VCardItem>
          <template #prepend><VIcon icon="mdi-database-arrow-left-outline" color="warning" size="26" /></template>
          <VCardTitle>选择性恢复预检</VCardTitle>
          <VCardSubtitle class="bc-dialog-subtitle">{{ selectedBackupLabel }} · {{ selectedBackupId }}</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="bc-dialog-scroll">
          <VAlert :type="preview?.online_restore_allowed ? 'success' : 'error'" variant="tonal" density="compact" class="mb-4">
            {{ preview?.online_restore_allowed ? 'MoviePilot 主版本兼容，可执行在线选择性恢复。' : 'MoviePilot 主版本不兼容，在线恢复已阻断。' }}
          </VAlert>
          <div class="bc-preview-grid">
            <div><span>来源版本</span><strong>{{ preview?.manifest?.source_mp_version || '未知' }}</strong></div>
            <div><span>数据库模式</span><strong>{{ preview?.database_restore_mode === 'offline' ? '整库仅离线' : '无整库快照' }}</strong></div>
            <div><span>外层校验</span><strong>{{ preview?.verified_files?.length || 0 }} 个文件</strong></div>
            <div><span>插件范围</span><strong>{{ preview?.manifest?.selected_plugin_ids?.length || 0 }} 个</strong></div>
          </div>
          <div class="bc-section-label mt-5">在线恢复哪些内容 · 已选 {{ restoreScopeCount }} 项</div>
          <div class="bc-muted bc-scope-explain">只能恢复这份备份里实际保存过的内容；可以只选一项，也可以按需多选。</div>
          <div class="bc-scope-groups">
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">MoviePilot</div>
              <VCheckbox v-model="restoreForm.selection.mpSettings" label="恢复 MoviePilot 配置" :disabled="!restoreAvailable.mpSettings" density="compact" hide-details />
              <div class="bc-muted px-2 pb-2">恢复非插件系统设置，不包含 app.env 和插件安装清单。</div>
            </section>
            <section class="bc-scope-group">
              <div class="bc-scope-group-title">插件</div>
              <VCheckbox v-model="restoreForm.selection.pluginSettings" label="恢复插件配置" :disabled="!restoreAvailable.pluginSettings" density="compact" hide-details />
              <VCheckbox v-model="restoreForm.selection.pluginData" label="恢复插件数据" :disabled="!restoreAvailable.pluginData" density="compact" hide-details />
              <div class="bc-muted px-2 pb-2">先在下方选择插件；数据包含 PluginData、插件文件和缓存。</div>
            </section>
          </div>
          <VSelect
            v-model="restoreForm.pluginIds"
            :items="restorePluginOptions"
            item-title="title"
            item-value="value"
            label="选择要恢复的插件"
            multiple
            chips
            closable-chips
            density="compact"
            variant="outlined"
            hide-details
            class="mt-4"
          />
          <VTextField
            v-if="preview?.encrypted"
            v-model="restoreForm.password"
            label="备份口令"
            type="password"
            density="compact"
            variant="outlined"
            hide-details
            autocomplete="current-password"
            class="mt-4"
            hint="留空时尝试使用配置页当前保存的口令"
            persistent-hint
          />
          <VAlert type="warning" variant="tonal" density="compact" class="mt-4">
            恢复时会停用目标插件并自动重载；失败项会单独列出。完整数据库和 app.env 不会在线恢复。
          </VAlert>
        </VCardText>
        <VDivider />
        <VCardActions class="bc-restore-actions">
          <VSpacer />
          <VBtn variant="text" @click="restoreDialog = false">取消</VBtn>
          <VBtn class="bc-restore-submit" color="warning" variant="flat" prepend-icon="mdi-shield-alert-outline" :disabled="!restoreReady" :loading="actionLoading === 'restore'" @click="restoreLogical">确认恢复</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="guideDialog" max-width="900">
      <VCard class="bc-guide-dialog">
        <VCardItem>
          <template #prepend><VIcon icon="mdi-book-open-page-variant-outline" color="primary" size="26" /></template>
          <VCardTitle>离线恢复教程</VCardTitle>
          <VCardSubtitle class="bc-dialog-subtitle">{{ selectedBackupLabel }} · {{ selectedBackupId }}</VCardSubtitle>
          <template #append><VBtn icon="mdi-close" variant="text" @click="guideDialog = false"><VTooltip activator="parent">关闭</VTooltip></VBtn></template>
        </VCardItem>
        <VDivider />
        <div class="bc-guide-layout">
          <section>
            <div class="bc-section-label">恢复教程</div>
            <pre class="bc-guide-text">{{ guide?.guide || '' }}</pre>
          </section>
          <section>
            <div class="bc-section-label">恢复核对清单</div>
            <pre class="bc-guide-text">{{ guide?.checklist || '' }}</pre>
          </section>
        </div>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn color="primary" variant="flat" prepend-icon="mdi-download-outline" @click="exportBackup(selectedBackupId)">下载完整离线包</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VSnackbar v-model="feedback.show" :color="feedback.color" timeout="6000">
      {{ feedback.message }}
    </VSnackbar>
  </div>
</template>

<style scoped>
:global(.v-overlay__content:has(.bc-page)) { width: min(960px, calc(100vw - 48px)) !important; max-width: min(960px, calc(100vw - 48px)) !important; }
:global(.v-overlay__content:has(.bc-page) > .v-card),
:global(.v-overlay__content:has(.bc-page) > .v-card > .v-card-text) { width: 100%; }
.bc-page { width: min(960px, calc(100vw - 48px)); max-width: 100%; height: min(660px, calc(100dvh - 48px)); min-width: 0; min-height: 0; margin: 0 auto; display: flex; flex-direction: column; background: transparent; overflow: hidden; }
.bc-toolbar { flex: 0 0 auto; background: transparent; }
.bc-toolbar-copy { min-width: 0; }
.bc-toolbar-subtitle { max-width: min(620px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bc-tabs { flex: 0 0 auto; display: flex; gap: 4px; padding: 7px 14px; overflow-x: auto; scrollbar-width: none; }
.bc-tabs::-webkit-scrollbar { display: none; }
.bc-tab { height: 36px; display: inline-flex; flex: 0 0 auto; align-items: center; gap: 7px; padding: 0 14px; border: 0; border-radius: 8px; color: rgba(var(--v-theme-on-surface), .7); background: transparent; cursor: pointer; font-size: 13px; font-weight: 500; }
.bc-tab:hover { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .07); }
.bc-tab--active { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); font-weight: 600; }
.bc-content { flex: 1 1 auto; width: 100%; min-height: 0; margin: 0 auto; padding: 14px 16px 18px; overflow-y: auto; }
.bc-state { min-height: 300px; display: grid; place-items: center; }
.bc-stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.bc-stat { min-width: 0; display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .018); }
.bc-stat > div { min-width: 0; display: flex; flex-direction: column; }
.bc-stat strong { font-size: 18px; line-height: 1.35; overflow-wrap: anywhere; }
.bc-stat span { color: rgba(var(--v-theme-on-surface), .6); font-size: 12px; }
.bc-band { margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.bc-band--top { margin-top: 0; padding-top: 0; border-top: 0; }
.bc-band-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 10px; }
.bc-muted { color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.bc-route-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.bc-route { display: flex; gap: 10px; padding: 11px 12px; border-left: 3px solid rgba(var(--v-theme-primary), .55); background: rgba(var(--v-theme-on-surface), .022); }
.bc-route:nth-child(2) { border-left-color: rgba(var(--v-theme-warning), .72); }
.bc-route-title { margin-bottom: 3px; font-size: 14px; font-weight: 650; }
.bc-empty { min-height: 128px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: rgba(var(--v-theme-on-surface), .5); }
.bc-backup-list { border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.bc-backup-row { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 16px; padding: 12px 4px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.bc-backup-main { min-width: 0; }
.bc-backup-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.bc-backup-meta { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .56); font-size: 12px; }
.bc-row-actions { display: flex; align-items: center; }
.bc-record-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.bc-record-card { min-width: 0; border-radius: 8px; background: transparent; }
.bc-record-title { font-size: 14px; overflow-wrap: anywhere; }
.bc-chip-list { display: flex; flex-wrap: wrap; gap: 5px; }
.bc-record-facts { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 14px; color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; }
.bc-backup-select { max-width: 680px; }
.bc-restore-paths { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.bc-restore-path { display: flex; gap: 12px; padding: 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.bc-restore-icon { width: 42px; height: 42px; flex: 0 0 42px; display: grid; place-items: center; border-radius: 8px; }
.bc-restore-icon--online { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), .12); }
.bc-restore-icon--offline { color: rgb(var(--v-theme-warning)); background: rgba(var(--v-theme-warning), .12); }
.bc-restore-copy { min-width: 0; }
.bc-dialog-card { max-height: min(720px, calc(100dvh - 24px)); border-radius: 8px; }
.bc-dialog-scroll { overflow-y: auto; }
.bc-dialog-subtitle { max-width: min(620px, 62vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bc-restore-actions { min-height: 76px; align-items: center; padding-block: 10px; }
.bc-restore-actions > :deep(.v-btn) { align-self: center; margin-block: 0; }
.bc-restore-submit.v-btn--disabled.v-btn--variant-flat { opacity: 1; color: rgba(var(--v-theme-warning), .72); background: rgba(var(--v-theme-warning), .12); border: 1px solid rgba(var(--v-theme-warning), .38); }
.bc-restore-submit.v-btn--disabled :deep(.v-btn__overlay) { opacity: 0; }
.bc-section-label { margin-bottom: 8px; color: rgba(var(--v-theme-on-surface), .78); font-size: 13px; font-weight: 650; }
.bc-option-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2px 16px; }
.bc-scope-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.bc-scope-group { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.bc-scope-group-title { margin-bottom: 4px; color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.bc-scope-explain { margin: -2px 0 10px; }
.bc-preview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.bc-preview-grid > div { min-width: 0; padding: 10px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.bc-preview-grid span, .bc-preview-grid strong { display: block; overflow-wrap: anywhere; }
.bc-preview-grid span { color: rgba(var(--v-theme-on-surface), .56); font-size: 11px; }
.bc-preview-grid strong { margin-top: 3px; font-size: 13px; }
.bc-guide-dialog { height: min(720px, calc(100dvh - 24px)); display: flex; flex-direction: column; border-radius: 8px; }
.bc-guide-layout { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr); gap: 16px; padding: 16px; overflow: hidden; }
.bc-guide-layout section { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.bc-guide-text { flex: 1 1 auto; min-height: 0; margin: 0; padding: 14px; overflow: auto; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .025); color: inherit; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 760px) {
  :global(.v-overlay__content:has(.bc-page)) { width: calc(100vw - 16px) !important; max-width: calc(100vw - 16px) !important; }
  .bc-page { width: min(100%, calc(100vw - 16px)); height: min(860px, 100dvh); max-height: 100%; }
  .bc-toolbar-subtitle { display: none; }
  .bc-tabs { padding-inline: 8px; }
  .bc-content { padding: 10px 10px 14px; }
  .bc-stat-grid { grid-template-columns: 1fr; gap: 8px; }
  .bc-stat { padding: 10px 12px; }
  .bc-band-heading { align-items: flex-start; }
  .bc-band-heading > :deep(.v-btn) { flex: 0 0 auto; }
  .bc-route-grid, .bc-record-grid, .bc-restore-paths { grid-template-columns: 1fr; }
  .bc-backup-row { grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
  .bc-backup-row > :deep(.v-chip) { grid-column: 1; justify-self: start; }
  .bc-row-actions { grid-column: 2; grid-row: 1 / span 2; }
  .bc-option-grid, .bc-preview-grid, .bc-scope-groups { grid-template-columns: 1fr; }
  .bc-dialog-subtitle { max-width: 58vw; }
  .bc-guide-layout { grid-template-columns: 1fr; overflow-y: auto; }
  .bc-guide-layout section { min-height: 320px; }
}
</style>
