import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi } from './_plugin-vue_export-helper-BKA7AlB8.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,createBlock:_createBlock,createCommentVNode:_createCommentVNode,vShow:_vShow,withDirectives:_withDirectives,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "ar-config" };
const _hoisted_2 = { class: "ar-config__body" };
const _hoisted_3 = {
  class: "ar-config__nav",
  "aria-label": "Agent榜单配置导航"
};
const _hoisted_4 = { class: "ar-config__content" };
const _hoisted_5 = { class: "ar-config__subtabs" };
const _hoisted_6 = {
  class: "ar-config__subtab ar-config__subtab--active",
  type: "button"
};
const _hoisted_7 = { class: "ar-config__pane ar-config__pane--overview" };
const _hoisted_8 = { class: "ar-config__pipeline" };
const _hoisted_9 = { class: "ar-config__overview-grid" };
const _hoisted_10 = { class: "d-flex align-center justify-space-between mb-2" };
const _hoisted_11 = { class: "ar-config__hint" };
const _hoisted_12 = { class: "ar-config__pane" };
const _hoisted_13 = { class: "ar-config__pane" };
const _hoisted_14 = { class: "ar-config__source-grid" };
const _hoisted_15 = { class: "ar-config__pane" };
const _hoisted_16 = { class: "ar-config__weight-grid" };
const _hoisted_17 = { class: "d-flex align-center mb-1" };
const _hoisted_18 = { class: "text-body-2 font-weight-medium" };
const _hoisted_19 = { class: "ar-config__default" };
const _hoisted_20 = { class: "ar-config__pane" };
const _hoisted_21 = { class: "text-caption mb-1" };
const _hoisted_22 = { class: "ar-config__pane" };
const _hoisted_23 = { class: "ar-config__pane" };

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');


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

const weightDefaults = {
  type_weight: 0.8,
  theme_weight: 0.8,
  actor_weight: 0.5,
  director_weight: 0.4,
  region_weight: 0.4,
  year_weight: 0.3,
  rating_weight: 0.7,
  heat_weight: 0.6,
  freshness_weight: 0.5,
  similarity_weight: 0.8,
};

const defaults = {
  enabled: false,
  schedule_enabled: false,
  cron: '0 8 * * *',
  users: [],
  default_user: '',
  discovery_sources: {
    douban: true,
    tmdb_movies: true,
    tmdb_tv: true,
    bangumi: true,
    extensions: true,
  },
  weights: { ...weightDefaults },
  media_types: ['movie', 'tv', 'anime'],
  profile_scope: 'all',
  recent_days: 365,
  subscription_sample_limit: 200,
  minimum_samples: 5,
  candidate_pool_size: 100,
  confidence_threshold: 0.6,
  exclude_keywords: [],
  action_mode: 'notify',
  notify: true,
  auto_subscribe_top_n: 0,
  auto_subscribe_limit: 10,
  history_limit: 50,
  profile_cache_enabled: true,
  rebuild_profile_each_run: false,
};

const form = reactive(structuredClone(defaults));
const activeMain = ref('overview');
const loading = ref(false);
const status = ref({ state: 'stopped', validation_errors: [] });
const availableUsers = ref([]);
const loadError = ref('');

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '配置参与用户、默认用户和运行周期。' },
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline', desc: '选择 MoviePilot 内置与扩展发现来源。' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical', desc: '设置 Agent 排序时十项偏好权重。' },
  { key: 'filter', title: '条件筛选', icon: 'mdi-filter-outline', desc: '限制媒体类型、候选数量和置信度。' },
  { key: 'board', title: '榜单行为', icon: 'mdi-format-list-numbered', desc: '选择仅更新、通知确认或自动订阅。' },
  { key: 'advanced', title: '高级选项', icon: 'mdi-shield-cog-outline', desc: '管理画像重建、历史上限和安全边界。' },
];

const weightDefs = [
  { key: 'type_weight', title: '媒体类型', icon: 'mdi-movie-open-outline' },
  { key: 'theme_weight', title: '题材主题', icon: 'mdi-tag-multiple-outline' },
  { key: 'actor_weight', title: '演员偏好', icon: 'mdi-account-star-outline' },
  { key: 'director_weight', title: '导演偏好', icon: 'mdi-chair-rolling' },
  { key: 'region_weight', title: '地区偏好', icon: 'mdi-earth' },
  { key: 'year_weight', title: '年代偏好', icon: 'mdi-calendar-range' },
  { key: 'rating_weight', title: '口碑评分', icon: 'mdi-star-outline' },
  { key: 'heat_weight', title: '当前热度', icon: 'mdi-fire' },
  { key: 'freshness_weight', title: '新鲜程度', icon: 'mdi-sprout-outline' },
  { key: 'similarity_weight', title: '画像相似', icon: 'mdi-vector-link' },
];

