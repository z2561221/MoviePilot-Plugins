import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as getPluginApi, d as downloadBackup, p as postPluginApi } from './_plugin-vue_export-helper-DZv_LBIW.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = {
  class: "bc-tabs",
  role: "tablist",
  "aria-label": "备份中心视图"
};
const _hoisted_2 = ["onClick"];
const _hoisted_3 = { class: "bc-content" };
const _hoisted_4 = {
  key: 0,
  class: "bc-state"
};
const _hoisted_5 = { class: "bc-stat-grid" };
const _hoisted_6 = { class: "bc-stat" };
const _hoisted_7 = { class: "bc-stat" };
const _hoisted_8 = { class: "bc-stat" };
const _hoisted_9 = { class: "bc-band" };
const _hoisted_10 = { class: "bc-band-heading" };
const _hoisted_11 = { class: "bc-route-grid" };
const _hoisted_12 = { class: "bc-route" };
const _hoisted_13 = { class: "bc-route" };
const _hoisted_14 = { class: "bc-band" };
const _hoisted_15 = { class: "bc-band-heading" };
const _hoisted_16 = {
  key: 0,
  class: "bc-empty"
};
const _hoisted_17 = {
  key: 1,
  class: "bc-backup-list"
};
const _hoisted_18 = { class: "bc-backup-main" };
const _hoisted_19 = { class: "bc-backup-title" };
const _hoisted_20 = { class: "bc-backup-meta" };
const _hoisted_21 = { class: "bc-row-actions" };
const _hoisted_22 = {
  key: 2,
  class: "bc-band bc-band--top"
};
const _hoisted_23 = { class: "bc-band-heading" };
const _hoisted_24 = {
  key: 0,
  class: "bc-empty"
};
const _hoisted_25 = {
  key: 1,
  class: "bc-record-grid"
};
const _hoisted_26 = { class: "bc-chip-list" };
const _hoisted_27 = { class: "bc-record-facts" };
const _hoisted_28 = {
  key: 3,
  class: "bc-band bc-band--top"
};
const _hoisted_29 = {
  key: 0,
  class: "bc-restore-paths"
};
const _hoisted_30 = { class: "bc-restore-path" };
const _hoisted_31 = { class: "bc-restore-icon bc-restore-icon--online" };
const _hoisted_32 = { class: "bc-restore-copy" };
const _hoisted_33 = { class: "bc-restore-path" };
const _hoisted_34 = { class: "bc-restore-icon bc-restore-icon--offline" };
const _hoisted_35 = { class: "bc-restore-copy" };
const _hoisted_36 = { class: "d-flex flex-wrap ga-2 mt-3" };
const _hoisted_37 = {
  key: 1,
  class: "bc-empty"
};
const _hoisted_38 = {
  key: 4,
  class: "bc-band bc-band--top"
};
const _hoisted_39 = { class: "bc-band-heading" };
const _hoisted_40 = {
  key: 0,
  class: "bc-empty"
};
const _hoisted_41 = {
  key: 1,
  class: "bc-log-list"
};
const _hoisted_42 = { class: "bc-log-main" };
const _hoisted_43 = { class: "bc-log-heading" };
const _hoisted_44 = { class: "bc-log-message" };
const _hoisted_45 = { class: "bc-log-meta" };
const _hoisted_46 = {
  key: 0,
  class: "bc-log-backup-id"
};
const _hoisted_47 = { class: "bc-section-label" };
const _hoisted_48 = {
  key: 1,
  class: "bc-scope-groups"
};
const _hoisted_49 = { class: "bc-scope-group" };
const _hoisted_50 = { class: "bc-scope-group" };
const _hoisted_51 = {
  key: 2,
  class: "bc-scope-groups"
};
const _hoisted_52 = { class: "bc-scope-group" };
const _hoisted_53 = { class: "bc-scope-group" };
const _hoisted_54 = { class: "bc-preview-grid" };
const _hoisted_55 = { class: "bc-section-label mt-5" };
const _hoisted_56 = { class: "bc-scope-groups" };
const _hoisted_57 = { class: "bc-scope-group" };
const _hoisted_58 = { class: "bc-scope-group" };
const _hoisted_59 = { class: "bc-guide-layout" };
const _hoisted_60 = { class: "bc-guide-text" };
const _hoisted_61 = { class: "bc-guide-text" };

const {computed,onBeforeUnmount,onMounted,reactive,ref} = await importShared('vue');

const pageOverlayClass = 'bc-page-overlay';


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  showClose: { type: Boolean, default: true },
  showSettings: { type: Boolean, default: false },
  show_switch: { type: Boolean, default: false },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const activeTab = ref('overview');
