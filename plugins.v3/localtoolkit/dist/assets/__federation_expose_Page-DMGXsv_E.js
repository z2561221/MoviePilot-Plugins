import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as apiPost, b as apiGet, p as pluginApiPath } from './_plugin-vue_export-helper-aSpYeKwD.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "lt-page" };
const _hoisted_2 = { class: "lt-layout" };
const _hoisted_3 = { class: "lt-side" };
const _hoisted_4 = { class: "lt-main" };
const _hoisted_5 = {
  key: 2,
  class: "lt-state"
};
const _hoisted_6 = {
  key: 3,
  class: "lt-pane"
};
const _hoisted_7 = { class: "lt-stat-grid mt-3" };
const _hoisted_8 = { class: "lt-stat-content" };
const _hoisted_9 = { class: "lt-stat-label" };
const _hoisted_10 = { class: "lt-stat-value" };
const _hoisted_11 = { class: "lt-stat-detail" };
const _hoisted_12 = { class: "lt-panel mt-3" };
const _hoisted_13 = { class: "lt-section-heading" };
const _hoisted_14 = { class: "lt-flow-grid mt-3" };
const _hoisted_15 = { class: "lt-flow-index" };
const _hoisted_16 = { class: "lt-flow-copy" };
const _hoisted_17 = {
  key: 0,
  class: "lt-attention-panel mt-3"
};
const _hoisted_18 = { class: "lt-section-heading" };
const _hoisted_19 = { class: "lt-attention-list mt-3" };
const _hoisted_20 = { class: "min-w-0" };
const _hoisted_21 = { class: "text-caption text-medium-emphasis lt-break-text" };
const _hoisted_22 = { class: "lt-panel mt-3" };
const _hoisted_23 = { class: "lt-section-heading" };
const _hoisted_24 = { class: "lt-action-row mt-3" };
const _hoisted_25 = {
  key: 4,
  class: "lt-pane"
};
const _hoisted_26 = { class: "lt-section-heading" };
const _hoisted_27 = { class: "lt-action-row lt-action-row--right" };
const _hoisted_28 = { class: "lt-plan-summary mt-3" };
const _hoisted_29 = { class: "lt-table-wrap mt-3" };
const _hoisted_30 = ["title"];
const _hoisted_31 = { key: 0 };
const _hoisted_32 = { class: "lt-mobile-list" };
const _hoisted_33 = { class: "lt-record-head" };
const _hoisted_34 = { class: "lt-record-meta" };
const _hoisted_35 = {
  key: 0,
  class: "lt-empty"
};
const _hoisted_36 = {
  key: 1,
  class: "lt-pagination"
};
const _hoisted_37 = {
  key: 5,
  class: "lt-pane"
};
const _hoisted_38 = { class: "lt-section-heading" };
const _hoisted_39 = { class: "lt-table-wrap mt-3" };
const _hoisted_40 = { class: "text-no-wrap" };
const _hoisted_41 = ["title"];
const _hoisted_42 = { key: 0 };
const _hoisted_43 = { class: "lt-mobile-list" };
const _hoisted_44 = { class: "lt-record-head" };
const _hoisted_45 = { class: "lt-record-meta" };
const _hoisted_46 = { class: "lt-record-summary" };
const _hoisted_47 = {
  key: 0,
  class: "lt-empty"
};
const _hoisted_48 = {
  key: 0,
  class: "lt-pagination"
};

const {computed,onMounted,ref} = await importShared('vue');

