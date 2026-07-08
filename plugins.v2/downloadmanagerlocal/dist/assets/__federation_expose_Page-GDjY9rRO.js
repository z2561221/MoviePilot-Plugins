import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-DxfxZJCG.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "dm-page" };
const _hoisted_2 = { class: "dm-layout" };
const _hoisted_3 = { class: "dm-side" };
const _hoisted_4 = { class: "dm-main" };
const _hoisted_5 = {
  key: 2,
  class: "dm-state"
};
const _hoisted_6 = {
  key: 3,
  class: "dm-pane"
};
const _hoisted_7 = { class: "d-flex align-center mb-3" };
const _hoisted_8 = {
  key: 0,
  class: "dm-state text-center text-medium-emphasis"
};
const _hoisted_9 = { class: "dm-table-scroll dm-desktop-table" };
const _hoisted_10 = { class: "text-caption text-no-wrap" };
const _hoisted_11 = ["title"];
const _hoisted_12 = ["title"];
const _hoisted_13 = { class: "d-flex ga-1" };
const _hoisted_14 = { class: "dm-mobile-list dm-history-list" };
const _hoisted_15 = { class: "dm-record-head" };
const _hoisted_16 = ["title"];
const _hoisted_17 = { class: "dm-record-meta" };
const _hoisted_18 = { class: "dm-record-row" };
const _hoisted_19 = { class: "dm-record-value" };
const _hoisted_20 = { class: "dm-record-row" };
const _hoisted_21 = ["title"];
const _hoisted_22 = { class: "dm-record-row" };
const _hoisted_23 = ["title"];
const _hoisted_24 = { class: "dm-record-actions" };
const _hoisted_25 = {
  key: 2,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_26 = { class: "text-caption mx-1" };
const _hoisted_27 = {
  key: 4,
  class: "dm-pane"
};
const _hoisted_28 = {
  key: 0,
  class: "dm-state text-center text-medium-emphasis"
};
const _hoisted_29 = { class: "dm-table-scroll dm-desktop-table" };
const _hoisted_30 = { class: "text-caption text-no-wrap" };
const _hoisted_31 = ["title"];
const _hoisted_32 = { class: "text-caption" };
const _hoisted_33 = ["title"];
const _hoisted_34 = { class: "d-flex ga-1" };
const _hoisted_35 = { class: "dm-mobile-list dm-archive-list" };
const _hoisted_36 = { class: "dm-record-head" };
const _hoisted_37 = ["title"];
const _hoisted_38 = { class: "dm-record-meta" };
const _hoisted_39 = { class: "dm-record-row" };
const _hoisted_40 = { class: "dm-record-value" };
const _hoisted_41 = { class: "dm-record-row" };
const _hoisted_42 = { class: "dm-record-value" };
const _hoisted_43 = { class: "dm-record-row" };
const _hoisted_44 = ["title"];
const _hoisted_45 = { class: "dm-record-actions" };
const _hoisted_46 = {
  key: 2,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_47 = { class: "text-caption mx-1" };
const _hoisted_48 = {
  key: 5,
  class: "dm-pane"
};
const _hoisted_49 = {
  key: 0,
  class: "dm-diagnostics"
};
const _hoisted_50 = { class: "dm-stat-grid mb-3" };
const _hoisted_51 = { class: "dm-stat" };
const _hoisted_52 = { class: "text-subtitle-2" };
const _hoisted_53 = { class: "dm-stat" };
const _hoisted_54 = { class: "text-subtitle-2" };
const _hoisted_55 = { class: "dm-stat" };
const _hoisted_56 = { class: "text-subtitle-2" };
const _hoisted_57 = { class: "dm-stat" };
const _hoisted_58 = { class: "text-subtitle-2" };
const _hoisted_59 = { class: "text-caption" };
const _hoisted_60 = { class: "dm-diagnostics-panel mb-3" };
const _hoisted_61 = { class: "dm-diagnostics-head" };
const _hoisted_62 = { class: "dm-diagnostics-title" };
const _hoisted_63 = { class: "dm-diagnostics-icon" };
const _hoisted_64 = { class: "dm-diagnostics-score" };
const _hoisted_65 = { key: 0 };
const _hoisted_66 = { class: "dm-diagnostics-grid" };
const _hoisted_67 = { class: "dm-diagnostic-state" };
const _hoisted_68 = { class: "dm-diagnostic-content" };
const _hoisted_69 = { class: "dm-diagnostic-name" };
const _hoisted_70 = { class: "dm-diagnostic-value" };
const _hoisted_71 = { class: "dm-diagnostic-note" };
const _hoisted_72 = { class: "dm-diagnostics-footer" };
const _hoisted_73 = {
  key: 0,
  class: "dm-diagnostics-attention"
};
const _hoisted_74 = {
  key: 0,
  class: "text-caption text-medium-emphasis py-2"
};
const _hoisted_75 = {
  key: 1,
  class: "dm-table-scroll"
};
const _hoisted_76 = { class: "text-caption text-no-wrap" };
const _hoisted_77 = ["title"];
const _hoisted_78 = { class: "text-caption" };
const _hoisted_79 = {
  key: 1,
  class: "dm-state text-center text-medium-emphasis"
};

const {ref,onMounted,computed} = await importShared('vue');

const pageSize = 15;

const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const activeTab = ref('history');
const diagnostics = ref(null);
const records = ref([]);
const archiveRecords = ref([]);
const total = ref(0);
const archiveTotal = ref(0);
const page = ref(1);
const archivePage = ref(1);
const loading = ref(false);
const retrying = ref(false);
const retryingHash = ref('');
const restoringHash = ref('');
const deletingHash = ref('');
const error = ref('');
const actionMsg = ref('');
const actionOk = ref(false);

const tabs = [
  { key: 'history', title: '命名历史', icon: 'mdi-history' },
  { key: 'archive', title: '归档记录', icon: 'mdi-archive-outline' },
  { key: 'diagnostics', title: '运行诊断', icon: 'mdi-stethoscope' },
];

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)));
const archiveTotalPages = computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / pageSize)));
const diagnosticsCards = computed(() => {
  const items = Array.isArray(diagnostics.value?.checks) ? diagnostics.value.checks : [];
  return items.map(item => ({
    ...item,
    statusText: item.status === 'ok' ? '正常' : item.status === 'warn' ? '关注' : '未启用',
    icon: item.status === 'ok'
      ? 'mdi-check-circle-outline'
      : item.status === 'warn'
        ? 'mdi-alert-circle-outline'
        : 'mdi-minus-circle-outline',
  }))
});
const diagnosticsOkCount = computed(() => diagnosticsCards.value.filter(item => item.status === 'ok').length);
const diagnosticsAttentionCount = computed(() => diagnosticsCards.value.length - diagnosticsOkCount.value);

