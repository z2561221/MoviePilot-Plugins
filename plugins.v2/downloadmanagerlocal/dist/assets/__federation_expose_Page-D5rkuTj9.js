import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-DxfxZJCG.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


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
const _hoisted_9 = { class: "text-caption text-no-wrap" };
const _hoisted_10 = ["title"];
const _hoisted_11 = ["title"];
const _hoisted_12 = { class: "d-flex ga-1" };
const _hoisted_13 = {
  key: 2,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_14 = { class: "text-caption mx-1" };
const _hoisted_15 = {
  key: 4,
  class: "dm-pane"
};
const _hoisted_16 = {
  key: 0,
  class: "dm-state text-center text-medium-emphasis"
};
const _hoisted_17 = { class: "text-caption text-no-wrap" };
const _hoisted_18 = ["title"];
const _hoisted_19 = { class: "text-caption" };
const _hoisted_20 = ["title"];
const _hoisted_21 = { class: "d-flex ga-1" };
const _hoisted_22 = {
  key: 2,
  class: "d-flex align-center justify-center pa-3"
};
const _hoisted_23 = { class: "text-caption mx-1" };
const _hoisted_24 = {
  key: 5,
  class: "dm-pane"
};
const _hoisted_25 = {
  key: 0,
  class: "dm-diagnostics"
};
const _hoisted_26 = { class: "dm-stat-grid mb-3" };
const _hoisted_27 = { class: "dm-stat" };
const _hoisted_28 = { class: "text-subtitle-2" };
const _hoisted_29 = { class: "dm-stat" };
const _hoisted_30 = { class: "text-subtitle-2" };
const _hoisted_31 = { class: "dm-stat" };
const _hoisted_32 = { class: "text-subtitle-2" };
const _hoisted_33 = { class: "dm-stat" };
const _hoisted_34 = { class: "text-subtitle-2" };
const _hoisted_35 = { class: "text-caption" };
const _hoisted_36 = { class: "dm-checks mb-3" };
const _hoisted_37 = { class: "text-body-2" };
const _hoisted_38 = { class: "d-flex align-center ga-2" };
const _hoisted_39 = { class: "text-caption text-medium-emphasis" };
const _hoisted_40 = {
  key: 0,
  class: "text-caption text-medium-emphasis py-2"
};
const _hoisted_41 = { class: "text-caption text-no-wrap" };
const _hoisted_42 = ["title"];
const _hoisted_43 = { class: "text-caption" };
const _hoisted_44 = {
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

function checkColor(status) {
  if (status === 'ok') return 'success'
  if (status === 'warn') return 'warning'
  if (status === 'off') return 'default'
  return 'default'
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
          class: "py-2"
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
                  : (_openBlock(), _createBlock(_component_VTable, {
                      key: 1,
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
                              _createElementVNode("td", _hoisted_9, _toDisplayString(r.time), 1),
                              _createElementVNode("td", {
                                class: "text-caption dm-ellipsis",
                                title: r.original_name
                              }, _toDisplayString(r.original_name), 9, _hoisted_10),
                              _createElementVNode("td", {
                                class: "text-caption dm-ellipsis",
                                title: r.after_name
                              }, _toDisplayString(r.after_name), 9, _hoisted_11),
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
                                _createElementVNode("div", _hoisted_12, [
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
                    })),
                (total.value > pageSize)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_13, [
                      _createVNode(_component_VBtn, {
                        size: "x-small",
                        variant: "tonal",
                        icon: "mdi-chevron-left",
                        disabled: page.value <= 1,
                        onClick: prevPage,
                        class: "mr-2"
                      }, null, 8, ["disabled"]),
                      _createElementVNode("span", _hoisted_14, _toDisplayString(page.value) + " / " + _toDisplayString(totalPages.value) + "（共 " + _toDisplayString(total.value) + " 条）", 1),
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
              ? (_openBlock(), _createElementBlock("section", _hoisted_15, [
                  _cache[16] || (_cache[16] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "归档记录", -1)),
                  (archiveRecords.value.length === 0)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_16, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-archive-outline",
                          size: "48",
                          color: "grey-lighten-1",
                          class: "mb-2"
                        }),
                        _cache[12] || (_cache[12] = _createElementVNode("div", null, "暂无归档记录", -1))
                      ]))
                    : (_openBlock(), _createBlock(_component_VTable, {
                        key: 1,
                        density: "compact",
                        class: "dm-table"
                      }, {
                        default: _withCtx(() => [
                          _cache[15] || (_cache[15] = _createElementVNode("thead", null, [
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
                                _createElementVNode("td", _hoisted_17, _toDisplayString(r.archived_at || r.last_failed_at), 1),
                                _createElementVNode("td", {
                                  class: "text-caption dm-ellipsis",
                                  title: r.name
                                }, _toDisplayString(r.name || r.hash), 9, _hoisted_18),
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
                                _createElementVNode("td", _hoisted_19, _toDisplayString(r.fail_count), 1),
                                _createElementVNode("td", {
                                  class: "text-caption dm-ellipsis",
                                  title: r.archive_reason || r.reason
                                }, _toDisplayString(r.archive_reason || r.reason), 9, _hoisted_20),
                                _createElementVNode("td", null, [
                                  _createElementVNode("div", _hoisted_21, [
                                    _createVNode(_component_VBtn, {
                                      size: "x-small",
                                      variant: "tonal",
                                      color: "primary",
                                      onClick: $event => (restoreArchive(r.hash)),
                                      loading: restoringHash.value === r.hash
                                    }, {
                                      default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
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
                                      default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
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
                      })),
                  (archiveTotal.value > pageSize)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_22, [
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-left",
                          disabled: archivePage.value <= 1,
                          onClick: prevArchivePage,
                          class: "mr-2"
                        }, null, 8, ["disabled"]),
                        _createElementVNode("span", _hoisted_23, _toDisplayString(archivePage.value) + " / " + _toDisplayString(archiveTotalPages.value) + "（共 " + _toDisplayString(archiveTotal.value) + " 条）", 1),
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
              : (_openBlock(), _createElementBlock("section", _hoisted_24, [
                  (diagnostics.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_25, [
                        _createElementVNode("div", _hoisted_26, [
                          _createElementVNode("div", _hoisted_27, [
                            _cache[17] || (_cache[17] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "版本", -1)),
                            _createElementVNode("div", _hoisted_28, _toDisplayString(diagnostics.value?.plugin?.version), 1)
                          ]),
                          _createElementVNode("div", _hoisted_29, [
                            _cache[18] || (_cache[18] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "源下载器", -1)),
                            _createElementVNode("div", _hoisted_30, _toDisplayString(diagnostics.value?.downloaders?.from?.name || '未配置'), 1),
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
                          _createElementVNode("div", _hoisted_31, [
                            _cache[19] || (_cache[19] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "目标下载器", -1)),
                            _createElementVNode("div", _hoisted_32, _toDisplayString(diagnostics.value?.downloaders?.to?.name || '未配置'), 1),
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
                          _createElementVNode("div", _hoisted_33, [
                            _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "补刀归档", -1)),
                            _createElementVNode("div", _hoisted_34, _toDisplayString(diagnostics.value?.rename_archive?.archived || 0) + " 条", 1),
                            _createElementVNode("div", _hoisted_35, "连续失败 " + _toDisplayString(diagnostics.value?.rename_archive?.active_failed || 0) + " · 阈值 " + _toDisplayString(diagnostics.value?.rename_archive?.threshold || 3), 1)
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_36, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(diagnostics.value.checks, (item) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: item.label,
                              class: "dm-check-row"
                            }, [
                              _createElementVNode("div", _hoisted_37, _toDisplayString(item.label), 1),
                              _createElementVNode("div", _hoisted_38, [
                                _createElementVNode("span", _hoisted_39, _toDisplayString(item.detail), 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: checkColor(item.status),
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.status), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ])
                            ]))
                          }), 128))
                        ]),
                        _createElementVNode("div", null, [
                          _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "最近失败", -1)),
                          (!diagnostics.value?.rename_history?.recent_failures?.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_40, "暂无失败记录"))
                            : (_openBlock(), _createBlock(_component_VTable, {
                                key: 1,
                                density: "compact",
                                class: "dm-table"
                              }, {
                                default: _withCtx(() => [
                                  _cache[21] || (_cache[21] = _createElementVNode("thead", null, [
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
                                        _createElementVNode("td", _hoisted_41, _toDisplayString(item.time), 1),
                                        _createElementVNode("td", {
                                          class: "text-caption dm-ellipsis",
                                          title: item.name
                                        }, _toDisplayString(item.name), 9, _hoisted_42),
                                        _createElementVNode("td", _hoisted_43, _toDisplayString(item.reason), 1)
                                      ]))
                                    }), 128))
                                  ])
                                ]),
                                _: 1
                              }))
                        ])
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_44, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-stethoscope",
                          size: "48",
                          color: "grey-lighten-1",
                          class: "mb-2"
                        }),
                        _cache[23] || (_cache[23] = _createElementVNode("div", null, "点击刷新诊断", -1))
                      ]))
                ]))
      ])
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-0eb5ad77"]]);

export { Page as default };
