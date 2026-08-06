import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as getPluginApi } from './_plugin-vue_export-helper-Cd7yiqDA.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,createBlock:_createBlock,createCommentVNode:_createCommentVNode,vShow:_vShow,withDirectives:_withDirectives,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "dc-config" };
const _hoisted_2 = { class: "dc-body" };
const _hoisted_3 = { class: "dc-nav" };
const _hoisted_4 = { class: "dc-content" };
const _hoisted_5 = { class: "dc-subtabs" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "dc-pane dc-pane--overview" };
const _hoisted_8 = { class: "dc-overview-section mb-3" };
const _hoisted_9 = { class: "dc-flow" };
const _hoisted_10 = { class: "dc-flow-label" };
const _hoisted_11 = {
  key: 0,
  class: "dc-flow-row"
};
const _hoisted_12 = {
  key: 1,
  class: "dc-flow-sub"
};
const _hoisted_13 = { class: "dc-flow-sub-label" };
const _hoisted_14 = { class: "dc-flow-row dc-flow-row--sub" };
const _hoisted_15 = { class: "dc-stat-grid mb-3" };
const _hoisted_16 = { class: "d-flex align-center ga-2 mb-1" };
const _hoisted_17 = { class: "text-caption text-medium-emphasis" };
const _hoisted_18 = { class: "text-subtitle-1 font-weight-bold" };
const _hoisted_19 = { class: "text-caption text-medium-emphasis" };
const _hoisted_20 = { class: "dc-overview-grid" };
const _hoisted_21 = { class: "dc-overview-section" };
const _hoisted_22 = { class: "dc-kv" };
const _hoisted_23 = { class: "dc-kv" };
const _hoisted_24 = { class: "dc-kv" };
const _hoisted_25 = { class: "dc-overview-section" };
const _hoisted_26 = { class: "dc-kv" };
const _hoisted_27 = { class: "dc-kv" };
const _hoisted_28 = { class: "dc-kv" };
const _hoisted_29 = { class: "dc-pane" };
const _hoisted_30 = { class: "dc-pane" };
const _hoisted_31 = { class: "dc-rank-list-heading" };
const _hoisted_32 = { class: "dc-rank-list-summary text-caption text-medium-emphasis" };
const _hoisted_33 = { class: "dc-rank-list-1col" };
const _hoisted_34 = { class: "dc-rank-card-summary" };
const _hoisted_35 = ["onClick"];
const _hoisted_36 = { class: "dc-rank-summary-title" };
const _hoisted_37 = { class: "dc-rank-summary-meta" };
const _hoisted_38 = { key: 0 };
const _hoisted_39 = { key: 1 };
const _hoisted_40 = { key: 2 };
const _hoisted_41 = { class: "dc-rank-actions" };
const _hoisted_42 = {
  key: 0,
  class: "dc-rank-card-details"
};
const _hoisted_43 = { class: "dc-rank-card-body" };
const _hoisted_44 = { class: "dc-rank-field" };
const _hoisted_45 = {
  key: 0,
  class: "dc-rank-field"
};
const _hoisted_46 = {
  key: 1,
  class: "dc-rank-field"
};
const _hoisted_47 = {
  key: 2,
  class: "dc-rank-field"
};
const _hoisted_48 = {
  key: 0,
  class: "dc-custom-rank-route-row"
};
const _hoisted_49 = {
  key: 1,
  class: "dc-rank-route-hint text-caption text-medium-emphasis"
};
const _hoisted_50 = {
  key: 1,
  class: "dc-custom-ranks-empty text-caption text-medium-emphasis"
};
const _hoisted_51 = { class: "dc-pane" };
const _hoisted_52 = { class: "dc-pane" };
const _hoisted_53 = { class: "dc-wish-status mt-3" };
const _hoisted_54 = { class: "dc-kv" };
const _hoisted_55 = { class: "dc-kv" };
const _hoisted_56 = { class: "dc-kv" };
const _hoisted_57 = { class: "dc-kv" };
const _hoisted_58 = { class: "dc-pane" };
const _hoisted_59 = { class: "dc-pane" };

