import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-Bq_GLM4N.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "bc-config" };
const _hoisted_2 = { class: "bc-body" };
const _hoisted_3 = { class: "bc-nav" };
const _hoisted_4 = { class: "bc-content" };
const _hoisted_5 = { class: "bc-subtabs" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "bc-pane bc-pane--overview" };
const _hoisted_8 = { class: "bc-pipeline" };
const _hoisted_9 = { class: "bc-pipeline-item" };
const _hoisted_10 = { class: "bc-hint" };
const _hoisted_11 = { class: "bc-pipeline-item" };
const _hoisted_12 = { class: "bc-pipeline-item" };
const _hoisted_13 = { class: "bc-hint" };
const _hoisted_14 = { class: "bc-pipeline-item" };
const _hoisted_15 = { class: "bc-hint" };
const _hoisted_16 = { class: "bc-status-grid" };
const _hoisted_17 = { class: "bc-status-row" };
const _hoisted_18 = { class: "bc-status-row" };
const _hoisted_19 = { class: "bc-status-row" };
const _hoisted_20 = { class: "bc-pane" };
const _hoisted_21 = { class: "bc-form-grid bc-form-grid--schedule" };
const _hoisted_22 = { class: "bc-form-span" };
const _hoisted_23 = { class: "bc-form-span bc-run-row" };
const _hoisted_24 = { class: "bc-form-span bc-scope-summary" };
const _hoisted_25 = { class: "bc-section-heading" };
const _hoisted_26 = { class: "bc-section-title" };
const _hoisted_27 = { class: "bc-scope-groups mt-3" };
const _hoisted_28 = { class: "bc-scope-group" };
const _hoisted_29 = { class: "bc-scope-group" };
const _hoisted_30 = { class: "bc-pane" };
const _hoisted_31 = { class: "bc-section-heading" };
const _hoisted_32 = { class: "bc-form-grid bc-form-grid--secret mt-4" };
const _hoisted_33 = { class: "bc-secret-actions" };

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const activeMain = ref('overview');
const activeSub = ref('overview');
const secretLoading = ref(false);
const runLoading = ref(false);
const secretConfigured = ref(false);
const passwordVisible = ref(false);
const feedback = reactive({ show: false, message: '', color: 'success' });

const defaultAutoBackupScope = {
  mp_settings: true,
  plugin_settings: true,
  plugin_data: true,
  plugin_files: true,
  app_env: true,
  cookies: false,
  database: false,
};

const form = reactive({
  enabled: true,
  auto_backup_enabled: false,
  auto_backup_cron: '0 3 * * 6',
  retention_count: 5,
  auto_backup_scope: { ...defaultAutoBackupScope },
  password: '',
  passwordConfirm: '',
});

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
];

