import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, b as apiPost, r as recheckCleanupPlan, a as apiGet, p as pluginApiPath } from './_plugin-vue_export-helper-B5niX35I.js';

const PLAN_ROW_HEIGHT = 36;
const PLAN_HEADER_HEIGHT = 32;
const PLAN_MOBILE_ROW_HEIGHT = 60;

/** 按列表实际可用高度分页，不用滚动条容纳一页中放不下的条目。 */
function fitPlanPage(height, mobile, page = 1, previousSize = 15) {
  const available = Number.isFinite(height) ? Math.max(0, height) : 0;
  const rowHeight = mobile ? PLAN_MOBILE_ROW_HEIGHT : PLAN_ROW_HEIGHT;
  const headerHeight = mobile ? 0 : PLAN_HEADER_HEIGHT;
  const pageSize = Math.max(1, Math.min(15, Math.floor((available - headerHeight) / rowHeight)));
  const firstIndex = Math.max(0, page - 1) * previousSize;
  return { pageSize, page: Math.floor(firstIndex / pageSize) + 1 }
}

/** 返回清理计划快照中的观看与收藏条件，未知值保持可辨认。 */
function planConditionSummary(item = {}) {
  const played = item.played === true ? '已看过' : item.played === false ? '未看过' : '观看未知';
  const favorite = item.favorite === true ? '已收藏' : item.favorite === false ? '未收藏' : '收藏未知';
  return `${played} · ${favorite}`
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,unref:_unref,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "lt-page" };
const _hoisted_2 = { class: "lt-layout" };
const _hoisted_3 = { class: "lt-side" };
const _hoisted_4 = {
  key: 2,
  class: "lt-state"
};
const _hoisted_5 = {
  key: 3,
  class: "lt-pane"
};
const _hoisted_6 = { class: "lt-stat-grid mt-3" };
const _hoisted_7 = { class: "lt-stat-content" };
const _hoisted_8 = { class: "lt-stat-label" };
const _hoisted_9 = { class: "lt-stat-value" };
const _hoisted_10 = { class: "lt-stat-detail" };
const _hoisted_11 = { class: "lt-panel mt-3" };
const _hoisted_12 = { class: "lt-section-heading" };
const _hoisted_13 = { class: "lt-flow-grid mt-3" };
const _hoisted_14 = { class: "lt-flow-index" };
const _hoisted_15 = { class: "lt-flow-copy" };
const _hoisted_16 = {
  key: 0,
  class: "lt-attention-panel mt-3"
};
const _hoisted_17 = { class: "lt-section-heading" };
const _hoisted_18 = { class: "lt-attention-list mt-3" };
const _hoisted_19 = { class: "min-w-0" };
const _hoisted_20 = { class: "text-caption text-medium-emphasis lt-break-text" };
const _hoisted_21 = { class: "lt-panel mt-3" };
const _hoisted_22 = { class: "lt-section-heading" };
const _hoisted_23 = { class: "lt-action-row mt-3" };
const _hoisted_24 = {
  key: 4,
  class: "lt-pane lt-pane--plan"
};
const _hoisted_25 = { class: "lt-section-heading" };
const _hoisted_26 = { class: "lt-action-row lt-action-row--right" };
const _hoisted_27 = { class: "lt-plan-summary lt-plan-summary--compact" };
const _hoisted_28 = ["aria-busy"];
const _hoisted_29 = ["title"];
const _hoisted_30 = ["title"];
const _hoisted_31 = ["title"];
const _hoisted_32 = { class: "lt-plan-actions" };
const _hoisted_33 = { key: 0 };
const _hoisted_34 = { class: "lt-plan-mobile" };
const _hoisted_35 = { class: "lt-plan-mobile-copy" };
const _hoisted_36 = { class: "lt-plan-mobile-title" };
const _hoisted_37 = { class: "text-caption text-medium-emphasis" };
const _hoisted_38 = {
  key: 0,
  class: "lt-empty"
};
const _hoisted_39 = { class: "lt-pagination lt-plan-pagination" };
const _hoisted_40 = {
  key: 5,
  class: "lt-pane"
};
const _hoisted_41 = { class: "lt-section-heading" };
const _hoisted_42 = { class: "lt-table-wrap mt-3" };
const _hoisted_43 = { class: "text-no-wrap" };
const _hoisted_44 = ["title"];
const _hoisted_45 = { class: "lt-duration" };
const _hoisted_46 = { key: 0 };
const _hoisted_47 = { class: "lt-mobile-list" };
const _hoisted_48 = { class: "lt-record-head" };
const _hoisted_49 = { class: "lt-record-meta" };
const _hoisted_50 = { class: "lt-duration" };
const _hoisted_51 = { class: "lt-record-summary" };
const _hoisted_52 = {
  key: 0,
  class: "lt-empty"
};
const _hoisted_53 = {
  key: 0,
  class: "lt-pagination"
};
const _hoisted_54 = { class: "text-subtitle-1 mb-3" };
const _hoisted_55 = { class: "lt-plan-details" };
const _hoisted_56 = { key: 0 };
const _hoisted_57 = { key: 1 };
const _hoisted_58 = { class: "mt-1" };
const _hoisted_59 = { class: "text-caption text-medium-emphasis mt-1" };

