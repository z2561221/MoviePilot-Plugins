import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as apiGet } from './_plugin-vue_export-helper-BX4pWp5Z.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives,createCommentVNode:_createCommentVNode,createBlock:_createBlock} = await importShared('vue');


const _hoisted_1 = { class: "plugin-config" };
const _hoisted_2 = { class: "plugin-body" };
const _hoisted_3 = { class: "plugin-nav" };
const _hoisted_4 = { class: "plugin-content" };
const _hoisted_5 = { class: "plugin-subtabs" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "plugin-window" };
const _hoisted_8 = { class: "plugin-pane" };
const _hoisted_9 = { class: "plugin-hint" };
const _hoisted_10 = { class: "plugin-hint" };
const _hoisted_11 = { class: "plugin-hint" };
const _hoisted_12 = { class: "plugin-hint" };
const _hoisted_13 = { class: "plugin-hint" };
const _hoisted_14 = { class: "plugin-pane" };
const _hoisted_15 = { key: 0 };
const _hoisted_16 = { key: 1 };
const _hoisted_17 = { key: 2 };
const _hoisted_18 = { class: "plugin-pane" };
const _hoisted_19 = { class: "plugin-pane" };

const {reactive,ref,computed,watch,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

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
};

const form = reactive(JSON.parse(JSON.stringify(defaults)));
const activeMain = ref('overview');
const activeSub = ref('basic');
const loadingOptions = ref(false);
const optionError = ref('');
const cleanupOptions = reactive({ servers: [], libraries: [], users: [] });

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '统一管理三个本地维护模块。', color: 'primary' },
  { key: 'library_cleanup', title: '清理库存', icon: 'mdi-delete-sweep-outline', desc: '唯一保留周期运行的模块，可按 Cron 自动巡检与删除。', color: 'error' },
  { key: 'check_missing', title: '扫描缺集', icon: 'mdi-magnify-scan', desc: '按需单次扫描媒体目录，检查已存在季的缺集。', color: 'primary' },
  { key: 'tmdb_cache', title: '清理TMDB', icon: 'mdi-database-refresh-outline', desc: '按需单次查询与清理 Redis 中的 TMDB 缓存。', color: 'warning' },
];

const subTabs = {
  overview: [{ key: 'basic', title: '模块职责', icon: 'mdi-clipboard-check-outline' }],
  library_cleanup: [
    { key: 'basic', title: '基础设置', icon: 'mdi-timer-cog-outline' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-outline' },
    { key: 'danger', title: '高级选项', icon: 'mdi-alert-outline' },
  ],
  check_missing: [{ key: 'basic', title: '按需扫描', icon: 'mdi-folder-search-outline' }],
  tmdb_cache: [{ key: 'basic', title: '按需清理', icon: 'mdi-database-cog-outline' }],
};

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);
const pathCount = computed(() => (form.check_missing.scan_paths || '').split('\n').map(i => i.trim()).filter(Boolean).length);
const serverItems = computed(() => cleanupOptions.servers?.length ? cleanupOptions.servers : fallbackItem(form.library_cleanup.selected_server));
const libraryItems = computed(() => cleanupOptions.libraries?.length ? cleanupOptions.libraries : fallbackItem(form.library_cleanup.selected_library));
const userItems = computed(() => cleanupOptions.users?.length ? cleanupOptions.users : fallbackItem(form.library_cleanup.selected_user));

function fallbackItem(value) {
  return value ? [{ title: value, value }] : []
}

function merge(target, source, path = '') {
  Object.entries(source || {}).forEach(([key, value]) => {
    const nextPath = path ? `${path}.${key}` : key;
    if ((nextPath === 'tmdb_cache.cron') || (nextPath === 'check_missing.cron')) return
    if (value && typeof value === 'object' && !Array.isArray(value) && target[key]) merge(target[key], value, nextPath);
    else target[key] = value;
  });
}

watch(() => props.initialConfig, value => {
  Object.keys(form).forEach(k => delete form[k]);
  Object.assign(form, JSON.parse(JSON.stringify(defaults)));
  merge(form, value || {});
  delete form.tmdb_cache.cron;
  delete form.check_missing.cron;
}, { immediate: true, deep: true });

async function loadOptions() {
  loadingOptions.value = true;
  optionError.value = '';
  try {
    const res = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/options');
    const data = res?.library_cleanup || res || {};
    cleanupOptions.servers = data.servers || [];
    cleanupOptions.libraries = data.libraries || [];
    cleanupOptions.users = data.users || [];
    optionError.value = data.error || '';
  } catch (e) {
    optionError.value = String(e);
  } finally {
    loadingOptions.value = false;
  }
}

function selectMain(key) {
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || 'basic';
  if (key === 'library_cleanup') loadOptions();
}

watch(() => form.library_cleanup.selected_server, (next, prev) => {
  if (next !== prev && prev !== undefined) {
    cleanupOptions.libraries = [];
    cleanupOptions.users = [];
    loadOptions();
  }
});

onMounted(loadOptions);