const sourceDefs = [
  { key: 'douban', title: '豆瓣发现', subtitle: '热门电影、剧集与动画', icon: 'mdi-alpha-d-circle-outline' },
  { key: 'tmdb_movies', title: 'TMDB电影', subtitle: '高热度电影候选', icon: 'mdi-movie-open-star-outline' },
  { key: 'tmdb_tv', title: 'TMDB剧集', subtitle: '高热度剧集候选', icon: 'mdi-television-classic' },
  { key: 'bangumi', title: 'Bangumi', subtitle: '动画与番剧候选', icon: 'mdi-animation-outline' },
  { key: 'extensions', title: '扩展来源', subtitle: '已安装插件提供的发现源', icon: 'mdi-puzzle-outline' },
];

const mediaTypeOptions = [
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
  { title: '动漫', value: 'anime' },
];
const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知确认', value: 'notify' },
  { title: '自动订阅前 N', value: 'auto_subscribe' },
];

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
const userOptions = computed(() => {
  const values = availableUsers.value.length ? availableUsers.value : form.users;
  return values.map(name => ({ title: name, value: name }))
});

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

function applyConfig(value) {
  const next = cloneConfig(value);
  Object.assign(form, cloneConfig(defaults), next);
  form.weights = { ...weightDefaults, ...(next.weights || {}) };
  form.discovery_sources = { ...defaults.discovery_sources, ...(next.discovery_sources || {}) };
  form.users = Array.isArray(next.users) ? [...new Set(next.users.filter(Boolean))] : [];
  form.media_types = Array.isArray(next.media_types) ? [...next.media_types] : [...defaults.media_types];
  form.exclude_keywords = Array.isArray(next.exclude_keywords) ? [...next.exclude_keywords] : [];
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true });
watch(
  () => [...form.users],
  users => {
    if (!users.includes(form.default_user)) form.default_user = users[0] || '';
  },
);

async function loadRuntime() {
  if (!props.api?.get) return
  loading.value = true;
  loadError.value = '';
  try {
    const [statusData, optionsData] = await Promise.all([
      getPluginApi(props.api, 'status'),
      getPluginApi(props.api, 'config/options'),
    ]);
    status.value = statusData || status.value;
    availableUsers.value = optionsData?.available_users || optionsData?.users || [];
  } catch (error) {
    loadError.value = error?.message || '运行信息加载失败';
  } finally {
    loading.value = false;
  }
}

function saveConfig() {
  const payload = cloneConfig(form);
  delete payload._validation_errors;
  emit('save', payload);
}