async function loadHistory() {
  loading.value = true;
  error.value = '';
  try {
    const resp = await getPluginApi(props.api, `rename_history?page=${page.value}&page_size=${pageSize}`);
    records.value = Array.isArray(resp?.items) ? resp.items : [];
    total.value = resp?.total || 0;
  } catch (e) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadArchive() {
  loading.value = true;
  error.value = '';
  try {
    const resp = await getPluginApi(props.api, `rename_archive?page=${archivePage.value}&page_size=${pageSize}`);
    archiveRecords.value = Array.isArray(resp?.items) ? resp.items : [];
    archiveTotal.value = resp?.total || 0;
  } catch (e) {
    error.value = e?.message || '归档加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadDiagnostics() {
  loading.value = true;
  error.value = '';
  try {
    const resp = await getPluginApi(props.api, 'diagnostics');
    if (resp?.code && resp.code !== 0) {
      error.value = resp?.msg || '诊断失败';
      return
    }
    diagnostics.value = resp;
  } catch (e) {
    error.value = e?.message || '诊断失败';
  } finally {
    loading.value = false;
  }
}

async function selectTab(key) {
  activeTab.value = key;
  await refreshActive();
}

async function refreshActive() {
  if (activeTab.value === 'history') return loadHistory()
  if (activeTab.value === 'archive') return loadArchive()
  return loadDiagnostics()
}

async function doRecovery(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  try {
    const resp = await postPluginApi(props.api, 'recovery_torrent', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await loadHistory();
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败';
  }
}

async function doDelete(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_history', { hash });
    actionOk.value = resp?.code === 0;
    actionMsg.value = resp?.msg || '已删除';
    if (resp?.code === 0) await loadHistory();
  } catch (e) {
    actionMsg.value = e?.message || '删除失败';
  }
}

async function doRetryRenames() {
  actionMsg.value = '';
  actionOk.value = false;
  retrying.value = true;
  try {
    const resp = await postPluginApi(props.api, 'retry_renames', {});
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await refreshActive();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '补刀失败';
  } finally {
    retrying.value = false;
  }
}

async function doRetryRename(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  retryingHash.value = hash;
  try {
    const resp = await postPluginApi(props.api, 'retry_rename', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await loadHistory();
  } catch (e) {
    actionOk.value = false;
    actionMsg.value = e?.message || '补刀失败';
  } finally {
    retryingHash.value = '';
  }
}

async function restoreArchive(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  restoringHash.value = hash;
  try {
    const resp = await postPluginApi(props.api, 'restore_rename_archive', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已恢复' : '恢复失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await loadArchive();
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败';
  } finally {
    restoringHash.value = '';
  }
}

async function deleteArchive(hash) {
  actionMsg.value = '';
  actionOk.value = false;
  deletingHash.value = hash;
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_archive', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已删除' : '删除失败');
    actionOk.value = resp?.code === 0;
    if (resp?.code === 0) await loadArchive();
  } catch (e) {
    actionMsg.value = e?.message || '删除失败';
  } finally {
    deletingHash.value = '';
  }
}

function prevPage() {
  if (page.value > 1) { page.value--; loadHistory(); }
}
function nextPage() {
  if (page.value < totalPages.value) { page.value++; loadHistory(); }
}
function prevArchivePage() {
  if (archivePage.value > 1) { archivePage.value--; loadArchive(); }
}
function nextArchivePage() {
  if (archivePage.value < archiveTotalPages.value) { archivePage.value++; loadArchive(); }
}

onMounted(loadHistory);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTable = _resolveComponent("VTable");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "dm-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-download",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-h6" }, "下载中心", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: refreshActive,
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("nav", _hoisted_3, [
        _createVNode(_component_VList, {
          density: "compact",
          nav: "",
          class: "dm-side-list py-2"
        }, {
          default: _withCtx(() => [
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
              return _createVNode(_component_VListItem, {
                key: tab.key,
                active: activeTab.value === tab.key,
                color: "primary",
                rounded: "lg",
                class: "dm-side-item",
                onClick: $event => (selectTab(tab.key))
              }, {
                prepend: _withCtx(() => [
                  _createVNode(_component_VIcon, {
                    icon: tab.icon
                  }, null, 8, ["icon"])
                ]),
                default: _withCtx(() => [
                  _createVNode(_component_VListItemTitle, null, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(tab.title), 1)
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
      _createElementVNode("main", _hoisted_4, [
        (actionMsg.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: actionOk.value ? 'success' : 'error',
              variant: "tonal",
              class: "mb-3",
              closable: "",
              density: "compact"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(actionMsg.value), 1)
              ]),
              _: 1
            }, 8, ["type"]))
          : _createCommentVNode("", true),
        (error.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 1,
              type: "error",
              variant: "tonal",
              class: "mb-3",
              density: "compact"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (loading.value)
          ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
              _createVNode(_component_VProgressCircular, {
                indeterminate: "",
                color: "primary"
              })
            ]))
          : (activeTab.value === 'history')
            ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                _createElementVNode("div", _hoisted_7, [
                  _cache[6] || (_cache[6] = _createElementVNode("div", { class: "text-subtitle-2" }, "命名历史", -1)),
                  _createVNode(_component_VSpacer),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    size: "small",
                    "prepend-icon": "mdi-auto-fix",
                    class: "text-none",
                    onClick: doRetryRenames,
                    loading: retrying.value
                  }, {
                    default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                      _createTextVNode("补刀", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"])
                ]),
                (records.value.length === 0)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-history",
                        size: "48",
                        color: "grey-lighten-1",
                        class: "mb-2"
                      }),
                      _cache[7] || (_cache[7] = _createElementVNode("div", null, "暂无命名记录", -1))
                    ]))
                  : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createElementVNode("div", _hoisted_9, [
                        _createVNode(_component_VTable, {
                          density: "compact",
                          class: "dm-table"
                        }, {
                          default: _withCtx(() => [
                            _cache[11] || (_cache[11] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", { class: "text-caption" }, "时间"),
                                _createElementVNode("th", { class: "text-caption" }, "原始名称"),
                                _createElementVNode("th", { class: "text-caption" }, "命名后"),
                                _createElementVNode("th", { class: "text-caption" }, "状态"),
                                _createElementVNode("th", { class: "text-caption" }, "操作")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (r) => {
                                return (_openBlock(), _createElementBlock("tr", {
                                  key: r.hash
                                }, [
                                  _createElementVNode("td", _hoisted_10, _toDisplayString(r.time), 1),
                                  _createElementVNode("td", {
                                    class: "text-caption dm-ellipsis",
                                    title: r.original_name
                                  }, _toDisplayString(r.original_name), 9, _hoisted_11),
                                  _createElementVNode("td", {
                                    class: "text-caption dm-ellipsis",
                                    title: r.after_name
                                  }, _toDisplayString(r.after_name), 9, _hoisted_12),
                                  _createElementVNode("td", null, [
                                    _createVNode(_component_VChip, {
                                      size: "x-small",
                                      color: r.success ? 'success' : 'error',
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(r.success ? '成功' : (r.reason || '失败')), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["color"])
                                  ]),
                                  _createElementVNode("td", null, [
                                    _createElementVNode("div", _hoisted_13, [
                                      _createVNode(_component_VBtn, {
                                        size: "x-small",
                                        variant: "tonal",
                                        color: "primary",
                                        onClick: $event => (doRetryRename(r.hash)),
                                        loading: retryingHash.value === r.hash
                                      }, {
                                        default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                                          _createTextVNode("补刀", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick", "loading"]),
                                      (r.success)
                                        ? (_openBlock(), _createBlock(_component_VBtn, {
                                            key: 0,
                                            size: "x-small",
                                            variant: "tonal",
                                            color: "warning",
                                            onClick: $event => (doRecovery(r.hash))
                                          }, {
                                            default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
                                              _createTextVNode("恢复", -1)
                                            ]))]),
                                            _: 1
                                          }, 8, ["onClick"]))
                                        : _createCommentVNode("", true),
                                      _createVNode(_component_VBtn, {
                                        size: "x-small",
                                        variant: "text",
                                        color: "error",
                                        onClick: $event => (doDelete(r.hash))
                                      }, {
                                        default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
                                          _createTextVNode("删除", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["onClick"])
                                    ])
                                  ])
                                ]))
                              }), 128))
                            ])
                          ]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_14, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (r) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: r.hash,
                            class: "dm-record-card dm-history-card"
                          }, [
                            _createElementVNode("div", _hoisted_15, [
                              _createElementVNode("div", {
                                class: "dm-record-title",
                                title: r.after_name || r.original_name
                              }, _toDisplayString(r.after_name || r.original_name || r.hash), 9, _hoisted_16),
                              _createVNode(_component_VChip, {
                                class: "dm-record-status",
                                size: "x-small",
                                color: r.success ? 'success' : 'error',
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(r.success ? '成功' : (r.reason || '失败')), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("div", _hoisted_17, [
                              _createElementVNode("div", _hoisted_18, [
                                _cache[12] || (_cache[12] = _createElementVNode("span", { class: "dm-record-label" }, "时间", -1)),
                                _createElementVNode("span", _hoisted_19, _toDisplayString(r.time || '-'), 1)
                              ]),
                              _createElementVNode("div", _hoisted_20, [
                                _cache[13] || (_cache[13] = _createElementVNode("span", { class: "dm-record-label" }, "原始", -1)),
                                _createElementVNode("span", {
                                  class: "dm-record-value",
                                  title: r.original_name
                                }, _toDisplayString(r.original_name || '-'), 9, _hoisted_21)
                              ]),
                              _createElementVNode("div", _hoisted_22, [
                                _cache[14] || (_cache[14] = _createElementVNode("span", { class: "dm-record-label" }, "命名后", -1)),
                                _createElementVNode("span", {
                                  class: "dm-record-value",
                                  title: r.after_name
                                }, _toDisplayString(r.after_name || '-'), 9, _hoisted_23)
                              ])
                            ]),
                            _createElementVNode("div", _hoisted_24, [
                              _createVNode(_component_VBtn, {
                                size: "x-small",
                                variant: "tonal",
                                color: "primary",
                                "prepend-icon": "mdi-auto-fix",
                                onClick: $event => (doRetryRename(r.hash)),
                                loading: retryingHash.value === r.hash
                              }, {
                                default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                                  _createTextVNode("补刀", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick", "loading"]),
                              (r.success)
                                ? (_openBlock(), _createBlock(_component_VBtn, {
                                    key: 0,
                                    size: "x-small",
                                    variant: "tonal",
                                    color: "warning",
                                    "prepend-icon": "mdi-undo",
                                    onClick: $event => (doRecovery(r.hash))
                                  }, {
                                    default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                                      _createTextVNode("恢复", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]))
                                : _createCommentVNode("", true),
                              _createVNode(_component_VBtn, {
                                size: "x-small",
                                variant: "text",
                                color: "error",
                                "prepend-icon": "mdi-delete-outline",
                                onClick: $event => (doDelete(r.hash))
                              }, {
                                default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                                  _createTextVNode("删除", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick"])
                            ])
                          ]))
                        }), 128))
                      ])
                    ], 64)),
                (total.value > pageSize)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_25, [
                      _createVNode(_component_VBtn, {
                        size: "x-small",
                        variant: "tonal",
                        icon: "mdi-chevron-left",
                        disabled: page.value <= 1,
                        onClick: prevPage,
                        class: "mr-2"
                      }, null, 8, ["disabled"]),
                      _createElementVNode("span", _hoisted_26, _toDisplayString(page.value) + " / " + _toDisplayString(totalPages.value) + "（共 " + _toDisplayString(total.value) + " 条）", 1),
                      _createVNode(_component_VBtn, {
                        size: "x-small",
                        variant: "tonal",
                        icon: "mdi-chevron-right",
                        disabled: page.value >= totalPages.value,
                        onClick: nextPage,
                        class: "ml-2"
                      }, null, 8, ["disabled"])
                    ]))
                  : _createCommentVNode("", true)
              ]))
            : (activeTab.value === 'archive')
              ? (_openBlock(), _createElementBlock("section", _hoisted_27, [
                  _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "归档记录", -1)),
                  (archiveRecords.value.length === 0)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-archive-outline",
                          size: "48",
                          color: "grey-lighten-1",
                          class: "mb-2"
                        }),
                        _cache[18] || (_cache[18] = _createElementVNode("div", null, "暂无归档记录", -1))
                      ]))
                    : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                        _createElementVNode("div", _hoisted_29, [
                          _createVNode(_component_VTable, {
                            density: "compact",
                            class: "dm-table"
                          }, {
                            default: _withCtx(() => [
                              _cache[21] || (_cache[21] = _createElementVNode("thead", null, [
                                _createElementVNode("tr", null, [
                                  _createElementVNode("th", { class: "text-caption" }, "归档时间"),
                                  _createElementVNode("th", { class: "text-caption" }, "名称"),
                                  _createElementVNode("th", { class: "text-caption" }, "分类"),
                                  _createElementVNode("th", { class: "text-caption" }, "次数"),
                                  _createElementVNode("th", { class: "text-caption" }, "原因"),
                                  _createElementVNode("th", { class: "text-caption" }, "操作")
                                ])
                              ], -1)),
                              _createElementVNode("tbody", null, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveRecords.value, (r) => {
                                  return (_openBlock(), _createElementBlock("tr", {
                                    key: r.hash
                                  }, [
                                    _createElementVNode("td", _hoisted_30, _toDisplayString(r.archived_at || r.last_failed_at), 1),
                                    _createElementVNode("td", {
                                      class: "text-caption dm-ellipsis",
                                      title: r.name
                                    }, _toDisplayString(r.name || r.hash), 9, _hoisted_31),
                                    _createElementVNode("td", null, [
                                      _createVNode(_component_VChip, {
                                        size: "x-small",
                                        color: "warning",
                                        variant: "tonal"
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(r.category_label || r.category), 1)
                                        ]),
                                        _: 2
                                      }, 1024)
                                    ]),
                                    _createElementVNode("td", _hoisted_32, _toDisplayString(r.fail_count), 1),
                                    _createElementVNode("td", {
                                      class: "text-caption dm-ellipsis",
                                      title: r.archive_reason || r.reason
                                    }, _toDisplayString(r.archive_reason || r.reason), 9, _hoisted_33),
                                    _createElementVNode("td", null, [
                                      _createElementVNode("div", _hoisted_34, [
                                        _createVNode(_component_VBtn, {
                                          size: "x-small",
                                          variant: "tonal",
                                          color: "primary",
                                          onClick: $event => (restoreArchive(r.hash)),
                                          loading: restoringHash.value === r.hash
                                        }, {
                                          default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                                            _createTextVNode("恢复", -1)
                                          ]))]),
                                          _: 1
                                        }, 8, ["onClick", "loading"]),
                                        _createVNode(_component_VBtn, {
                                          size: "x-small",
                                          variant: "text",
                                          color: "error",
                                          onClick: $event => (deleteArchive(r.hash)),
                                          loading: deletingHash.value === r.hash
                                        }, {
                                          default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                                            _createTextVNode("删除", -1)
                                          ]))]),
                                          _: 1
                                        }, 8, ["onClick", "loading"])
                                      ])
                                    ])
                                  ]))
                                }), 128))
                              ])
                            ]),
                            _: 1
                          })
                        ]),
                        _createElementVNode("div", _hoisted_35, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveRecords.value, (r) => {
                            return (_openBlock(), _createElementBlock("article", {
                              key: r.hash,
                              class: "dm-record-card dm-archive-card"
                            }, [
                              _createElementVNode("div", _hoisted_36, [
                                _createElementVNode("div", {
                                  class: "dm-record-title",
                                  title: r.name || r.hash
                                }, _toDisplayString(r.name || r.hash), 9, _hoisted_37),
                                _createVNode(_component_VChip, {
                                  class: "dm-record-status",
                                  size: "x-small",
                                  color: "warning",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(r.category_label || r.category), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _createElementVNode("div", _hoisted_38, [
                                _createElementVNode("div", _hoisted_39, [
                                  _cache[22] || (_cache[22] = _createElementVNode("span", { class: "dm-record-label" }, "归档", -1)),
                                  _createElementVNode("span", _hoisted_40, _toDisplayString(r.archived_at || r.last_failed_at || '-'), 1)
                                ]),
                                _createElementVNode("div", _hoisted_41, [
                                  _cache[23] || (_cache[23] = _createElementVNode("span", { class: "dm-record-label" }, "次数", -1)),
                                  _createElementVNode("span", _hoisted_42, _toDisplayString(r.fail_count || 0), 1)
                                ]),
                                _createElementVNode("div", _hoisted_43, [
                                  _cache[24] || (_cache[24] = _createElementVNode("span", { class: "dm-record-label" }, "原因", -1)),
                                  _createElementVNode("span", {
                                    class: "dm-record-value",
                                    title: r.archive_reason || r.reason
                                  }, _toDisplayString(r.archive_reason || r.reason || '-'), 9, _hoisted_44)
                                ])
                              ]),
                              _createElementVNode("div", _hoisted_45, [
                                _createVNode(_component_VBtn, {
                                  size: "x-small",
                                  variant: "tonal",
                                  color: "primary",
                                  "prepend-icon": "mdi-archive-arrow-up-outline",
                                  onClick: $event => (restoreArchive(r.hash)),
                                  loading: restoringHash.value === r.hash
                                }, {
                                  default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                                    _createTextVNode("恢复", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick", "loading"]),
                                _createVNode(_component_VBtn, {
                                  size: "x-small",
                                  variant: "text",
                                  color: "error",
                                  "prepend-icon": "mdi-delete-outline",
                                  onClick: $event => (deleteArchive(r.hash)),
                                  loading: deletingHash.value === r.hash
                                }, {
                                  default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
                                    _createTextVNode("删除", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick", "loading"])
                              ])
                            ]))
                          }), 128))
                        ])
                      ], 64)),
                  (archiveTotal.value > pageSize)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_46, [
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-left",
                          disabled: archivePage.value <= 1,
                          onClick: prevArchivePage,
                          class: "mr-2"
                        }, null, 8, ["disabled"]),
                        _createElementVNode("span", _hoisted_47, _toDisplayString(archivePage.value) + " / " + _toDisplayString(archiveTotalPages.value) + "（共 " + _toDisplayString(archiveTotal.value) + " 条）", 1),
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-right",
                          disabled: archivePage.value >= archiveTotalPages.value,
                          onClick: nextArchivePage,
                          class: "ml-2"
                        }, null, 8, ["disabled"])
                      ]))
                    : _createCommentVNode("", true)
                ]))
              : (_openBlock(), _createElementBlock("section", _hoisted_48, [
                  (diagnostics.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_49, [
                        _createElementVNode("div", _hoisted_50, [
                          _createElementVNode("div", _hoisted_51, [
                            _cache[28] || (_cache[28] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "版本", -1)),
                            _createElementVNode("div", _hoisted_52, _toDisplayString(diagnostics.value?.plugin?.version), 1)
                          ]),
                          _createElementVNode("div", _hoisted_53, [
                            _cache[29] || (_cache[29] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "源下载器", -1)),
                            _createElementVNode("div", _hoisted_54, _toDisplayString(diagnostics.value?.downloaders?.from?.name || '未配置'), 1),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: diagnostics.value?.downloaders?.from?.available ? 'success' : 'warning',
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(diagnostics.value?.downloaders?.from?.message), 1)
                              ]),
                              _: 1
                            }, 8, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_55, [
                            _cache[30] || (_cache[30] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "目标下载器", -1)),
                            _createElementVNode("div", _hoisted_56, _toDisplayString(diagnostics.value?.downloaders?.to?.name || '未配置'), 1),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: diagnostics.value?.downloaders?.to?.available ? 'success' : 'warning',
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(diagnostics.value?.downloaders?.to?.message), 1)
                              ]),
                              _: 1
                            }, 8, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_57, [
                            _cache[31] || (_cache[31] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "补刀归档", -1)),
                            _createElementVNode("div", _hoisted_58, _toDisplayString(diagnostics.value?.rename_archive?.archived || 0) + " 条", 1),
                            _createElementVNode("div", _hoisted_59, "连续失败 " + _toDisplayString(diagnostics.value?.rename_archive?.active_failed || 0) + " · 阈值 " + _toDisplayString(diagnostics.value?.rename_archive?.threshold || 3), 1)
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_60, [
                          _createElementVNode("div", _hoisted_61, [
                            _createElementVNode("div", _hoisted_62, [
                              _createElementVNode("span", _hoisted_63, [
                                _createVNode(_component_VIcon, {
                                  icon: "mdi-stethoscope",
                                  size: "20"
                                })
                              ]),
                              _cache[32] || (_cache[32] = _createElementVNode("span", null, "运行诊断", -1))
                            ]),
                            _createElementVNode("div", _hoisted_64, [
                              _createElementVNode("strong", null, _toDisplayString(diagnosticsOkCount.value) + " / " + _toDisplayString(diagnosticsCards.value.length), 1),
                              _cache[33] || (_cache[33] = _createElementVNode("span", null, "正常", -1)),
                              (diagnosticsAttentionCount.value)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_65, "· " + _toDisplayString(diagnosticsAttentionCount.value) + " 项关注", 1))
                                : _createCommentVNode("", true)
                            ])
                          ]),
                          _createElementVNode("div", _hoisted_66, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnosticsCards.value, (item) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: item.label,
                                class: _normalizeClass(["dm-diagnostic-card", `dm-diagnostic-card--${item.status || 'off'}`])
                              }, [
                                _createElementVNode("div", _hoisted_67, [
                                  _createVNode(_component_VIcon, {
                                    icon: item.icon,
                                    size: "22"
                                  }, null, 8, ["icon"])
                                ]),
                                _createElementVNode("div", _hoisted_68, [
                                  _createElementVNode("div", _hoisted_69, _toDisplayString(item.label), 1),
                                  _createElementVNode("div", _hoisted_70, _toDisplayString(item.detail), 1),
                                  _createElementVNode("div", _hoisted_71, _toDisplayString(item.statusText), 1)
                                ])
                              ], 2))
                            }), 128))
                          ]),
                          _createElementVNode("div", _hoisted_72, [
                            _cache[34] || (_cache[34] = _createElementVNode("span", null, "按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。", -1)),
                            (diagnosticsAttentionCount.value)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_73, "关注项不阻断运行"))
                              : _createCommentVNode("", true)
                          ])
                        ]),
                        _createElementVNode("div", null, [
                          _cache[36] || (_cache[36] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "最近失败", -1)),
                          (!diagnostics.value?.rename_history?.recent_failures?.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_74, "暂无失败记录"))
                            : (_openBlock(), _createElementBlock("div", _hoisted_75, [
                                _createVNode(_component_VTable, {
                                  density: "compact",
                                  class: "dm-table"
                                }, {
                                  default: _withCtx(() => [
                                    _cache[35] || (_cache[35] = _createElementVNode("thead", null, [
                                      _createElementVNode("tr", null, [
                                        _createElementVNode("th", { class: "text-caption" }, "时间"),
                                        _createElementVNode("th", { class: "text-caption" }, "名称"),
                                        _createElementVNode("th", { class: "text-caption" }, "原因")
                                      ])
                                    ], -1)),
                                    _createElementVNode("tbody", null, [
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnostics.value.rename_history.recent_failures, (item) => {
                                        return (_openBlock(), _createElementBlock("tr", {
                                          key: item.hash
                                        }, [
                                          _createElementVNode("td", _hoisted_76, _toDisplayString(item.time), 1),
                                          _createElementVNode("td", {
                                            class: "text-caption dm-ellipsis",
                                            title: item.name
                                          }, _toDisplayString(item.name), 9, _hoisted_77),
                                          _createElementVNode("td", _hoisted_78, _toDisplayString(item.reason), 1)
                                        ]))
                                      }), 128))
                                    ])
                                  ]),
                                  _: 1
                                })
                              ]))
                        ])
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_79, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-stethoscope",
                          size: "48",
                          color: "grey-lighten-1",
                          class: "mb-2"
                        }),
                        _cache[37] || (_cache[37] = _createElementVNode("div", null, "点击刷新诊断", -1))
                      ]))
                ]))
      ])
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-31fe3a40"]]);

export { Page as default };
