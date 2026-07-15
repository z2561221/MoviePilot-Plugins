import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState, R as RecommendationActions } from './RecommendationActions-CBQjsTdv.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-BGNRvR24.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "ar-page" };
const _hoisted_2 = { class: "ar-page__summary-bar" };
const _hoisted_3 = { class: "ar-page__stat-value" };
const _hoisted_4 = { class: "ar-page__stat-label" };
const _hoisted_5 = { class: "ar-page__content" };
const _hoisted_6 = { class: "ar-page__pane" };
const _hoisted_7 = { class: "ar-page__section-head" };
const _hoisted_8 = {
  key: 1,
  class: "ar-page__ranking"
};
const _hoisted_9 = { class: "ar-page__poster" };
const _hoisted_10 = { class: "ar-page__poster-error" };
const _hoisted_11 = { class: "ar-page__rank-main" };
const _hoisted_12 = { class: "ar-page__title-row" };
const _hoisted_13 = { class: "ar-page__media-title" };
const _hoisted_14 = { class: "ar-page__meta-row" };
const _hoisted_15 = { class: "ar-page__rank-copy" };
const _hoisted_16 = { class: "ar-page__rank-copy ar-page__rank-copy--muted" };
const _hoisted_17 = { class: "ar-page__rank-actions" };
const _hoisted_18 = { class: "ar-page__pane" };
const _hoisted_19 = { class: "ar-page__profile-summary" };
const _hoisted_20 = { class: "ar-page__profile-sample" };
const _hoisted_21 = { class: "ar-page__chips" };
const _hoisted_22 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_23 = { class: "ar-page__pane" };
const _hoisted_24 = { class: "ar-page__section-head" };
const _hoisted_25 = {
  key: 1,
  class: "ar-page__archive-list"
};
const _hoisted_26 = { class: "ar-page__archive-rank" };
const _hoisted_27 = { class: "ar-page__pane" };
const _hoisted_28 = { class: "ar-page__section-head" };
const _hoisted_29 = { class: "ar-page__table-wrap" };
const _hoisted_30 = { class: "ar-page__time-cell" };
const _hoisted_31 = { class: "ar-page__error-cell" };

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
const snackbar = ref({ show: false, message: '', color: 'success' });
const historyPage = ref(1);
const initialized = ref(false);
const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 10) || []);
const archiveEntries = computed(() => state.overview.value?.archive?.entries || []);
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)));
const detailStats = computed(() => [
  { label: '榜单条目', value: recommendations.value.length, suffix: '部', icon: 'mdi-format-list-numbered' },
  { label: '画像样本', value: state.profile.value?.subscription_count || 0, suffix: '条', icon: 'mdi-account-heart-outline' },
  { label: '忽略归档', value: archiveEntries.value.length, suffix: '部', icon: 'mdi-archive-outline' },
]);

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

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'archive', title: '忽略归档', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return ({ movie: '电影', tv: '剧集', anime: '动漫' })[value] || value || '未知'
}

async function initialize() {
  try {
    await state.loadOptions();
    if (state.selectedUser.value) await state.loadUserData();
  } catch (_) {
    // 共享状态承载错误。
  } finally {
    initialized.value = true;
  }
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
  if (!initialized.value || !value || value === oldValue) return
  historyPage.value = 1;
  try { await state.loadUserData(value); } catch (_) { /* 错误已保存 */ }
});

watch(activeTab, async value => {
  if (value === 'history') await changeHistoryPage(1);
});

onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "ar-page__toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VAvatar, {
          color: "primary",
          variant: "tonal",
          size: "42",
          rounded: "lg",
          class: "ar-page__brand ms-4 me-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VIcon, {
              icon: "mdi-brain",
              size: "24"
            })
          ]),
          _: 1
        }),
        _cache[9] || (_cache[9] = _createElementVNode("div", { class: "ar-page__heading" }, [
          _createElementVNode("div", { class: "ar-page__title" }, "Agent榜单中心"),
          _createElementVNode("div", { class: "ar-page__subtitle" }, "推荐结果、用户画像与运行记录")
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
          class: "me-2",
          onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(detailStats.value, (stat) => {
        return (_openBlock(), _createElementBlock("div", {
          key: stat.label,
          class: "ar-page__stat"
        }, [
          _createVNode(_component_VIcon, {
            icon: stat.icon,
            color: "primary",
            size: "20"
          }, null, 8, ["icon"]),
          _createElementVNode("div", null, [
            _createElementVNode("div", _hoisted_3, [
              _createTextVNode(_toDisplayString(stat.value), 1),
              _createElementVNode("span", null, _toDisplayString(stat.suffix), 1)
            ]),
            _createElementVNode("div", _hoisted_4, _toDisplayString(stat.label), 1)
          ])
        ]))
      }), 128)),
      _createVNode(_component_VChip, {
        color: _unref(state).isRunning.value ? 'primary' : 'success',
        variant: "tonal",
        size: "small",
        "prepend-icon": _unref(state).isRunning.value ? 'mdi-loading' : 'mdi-check-circle-outline',
        class: "ar-page__runtime-chip"
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(_unref(state).isRunning.value ? '正在生成' : '运行就绪'), 1)
        ]),
        _: 1
      }, 8, ["color", "prepend-icon"])
    ]),
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
            value: tab.key,
            class: "text-none"
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
    _createElementVNode("div", _hoisted_5, [
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
            type: "list-item-avatar-three-line@5"
          }))
        : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
            _withDirectives(_createElementVNode("section", _hoisted_6, [
              _createElementVNode("div", _hoisted_7, [
                _cache[10] || (_cache[10] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "个性推荐榜单"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "Agent 根据订阅画像，从发现候选中挑出的 Top 10。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  color: "primary",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(recommendations.value.length) + " 部", 1)
                  ]),
                  _: 1
                })
              ]),
              (!recommendations.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-format-list-numbered",
                    title: "推荐榜单尚未生成",
                    text: "点击右上角刷新，为当前用户生成 Top 10。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_8, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recommendations.value, (item) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: item.candidate_id,
                        class: "ar-page__rank-item"
                      }, [
                        _createElementVNode("div", {
                          class: _normalizeClass(["ar-page__rank", { 'ar-page__rank--top': item.rank <= 3 }])
                        }, _toDisplayString(item.rank), 3),
                        _createElementVNode("div", _hoisted_9, [
                          (item.poster_path)
                            ? (_openBlock(), _createBlock(_component_VImg, {
                                key: 0,
                                src: item.poster_path,
                                alt: `${item.title} 海报`,
                                cover: ""
                              }, {
                                error: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_10, [
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
                        _createElementVNode("div", _hoisted_11, [
                          _createElementVNode("div", _hoisted_12, [
                            _createElementVNode("div", _hoisted_13, _toDisplayString(item.title), 1),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(mediaTypeLabel(item.media_type)), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _createElementVNode("div", _hoisted_14, [
                            _createElementVNode("span", null, _toDisplayString(item.year || '年份未知'), 1),
                            _createElementVNode("span", null, "置信度 " + _toDisplayString(item.confidence) + "%", 1)
                          ]),
                          _createElementVNode("div", _hoisted_15, [
                            _cache[11] || (_cache[11] = _createElementVNode("span", { class: "ar-page__copy-label" }, "推荐", -1)),
                            _createElementVNode("span", null, _toDisplayString(item.reason || item.summary || '等待 Agent 补充推荐理由'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_16, [
                            _cache[12] || (_cache[12] = _createElementVNode("span", { class: "ar-page__copy-label" }, "简介", -1)),
                            _createElementVNode("span", null, _toDisplayString(item.summary || '暂无简介'), 1)
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_17, [
                          _createVNode(RecommendationActions, {
                            item: item,
                            "loading-action": _unref(state).loading.action,
                            size: "small",
                            onSubscribe: _cache[5] || (_cache[5] = candidateId => runAction(() => _unref(state).subscribe(candidateId), '订阅操作已完成')),
                            onArchive: _cache[6] || (_cache[6] = candidateId => runAction(() => _unref(state).archive(candidateId), '已忽略推荐'))
                          }, null, 8, ["item", "loading-action"])
                        ])
                      ]))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'board']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_18, [
              _cache[15] || (_cache[15] = _createElementVNode("div", { class: "ar-page__section-head" }, [
                _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "用户画像"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "画像来自当前订阅样本，用于约束推荐方向。")
                ])
              ], -1)),
              _createVNode(_component_VCard, {
                variant: "outlined",
                class: "ar-page__section-card"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardItem, { class: "ar-page__profile-head" }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VAvatar, {
                        color: "primary",
                        variant: "tonal",
                        size: "44"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VIcon, { icon: "mdi-account-heart-outline" })
                        ]),
                        _: 1
                      })
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VCardTitle, { class: "text-subtitle-1 font-weight-bold" }, {
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
                  _createVNode(_component_VDivider),
                  _createVNode(_component_VCardText, { class: "ar-page__profile-body" }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_19, _toDisplayString(_unref(state).profile.value?.summary || '尚未生成用户画像'), 1),
                      _createElementVNode("div", _hoisted_20, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-database-check-outline",
                          color: "primary",
                          size: "20"
                        }),
                        _createElementVNode("div", null, [
                          _createElementVNode("strong", null, _toDisplayString(_unref(state).profile.value?.subscription_count || 0), 1),
                          _cache[14] || (_cache[14] = _createElementVNode("span", null, "订阅样本", -1))
                        ])
                      ]),
                      _createElementVNode("div", _hoisted_21, [
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
                        }), 128)),
                        (!_unref(state).profile.value?.tags?.length)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_22, "暂无画像标签"))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ], 512), [
              [_vShow, activeTab.value === 'profile']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_23, [
              _createElementVNode("div", _hoisted_24, [
                _cache[16] || (_cache[16] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "忽略归档"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "保留被忽略条目的原排名，可随时恢复推荐。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(archiveEntries.value.length) + " 部", 1)
                  ]),
                  _: 1
                })
              ]),
              (!archiveEntries.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-archive-outline",
                    title: "暂无忽略记录",
                    text: "榜单中点击忽略后，条目会出现在这里。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_25, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveEntries.value, (entry) => {
                      return (_openBlock(), _createBlock(_component_VCard, {
                        key: entry.candidate_id,
                        variant: "outlined",
                        class: "ar-page__archive-card"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardItem, null, {
                            prepend: _withCtx(() => [
                              _createElementVNode("div", _hoisted_26, "#" + _toDisplayString(entry.original_rank), 1)
                            ]),
                            append: _withCtx(() => [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "primary",
                                class: "mr-1",
                                "prepend-icon": "mdi-backup-restore",
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
                              _createVNode(_component_VCardTitle, { class: "text-subtitle-2 font-weight-bold" }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(entry.recommendation?.title || entry.candidate_id), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardSubtitle, null, {
                                default: _withCtx(() => [
                                  _createTextVNode("忽略于 " + _toDisplayString(formatTime(entry.archived_at)), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024),
                          (entry.recommendation?.summary)
                            ? (_openBlock(), _createBlock(_component_VCardText, {
                                key: 0,
                                class: "ar-page__archive-summary"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(entry.recommendation.summary), 1)
                                ]),
                                _: 2
                              }, 1024))
                            : _createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'archive']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_27, [
              _createElementVNode("div", _hoisted_28, [
                _cache[18] || (_cache[18] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "运行历史"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "查看候选数量、Agent 调用与自动订阅结果。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(_unref(state).historyMeta.value.total || 0) + " 次", 1)
                  ]),
                  _: 1
                })
              ]),
              (!_unref(state).history.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-history",
                    title: "暂无运行记录",
                    text: "榜单生成后，这里会记录每次执行结果。"
                  }))
                : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                    _createVNode(_component_VCard, {
                      variant: "outlined",
                      class: "ar-page__table-card"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_29, [
                          _createVNode(_component_VTable, {
                            density: "compact",
                            "fixed-header": "",
                            height: "430"
                          }, {
                            default: _withCtx(() => [
                              _cache[19] || (_cache[19] = _createElementVNode("thead", null, [
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
                                    _createElementVNode("td", _hoisted_30, _toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
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
                                    _createElementVNode("td", _hoisted_31, _toDisplayString(run.errors?.join('；') || run.message || '—'), 1)
                                  ]))
                                }), 128))
                              ])
                            ]),
                            _: 1
                          })
                        ])
                      ]),
                      _: 1
                    }),
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
                    }, null, 8, ["modelValue", "length"])
                  ], 64)),
              _createElementVNode("span", { class: "d-none" }, "page_size=" + _toDisplayString(historyPageSize))
            ], 512), [
              [_vShow, activeTab.value === 'history']
            ])
          ], 64))
    ]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((snackbar.value.show) = $event)),
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c7baf2be"]]);

export { Page as default };