const loading = ref(false);
const logsLoading = ref(false);
const actionLoading = ref('');
const overview = ref({ backups: [], installed_plugin_ids: [], plugin_options: [] });
const logs = ref([]);
const selectedBackupId = ref('');
const preview = ref(null);
const guide = ref(null);
const createDialog = ref(false);
const restoreDialog = ref(false);
const guideDialog = ref(false);
const feedback = reactive({ show: false, message: '', color: 'success' });
const createForm = reactive({
  target: 'plugin',
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
  },
});
const restoreForm = reactive({
  password: '',
  pluginIds: [],
  selection: {
    mpSettings: false,
    pluginSettings: false,
    pluginData: false,
  },
});
const pageRoot = ref(null);
let pageOverlay = null;
const tabs = [
  { key: 'overview', title: '备份总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'backups', title: '备份记录', icon: 'mdi-archive-outline' },
  { key: 'restore', title: '恢复中心', icon: 'mdi-database-arrow-left-outline' },
  { key: 'logs', title: '运行日志', icon: 'mdi-text-box-search-outline' },
];
const settingsShortcutVisible = computed(() => props.showSettings || props.show_switch);
const backups = computed(() => overview.value?.backups || []);
const backupOptions = computed(() => backups.value.map(item => ({
  title: backupOptionTitle(item),
  value: item.backup_id,
})));
const selectedBackup = computed(() => (
  backups.value.find(item => item.backup_id === selectedBackupId.value) || null
));
const selectedBackupLabel = computed(() => (
  selectedBackup.value ? backupDisplayName(selectedBackup.value) : selectedBackupId.value
));
const createPluginOptions = computed(() => {
  const options = overview.value?.plugin_options || [];
  if (options.length) return options
  return (overview.value?.installed_plugin_ids || []).map(value => ({ title: value, value }))
});
const pluginTitleById = computed(() => new Map(
  createPluginOptions.value.map(item => [item.value, item.title]),
));
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
));
const createSelection = computed(() => (
  createForm.target === 'plugin' ? createForm.pluginSelection : createForm.moviepilotSelection
));
const createScopeCount = computed(() => Object.values(createSelection.value).filter(Boolean).length);
const createReady = computed(() => (
  createScopeCount.value > 0
  && (createForm.target === 'moviepilot' || Boolean(createForm.pluginId))
));
const restoreScopeCount = computed(() => Object.values(restoreForm.selection).filter(Boolean).length);
const restoreNeedsPlugins = computed(() => (
  restoreForm.selection.pluginSettings || restoreForm.selection.pluginData
));
const restoreAvailable = computed(() => {
  const scope = preview.value?.manifest?.scope || {};
  return {
    mpSettings: Boolean(scope.mp_settings),
    pluginSettings: Boolean(scope.plugin_settings),
    pluginData: Boolean(scope.plugin_data || scope.plugin_files),
  }
});
const restoreReady = computed(() => (
  Boolean(preview.value?.online_restore_allowed)
  && restoreScopeCount.value > 0
  && (!restoreNeedsPlugins.value || restoreForm.pluginIds.length > 0)
));

function notify(message, color = 'success') {
  feedback.show = true;
  feedback.message = message;
  feedback.color = color;
}

function formatDate(value) {
  if (!value) return '未知时间'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN')
}

function formatSize(bytes) {
  const size = Number(bytes || 0);
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatDuration(milliseconds) {
  const duration = Number(milliseconds || 0);
  if (duration < 1000) return `${duration} ms`
  if (duration < 60000) return `${(duration / 1000).toFixed(1)} 秒`
  return `${(duration / 60000).toFixed(1)} 分钟`
}

function operationLabel(operation) {
  return {
    automatic_backup: '自动备份',
    manual_backup: '手动备份',
    verify_backup: '备份校验',
    delete_backup: '删除备份',
    restore_logical: '在线恢复',
  }[operation] || '备份中心操作'
}

function backupKindLabel(kind) {
  return {
    automatic: '自动备份',
    emergency: '恢复前应急备份',
    manual: '手动备份',
  }[kind] || '备份'
}

function backupDisplayName(item = {}) {
  const explicitName = String(item.display_name || '').trim();
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
  };
  return Object.entries(scope).filter(([, enabled]) => enabled).map(([key]) => labels[key])
}

async function loadOverview() {
  loading.value = true;
  try {
    overview.value = await getPluginApi(props.api, 'overview') || {};
    if (!selectedBackupId.value && backups.value.length) {
      selectedBackupId.value = backups.value[0].backup_id;
    }
  } catch (error) {
    notify(error.message || '备份概览加载失败', 'error');
  } finally {
    loading.value = false;
  }
}

async function loadLogs({ silent = false } = {}) {
  logsLoading.value = true;
  try {
    const result = await getPluginApi(props.api, 'logs') || {};
    logs.value = Array.isArray(result.logs) ? result.logs : [];
  } catch (error) {
    if (!silent) notify(error.message || '运行日志加载失败', 'error');
  } finally {
    logsLoading.value = false;
  }
}

async function refreshAll() {
  await Promise.all([loadOverview(), loadLogs()]);
}

function openCreate() {
  createForm.target = 'plugin';
  createForm.pluginId = '';
  Object.keys(createForm.pluginSelection).forEach(key => { createForm.pluginSelection[key] = false; });
  Object.keys(createForm.moviepilotSelection).forEach(key => { createForm.moviepilotSelection[key] = false; });
  createDialog.value = true;
}

async function createBackup() {
  if (!createScopeCount.value) {
    notify(createForm.target === 'plugin' ? '至少选择配置或数据中的一项' : '至少选择一项备份内容', 'warning');
    return
  }
  if (createForm.target === 'plugin' && !createForm.pluginId) {
    notify('请选择一个插件', 'warning');
    return
  }
  actionLoading.value = 'create';
  try {
    const result = await postPluginApi(props.api, 'backups', {
      target: createForm.target,
      plugin_ids: createForm.target === 'plugin' ? [createForm.pluginId] : [],
      selection: { ...createSelection.value },
    });
    createDialog.value = false;
    selectedBackupId.value = result.backup_id;
    notify(result.encrypted ? '加密备份已创建，可校验并下载' : '未加密备份已创建，可校验并下载');
    await loadOverview();
  } catch (error) {
    notify(error.message || '创建备份失败', 'error');
  } finally {
    actionLoading.value = '';
    await loadLogs({ silent: true });
  }
}

