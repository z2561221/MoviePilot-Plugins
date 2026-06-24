import { importShared } from './__federation_fn_import.JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper.pcqpp-6-.js';

function unwrap(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'data')) return data.data
  return data
}
async function getPluginApi(api, path) {
  if (api?.get) return unwrap(await api.get(`plugin/DoubanCenterNew2/${path}`))
  const r = await fetch(`/api/v1/plugin/DoubanCenterNew2/${path}`);
  return unwrap(await r.json())
}
async function postPluginApi(api, path, body = {}) {
  if (api?.post) return unwrap(await api.post(`plugin/DoubanCenterNew2/${path}`, body))
  const r = await fetch(`/api/v1/plugin/DoubanCenterNew2/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return unwrap(await r.json())
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = {
  key: 1,
  class: "mb-4"
};
const _hoisted_2 = { class: "d-flex align-center mb-2" };
const _hoisted_3 = { class: "text-body-2 font-weight-medium" };
const _hoisted_4 = {
  class: "d-flex flex-wrap",
  style: {"gap":"6px"}
};
const _hoisted_5 = ["href", "title"];
const _hoisted_6 = {
  key: 1,
  class: "dc-poster-placeholder"
};
const _hoisted_7 = {
  key: 2,
  class: "d-flex flex-wrap",
  style: {"gap":"12px"}
};
const _hoisted_8 = {
  key: 0,
  class: "text-caption text-medium-emphasis mr-1"
};
const _hoisted_9 = {
  key: 1,
  class: "text-caption text-medium-emphasis mr-1"
};

const {ref,computed,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const config = ref({});
const rankHistory = ref({});
const folioData = ref({});
const loading = ref(false);
const refreshing = ref(false);
const subscribeResult = ref('');
const refreshResult = ref('');

const rankDefs = { coming:{name:'即将上映'}, tv_real_time:{name:'实时热门'}, tv_chinese:{name:'华语口碑'}, tv_global:{name:'全球口碑'}, movie_weekly:{name:'电影口碑'}, bangumi:{name:'BangumiTV'} };

async function load() {
  loading.value = true;
  try {
    config.value = await getPluginApi(props.api, 'config') || {};
    rankHistory.value = await getPluginApi(props.api, 'rank_history') || {};
    folioData.value = await getPluginApi(props.api, 'folio_data') || {};
  } catch(e) { console.error(e); }
  loading.value = false;
}

async function refreshRss() {
  refreshing.value = true;
  refreshResult.value = '';
  try {
    const res = await postPluginApi(props.api, 'refresh_rss', {});
    if (res.success) {
      if (res.data) {
        rankHistory.value = res.data;
      } else {
        rankHistory.value = await getPluginApi(props.api, 'rank_history') || {};
      }
      refreshResult.value = '✓ RSS已刷新';
    } else {
      refreshResult.value = `✗ ${res.message}`;
    }
  } catch(e) { refreshResult.value = `✗ 刷新失败: ${e}`; }
  refreshing.value = false;
  setTimeout(() => { refreshResult.value = ''; }, 3000);
}

async function subscribe(rankKey, item) {
  if (!item) return
  subscribeResult.value = '';
  try {
    const res = await postPluginApi(props.api, 'subscribe', { tmdb_id: item.tmdbid, media_type: 'tv', title: item.title, year: item.year || '' });
    subscribeResult.value = res.success ? `✓ ${item.title} 已订阅` : `✗ ${item.title}: ${res.message}`;
  } catch(e) { subscribeResult.value = `✗ 订阅失败: ${e}`; }
  setTimeout(() => { subscribeResult.value = ''; }, 3000);
}

const timelineGroups = computed(() => {
  const data = folioData.value || {};
  const limitMonth = config.value?.folio_pc_month || 3;
  const limitNum = config.value?.folio_pc_num || 50;
  const entries = Object.entries(data)
    .filter(([_, v]) => v && typeof v === 'object' && v.timestamp)
    .map(([key, val]) => ({ key, ...val }))
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  const groups = [];
  let currentGroup = null;
  for (const entry of entries) {
    const d = new Date(entry.timestamp);
    const monthKey = `${d.getFullYear()}-${d.getMonth()+1}`;
    if (!currentGroup || currentGroup.monthKey !== monthKey) {
      if (groups.length >= limitMonth) break
      currentGroup = { monthKey, year: d.getFullYear(), month: d.getMonth()+1, label: `${d.getFullYear()}年${d.getMonth()+1}月`, items: [] };
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
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VList = _resolveComponent("VList");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "dc-dashboard"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, { class: "dc-header" }, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            size: "40",
            rounded: "lg"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-book-open-page-variant-outline",
                size: "22"
              })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-refresh",
            class: "text-none me-1",
            onClick: refreshRss,
            loading: refreshing.value
          }, {
            default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            class: "text-none me-1",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode("设置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            icon: "mdi-close",
            variant: "text",
            size: "small",
            onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
          })
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "text-h6" }, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("豆瓣中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, { class: "text-caption" })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      (subscribeResult.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: subscribeResult.value.startsWith('✓')?'success':'error',
            variant: "tonal",
            class: "ma-3",
            text: subscribeResult.value,
            density: "compact"
          }, null, 8, ["type", "text"]))
        : _createCommentVNode("", true),
      (refreshResult.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            type: refreshResult.value.startsWith('✓')?'success':'error',
            variant: "tonal",
            class: "ma-3",
            text: refreshResult.value,
            density: "compact"
          }, null, 8, ["type", "text"]))
        : _createCommentVNode("", true),
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
          (timelineGroups.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                _createVNode(_component_VCard, {
                  variant: "tonal",
                  color: "orange-darken-1",
                  class: "timeline-panel"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCardItem, null, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCardTitle, { class: "text-subtitle-2 font-weight-bold" }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-timeline-clock-outline",
                              size: "18",
                              class: "mr-1"
                            }),
                            _cache[5] || (_cache[5] = _createTextVNode("追影时间线", -1))
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
                          default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                            _createTextVNode("豆瓣观影记录按月展示", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VDivider),
                    _createVNode(_component_VCardText, { class: "pa-3" }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timelineGroups.value, (group) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: group.monthKey,
                            class: "mb-3"
                          }, [
                            _createElementVNode("div", _hoisted_2, [
                              _createElementVNode("span", _hoisted_3, _toDisplayString(group.label), 1),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: "orange-darken-1",
                                variant: "tonal",
                                class: "ml-2"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode("看过 " + _toDisplayString(group.items.length) + " 部", 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _createElementVNode("div", _hoisted_4, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                                return (_openBlock(), _createElementBlock("a", {
                                  key: item.key,
                                  href: `https://www.douban.com/doubanapp/dispatch?uri=/movie/${item.subject_id}?from=mdouban&open=app`,
                                  target: "_blank",
                                  class: "dc-poster-link",
                                  title: item.subject_name
                                }, [
                                  _createVNode(_component_VCard, {
                                    class: "dc-poster-card",
                                    variant: "outlined",
                                    rounded: "md"
                                  }, {
                                    default: _withCtx(() => [
                                      (item.poster)
                                        ? (_openBlock(), _createBlock(_component_VImg, {
                                            key: 0,
                                            src: item.poster,
                                            width: "52",
                                            height: "78",
                                            cover: "",
                                            "aspect-ratio": "2/3"
                                          }, null, 8, ["src"]))
                                        : (_openBlock(), _createElementBlock("div", _hoisted_6, [
                                            _createVNode(_component_VIcon, {
                                              icon: "mdi-filmstrip",
                                              size: "20"
                                            })
                                          ]))
                                    ]),
                                    _: 2
                                  }, 1024)
                                ], 8, _hoisted_5))
                              }), 128))
                            ])
                          ]))
                        }), 128))
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]))
            : _createCommentVNode("", true),
          (config.value.dashboard_rank_keys && config.value.dashboard_rank_keys.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(config.value.dashboard_rank_keys, (rk) => {
                  return (_openBlock(), _createBlock(_component_VCard, {
                    key: rk,
                    variant: "tonal",
                    class: "rank-panel",
                    color: rk==='coming'?'primary':'teal'
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardItem, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardTitle, { class: "text-subtitle-2 font-weight-bold" }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(rankDefs[rk]?.name||rk), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
                            default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                              _createTextVNode("点击剧名直接订阅", -1)
                            ]))]),
                            _: 1
                          })
                        ]),
                        _: 2
                      }, 1024),
                      _createVNode(_component_VDivider),
                      _createVNode(_component_VList, { density: "compact" }, {
                        default: _withCtx(() => [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((rankHistory.value[rk]||[]).slice(0,5), (item, i) => {
                            return (_openBlock(), _createBlock(_component_VListItem, {
                              key: i,
                              title: item.title,
                              density: "compact",
                              class: "rank-item",
                              onClick: $event => (subscribe(rk,item))
                            }, {
                              prepend: _withCtx(() => [
                                _createVNode(_component_VAvatar, {
                                  size: "22",
                                  class: "mr-1"
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
                                          size: "16"
                                        }))
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              append: _withCtx(() => [
                                (rk==='coming' && item.wish_count)
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_8, _toDisplayString(item.wish_count) + " 想", 1))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_9, _toDisplayString(item.year||''), 1)),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: "primary",
                                  variant: "flat"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(i+1), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1032, ["title", "onClick"]))
                          }), 128)),
                          (!(rankHistory.value[rk]||[]).length)
                            ? (_openBlock(), _createBlock(_component_VListItem, { key: 0 }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VListItemTitle, { class: "text-center text-medium-emphasis py-2 text-caption" }, {
                                    default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                                      _createTextVNode("暂无数据", -1)
                                    ]))]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              }))
                            : _createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["color"]))
                }), 128))
              ]))
            : _createCommentVNode("", true),
          (!loading.value && !config.value.dashboard_rank_keys?.length && !timelineGroups.value.length)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 3,
                type: "info",
                variant: "tonal",
                density: "compact",
                text: "请在配置页「仪表显示」中选择要显示的榜单，并确保对应榜单已启用。"
              }))
            : _createCommentVNode("", true)
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cab722bf"]]);

export { Dashboard as default };
