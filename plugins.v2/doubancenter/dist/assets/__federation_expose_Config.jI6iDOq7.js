import { importShared } from './__federation_fn_import.JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper.pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "dc-config" };
const _hoisted_2 = { class: "dc-body" };
const _hoisted_3 = { class: "dc-nav" };
const _hoisted_4 = { class: "dc-content" };
const _hoisted_5 = { class: "dc-subtabs" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "dc-window" };
const _hoisted_8 = { class: "dc-pane" };
const _hoisted_9 = { class: "dc-pane" };
const _hoisted_10 = { class: "dc-section-title" };
const _hoisted_11 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_12 = { class: "dc-pane" };
const _hoisted_13 = { class: "dc-pane" };
const _hoisted_14 = { class: "dc-pane" };

const {reactive,ref,computed,watch} = await importShared('vue');



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
const activeMain = ref('rank');
const activeSub = ref('basic');

const defaults = {
  enabled: false, cron: '0 8 * * *', notify: false, proxy: false, onlyonce: false,
  rsshub_domain: 'https://rsshub.ddsrem.com',
  rank_configs: {
    coming: { enabled: false, count: 10, wish_count: 5000, air_days: 7, vote: 0, year: 0 },
    tv_real_time: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    tv_chinese: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    tv_global: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    movie_weekly: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    bangumi: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
  },
  region_filters: [], genre_filters: [], resolution_filters: [], custom_rss_addrs: '',
  folio_enabled: true, folio_private: true, folio_first: true, folio_notify: false,
  folio_user: '', folio_exclude: '', folio_cookie: '',
  folio_pc_month: 3, folio_pc_num: 50, folio_mobile_month: 2, folio_mobile_num: 15,
  dashboard_rank_keys: [],
};

const regionOptions = ["中国大陆","中国香港","中国台湾","美国","日本","韩国","英国","泰国","印度","法国","德国","西班牙","加拿大","澳大利亚","俄罗斯","瑞典","丹麦","爱尔兰","意大利","巴西"];
const genreOptions = ["爱情","喜剧","剧情","悬疑","古装","动作","犯罪","科幻","家庭","奇幻","武侠","历史","动画","惊悚","战争","冒险","恐怖","灾难","传记","音乐","歌舞"];
const resolutionOptions = [{title:"2160p/4K",value:"2160p|4k|uhd"},{title:"1080p",value:"1080p"},{title:"720p",value:"720p"}];

const rankDefs = [
  {key:'coming',name:'即将上映',route:'/douban/tv/coming',filters:['wish_count','air_days']},
  {key:'tv_real_time',name:'实时热门',route:'/douban/list/tv_real_time_hotest',filters:['vote','year']},
  {key:'tv_chinese',name:'华语口碑',route:'/douban/list/tv_chinese_best_weekly',filters:['vote','year']},
  {key:'tv_global',name:'全球口碑',route:'/douban/list/tv_global_best_weekly',filters:['vote','year']},
  {key:'movie_weekly',name:'电影口碑',route:'/douban/list/movie_weekly_best',filters:['vote','year']},
  {key:'bangumi',name:'BangumiTV',route:'/bangumi.tv/anime/followrank',filters:['vote','year']},
];

const mainTabs = [
  {key:'rank',title:'榜单订阅',icon:'mdi-trophy-outline',desc:'6个内置榜单+自定义RSS，统一订阅到豆瓣中心。'},
  {key:'folio',title:'豆瓣档案',icon:'mdi-book-open-page-variant-outline',desc:'追剧观影自动同步进度到豆瓣。'},
  {key:'dashboard',title:'仪表显示',icon:'mdi-view-dashboard-outline',desc:'时间线+榜单排行双面板。'},
];

const subTabs = {
  rank: [{key:'basic',title:'基础设置',icon:'mdi-tune-variant'},{key:'list',title:'榜单列表',icon:'mdi-format-list-bulleted'},{key:'filter',title:'条件筛选',icon:'mdi-filter-variant'}],
  folio: [{key:'sync',title:'同步设置',icon:'mdi-sync'}],
  dashboard: [{key:'view',title:'仪表盘选择',icon:'mdi-view-dashboard-outline'}],
};

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);