async function verifyBackup(backupId) {
  actionLoading.value = `verify:${backupId}`;
  try {
    const result = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/verify`);
    notify(`校验通过，共验证 ${result.verified_files?.length || 0} 个文件`);
  } catch (error) {
    notify(error.message || '备份校验失败', 'error');
  } finally {
    actionLoading.value = '';
    await loadLogs({ silent: true });
  }
}

async function deleteBackup(backupId) {
  const item = backups.value.find(backup => backup.backup_id === backupId);
  if (!window.confirm(`确认删除“${backupDisplayName(item)}”？此操作不可撤销。`)) return
  actionLoading.value = `delete:${backupId}`;
  try {
    await postPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/delete`);
    if (selectedBackupId.value === backupId) selectedBackupId.value = '';
    notify('备份已删除');
    await loadOverview();
  } catch (error) {
    notify(error.message || '备份删除失败', 'error');
  } finally {
    actionLoading.value = '';
    await loadLogs({ silent: true });
  }
}

async function exportBackup(backupId) {
  actionLoading.value = `export:${backupId}`;
  try {
    const item = backups.value.find(backup => backup.backup_id === backupId);
    await downloadBackup(
      props.api,
      encodeURIComponent(backupId),
      backupDownloadName(item || { backup_id: backupId }),
    );
    notify('备份包下载已开始');
  } catch (error) {
    notify(error.message || '备份包下载失败', 'error');
  } finally {
    actionLoading.value = '';
  }
}