onMounted(loadRuntime);

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
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VAutocomplete = _resolveComponent("VAutocomplete");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSlider = _resolveComponent("VSlider");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "ar-config__card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "ar-config__header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-brain",
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
              label: "启用插件"
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                _createTextVNode("Agent榜单中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
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
              class: "ar-config__nav-list py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "ar-config__nav-item",
                    onClick: $event => (activeMain.value = item.key)
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
              _createElementVNode("button", _hoisted_6, [
                _createVNode(_component_VIcon, {
                  icon: currentMain.value.icon,
                  size: "18",
                  class: "mr-1"
                }, null, 8, ["icon"]),
                _createTextVNode(_toDisplayString(currentMain.value.title), 1)
              ])
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", {
              class: _normalizeClass(["ar-config__window", { 'ar-config__window--overview': activeMain.value === 'overview' }])
            }, [
              _withDirectives(_createElementVNode("div", _hoisted_7, [
                _cache[23] || (_cache[23] = _createElementVNode("div", { class: "ar-config__section-title" }, "运行链路步骤", -1)),
                _createElementVNode("div", _hoisted_8, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(['读取用户订阅', '冻结发现候选', '受限Agent排序', '确定性安全校验', '更新榜单与动作'], (step, index) => {
                    return _createElementVNode("div", {
                      key: step,
                      class: "ar-config__step"
                    }, [
                      _createVNode(_component_VAvatar, {
                        size: "28",
                        color: "primary",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(index + 1), 1)
                        ]),
                        _: 2
                      }, 1024),
                      _createElementVNode("span", null, _toDisplayString(step), 1),
                      (index < 4)
                        ? (_openBlock(), _createBlock(_component_VIcon, {
                            key: 0,
                            icon: "mdi-chevron-right",
                            size: "18",
                            class: "ar-config__step-arrow"
                          }))
                        : _createCommentVNode("", true)
                    ])
                  }), 64))
                ]),
                _createElementVNode("div", _hoisted_9, [
                  _createVNode(_component_VCard, {
                    variant: "outlined",
                    class: "ar-config__overview-card"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardText, null, {
                        default: _withCtx(() => [
                          _createElementVNode("div", _hoisted_10, [
                            _cache[21] || (_cache[21] = _createElementVNode("span", { class: "text-subtitle-2" }, "当前状态", -1)),
                            _createVNode(_component_VChip, {
                              color: status.value.state === 'ready' ? 'success' : 'warning',
                              variant: "tonal",
                              size: "small"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(status.value.state === 'ready' ? '已就绪' : '未运行'), 1)
                              ]),
                              _: 1
                            }, 8, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_11, _toDisplayString(form.enabled ? '插件已启用，等待手动或周期刷新。' : '启用并保存后才会生成榜单。'), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCard, {
                    variant: "outlined",
                    class: "ar-config__overview-card"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardText, null, {
                        default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                          _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "失败兜底", -1),
                          _createElementVNode("div", { class: "ar-config__hint" }, "Agent、候选或保存失败时保留旧画像与旧榜单，不执行订阅。", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                (loadError.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(loadError.value), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                (status.value.validation_errors?.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 1,
                      type: "warning",
                      variant: "tonal",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.validation_errors, (item) => {
                          return (_openBlock(), _createElementBlock("div", { key: item }, _toDisplayString(item), 1))
                        }), 128))
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true)
              ], 512), [
                [_vShow, activeMain.value === 'overview']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_12, [
                _cache[25] || (_cache[25] = _createElementVNode("div", { class: "ar-config__section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "7"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VAutocomplete, {
                          modelValue: form.users,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.users) = $event)),
                          items: userOptions.value,
                          "item-title": "title",
                          "item-value": "value",
                          label: "参与用户",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "5"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.default_user,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.default_user) = $event)),
                          items: form.users,
                          label: "默认用户",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !form.users.length
                        }, null, 8, ["modelValue", "items", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.schedule_enabled,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.schedule_enabled) = $event)),
                          color: "success",
                          label: "周期运行",
                          "hide-details": "",
                          inset: ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.cron) = $event)),
                          label: "运行周期",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !form.schedule_enabled
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                    _createTextVNode("周期任务按参与用户顺序执行，单用户失败不会阻断后续用户。", -1)
                  ]))]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_13, [
                _cache[26] || (_cache[26] = _createElementVNode("div", { class: "ar-config__section-title" }, "发现来源", -1)),
                _createElementVNode("div", _hoisted_14, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(sourceDefs, (source) => {
                    return _createVNode(_component_VCard, {
                      key: source.key,
                      variant: "outlined",
                      class: "ar-config__source-card"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCardItem, null, {
                          prepend: _withCtx(() => [
                            _createVNode(_component_VAvatar, {
                              color: "primary",
                              variant: "tonal",
                              size: "36"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VIcon, {
                                  icon: source.icon
                                }, null, 8, ["icon"])
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          append: _withCtx(() => [
                            _createVNode(_component_VSwitch, {
                              modelValue: form.discovery_sources[source.key],
                              "onUpdate:modelValue": $event => ((form.discovery_sources[source.key]) = $event),
                              color: "success",
                              "hide-details": "",
                              inset: "",
                              "aria-label": `启用${source.title}`
                            }, null, 8, ["modelValue", "onUpdate:modelValue", "aria-label"])
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(source.title), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VCardSubtitle, null, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(source.subtitle), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024)
                  }), 64))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'sources']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_15, [
                _cache[28] || (_cache[28] = _createElementVNode("div", { class: "ar-config__section-title" }, "权重设置", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                    _createTextVNode("Config 是权重唯一写入口；数值越高，Agent 排序时越重视该维度。", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_16, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(weightDefs, (weight) => {
                    return _createElementVNode("div", {
                      key: weight.key,
                      class: "ar-config__weight-item"
                    }, [
                      _createElementVNode("div", _hoisted_17, [
                        _createVNode(_component_VIcon, {
                          icon: weight.icon,
                          size: "18",
                          color: "primary",
                          class: "mr-2"
                        }, null, 8, ["icon"]),
                        _createElementVNode("span", _hoisted_18, _toDisplayString(weight.title), 1),
                        _createVNode(_component_VSpacer),
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          variant: "tonal",
                          color: "primary"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(Number(form.weights[weight.key]).toFixed(1)), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _createVNode(_component_VSlider, {
                        modelValue: form.weights[weight.key],
                        "onUpdate:modelValue": $event => ((form.weights[weight.key]) = $event),
                        min: 0,
                        max: 1,
                        step: 0.1,
                        color: "primary",
                        "hide-details": "",
                        "thumb-label": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createElementVNode("div", _hoisted_19, "默认 " + _toDisplayString(weightDefaults[weight.key].toFixed(1)), 1)
                    ])
                  }), 64))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'weights']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_20, [
                _cache[29] || (_cache[29] = _createElementVNode("div", { class: "ar-config__section-title" }, "条件筛选", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.media_types,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.media_types) = $event)),
                          items: mediaTypeOptions,
                          label: "媒体类型",
                          multiple: "",
                          chips: "",
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
                        _createVNode(_component_VSelect, {
                          modelValue: form.profile_scope,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.profile_scope) = $event)),
                          items: [{ title: '全部订阅', value: 'all' }, { title: '近期订阅', value: 'recent' }],
                          label: "画像范围",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
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
                          modelValue: form.candidate_pool_size,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.candidate_pool_size) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "10",
                          max: "500",
                          label: "候选池数量",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_21, "置信度阈值 " + _toDisplayString(Math.round(form.confidence_threshold * 100)) + "%", 1),
                        _createVNode(_component_VSlider, {
                          modelValue: form.confidence_threshold,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.confidence_threshold) = $event)),
                          min: 0,
                          max: 1,
                          step: 0.05,
                          color: "primary",
                          "hide-details": "",
                          "thumb-label": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCombobox, {
                          modelValue: form.exclude_keywords,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.exclude_keywords) = $event)),
                          label: "排除关键词",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
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
                [_vShow, activeMain.value === 'filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_22, [
                _cache[30] || (_cache[30] = _createElementVNode("div", { class: "ar-config__section-title" }, "榜单行为", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.action_mode,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.action_mode) = $event)),
                          items: actionOptions,
                          label: "动作模式",
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
                          modelValue: form.auto_subscribe_top_n,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.auto_subscribe_top_n) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "0",
                          max: form.auto_subscribe_limit,
                          label: "自动订阅前 N",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: form.action_mode !== 'auto_subscribe'
                        }, null, 8, ["modelValue", "max", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.auto_subscribe_limit,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.auto_subscribe_limit) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "0",
                          max: "10",
                          label: "安全上限",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.notify) = $event)),
                          color: "info",
                          label: "发送通知",
                          "hide-details": "",
                          inset: "",
                          disabled: form.action_mode === 'update'
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: form.action_mode === 'auto_subscribe' ? 'warning' : 'info',
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、置信度、识别 ID 和重复订阅。' : '通知确认只发送摘要，用户仍需从榜单界面手动订阅。'), 1)
                  ]),
                  _: 1
                }, 8, ["type"])
              ], 512), [
                [_vShow, activeMain.value === 'board']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_23, [
                _cache[32] || (_cache[32] = _createElementVNode("div", { class: "ar-config__section-title" }, "高级选项", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.profile_cache_enabled,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.profile_cache_enabled) = $event)),
                          color: "success",
                          label: "画像缓存",
                          "hide-details": "",
                          inset: ""
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
                          modelValue: form.rebuild_profile_each_run,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.rebuild_profile_each_run) = $event)),
                          color: "warning",
                          label: "每次重建",
                          "hide-details": "",
                          inset: ""
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
                          modelValue: form.subscription_sample_limit,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.subscription_sample_limit) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "1000",
                          label: "订阅样本上限",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
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
                          modelValue: form.minimum_samples,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.minimum_samples) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "100",
                          label: "最少样本",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
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
                          modelValue: form.history_limit,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.history_limit) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "200",
                          label: "历史上限",
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
                  type: "warning",
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                    _createTextVNode("画像、榜单和归档清理属于用户级危险操作，请在完整榜单或详情页二次确认后执行。", -1)
                  ]))]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'advanced']
              ])
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "ar-config__actions" }, {
          default: _withCtx(() => [
            (loading.value)
              ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                  key: 0,
                  indeterminate: "",
                  size: "20",
                  width: "2",
                  color: "primary"
                }))
              : _createCommentVNode("", true),
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[19] || (_cache[19] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
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
              default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-166dd150"]]);

export { Config as default };
