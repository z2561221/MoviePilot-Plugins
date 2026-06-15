import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "dc-config" };
const _hoisted_2 = { class: "d-flex align-center" };
const _hoisted_3 = { class: "dc-body" };
const _hoisted_4 = { class: "dc-nav" };
const _hoisted_5 = { class: "dc-content" };
const _hoisted_6 = { class: "dc-subtabs" };
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "dc-window" };
const _hoisted_9 = { class: "dc-pane" };
const _hoisted_10 = { class: "dc-pane" };
const _hoisted_11 = { class: "dc-pane" };
const _hoisted_12 = { class: "dc-pane" };
const _hoisted_13 = { class: "dc-pane" };
const _hoisted_14 = { class: "dc-pane" };
const _hoisted_15 = { class: "dc-pane" };

const {reactive,ref,computed,watch,onMounted} = await importShared('vue');


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
const activeMain = ref('coming');
const activeSub = ref('basic');

const defaults = {
  enabled: false,
  cron: '0 8 * * *',
  notify: false,
  proxy: false,
  onlyonce_coming: false,
  onlyonce_rank: false,
  coming_enabled: true,
  coming_min_wish: 5000,
  coming_air_days: 7,
  coming_region_filters: [],
  coming_genre_filters: [],
  coming_resolution_filters: [],
  coming_subscribe_sites: [],
  coming_rss_domain: 'https://rsshub.ddsrem.com',
  rank_enabled: true,
  rank_vote: 0,
  rank_release_year: 0,
  rank_ranks: [],
  rank_rss_addrs: '',
  rank_is_seasons_all: true,
  rank_is_only_movies: false,
  folio_enabled: true,
  folio_private: true,
  folio_first: true,
  folio_notify: false,
  folio_user: '',
  folio_exclude: '',
  folio_cookie: '',
  folio_pc_month: 3,
  folio_pc_num: 50,
  folio_mobile_month: 2,
  folio_mobile_num: 15,
};

const regionOptions = [
  "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "泰国", "印度", "法国",
  "德国", "西班牙", "加拿大", "澳大利亚", "俄罗斯", "瑞典", "丹麦", "爱尔兰", "意大利", "巴西"
];
const genreOptions = [
  "爱情", "喜剧", "剧情", "悬疑", "古装", "动作", "犯罪", "科幻", "家庭", "奇幻", "武侠",
  "历史", "动画", "惊悚", "战争", "冒险", "恐怖", "灾难", "传记", "音乐", "歌舞"
];
const resolutionOptions = [
  { title: "2160p / 4K", value: "2160p|4k|uhd" },
  { title: "1080p", value: "1080p" },
  { title: "720p", value: "720p" },
];

const mainTabs = [
  { key: 'coming', title: '即将播出', icon: 'mdi-television-play', desc: '豆瓣即将播出剧集，按想看人数自动订阅。' },
  { key: 'rank', title: '榜单订阅', icon: 'mdi-trophy-outline', desc: '豆瓣热门榜单 + 自定义豆列，自动订阅。' },
  { key: 'folio', title: '豆瓣档案', icon: 'mdi-book-open-page-variant-outline', desc: '追剧观影自动同步进度到豆瓣。' },
  { key: 'general', title: '通用设置', icon: 'mdi-cog-outline', desc: '运行周期、通知、代理等全局设置。' },
];

const subTabs = {
  coming: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-variant' },
  ],
  rank: [
    { key: 'rss', title: 'RSS 订阅', icon: 'mdi-rss' },
  ],
  folio: [
    { key: 'sync', title: '同步设置', icon: 'mdi-sync' },
    { key: 'display', title: '显示设置', icon: 'mdi-monitor-screenshot' },
  ],
  general: [
    { key: 'schedule', title: '运行周期', icon: 'mdi-clock-outline' },
    { key: 'advanced', title: '高级', icon: 'mdi-tune' },
  ],
};

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);

watch(() => props.initialConfig, value => {
  Object.keys(form).forEach(key => delete form[key]);
  Object.assign(form, defaults, value || {});
}, { immediate: true, deep: true });

function saveConfig() {
  emit('save', { ...form });
}

