import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useRequestScope, t as toPosterThumbnail, a as getPluginApi, o as openNativeSubscription, p as postPluginApi, _ as _export_sfc } from './useRequestScope-CDEhkzJg.js';
import { u as useManagementPermissions, a as useRankDialog, b as useRankMediaActions, s as sourceDescriptor, r as rankNames, c as rankIconColors, d as doubanDispatchUrl } from './useRankDialog-Bbb1bemS.js';

const {ref,computed,onMounted} = await importShared('vue');


function useDashboardRuntime(props) {
  const dashboardPluginId = computed(
    () => String(props.pluginId || props.config?.id || 'DoubanCenter').trim() || 'DoubanCenter',
  );

  const { canManage, permissionError } = useManagementPermissions(() => props.api, () => dashboardPluginId.value);

  const config = ref({});
  const rankHistory = ref({});
  const folioData = ref({});
  const loading = ref(false);
  const folioLoading = ref(false);
  const refreshing = ref(false);
  const subscribeResult = ref('');
  const refreshResult = ref('');
  const loadError = ref('');
  const { dialogItem, showDialog, dialogResolving, dialogResolveError, dialogResolveToken, showActionDialog } = useRankDialog({
    requestScope: () => requestScope,
    resolveRankMedia: (...args) => resolveRankMedia(...args),
    tmdbIdOf: item => tmdbIdOf(item),
  });

  const timelineImageFailed = ref({});
  let loadEpoch = 0;
  let rankEpoch = 0;
  let refreshEpoch = 0;
  let subscribeEpoch = 0;
  const requestScope = useRequestScope(() => dashboardPluginId.value, () => {
    loadEpoch += 1;
    refreshEpoch += 1;
    subscribeEpoch += 1;
    dialogResolveToken.value += 1;
    loading.value = false;
    folioLoading.value = false;
    refreshing.value = false;
    dialogResolving.value = false;
    showDialog.value = false;
    subscribeResult.value = '';
    refreshResult.value = '';
  });

  const TIMELINE_MONTH_LIMIT = 3;
  const TIMELINE_ITEM_LIMIT = 50;
  const INITIAL_LOAD_TIMEOUT_MS = 8000;
  const TIMELINE_RETRY_DELAYS_MS = [800, 2500];
  const TIMELINE_RETRY_TIMEOUT_MS = 12000;

  function rankColorOf(key) {
    return rankIconColors[key] || rankIconColors.unknown
  }

  function rankIconStyle(key) {
    return { color: rankColorOf(key) }
  }

  function rankNameOf(key, item = null) {
    if (item?.rank_name) return item.rank_name
    const option = (config.value?.rank_options || []).find(entry => entry?.value === key);
    return option?.title || rankNames[key] || key
  }

  const {
    mediaTypeOf,
    normalizeApiData,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  } = useRankMediaActions({
    api: () => props.api,
    pluginId: () => dashboardPluginId.value,
    rankNameOf,
  });

  async function requestFolioData(timeoutMs) {
    const response = await getPluginApi(props.api, dashboardPluginId.value, 'folio_data', { timeoutMs });
    if (response?.success === false) throw new Error(response.message || '追影时间线加载失败')
    return response
  }

  async function loadFolioData() {
    const owner = requestScope.capture();
    const epoch = loadEpoch;
    const current = () => owner() && epoch === loadEpoch;
    let lastError = null;
    for (let attempt = 0; attempt <= TIMELINE_RETRY_DELAYS_MS.length; attempt += 1) {
      if (!current()) return null
      if (attempt > 0) {
        if (!await requestScope.wait(TIMELINE_RETRY_DELAYS_MS[attempt - 1]) || !current()) return null
      }
      try {
        const timeoutMs = attempt === 0 ? INITIAL_LOAD_TIMEOUT_MS : TIMELINE_RETRY_TIMEOUT_MS;
        return await requestFolioData(timeoutMs)
      } catch (error) {
        if (!current()) return null
        lastError = error;
        if (error?.code === 'PLUGIN_API_TIMEOUT' && attempt > 0) break
      }
    }
    throw lastError || new Error('追影时间线加载失败')
  }

  async function load() {
    if (!requestScope.isActive()) return
    const owner = requestScope.capture();
    const epoch = ++loadEpoch;
    const rankRequestEpoch = rankEpoch;
    const current = () => owner() && epoch === loadEpoch;
    loading.value = true;
    folioLoading.value = true;
    loadError.value = '';
    const errors = [];
    const folioRequest = Promise.allSettled([loadFolioData()]);
    const coreRequests = [
      { label: '仪表配置', run: getPluginApi(props.api, dashboardPluginId.value, 'config', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS }) },
      { label: '榜单快照', run: getPluginApi(props.api, dashboardPluginId.value, 'rank_history', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS }) },
    ];
    const coreResults = await Promise.allSettled(coreRequests.map(item => item.run));
    if (!current()) return

    coreResults.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        if (result.value?.success === false) {
          errors.push(coreRequests[index].label);
          return
        }
        const data = normalizeApiData(result.value);
        if (index === 0) config.value = data || {};
        else if (rankRequestEpoch === rankEpoch) rankHistory.value = data || {};
        return
      }
      errors.push(coreRequests[index].label);
      console.error(`[DoubanCenter] ${coreRequests[index].label}加载失败`, result.reason);
    });
    loading.value = false;

    const [folioResult] = await folioRequest;
    if (!current()) return
    if (folioResult.status === 'fulfilled') {
      if (folioResult.value?.success === false) {
        errors.push('追影时间线');
        } else {
          folioData.value = normalizeApiData(folioResult.value) || {};
          timelineImageFailed.value = {};
        }
    } else {
      errors.push('追影时间线');
      console.error('[DoubanCenter] 追影时间线加载失败', folioResult.reason);
    }
    folioLoading.value = false;
    loadError.value = errors.length ? `部分数据加载失败：${errors.join('、')}` : '';
  }

  async function refreshDashboard() {
    if (refreshing.value || !requestScope.isActive()) return
    const owner = requestScope.capture();
    const epoch = ++refreshEpoch;
    const current = () => owner() && epoch === refreshEpoch;
    refreshing.value = true;
    refreshResult.value = '';
    try {
      const res = await postPluginApi(props.api, dashboardPluginId.value, 'refresh_rss', {});
      if (!current()) return
      if (res.success) {
        rankEpoch += 1;
        if (res.data) rankHistory.value = res.data;
        refreshResult.value = 'RSS 已刷新';
      } else {
        refreshResult.value = res.message || 'RSS 刷新失败';
      }
    } catch (e) {
      if (!current()) return
      refreshResult.value = `刷新失败: ${e}`;
    }
    refreshing.value = false;
    requestScope.later(() => { if (current()) refreshResult.value = ''; }, 3000);
  }


  function markTimelineImageFailed(key) {
    timelineImageFailed.value = { ...timelineImageFailed.value, [key]: true };
  }

  function dialogPoster() {
    const item = dialogItem.value?.item || {};
    return toPosterThumbnail(item.poster || item.poster_path || item.cover)
  }

  async function subscribeViaNativeDialog(rk, item, current) {
    const open = props.nativeSubscribe;
    const media = await resolveRankMedia(rk, item);
    if (!current()) return
    await openNativeSubscription(open, media);
    if (!current()) return
    subscribeResult.value = '已打开 MP 原生订阅窗口';
  }

  async function subscribeRankItem(rk, item, current) {
    const res = await requestRankSubscription(rk, item);
    if (!current()) return
    if (!res?.success) throw new Error(res?.message || '订阅失败')
    subscribeResult.value = res?.message || `${item.title || ''} 已添加订阅`;
  }

  async function doSubscribe() {
    if (!dialogItem.value || dialogResolving.value) return
    if (!requestScope.isActive()) return
    const owner = requestScope.capture();
    const epoch = ++subscribeEpoch;
    const current = () => owner() && epoch === subscribeEpoch;
    const { rk, item } = dialogItem.value;
    showDialog.value = false;
    subscribeResult.value = '';
    try {
      if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item, current);
      else await subscribeRankItem(rk, item, current);
    } catch (e) {
      if (!current()) return
      subscribeResult.value = `订阅失败: ${e?.message || e}`;
    }
    if (current()) requestScope.later(() => { if (current()) subscribeResult.value = ''; }, 3000);
  }

  function sourceButtonColor() {
    if (!dialogItem.value) return 'primary'
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, config.value).color
  }

  function sourceButtonIcon() {
    if (!dialogItem.value) return 'mdi-link-variant'
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, config.value).icon
  }

  function sourceButtonLabel() {
    if (!dialogItem.value) return '详情'
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, config.value).label
  }

  function sourceButtonUrl() {
    if (!dialogItem.value) return ''
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, config.value).url
  }

  function sourceButtonAppUrl() {
    if (!dialogItem.value) return ''
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, config.value).appUrl || ''
  }

  function sourceButtonHref() {
    const webUrl = sourceButtonUrl();
    return sourceButtonAppUrl() || webUrl
  }

  function openSource(event) {
    const appUrl = sourceButtonAppUrl();
    if (!appUrl) {
      showDialog.value = false;
      return
    }
    event?.preventDefault?.();
    showDialog.value = false;
    window.open(appUrl, '_blank');
  }

  function doOpenTmdb() {
    if (!dialogItem.value) return
    const { rk, item } = dialogItem.value;
    const tmdbId = tmdbIdOf(item);
    if (!tmdbId) return
    const mediaType = mediaTypeOf(rk, item);
    const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`;
    showDialog.value = false;
    window.open(url, '_blank');
  }

  const timelineGroups = computed(() => {
    const data = folioData.value || {};
    const limitMonth = TIMELINE_MONTH_LIMIT;
    const limitNum = TIMELINE_ITEM_LIMIT;
    const entries = Object.entries(data)
      .filter(([, v]) => v && typeof v === 'object' && v.timestamp)
      .map(([key, val]) => ({ key, ...val }))
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const groups = [];
    let currentGroup = null;
    for (const entry of entries) {
      const d = new Date(entry.timestamp);
      const monthKey = `${d.getFullYear()}-${d.getMonth() + 1}`;
      if (!currentGroup || currentGroup.monthKey !== monthKey) {
        if (groups.length >= limitMonth) break
        currentGroup = { monthKey, year: d.getFullYear(), month: d.getMonth() + 1, label: `${d.getFullYear()}年${d.getMonth() + 1}月`, items: [] };
        groups.push(currentGroup);
      }
      if (currentGroup.items.length < limitNum) {
        const poster = toPosterThumbnail(entry.poster_path);
        currentGroup.items.push({ key: entry.key, subject_name: entry.display_title || entry.subject_name || entry.key, subject_id: entry.subject_id, poster, type: entry.type });
      }
    }
    return groups
  });

  onMounted(load);

  return {
    rankColorOf,
    rankIconStyle,
    rankNameOf,
    requestFolioData,
    loadFolioData,
    load,
    refreshDashboard,
    showActionDialog,
    markTimelineImageFailed,
    dialogPoster,
    subscribeViaNativeDialog,
    subscribeRankItem,
    doSubscribe,
    sourceButtonColor,
    sourceButtonIcon,
    sourceButtonLabel,
    sourceButtonUrl,
    sourceButtonAppUrl,
    sourceButtonHref,
    openSource,
    doOpenTmdb,
    dashboardPluginId,
    config,
    rankHistory,
    folioData,
    loading,
    folioLoading,
    refreshing,
    subscribeResult,
    refreshResult,
    loadError,
    dialogItem,
    showDialog,
    dialogResolving,
    dialogResolveError,
    dialogResolveToken,
    timelineImageFailed,
    loadEpoch,
    rankEpoch,
    refreshEpoch,
    subscribeEpoch,
    requestScope,
    TIMELINE_MONTH_LIMIT,
    TIMELINE_ITEM_LIMIT,
    INITIAL_LOAD_TIMEOUT_MS,
    TIMELINE_RETRY_DELAYS_MS,
    TIMELINE_RETRY_TIMEOUT_MS,
    timelineGroups,
    canManage,
    permissionError,
    mediaTypeOf,
    normalizeApiData,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  }
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeStyle:_normalizeStyle,isRef:_isRef} = await importShared('vue');


const _hoisted_1 = { class: "dc-load-alert__content" };
const _hoisted_2 = {
  key: 3,
  class: "mb-3"
};
const _hoisted_3 = { class: "dc-rank-grid" };
const _hoisted_4 = {
  class: "dc-rank-cell dc-tl-cell",
  style: {"grid-column":"1 / -1"}
};
const _hoisted_5 = { class: "dc-rank-head" };
const _hoisted_6 = { class: "dc-rank-body" };
const _hoisted_7 = { class: "dc-timeline-scroll" };
const _hoisted_8 = { class: "dc-timeline-months" };
const _hoisted_9 = {
  class: "text-caption text-medium-emphasis mb-1",
  style: {"font-size":"11px"}
};
const _hoisted_10 = { class: "dc-timeline-posters" };
const _hoisted_11 = ["href", "title"];
const _hoisted_12 = {
  key: 1,
  class: "dc-ph"
};
const _hoisted_13 = { key: 4 };
const _hoisted_14 = { class: "dc-rank-grid" };
const _hoisted_15 = { class: "dc-rank-head" };
const _hoisted_16 = { class: "dc-rank-body" };
const _hoisted_17 = ["title", "onClick"];
const _hoisted_18 = { class: "dc-rank-title" };
const _hoisted_19 = {
  key: 0,
  class: "dc-rank-wish"
};
const _hoisted_20 = {
  key: 0,
  class: "text-center text-medium-emphasis py-2 text-caption"
};
const _hoisted_21 = {
  key: 5,
  class: "text-center text-medium-emphasis py-4 text-caption"
};


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: '' },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
  nativeSubscribe: { type: Function, default: null },
},
  setup(__props) {

const props = __props;

const {
  rankIconStyle,
  rankNameOf,
  load,
  refreshDashboard,
  showActionDialog,
  markTimelineImageFailed,
  dialogPoster,
  doSubscribe,
  sourceButtonColor,
  sourceButtonIcon,
  sourceButtonLabel,
  sourceButtonUrl,
  sourceButtonHref,
  openSource,
  doOpenTmdb,
  config,
  rankHistory,
  loading,
  folioLoading,
  refreshing,
  subscribeResult,
  refreshResult,
  loadError,
  dialogItem,
  showDialog,
  dialogResolving,
  dialogResolveError,
  timelineImageFailed,
  timelineGroups,
  canManage,
  permissionError,
  tmdbIdOf,
} = useDashboardRuntime(props);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createBlock(_component_VCard, {
    class: "dc-card",
    variant: "flat"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, null, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-book-open-page-variant-outline" })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "x-small",
            "prepend-icon": "mdi-refresh",
            class: "text-none",
            loading: _unref(refreshing),
            disabled: !_unref(canManage),
            title: _unref(canManage) ? '刷新榜单' : _unref(permissionError) || '刷新榜单需要管理员权限',
            onClick: _unref(refreshDashboard)
          }, {
            default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading", "disabled", "title", "onClick"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, null, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("豆瓣中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("点击榜单条目可选择来源、TMDB 或订阅", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      (_unref(loading) || _unref(folioLoading))
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true),
      _createVNode(_component_VCardText, { class: "pa-3" }, {
        default: _withCtx(() => [
          (_unref(loadError))
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "mb-2 dc-load-alert"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_1, [
                    _createElementVNode("span", null, _toDisplayString(_unref(loadError)), 1),
                    _createVNode(_component_VBtn, {
                      variant: "text",
                      size: "x-small",
                      "prepend-icon": "mdi-refresh",
                      class: "text-none",
                      loading: _unref(loading) || _unref(folioLoading),
                      onClick: _unref(load)
                    }, {
                      default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                        _createTextVNode("重试", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"])
                  ])
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (_unref(subscribeResult))
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 1,
                type: _unref(subscribeResult).includes('失败') ? 'error' : 'success',
                variant: "tonal",
                class: "mb-2",
                text: _unref(subscribeResult),
                density: "compact",
                closable: ""
              }, null, 8, ["type", "text"]))
            : _createCommentVNode("", true),
          (_unref(refreshResult))
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 2,
                type: _unref(refreshResult).includes('已刷新') ? 'success' : 'error',
                variant: "tonal",
                class: "mb-2",
                text: _unref(refreshResult),
                density: "compact",
                closable: ""
              }, null, 8, ["type", "text"]))
            : _createCommentVNode("", true),
          (_unref(timelineGroups).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
                _createElementVNode("div", _hoisted_3, [
                  _createElementVNode("div", _hoisted_4, [
                    _createElementVNode("div", _hoisted_5, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-timeline-clock-outline",
                        size: "14",
                        class: "mr-1",
                        color: "primary"
                      }),
                      _cache[5] || (_cache[5] = _createTextVNode("追影时间线", -1))
                    ]),
                    _createElementVNode("div", _hoisted_6, [
                      _createElementVNode("div", _hoisted_7, [
                        _createElementVNode("div", _hoisted_8, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(timelineGroups), (group) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: group.monthKey,
                              class: "dc-timeline-month"
                            }, [
                              _createElementVNode("div", _hoisted_9, [
                                _createTextVNode(_toDisplayString(group.label) + " ", 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: "primary",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(group.items.length), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _createElementVNode("div", _hoisted_10, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                                  return (_openBlock(), _createElementBlock("a", {
                                    key: item.key,
                                    href: _unref(doubanDispatchUrl)(item.subject_id, item.type),
                                    target: "_blank",
                                    rel: "noopener noreferrer",
                                    class: "dc-poster",
                                    title: item.subject_name
                                  }, [
                                    (item.poster && !_unref(timelineImageFailed)[item.key])
                                      ? (_openBlock(), _createBlock(_component_VImg, {
                                          key: 0,
                                          src: item.poster,
                                          width: "60",
                                          height: "90",
                                          cover: "",
                                          class: "rounded",
                                          onError: $event => (_unref(markTimelineImageFailed)(item.key))
                                        }, null, 8, ["src", "onError"]))
                                      : (_openBlock(), _createElementBlock("div", _hoisted_12, [
                                          _createVNode(_component_VIcon, {
                                            icon: "mdi-filmstrip",
                                            size: "14"
                                          })
                                        ]))
                                  ], 8, _hoisted_11))
                                }), 128))
                              ])
                            ]))
                          }), 128))
                        ])
                      ])
                    ])
                  ])
                ])
              ]))
            : _createCommentVNode("", true),
          (_unref(config).dashboard_rank_keys && _unref(config).dashboard_rank_keys.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_13, [
                _createElementVNode("div", _hoisted_14, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(config).dashboard_rank_keys.slice(0, 6), (rk) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: rk,
                      class: "dc-rank-cell"
                    }, [
                      _createElementVNode("div", _hoisted_15, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-format-list-numbered",
                          size: "15",
                          style: _normalizeStyle(_unref(rankIconStyle)(rk)),
                          class: "mr-1"
                        }, null, 8, ["style"]),
                        _createElementVNode("span", null, _toDisplayString(_unref(rankNameOf)(rk, _unref(rankHistory)[rk]?.[0])), 1)
                      ]),
                      _createElementVNode("div", _hoisted_16, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((_unref(rankHistory)[rk] || []).slice(0, 5), (item, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-rank-row",
                            title: item.title,
                            onClick: $event => (_unref(showActionDialog)(rk, item))
                          }, [
                            _createVNode(_component_VAvatar, {
                              rounded: "sm",
                              class: "dc-rank-poster"
                            }, {
                              default: _withCtx(() => [
                                (item.poster)
                                  ? (_openBlock(), _createBlock(_component_VImg, {
                                      key: 0,
                                      src: _unref(toPosterThumbnail)(item.poster),
                                      cover: ""
                                    }, null, 8, ["src"]))
                                  : (_openBlock(), _createBlock(_component_VIcon, {
                                      key: 1,
                                      icon: "mdi-filmstrip",
                                      size: "13"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", _hoisted_18, _toDisplayString(item.title), 1),
                            (rk === 'coming' && item.wish_count)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_19, _toDisplayString(item.wish_count), 1))
                              : _createCommentVNode("", true)
                          ], 8, _hoisted_17))
                        }), 128)),
                        (!(_unref(rankHistory)[rk] || []).length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_20, "暂无数据"))
                          : _createCommentVNode("", true)
                      ])
                    ]))
                  }), 128))
                ])
              ]))
            : _createCommentVNode("", true),
          (!_unref(loading) && !_unref(folioLoading) && !_unref(config).dashboard_rank_keys?.length && !_unref(timelineGroups).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_21, " 请在配置页「仪表显示」中选择要显示的榜单 "))
            : _createCommentVNode("", true)
        ]),
        _: 1
      }),
      _createVNode(_component_VDialog, {
        modelValue: _unref(showDialog),
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (_isRef(showDialog) ? (showDialog).value = $event : null)),
        "max-width": "420"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCard, {
            rounded: "lg",
            class: "dc-action-dialog"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, { class: "pa-3" }, {
                prepend: _withCtx(() => [
                  _createVNode(_component_VAvatar, {
                    size: "36",
                    rounded: "md",
                    class: "mr-2"
                  }, {
                    default: _withCtx(() => [
                      (_unref(dialogPoster)())
                        ? (_openBlock(), _createBlock(_component_VImg, {
                            key: 0,
                            src: _unref(dialogPoster)()
                          }, null, 8, ["src"]))
                        : (_openBlock(), _createBlock(_component_VIcon, {
                            key: 1,
                            icon: "mdi-filmstrip"
                          }))
                    ]),
                    _: 1
                  })
                ]),
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-body-1 font-weight-bold pa-0" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(_unref(dialogItem)?.item?.title || ''), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCardSubtitle, { class: "text-caption pa-0" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(_unref(dialogItem)?.rk ? _unref(rankNameOf)(_unref(dialogItem).rk, _unref(dialogItem).item) : ''), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              (_unref(dialogResolveError))
                ? (_openBlock(), _createBlock(_component_VAlert, {
                    key: 0,
                    type: "warning",
                    variant: "tonal",
                    density: "compact",
                    class: "mx-3 mt-3",
                    text: _unref(dialogResolveError)
                  }, null, 8, ["text"]))
                : _createCommentVNode("", true),
              _createVNode(_component_VCardActions, { class: "pa-3 pt-2 dc-dialog-actions" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-plus-circle-outline",
                    class: "dc-dialog-action text-none",
                    disabled: _unref(dialogResolving),
                    onClick: _unref(doSubscribe)
                  }, {
                    default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                      _createTextVNode("订阅", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    "prepend-icon": "mdi-movie-open-outline",
                    class: "dc-dialog-action dc-dialog-action--tmdb text-none",
                    loading: _unref(dialogResolving),
                    disabled: _unref(dialogResolving) || !_unref(tmdbIdOf)(_unref(dialogItem)?.item),
                    onClick: _unref(doOpenTmdb)
                  }, {
                    default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                      _createTextVNode("TMDB", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled", "onClick"]),
                  _createVNode(_component_VBtn, {
                    href: _unref(sourceButtonHref)() || undefined,
                    target: "_blank",
                    rel: "noopener noreferrer",
                    variant: "tonal",
                    color: _unref(sourceButtonColor)(),
                    "prepend-icon": _unref(sourceButtonIcon)(),
                    disabled: !_unref(sourceButtonUrl)(),
                    class: "dc-dialog-action text-none",
                    onClick: _unref(openSource)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(_unref(sourceButtonLabel)()), 1)
                    ]),
                    _: 1
                  }, 8, ["href", "color", "prepend-icon", "disabled", "onClick"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"])
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-7a930da6"]]);

export { Dashboard as default };
