import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-BHpYs4LN.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = {
  key: 3,
  class: "mb-3"
};
const _hoisted_2 = { class: "dc-rank-grid" };
const _hoisted_3 = {
  class: "dc-rank-cell dc-tl-cell",
  style: {"grid-column":"1 / -1"}
};
const _hoisted_4 = { class: "dc-rank-head" };
const _hoisted_5 = { class: "dc-rank-body" };
const _hoisted_6 = { class: "dc-timeline-scroll" };
const _hoisted_7 = { class: "dc-timeline-months" };
const _hoisted_8 = {
  class: "text-caption text-medium-emphasis mb-1",
  style: {"font-size":"11px"}
};
const _hoisted_9 = { class: "dc-timeline-posters" };
const _hoisted_10 = ["href", "title"];
const _hoisted_11 = {
  key: 1,
  class: "dc-ph"
};
const _hoisted_12 = { key: 4 };
const _hoisted_13 = { class: "dc-rank-grid" };
const _hoisted_14 = { class: "dc-rank-head" };
const _hoisted_15 = { class: "dc-rank-body" };
const _hoisted_16 = ["title", "onClick"];
const _hoisted_17 = { class: "dc-rank-title" };
const _hoisted_18 = {
  key: 0,
  class: "dc-rank-wish"
};
const _hoisted_19 = {
  key: 0,
  class: "text-center text-medium-emphasis py-2 text-caption"
};
const _hoisted_20 = {
  key: 5,
  class: "text-center text-medium-emphasis py-4 text-caption"
};

const {ref,computed,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
},
  setup(__props) {

const props = __props;

const config = ref({});
const rankHistory = ref({});
const folioData = ref({});
const loading = ref(false);
const refreshing = ref(false);
const subscribeResult = ref('');
const refreshResult = ref('');
const dialogItem = ref(null);
const showDialog = ref(false);

const rankDefs = {
  coming: { name: '即将上映' },
  tv_real_time: { name: '实时热门' },
  tv_chinese: { name: '华语口碑' },
  tv_global: { name: '全球口碑' },
  movie_weekly: { name: '电影口碑' },
  bangumi: { name: 'BangumiTV' },
};
const rankIconColors = {
  coming: '#f97316',
  tv_real_time: '#06b6d4',
  tv_chinese: '#eab308',
  tv_global: '#ef4444',
  movie_weekly: '#ec4899',
  bangumi: '#8b5cf6',
  unknown: '#94a3b8',
};

function rankColorOf(key) {
  return rankIconColors[key] || rankIconColors.unknown
}

function rankIconStyle(key) {
  return { color: rankColorOf(key) }
}

function queryString(params) {
  return Object.entries(params || {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}

function normalizeApiData(value) {
  if (value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, 'success')) return value
  return value?.data && !Array.isArray(value?.data) ? value.data : value
}

function mediaIdOf(media) {
  if (media?.tmdb_id) return `tmdb:${media.tmdb_id}`
  if (media?.douban_id) return `douban:${media.douban_id}`
  if (media?.bangumi_id) return `bangumi:${media.bangumi_id}`
  if (media?.media_id && media?.mediaid_prefix) return `${media.mediaid_prefix}:${media.media_id}`
  return ''
}

function bangumiIdOf(rk, item) {
  if (item?.bangumi_id || item?.bangumiid) return item.bangumi_id || item.bangumiid
  if (rk === 'bangumi' && item?.douban_id) return item.douban_id
  const match = String(item?.link || '').match(/(?:bgm\.tv|bangumi\.tv)\/subject\/(\d+)/);
  return match ? match[1] : ''
}

function mediaTypeOf(rk, item) {
  const type = item?.media_type || item?.mtype || item?.type || '';
  if (type === '电影' || type === 'movie') return 'movie'
  if (type === '电视剧' || type === 'tv') return 'tv'
  return rk === 'movie_weekly' ? 'movie' : 'tv'
}

async function resolveRankMedia(rk, item) {
  const mediaType = mediaTypeOf(rk, item);
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  });
  const res = normalizeApiData(await getPluginApi(props.api, `resolve_media?${params}`));
  if (res?.success === false) throw new Error(res?.message || '媒体识别失败')
  const media = res?.data && !Array.isArray(res.data) ? res.data : res;
  if (!media || typeof media !== 'object') throw new Error('媒体识别失败')
  const merged = { ...item, ...media };
  merged.title = media.title || media.name || item?.title || item?.name || '';
  merged.name = media.name || media.title || item?.name || item?.title || '';
  merged.year = media.year || item?.year || '';
  merged.type = media.type || (mediaType === 'movie' ? '电影' : '电视剧');
  merged.tmdb_id = media.tmdb_id || media.tmdbid || item?.tmdb_id || item?.tmdbid || null;
  merged.tmdbid = media.tmdbid || media.tmdb_id || item?.tmdbid || item?.tmdb_id || null;
  merged.douban_id = media.douban_id || media.doubanid || item?.douban_id || item?.doubanid || null;
  merged.doubanid = media.doubanid || media.douban_id || item?.doubanid || item?.douban_id || null;
  merged.bangumi_id = media.bangumi_id || media.bangumiid || bangumiIdOf(rk, item) || null;
  merged.bangumiid = media.bangumiid || media.bangumi_id || bangumiIdOf(rk, item) || null;
  if (!merged.mediaid_prefix || !merged.media_id) {
    const mediaId = mediaIdOf(merged);
    if (mediaId) {
      const [prefix, id] = mediaId.split(':');
      merged.mediaid_prefix = merged.mediaid_prefix || prefix;
      merged.media_id = merged.media_id || id;
    }
  }
  return merged
}