const subTabs = {
  overview: [
    { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  ],
  settings: [
    { key: 'basic', title: '基础设置', icon: 'mdi-timer-cog-outline' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-shield-key-outline' },
  ],
};

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);
const scheduleText = computed(() => (
  form.auto_backup_cron === '0 3 * * 6'
    ? '每周六 03:00'
    : form.auto_backup_cron || '0 3 * * 6'
));
const encryptionText = computed(() => secretConfigured.value ? 'AES-256-GCM' : '普通 ZIP');
const autoScopeCount = computed(() => Object.values(form.auto_backup_scope).filter(Boolean).length);

function normalizeAutoBackupScope(value) {
  const normalized = { ...defaultAutoBackupScope, ...(value || {}) };
  return Object.fromEntries(Object.keys(defaultAutoBackupScope).map(key => [key, Boolean(normalized[key])]))
}

watch(() => props.initialConfig, value => {
  Object.assign(form, {
    enabled: true,
    auto_backup_enabled: false,
    auto_backup_cron: '0 3 * * 6',
    retention_count: 5,
  }, value || {});
  form.auto_backup_scope = normalizeAutoBackupScope(value?.auto_backup_scope);
  if (!value?.auto_backup_cron && /^([01]\d|2[0-3]):[0-5]\d$/.test(value?.auto_backup_time || '')) {
    const [hour, minute] = value.auto_backup_time.split(':');
    form.auto_backup_cron = `${Number(minute)} ${Number(hour)} * * 6`;
  }
  form.password = '';
  form.passwordConfirm = '';
  secretConfigured.value = Boolean(value?.encryption_configured);
}, { immediate: true, deep: true });

function notify(message, color = 'success') {
  feedback.show = true;
  feedback.message = message;
  feedback.color = color;
}

function selectMain(key) {
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || 'overview';
}

async function loadSecretStatus() {
  try {
    const result = await getPluginApi(props.api, 'encryption/status');
    secretConfigured.value = Boolean(result?.configured);
  } catch (error) {
    notify(error.message || '口令状态读取失败', 'error');
  }
}

async function updatePassword() {
  if (form.password.length < 4) {
    notify('备份口令至少需要 4 个字符，建议使用更长口令', 'warning');
    return
  }
  if (form.password !== form.passwordConfirm) {
    notify('两次输入的备份口令不一致', 'warning');
    return
  }
  secretLoading.value = true;
  try {
    const result = await postPluginApi(props.api, 'encryption/secret', {
      action: 'set',
      password: form.password,
    });
    secretConfigured.value = Boolean(result?.configured);
    form.password = '';
    form.passwordConfirm = '';
    notify('备份口令已密文保存');
  } catch (error) {
    notify(error.message || '备份口令保存失败', 'error');
  } finally {
    secretLoading.value = false;
  }
}

async function clearPassword() {
  secretLoading.value = true;
  try {
    const result = await postPluginApi(props.api, 'encryption/secret', { action: 'clear' });
    secretConfigured.value = Boolean(result?.configured);
    form.password = '';
    form.passwordConfirm = '';
    notify('备份口令已清除', 'warning');
  } catch (error) {
    notify(error.message || '备份口令清除失败', 'error');
  } finally {
    secretLoading.value = false;
  }
}

async function runAutomaticBackup() {
  if (runLoading.value) return
  runLoading.value = true;
  try {
    const result = await postPluginApi(props.api, 'run');
    const backup = result?.backup || {};
    const label = backup.display_name || backup.backup_id || '自动备份';
    notify(`已完成：${label}`);
  } catch (error) {
    notify(error.message || '立即备份失败', 'error');
  } finally {
    runLoading.value = false;
  }
}

function save() {
  if (!autoScopeCount.value) {
    notify('周期备份范围至少选择一项', 'warning');
    return
  }
  emit('save', {
    enabled: Boolean(form.enabled),
    auto_backup_enabled: Boolean(form.auto_backup_enabled),
    auto_backup_cron: String(form.auto_backup_cron || '0 3 * * 6'),
    retention_count: Number(form.retention_count || 5),
    auto_backup_scope: { ...form.auto_backup_scope },
  });
}

onMounted(loadSecretStatus);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "bc-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "bc-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "46",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: currentMain.value.icon,
                  size: "26"
                }, null, 8, ["icon"])
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
              class: "bc-header-switch",
              color: "success",
              "hide-details": "",
              inset: "",
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                _createTextVNode("备份中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(currentMain.value.desc), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_2, [
          _createElementVNode("nav", _hoisted_3, [
            _createVNode(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "bc-nav-list py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "bc-nav-item",
                    onClick: $event => (selectMain(item.key))
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["active", "onClick"])
                }), 64))
              ]),
              _: 1
            })
          ]),
          _createElementVNode("section", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(currentSubs.value, (sub) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: sub.key,
                  type: "button",
                  class: _normalizeClass(["bc-subtab", { 'bc-subtab--active': activeSub.value === sub.key }]),
                  onClick: $event => (activeSub.value = sub.key)
                }, [
                  _createVNode(_component_VIcon, {
                    icon: sub.icon,
                    size: "18",
                    class: "mr-1"
                  }, null, 8, ["icon"]),
                  _createTextVNode(" " + _toDisplayString(sub.title), 1)
                ], 10, _hoisted_6))
              }), 128))
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", {
              class: _normalizeClass(["bc-window", { 'bc-window--overview': activeMain.value === 'overview' }])
            }, [
              _withDirectives(_createElementVNode("div", _hoisted_7, [
                _cache[25] || (_cache[25] = _createElementVNode("div", { class: "bc-section-title" }, "运行链路", -1)),
                _createElementVNode("div", _hoisted_8, [
                  _createElementVNode("div", _hoisted_9, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-calendar-clock-outline",
                      color: "primary"
                    }),
                    _createElementVNode("div", null, [
                      _cache[17] || (_cache[17] = _createElementVNode("div", { class: "bc-item-title" }, "定时触发", -1)),
                      _createElementVNode("div", _hoisted_10, _toDisplayString(scheduleText.value), 1)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_11, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-archive-arrow-down-outline",
                      color: "primary"
                    }),
                    _cache[18] || (_cache[18] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "bc-item-title" }, "收集数据"),
                      _createElementVNode("div", { class: "bc-hint" }, "配置和数据")
                    ], -1))
                  ]),
                  _createElementVNode("div", _hoisted_12, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-shield-lock-outline",
                      color: "primary"
                    }),
                    _createElementVNode("div", null, [
                      _cache[19] || (_cache[19] = _createElementVNode("div", { class: "bc-item-title" }, "生成备份", -1)),
                      _createElementVNode("div", _hoisted_13, _toDisplayString(encryptionText.value), 1)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_14, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-delete-clock-outline",
                      color: "primary"
                    }),
                    _createElementVNode("div", null, [
                      _cache[20] || (_cache[20] = _createElementVNode("div", { class: "bc-item-title" }, "轮换归档", -1)),
                      _createElementVNode("div", _hoisted_15, "保留 " + _toDisplayString(form.retention_count || 5) + " 份自动备份", 1)
                    ])
                  ])
                ]),
                _cache[26] || (_cache[26] = _createElementVNode("div", { class: "bc-section-title bc-section-title--status" }, "当前状态", -1)),
                _createElementVNode("div", _hoisted_16, [
                  _createElementVNode("div", _hoisted_17, [
                    _cache[21] || (_cache[21] = _createElementVNode("span", null, "插件状态", -1)),
                    _createVNode(_component_VChip, {
                      size: "small",
                      color: form.enabled ? 'success' : 'default',
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(form.enabled ? '已启用' : '已停用'), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  _createElementVNode("div", _hoisted_18, [
                    _cache[22] || (_cache[22] = _createElementVNode("span", null, "自动备份", -1)),
                    _createVNode(_component_VChip, {
                      size: "small",
                      color: form.auto_backup_enabled ? 'success' : 'default',
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(form.auto_backup_enabled ? '已开启' : '已关闭'), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  _createElementVNode("div", _hoisted_19, [
                    _cache[23] || (_cache[23] = _createElementVNode("span", null, "备份加密", -1)),
                    _createVNode(_component_VChip, {
                      size: "small",
                      color: secretConfigured.value ? 'success' : 'default',
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(secretConfigured.value ? '已设置' : '未设置'), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  _cache[24] || (_cache[24] = _createElementVNode("div", { class: "bc-status-row" }, [
                    _createElementVNode("span", null, "手动操作"),
                    _createElementVNode("span", { class: "bc-status-value" }, "插件详情页")
                  ], -1))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'overview']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_20, [
                _cache[34] || (_cache[34] = _createElementVNode("div", { class: "bc-section-title" }, "基础设置", -1)),
                _createElementVNode("div", _hoisted_21, [
                  _createElementVNode("div", _hoisted_22, [
                    _createVNode(_component_VSwitch, {
                      modelValue: form.auto_backup_enabled,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.auto_backup_enabled) = $event)),
                      color: "success",
                      label: "启用自动备份",
                      "hide-details": "",
                      inset: ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", null, [
                    _createVNode(_component_VCronField, {
                      modelValue: form.auto_backup_cron,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.auto_backup_cron) = $event)),
                      label: "运行周期",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      disabled: !form.auto_backup_enabled
                    }, null, 8, ["modelValue", "disabled"])
                  ]),
                  _createElementVNode("div", null, [
                    _createVNode(_component_VTextField, {
                      modelValue: form.retention_count,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.retention_count) = $event)),
                      modelModifiers: { number: true },
                      label: "保留数量",
                      type: "number",
                      min: "1",
                      max: "200",
                      hint: "只清理最旧的自动备份",
                      "persistent-hint": "",
                      density: "compact",
                      variant: "outlined"
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", _hoisted_23, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-play-circle-outline",
                      loading: runLoading.value,
                      disabled: runLoading.value,
                      onClick: runAutomaticBackup
                    }, {
                      default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                        _createTextVNode(" 立即运行一次 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _cache[28] || (_cache[28] = _createElementVNode("span", { class: "bc-hint" }, "按当前周期备份范围立即生成一份自动备份。", -1))
                  ]),
                  _createElementVNode("div", _hoisted_24, [
                    _createElementVNode("div", _hoisted_25, [
                      _createElementVNode("div", null, [
                        _createElementVNode("div", _hoisted_26, "周期备份范围 · 已选 " + _toDisplayString(autoScopeCount.value) + " 项", 1),
                        _cache[29] || (_cache[29] = _createElementVNode("div", { class: "bc-hint" }, "这里只影响每周自动备份；详情页的手动备份范围单独选择。", -1))
                      ]),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                          _createTextVNode("按配置执行", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _createElementVNode("div", _hoisted_27, [
                      _createElementVNode("section", _hoisted_28, [
                        _cache[31] || (_cache[31] = _createElementVNode("div", { class: "bc-scope-group-title" }, "配置", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.mp_settings,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.auto_backup_scope.mp_settings) = $event)),
                          label: "MoviePilot 设置",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.app_env,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.auto_backup_scope.app_env) = $event)),
                          label: "环境变量（app.env）",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.plugin_settings,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.auto_backup_scope.plugin_settings) = $event)),
                          label: "插件设置",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.cookies,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.auto_backup_scope.cookies) = $event)),
                          label: "登录 Cookie",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createElementVNode("section", _hoisted_29, [
                        _cache[32] || (_cache[32] = _createElementVNode("div", { class: "bc-scope-group-title" }, "数据", -1)),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.plugin_data,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.auto_backup_scope.plugin_data) = $event)),
                          label: "插件保存的数据（PluginData）",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.plugin_files,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.auto_backup_scope.plugin_files) = $event)),
                          label: "插件文件和缓存",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.auto_backup_scope.database,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.auto_backup_scope.database) = $event)),
                          label: "整个数据库",
                          color: "warning",
                          density: "compact",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    (form.auto_backup_scope.database)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 0,
                          type: "warning",
                          variant: "tonal",
                          density: "compact",
                          class: "mt-3"
                        }, {
                          default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                            _createTextVNode(" 周期备份包含整个数据库时，生成的整库快照只能停机后按离线教程恢复。 ", -1)
                          ]))]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ])
                ])
              ], 512), [
                [_vShow, activeMain.value === 'settings' && activeSub.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_30, [
                _createElementVNode("div", _hoisted_31, [
                  _cache[35] || (_cache[35] = _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "bc-section-title mb-1" }, "备份加密"),
                    _createElementVNode("div", { class: "bc-hint" }, "最低 4 位，建议使用更长口令；不设置口令时生成普通 ZIP。"),
                    _createElementVNode("div", { class: "bc-hint" }, "口令单独密文保存，不进入普通插件配置。")
                  ], -1)),
                  _createVNode(_component_VChip, {
                    size: "small",
                    color: secretConfigured.value ? 'success' : 'default',
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(secretConfigured.value ? '已设置' : '未设置'), 1)
                    ]),
                    _: 1
                  }, 8, ["color"])
                ]),
                _createElementVNode("div", _hoisted_32, [
                  _createElementVNode("div", null, [
                    _createVNode(_component_VTextField, {
                      modelValue: form.password,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.password) = $event)),
                      label: "备份口令",
                      type: passwordVisible.value ? 'text' : 'password',
                      "append-inner-icon": passwordVisible.value ? 'mdi-eye-off-outline' : 'mdi-eye-outline',
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      autocomplete: "new-password",
                      "onClick:appendInner": _cache[12] || (_cache[12] = $event => (passwordVisible.value = !passwordVisible.value))
                    }, null, 8, ["modelValue", "type", "append-inner-icon"])
                  ]),
                  _createElementVNode("div", null, [
                    _createVNode(_component_VTextField, {
                      modelValue: form.passwordConfirm,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.passwordConfirm) = $event)),
                      label: "确认口令",
                      type: passwordVisible.value ? 'text' : 'password',
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      autocomplete: "new-password"
                    }, null, 8, ["modelValue", "type"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_33, [
                  (secretConfigured.value)
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        color: "error",
                        variant: "text",
                        "prepend-icon": "mdi-key-remove",
                        loading: secretLoading.value,
                        onClick: clearPassword
                      }, {
                        default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                          _createTextVNode(" 清除口令 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"]))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "tonal",
                    "prepend-icon": "mdi-key-change",
                    loading: secretLoading.value,
                    onClick: updatePassword
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(secretConfigured.value ? '更新口令' : '设置口令'), 1)
                    ]),
                    _: 1
                  }, 8, ["loading"])
                ])
              ], 512), [
                [_vShow, activeMain.value === 'settings' && activeSub.value === 'advanced']
              ])
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "bc-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[14] || (_cache[14] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: save
            }, {
              default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                _createTextVNode(" 保存配置 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VSnackbar, {
      modelValue: feedback.show,
      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((feedback.show) = $event)),
      color: feedback.color,
      timeout: "5000"
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(feedback.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-a5e2325e"]]);

export { Config as default };