const cleanupPlanPageSize = 15;
const historyPageSize = 15;

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const activeTab = ref('overview');
const status = ref(null);
const cleanupPlan = ref({ total: 0, page: 1, page_size: 15, total_pages: 1, items: [], batch_size: 10 });
const cleanupPlanPage = ref(1);
const history = ref([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const loading = ref(false);
const loadingAction = ref('');
const error = ref('');
const actionMessage = ref('');
const actionOk = ref(false);

const tabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'cleanup_plan', title: '清理计划', icon: 'mdi-playlist-check' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

const historyTotalPages = computed(() => Math.max(1, Math.ceil((historyTotal.value || 0) / historyPageSize)));
const cleanupPlanTotalPages = computed(() => Math.max(1, Number(cleanupPlan.value?.total_pages || Math.ceil((cleanupPlan.value?.total || 0) / cleanupPlanPageSize))));
const cleanupStatus = computed(() => status.value?.modules?.library_cleanup || {});
const batchSize = computed(() => Number(cleanupPlan.value?.batch_size || cleanupStatus.value?.cycle_batch_size || 10));
const overviewCards = computed(() => [
  {
    title: '周期状态',
    value: cleanupStatus.value.enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.cron ? `周期 ${cleanupStatus.value.cron}` : '未设置清理周期',
    icon: 'mdi-calendar-clock-outline',
    color: cleanupStatus.value.enabled ? 'success' : 'default',
  },
  {
    title: '清理计划',
    value: `${cleanupPlan.value.total || 0} 部`,
    detail: cleanupStatus.value.auto_delete ? '自动删除已开启' : '仅扫描入队，不自动删除',
    icon: 'mdi-playlist-check',
    color: cleanupPlan.value.total ? 'warning' : 'primary',
  },
  {
    title: '本周期数量',
    value: `${batchSize.value} 部`,
    detail: `冷却 ${cleanupPlan.value.cooldown_minutes || cleanupStatus.value.cooldown_minutes || 0} 分钟`,
    icon: 'mdi-counter',
    color: 'primary',
  },
  {
    title: '下次执行',
    value: cleanupPlan.value.next_cycle_at ? '冷却中' : '等待周期',
    detail: cleanupPlan.value.next_cycle_at || '当前没有冷却中的周期',
    icon: 'mdi-timer-sand-outline',
    color: cleanupPlan.value.next_cycle_at ? 'info' : 'default',
  },
]);
const attentionItems = computed(() => {
  const items = [];
  if (cleanupStatus.value.last_error) {
    items.push({ icon: 'mdi-alert-circle-outline', color: 'error', title: '最近运行异常', detail: cleanupStatus.value.last_error });
  }
  if (cleanupPlan.value.total) {
    items.push({ icon: 'mdi-playlist-check', color: 'warning', title: '计划待处理', detail: `${cleanupPlan.value.total} 部对象等待清理` });
  }
  if (cleanupPlan.value.next_cycle_at) {
    items.push({ icon: 'mdi-timer-sand-outline', color: 'info', title: '周期冷却中', detail: `下次可执行：${cleanupPlan.value.next_cycle_at}` });
  }
  return items
});

function apiPath(path) {
  return pluginApiPath(props.pluginId, path)
}

async function loadStatus() {
  status.value = await apiGet(props.api, apiPath('local_toolkit/status'));
}

async function loadPlan() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/cleanup_plan?page=${cleanupPlanPage.value}&page_size=${cleanupPlanPageSize}`));
  cleanupPlan.value = data || { total: 0, page: 1, page_size: cleanupPlanPageSize, total_pages: 1, items: [], batch_size: 10 };
  cleanupPlanPage.value = Number(cleanupPlan.value.page || cleanupPlanPage.value);
}

async function loadOverview() {
  await Promise.all([loadStatus(), loadPlan()]);
}

async function loadHistory() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/history?page=${historyPage.value}&page_size=${historyPageSize}`));
  history.value = data?.items || [];
  historyTotal.value = data?.total || 0;
}

async function refreshActive() {
  loading.value = true;
  error.value = '';
  try {
    if (activeTab.value === 'overview') await loadOverview();
    else if (activeTab.value === 'cleanup_plan') await Promise.all([loadStatus(), loadPlan()]);
    else await loadHistory();
  } catch (err) {
    error.value = String(err);
  } finally {
    loading.value = false;
  }
}

async function selectTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key;
  await refreshActive();
}

async function refreshAfterAction() {
  await Promise.all([loadStatus(), loadPlan()]);
  if (activeTab.value === 'history') await loadHistory();
}

async function runModule(moduleKey) {
  loadingAction.value = moduleKey;
  actionMessage.value = '';
  try {
    const response = await apiPost(props.api, apiPath(`local_toolkit/run/${moduleKey}`));
    actionOk.value = response?.success !== false;
    actionMessage.value = response?.message || response?.summary || '运行完成';
  } catch (err) {
    actionOk.value = false;
    actionMessage.value = String(err);
  } finally {
    loadingAction.value = '';
    await refreshAfterAction();
  }
}

