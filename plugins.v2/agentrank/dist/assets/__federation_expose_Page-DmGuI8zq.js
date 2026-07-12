import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState } from './useAgentRankState-DMJYFSWp.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-BKA7AlB8.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "ar-page" };
const _hoisted_2 = { class: "ar-page__content" };
const _hoisted_3 = { class: "ar-page__pane" };
const _hoisted_4 = {
  key: 1,
  class: "ar-page__ranking"
};
const _hoisted_5 = { class: "ar-page__rank" };
const _hoisted_6 = { class: "ar-page__poster" };
const _hoisted_7 = { class: "ar-page__poster-error" };
const _hoisted_8 = { class: "ar-page__rank-main" };
const _hoisted_9 = { class: "font-weight-bold text-truncate" };
const _hoisted_10 = { class: "text-caption text-medium-emphasis" };
const _hoisted_11 = { class: "text-body-2 mt-1" };
const _hoisted_12 = { class: "ar-page__rank-actions" };
const _hoisted_13 = { class: "ar-page__pane" };
const _hoisted_14 = { class: "text-body-1 mb-4" };
const _hoisted_15 = { class: "ar-page__chips" };
const _hoisted_16 = { class: "text-caption text-medium-emphasis mt-4" };
const _hoisted_17 = { class: "ar-page__pane" };
const _hoisted_18 = { class: "ar-page__weights" };
const _hoisted_19 = { class: "ar-page__pane" };
const _hoisted_20 = {
  key: 1,
  class: "ar-page__archive-list"
};
const _hoisted_21 = { class: "ar-page__pane" };
const _hoisted_22 = { class: "ar-page__table-wrap" };
const _hoisted_23 = { class: "ar-page__error-cell" };

const {computed,onMounted,ref,watch} = await importShared('vue');

const historyPageSize = 10;


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const state = useAgentRankState(props.api);