function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || '';
}

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
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VCronField = _resolveComponent("VCronField");
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
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_VSwitch, {
                modelValue: form.enabled,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
                color: "success",
                "hide-details": "",
                inset: "",
                label: form.enabled ? '已启用' : '已停用'
              }, null, 8, ["modelValue", "label"])
            ])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode("豆瓣中心", -1)
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
        _createElementVNode("div", _hoisted_3, [
          _createElementVNode("nav", _hoisted_4, [
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
          _createElementVNode("section", _hoisted_5, [
            _createElementVNode("div", _hoisted_6, [
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
                ], 10, _hoisted_7))
              }), 128))
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", _hoisted_8, [
              _withDirectives(_createElementVNode("div", _hoisted_9, [
                _cache[33] || (_cache[33] = _createElementVNode("div", { class: "dc-section-title" }, "即将播出 · 基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.coming_enabled,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.coming_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用即将播出订阅"
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
                          modelValue: form.coming_min_wish,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.coming_min_wish) = $event)),
                          label: "最小想看人数",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "想看人数 ≥ 此值才订阅",
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
                          modelValue: form.onlyonce_coming,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.onlyonce_coming) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
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
                          modelValue: form.coming_air_days,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.coming_air_days) = $event)),
                          label: "播出窗口（天）",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "首播日期距今天数 ≤ 此值",
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
                          modelValue: form.coming_rss_domain,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.coming_rss_domain) = $event)),
                          label: "RSSHub 域名",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "默认 https://rsshub.ddsrem.com",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_10, [
                _cache[36] || (_cache[36] = _createElementVNode("div", { class: "dc-section-title" }, "筛选条件", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.coming_region_filters,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.coming_region_filters) = $event)),
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
                        _cache[34] || (_cache[34] = _createElementVNode("div", { class: "dc-hint" }, "命中任一即通过，不选则不筛选", -1))
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.coming_genre_filters,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.coming_genre_filters) = $event)),
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
                        _cache[35] || (_cache[35] = _createElementVNode("div", { class: "dc-hint" }, "命中任一即通过，不选则不筛选", -1))
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
                          modelValue: form.coming_resolution_filters,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.coming_resolution_filters) = $event)),
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
                          hint: "不选时沿用系统默认",
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
                          modelValue: form.coming_subscribe_sites,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.coming_subscribe_sites) = $event)),
                          label: "订阅站点ID（逗号分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "不填则沿用系统默认",
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
                  text: "先按想看人数过滤；地区/类型命中任一即通过；随后通过 TMDB 获取首播日期，仅订阅窗口期内剧集。"
                })
              ], 512), [
                [_vShow, activeSub.value === 'filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_11, [
                _cache[37] || (_cache[37] = _createElementVNode("div", { class: "dc-section-title" }, "RSS 订阅", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.rank_enabled,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.rank_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用榜单订阅"
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
                          modelValue: form.onlyonce_rank,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.onlyonce_rank) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
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
                          modelValue: form.rank_rss_addrs,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.rank_rss_addrs) = $event)),
                          label: "自定义 RSS 地址（每行一个）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "4",
                          hint: "支持豆瓣 RSSHub 路由，如 /douban/movie/weekly/movie_real_time_hotest",
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
                          modelValue: form.rank_vote,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.rank_vote) = $event)),
                          label: "最低评分",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "0 表示不限制",
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
                          modelValue: form.rank_release_year,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.rank_release_year) = $event)),
                          label: "最早年份",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "0 表示不限制",
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
                        _createVNode(_component_VSwitch, {
                          modelValue: form.rank_is_seasons_all,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.rank_is_seasons_all) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "订阅剧集全季度"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.rank_is_only_movies,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.rank_is_only_movies) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "只订阅电影"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'rss']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_12, [
                _cache[38] || (_cache[38] = _createElementVNode("div", { class: "dc-section-title" }, "同步设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.folio_enabled,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.folio_enabled) = $event)),
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
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.folio_private) = $event)),
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
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.folio_first) = $event)),
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
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.folio_notify) = $event)),
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
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.folio_user) = $event)),
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
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.folio_exclude) = $event)),
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
                }),
                _createVNode(_component_VAlert, {
                  class: "mt-3",
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  text: "需要开启媒体服务器的 Webhook，并确保豆瓣已登录。Cookie 不异地登录有效期很久。"
                })
              ], 512), [
                [_vShow, activeSub.value === 'sync']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_13, [
                _cache[39] || (_cache[39] = _createElementVNode("div", { class: "dc-section-title" }, "仪表盘显示设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.folio_pc_month,
                          "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.folio_pc_month) = $event)),
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
                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.folio_pc_num) = $event)),
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
                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.folio_mobile_month) = $event)),
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
                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((form.folio_mobile_num) = $event)),
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
                [_vShow, activeSub.value === 'display']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_14, [
                _cache[40] || (_cache[40] = _createElementVNode("div", { class: "dc-section-title" }, "运行周期", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((form.cron) = $event)),
                          label: "执行周期",
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
                [_vShow, activeSub.value === 'schedule']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_15, [
                _cache[41] || (_cache[41] = _createElementVNode("div", { class: "dc-section-title" }, "高级设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((form.notify) = $event)),
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
                          modelValue: form.proxy,
                          "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((form.proxy) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "使用代理"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'advanced']
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
              onClick: _cache[31] || (_cache[31] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
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
              default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c7853dd2"]]);

export { Config as default };
