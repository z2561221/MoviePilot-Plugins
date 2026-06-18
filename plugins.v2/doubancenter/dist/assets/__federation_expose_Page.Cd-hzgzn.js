import { importShared } from './__federation_fn_import.JrT3xvdd.js';
import { g as getPluginApi } from './api.DOkqWlC3.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper.pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = {
  key: 0,
  class: "mb-4"
};
const _hoisted_2 = { class: "dc-stats-grid" };
const _hoisted_3 = { class: "dc-stat-card" };
const _hoisted_4 = { class: "dc-stat-value" };
const _hoisted_5 = { class: "dc-stat-card" };
const _hoisted_6 = { class: "dc-stat-value" };
const _hoisted_7 = { class: "dc-stat-label" };
const _hoisted_8 = { class: "mb-4" };
const _hoisted_9 = { class: "dc-section-title mb-2" };
const _hoisted_10 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_11 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_12 = { class: "dc-history-info" };
const _hoisted_13 = { class: "dc-history-title" };
const _hoisted_14 = { class: "dc-history-meta" };
const _hoisted_15 = { class: "text-caption text-medium-emphasis" };
const _hoisted_16 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_17 = {
  key: 2,
  class: "d-flex justify-center mt-2"
};
const _hoisted_18 = { class: "d-flex align-center mx-2 text-caption text-medium-emphasis" };
const _hoisted_19 = { key: 1 };
const _hoisted_20 = { class: "dc-section-title mb-2" };
const _hoisted_21 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_22 = { class: "dc-cheat-list" };
const _hoisted_23 = { class: "dc-cheat-title" };
const _hoisted_24 = { class: "text-caption text-medium-emphasis" };