const {computed,onBeforeUnmount,onMounted,ref,watch} = await importShared('vue');

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
const cleanupPlanPageSize = ref(15);
const planListElement = ref(null);
const planLoading = ref(false);
const planDetailsOpen = ref(false);
const planDetails = ref(null);
const recheckResultsOpen = ref(false);
let planLoadSequence = 0;
let planResizeObserver = null;
let planResizeFrame = 0;
const history = ref([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const loading = ref(false);
const loadingAction = ref('');
const error = ref('');
const actionMessage = ref('');
const actionOk = ref(false);
const recheckResults = ref([]);
let pageActive = true;
watch([actionMessage, actionOk], ([message, ok], _previous, onCleanup) => {
  if (!pageActive || !message || !ok) return
  const timer = setTimeout(() => { actionMessage.value = ''; }, 5000);
  onCleanup(() => clearTimeout(timer));
});
onBeforeUnmount(() => {
  pageActive = false;
  planResizeObserver?.disconnect();
  if (planResizeFrame) cancelAnimationFrame(planResizeFrame);
});

watch(planListElement, (element) => {
  planResizeObserver?.disconnect();
  if (planResizeFrame) cancelAnimationFrame(planResizeFrame);
  if (!element) return
  const resize = () => {
    if (planResizeFrame) cancelAnimationFrame(planResizeFrame);
    planResizeFrame = requestAnimationFrame(() => {
      if (!pageActive || activeTab.value !== 'cleanup_plan' || !element.clientHeight) return
      const next = fitPlanPage(element.clientHeight, window.matchMedia('(max-width: 760px)').matches,
        cleanupPlanPage.value, cleanupPlanPageSize.value);
      if (next.pageSize === cleanupPlanPageSize.value) return
      cleanupPlanPageSize.value = next.pageSize;
      cleanupPlanPage.value = next.page;
      loadPlan().catch((err) => { if (pageActive) error.value = String(err); });
    });
  };
  planResizeObserver = new ResizeObserver(resize);
  planResizeObserver.observe(element);
  resize();
});

const tabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'cleanup_plan', title: '清理计划', icon: 'mdi-playlist-check' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

const historyTotalPages = computed(() => Math.max(1, Math.ceil((historyTotal.value || 0) / historyPageSize)));
const cleanupPlanTotalPages = computed(() => Math.max(1, Number(cleanupPlan.value?.total_pages || Math.ceil((cleanupPlan.value?.total || 0) / cleanupPlanPageSize.value))));
const cleanupStatus = computed(() => status.value?.modules?.library_cleanup || {});
const batchSize = computed(() => Number(cleanupPlan.value?.batch_size || cleanupStatus.value?.cycle_batch_size || 10));
function formatDuration(value) {
  if (value == null || value === '' || !['number', 'string'].includes(typeof value)) return '--:--'
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--'
  const total = Math.floor(seconds);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
function formatPlanTime(value) {
  if (!value) return '尚未扫描'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
const overviewCards = computed(() => [
  {
    title: '周期扫描',
    value: status.value?.enabled && cleanupStatus.value.scan_enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.scan_cron ? `周期 ${cleanupStatus.value.scan_cron}` : '未设置扫描周期',
    icon: 'mdi-magnify-scan',
    color: status.value?.enabled && cleanupStatus.value.scan_enabled ? 'success' : 'default',
  },
  {
    title: '周期清理',
    value: status.value?.enabled && cleanupStatus.value.cleanup_enabled ? '已开启' : '未开启',
    detail: cleanupStatus.value.cleanup_cron ? `周期 ${cleanupStatus.value.cleanup_cron}` : '未设置清理周期',
    icon: 'mdi-calendar-clock-outline',
    color: status.value?.enabled && cleanupStatus.value.cleanup_enabled ? 'success' : 'default',
  },
  {
    title: '清理计划',
    value: `${cleanupPlan.value.total || 0} 部`,
    detail: `最近扫描：${formatPlanTime(cleanupPlan.value.last_scan_at)}`,
    icon: 'mdi-playlist-check',
    color: cleanupPlan.value.total ? 'warning' : 'primary',
  },
  {
    title: '本周期数量',
    value: `${batchSize.value} 部`,
    detail: !cleanupStatus.value.auto_delete ? '自动删除未开启' : cleanupPlan.value.next_cycle_at
      ? `冷却至 ${formatPlanTime(cleanupPlan.value.next_cycle_at)}`
      : `清理冷却 ${cleanupPlan.value.cooldown_minutes ?? cleanupStatus.value.cooldown_minutes ?? 0} 分钟`,
    icon: 'mdi-counter',
    color: 'primary',
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
    items.push({ icon: 'mdi-timer-sand-outline', color: 'info', title: '周期冷却中', detail: `冷却结束：${formatPlanTime(cleanupPlan.value.next_cycle_at)}` });
  }
  return items
});

function apiPath(path) {
  return pluginApiPath(props.pluginId, path)
}

async function loadStatus() {
  const data = await apiGet(props.api, apiPath('local_toolkit/status'));
  if (pageActive) status.value = data;
}

async function loadPlan() {
  const sequence = ++planLoadSequence;
  planLoading.value = true;
  try {
    const data = await apiGet(props.api, apiPath(`local_toolkit/cleanup_plan?page=${cleanupPlanPage.value}&page_size=${cleanupPlanPageSize.value}`));
    if (!pageActive || sequence !== planLoadSequence) return
    cleanupPlan.value = data || { total: 0, page: 1, page_size: cleanupPlanPageSize.value, total_pages: 1, items: [], batch_size: 10 };
    cleanupPlanPage.value = Number(cleanupPlan.value.page || cleanupPlanPage.value);
  } catch (err) {
    if (pageActive && sequence === planLoadSequence) throw err
  } finally {
    if (pageActive && sequence === planLoadSequence) planLoading.value = false;
  }
}

async function loadOverview() {
  await Promise.all([loadStatus(), loadPlan()]);
}

async function loadHistory() {
  const data = await apiGet(props.api, apiPath(`local_toolkit/history?page=${historyPage.value}&page_size=${historyPageSize}`));
  if (!pageActive) return
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
  if (loadingAction.value) return
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
  if (loadingAction.value) return
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
  if (loadingAction.value) return
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

function showPlanDetails(item) {
  planDetails.value = item;
  planDetailsOpen.value = true;
}

async function recheckPlan(item = null) {
  if (loadingAction.value) return
  loadingAction.value = item ? `recheck:${item.queue_key}` : 'recheck';
  actionMessage.value = '';
  recheckResults.value = [];
  try {
    const response = await recheckCleanupPlan(props.api, props.pluginId, item?.queue_key ?? null);
    if (!pageActive) return
    actionOk.value = response?.success !== false;
    actionMessage.value = response?.message || response?.summary || '核验完成';
    recheckResults.value = response?.results || [];
    try {
      await refreshAfterAction();
    } catch {
      if (pageActive) {
        actionOk.value = false;
        actionMessage.value += ' 列表刷新失败，请手动刷新；上方核验结果已保留。';
      }
    }
  } catch (err) {
    if (!pageActive) return
    actionOk.value = false;
    actionMessage.value = `${String(err)}；请先刷新计划确认状态，再决定是否重新核验。`;
  } finally {
    if (pageActive) loadingAction.value = '';
  }
}

function planRecoveryHint(item) {
  return item.recovery_hint || '点击重新核验查看当前状态及处理办法'
}

function historyStatus(item) {
  return item.status === 'success' ? '成功' : item.status === 'failed' ? '失败' : item.status === 'skipped' ? '跳过' : item.status || '未知'
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
  loadPlan().catch((err) => { if (pageActive) error.value = String(err); });
}

function nextCleanupPlanPage() {
  if (cleanupPlanPage.value >= cleanupPlanTotalPages.value) return
  cleanupPlanPage.value += 1;
  loadPlan().catch((err) => { if (pageActive) error.value = String(err); });
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
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

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
        _cache[17] || (_cache[17] = _createElementVNode("div", { class: "lt-toolbar-title" }, "工具中心", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: refreshActive,
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
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
          default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
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
      _createElementVNode("main", {
        class: _normalizeClass(["lt-main", { 'lt-main--plan': activeTab.value === 'cleanup_plan' }])
      }, [
        (actionMessage.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: actionOk.value ? 'success' : 'error',
              variant: "tonal",
              class: "lt-feedback mb-3",
              closable: "",
              density: "compact",
              "onUpdate:modelValue": _cache[2] || (_cache[2] = value => { if (!value) actionMessage.value = ''; })
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
              class: "lt-feedback mb-3",
              closable: "",
              density: "compact",
              "onUpdate:modelValue": _cache[3] || (_cache[3] = value => { if (!value) error.value = ''; })
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (loading.value)
          ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
              _createVNode(_component_VProgressCircular, {
                indeterminate: "",
                color: "primary"
              })
            ]))
          : (activeTab.value === 'overview')
            ? (_openBlock(), _createElementBlock("section", _hoisted_5, [
                _cache[26] || (_cache[26] = _createElementVNode("div", { class: "lt-section-heading" }, [
                  _createElementVNode("div", null, [
                    _createElementVNode("div", { class: "lt-section-title" }, "运行总览"),
                    _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "清理库存按“扫描、入队、按序执行、复核”运行，其他工具保持按需执行。")
                  ])
                ], -1)),
                _createElementVNode("div", _hoisted_6, [
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
                      _createElementVNode("div", _hoisted_7, [
                        _createElementVNode("div", _hoisted_8, _toDisplayString(card.title), 1),
                        _createElementVNode("div", _hoisted_9, _toDisplayString(card.value), 1),
                        _createElementVNode("div", _hoisted_10, _toDisplayString(card.detail), 1)
                      ])
                    ], 2))
                  }), 128))
                ]),
                _createElementVNode("section", _hoisted_11, [
                  _createElementVNode("div", _hoisted_12, [
                    _cache[18] || (_cache[18] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "运行链路"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "扫描和清理使用独立周期；扫描更新计划，清理只处理已有计划中的本批对象。")
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
                  _createElementVNode("div", _hoisted_13, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList([
                { icon: 'mdi-magnify-scan', title: '周期扫描', detail: '独立扫描周期，仅读取媒体库' },
                { icon: 'mdi-playlist-plus', title: '更新计划', detail: '新增入队，失效移出，失败保留原计划' },
                { icon: 'mdi-format-list-numbered', title: '周期清理', detail: `按序取最多 ${batchSize.value} 部，逐项复核条件` },
                { icon: 'mdi-check-decagram-outline', title: '删除复核', detail: '确认移除后出队，异常对象保留重试' },
              ], (step, index) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: step.title,
                        class: "lt-flow-step"
                      }, [
                        _createElementVNode("div", _hoisted_14, _toDisplayString(index + 1), 1),
                        _createVNode(_component_VIcon, {
                          icon: step.icon,
                          color: "primary",
                          size: "22"
                        }, null, 8, ["icon"]),
                        _createElementVNode("div", _hoisted_15, [
                          _createElementVNode("strong", null, _toDisplayString(step.title), 1),
                          _createElementVNode("span", null, _toDisplayString(step.detail), 1)
                        ])
                      ]))
                    }), 128))
                  ])
                ]),
                (attentionItems.value.length)
                  ? (_openBlock(), _createElementBlock("section", _hoisted_16, [
                      _createElementVNode("div", _hoisted_17, [
                        _cache[19] || (_cache[19] = _createElementVNode("div", null, [
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
                      _createElementVNode("div", _hoisted_18, [
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
                            _createElementVNode("div", _hoisted_19, [
                              _createElementVNode("strong", null, _toDisplayString(item.title), 1),
                              _createElementVNode("div", _hoisted_20, _toDisplayString(item.detail), 1)
                            ])
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("section", _hoisted_21, [
                  _createElementVNode("div", _hoisted_22, [
                    _cache[21] || (_cache[21] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "lt-section-title" }, "快速操作"),
                      _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "生成计划会扫描；立即清理只处理已有计划。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      "prepend-icon": "mdi-format-list-bulleted",
                      class: "text-none",
                      onClick: _cache[4] || (_cache[4] = $event => (selectTab('cleanup_plan')))
                    }, {
                      default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                        _createTextVNode("查看计划", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_23, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-playlist-plus",
                      loading: loadingAction.value === 'scan_plan',
                      onClick: scanPlan
                    }, {
                      default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                        _createTextVNode("生成计划", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "error",
                      variant: "flat",
                      "prepend-icon": "mdi-delete-sweep-outline",
                      loading: loadingAction.value === 'library_cleanup',
                      onClick: _cache[5] || (_cache[5] = $event => (runModule('library_cleanup')))
                    }, {
                      default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                        _createTextVNode("立即清理", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-magnify-scan",
                      loading: loadingAction.value === 'check_missing',
                      onClick: _cache[6] || (_cache[6] = $event => (runModule('check_missing')))
                    }, {
                      default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                        _createTextVNode("扫描缺集", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode(_component_VBtn, {
                      color: "warning",
                      variant: "tonal",
                      "prepend-icon": "mdi-database-refresh-outline",
                      loading: loadingAction.value === 'tmdb_cache',
                      onClick: _cache[7] || (_cache[7] = $event => (runModule('tmdb_cache')))
                    }, {
                      default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                        _createTextVNode("清TMDB", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ])
              ]))
            : (activeTab.value === 'cleanup_plan')
              ? (_openBlock(), _createElementBlock("section", _hoisted_24, [
                  _createElementVNode("div", _hoisted_25, [
                    _cache[30] || (_cache[30] = _createElementVNode("div", { class: "lt-section-title text-no-wrap" }, "清理计划", -1)),
                    _createElementVNode("div", _hoisted_26, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "primary",
                        variant: "tonal",
                        "prepend-icon": "mdi-refresh",
                        disabled: !!loadingAction.value || !cleanupPlan.value.error_count,
                        loading: loadingAction.value === 'recheck',
                        onClick: _cache[8] || (_cache[8] = $event => (recheckPlan()))
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("核验异常（" + _toDisplayString(cleanupPlan.value.error_count || 0) + "）", 1)
                        ]),
                        _: 1
                      }, 8, ["disabled", "loading"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-playlist-plus",
                        loading: loadingAction.value === 'scan_plan',
                        onClick: scanPlan
                      }, {
                        default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
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
                        onClick: _cache[9] || (_cache[9] = $event => (runModule('library_cleanup')))
                      }, {
                        default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                          _createTextVNode("立即清理", -1)
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
                        default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                          _createTextVNode("清空计划", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"])
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_27, [
                    _createElementVNode("span", null, [
                      _cache[31] || (_cache[31] = _createTextVNode("待处理 ", -1)),
                      _createElementVNode("strong", null, _toDisplayString(cleanupPlan.value.total || 0), 1),
                      _cache[32] || (_cache[32] = _createTextVNode(" 部", -1))
                    ]),
                    _createElementVNode("span", null, [
                      _cache[33] || (_cache[33] = _createTextVNode("每批 ", -1)),
                      _createElementVNode("strong", null, _toDisplayString(batchSize.value), 1),
                      _cache[34] || (_cache[34] = _createTextVNode(" 部", -1))
                    ]),
                    _createElementVNode("span", null, "冷却 " + _toDisplayString(cleanupPlan.value.cooldown_minutes ?? cleanupStatus.value.cooldown_minutes ?? 0) + " 分钟", 1),
                    _createElementVNode("span", null, _toDisplayString(cleanupPlan.value.next_cycle_at ? `冷却至 ${formatPlanTime(cleanupPlan.value.next_cycle_at)}` : '可执行'), 1),
                    (recheckResults.value.length)
                      ? (_openBlock(), _createBlock(_component_VBtn, {
                          key: 0,
                          size: "x-small",
                          variant: "text",
                          color: "primary",
                          onClick: _cache[10] || (_cache[10] = $event => (recheckResultsOpen.value = true))
                        }, {
                          default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                            _createTextVNode("查看核验结果", -1)
                          ]))]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("div", {
                    ref_key: "planListElement",
                    ref: planListElement,
                    class: _normalizeClass(["lt-plan-list", { 'lt-plan-list--loading': planLoading.value }]),
                    "aria-busy": planLoading.value,
                    style: _normalizeStyle({ '--lt-plan-row-height': `${_unref(PLAN_ROW_HEIGHT)}px`, '--lt-plan-header-height': `${_unref(PLAN_HEADER_HEIGHT)}px`, '--lt-plan-mobile-row-height': `${_unref(PLAN_MOBILE_ROW_HEIGHT)}px` })
                  }, [
                    _createVNode(_component_VTable, {
                      class: "lt-table lt-plan-table",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _cache[37] || (_cache[37] = _createElementVNode("colgroup", null, [
                          _createElementVNode("col", { style: {"width":"34px"} }),
                          _createElementVNode("col"),
                          _createElementVNode("col", { style: {"width":"100px"} }),
                          _createElementVNode("col", { style: {"width":"150px"} }),
                          _createElementVNode("col", { style: {"width":"44px"} }),
                          _createElementVNode("col", { style: {"width":"68px"} }),
                          _createElementVNode("col", { style: {"width":"68px"} })
                        ], -1)),
                        _cache[38] || (_cache[38] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "#"),
                            _createElementVNode("th", null, "对象"),
                            _createElementVNode("th", null, "入库日期"),
                            _createElementVNode("th", null, "满足条件"),
                            _createElementVNode("th", null, "尝试"),
                            _createElementVNode("th", null, "状态"),
                            _createElementVNode("th", null, "操作")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupPlan.value.items, (item, index) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: item.queue_key || index
                            }, [
                              _createElementVNode("td", null, _toDisplayString((cleanupPlanPage.value - 1) * cleanupPlanPageSize.value + index + 1), 1),
                              _createElementVNode("td", {
                                title: item.title || item.code || item.movie_id
                              }, _toDisplayString(item.title || item.code || item.movie_id || '未知对象'), 9, _hoisted_29),
                              _createElementVNode("td", null, _toDisplayString(item.date_created ? item.date_created.slice(0, 10) : '未知'), 1),
                              _createElementVNode("td", {
                                title: _unref(planConditionSummary)(item)
                              }, _toDisplayString(_unref(planConditionSummary)(item)), 9, _hoisted_30),
                              _createElementVNode("td", null, _toDisplayString(item.attempts || 0), 1),
                              _createElementVNode("td", {
                                class: _normalizeClass(item.last_error ? 'text-warning' : 'text-primary'),
                                title: planStatus(item)
                              }, _toDisplayString(item.last_error ? '待核验' : '待处理'), 11, _hoisted_31),
                              _createElementVNode("td", _hoisted_32, [
                                _createVNode(_component_VBtn, {
                                  size: "x-small",
                                  variant: "text",
                                  icon: "mdi-information-outline",
                                  title: "查看状态与处理办法",
                                  "aria-label": "查看状态与处理办法",
                                  onClick: $event => (showPlanDetails(item))
                                }, null, 8, ["onClick"]),
                                _createVNode(_component_VBtn, {
                                  size: "x-small",
                                  variant: "text",
                                  color: "primary",
                                  icon: "mdi-refresh",
                                  title: "重新核验（不删除媒体）",
                                  "aria-label": "重新核验",
                                  disabled: !!loadingAction.value,
                                  loading: loadingAction.value === `recheck:${item.queue_key}`,
                                  onClick: $event => (recheckPlan(item))
                                }, null, 8, ["disabled", "loading", "onClick"])
                              ])
                            ]))
                          }), 128)),
                          (!cleanupPlan.value.items?.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_33, [...(_cache[36] || (_cache[36] = [
                                _createElementVNode("td", {
                                  colspan: "7",
                                  class: "text-center text-medium-emphasis"
                                }, "暂无待处理对象", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    }),
                    _createElementVNode("div", _hoisted_34, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupPlan.value.items, (item, index) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: `mobile-${item.queue_key || index}`,
                          class: "lt-plan-mobile-row"
                        }, [
                          _createElementVNode("div", _hoisted_35, [
                            _createElementVNode("div", _hoisted_36, _toDisplayString(item.title || item.code || item.movie_id || '未知对象'), 1),
                            _createElementVNode("div", _hoisted_37, _toDisplayString(item.date_created ? item.date_created.slice(0, 10) : '日期未知') + " · " + _toDisplayString(_unref(planConditionSummary)(item)) + " · " + _toDisplayString(item.attempts || 0) + " 次", 1)
                          ]),
                          _createElementVNode("span", {
                            class: _normalizeClass(["text-caption text-no-wrap", item.last_error ? 'text-warning' : 'text-primary'])
                          }, _toDisplayString(item.last_error ? '待核验' : '待处理'), 3),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            icon: "mdi-information-outline",
                            "aria-label": "查看状态与处理办法",
                            onClick: $event => (showPlanDetails(item))
                          }, null, 8, ["onClick"]),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            color: "primary",
                            icon: "mdi-refresh",
                            "aria-label": "重新核验",
                            disabled: !!loadingAction.value,
                            loading: loadingAction.value === `recheck:${item.queue_key}`,
                            onClick: $event => (recheckPlan(item))
                          }, null, 8, ["disabled", "loading", "onClick"])
                        ]))
                      }), 128)),
                      (!cleanupPlan.value.items?.length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_38, "暂无待处理对象"))
                        : _createCommentVNode("", true)
                    ])
                  ], 14, _hoisted_28),
                  _createElementVNode("div", _hoisted_39, [
                    _createVNode(_component_VBtn, {
                      size: "x-small",
                      variant: "tonal",
                      icon: "mdi-chevron-left",
                      "aria-label": "上一页",
                      disabled: planLoading.value || cleanupPlanPage.value <= 1,
                      onClick: prevCleanupPlanPage
                    }, null, 8, ["disabled"]),
                    _createElementVNode("span", null, _toDisplayString(cleanupPlanPage.value) + " / " + _toDisplayString(cleanupPlanTotalPages.value) + " · 共 " + _toDisplayString(cleanupPlan.value.total || 0) + " 部 · 每页 " + _toDisplayString(cleanupPlanPageSize.value) + " 条", 1),
                    _createVNode(_component_VBtn, {
                      size: "x-small",
                      variant: "tonal",
                      icon: "mdi-chevron-right",
                      "aria-label": "下一页",
                      disabled: planLoading.value || cleanupPlanPage.value >= cleanupPlanTotalPages.value,
                      onClick: nextCleanupPlanPage
                    }, null, 8, ["disabled"])
                  ])
                ]))
              : (_openBlock(), _createElementBlock("section", _hoisted_40, [
                  _createElementVNode("div", _hoisted_41, [
                    _cache[39] || (_cache[39] = _createElementVNode("div", null, [
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
                  _createElementVNode("div", _hoisted_42, [
                    _createVNode(_component_VTable, {
                      class: "lt-table",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _cache[41] || (_cache[41] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "时间"),
                            _createElementVNode("th", null, "模块"),
                            _createElementVNode("th", null, "状态"),
                            _createElementVNode("th", null, "摘要"),
                            _createElementVNode("th", { class: "lt-duration" }, "耗时（分:秒）")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item, index) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: `${item.time}-${index}`
                            }, [
                              _createElementVNode("td", _hoisted_43, _toDisplayString(item.time), 1),
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
                              }, _toDisplayString(item.summary), 9, _hoisted_44),
                              _createElementVNode("td", _hoisted_45, _toDisplayString(formatDuration(item.duration)), 1)
                            ]))
                          }), 128)),
                          (!history.value.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_46, [...(_cache[40] || (_cache[40] = [
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
                  _createElementVNode("div", _hoisted_47, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value, (item, index) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: `mobile-history-${item.time}-${index}`,
                        class: "lt-record"
                      }, [
                        _createElementVNode("div", _hoisted_48, [
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
                        _createElementVNode("div", _hoisted_49, [
                          _cache[42] || (_cache[42] = _createElementVNode("span", null, "时间", -1)),
                          _createElementVNode("b", null, _toDisplayString(item.time), 1),
                          _cache[43] || (_cache[43] = _createElementVNode("span", null, "耗时", -1)),
                          _createElementVNode("b", _hoisted_50, _toDisplayString(formatDuration(item.duration)), 1)
                        ]),
                        _createElementVNode("div", _hoisted_51, _toDisplayString(item.summary), 1)
                      ]))
                    }), 128)),
                    (!history.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_52, "暂无运行历史"))
                      : _createCommentVNode("", true)
                  ]),
                  (historyTotal.value > historyPageSize)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_53, [
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
      ], 2)
    ]),
    _createVNode(_component_VDialog, {
      modelValue: planDetailsOpen.value,
      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((planDetailsOpen).value = $event)),
      "max-width": "620",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        (planDetails.value)
          ? (_openBlock(), _createBlock(_component_VCard, {
              key: 0,
              title: "条目详情"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardText, { class: "lt-break-text" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_54, _toDisplayString(planDetails.value.title || planDetails.value.code || planDetails.value.movie_id), 1),
                    _createElementVNode("dl", _hoisted_55, [
                      _cache[44] || (_cache[44] = _createElementVNode("dt", null, "媒体库", -1)),
                      _createElementVNode("dd", null, _toDisplayString(planDetails.value.library_name || planDetails.value.server), 1),
                      _cache[45] || (_cache[45] = _createElementVNode("dt", null, "入库日期", -1)),
                      _createElementVNode("dd", null, _toDisplayString(planDetails.value.date_created ? formatPlanTime(planDetails.value.date_created) : '未知'), 1),
                      _cache[46] || (_cache[46] = _createElementVNode("dt", null, "清理尝试", -1)),
                      _createElementVNode("dd", null, _toDisplayString(planDetails.value.attempts || 0) + " 次", 1),
                      _cache[47] || (_cache[47] = _createElementVNode("dt", null, "当前状态", -1)),
                      _createElementVNode("dd", null, _toDisplayString(planStatus(planDetails.value)), 1),
                      (planDetails.value.last_error)
                        ? (_openBlock(), _createElementBlock("dt", _hoisted_56, "处理办法"))
                        : _createCommentVNode("", true),
                      (planDetails.value.last_error)
                        ? (_openBlock(), _createElementBlock("dd", _hoisted_57, _toDisplayString(planRecoveryHint(planDetails.value)), 1))
                        : _createCommentVNode("", true),
                      _cache[48] || (_cache[48] = _createElementVNode("dt", null, "最近核验", -1)),
                      _createElementVNode("dd", null, _toDisplayString(planDetails.value.last_recheck_at ? formatPlanTime(planDetails.value.last_recheck_at) : '尚未核验'), 1)
                    ]),
                    _cache[49] || (_cache[49] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-4" }, "重新核验只查询媒体状态，不删除媒体。批量每次最多核验 10 部异常条目。", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardActions, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSpacer),
                    _createVNode(_component_VBtn, {
                      onClick: _cache[11] || (_cache[11] = $event => (planDetailsOpen.value = false))
                    }, {
                      default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                        _createTextVNode("关闭", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode("", true)
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: recheckResultsOpen.value,
      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((recheckResultsOpen).value = $event)),
      "max-width": "680",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { title: "核验结果" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardText, { class: "lt-recheck-results" }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recheckResults.value, (result) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: result.queue_key,
                    class: "lt-record"
                  }, [
                    _createElementVNode("strong", null, _toDisplayString(result.title), 1),
                    _createElementVNode("div", _hoisted_58, _toDisplayString(result.reason), 1),
                    _createElementVNode("div", _hoisted_59, _toDisplayString(result.action), 1)
                  ]))
                }), 128))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  onClick: _cache[13] || (_cache[13] = $event => (recheckResultsOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
                    _createTextVNode("关闭", -1)
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
    }, 8, ["modelValue"])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-016f5ea4"]]);

export { Page as default };