const {computed,nextTick,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const form = reactive({});
const activeMain = ref('overview');
const activeSub = ref('overview');
const overview = ref(null);
const loadingOverview = ref(false);
const customRankError = ref('');
const expandedRankKeys = ref(new Set());
const deleteTarget = ref(null);
const deleteDialog = ref(false);
const nameInputRefs = new Map();

const defaults = {
  enabled: false, cron: '0 8 * * *', notify: false, proxy: false, onlyonce: false,
  rsshub_domain: 'https://rsshub.ddsrem.com',
  rank_configs: {
    coming: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_real_time: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_chinese: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_global: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    movie_weekly: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    bangumi: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
  },
  region_filters: [], genre_filters: [], resolution_filters: [], custom_rss_addrs: '', custom_ranks: [],
  folio_enabled: true, folio_private: true, folio_first: true, folio_notify: false, folio_exclude_live_tv: true,
  folio_user: '', folio_exclude: '', folio_cookie: '',
  wish_enabled: false, wish_cron: '*/30 * * * *', wish_user: '', wish_notify: false, wish_onlyonce: false, wish_max_pages: 1, wish_days: 7,
  dashboard_rank_keys: [],
  discovery_page_enabled: false,
  blacklist_keywords: '',
  observe_days: 0,
  observe_rank_keys: ['coming', 'tv_real_time'],
};

const builtinRankDefs = [
  { key: 'coming', name: '即将上映', route: '/douban/tv/coming', filters: ['vote', 'wish_count'] },
  { key: 'tv_real_time', name: '实时热门', route: '/douban/list/tv_real_time_hotest', filters: ['vote', 'year'] },
  { key: 'tv_chinese', name: '华语口碑', route: '/douban/list/tv_chinese_best_weekly', filters: ['vote', 'year'] },
  { key: 'tv_global', name: '全球口碑', route: '/douban/list/tv_global_best_weekly', filters: ['vote', 'year'] },
  { key: 'movie_weekly', name: '电影口碑', route: '/douban/list/movie_weekly_best', filters: ['vote', 'year'] },
  { key: 'bangumi', name: 'BangumiTV', route: '/bangumi.tv/anime/followrank', filters: ['vote', 'year'] },
];

const rankDefs = computed(() => [
  ...builtinRankDefs,
  ...(Array.isArray(form.custom_ranks) ? form.custom_ranks : []).map(rank => ({
    ...rank,
    model: rank,
    custom: true,
    filters: ['vote', 'year'],
  })),
]);

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '运行链路、模块状态和待关注事项。' },
  { key: 'rank', title: '榜单订阅', icon: 'mdi-trophy-outline', desc: '内置与自定义榜单统一订阅到豆瓣中心。' },
  { key: 'folio', title: '豆瓣时间', icon: 'mdi-book-clock-outline', desc: '追剧观影自动同步进度到豆瓣时间线。' },
  { key: 'dashboard', title: '仪表显示', icon: 'mdi-view-dashboard-outline', desc: '时间线 + 榜单排行双面板。' },
];

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  rank: [{ key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' }, { key: 'list', title: '榜单列表', icon: 'mdi-format-list-bulleted' }, { key: 'filter', title: '订阅观察', icon: 'mdi-shield-search' }],
  folio: [{ key: 'wish', title: '同步想看', icon: 'mdi-heart-plus-outline' }, { key: 'sync', title: '同步观影', icon: 'mdi-sync' }],
  dashboard: [{ key: 'view', title: '仪表盘选择', icon: 'mdi-view-dashboard-outline' }],
};

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);
const enabledRankCount = computed(() => rankDefs.value.filter(r => form.rank_configs?.[r.key]?.enabled).length);
const customRankCount = computed(() => rankDefs.value.filter(r => r.custom).length);
const overviewCards = computed(() => {
  const cards = overview.value?.cards || {};
  return [
    {
      title: '榜单订阅',
      icon: 'mdi-rss',
      color: cards.rss?.enabled ? 'success' : 'warning',
      value: `${cards.rss?.enabled || 0}/${cards.rss?.total || rankDefs.value.length}`,
      desc: cards.rss?.last_refresh ? `最近刷新 ${cards.rss.last_refresh}` : '等待 RSS 刷新',
    },
    {
      title: '订阅记录',
      icon: 'mdi-playlist-check',
      color: cards.subscribe?.enabled ? 'primary' : 'default',
      value: `${cards.subscribe?.total || 0} 条`,
      desc: `本月新增 ${cards.subscribe?.month_new || 0} 条`,
    },
    {
      title: '归档治理',
      icon: 'mdi-shield-check-outline',
      color: cards.observe?.pending ? 'warning' : 'success',
      value: `${cards.observe?.pending || 0} 待观察`,
      desc: `观察期 ${cards.observe?.days || 0} 天，已忽略 ${cards.observe?.ignored || 0}`,
    },
    {
      title: '豆瓣时间',
      icon: 'mdi-book-clock-outline',
      color: cards.folio?.enabled ? 'success' : 'default',
      value: `${cards.folio?.items || 0} 条`,
      desc: cards.folio?.user ? `用户 ${cards.folio.user}` : '未配置用户',
    },
  ]
});

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function customRankKey() {
  return `custom_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function addCustomRank() {
  customRankError.value = '';
  const key = customRankKey();
  form.custom_ranks.push({ key, name: '', route: '' });
  form.rank_configs[key] = { enabled: false, count: 1, vote: '', year: '', regions: [] };
  expandedRankKeys.value = new Set([...expandedRankKeys.value, key]);
  activeMain.value = 'rank';
  activeSub.value = 'list';
  nextTick(() => nameInputRefs.get(key)?.focus?.());
}

function setNameInputRef(key, value) {
  if (value) nameInputRefs.set(key, value);
  else nameInputRefs.delete(key);
}

function toggleRank(key) {
  const next = new Set(expandedRankKeys.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedRankKeys.value = next;
}

function isExpanded(key) {
  return expandedRankKeys.value.has(key)
}

function requestRemoveCustomRank(rank) {
  deleteTarget.value = rank;
  deleteDialog.value = true;
}

function removeCustomRank(key) {
  customRankError.value = '';
  form.custom_ranks = form.custom_ranks.filter(rank => rank.key !== key);
  delete form.rank_configs[key];
  form.dashboard_rank_keys = (form.dashboard_rank_keys || []).filter(value => value !== key);
  form.observe_rank_keys = (form.observe_rank_keys || []).filter(value => value !== key);
  expandedRankKeys.value = new Set([...expandedRankKeys.value].filter(value => value !== key));
  deleteTarget.value = null;
  deleteDialog.value = false;
}

function validCustomRoute(route) {
  const value = String(route || '').trim();
  return value.startsWith('/') && !value.startsWith('//') && !value.includes('#') && (() => {
    try {
      const parsed = new URL(value, 'https://rsshub.local');
      return parsed.origin === 'https://rsshub.local'
    } catch {
      return false
    }
  })()
}

function validateCustomRanks() {
  const seen = new Set(builtinRankDefs.map(rank => rank.key));
  for (const rank of form.custom_ranks || []) {
    const key = String(rank?.key || '').trim();
    if (!key || seen.has(key)) return '自定义榜单标识重复或无效'
    if (!String(rank?.name || '').trim()) return '请填写自定义榜单名称'
    if (!validCustomRoute(rank?.route)) return 'RSSHub 路由必须是以 / 开头的相对路径'
    seen.add(key);
  }
  return ''
}

function normalizeInitialConfig(value) {
  const m = Object.assign({}, cloneConfig(defaults), cloneConfig(value));
  m.custom_ranks = Array.isArray(m.custom_ranks)
    ? m.custom_ranks.filter(rank => isPlainObject(rank)).map(rank => ({
      key: String(rank.key || ''),
      name: String(rank.name || ''),
      route: String(rank.route || ''),
    }))
    : [];
  if (!(m.rank_configs && typeof m.rank_configs === 'object' && !Array.isArray(m.rank_configs))) {
    m.rank_configs = {};
  }
  for (const rd of [...builtinRankDefs, ...m.custom_ranks.map(rank => ({ ...rank, filters: ['vote', 'year'] }))]) {
    m.rank_configs[rd.key] = {
      ...(defaults.rank_configs[rd.key] || { enabled: false, count: 1, vote: '', year: '' }),
      ...(isPlainObject(m.rank_configs[rd.key]) ? m.rank_configs[rd.key] : {}),
    };
    m.rank_configs[rd.key].regions = Array.isArray(m.rank_configs[rd.key].regions)
      ? [...new Set(m.rank_configs[rd.key].regions.map(value => String(value || '').trim()).filter(Boolean))]
      : [];
    const rankConfig = m.rank_configs[rd.key];
    const rawCount = rankConfig.count;
    rankConfig.count = rawCount === undefined || rawCount === null || rawCount === ''
      ? 1
      : (Number(rawCount) === 0 ? '' : rawCount);
    for (const field of ['vote', 'year', 'wish_count', 'air_days']) {
      if (rankConfig[field] === undefined || rankConfig[field] === null || Number(rankConfig[field]) === 0) rankConfig[field] = '';
    }
    delete m.rank_configs[rd.key].media_type;
  }
  if (!Array.isArray(m.dashboard_rank_keys)) m.dashboard_rank_keys = [];
  m.dashboard_rank_keys = [...new Set(m.dashboard_rank_keys.map(value => String(value || '').trim()).filter(Boolean))].slice(0, 6);
  if (!Array.isArray(m.observe_rank_keys)) m.observe_rank_keys = [...defaults.observe_rank_keys];
  return m
}

watch(() => props.initialConfig, val => {
  Object.keys(form).forEach(k => delete form[k]);
  Object.assign(form, normalizeInitialConfig(val));
}, { immediate: true, deep: true });

function saveConfig() {
  customRankError.value = validateCustomRanks();
  if (customRankError.value) {
    activeMain.value = 'rank';
    activeSub.value = 'list';
    return
  }
  emit('save', {
    ...form,
    custom_ranks: (form.custom_ranks || []).map(rank => ({
      key: String(rank.key || '').trim(),
      name: String(rank.name || '').trim(),
      route: String(rank.route || '').trim(),
    })),
    rank_configs: Object.fromEntries(Object.entries(form.rank_configs || {}).map(([key, config]) => [key, {
      ...cloneConfig(config),
      regions: Array.isArray(config?.regions) ? [...new Set(config.regions.map(value => String(value || '').trim()).filter(Boolean))] : [],
    }])),
    region_filters: [],
    genre_filters: [],
    resolution_filters: [],
    custom_rss_addrs: '',
  });
}

function limitDashboardRanks() {
  form.dashboard_rank_keys = [...new Set((form.dashboard_rank_keys || []).map(value => String(value || '').trim()).filter(Boolean))].slice(0, 6);
}

function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || '';
}

async function loadOverview() {
  loadingOverview.value = true;
  try {
    const resp = await getPluginApi(props.api, 'overview');
    if (resp?.code === 0 || resp?.cards) overview.value = resp;
  } catch (error) {
    console.error('加载豆瓣中心总览失败:', error);
  } finally {
    loadingOverview.value = false;
  }
}

onMounted(loadOverview);

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
  const _component_VCol = _resolveComponent("VCol");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VExpandTransition = _resolveComponent("VExpandTransition");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextarea = _resolveComponent("VTextarea");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "dc-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "dc-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg",
              class: "dc-header-avatar"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-book-open-page-variant-outline",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              class: "dc-enable-switch",
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6 dc-header-title" }, {
              default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                _createTextVNode("豆瓣中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption dc-header-subtitle" }, {
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
              class: "py-2 dc-nav-list"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "dc-nav-item",
                    onClick: $event => (selectMain(item.key))
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon,
                        class: "dc-nav-icon"
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, { class: "dc-nav-title" }, {
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
                  class: _normalizeClass(["dc-subtab", { 'dc-subtab--active': activeSub.value === sub.key }]),
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
            _createElementVNode("div", {
              class: _normalizeClass(["dc-window", { 'dc-window--overview': activeMain.value === 'overview' }])
            }, [
              _withDirectives(_createElementVNode("div", _hoisted_7, [
                _createElementVNode("div", _hoisted_8, [
                  _cache[28] || (_cache[28] = _createElementVNode("div", { class: "dc-section-title d-flex align-center" }, [
                    _createElementVNode("span", null, "运行链路")
                  ], -1)),
                  _createElementVNode("div", _hoisted_9, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((overview.value?.flows || []), (flow) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: flow.label,
                        class: "dc-flow-block"
                      }, [
                        _createElementVNode("div", _hoisted_10, _toDisplayString(flow.label), 1),
                        (flow.steps?.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(flow.steps, (step, idx) => {
                                return (_openBlock(), _createElementBlock(_Fragment, {
                                  key: `${flow.label}-${step}`
                                }, [
                                  _createElementVNode("span", null, _toDisplayString(step), 1),
                                  (idx < flow.steps.length - 1)
                                    ? (_openBlock(), _createBlock(_component_VIcon, {
                                        key: 0,
                                        icon: "mdi-arrow-right",
                                        size: "15"
                                      }))
                                    : _createCommentVNode("", true)
                                ], 64))
                              }), 128))
                            ]))
                          : (flow.flows?.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(flow.flows, (subFlow) => {
                                  return (_openBlock(), _createElementBlock("div", {
                                    key: `${flow.label}-${subFlow.label}`,
                                    class: "dc-flow-sub-block"
                                  }, [
                                    _createElementVNode("div", _hoisted_13, _toDisplayString(subFlow.label), 1),
                                    _createElementVNode("div", _hoisted_14, [
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(subFlow.steps, (step, idx) => {
                                        return (_openBlock(), _createElementBlock(_Fragment, {
                                          key: `${subFlow.label}-${step}`
                                        }, [
                                          _createElementVNode("span", null, _toDisplayString(step), 1),
                                          (idx < subFlow.steps.length - 1)
                                            ? (_openBlock(), _createBlock(_component_VIcon, {
                                                key: 0,
                                                icon: "mdi-arrow-right",
                                                size: "15"
                                              }))
                                            : _createCommentVNode("", true)
                                        ], 64))
                                      }), 128))
                                    ])
                                  ]))
                                }), 128))
                              ]))
                            : _createCommentVNode("", true)
                      ]))
                    }), 128))
                  ])
                ]),
                _createElementVNode("div", _hoisted_15, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewCards.value, (card) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: card.title,
                      class: "dc-stat"
                    }, [
                      _createElementVNode("div", _hoisted_16, [
                        _createVNode(_component_VAvatar, {
                          color: card.color,
                          variant: "tonal",
                          size: "28",
                          rounded: "lg"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VIcon, {
                              icon: card.icon,
                              size: "17"
                            }, null, 8, ["icon"])
                          ]),
                          _: 2
                        }, 1032, ["color"]),
                        _createElementVNode("div", _hoisted_17, _toDisplayString(card.title), 1)
                      ]),
                      _createElementVNode("div", _hoisted_18, _toDisplayString(card.value), 1),
                      _createElementVNode("div", _hoisted_19, _toDisplayString(card.desc), 1)
                    ]))
                  }), 128))
                ]),
                _createElementVNode("div", _hoisted_20, [
                  _createElementVNode("div", _hoisted_21, [
                    _cache[32] || (_cache[32] = _createElementVNode("div", { class: "dc-section-title" }, "待关注", -1)),
                    _createElementVNode("div", _hoisted_22, [
                      _cache[29] || (_cache[29] = _createElementVNode("span", null, "观察队列", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.attention?.pending_observations || 0), 1)
                    ]),
                    _createElementVNode("div", _hoisted_23, [
                      _cache[30] || (_cache[30] = _createElementVNode("span", null, "防刷日志", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.attention?.anti_cheat_logs || 0), 1)
                    ]),
                    _createElementVNode("div", _hoisted_24, [
                      _cache[31] || (_cache[31] = _createElementVNode("span", null, "黑名命中", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.attention?.blacklist_hits || 0), 1)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_25, [
                    _cache[36] || (_cache[36] = _createElementVNode("div", { class: "dc-section-title" }, "治理概况", -1)),
                    _createElementVNode("div", _hoisted_26, [
                      _cache[33] || (_cache[33] = _createElementVNode("span", null, "忽略条目", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.governance?.ignored_observations || 0), 1)
                    ]),
                    _createElementVNode("div", _hoisted_27, [
                      _cache[34] || (_cache[34] = _createElementVNode("span", null, "订阅记录", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.governance?.subscribe_records || 0), 1)
                    ]),
                    _createElementVNode("div", _hoisted_28, [
                      _cache[35] || (_cache[35] = _createElementVNode("span", null, "防刷日志", -1)),
                      _createElementVNode("strong", null, _toDisplayString(overview.value?.governance?.anti_cheat_logs || 0), 1)
                    ])
                  ])
                ])
              ], 512), [
                [_vShow, activeSub.value === 'overview']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_29, [
                _cache[37] || (_cache[37] = _createElementVNode("div", { class: "dc-section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.onlyonce,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.onlyonce) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.cron) = $event)),
                          label: "运行周期",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.rsshub_domain,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.rsshub_domain) = $event)),
                          label: "RSSHub 域名",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 https://rsshub.ddsrem.com，所有榜单共用",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  class: "mt-3",
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  text: "订阅用户名统一为「豆瓣中心」。即将上映支持评分、地区、想看筛选；空或 0 表示不限。"
                })
              ], 512), [
                [_vShow, activeSub.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_30, [
                _createElementVNode("div", _hoisted_31, [
                  _createElementVNode("div", null, [
                    _cache[38] || (_cache[38] = _createElementVNode("div", { class: "dc-section-title mb-1" }, "榜单列表", -1)),
                    _createElementVNode("div", _hoisted_32, "已启用 " + _toDisplayString(enabledRankCount.value) + " 个 · 自定义 " + _toDisplayString(customRankCount.value) + " 个", 1)
                  ]),
                  _createVNode(_component_VBtn, {
                    icon: "",
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    "aria-label": "新增自定义榜单",
                    onClick: addCustomRank
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-plus",
                        size: "20"
                      }),
                      _createVNode(_component_VTooltip, {
                        activator: "parent",
                        location: "top"
                      }, {
                        default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
                          _createTextVNode("新增自定义榜单", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3",
                  text: "每个榜单独立控制；地区为多选 OR，与评分、年份、数量等条件共同生效。空地区表示不限。"
                }),
                (customRankError.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      density: "compact",
                      class: "mb-2",
                      text: customRankError.value
                    }, null, 8, ["text"]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_33, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(rankDefs.value, (rd) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: rd.key,
                      class: _normalizeClass(["dc-rank-card", { 'dc-rank-card--on': form.rank_configs[rd.key]?.enabled, 'dc-rank-card--expanded': isExpanded(rd.key) }])
                    }, [
                      _createElementVNode("div", _hoisted_34, [
                        _createVNode(_component_VBtn, {
                          icon: "",
                          "aria-label": `${isExpanded(rd.key) ? '收起' : '展开'}${rd.name}`,
                          variant: "text",
                          size: "small",
                          class: "dc-rank-expand",
                          onClick: $event => (toggleRank(rd.key))
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VIcon, {
                              icon: isExpanded(rd.key) ? 'mdi-chevron-down' : 'mdi-chevron-right',
                              size: "20"
                            }, null, 8, ["icon"])
                          ]),
                          _: 2
                        }, 1032, ["aria-label", "onClick"]),
                        _createVNode(_component_VCheckbox, {
                          modelValue: form.rank_configs[rd.key].enabled,
                          "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].enabled) = $event),
                          color: "primary",
                          "hide-details": "",
                          density: "compact",
                          class: "dc-rank-check",
                          "aria-label": `启用${rd.name}`
                        }, null, 8, ["modelValue", "onUpdate:modelValue", "aria-label"]),
                        _createElementVNode("div", {
                          class: "dc-rank-summary-main",
                          onClick: $event => (toggleRank(rd.key))
                        }, [
                          _createElementVNode("div", _hoisted_36, [
                            _createElementVNode("span", null, _toDisplayString(rd.name), 1),
                            (rd.custom)
                              ? (_openBlock(), _createBlock(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  color: "primary",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                                    _createTextVNode("自定义", -1)
                                  ]))]),
                                  _: 1
                                }))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_37, [
                            _createElementVNode("span", null, "数量 " + _toDisplayString(form.rank_configs[rd.key]?.count || '不限'), 1),
                            (rd.filters.includes('vote'))
                              ? (_openBlock(), _createElementBlock("span", _hoisted_38, "评分 " + _toDisplayString(form.rank_configs[rd.key]?.vote || '不限'), 1))
                              : _createCommentVNode("", true),
                            _createElementVNode("span", null, "地区 " + _toDisplayString((form.rank_configs[rd.key]?.regions || []).join('、') || '不限'), 1),
                            (rd.filters.includes('year'))
                              ? (_openBlock(), _createElementBlock("span", _hoisted_39, "年份 " + _toDisplayString(form.rank_configs[rd.key]?.year || '不限'), 1))
                              : _createCommentVNode("", true),
                            (rd.filters.includes('wish_count'))
                              ? (_openBlock(), _createElementBlock("span", _hoisted_40, "想看 " + _toDisplayString(form.rank_configs[rd.key]?.wish_count || '不限'), 1))
                              : _createCommentVNode("", true)
                          ])
                        ], 8, _hoisted_35),
                        _createElementVNode("div", _hoisted_41, [
                          (rd.custom)
                            ? (_openBlock(), _createBlock(_component_VBtn, {
                                key: 0,
                                icon: "",
                                variant: "flat",
                                color: "error",
                                class: "dc-delete-rank",
                                "aria-label": `删除${rd.name || '自定义榜单'}`,
                                onClick: _withModifiers($event => (requestRemoveCustomRank(rd)), ["stop"])
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-delete-outline",
                                    size: "20"
                                  }),
                                  _createVNode(_component_VTooltip, {
                                    activator: "parent",
                                    location: "top"
                                  }, {
                                    default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                                      _createTextVNode("删除自定义榜单", -1)
                                    ]))]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              }, 8, ["aria-label", "onClick"]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _createVNode(_component_VExpandTransition, null, {
                        default: _withCtx(() => [
                          (isExpanded(rd.key))
                            ? (_openBlock(), _createElementBlock("div", _hoisted_42, [
                                _createElementVNode("div", _hoisted_43, [
                                  _createVNode(_component_VCheckbox, {
                                    modelValue: form.rank_configs[rd.key].enabled,
                                    "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].enabled) = $event),
                                    label: "自动订阅",
                                    color: "primary",
                                    "hide-details": "",
                                    density: "compact",
                                    class: "dc-rank-detail-enable"
                                  }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                                  _createElementVNode("div", _hoisted_44, [
                                    _createVNode(_component_VTextField, {
                                      modelValue: form.rank_configs[rd.key].count,
                                      "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].count) = $event),
                                      modelModifiers: { number: true },
                                      label: "数量",
                                      placeholder: "0 不限",
                                      type: "number",
                                      min: "0",
                                      density: "compact",
                                      variant: "outlined",
                                      "hide-details": "",
                                      class: "dc-rank-input"
                                    }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                  ]),
                                  (rd.filters.includes('vote'))
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_45, [
                                        _createVNode(_component_VTextField, {
                                          modelValue: form.rank_configs[rd.key].vote,
                                          "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].vote) = $event),
                                          modelModifiers: { number: true },
                                          label: "评分",
                                          placeholder: "0 不限",
                                          type: "number",
                                          min: "0",
                                          max: "10",
                                          step: "0.1",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": "",
                                          class: "dc-rank-input"
                                        }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                      ]))
                                    : _createCommentVNode("", true),
                                  _createVNode(_component_VCombobox, {
                                    modelValue: form.rank_configs[rd.key].regions,
                                    "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].regions) = $event),
                                    items: [],
                                    label: "地区",
                                    placeholder: "自定义填写",
                                    multiple: "",
                                    chips: "",
                                    "closable-chips": "",
                                    clearable: "",
                                    "hide-details": "",
                                    density: "compact",
                                    variant: "outlined",
                                    class: "dc-rank-regions"
                                  }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                                  (rd.filters.includes('year'))
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_46, [
                                        _createVNode(_component_VTextField, {
                                          modelValue: form.rank_configs[rd.key].year,
                                          "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].year) = $event),
                                          modelModifiers: { number: true },
                                          label: "年份",
                                          placeholder: "0 不限",
                                          type: "number",
                                          min: "0",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": "",
                                          class: "dc-rank-input"
                                        }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                      ]))
                                    : _createCommentVNode("", true),
                                  (rd.filters.includes('wish_count'))
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_47, [
                                        _createVNode(_component_VTextField, {
                                          modelValue: form.rank_configs[rd.key].wish_count,
                                          "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].wish_count) = $event),
                                          modelModifiers: { number: true },
                                          label: "想看",
                                          placeholder: "0 不限",
                                          type: "number",
                                          min: "0",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": "",
                                          class: "dc-rank-input"
                                        }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                      ]))
                                    : _createCommentVNode("", true)
                                ]),
                                (rd.custom)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
                                      _createVNode(_component_VTextField, {
                                        ref_for: true,
                                        ref: el => setNameInputRef(rd.key, el),
                                        modelValue: rd.model.name,
                                        "onUpdate:modelValue": $event => ((rd.model.name) = $event),
                                        label: "榜单名称",
                                        density: "compact",
                                        variant: "outlined",
                                        "hide-details": "",
                                        class: "dc-custom-rank-name"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                                      _createVNode(_component_VTextField, {
                                        modelValue: rd.model.route,
                                        "onUpdate:modelValue": $event => ((rd.model.route) = $event),
                                        label: "路由",
                                        placeholder: "/example/rsshub/route?foo=bar",
                                        density: "compact",
                                        variant: "outlined",
                                        "hide-details": "",
                                        class: "dc-custom-rank-route"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]))
                                  : (_openBlock(), _createElementBlock("div", _hoisted_49, "路由：" + _toDisplayString(rd.route), 1))
                              ]))
                            : _createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1024)
                    ], 2))
                  }), 128))
                ]),
                (!form.custom_ranks.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_50, "尚未添加自定义榜单"))
                  : _createCommentVNode("", true),
                _createVNode(_component_VDialog, {
                  modelValue: deleteDialog.value,
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((deleteDialog).value = $event)),
                  "max-width": "420"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCard, null, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCardTitle, { class: "text-body-1" }, {
                          default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                            _createTextVNode("删除自定义榜单", -1)
                          ]))]),
                          _: 1
                        }),
                        _createVNode(_component_VCardText, null, {
                          default: _withCtx(() => [
                            _createTextVNode("确定删除「" + _toDisplayString(deleteTarget.value?.name || '未命名榜单') + "」吗？相关订阅、历史和运行条目不会被删除。", 1)
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_VCardActions, null, {
                          default: _withCtx(() => [
                            _createVNode(_component_VSpacer),
                            _createVNode(_component_VBtn, {
                              variant: "text",
                              onClick: _cache[4] || (_cache[4] = $event => (deleteDialog.value = false))
                            }, {
                              default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                                _createTextVNode("取消", -1)
                              ]))]),
                              _: 1
                            }),
                            _createVNode(_component_VBtn, {
                              color: "error",
                              variant: "tonal",
                              onClick: _cache[5] || (_cache[5] = $event => (removeCustomRank(deleteTarget.value?.key)))
                            }, {
                              default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                                _createTextVNode("删除", -1)
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
              ], 512), [
                [_vShow, activeSub.value === 'list']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_51, [
                _cache[45] || (_cache[45] = _createElementVNode("div", { class: "dc-section-title" }, "观察设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.observe_rank_keys,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.observe_rank_keys) = $event)),
                          items: rankDefs.value.map(r => ({ title: r.name, value: r.key })),
                          label: "观察榜单",
                          multiple: "",
                          chips: "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "被选中的榜单会先进入观察队列，达到观察期后再订阅",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.observe_days,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.observe_days) = $event)),
                          modelModifiers: { number: true },
                          label: "观察期（天）",
                          type: "number",
                          min: "0",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "新条目在榜 N 天后才订阅，0 为不启用",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.blacklist_keywords,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.blacklist_keywords) = $event)),
                          label: "黑名单关键词（一行一个）",
                          rows: "3",
                          "auto-grow": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "标题包含任一关键词则跳过订阅。支持片段匹配，如输入「综艺」会匹配所有含「综艺」的剧名",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_52, [
                _cache[50] || (_cache[50] = _createElementVNode("div", { class: "dc-section-title" }, "同步想看", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.wish_enabled,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.wish_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用想看同步"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.wish_onlyonce,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.wish_onlyonce) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.wish_cron,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.wish_cron) = $event)),
                          label: "独立同步周期",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.wish_days,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.wish_days) = $event)),
                          modelModifiers: { number: true },
                          label: "最近天数",
                          type: "number",
                          min: "0",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 7 天",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.wish_user,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.wish_user) = $event)),
                          label: "豆瓣用户 ID",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "读取该用户的动态 feed，仅处理「想看」条目",
                          "persistent-hint": ""
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
                          modelValue: form.wish_notify,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.wish_notify) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "发送通知"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  class: "mt-3",
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  text: "通过豆瓣动态 feed 同步，首次只建立最近天数内的基线；后续周期只处理最近天数内新增的想看。"
                }),
                _createElementVNode("div", _hoisted_53, [
                  _createElementVNode("div", _hoisted_54, [
                    _cache[46] || (_cache[46] = _createElementVNode("span", null, "队列待处理", -1)),
                    _createElementVNode("strong", null, _toDisplayString(overview.value?.cards?.folio?.wish?.queue || 0), 1)
                  ]),
                  _createElementVNode("div", _hoisted_55, [
                    _cache[47] || (_cache[47] = _createElementVNode("span", null, "失败记录", -1)),
                    _createElementVNode("strong", null, _toDisplayString(overview.value?.cards?.folio?.wish?.failed || 0), 1)
                  ]),
                  _createElementVNode("div", _hoisted_56, [
                    _cache[48] || (_cache[48] = _createElementVNode("span", null, "最近运行", -1)),
                    _createElementVNode("strong", null, _toDisplayString(overview.value?.cards?.folio?.wish?.last_run || '尚未运行'), 1)
                  ]),
                  _createElementVNode("div", _hoisted_57, [
                    _cache[49] || (_cache[49] = _createElementVNode("span", null, "状态错误", -1)),
                    _createElementVNode("strong", null, _toDisplayString(overview.value?.cards?.folio?.wish?.last_error || '无'), 1)
                  ])
                ])
              ], 512), [
                [_vShow, activeSub.value === 'wish']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_58, [
                _cache[51] || (_cache[51] = _createElementVNode("div", { class: "dc-section-title" }, "同步观影", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.folio_enabled,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.folio_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用豆瓣时间"
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
                          modelValue: form.folio_private,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.folio_private) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "仅自己可见"
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
                          modelValue: form.folio_first,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.folio_first) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "不标记第一集"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.folio_notify,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.folio_notify) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "发送通知"
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
                          modelValue: form.folio_exclude_live_tv,
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.folio_exclude_live_tv) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "排除电视直播源"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_user,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.folio_user) = $event)),
                          label: "媒体库用户名（多个以 , 分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_exclude,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.folio_exclude) = $event)),
                          label: "路径排除关键词（多个以 , 分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_cookie,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.folio_cookie) = $event)),
                          label: "豆瓣 Cookie（留空从 CookieCloud 获取）",
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
                [_vShow, activeSub.value === 'sync']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_59, [
                _cache[52] || (_cache[52] = _createElementVNode("div", { class: "dc-section-title" }, "仪表盘选择", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2",
                  text: "仪表盘最多显示 6 个已启用榜单；开启发现页后，保存并刷新 MP 页面即可从左侧「发现」分组进入豆瓣中心。"
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.dashboard_rank_keys,
                          "onUpdate:modelValue": [
                            _cache[24] || (_cache[24] = $event => ((form.dashboard_rank_keys) = $event)),
                            limitDashboardRanks
                          ],
                          label: "选择要显示的榜单（最多 6 个）",
                          items: rankDefs.value.filter(r => form.rank_configs?.[r.key]?.enabled).map(r => ({ title: r.name, value: r.key })),
                          multiple: "",
                          chips: "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.discovery_page_enabled,
                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.discovery_page_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "开启发现页"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'view']
              ])
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "dc-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              class: "dc-action-btn",
              onClick: _cache[26] || (_cache[26] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              class: "dc-action-btn dc-action-btn--save",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2b3b9352"]]);

export { Config as default };