watch(() => props.initialConfig, val => {
  Object.keys(form).forEach(k => delete form[k]);
  const m = {};
  Object.assign(m, defaults, JSON.parse(JSON.stringify(val || {})));
  for (const rd of rankDefs) {
    if (!m.rank_configs[rd.key]) m.rank_configs[rd.key] = {...defaults.rank_configs[rd.key]};
  }
  Object.assign(form, m);
}, { immediate: true, deep: true });

function saveConfig() { emit('save', {...form}); }

function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || '';
}

const enabledRankCount = computed(() => rankDefs.filter(r => form.rank_configs?.[r.key]?.enabled).length);

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
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

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
              rounded: "lg"
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
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                _createTextVNode("豆瓣中心New2", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
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
              class: "py-2"
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
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
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
                  class: _normalizeClass(["dc-subtab", {'dc-subtab--active':activeSub.value===sub.key}]),
                  onClick: $event => (activeSub.value=sub.key)
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
            _createElementVNode("div", _hoisted_7, [
              _withDirectives(_createElementVNode("div", _hoisted_8, [
                _cache[23] || (_cache[23] = _createElementVNode("div", { class: "dc-section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.notify) = $event)),
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
                          modelValue: form.onlyonce,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.onlyonce) = $event)),
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
                        _createVNode(_component_VTextField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.cron) = $event)),
                          label: "运行周期",
                          placeholder: "0 8 * * *",
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
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.rsshub_domain) = $event)),
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
                  text: "订阅用户名统一为「豆瓣中心」。即将上映保留播出窗口、想看人数过滤逻辑。"
                })
              ], 512), [
                [_vShow, activeSub.value==='basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_9, [
                _createElementVNode("div", _hoisted_10, [
                  _cache[24] || (_cache[24] = _createTextVNode("榜单列表 ", -1)),
                  _createElementVNode("span", _hoisted_11, "（已启用 " + _toDisplayString(enabledRankCount.value) + "/" + _toDisplayString(rankDefs.length) + "）", 1)
                ]),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2",
                  text: "每个榜单独立控制，条件框之间是且的关系。即将上映保留特殊处理。"
                }),
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(rankDefs, (rd) => {
                  return _createElementVNode("div", {
                    key: rd.key,
                    class: "dc-rank-row pa-1 mb-1"
                  }, [
                    _createVNode(_component_VRow, {
                      align: "center",
                      dense: ""
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCol, {
                          cols: "12",
                          md: "2"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VSwitch, {
                              modelValue: form.rank_configs[rd.key].enabled,
                              "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].enabled) = $event),
                              label: rd.name,
                              color: "primary",
                              "hide-details": "",
                              inset: "",
                              density: "compact",
                              class: "dc-rank-switch"
                            }, null, 8, ["modelValue", "onUpdate:modelValue", "label"])
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode(_component_VCol, {
                          cols: "12",
                          md: "2"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VTextField, {
                              modelValue: form.rank_configs[rd.key].count,
                              "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].count) = $event),
                              modelModifiers: { number: true },
                              label: "数量",
                              type: "number",
                              min: "1",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": ""
                            }, null, 8, ["modelValue", "onUpdate:modelValue"])
                          ]),
                          _: 2
                        }, 1024),
                        (rd.filters.includes('wish_count'))
                          ? (_openBlock(), _createBlock(_component_VCol, {
                              key: 0,
                              cols: "12",
                              md: "3"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTextField, {
                                  modelValue: form.rank_configs[rd.key].wish_count,
                                  "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].wish_count) = $event),
                                  modelModifiers: { number: true },
                                  label: "想看人数",
                                  type: "number",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"])
                              ]),
                              _: 2
                            }, 1024))
                          : _createCommentVNode("", true),
                        (rd.filters.includes('air_days'))
                          ? (_openBlock(), _createBlock(_component_VCol, {
                              key: 1,
                              cols: "12",
                              md: "3"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTextField, {
                                  modelValue: form.rank_configs[rd.key].air_days,
                                  "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].air_days) = $event),
                                  modelModifiers: { number: true },
                                  label: "播出窗口",
                                  type: "number",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"])
                              ]),
                              _: 2
                            }, 1024))
                          : _createCommentVNode("", true),
                        (rd.filters.includes('vote'))
                          ? (_openBlock(), _createBlock(_component_VCol, {
                              key: 2,
                              cols: "12",
                              md: "2"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTextField, {
                                  modelValue: form.rank_configs[rd.key].vote,
                                  "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].vote) = $event),
                                  modelModifiers: { number: true },
                                  label: "评分",
                                  type: "number",
                                  min: "0",
                                  max: "10",
                                  step: "0.1",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"])
                              ]),
                              _: 2
                            }, 1024))
                          : _createCommentVNode("", true),
                        (rd.filters.includes('year'))
                          ? (_openBlock(), _createBlock(_component_VCol, {
                              key: 3,
                              cols: "12",
                              md: "2"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VTextField, {
                                  modelValue: form.rank_configs[rd.key].year,
                                  "onUpdate:modelValue": $event => ((form.rank_configs[rd.key].year) = $event),
                                  modelModifiers: { number: true },
                                  label: "年份",
                                  type: "number",
                                  min: "0",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"])
                              ]),
                              _: 2
                            }, 1024))
                          : _createCommentVNode("", true)
                      ]),
                      _: 2
                    }, 1024)
                  ])
                }), 64)),
                _cache[25] || (_cache[25] = _createElementVNode("div", { class: "dc-section-title mt-4" }, "自定义榜单", -1)),
                _createVNode(_component_VTextarea, {
                  modelValue: form.custom_rss_addrs,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.custom_rss_addrs) = $event)),
                  label: "自定义RSS地址（一行一个）",
                  rows: "3",
                  "auto-grow": "",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ], 512), [
                [_vShow, activeSub.value==='list']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_12, [
                _cache[28] || (_cache[28] = _createElementVNode("div", { class: "dc-section-title" }, "条件筛选", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.region_filters,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.region_filters) = $event)),
                          items: regionOptions,
                          label: "地区筛选",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _cache[26] || (_cache[26] = _createElementVNode("div", { class: "dc-hint" }, "即将上映专用", -1))
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.genre_filters,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.genre_filters) = $event)),
                          items: genreOptions,
                          label: "类型筛选",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _cache[27] || (_cache[27] = _createElementVNode("div", { class: "dc-hint" }, "即将上映专用", -1))
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
                        _createVNode(_component_VSelect, {
                          modelValue: form.resolution_filters,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.resolution_filters) = $event)),
                          items: resolutionOptions,
                          "item-title": "title",
                          "item-value": "value",
                          label: "订阅分辨率",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "不选则沿用系统默认",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value==='filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_13, [
                _cache[29] || (_cache[29] = _createElementVNode("div", { class: "dc-section-title" }, "同步设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.folio_enabled,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.folio_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用豆瓣档案"
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
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.folio_private) = $event)),
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
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.folio_first) = $event)),
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
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.folio_notify) = $event)),
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
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_user,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.folio_user) = $event)),
                          label: "媒体库用户名（多个以,分隔）",
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
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.folio_exclude) = $event)),
                          label: "路径排除关键词（多个以,分隔）",
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
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.folio_cookie) = $event)),
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
                [_vShow, activeSub.value==='sync']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_14, [
                _cache[30] || (_cache[30] = _createElementVNode("div", { class: "dc-section-title" }, "仪表盘选择", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2",
                  text: "先在「榜单列表」中启用榜单，此处即可选择在仪表盘并排显示。最多选2个。"
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
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.dashboard_rank_keys) = $event)),
                          label: "选择要显示的榜单",
                          items: rankDefs.filter(r=>form.rank_configs?.[r.key]?.enabled).map(r=>({title:r.name,value:r.key})),
                          multiple: "",
                          chips: "",
                          clearable: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[31] || (_cache[31] = _createElementVNode("div", { class: "dc-section-title mt-4" }, "档案时间线显示设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_pc_month,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.folio_pc_month) = $event)),
                          label: "大屏显示月份数",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 3",
                          "persistent-hint": ""
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
                          modelValue: form.folio_pc_num,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.folio_pc_num) = $event)),
                          label: "大屏每月最多显示数",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 50",
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
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_mobile_month,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.folio_mobile_month) = $event)),
                          label: "小屏显示月份数",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 2",
                          "persistent-hint": ""
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
                          modelValue: form.folio_mobile_num,
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.folio_mobile_num) = $event)),
                          label: "小屏每月最多显示数",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 15",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value==='view']
              ])
            ])
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "dc-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[21] || (_cache[21] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d39fd440"]]);

export { Config as default };
