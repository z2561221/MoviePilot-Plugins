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

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = {
  key: 3,
  class: "mb-3"
};
const _hoisted_2 = {
  class: "d-flex flex-wrap",
  style: {"gap":"8px"}
};
const _hoisted_3 = {
  class: "text-caption text-medium-emphasis mb-1",
  style: {"font-size":"11px"}
};
const _hoisted_4 = {
  class: "d-flex flex-wrap",
  style: {"gap":"4px"}
};
const _hoisted_5 = ["href", "title"];
const _hoisted_6 = {
  key: 1,
  class: "dc-ph"
};
const _hoisted_7 = { key: 4 };
const _hoisted_8 = { class: "dc-rank-grid" };
const _hoisted_9 = { class: "dc-rank-head" };
const _hoisted_10 = { class: "dc-rank-body" };
const _hoisted_11 = ["title", "onClick"];
const _hoisted_12 = { class: "dc-rank-name" };
const _hoisted_13 = { class: "dc-rank-num" };
const _hoisted_14 = {
  key: 0,
  class: "text-center text-medium-emphasis py-2 text-caption"
};
const _hoisted_15 = {
  key: 5,
  class: "text-center text-medium-emphasis py-4 text-caption"
};

const {ref,computed,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;

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
      if (res.data) rankHistory.value = res.data;
      else rankHistory.value = await getPluginApi(props.api, 'rank_history') || {};
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
    const params = `tmdb_id=${item.tmdbid}&media_type=tv&title=${encodeURIComponent(item.title)}&year=${item.year||''}`;
    const res = await getPluginApi(props.api, `subscribe?${params}`);
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
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

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
            onClick: refreshRss,
            loading: refreshing.value
          }, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, null, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("豆瓣中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("点击榜单条目可直接订阅", -1)
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
                type: subscribeResult.value.startsWith('✓')?'success':'error',
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
                type: refreshResult.value.startsWith('✓')?'success':'error',
                variant: "tonal",
                class: "mb-2",
                text: refreshResult.value,
                density: "compact",
                closable: ""
              }, null, 8, ["type", "text"]))
            : _createCommentVNode("", true),
          (timelineGroups.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                _createVNode(_component_VCard, {
                  variant: "tonal",
                  color: "primary",
                  class: "mb-2",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCardItem, { class: "pa-2" }, {
                      prepend: _withCtx(() => [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-timeline-clock-outline",
                          size: "16",
                          color: "primary"
                        })
                      ]),
                      append: _withCtx(() => [
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          color: "primary",
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(timelineGroups.value.reduce((s,g)=>s+g.items.length,0)) + " 部", 1)
                          ]),
                          _: 1
                        })
                      ]),
                      default: _withCtx(() => [
                        _createVNode(_component_VCardTitle, { class: "text-body-2 font-weight-bold pa-0" }, {
                          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
                            _createTextVNode("追影时间线", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VDivider),
                    _createVNode(_component_VCardText, { class: "pa-2" }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_2, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timelineGroups.value, (group) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: group.monthKey,
                              class: "flex-shrink-0"
                            }, [
                              _createElementVNode("div", _hoisted_3, _toDisplayString(group.label), 1),
                              _createElementVNode("div", _hoisted_4, [
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
                                          width: "52",
                                          height: "78",
                                          cover: "",
                                          class: "rounded"
                                        }, null, 8, ["src"]))
                                      : (_openBlock(), _createElementBlock("div", _hoisted_6, [
                                          _createVNode(_component_VIcon, {
                                            icon: "mdi-filmstrip",
                                            size: "14"
                                          })
                                        ]))
                                  ], 8, _hoisted_5))
                                }), 128))
                              ])
                            ]))
                          }), 128))
                        ])
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
                _createElementVNode("div", _hoisted_8, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(config.value.dashboard_rank_keys, (rk) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: rk,
                      class: "dc-rank-cell"
                    }, [
                      _createElementVNode("div", _hoisted_9, _toDisplayString(rankDefs[rk]?.name||rk), 1),
                      _createElementVNode("div", _hoisted_10, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((rankHistory.value[rk]||[]).slice(0,5), (item, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-rank-row",
                            title: item.title,
                            onClick: $event => (subscribe(rk,item))
                          }, [
                            _createVNode(_component_VAvatar, {
                              size: "16",
                              class: "mr-1 flex-shrink-0"
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
                            _createElementVNode("span", _hoisted_12, _toDisplayString(item.title), 1),
                            _createElementVNode("span", _hoisted_13, [
                              (rk==='coming' && item.wish_count)
                                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                    _createTextVNode(_toDisplayString(item.wish_count), 1)
                                  ], 64))
                                : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                    _createTextVNode(_toDisplayString(item.year||''), 1)
                                  ], 64))
                            ])
                          ], 8, _hoisted_11))
                        }), 128)),
                        (!(rankHistory.value[rk]||[]).length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_14, "暂无数据"))
                          : _createCommentVNode("", true)
                      ])
                    ]))
                  }), 128))
                ])
              ]))
            : _createCommentVNode("", true),
          (!loading.value && !config.value.dashboard_rank_keys?.length && !timelineGroups.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_15, " 请在配置页「仪表显示」中选择要显示的榜单 "))
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
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-44bfafbe"]]);

export { Dashboard as default };