async function scanPlan() {
  loadingAction.value = 'scan_plan';
  actionMessage.value = '';
  try {
    const response = await apiPost(props.api, apiPath('local_toolkit/cleanup_plan/scan'));
    actionOk.value = response?.success !== false;
    actionMessage.value = response?.message || response?.summary || '清理计划已更新';
  } catch (err) {
    actionOk.value = false;
    actionMessage.value = String(err);
  } finally {
    loadingAction.value = '';
    await refreshAfterAction();
  }
}

async function clearPlan() {
  if (!window.confirm('确认清空当前清理计划吗？这不会删除媒体库条目。')) return
  loadingAction.value = 'clear_plan';
  actionMessage.value = '';
  try {
    const response = await apiPost(props.api, apiPath('local_toolkit/cleanup_plan/clear'));
    actionOk.value = response?.success !== false;
    actionMessage.value = response?.message || response?.summary || '清理计划已清空';
  } catch (err) {
    actionOk.value = false;
    actionMessage.value = String(err);
  } finally {
    loadingAction.value = '';
    await refreshAfterAction();
  }
}

function planStatus(item) {
  return item.last_error || '待处理'
}

function planStatusColor(item) {
  return item.last_error ? 'warning' : 'primary'
}

function historyStatus(item) {
  return item.status === 'success' ? '成功' : item.status === 'failed' ? '失败' : item.status || '未知'
}

function historyStatusColor(item) {
  return item.status === 'success' ? 'success' : item.status === 'failed' ? 'error' : 'default'
}

function prevHistoryPage() {
  if (historyPage.value <= 1) return
  historyPage.value -= 1;
  loadHistory();
}

function nextHistoryPage() {
  if (historyPage.value >= historyTotalPages.value) return
  historyPage.value += 1;
  loadHistory();
}

function prevCleanupPlanPage() {
  if (cleanupPlanPage.value <= 1) return
  cleanupPlanPage.value -= 1;
  loadPlan();
}

function nextCleanupPlanPage() {
  if (cleanupPlanPage.value >= cleanupPlanTotalPages.value) return
  cleanupPlanPage.value += 1;
  loadPlan();
}