async function load() {
  loading.value = true;
  try {
    config.value = await getPluginApi(props.api, 'config') || {};
    rankHistory.value = await getPluginApi(props.api, 'rank_history') || {};
    folioData.value = await getPluginApi(props.api, 'folio_data') || {};
  } catch (e) {
    console.error(e);
  }
  loading.value = false;
}

async function refreshRss() {
  refreshing.value = true;
  refreshResult.value = '';
  try {
    const res = await postPluginApi(props.api, 'refresh_rss', {});
    if (res.success) {
      if (res.data) rankHistory.value = res.data;
      else rankHistory.value = await getPluginApi(props.api, 'rank_history') || {};
      refreshResult.value = 'RSS 已刷新';
    } else {
      refreshResult.value = res.message || 'RSS 刷新失败';
    }
  } catch (e) {
    refreshResult.value = `刷新失败: ${e}`;
  }
  refreshing.value = false;
  setTimeout(() => { refreshResult.value = ''; }, 3000);
}

function showActionDialog(rk, item) {
  dialogItem.value = { rk, item };
  showDialog.value = true;
}

function dialogPoster() {
  const item = dialogItem.value?.item || {};
  return item.poster || item.poster_path || item.cover || ''
}

async function subscribeViaNativeDialog(rk, item) {
  const media = await resolveRankMedia(rk, item);
  await props.nativeSubscribe(media);
  subscribeResult.value = '已打开 MP 原生订阅窗口';
}

async function subscribeRankItem(rk, item) {
  const mediaType = mediaTypeOf(rk, item);
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  });
  const res = await postPluginApi(props.api, `subscribe?${params}`, {});
  if (!res?.success) throw new Error(res?.message || '订阅失败')
  subscribeResult.value = res?.message || `${item.title || ''} 已添加订阅`;
}

async function doSubscribe() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  showDialog.value = false;
  subscribeResult.value = '';
  try {
    if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item);
    else await subscribeRankItem(rk, item);
  } catch (e) {
    subscribeResult.value = `订阅失败: ${e?.message || e}`;
  }
  setTimeout(() => { subscribeResult.value = ''; }, 3000);
}