const activeTab = ref('board');
const clearDialog = ref(false);
const snackbar = ref({ show: false, message: '', color: 'success' });
const historyPage = ref(1);
const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 10) || []);
const archiveEntries = computed(() => state.overview.value?.archive?.entries || []);
const weights = computed(() => state.options.value?.config?.weights || {});
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)));
const statusMetaFor = status => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
}[status] || { text: status || '未知', color: 'default' });
const weightLabels = {
  type_weight: '媒体类型',
  theme_weight: '题材主题',
  actor_weight: '演员偏好',
  director_weight: '导演偏好',
  region_weight: '地区偏好',
  year_weight: '年代偏好',
  rating_weight: '评分质量',
  heat_weight: '热门程度',
  freshness_weight: '新鲜程度',
  similarity_weight: '相似程度',
};

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'weights', title: '权重配置', icon: 'mdi-tune-vertical' },
  { key: 'archive', title: '归档区', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function weightLabel(key) {
  return weightLabels[key] || key
}

function formatWeight(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

async function initialize() {
  try {
    await state.loadOptions();
    if (state.selectedUser.value) await state.loadUserData();
  } catch (_) { /* 共享状态承载错误 */ }
}

async function runAction(action, successMessage) {
  try {
    await action();
    snackbar.value = { show: true, message: successMessage, color: 'success' };
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' };
  }
}

async function changeHistoryPage(page) {
  historyPage.value = page;
  try { await state.loadHistory(page, historyPageSize); } catch (_) { /* 错误已保存 */ }
}

watch(state.selectedUser, async (value, oldValue) => {
  if (!value || value === oldValue) return
  historyPage.value = 1;
  try { await state.loadUserData(value); } catch (_) { /* 错误已保存 */ }
});

watch(activeTab, async value => {
  if (value === 'history') await changeHistoryPage(1);
});

onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "ar-page__toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-brain",
          color: "primary",
          class: "ar-page__brand-icon ms-3 me-2"
        }),
        _cache[12] || (_cache[12] = _createElementVNode("div", { class: "ar-page__heading" }, [
          _createElementVNode("div", { class: "text-h6" }, "Agent榜单中心详情"),
          _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "推荐、画像、归档与运行记录")
        ], -1)),
        _createVNode(_component_VSpacer),
        (_unref(state).users.value.length > 1)
          ? (_openBlock(), _createBlock(_component_VSelect, {
              key: 0,
              modelValue: _unref(state).selectedUser.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref(state).selectedUser.value) = $event)),
              items: _unref(state).users.value,
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              label: "用户",
              class: "ar-page__user"
            }, null, 8, ["modelValue", "items"]))
          : _createCommentVNode("", true),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          loading: _unref(state).loading.action === 'refresh' || _unref(state).loading.data,
          disabled: _unref(state).isRunning.value,
          "aria-label": "刷新详情",
          onClick: _cache[1] || (_cache[1] = $event => (runAction(_unref(state).refresh, '榜单刷新已完成')))
        }, null, 8, ["loading", "disabled"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-cog-outline",
          variant: "text",
          "aria-label": "打开设置",
          onClick: _cache[2] || (_cache[2] = $event => (emit('switch')))
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          "aria-label": "关闭详情",
          onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createVNode(_component_VTabs, {
      modelValue: activeTab.value,
      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((activeTab).value = $event)),
      color: "primary",
      density: "compact",
      class: "ar-page__tabs",
      "show-arrows": ""
    }, {
      default: _withCtx(() => [
        (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
          return _createVNode(_component_VTab, {
            key: tab.key,
            value: tab.key
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: tab.icon,
                size: "18",
                class: "mr-1"
              }, null, 8, ["icon"]),
              _createTextVNode(_toDisplayString(tab.title), 1)
            ]),
            _: 2
          }, 1032, ["value"])
        }), 64))
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (_unref(state).error.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            class: "mb-3"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(_unref(state).error.value.message), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (_unref(state).loading.data)
        ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
            key: 1,
            type: "article, article"
          }))
        : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
            _withDirectives(_createElementVNode("section", _hoisted_3, [
              (!recommendations.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-format-list-numbered",
                    title: "推荐榜单尚未生成",
                    text: "点击刷新生成当前用户的 Top 10。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_4, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recommendations.value, (item) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: item.candidate_id,
                        class: "ar-page__rank-item"
                      }, [
                        _createElementVNode("div", _hoisted_5, _toDisplayString(item.rank), 1),
                        _createElementVNode("div", _hoisted_6, [
                          (item.poster_path)
                            ? (_openBlock(), _createBlock(_component_VImg, {
                                key: 0,
                                src: item.poster_path,
                                alt: `${item.title} 海报`,
                                cover: "",
                                eager: ""
                              }, {
                                error: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_7, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-image-off-outline",
                                      size: "26"
                                    })
                                  ])
                                ]),
                                _: 1
                              }, 8, ["src", "alt"]))
                            : (_openBlock(), _createBlock(_component_VIcon, {
                                key: 1,
                                icon: "mdi-image-off-outline",
                                size: "26"
                              }))
                        ]),
                        _createElementVNode("div", _hoisted_8, [
                          _createElementVNode("div", _hoisted_9, _toDisplayString(item.title), 1),
                          _createElementVNode("div", _hoisted_10, _toDisplayString(item.year || '年份未知') + " · " + _toDisplayString(item.media_type), 1),
                          _createElementVNode("div", _hoisted_11, _toDisplayString(item.summary), 1)
                        ]),
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          color: "primary",
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(item.confidence) + "%", 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createElementVNode("div", _hoisted_12, [
                          _createVNode(_component_VBtn, {
                            icon: "mdi-plus-circle-outline",
                            color: "primary",
                            variant: "tonal",
                            size: "small",
                            "min-width": "40",
                            height: "40",
                            "aria-label": `订阅 ${item.title}`,
                            onClick: $event => (runAction(() => _unref(state).subscribe(item.candidate_id), '订阅操作已完成'))
                          }, null, 8, ["aria-label", "onClick"]),
                          _createVNode(_component_VBtn, {
                            icon: "mdi-eye-off-outline",
                            variant: "text",
                            size: "small",
                            "min-width": "40",
                            height: "40",
                            "aria-label": `忽略 ${item.title}`,
                            onClick: $event => (runAction(() => _unref(state).archive(item.candidate_id), '已忽略推荐'))
                          }, null, 8, ["aria-label", "onClick"])
                        ])
                      ]))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'board']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_13, [
              _createVNode(_component_VCard, {
                variant: "outlined",
                class: "ar-page__section-card"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardItem, null, {
                    append: _withCtx(() => [
                      _createVNode(_component_VBtn, {
                        color: "error",
                        variant: "text",
                        "prepend-icon": "mdi-account-remove-outline",
                        onClick: _cache[5] || (_cache[5] = $event => (clearDialog.value = true))
                      }, {
                        default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                          _createTextVNode("清除画像", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                        default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                          _createTextVNode("画像摘要", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode(_component_VCardSubtitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode("生成于 " + _toDisplayString(formatTime(_unref(state).profile.value?.generated_at)), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCardText, null, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_14, _toDisplayString(_unref(state).profile.value?.summary || '尚未生成用户画像'), 1),
                      _createElementVNode("div", _hoisted_15, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(state).profile.value?.tags || [], (tag) => {
                          return (_openBlock(), _createBlock(_component_VChip, {
                            key: tag,
                            color: "primary",
                            variant: "tonal",
                            size: "small"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(tag), 1)
                            ]),
                            _: 2
                          }, 1024))
                        }), 128))
                      ]),
                      _createElementVNode("div", _hoisted_16, "订阅样本 " + _toDisplayString(_unref(state).profile.value?.subscription_count || 0) + " 条", 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ], 512), [
              [_vShow, activeTab.value === 'profile']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_17, [
              _createVNode(_component_VAlert, {
                type: "info",
                variant: "tonal",
                class: "mb-3"
              }, {
                default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                  _createTextVNode("权重配置在此只读展示，请进入 Config 修改。", -1)
                ]))]),
                _: 1
              }),
              _createElementVNode("div", _hoisted_18, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(weights.value, (value, key) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: key,
                    class: "ar-page__weight"
                  }, [
                    _createElementVNode("span", null, _toDisplayString(weightLabel(key)), 1),
                    _createVNode(_component_VProgressLinear, {
                      "model-value": Number(value) * 100,
                      color: "primary",
                      height: "8",
                      rounded: ""
                    }, null, 8, ["model-value"]),
                    _createElementVNode("strong", null, _toDisplayString(formatWeight(value)), 1)
                  ]))
                }), 128))
              ]),
              _createVNode(_component_VBtn, {
                color: "primary",
                variant: "tonal",
                "prepend-icon": "mdi-cog-outline",
                class: "mt-4",
                onClick: _cache[6] || (_cache[6] = $event => (emit('switch')))
              }, {
                default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                  _createTextVNode("进入设置", -1)
                ]))]),
                _: 1
              })
            ], 512), [
              [_vShow, activeTab.value === 'weights']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_19, [
              (!archiveEntries.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-archive-outline",
                    title: "暂无归档",
                    text: "忽略的推荐会保留原排名和恢复信息。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_20, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveEntries.value, (entry) => {
                      return (_openBlock(), _createBlock(_component_VCard, {
                        key: entry.candidate_id,
                        variant: "outlined",
                        class: "ar-page__archive-card"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardItem, null, {
                            append: _withCtx(() => [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "primary",
                                class: "mr-1",
                                onClick: $event => (runAction(() => _unref(state).restore(entry.candidate_id), '推荐已恢复'))
                              }, {
                                default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                                  _createTextVNode("恢复", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick"]),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                size: "small",
                                variant: "text",
                                color: "error",
                                "aria-label": `删除归档 ${entry.candidate_id}`,
                                onClick: $event => (runAction(() => _unref(state).deleteArchive(entry.candidate_id), '归档记录已删除'))
                              }, null, 8, ["aria-label", "onClick"])
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(entry.recommendation?.title || entry.candidate_id), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardSubtitle, null, {
                                default: _withCtx(() => [
                                  _createTextVNode("原排名 #" + _toDisplayString(entry.original_rank) + " · " + _toDisplayString(formatTime(entry.archived_at)), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'archive']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_21, [
              _createElementVNode("div", _hoisted_22, [
                _createVNode(_component_VTable, {
                  density: "compact",
                  "fixed-header": "",
                  height: "420"
                }, {
                  default: _withCtx(() => [
                    _cache[18] || (_cache[18] = _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _createElementVNode("th", null, "时间"),
                        _createElementVNode("th", null, "状态"),
                        _createElementVNode("th", null, "候选"),
                        _createElementVNode("th", null, "推荐"),
                        _createElementVNode("th", null, "Agent"),
                        _createElementVNode("th", null, "自动订阅"),
                        _createElementVNode("th", null, "失败原因")
                      ])
                    ], -1)),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(state).history.value, (run) => {
                        return (_openBlock(), _createElementBlock("tr", {
                          key: `${run.run_id}-${run.finished_at}`
                        }, [
                          _createElementVNode("td", null, _toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                          _createElementVNode("td", null, [
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: statusMetaFor(run.status).color,
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(statusMetaFor(run.status).text), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"])
                          ]),
                          _createElementVNode("td", null, _toDisplayString(run.metrics?.candidate_count ?? '—'), 1),
                          _createElementVNode("td", null, _toDisplayString(run.metrics?.final_count ?? '—'), 1),
                          _createElementVNode("td", null, _toDisplayString(run.metrics?.agent_calls ?? '—') + " 次", 1),
                          _createElementVNode("td", null, _toDisplayString(run.metrics?.subscription_success_count ?? 0), 1),
                          _createElementVNode("td", _hoisted_23, _toDisplayString(run.errors?.join('；') || run.message || '—'), 1)
                        ]))
                      }), 128))
                    ])
                  ]),
                  _: 1
                })
              ]),
              _createVNode(_component_VPagination, {
                modelValue: historyPage.value,
                "onUpdate:modelValue": [
                  _cache[7] || (_cache[7] = $event => ((historyPage).value = $event)),
                  changeHistoryPage
                ],
                length: historyPages.value,
                density: "compact",
                "total-visible": "7",
                class: "mt-3"
              }, null, 8, ["modelValue", "length"]),
              _createElementVNode("span", { class: "d-none" }, "page_size=" + _toDisplayString(historyPageSize))
            ], 512), [
              [_vShow, activeTab.value === 'history']
            ])
          ], 64))
    ]),
    _createVNode(_component_VDialog, {
      modelValue: clearDialog.value,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((clearDialog).value = $event)),
      "max-width": "480"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode("清除当前画像？", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                _createTextVNode("会级联删除当前画像和榜单，但不会删除 MoviePilot 订阅、订阅任务、归档或全局配置。", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[8] || (_cache[8] = $event => (clearDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  onClick: _cache[9] || (_cache[9] = $event => {runAction(async () => { await _unref(state).clearProfile(); clearDialog.value = false; }, '画像与榜单已清除');})
                }, {
                  default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                    _createTextVNode("清除画像", -1)
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((snackbar.value.show) = $event)),
      color: snackbar.value.color
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(snackbar.value.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-dbbd3756"]]);

export { Page as default };
