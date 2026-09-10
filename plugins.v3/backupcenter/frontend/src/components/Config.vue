<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi, postPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'BackupCenter' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close'])

const activeMain = ref('overview')
const activeSub = ref('overview')
const secretLoading = ref(false)
const runLoading = ref(false)
const secretConfigured = ref(false)
const passwordVisible = ref(false)
const feedback = reactive({ show: false, message: '', color: 'success' })

const defaultAutoBackupScope = {
  mp_settings: false,
  plugin_settings: true,
  plugin_data: true,
  plugin_files: true,
  app_env: false,
  cookies: false,
}

const form = reactive({
  enabled: true,
  auto_backup_enabled: false,
  auto_backup_cron: '0 3 * * 6',
  retention_count: 5,
  auto_backup_scope: { ...defaultAutoBackupScope },
  password: '',
  passwordConfirm: '',
})

const mainTabs = [
  {
    key: 'overview',
    title: '运行总览',
    icon: 'mdi-view-dashboard-outline',
    desc: '查看自动备份链路和当前策略。',
  },
  {
    key: 'settings',
    title: '插件设置',
    icon: 'mdi-cog-outline',
    desc: '配置每周自动备份与可选加密。',
  },
]

const subTabs = {
  overview: [
    { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  ],
  settings: [
    { key: 'basic', title: '基础设置', icon: 'mdi-timer-cog-outline' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-shield-key-outline' },
  ],
}

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const scheduleText = computed(() => (
  form.auto_backup_cron === '0 3 * * 6'
    ? '每周六 03:00'
    : form.auto_backup_cron || '0 3 * * 6'
))
const encryptionText = computed(() => secretConfigured.value ? 'AES-256-GCM' : '普通 ZIP')
const autoScopeCount = computed(() => Object.values(form.auto_backup_scope).filter(Boolean).length)

function normalizeAutoBackupScope(value) {
  const normalized = { ...defaultAutoBackupScope, ...(value || {}) }
  return Object.fromEntries(Object.keys(defaultAutoBackupScope).map(key => [key, Boolean(normalized[key])]))
}

watch(() => props.initialConfig, value => {
  Object.assign(form, {
    enabled: true,
    auto_backup_enabled: false,
    auto_backup_cron: '0 3 * * 6',
    retention_count: 5,
  }, value || {})
  form.auto_backup_scope = normalizeAutoBackupScope(value?.auto_backup_scope)
  if (!value?.auto_backup_cron && /^([01]\d|2[0-3]):[0-5]\d$/.test(value?.auto_backup_time || '')) {
    const [hour, minute] = value.auto_backup_time.split(':')
    form.auto_backup_cron = `${Number(minute)} ${Number(hour)} * * 6`
  }
  form.password = ''
  form.passwordConfirm = ''
  secretConfigured.value = Boolean(value?.encryption_configured)
}, { immediate: true, deep: true })

function notify(message, color = 'success') {
  feedback.show = true
  feedback.message = message
  feedback.color = color
}

function selectMain(key) {
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || 'overview'
}

async function loadSecretStatus() {
  try {
    const result = await getPluginApi(props.api, props.pluginId, 'encryption/status')
    secretConfigured.value = Boolean(result?.configured)
  } catch (error) {
    notify(error.message || '口令状态读取失败', 'error')
  }
}

async function updatePassword() {
  if (form.password.length < 4) {
    notify('备份口令至少需要 4 个字符，建议使用更长口令', 'warning')
    return
  }
  if (form.password !== form.passwordConfirm) {
    notify('两次输入的备份口令不一致', 'warning')
    return
  }
  secretLoading.value = true
  try {
    const result = await postPluginApi(props.api, props.pluginId, 'encryption/secret', {
      action: 'set',
      password: form.password,
    })
    secretConfigured.value = Boolean(result?.configured)
    form.password = ''
    form.passwordConfirm = ''
    notify('备份口令已密文保存')
  } catch (error) {
    notify(error.message || '备份口令保存失败', 'error')
  } finally {
    secretLoading.value = false
  }
}

async function clearPassword() {
  secretLoading.value = true
  try {
    const result = await postPluginApi(props.api, props.pluginId, 'encryption/secret', { action: 'clear' })
    secretConfigured.value = Boolean(result?.configured)
    form.password = ''
    form.passwordConfirm = ''
    notify('备份口令已清除', 'warning')
  } catch (error) {
    notify(error.message || '备份口令清除失败', 'error')
  } finally {
    secretLoading.value = false
  }
}

async function runAutomaticBackup() {
  if (runLoading.value) return
  runLoading.value = true
  try {
    const result = await postPluginApi(props.api, props.pluginId, 'run')
    const backup = result?.backup || {}
    const label = backup.display_name || backup.backup_id || '自动备份'
    notify(`已完成：${label}`)
  } catch (error) {
    notify(error.message || '立即备份失败', 'error')
  } finally {
    runLoading.value = false
  }
}

function save() {
  if (!autoScopeCount.value) {
    notify('周期备份范围至少选择一项', 'warning')
    return
  }
  emit('save', {
    enabled: Boolean(form.enabled),
    auto_backup_enabled: Boolean(form.auto_backup_enabled),
    auto_backup_cron: String(form.auto_backup_cron || '0 3 * * 6'),
    retention_count: Number(form.retention_count || 5),
    auto_backup_scope: { ...form.auto_backup_scope },
  })
}

onMounted(loadSecretStatus)
</script>

<template>
  <div class="bc-config">
    <VCard flat class="bc-card">
      <VCardItem class="bc-header">
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="46" rounded="lg">
            <VIcon :icon="currentMain.icon" size="26" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">备份中心</VCardTitle>
        <VCardSubtitle class="text-caption">{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch
            v-model="form.enabled"
            class="bc-header-switch"
            color="success"
            hide-details
            inset
            :label="form.enabled ? '已启用' : '已停用'"
          />
        </template>
      </VCardItem>

      <VDivider />

      <div class="bc-body">
        <nav class="bc-nav">
          <VList density="comfortable" nav class="bc-nav-list py-2">
            <VListItem
              v-for="item in mainTabs"
              :key="item.key"
              :active="activeMain === item.key"
              color="primary"
              rounded="lg"
              class="bc-nav-item"
              @click="selectMain(item.key)"
            >
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>

        <section class="bc-content">
          <div class="bc-subtabs">
            <button
              v-for="sub in currentSubs"
              :key="sub.key"
              type="button"
              class="bc-subtab"
              :class="{ 'bc-subtab--active': activeSub === sub.key }"
              @click="activeSub = sub.key"
            >
              <VIcon :icon="sub.icon" size="18" class="mr-1" />
              {{ sub.title }}
            </button>
          </div>

          <VDivider />

          <div class="bc-window" :class="{ 'bc-window--overview': activeMain === 'overview' }">
            <div v-show="activeMain === 'overview'" class="bc-pane bc-pane--overview">
              <div class="bc-section-title">运行链路</div>
              <div class="bc-pipeline">
                <div class="bc-pipeline-item">
                  <VIcon icon="mdi-calendar-clock-outline" color="primary" />
                  <div>
                    <div class="bc-item-title">定时触发</div>
                    <div class="bc-hint">{{ scheduleText }}</div>
                  </div>
                </div>
                <div class="bc-pipeline-item">
                  <VIcon icon="mdi-archive-arrow-down-outline" color="primary" />
                  <div>
                    <div class="bc-item-title">收集数据</div>
                    <div class="bc-hint">配置和数据</div>
                  </div>
                </div>
                <div class="bc-pipeline-item">
                  <VIcon icon="mdi-shield-lock-outline" color="primary" />
                  <div>
                    <div class="bc-item-title">生成备份</div>
                    <div class="bc-hint">{{ encryptionText }}</div>
                  </div>
                </div>
                <div class="bc-pipeline-item">
                  <VIcon icon="mdi-delete-clock-outline" color="primary" />
                  <div>
                    <div class="bc-item-title">轮换归档</div>
                    <div class="bc-hint">保留 {{ form.retention_count || 5 }} 份自动备份</div>
                  </div>
                </div>
              </div>

              <div class="bc-section-title bc-section-title--status">当前状态</div>
              <div class="bc-status-grid">
                <div class="bc-status-row">
                  <span>插件状态</span>
                  <VChip size="small" :color="form.enabled ? 'success' : 'default'" variant="tonal">
                    {{ form.enabled ? '已启用' : '已停用' }}
                  </VChip>
                </div>
                <div class="bc-status-row">
                  <span>自动备份</span>
                  <VChip size="small" :color="form.auto_backup_enabled ? 'success' : 'default'" variant="tonal">
                    {{ form.auto_backup_enabled ? '已开启' : '已关闭' }}
                  </VChip>
                </div>
                <div class="bc-status-row">
                  <span>备份加密</span>
                  <VChip size="small" :color="secretConfigured ? 'success' : 'default'" variant="tonal">
                    {{ secretConfigured ? '已设置' : '未设置' }}
                  </VChip>
                </div>
                <div class="bc-status-row">
                  <span>手动操作</span>
                  <span class="bc-status-value">插件详情页</span>
                </div>
              </div>
            </div>

            <div v-show="activeMain === 'settings' && activeSub === 'basic'" class="bc-pane">
              <div class="bc-section-title">基础设置</div>
              <div class="bc-form-grid bc-form-grid--schedule">
                <div class="bc-form-span">
                  <VSwitch
                    v-model="form.auto_backup_enabled"
                    color="success"
                    label="启用自动备份"
                    hide-details
                    inset
                  />
                </div>
                <div>
                  <VCronField
                    v-model="form.auto_backup_cron"
                    label="运行周期"
                    density="compact"
                    variant="outlined"
                    hide-details
                    :disabled="!form.auto_backup_enabled"
                  />
                </div>
                <div>
                  <VTextField
                    v-model.number="form.retention_count"
                    label="保留数量"
                    type="number"
                    min="1"
                    max="200"
                    hint="只清理最旧的自动备份"
                    persistent-hint
                    density="compact"
                    variant="outlined"
                  />
                </div>
                <div class="bc-form-span bc-run-row">
                  <VBtn
                    color="primary"
                    variant="tonal"
                    prepend-icon="mdi-play-circle-outline"
                    :loading="runLoading"
                    :disabled="runLoading"
                    @click="runAutomaticBackup"
                  >
                    立即运行一次
                  </VBtn>
                  <span class="bc-hint">按当前周期备份范围立即生成一份自动备份。</span>
                </div>
                <div class="bc-form-span bc-scope-summary">
                  <div class="bc-section-heading">
                    <div>
                      <div class="bc-section-title">周期备份范围 · 已选 {{ autoScopeCount }} 项</div>
                      <div class="bc-hint">这里只影响每周自动备份；详情页的手动备份范围单独选择。</div>
                    </div>
                    <VChip size="small" variant="tonal">按配置执行</VChip>
                  </div>
                  <div class="bc-scope-groups mt-3">
                    <section class="bc-scope-group">
                      <div class="bc-scope-group-title">配置</div>
                      <VCheckbox v-model="form.auto_backup_scope.mp_settings" label="MoviePilot 设置" density="compact" hide-details />
                      <VCheckbox v-model="form.auto_backup_scope.app_env" label="环境变量（app.env）" density="compact" hide-details />
                      <VCheckbox v-model="form.auto_backup_scope.plugin_settings" label="插件设置" density="compact" hide-details />
                      <VCheckbox v-model="form.auto_backup_scope.cookies" label="登录 Cookie" density="compact" hide-details />
                    </section>
                    <section class="bc-scope-group">
                      <div class="bc-scope-group-title">数据</div>
                      <VCheckbox v-model="form.auto_backup_scope.plugin_data" label="插件保存的数据（PluginData）" density="compact" hide-details />
                      <VCheckbox v-model="form.auto_backup_scope.plugin_files" label="插件文件和缓存" density="compact" hide-details />
                    </section>
                  </div>
                  <VAlert type="info" variant="tonal" density="compact" class="mt-3">
                    数据库备份由 MoviePilot 主程序统一管理，插件只负责插件设置、数据与标准目录。
                  </VAlert>
                </div>
              </div>
            </div>

            <div v-show="activeMain === 'settings' && activeSub === 'advanced'" class="bc-pane">
              <div class="bc-section-heading">
                <div>
                  <div class="bc-section-title mb-1">备份加密</div>
                  <div class="bc-hint">最低 4 位，建议使用更长口令；不设置口令时生成普通 ZIP。</div>
                  <div class="bc-hint">口令单独密文保存，不进入普通插件配置。</div>
                </div>
                <VChip size="small" :color="secretConfigured ? 'success' : 'default'" variant="tonal">
                  {{ secretConfigured ? '已设置' : '未设置' }}
                </VChip>
              </div>

              <div class="bc-form-grid bc-form-grid--secret mt-4">
                <div>
                  <VTextField
                    v-model="form.password"
                    label="备份口令"
                    :type="passwordVisible ? 'text' : 'password'"
                    :append-inner-icon="passwordVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autocomplete="new-password"
                    @click:append-inner="passwordVisible = !passwordVisible"
                  />
                </div>
                <div>
                  <VTextField
                    v-model="form.passwordConfirm"
                    label="确认口令"
                    :type="passwordVisible ? 'text' : 'password'"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autocomplete="new-password"
                  />
                </div>
              </div>

              <div class="bc-secret-actions">
                <VBtn
                  v-if="secretConfigured"
                  color="error"
                  variant="text"
                  prepend-icon="mdi-key-remove"
                  :loading="secretLoading"
                  @click="clearPassword"
                >
                  清除口令
                </VBtn>
                <VBtn
                  color="primary"
                  variant="tonal"
                  prepend-icon="mdi-key-change"
                  :loading="secretLoading"
                  @click="updatePassword"
                >
                  {{ secretConfigured ? '更新口令' : '设置口令' }}
                </VBtn>
              </div>
            </div>
          </div>
        </section>
      </div>

      <VDivider />
      <VCardActions class="bc-actions">
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="save">
          保存配置
        </VBtn>
      </VCardActions>
    </VCard>

    <VSnackbar v-model="feedback.show" :color="feedback.color" timeout="5000">
      {{ feedback.message }}
    </VSnackbar>
  </div>
</template>

<style scoped>
.bc-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.bc-card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 14px; }
.bc-header { padding: 14px 18px; }
.bc-header :deep(.v-card-subtitle) { max-width: min(560px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bc-body { flex: 1 1 auto; min-height: 0; display: flex; }
.bc-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.bc-nav-list { width: 100%; }
.bc-nav-item { margin: 2px 8px; }
.bc-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.bc-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.bc-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border: none; border-radius: 8px; color: rgba(var(--v-theme-on-surface), .7); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: background .15s, color .15s; }
.bc-subtab:hover { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .08); }
.bc-subtab--active { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); font-weight: 600; }
.bc-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.bc-window--overview { overflow-y: hidden; }
.bc-pane { min-height: 100%; padding: 18px 20px; }
.bc-pane--overview { padding: 12px 16px; }
.bc-section-title { color: rgb(var(--v-theme-primary)); font-size: 14px; font-weight: 600; }
.bc-section-title--status { margin-top: 18px; }
.bc-pipeline { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 8px; }
.bc-pipeline-item { display: flex; min-width: 0; align-items: flex-start; gap: 10px; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); }
.bc-item-title { margin-bottom: 2px; font-size: 13px; font-weight: 600; }
.bc-hint { color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.bc-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; margin-top: 8px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.bc-status-row { display: flex; min-width: 0; min-height: 48px; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); font-size: 13px; }
.bc-status-value { color: rgba(var(--v-theme-on-surface), .7); white-space: nowrap; }
.bc-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.bc-form-grid { display: grid; align-items: start; gap: 18px; margin-top: 12px; }
.bc-form-grid--schedule { grid-template-columns: minmax(0, 2fr) minmax(120px, 1fr); }
.bc-form-grid--secret { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.bc-form-span { grid-column: 1 / -1; }
.bc-run-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.bc-scope-summary { padding-top: 14px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.bc-scope-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.bc-scope-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.bc-scope-group { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.bc-scope-group-title { margin-bottom: 4px; color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.bc-secret-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.bc-actions { padding: 10px 18px; }

@media (max-width: 760px) {
  .bc-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .bc-card { height: min(860px, calc(100dvh - 16px)); }
  .bc-header :deep(.v-card-subtitle) { display: none; }
  .bc-header-switch :deep(.v-label) { display: none; }
  .bc-body { flex-direction: column; }
  .bc-nav { width: 100%; flex: 0 0 auto; overflow-x: auto; overflow-y: hidden; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); scrollbar-width: none; }
  .bc-nav::-webkit-scrollbar { display: none; }
  .bc-nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .bc-nav-item { flex: 0 0 auto; min-width: 112px; margin: 0; padding-inline: 10px; }
  .bc-nav-item :deep(.v-list-item-title) { white-space: nowrap; }
  .bc-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; padding: 6px 12px; scrollbar-width: none; }
  .bc-subtabs::-webkit-scrollbar { display: none; }
  .bc-subtab { flex: 0 0 auto; padding: 6px 12px; }
  .bc-window--overview { overflow-y: auto; }
  .bc-pane, .bc-pane--overview { padding: 14px 12px; }
  .bc-pipeline, .bc-status-grid { grid-template-columns: 1fr; }
  .bc-form-grid--schedule, .bc-form-grid--secret { grid-template-columns: minmax(0, 1fr); }
  .bc-scope-groups { grid-template-columns: minmax(0, 1fr); }
}

@media (max-height: 760px) {
  .bc-window--overview { overflow-y: auto; }
}
</style>