async function showGuide(backupId) {
  actionLoading.value = `guide:${backupId}`;
  try {
    guide.value = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/guide`);
    selectedBackupId.value = backupId;
    guideDialog.value = true;
  } catch (error) {
    notify(error.message || '恢复教程读取失败', 'error');
  } finally {
    actionLoading.value = '';
  }
}

async function prepareRestore(backupId) {
  selectedBackupId.value = backupId;
  actionLoading.value = `preview:${backupId}`;
  try {
    preview.value = await getPluginApi(props.api, `backups/${encodeURIComponent(backupId)}/preview`);
    restoreForm.password = '';
    restoreForm.pluginIds = [];
    Object.keys(restoreForm.selection).forEach(key => { restoreForm.selection[key] = false; });
    restoreDialog.value = true;
  } catch (error) {
    notify(error.message || '恢复预检失败', 'error');
  } finally {
    actionLoading.value = '';
  }
}

async function restoreLogical() {
  if (!preview.value?.online_restore_allowed) {
    notify('源与目标 MoviePilot 主版本不一致，在线恢复已阻断', 'error');
    return
  }
  if (!restoreScopeCount.value) {
    notify('至少选择一项在线恢复内容', 'warning');
    return
  }
  actionLoading.value = 'restore';
  try {
    const scope = preview.value?.manifest?.scope || {};
    const hasPluginSelection = restoreForm.pluginIds.length > 0;
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
    });
    restoreDialog.value = false;
    const reloaded = result.reloaded?.length
      ? `；已重载：${result.reloaded.join('、')}`
      : '';
    const reload = result.reload_required?.length
      ? `；重载失败，请检查：${result.reload_required.join('、')}`
      : '';
    const hostBackup = result.host_database_backup_name
      ? `；宿主恢复点：${result.host_database_backup_name}`
      : '';
    notify(
      `选择性恢复完成，应急备份 ${result.emergency_backup_id}${hostBackup}${reloaded}${reload}`,
      result.reload_required?.length ? 'warning' : 'success',
    );
    await loadOverview();
  } catch (error) {
    notify(error.message || '选择性恢复失败', 'error');
  } finally {
    actionLoading.value = '';
    await loadLogs({ silent: true });
  }
}

function attachPageOverlay() {
  pageOverlay = pageRoot.value?.closest('.v-overlay__content') || null;
  pageOverlay?.classList.add(pageOverlayClass);
}

function detachPageOverlay() {
  pageOverlay?.classList.remove(pageOverlayClass);
  pageOverlay = null;
}

onMounted(() => {
  attachPageOverlay();
  refreshAll();
});

onBeforeUnmount(detachPageOverlay);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtnToggle = _resolveComponent("VBtnToggle");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", {
    ref_key: "pageRoot",
    ref: pageRoot,
    class: "bc-page"
  }, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "bc-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-shield-sync-outline",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[34] || (_cache[34] = _createElementVNode("div", { class: "bc-toolbar-copy" }, [
          _createElementVNode("div", { class: "text-h6" }, "备份中心"),
          _createElementVNode("div", { class: "text-caption text-medium-emphasis bc-toolbar-subtitle" }, " 插件配置数据保护与宿主数据库恢复点 ")
        ], -1)),
        _createVNode(_component_VSpacer),
        (settingsShortcutVisible.value)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 0,
              icon: "mdi-cog-outline",
              variant: "text",
              "aria-label": "打开配置",
              onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VTooltip, { activator: "parent" }, {
                  default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                    _createTextVNode("打开配置", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          "aria-label": "刷新",
          loading: loading.value || logsLoading.value,
          onClick: refreshAll
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTooltip, { activator: "parent" }, {
              default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode("刷新", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["loading"]),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 1,
              icon: "mdi-close",
              variant: "text",
              "aria-label": "关闭",
              onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VTooltip, { activator: "parent" }, {
                  default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode("", true)
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_1, [
      (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
        return _createElementVNode("button", {
          key: tab.key,
          type: "button",
          class: _normalizeClass(["bc-tab", { 'bc-tab--active': activeTab.value === tab.key }]),
          onClick: $event => (activeTab.value = tab.key)
        }, [
          _createVNode(_component_VIcon, {
            icon: tab.icon,
            size: "18"
          }, null, 8, ["icon"]),
          _createElementVNode("span", null, _toDisplayString(tab.title), 1)
        ], 10, _hoisted_2)
      }), 64))
    ]),
    _createVNode(_component_VDivider),
    _createElementVNode("main", _hoisted_3, [
      ((activeTab.value !== 'logs' && loading.value && !backups.value.length) || (activeTab.value === 'logs' && logsLoading.value && !logs.value.length))
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
            _createVNode(_component_VProgressCircular, {
              indeterminate: "",
              color: "primary"
            })
          ]))
        : (activeTab.value === 'overview')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              _createElementVNode("section", _hoisted_5, [
                _createElementVNode("div", _hoisted_6, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-archive-check-outline",
                    color: "primary",
                    size: "24"
                  }),
                  _createElementVNode("div", null, [
                    _createElementVNode("strong", null, _toDisplayString(overview.value.backup_count || 0), 1),
                    _cache[35] || (_cache[35] = _createElementVNode("span", null, "本地备份", -1))
                  ])
                ]),
                _createElementVNode("div", _hoisted_7, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-database-check-outline",
                    color: "info",
                    size: "24"
                  }),
                  _cache[36] || (_cache[36] = _createElementVNode("div", null, [
                    _createElementVNode("strong", null, "主程序托管"),
                    _createElementVNode("span", null, "数据库恢复")
                  ], -1))
                ]),
                _createElementVNode("div", _hoisted_8, [
                  _createVNode(_component_VIcon, {
                    icon: overview.value.encryption_active ? 'mdi-lock-check-outline' : 'mdi-lock-open-outline',
                    color: overview.value.encryption_active ? 'success' : 'warning',
                    size: "24"
                  }, null, 8, ["icon", "color"]),
                  _createElementVNode("div", null, [
                    _createElementVNode("strong", null, _toDisplayString(overview.value.encryption_active ? '已加密' : '未加密'), 1),
                    _cache[37] || (_cache[37] = _createElementVNode("span", null, "新建备份格式", -1))
                  ])
                ])
              ]),
              _createElementVNode("section", _hoisted_9, [
                _createElementVNode("div", _hoisted_10, [
                  _cache[39] || (_cache[39] = _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "恢复路径"),
                    _createElementVNode("div", { class: "bc-muted" }, "不同数据按风险进入独立恢复路径。")
                  ], -1)),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    "prepend-icon": "mdi-plus",
                    onClick: openCreate
                  }, {
                    default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                      _createTextVNode(" 新建备份 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _createElementVNode("div", _hoisted_11, [
                  _createElementVNode("div", _hoisted_12, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-cloud-sync-outline",
                      color: "success",
                      size: "26"
                    }),
                    _cache[40] || (_cache[40] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "bc-route-title" }, "在线选择性恢复"),
                      _createElementVNode("div", { class: "bc-muted" }, "配置和数据。恢复前自动创建应急备份。")
                    ], -1))
                  ]),
                  _createElementVNode("div", _hoisted_13, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-database-check-outline",
                      color: "info",
                      size: "26"
                    }),
                    _cache[41] || (_cache[41] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "bc-route-title" }, "宿主数据库恢复点"),
                      _createElementVNode("div", { class: "bc-muted" }, "在线恢复前自动创建；整库回退请使用 MoviePilot 主程序命令。")
                    ], -1))
                  ])
                ])
              ]),
              _createElementVNode("section", _hoisted_14, [
                _createElementVNode("div", _hoisted_15, [
                  _cache[43] || (_cache[43] = _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "最近备份"),
                    _createElementVNode("div", { class: "bc-muted" }, "先校验，再下载或进入恢复预检。")
                  ], -1)),
                  _createVNode(_component_VBtn, {
                    variant: "text",
                    "append-icon": "mdi-arrow-right",
                    onClick: _cache[2] || (_cache[2] = $event => (activeTab.value = 'backups'))
                  }, {
                    default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                      _createTextVNode("全部记录", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                (!backups.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_16, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-archive-off-outline",
                        size: "34"
                      }),
                      _cache[44] || (_cache[44] = _createElementVNode("span", null, "尚无备份记录", -1))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_17, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(backups.value.slice(0, 3), (item) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: item.backup_id,
                          class: "bc-backup-row"
                        }, [
                          _createElementVNode("div", _hoisted_18, [
                            _createElementVNode("div", _hoisted_19, _toDisplayString(backupDisplayName(item)), 1),
                            _createElementVNode("div", _hoisted_20, _toDisplayString(formatSize(item.package_size)) + " · " + _toDisplayString(item.backup_id), 1)
                          ]),
                          _createVNode(_component_VChip, {
                            size: "small",
                            color: "success",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                              _createTextVNode("逻辑备份", -1)
                            ]))]),
                            _: 1
                          }),
                          _createElementVNode("div", _hoisted_21, [
                            _createVNode(_component_VBtn, {
                              icon: "mdi-check-decagram-outline",
                              size: "small",
                              variant: "text",
                              loading: actionLoading.value === `verify:${item.backup_id}`,
                              onClick: $event => (verifyBackup(item.backup_id))
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTooltip, { activator: "parent" }, {
                                  default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
                                    _createTextVNode("校验", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }, 8, ["loading", "onClick"]),
                            _createVNode(_component_VBtn, {
                              icon: "mdi-download-outline",
                              size: "small",
                              variant: "text",
                              loading: actionLoading.value === `export:${item.backup_id}`,
                              onClick: $event => (exportBackup(item.backup_id))
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTooltip, { activator: "parent" }, {
                                  default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                                    _createTextVNode("下载备份包", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }, 8, ["loading", "onClick"]),
                            _createVNode(_component_VBtn, {
                              icon: "mdi-database-arrow-left-outline",
                              size: "small",
                              variant: "text",
                              onClick: $event => (prepareRestore(item.backup_id))
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTooltip, { activator: "parent" }, {
                                  default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                                    _createTextVNode("恢复预检", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }, 8, ["onClick"]),
                            _createVNode(_component_VBtn, {
                              icon: "mdi-delete-outline",
                              size: "small",
                              variant: "text",
                              color: "error",
                              loading: actionLoading.value === `delete:${item.backup_id}`,
                              onClick: $event => (deleteBackup(item.backup_id))
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTooltip, { activator: "parent" }, {
                                  default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                                    _createTextVNode("删除备份", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ])
                        ]))
                      }), 128))
                    ]))
              ])
            ], 64))
          : (activeTab.value === 'backups')
            ? (_openBlock(), _createElementBlock("section", _hoisted_22, [
                _createElementVNode("div", _hoisted_23, [
                  _cache[51] || (_cache[51] = _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "备份记录"),
                    _createElementVNode("div", { class: "bc-muted" }, "每个备份包都包含明文教程、校验清单、校验工具，以及普通 ZIP 或加密负载。")
                  ], -1)),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    "prepend-icon": "mdi-plus",
                    onClick: openCreate
                  }, {
                    default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                      _createTextVNode("新建备份", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                (!backups.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_24, "暂无备份记录"))
                  : (_openBlock(), _createElementBlock("div", _hoisted_25, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(backups.value, (item) => {
                        return (_openBlock(), _createBlock(_component_VCard, {
                          key: item.backup_id,
                          variant: "outlined",
                          class: "bc-record-card"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardItem, null, {
                              append: _withCtx(() => [
                                _createVNode(_component_VChip, {
                                  size: "small",
                                  color: "success",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                                    _createTextVNode("逻辑", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              default: _withCtx(() => [
                                _createVNode(_component_VCardTitle, { class: "bc-record-title" }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(backupDisplayName(item)), 1)
                                  ]),
                                  _: 2
                                }, 1024),
                                _createVNode(_component_VCardSubtitle, null, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.backup_id), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                _createElementVNode("div", _hoisted_26, [
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(scopeLabels(item.scope), (label) => {
                                    return (_openBlock(), _createBlock(_component_VChip, {
                                      key: label,
                                      size: "x-small",
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(label), 1)
                                      ]),
                                      _: 2
                                    }, 1024))
                                  }), 128))
                                ]),
                                _createElementVNode("div", _hoisted_27, [
                                  _createElementVNode("span", null, _toDisplayString(item.selected_plugin_ids?.length || 0) + " 个插件", 1),
                                  _createElementVNode("span", null, _toDisplayString(formatSize(item.package_size)), 1),
                                  _createElementVNode("span", null, _toDisplayString(backupKindLabel(item.backup_kind)), 1),
                                  _createElementVNode("span", null, _toDisplayString(item.encrypted ? 'AES-256-GCM' : '未加密'), 1)
                                ])
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VDivider),
                            _createVNode(_component_VCardActions, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  "prepend-icon": "mdi-check-decagram-outline",
                                  loading: actionLoading.value === `verify:${item.backup_id}`,
                                  onClick: $event => (verifyBackup(item.backup_id))
                                }, {
                                  default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                                    _createTextVNode("校验", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"]),
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  "prepend-icon": "mdi-book-open-page-variant-outline",
                                  loading: actionLoading.value === `guide:${item.backup_id}`,
                                  onClick: $event => (showGuide(item.backup_id))
                                }, {
                                  default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                                    _createTextVNode("教程", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"]),
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  color: "error",
                                  "prepend-icon": "mdi-delete-outline",
                                  loading: actionLoading.value === `delete:${item.backup_id}`,
                                  onClick: $event => (deleteBackup(item.backup_id))
                                }, {
                                  default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                                    _createTextVNode("删除", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"]),
                                _createVNode(_component_VSpacer),
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  color: "primary",
                                  variant: "tonal",
                                  "prepend-icon": "mdi-download-outline",
                                  loading: actionLoading.value === `export:${item.backup_id}`,
                                  onClick: $event => (exportBackup(item.backup_id))
                                }, {
                                  default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                                    _createTextVNode("下载", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"])
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                    ]))
              ]))
            : (activeTab.value === 'restore')
              ? (_openBlock(), _createElementBlock("section", _hoisted_28, [
                  _cache[64] || (_cache[64] = _createElementVNode("div", { class: "bc-band-heading" }, [
                    _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "恢复中心"),
                      _createElementVNode("div", { class: "bc-muted" }, "一次选择一份备份；恢复内容可以只选一项，也可以按需多选。")
                    ])
                  ], -1)),
                  _createVNode(_component_VSelect, {
                    modelValue: selectedBackupId.value,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((selectedBackupId).value = $event)),
                    items: backupOptions.value,
                    "item-title": "title",
                    "item-value": "value",
                    label: "选择一份备份",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    class: "bc-backup-select"
                  }, null, 8, ["modelValue", "items"]),
                  (selectedBackup.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_29, [
                        _createElementVNode("div", _hoisted_30, [
                          _createElementVNode("div", _hoisted_31, [
                            _createVNode(_component_VIcon, { icon: "mdi-cloud-sync-outline" })
                          ]),
                          _createElementVNode("div", _hoisted_32, [
                            _cache[58] || (_cache[58] = _createElementVNode("div", { class: "bc-route-title" }, "在线选择性恢复", -1)),
                            _cache[59] || (_cache[59] = _createElementVNode("div", { class: "bc-muted" }, "恢复配置或数据。不会替换数据库，执行前会创建宿主恢复点。", -1)),
                            _createVNode(_component_VBtn, {
                              class: "mt-3",
                              color: "primary",
                              variant: "tonal",
                              "prepend-icon": "mdi-file-search-outline",
                              loading: actionLoading.value === `preview:${selectedBackupId.value}`,
                              onClick: _cache[4] || (_cache[4] = $event => (prepareRestore(selectedBackupId.value)))
                            }, {
                              default: _withCtx(() => [...(_cache[57] || (_cache[57] = [
                                _createTextVNode("开始预检", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading"])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_33, [
                          _createElementVNode("div", _hoisted_34, [
                            _createVNode(_component_VIcon, { icon: "mdi-database-check-outline" })
                          ]),
                          _createElementVNode("div", _hoisted_35, [
                            _cache[62] || (_cache[62] = _createElementVNode("div", { class: "bc-route-title" }, "宿主数据库恢复点", -1)),
                            _cache[63] || (_cache[63] = _createElementVNode("div", { class: "bc-muted" }, "数据库由 MoviePilot 主程序统一备份与整库恢复，本插件不会导出或替换数据库。", -1)),
                            _createElementVNode("div", _hoisted_36, [
                              _createVNode(_component_VBtn, {
                                variant: "outlined",
                                "prepend-icon": "mdi-book-open-page-variant-outline",
                                onClick: _cache[5] || (_cache[5] = $event => (showGuide(selectedBackupId.value)))
                              }, {
                                default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                                  _createTextVNode("查看说明", -1)
                                ]))]),
                                _: 1
                              }),
                              _createVNode(_component_VBtn, {
                                color: "primary",
                                variant: "tonal",
                                "prepend-icon": "mdi-download-outline",
                                onClick: _cache[6] || (_cache[6] = $event => (exportBackup(selectedBackupId.value)))
                              }, {
                                default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                                  _createTextVNode("下载备份包", -1)
                                ]))]),
                                _: 1
                              })
                            ])
                          ])
                        ])
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_37, "请选择一份备份"))
                ]))
              : (_openBlock(), _createElementBlock("section", _hoisted_38, [
                  _createElementVNode("div", _hoisted_39, [
                    _cache[66] || (_cache[66] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "运行日志"),
                      _createElementVNode("div", { class: "bc-muted" }, "保留最近 200 条备份、校验、删除与在线恢复结果。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      icon: "mdi-refresh",
                      variant: "text",
                      "aria-label": "刷新运行日志",
                      loading: logsLoading.value,
                      onClick: _cache[7] || (_cache[7] = $event => (loadLogs()))
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTooltip, { activator: "parent" }, {
                          default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
                            _createTextVNode("刷新运行日志", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (!logs.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_40, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-text-box-search-outline",
                          size: "34"
                        }),
                        _cache[67] || (_cache[67] = _createElementVNode("span", null, "暂无运行日志", -1))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_41, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(logs.value, (item) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: item.log_id,
                            class: "bc-log-row"
                          }, [
                            _createElementVNode("div", {
                              class: _normalizeClass(["bc-log-state", `bc-log-state--${item.status}`])
                            }, [
                              _createVNode(_component_VIcon, {
                                icon: item.status === 'success' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline',
                                size: "20"
                              }, null, 8, ["icon"])
                            ], 2),
                            _createElementVNode("div", _hoisted_42, [
                              _createElementVNode("div", _hoisted_43, [
                                _createElementVNode("strong", null, _toDisplayString(operationLabel(item.operation)), 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: item.status === 'success' ? 'success' : 'error',
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.status === 'success' ? '成功' : '失败'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createElementVNode("span", null, _toDisplayString(formatDuration(item.duration_ms)), 1)
                              ]),
                              _createElementVNode("div", _hoisted_44, _toDisplayString(item.message), 1),
                              _createElementVNode("div", _hoisted_45, [
                                _createElementVNode("span", null, _toDisplayString(formatDate(item.finished_at)), 1),
                                (item.backup_id)
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_46, _toDisplayString(item.backup_id), 1))
                                  : _createCommentVNode("", true)
                              ])
                            ])
                          ]))
                        }), 128))
                      ]))
                ]))
    ]),
    _createVNode(_component_VDialog, {
      modelValue: createDialog.value,
      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((createDialog).value = $event)),
      "max-width": "760",
      persistent: actionLoading.value === 'create'
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "bc-dialog-card" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-archive-lock-outline",
                  color: "primary",
                  size: "26"
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, null, {
                  default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                    _createTextVNode("新建备份", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, null, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(overview.value.encryption_active ? '将使用配置页保存的口令加密。' : '当前未设置口令，将生成普通 ZIP。'), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "bc-dialog-scroll" }, {
              default: _withCtx(() => [
                _cache[79] || (_cache[79] = _createElementVNode("div", { class: "bc-section-label" }, "备份对象", -1)),
                _createVNode(_component_VBtnToggle, {
                  modelValue: createForm.target,
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((createForm.target) = $event)),
                  mandatory: "",
                  density: "compact",
                  color: "primary",
                  variant: "outlined",
                  divided: "",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VBtn, {
                      value: "moviepilot",
                      "prepend-icon": "mdi-movie-open-cog-outline"
                    }, {
                      default: _withCtx(() => [...(_cache[69] || (_cache[69] = [
                        _createTextVNode("MoviePilot", -1)
                      ]))]),
                      _: 1
                    }),
                    _createVNode(_component_VBtn, {
                      value: "plugin",
                      "prepend-icon": "mdi-puzzle-outline"
                    }, {
                      default: _withCtx(() => [...(_cache[70] || (_cache[70] = [
                        _createTextVNode("插件", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["modelValue"]),
                (createForm.target === 'plugin')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _cache[71] || (_cache[71] = _createElementVNode("div", { class: "bc-muted mb-2" }, "每份手动备份只打包一个插件，包名会使用插件中文名。", -1)),
                      _createVNode(_component_VSelect, {
                        modelValue: createForm.pluginId,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((createForm.pluginId) = $event)),
                        items: createPluginOptions.value,
                        "item-title": "title",
                        "item-value": "value",
                        label: "选择一个插件",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": "",
                        class: "mb-5"
                      }, null, 8, ["modelValue", "items"])
                    ], 64))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_47, "备份内容 · 已选 " + _toDisplayString(createScopeCount.value) + " 项", 1),
                _cache[80] || (_cache[80] = _createElementVNode("div", { class: "bc-muted bc-scope-explain" }, "默认全部不选，只保存你明确勾选的内容。", -1)),
                (createForm.target === 'plugin')
                  ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
                      _createElementVNode("section", _hoisted_49, [
                        _cache[72] || (_cache[72] = _createElementVNode("div", { class: "bc-scope-group-title" }, "配置", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.pluginSelection.configuration,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((createForm.pluginSelection.configuration) = $event)),
                          label: "插件设置",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _cache[73] || (_cache[73] = _createElementVNode("div", { class: "bc-muted px-2 pb-2" }, "插件在 MoviePilot 中保存的配置。", -1))
                      ]),
                      _createElementVNode("section", _hoisted_50, [
                        _cache[74] || (_cache[74] = _createElementVNode("div", { class: "bc-scope-group-title" }, "数据", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.pluginSelection.data,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((createForm.pluginSelection.data) = $event)),
                          label: "插件数据",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _cache[75] || (_cache[75] = _createElementVNode("div", { class: "bc-muted px-2 pb-2" }, "插件保存的数据、文件和缓存。", -1))
                      ])
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_51, [
                      _createElementVNode("section", _hoisted_52, [
                        _cache[76] || (_cache[76] = _createElementVNode("div", { class: "bc-scope-group-title" }, "配置", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.mp_settings,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((createForm.moviepilotSelection.mp_settings) = $event)),
                          label: "MoviePilot 设置",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.app_env,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((createForm.moviepilotSelection.app_env) = $event)),
                          label: "环境变量（app.env）",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.plugin_settings,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((createForm.moviepilotSelection.plugin_settings) = $event)),
                          label: "插件设置",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.cookies,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((createForm.moviepilotSelection.cookies) = $event)),
                          label: "登录 Cookie",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("section", _hoisted_53, [
                        _cache[77] || (_cache[77] = _createElementVNode("div", { class: "bc-scope-group-title" }, "数据", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.plugin_data,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((createForm.moviepilotSelection.plugin_data) = $event)),
                          label: "插件保存的数据（PluginData）",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: createForm.moviepilotSelection.plugin_files,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((createForm.moviepilotSelection.plugin_files) = $event)),
                          label: "插件文件和缓存",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _cache[78] || (_cache[78] = _createElementVNode("div", { class: "bc-muted px-2 pb-2" }, "数据库由 MoviePilot 主程序统一管理；此处只保存可在线恢复的逻辑内容。", -1))
                      ])
                    ])),
                _createVNode(_component_VAlert, {
                  type: overview.value.encryption_active ? 'info' : 'warning',
                  variant: "tonal",
                  density: "compact",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(overview.value.encryption_active ? '这份备份会使用配置页保存的口令加密。' : '这份备份不会加密，请妥善保管下载文件。'), 1)
                  ]),
                  _: 1
                }, 8, ["type"])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[18] || (_cache[18] = $event => (createDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[81] || (_cache[81] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  "prepend-icon": "mdi-archive-plus-outline",
                  disabled: !createReady.value,
                  loading: actionLoading.value === 'create',
                  onClick: createBackup
                }, {
                  default: _withCtx(() => [...(_cache[82] || (_cache[82] = [
                    _createTextVNode("创建备份", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue", "persistent"]),
    _createVNode(_component_VDialog, {
      modelValue: restoreDialog.value,
      "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((restoreDialog).value = $event)),
      "max-width": "820",
      persistent: actionLoading.value === 'restore'
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "bc-dialog-card" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-database-arrow-left-outline",
                  color: "warning",
                  size: "26"
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, null, {
                  default: _withCtx(() => [...(_cache[83] || (_cache[83] = [
                    _createTextVNode("选择性恢复预检", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "bc-dialog-subtitle" }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(selectedBackupLabel.value) + " · " + _toDisplayString(selectedBackupId.value), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "bc-dialog-scroll" }, {
              default: _withCtx(() => [
                _createVNode(_component_VAlert, {
                  type: preview.value?.online_restore_allowed ? 'success' : 'error',
                  variant: "tonal",
                  density: "compact",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(preview.value?.online_restore_allowed ? 'MoviePilot 主版本兼容，可执行在线选择性恢复。' : 'MoviePilot 主版本不兼容，在线恢复已阻断。'), 1)
                  ]),
                  _: 1
                }, 8, ["type"]),
                _createElementVNode("div", _hoisted_54, [
                  _createElementVNode("div", null, [
                    _cache[84] || (_cache[84] = _createElementVNode("span", null, "来源版本", -1)),
                    _createElementVNode("strong", null, _toDisplayString(preview.value?.manifest?.source_mp_version || '未知'), 1)
                  ]),
                  _createElementVNode("div", null, [
                    _cache[85] || (_cache[85] = _createElementVNode("span", null, "数据库模式", -1)),
                    _createElementVNode("strong", null, _toDisplayString(preview.value?.database_restore_mode === 'host_managed' ? '主程序托管' : '历史离线包'), 1)
                  ]),
                  _createElementVNode("div", null, [
                    _cache[86] || (_cache[86] = _createElementVNode("span", null, "外层校验", -1)),
                    _createElementVNode("strong", null, _toDisplayString(preview.value?.verified_files?.length || 0) + " 个文件", 1)
                  ]),
                  _createElementVNode("div", null, [
                    _cache[87] || (_cache[87] = _createElementVNode("span", null, "插件范围", -1)),
                    _createElementVNode("strong", null, _toDisplayString(preview.value?.manifest?.selected_plugin_ids?.length || 0) + " 个", 1)
                  ])
                ]),
                _createElementVNode("div", _hoisted_55, "在线恢复哪些内容 · 已选 " + _toDisplayString(restoreScopeCount.value) + " 项", 1),
                _cache[93] || (_cache[93] = _createElementVNode("div", { class: "bc-muted bc-scope-explain" }, "只能恢复这份备份里实际保存过的内容；可以只选一项，也可以按需多选。", -1)),
                _createElementVNode("div", _hoisted_56, [
                  _createElementVNode("section", _hoisted_57, [
                    _cache[88] || (_cache[88] = _createElementVNode("div", { class: "bc-scope-group-title" }, "MoviePilot", -1)),
                    _createVNode(_component_VCheckbox, {
                      modelValue: restoreForm.selection.mpSettings,
                      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((restoreForm.selection.mpSettings) = $event)),
                      label: "恢复 MoviePilot 配置",
                      disabled: !restoreAvailable.value.mpSettings,
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"]),
                    _cache[89] || (_cache[89] = _createElementVNode("div", { class: "bc-muted px-2 pb-2" }, "恢复非插件系统设置，不包含 app.env 和插件安装清单。", -1))
                  ]),
                  _createElementVNode("section", _hoisted_58, [
                    _cache[90] || (_cache[90] = _createElementVNode("div", { class: "bc-scope-group-title" }, "插件", -1)),
                    _createVNode(_component_VCheckbox, {
                      modelValue: restoreForm.selection.pluginSettings,
                      "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((restoreForm.selection.pluginSettings) = $event)),
                      label: "恢复插件配置",
                      disabled: !restoreAvailable.value.pluginSettings,
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"]),
                    _createVNode(_component_VCheckbox, {
                      modelValue: restoreForm.selection.pluginData,
                      "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((restoreForm.selection.pluginData) = $event)),
                      label: "恢复插件数据",
                      disabled: !restoreAvailable.value.pluginData,
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "disabled"]),
                    _cache[91] || (_cache[91] = _createElementVNode("div", { class: "bc-muted px-2 pb-2" }, "先在下方选择插件；数据包含 PluginData、插件文件和缓存。", -1))
                  ])
                ]),
                _createVNode(_component_VSelect, {
                  modelValue: restoreForm.pluginIds,
                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((restoreForm.pluginIds) = $event)),
                  items: restorePluginOptions.value,
                  "item-title": "title",
                  "item-value": "value",
                  label: "选择要恢复的插件",
                  multiple: "",
                  chips: "",
                  "closable-chips": "",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "mt-4"
                }, null, 8, ["modelValue", "items"]),
                (preview.value?.encrypted)
                  ? (_openBlock(), _createBlock(_component_VTextField, {
                      key: 0,
                      modelValue: restoreForm.password,
                      "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((restoreForm.password) = $event)),
                      label: "备份口令",
                      type: "password",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      autocomplete: "current-password",
                      class: "mt-4",
                      hint: "留空时尝试使用配置页当前保存的口令",
                      "persistent-hint": ""
                    }, null, 8, ["modelValue"]))
                  : _createCommentVNode("", true),
                _createVNode(_component_VAlert, {
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[92] || (_cache[92] = [
                    _createTextVNode(" 恢复时会先创建宿主数据库恢复点，再停用目标插件并自动重载；数据库文件与 app.env 不会在线替换。 ", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "bc-restore-actions" }, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[25] || (_cache[25] = $event => (restoreDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[94] || (_cache[94] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  class: "bc-restore-submit",
                  color: "warning",
                  variant: "flat",
                  "prepend-icon": "mdi-shield-alert-outline",
                  disabled: !restoreReady.value,
                  loading: actionLoading.value === 'restore',
                  onClick: restoreLogical
                }, {
                  default: _withCtx(() => [...(_cache[95] || (_cache[95] = [
                    _createTextVNode("确认恢复", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue", "persistent"]),
    _createVNode(_component_VDialog, {
      modelValue: guideDialog.value,
      "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((guideDialog).value = $event)),
      "max-width": "900"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "bc-guide-dialog" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-book-open-page-variant-outline",
                  color: "primary",
                  size: "26"
                })
              ]),
              append: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[27] || (_cache[27] = $event => (guideDialog.value = false))
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTooltip, { activator: "parent" }, {
                      default: _withCtx(() => [...(_cache[97] || (_cache[97] = [
                        _createTextVNode("关闭", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, null, {
                  default: _withCtx(() => [...(_cache[96] || (_cache[96] = [
                    _createTextVNode("备份恢复说明", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "bc-dialog-subtitle" }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(selectedBackupLabel.value) + " · " + _toDisplayString(selectedBackupId.value), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createElementVNode("div", _hoisted_59, [
              _createElementVNode("section", null, [
                _cache[98] || (_cache[98] = _createElementVNode("div", { class: "bc-section-label" }, "恢复教程", -1)),
                _createElementVNode("pre", _hoisted_60, _toDisplayString(guide.value?.guide || ''), 1)
              ]),
              _createElementVNode("section", null, [
                _cache[99] || (_cache[99] = _createElementVNode("div", { class: "bc-section-label" }, "恢复核对清单", -1)),
                _createElementVNode("pre", _hoisted_61, _toDisplayString(guide.value?.checklist || ''), 1)
              ])
            ]),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  "prepend-icon": "mdi-download-outline",
                  onClick: _cache[28] || (_cache[28] = $event => (exportBackup(selectedBackupId.value)))
                }, {
                  default: _withCtx(() => [...(_cache[100] || (_cache[100] = [
                    _createTextVNode("下载备份包", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VSnackbar, {
      modelValue: feedback.show,
      "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((feedback.show) = $event)),
      color: feedback.color,
      timeout: "6000"
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(feedback.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ], 512))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-777ac6bd"]]);

export { Page as default };