function saveConfig() {
  const payload = JSON.parse(JSON.stringify(form));
  delete payload.tmdb_cache.cron;
  delete payload.check_missing.cron;
  emit('save', payload);
}

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
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "plugin-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "plugin-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: currentMain.value.color,
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
            }, 8, ["color"])
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                _createTextVNode("工具中心", -1)
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
              class: "py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: item.color,
                    rounded: "lg",
                    class: "plugin-nav-item",
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
                  }, 1032, ["active", "color", "onClick"])
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
                  class: _normalizeClass(["plugin-subtab", { 'plugin-subtab--active': activeSub.value === sub.key }]),
                  onClick: $event => (activeSub.value = sub.key)
                }, [
                  _createVNode(_component_VIcon, {
                    icon: sub.icon,
                    size: "18",
                    class: "mr-1"
                  }, null, 8, ["icon"]),
                  _createTextVNode(_toDisplayString(sub.title), 1)
                ], 10, _hoisted_6))
              }), 128))
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", _hoisted_7, [
              _withDirectives(_createElementVNode("div", _hoisted_8, [
                _cache[29] || (_cache[29] = _createElementVNode("div", { class: "plugin-section-title" }, "模块职责", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          color: "error",
                          class: "status-card"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "清理库存", -1)),
                                _createElementVNode("div", _hoisted_9, "周期运行：" + _toDisplayString(form.library_cleanup.enabled && form.enabled ? '开启' : '关闭'), 1),
                                _createElementVNode("div", _hoisted_10, "Cron：" + _toDisplayString(form.library_cleanup.cron || '未设置'), 1),
                                _createElementVNode("div", _hoisted_11, "自动删除：" + _toDisplayString(form.library_cleanup.auto_delete ? '开启' : '关闭'), 1)
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          color: "primary",
                          class: "status-card"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                _cache[23] || (_cache[23] = _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "扫描缺集", -1)),
                                _cache[24] || (_cache[24] = _createElementVNode("div", { class: "plugin-hint" }, "运行方式：按需单次", -1)),
                                _createElementVNode("div", _hoisted_12, "扫描路径：" + _toDisplayString(pathCount.value) + " 个", 1),
                                _cache[25] || (_cache[25] = _createElementVNode("div", { class: "plugin-hint" }, "在详情页点击「立即扫描」运行", -1))
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          color: "warning",
                          class: "status-card"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                _cache[26] || (_cache[26] = _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "TMDB 缓存", -1)),
                                _cache[27] || (_cache[27] = _createElementVNode("div", { class: "plugin-hint" }, "运行方式：按需单次", -1)),
                                _createElementVNode("div", _hoisted_13, "阈值：" + _toDisplayString(form.tmdb_cache.threshold_mb) + " MB", 1),
                                _cache[28] || (_cache[28] = _createElementVNode("div", { class: "plugin-hint" }, "在详情页点击「立即清理」运行", -1))
                              ]),
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
                }),
                _createVNode(_component_VAlert, {
                  class: "mt-4",
                  type: "info",
                  variant: "tonal",
                  text: "详情页提供三个模块的一键立即执行按钮；配置页只负责保存参数。只有清理库存会在插件启用且模块启用时按 Cron 周期运行。"
                })
              ], 512), [
                [_vShow, activeMain.value === 'overview']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_14, [
                (activeSub.value === 'basic')
                  ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                      _cache[30] || (_cache[30] = _createElementVNode("div", { class: "plugin-section-title text-error" }, "清理库存基础设置", -1)),
                      _createVNode(_component_VAlert, {
                        type: "warning",
                        variant: "tonal",
                        class: "mb-4",
                        text: "清理库存是唯一周期运行模块。若开启自动删除，请务必确认筛选范围和删除策略。"
                      }),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.library_cleanup.enabled,
                                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.library_cleanup.enabled) = $event)),
                                color: "error",
                                label: "启用周期清理库存",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.library_cleanup.notify,
                                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.library_cleanup.notify) = $event)),
                                color: "info",
                                label: "运行通知",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.library_cleanup.cron,
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.library_cleanup.cron) = $event)),
                                label: "Cron 周期",
                                placeholder: "9 0 * * *",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]))
                  : _createCommentVNode("", true),
                (activeSub.value === 'filter')
                  ? (_openBlock(), _createElementBlock("div", _hoisted_16, [
                      _cache[31] || (_cache[31] = _createElementVNode("div", { class: "plugin-section-title text-error" }, "筛选条件", -1)),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSelect, {
                                modelValue: form.library_cleanup.selected_server,
                                "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.library_cleanup.selected_server) = $event)),
                                label: "媒体服务器",
                                items: serverItems.value,
                                loading: loadingOptions.value,
                                density: "compact",
                                variant: "outlined",
                                clearable: "",
                                "hide-details": ""
                              }, null, 8, ["modelValue", "items", "loading"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSelect, {
                                modelValue: form.library_cleanup.selected_library,
                                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.library_cleanup.selected_library) = $event)),
                                label: "媒体库",
                                items: libraryItems.value,
                                loading: loadingOptions.value,
                                density: "compact",
                                variant: "outlined",
                                clearable: "",
                                "hide-details": ""
                              }, null, 8, ["modelValue", "items", "loading"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSelect, {
                                modelValue: form.library_cleanup.selected_user,
                                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.library_cleanup.selected_user) = $event)),
                                label: "用户",
                                items: userItems.value,
                                loading: loadingOptions.value,
                                density: "compact",
                                variant: "outlined",
                                clearable: "",
                                "hide-details": ""
                              }, null, 8, ["modelValue", "items", "loading"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSelect, {
                                modelValue: form.library_cleanup.filter_favorite,
                                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.library_cleanup.filter_favorite) = $event)),
                                label: "收藏状态",
                                items: [{ title: '全部', value: 'all' }, { title: '已收藏', value: 'fav' }, { title: '未收藏', value: 'unfav' }],
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSelect, {
                                modelValue: form.library_cleanup.filter_played,
                                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.library_cleanup.filter_played) = $event)),
                                label: "看过状态",
                                items: [{ title: '全部', value: 'all' }, { title: '已看过', value: 'played' }, { title: '未看过', value: 'unplayed' }],
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.library_cleanup.days_threshold,
                                "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.library_cleanup.days_threshold) = $event)),
                                modelModifiers: { number: true },
                                label: "创建时间阈值（天）",
                                type: "number",
                                min: "1",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          (optionError.value)
                            ? (_openBlock(), _createBlock(_component_VCol, {
                                key: 0,
                                cols: "12"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VAlert, {
                                    type: "warning",
                                    variant: "tonal",
                                    density: "compact",
                                    text: `媒体服务器选项加载异常：${optionError.value}`
                                  }, null, 8, ["text"])
                                ]),
                                _: 1
                              }))
                            : _createCommentVNode("", true)
                        ]),
                        _: 1
                      })
                    ]))
                  : _createCommentVNode("", true),
                (activeSub.value === 'danger')
                  ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                      _cache[32] || (_cache[32] = _createElementVNode("div", { class: "plugin-section-title text-error" }, "高级选项", -1)),
                      _createVNode(_component_VAlert, {
                        type: "error",
                        variant: "tonal",
                        class: "mb-4",
                        text: "自动删除会直接删除 Emby 条目。按钮手动执行清理库存时也会遵循这里的自动删除配置。"
                      }),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.library_cleanup.auto_delete,
                                "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.library_cleanup.auto_delete) = $event)),
                                color: "error",
                                label: "自动删除",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.library_cleanup.dry_run,
                                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.library_cleanup.dry_run) = $event)),
                                color: "warning",
                                label: "演练模式",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.library_cleanup.auto_delete_delay,
                                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.library_cleanup.auto_delete_delay) = $event)),
                                modelModifiers: { number: true },
                                label: "删除间隔（秒）",
                                type: "number",
                                min: "0",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.library_cleanup.auto_delete_max_count,
                                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.library_cleanup.auto_delete_max_count) = $event)),
                                modelModifiers: { number: true },
                                label: "单次删除上限",
                                type: "number",
                                min: "0",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]))
                  : _createCommentVNode("", true)
              ], 512), [
                [_vShow, activeMain.value === 'library_cleanup']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_18, [
                _cache[33] || (_cache[33] = _createElementVNode("div", { class: "plugin-section-title" }, "扫描缺集按需扫描", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-4",
                  text: "扫描缺集不再提供 Cron 周期配置，只在详情页点击“立即扫描”时运行。空文件夹可按规则跳过。"
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.check_missing.notify,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.check_missing.notify) = $event)),
                          color: "info",
                          label: "运行通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.check_missing.skip_empty,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.check_missing.skip_empty) = $event)),
                          color: "success",
                          label: "跳过空文件夹",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.check_missing.scan_paths,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.check_missing.scan_paths) = $event)),
                          label: "扫描路径（一行一个）",
                          rows: "6",
                          "auto-grow": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'check_missing']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_19, [
                _cache[34] || (_cache[34] = _createElementVNode("div", { class: "plugin-section-title text-warning" }, "TMDB 缓存按需清理", -1)),
                _createVNode(_component_VAlert, {
                  type: "warning",
                  variant: "tonal",
                  class: "mb-4",
                  text: "清理TMDB不再提供 Cron 周期配置，只在详情页点击“立即清理”时运行。可选择按阈值判断是否真正删除。"
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.tmdb_cache.notify,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.tmdb_cache.notify) = $event)),
                          color: "info",
                          label: "运行通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.tmdb_cache.auto_clear,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.tmdb_cache.auto_clear) = $event)),
                          color: "warning",
                          label: "按阈值清理",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.tmdb_cache.threshold_mb,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.tmdb_cache.threshold_mb) = $event)),
                          modelModifiers: { number: true },
                          label: "阈值 MB",
                          type: "number",
                          min: "0",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'tmdb_cache']
              ])
            ])
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "plugin-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[20] || (_cache[20] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                _createTextVNode("保存配置", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-95182d87"]]);

export { Config as default };