onMounted(loadOverview);

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
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTable = _resolveComponent("VTable");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "lt-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-tools",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[9] || (_cache[9] = _createElementVNode("div", { class: "lt-toolbar-title" }, "工具中心", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: refreshActive,
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none me-2",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
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
          class: "lt-side-list py-2"
        }, {
          default: _withCtx(() => [
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
              return _createVNode(_component_VListItem, {
                key: tab.key,
                active: activeTab.value === tab.key,
                color: "primary",
                rounded: "lg",
                class: "lt-side-item",
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
        (actionMessage.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: actionOk.value ? 'success' : 'error',
              variant: "tonal",
              class: "mb-3",
              closable: "",
              density: "compact"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(actionMessage.value), 1)
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
          : (activeTab.value === 'overview')
            ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                _cache[18] || (_cache[18] = _createElementVNode("div", { class: "lt-section-heading" }, [
                  _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "lt-section-title" }, "运行总览"),
                    _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "清理库存按“扫描、入队、倒序执行、复核”运行，其他工具保持按需执行。")
                  ])
                ], -1)),
                _createElementVNode("div", _hoisted_7, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewCards.value, (card) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: card.title,
                      class: _normalizeClass(["lt-stat", `lt-stat--${card.color}`])
                    }, [
                      _createVNode(_component_VAvatar, {
                        color: card.color,
                        variant: "tonal",
                        size: "32",
                        rounded: "lg"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VIcon, {
                            icon: card.icon,
                            size: "18"
                          }, null, 8, ["icon"])
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      _createElementVNode("div", _hoisted_8, [
                        _createElementVNode("div", _hoisted_9, _toDisplayString(card.title), 1),
                        _createElementVNode("div", _hoisted_10, _toDisplayString(card.value), 1),
                        _createElementVNode("div", _hoisted_11, _toDisplayString(card.detail), 1)
                      ])
                    ], 2))
                  }), 128))
                ]),
                _createElementVNode("section", _hoisted_12, [
                  _createElementVNode("div", _hoisted_13, [
                    _cache[10] || (_cache[10] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "运行链路"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "周期任务必须先完成扫描，删除阶段只消费持久化计划。")
                    ], -1)),
                    _createVNode(_component_VChip, {
                      size: "small",
                      color: "primary",
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("每周期 " + _toDisplayString(batchSize.value) + " 部", 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_14, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList([
                { icon: 'mdi-magnify-scan', title: '完整扫描', detail: '按当前筛选条件读取媒体库' },
                { icon: 'mdi-playlist-plus', title: '持久化入队', detail: '按服务器与条目 ID 去重' },
                { icon: 'mdi-sort-numeric-descending', title: '倒序执行', detail: `按设置数量处理 ${batchSize.value} 部` },
                { icon: 'mdi-check-decagram-outline', title: '删除复核', detail: '成功移除，异常对象留队重试' },
              ], (step, index) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: step.title,
                        class: "lt-flow-step"
                      }, [
                        _createElementVNode("div", _hoisted_15, _toDisplayString(index + 1), 1),
                        _createVNode(_component_VIcon, {
                          icon: step.icon,
                          color: "primary",
                          size: "22"
                        }, null, 8, ["icon"]),
                        _createElementVNode("div", _hoisted_16, [
                          _createElementVNode("strong", null, _toDisplayString(step.title), 1),
                          _createElementVNode("span", null, _toDisplayString(step.detail), 1)
                        ])
                      ]))
                    }), 128))
                  ])
                ]),
                (attentionItems.value.length)
                  ? (_openBlock(), _createElementBlock("section", _hoisted_17, [
                      _createElementVNode("div", _hoisted_18, [
                        _cache[11] || (_cache[11] = _createElementVNode("div", null, [
                          _createElementVNode("div", { class: "lt-section-title" }, "需要关注"),
                          _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "队列状态和异常会集中显示在这里。")
                        ], -1)),
                        _createVNode(_component_VChip, {
                          color: "warning",
                          size: "small",
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(attentionItems.value.length) + " 项", 1)
                          ]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_19, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(attentionItems.value, (item) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: `${item.title}-${item.detail}`,
                            class: "lt-attention-item"
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: item.icon,
                              color: item.color,
                              size: "19"
                            }, null, 8, ["icon", "color"]),
                            _createElementVNode("div", _hoisted_20, [
                              _createElementVNode("strong", null, _toDisplayString(item.title), 1),
                              _createElementVNode("div", _hoisted_21, _toDisplayString(item.detail), 1)
                            ])
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("section", _hoisted_22, [
                  _createElementVNode("div", _hoisted_23, [
                    _cache[13] || (_cache[13] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "快速操作"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "清理计划操作不会跳过扫描阶段。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      "prepend-icon": "mdi-format-list-bulleted",
                      class: "text-none",
                      onClick: _cache[2] || (_cache[2] = $event => (selectTab('cleanup_plan')))
                    }, {
                      default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                        _createTextVNode("查看计划", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_24, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-playlist-plus",
                      loading: loadingAction.value === 'scan_plan',
                      onClick: scanPlan
                    }, {
                      default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode("生成清理计划", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "error",
                      variant: "flat",
                      "prepend-icon": "mdi-delete-sweep-outline",
                      loading: loadingAction.value === 'library_cleanup',
                      onClick: _cache[3] || (_cache[3] = $event => (runModule('library_cleanup')))
                    }, {
                      default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                        _createTextVNode("执行一周期", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "text",
                      "prepend-icon": "mdi-magnify-scan",
                      loading: loadingAction.value === 'check_missing',
                      onClick: _cache[4] || (_cache[4] = $event => (runModule('check_missing')))
                    }, {
                      default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                        _createTextVNode("扫描缺集", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "warning",
                      variant: "text",
                      "prepend-icon": "mdi-database-refresh-outline",
                      loading: loadingAction.value === 'tmdb_cache',
                      onClick: _cache[5] || (_cache[5] = $event => (runModule('tmdb_cache')))
                    }, {
                      default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                        _createTextVNode("清理 TMDB", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ])
              ]))
            : (activeTab.value === 'cleanup_plan')
              ? (_openBlock(), _createElementBlock("section", _hoisted_25, [
                  _createElementVNode("div", _hoisted_26, [
                    _cache[22] || (_cache[22] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "清理计划"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "扫描完成后进入队列，执行阶段按倒序消费；数量取设置页配置。")
                    ], -1)),
                    _createElementVNode("div", _hoisted_27, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-playlist-plus",
                        loading: loadingAction.value === 'scan_plan',
                        onClick: scanPlan
                      }, {
                        default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                          _createTextVNode("生成计划", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "error",
                        variant: "flat",
                        "prepend-icon": "mdi-delete-sweep-outline",
                        loading: loadingAction.value === 'library_cleanup',
                        onClick: _cache[6] || (_cache[6] = $event => (runModule('library_cleanup')))
                      }, {
                        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                          _createTextVNode("执行一周期", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "warning",
                        variant: "text",
                        "prepend-icon": "mdi-playlist-remove",
                        disabled: !cleanupPlan.value.total,
                        loading: loadingAction.value === 'clear_plan',
                        onClick: clearPlan
                      }, {
                        default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                          _createTextVNode("清空计划", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"])
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_28, [
                    _createElementVNode("div", null, [
                      _cache[23] || (_cache[23] = _createElementVNode("span", null, "待处理对象", -1)),
                      _createElementVNode("strong", null, _toDisplayString(cleanupPlan.value.total || 0) + " 部", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[24] || (_cache[24] = _createElementVNode("span", null, "本周期数量", -1)),
                      _createElementVNode("strong", null, _toDisplayString(batchSize.value) + " 部", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[25] || (_cache[25] = _createElementVNode("span", null, "冷却", -1)),
                      _createElementVNode("strong", null, _toDisplayString(cleanupPlan.value.cooldown_minutes || cleanupStatus.value.cooldown_minutes || 0) + " 分钟", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[26] || (_cache[26] = _createElementVNode("span", null, "下次执行", -1)),
                      _createElementVNode("strong", null, _toDisplayString(cleanupPlan.value.next_cycle_at || '等待周期'), 1)
                    ])
                  ]),
                  (cleanupPlan.value.next_cycle_at)
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 0,
                        type: "info",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("当前处于周期冷却，下次可执行：" + _toDisplayString(cleanupPlan.value.next_cycle_at), 1)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_29, [
                    _createVNode(_component_VTable, {
                      class: "lt-table",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _cache[28] || (_cache[28] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "#"),
                            _createElementVNode("th", null, "对象"),
                            _createElementVNode("th", null, "媒体库"),
                            _createElementVNode("th", null, "入库日期"),
                            _createElementVNode("th", null, "尝试"),
                            _createElementVNode("th", null, "状态")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupPlan.value.items, (item, index) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: item.queue_key || index
                            }, [
                              _createElementVNode("td", null, _toDisplayString(index + 1), 1),
                              _createElementVNode("td", {
                                class: "lt-ellipsis",
                                title: item.title || item.code || item.movie_id
                              }, _toDisplayString(item.title || item.code || item.movie_id || '未知对象'), 9, _hoisted_30),
                              _createElementVNode("td", null, _toDisplayString(item.library_name || item.server || '未标记媒体库'), 1),
                              _createElementVNode("td", null, _toDisplayString(item.date_created ? item.date_created.slice(0, 10) : '未知'), 1),
                              _createElementVNode("td", null, _toDisplayString(item.attempts || 0), 1),
                              _createElementVNode("td", null, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: planStatusColor(item),
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(planStatus(item)), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ])
                            ]))
                          }), 128)),
                          (!cleanupPlan.value.items?.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_31, [...(_cache[27] || (_cache[27] = [
                                _createElementVNode("td", {
                                  colspan: "6",
                                  class: "text-center text-medium-emphasis py-8"
                                }, "暂无待处理对象", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_32, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupPlan.value.items, (item, index) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: `mobile-${item.queue_key || index}`,
                        class: "lt-record"
                      }, [
                        _createElementVNode("div", _hoisted_33, [
                          _createElementVNode("strong", null, _toDisplayString(item.title || item.code || item.movie_id || '未知对象'), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: planStatusColor(item),
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(planStatus(item)), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("div", _hoisted_34, [
                          _cache[29] || (_cache[29] = _createElementVNode("span", null, "媒体库", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.library_name || item.server || '未标记媒体库'), 1),
                          _cache[30] || (_cache[30] = _createElementVNode("span", null, "入库", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.date_created ? item.date_created.slice(0, 10) : '未知'), 1),
                          _cache[31] || (_cache[31] = _createElementVNode("span", null, "尝试", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.attempts || 0), 1)
                        ])
                      ]))
                    }), 128)),
                    (!cleanupPlan.value.items?.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_35, "暂无待处理对象"))
                      : _createCommentVNode("", true)
                  ]),
                  (cleanupPlanTotalPages.value > 1)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_36, [
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-left",
                          disabled: cleanupPlanPage.value <= 1,
                          onClick: prevCleanupPlanPage
                        }, null, 8, ["disabled"]),
                        _createElementVNode("span", null, _toDisplayString(cleanupPlanPage.value) + " / " + _toDisplayString(cleanupPlanTotalPages.value) + "（共 " + _toDisplayString(cleanupPlan.value.total || 0) + " 部）", 1),
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-right",
                          disabled: cleanupPlanPage.value >= cleanupPlanTotalPages.value,
                          onClick: nextCleanupPlanPage
                        }, null, 8, ["disabled"])
                      ]))
                    : _createCommentVNode("", true)
                ]))
              : (_openBlock(), _createElementBlock("section", _hoisted_37, [
                  _createElementVNode("div", _hoisted_38, [
                    _cache[32] || (_cache[32] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "运行历史"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "保留最近 30 条模块运行记录，按后端分页查看。")
                    ], -1)),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("共 " + _toDisplayString(historyTotal.value || 0) + " 条", 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_39, [
                    _createVNode(_component_VTable, {
                      class: "lt-table",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _cache[34] || (_cache[34] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "时间"),
                            _createElementVNode("th", null, "模块"),
                            _createElementVNode("th", null, "状态"),
                            _createElementVNode("th", null, "摘要"),
                            _createElementVNode("th", null, "耗时")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item, index) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: `${item.time}-${index}`
                            }, [
                              _createElementVNode("td", _hoisted_40, _toDisplayString(item.time), 1),
                              _createElementVNode("td", null, _toDisplayString(item.module_name), 1),
                              _createElementVNode("td", null, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: historyStatusColor(item),
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(historyStatus(item)), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ]),
                              _createElementVNode("td", {
                                class: "lt-ellipsis",
                                title: item.summary
                              }, _toDisplayString(item.summary), 9, _hoisted_41),
                              _createElementVNode("td", null, _toDisplayString(item.duration) + "s", 1)
                            ]))
                          }), 128)),
                          (!history.value.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_42, [...(_cache[33] || (_cache[33] = [
                                _createElementVNode("td", {
                                  colspan: "5",
                                  class: "text-center text-medium-emphasis py-8"
                                }, "暂无运行历史", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_43, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item, index) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: `mobile-history-${item.time}-${index}`,
                        class: "lt-record"
                      }, [
                        _createElementVNode("div", _hoisted_44, [
                          _createElementVNode("strong", null, _toDisplayString(item.module_name), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: historyStatusColor(item),
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(historyStatus(item)), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("div", _hoisted_45, [
                          _cache[35] || (_cache[35] = _createElementVNode("span", null, "时间", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.time), 1),
                          _cache[36] || (_cache[36] = _createElementVNode("span", null, "耗时", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.duration) + "s", 1)
                        ]),
                        _createElementVNode("div", _hoisted_46, _toDisplayString(item.summary), 1)
                      ]))
                    }), 128)),
                    (!history.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_47, "暂无运行历史"))
                      : _createCommentVNode("", true)
                  ]),
                  (historyTotal.value > historyPageSize)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-left",
                          disabled: historyPage.value <= 1,
                          onClick: prevHistoryPage
                        }, null, 8, ["disabled"]),
                        _createElementVNode("span", null, _toDisplayString(historyPage.value) + " / " + _toDisplayString(historyTotalPages.value), 1),
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "tonal",
                          icon: "mdi-chevron-right",
                          disabled: historyPage.value >= historyTotalPages.value,
                          onClick: nextHistoryPage
                        }, null, 8, ["disabled"])
                      ]))
                    : _createCommentVNode("", true)
                ]))
      ])
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2f49591f"]]);

export { Page as default };