function doOpenSource() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  showDialog.value = false;
  const link = item?.link || '';
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) {
    if (link) window.open(link, '_blank');
    return
  }
  const subjectId = item?.douban_id || item?.doubanid || '';
  if (subjectId) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${subjectId}?from=mdouban&open=app`, '_blank');
    return
  }
  const match = link.match(/subject\/(\d+)/);
  if (match && (link.includes('douban.com') || link.includes('doubanapp'))) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${match[1]}?from=mdouban&open=app`, '_blank');
    return
  }
  if (link) window.open(link, '_blank');
}

function sourceButtonColor() {
  if (!dialogItem.value) return 'primary'
  const { rk, item } = dialogItem.value;
  const link = String(item?.link || '');
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) return '#F838A0'
  if (link.includes('douban') || item?.douban_id || item?.doubanid) return '#08B810'
  return 'primary'
}

function sourceButtonIcon() {
  const { rk, item } = dialogItem.value || {};
  const link = String(item?.link || '');
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) return 'mdi-link-variant'
  if (link.includes('douban')) return 'mdi-open-in-new'
  return 'mdi-link-variant'
}

function sourceButtonLabel() {
  const { rk, item } = dialogItem.value || {};
  const link = String(item?.link || '');
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) return 'Bgm'
  if (link.includes('douban') || item?.douban_id || item?.doubanid) return '豆瓣'
  return '详情'
}