const {ref,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const loading = ref(false);
const stats = ref(null);
const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
const cheatLogs = ref([]);

async function loadAll() {
  loading.value = true;
  try {
    const [s, h, c] = await Promise.all([
      getPluginApi(props.api, 'stats'),
      getPluginApi(props.api, `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`),
      getPluginApi(props.api, 'anti_cheat_logs'),
    ]);
    if (s) stats.value = s;
    if (h) historyData.value = h;
    if (c) cheatLogs.value = c;
  } catch(e) { console.error(e); }
  loading.value = false;
}

async function goPage(p) {
  if (p < 1 || p > historyData.value.total_pages) return
  historyData.value.page = p;
  await loadAll();
}

const rankColors = {
  coming: 'primary',
  tv_real_time: 'teal',
  tv_chinese: 'orange-darken-1',
  tv_global: 'deep-purple',
  movie_weekly: 'pink',
  bangumi: 'brown',
};

onMounted(loadAll);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "dc-page"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, { class: "dc-page-header" }, {
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
            size: "small",
            "prepend-icon": "mdi-refresh",
            class: "text-none me-1",
            onClick: loadAll,
            loading: loading.value
          }, {
            default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
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
            default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
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
          _createVNode(_component_VCardTitle, null, {
            default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode("豆瓣中心 · 订阅记录", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
              _createTextVNode("榜单订阅历史与统计", -1)
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
          (!loading.value)
            ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                (stats.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                      _cache[10] || (_cache[10] = _createElementVNode("div", { class: "dc-section-title mb-2" }, "订阅统计", -1)),
                      _createElementVNode("div", _hoisted_2, [
                        _createElementVNode("div", _hoisted_3, [
                          _createElementVNode("div", _hoisted_4, _toDisplayString(stats.value.total || 0), 1),
                          _cache[8] || (_cache[8] = _createElementVNode("div", { class: "dc-stat-label" }, "总订阅数", -1))
                        ]),
                        _createElementVNode("div", _hoisted_5, [
                          _createElementVNode("div", _hoisted_6, _toDisplayString(stats.value.month_new || 0), 1),
                          _cache[9] || (_cache[9] = _createElementVNode("div", { class: "dc-stat-label" }, "本月新增", -1))
                        ]),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(stats.value.rank_dist, (count, key) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: key,
                            class: "dc-stat-card"
                          }, [
                            _createElementVNode("div", {
                              class: "dc-stat-value",
                              style: _normalizeStyle({color:`rgb(var(--v-theme-${rankColors[key]||'primary'}))`})
                            }, _toDisplayString(count), 5),
                            _createElementVNode("div", _hoisted_7, _toDisplayString(({coming:'即将上映',tv_real_time:'实时热门',tv_chinese:'华语口碑',tv_global:'全球口碑',movie_weekly:'电影口碑',bangumi:'BangumiTV'})[key] || key), 1)
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_8, [
                  _createElementVNode("div", _hoisted_9, [
                    _cache[11] || (_cache[11] = _createTextVNode("订阅历史 ", -1)),
                    _createElementVNode("span", _hoisted_10, "（共 " + _toDisplayString(historyData.value.total) + " 条）", 1)
                  ]),
                  (historyData.value.items && historyData.value.items.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyData.value.items, (item, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-history-row"
                          }, [
                            _createVNode(_component_VAvatar, {
                              size: "28",
                              class: "mr-2 flex-shrink-0"
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
                                      size: "14"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("div", _hoisted_12, [
                              _createElementVNode("div", _hoisted_13, _toDisplayString(item.title), 1),
                              _createElementVNode("div", _hoisted_14, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  color: rankColors[item.rank_key]||'primary',
                                  variant: "tonal",
                                  class: "mr-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.rank_name), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createElementVNode("span", _hoisted_15, _toDisplayString(item.time ? item.time.split(' ')[0] : ''), 1)
                              ])
                            ])
                          ]))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_16, "暂无订阅记录")),
                  (historyData.value.total_pages > 1)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                        _createVNode(_component_VBtn, {
                          variant: "text",
                          size: "x-small",
                          disabled: historyData.value.page <= 1,
                          onClick: _cache[2] || (_cache[2] = $event => (goPage(historyData.value.page - 1))),
                          class: "mx-1"
                        }, {
                          default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                            _createTextVNode("上一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"]),
                        _createElementVNode("span", _hoisted_18, _toDisplayString(historyData.value.page) + " / " + _toDisplayString(historyData.value.total_pages), 1),
                        _createVNode(_component_VBtn, {
                          variant: "text",
                          size: "x-small",
                          disabled: historyData.value.page >= historyData.value.total_pages,
                          onClick: _cache[3] || (_cache[3] = $event => (goPage(historyData.value.page + 1))),
                          class: "mx-1"
                        }, {
                          default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                            _createTextVNode("下一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"])
                      ]))
                    : _createCommentVNode("", true)
                ]),
                (cheatLogs.value && cheatLogs.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_19, [
                      _createElementVNode("div", _hoisted_20, [
                        _cache[14] || (_cache[14] = _createTextVNode("防刷榜日志 ", -1)),
                        _createElementVNode("span", _hoisted_21, "（最近 " + _toDisplayString(cheatLogs.value.length) + " 条）", 1)
                      ]),
                      _createElementVNode("div", _hoisted_22, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cheatLogs.value.slice().reverse(), (log, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-cheat-row"
                          }, [
                            _createVNode(_component_VIcon, {
                              size: "14",
                              color: "warning",
                              class: "mr-1"
                            }, {
                              default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                                _createTextVNode("mdi-shield-off-outline", -1)
                              ]))]),
                              _: 1
                            }),
                            _createElementVNode("span", _hoisted_23, _toDisplayString(log.title), 1),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: "warning",
                              variant: "tonal",
                              class: "mx-1"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(log.reason), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", _hoisted_24, _toDisplayString(log.time ? log.time.split(' ')[0] : ''), 1)
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true)
              ], 64))
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-532e785a"]]);

export { Page as default };