function doOpenTmdb() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  const tmdbId = item?.tmdbid || item?.tmdb_id || '';
  if (!tmdbId) return
  const mediaType = mediaTypeOf(rk, item);
  const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`;
  showDialog.value = false;
  window.open(url, '_blank');
}

const timelineGroups = computed(() => {
  const data = folioData.value || {};
  const limitMonth = config.value?.folio_pc_month || 3;
  const limitNum = config.value?.folio_pc_num || 50;
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
      const poster = (entry.poster_path || '').replace('/original/', '/w200/');
      currentGroup.items.push({ key: entry.key, subject_name: entry.subject_name || entry.key, subject_id: entry.subject_id, poster, type: entry.type });
    }
  }
  return groups
});

onMounted(load);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
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
            loading: refreshing.value,
            onClick: refreshRss
          }, {
            default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading"])
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
      _createVNode(_component_VCardText, { class: "pa-3" }, {
        default: _withCtx(() => [
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                key: 0,
                indeterminate: "",
                color: "primary",
                class: "d-block mx-auto my-6"
              }))
            : _createCommentVNode("", true),
          (subscribeResult.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 1,
                type: subscribeResult.value.includes('失败') ? 'error' : 'success',
                variant: "tonal",
                class: "mb-2",
                text: subscribeResult.value,
                density: "compact",
                closable: ""
              }, null, 8, ["type", "text"]))
            : _createCommentVNode("", true),
          (refreshResult.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 2,
                type: refreshResult.value.includes('已刷新') ? 'success' : 'error',
                variant: "tonal",
                class: "mb-2",
                text: refreshResult.value,
                density: "compact",
                closable: ""
              }, null, 8, ["type", "text"]))
            : _createCommentVNode("", true),
          (timelineGroups.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                _createElementVNode("div", _hoisted_2, [
                  _createElementVNode("div", _hoisted_3, [
                    _createElementVNode("div", _hoisted_4, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-timeline-clock-outline",
                        size: "14",
                        class: "mr-1",
                        color: "primary"
                      }),
                      _cache[4] || (_cache[4] = _createTextVNode("追影时间线", -1))
                    ]),
                    _createElementVNode("div", _hoisted_5, [
                      _createElementVNode("div", _hoisted_6, [
                        _createElementVNode("div", _hoisted_7, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timelineGroups.value, (group) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: group.monthKey,
                              class: "dc-timeline-month"
                            }, [
                              _createElementVNode("div", _hoisted_8, [
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
                              _createElementVNode("div", _hoisted_9, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                                  return (_openBlock(), _createElementBlock("a", {
                                    key: item.key,
                                    href: `https://www.douban.com/doubanapp/dispatch?uri=/movie/${item.subject_id}?from=mdouban&open=app`,
                                    target: "_blank",
                                    class: "dc-poster",
                                    title: item.subject_name
                                  }, [
                                    (item.poster)
                                      ? (_openBlock(), _createBlock(_component_VImg, {
                                          key: 0,
                                          src: item.poster,
                                          width: "60",
                                          height: "90",
                                          cover: "",
                                          class: "rounded"
                                        }, null, 8, ["src"]))
                                      : (_openBlock(), _createElementBlock("div", _hoisted_11, [
                                          _createVNode(_component_VIcon, {
                                            icon: "mdi-filmstrip",
                                            size: "14"
                                          })
                                        ]))
                                  ], 8, _hoisted_10))
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
          (config.value.dashboard_rank_keys && config.value.dashboard_rank_keys.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                _createElementVNode("div", _hoisted_13, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(config.value.dashboard_rank_keys, (rk) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: rk,
                      class: "dc-rank-cell"
                    }, [
                      _createElementVNode("div", _hoisted_14, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-format-list-numbered",
                          size: "15",
                          style: _normalizeStyle(rankIconStyle(rk)),
                          class: "mr-1"
                        }, null, 8, ["style"]),
                        _createElementVNode("span", null, _toDisplayString(rankDefs[rk]?.name || rk), 1)
                      ]),
                      _createElementVNode("div", _hoisted_15, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((rankHistory.value[rk] || []).slice(0, 5), (item, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-rank-row",
                            title: item.title,
                            onClick: $event => (showActionDialog(rk, item))
                          }, [
                            _createVNode(_component_VAvatar, {
                              size: "16",
                              class: "dc-rank-poster"
                            }, {
                              default: _withCtx(() => [
                                (item.poster)
                                  ? (_openBlock(), _createBlock(_component_VImg, {
                                      key: 0,
                                      src: item.poster
                                    }, null, 8, ["src"]))
                                  : (_openBlock(), _createBlock(_component_VIcon, {
                                      key: 1,
                                      icon: "mdi-filmstrip",
                                      size: "10"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", _hoisted_17, _toDisplayString(item.title), 1),
                            (rk === 'coming' && item.wish_count)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_18, _toDisplayString(item.wish_count), 1))
                              : _createCommentVNode("", true)
                          ], 8, _hoisted_16))
                        }), 128)),
                        (!(rankHistory.value[rk] || []).length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_19, "暂无数据"))
                          : _createCommentVNode("", true)
                      ])
                    ]))
                  }), 128))
                ])
              ]))
            : _createCommentVNode("", true),
          (!loading.value && !config.value.dashboard_rank_keys?.length && !timelineGroups.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_20, " 请在配置页「仪表显示」中选择要显示的榜单 "))
            : _createCommentVNode("", true)
        ]),
        _: 1
      }),
      _createVNode(_component_VDialog, {
        modelValue: showDialog.value,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((showDialog).value = $event)),
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
                      (dialogPoster())
                        ? (_openBlock(), _createBlock(_component_VImg, {
                            key: 0,
                            src: dialogPoster()
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
                      _createTextVNode(_toDisplayString(dialogItem.value?.item?.title || ''), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCardSubtitle, { class: "text-caption pa-0" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(dialogItem.value?.rk ? (rankDefs[dialogItem.value.rk]?.name || dialogItem.value.rk) : ''), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              _createVNode(_component_VCardActions, {
                class: "pa-3 pt-2",
                style: {"gap":"8px"}
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-plus-circle-outline",
                    class: "dc-dialog-action text-none",
                    onClick: doSubscribe
                  }, {
                    default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                      _createTextVNode("订阅", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "info",
                    "prepend-icon": "mdi-movie-open-outline",
                    class: "dc-dialog-action text-none",
                    disabled: !(dialogItem.value?.item?.tmdbid || dialogItem.value?.item?.tmdb_id),
                    onClick: doOpenTmdb
                  }, {
                    default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                      _createTextVNode("TMDB", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: sourceButtonColor(),
                    "prepend-icon": sourceButtonIcon(),
                    class: "dc-dialog-action text-none",
                    onClick: doOpenSource
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(sourceButtonLabel()), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "prepend-icon"])
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
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2cc0aef0"]]);

export { Dashboard as default };
