import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState, R as RecommendationActions } from './RecommendationActions-BpIYbzqo.js';
import Config from './__federation_expose_Config-DllUt3jp.js';
import { _ as _export_sfc, s as savePluginConfig } from './_plugin-vue_export-helper-BGNRvR24.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,unref:_unref,isRef:_isRef,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,createSlots:_createSlots} = await importShared('vue');


const _hoisted_1 = { class: "ar-app-page" };
const _hoisted_2 = { class: "ar-app-page__heading" };
const _hoisted_3 = { class: "text-caption text-medium-emphasis" };
const _hoisted_4 = {
  key: 0,
  class: "ar-app-page__state"
};
const _hoisted_5 = {
  key: 1,
  class: "ar-app-page__state"
};
const _hoisted_6 = {
  key: 2,
  class: "ar-app-page__content"
};
const _hoisted_7 = { class: "ar-app-page__layout" };
const _hoisted_8 = {
  class: "ar-app-page__ranking",
  "aria-label": "Top 10 推荐榜单"
};
const _hoisted_9 = { class: "ar-app-page__section-head" };
const _hoisted_10 = {
  key: 2,
  class: "ar-app-page__list"
};
const _hoisted_11 = { class: "ar-app-page__poster" };
const _hoisted_12 = { class: "ar-app-page__poster-error" };
const _hoisted_13 = { class: "ar-app-page__item-main" };
const _hoisted_14 = { class: "ar-app-page__title-row" };
const _hoisted_15 = { class: "ar-app-page__title" };
const _hoisted_16 = { class: "ar-app-page__meta" };
const _hoisted_17 = { class: "ar-app-page__summary" };
const _hoisted_18 = { class: "ar-app-page__summary ar-app-page__summary--intro" };
const _hoisted_19 = { class: "ar-app-page__tags" };
const _hoisted_20 = { class: "ar-app-page__item-actions" };

const {computed,onMounted,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
},
  setup(__props) {

const props = __props;
const state = useAgentRankState(props.api);
const {
  options,
  users,
  selectedUser,
  overview,
  board,
  loading,
  error,
  isRunning,
} = state;

const settingsDialog = ref(false);
const savingSettings = ref(false);
const snackbar = ref({ show: false, message: '', color: 'success', undo: false });
const lastArchivedId = ref('');
const initialized = ref(false);

const recommendations = computed(() => board.value?.recommendations?.slice(0, 10) || []);
const generatedAt = computed(() => board.value?.generated_at || overview.value?.latest_run?.finished_at || '');
const boardStatus = computed(() => board.value?.status || 'idle');

const statusMeta = computed(() => {
  const map = {
    idle: { text: '待生成', color: 'default', icon: 'mdi-clock-outline' },
    running: { text: '运行中', color: 'primary', icon: 'mdi-loading mdi-spin' },
    success: { text: '已完成', color: 'success', icon: 'mdi-check-circle-outline' },
    sample_insufficient: { text: '样本不足', color: 'warning', icon: 'mdi-database-alert-outline' },
    candidate_insufficient: { text: '候选不足', color: 'warning', icon: 'mdi-compass-off-outline' },
    recommendation_incomplete: { text: '榜单不足', color: 'warning', icon: 'mdi-format-list-numbered' },
    agent_failed: { text: 'Agent失败', color: 'error', icon: 'mdi-robot-confused-outline' },
    validation_failed: { text: '校验失败', color: 'error', icon: 'mdi-shield-alert-outline' },
    subscription_partial_failed: { text: '部分订阅失败', color: 'warning', icon: 'mdi-alert-circle-outline' },
  };
  return map[boardStatus.value] || { text: boardStatus.value, color: 'info', icon: 'mdi-information-outline' }
});

const stateMessage = computed(() => {
  if (error.value) return error.value.message
  const messages = {
    sample_insufficient: '当前用户需要更多订阅样本，旧榜单不会被覆盖。',
    candidate_insufficient: '当前发现来源没有足够候选，请检查来源设置。',
    recommendation_incomplete: `本轮仅生成 ${recommendations.value.length} 条安全推荐。`,
    agent_failed: '本轮 Agent 调用失败，正在展示上一次成功榜单。',
    validation_failed: '本轮输出未通过安全校验，旧榜单已保留。',
    subscription_partial_failed: '部分自动订阅失败，成功项不受影响。',
  };
  return messages[boardStatus.value] || ''
});

function formatTime(value) {
  if (!value) return '尚未生成'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return { movie: '电影', tv: '剧集', anime: '动漫' }[value] || '媒体'
}

function sourceLabel(item) {
  const sources = item?.sources || Object.keys(item?.source_ids || {});
  return sources.length ? sources.join(' · ') : 'MP发现'
}

function posterSource(item) {
  return item?.poster_path || ''
}

async function initialize() {
  try {
    await state.loadOptions();
    if (selectedUser.value) await state.loadUserData();
  } catch (_) {
    // 共享状态已保存可见错误。
  } finally {
    initialized.value = true;
  }
}

async function refreshBoard() {
  try {
    await state.refresh();
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '榜单刷新失败', color: 'error', undo: false };
  }
}

async function subscribeItem(candidateId) {
  try {
    const result = await state.subscribe(candidateId);
    snackbar.value = { show: true, message: result?.message || '订阅操作已完成', color: 'success', undo: false };
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '订阅失败', color: 'error', undo: false };
  }
}

async function archiveItem(candidateId) {
  try {
    await state.archive(candidateId);
    lastArchivedId.value = candidateId;
    snackbar.value = { show: true, message: '已忽略该推荐', color: 'success', undo: true };
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '忽略失败', color: 'error', undo: false };
  }
}

async function undoArchive() {
  if (!lastArchivedId.value) return
  try {
    await state.restore(lastArchivedId.value);
    snackbar.value = { show: true, message: '已撤销忽略', color: 'success', undo: false };
    lastArchivedId.value = '';
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '撤销失败', color: 'error', undo: false };
  }
}

function openSettings() {
  settingsDialog.value = true;
}

async function saveSettings(payload) {
  savingSettings.value = true;
  try {
    await savePluginConfig(props.api, payload);
    await state.loadOptions({ force: true });
    settingsDialog.value = false;
    snackbar.value = { show: true, message: '插件设置已保存', color: 'success', undo: false };
  } catch (err) {
    snackbar.value = { show: true, message: err?.message || '设置保存失败', color: 'error', undo: false };
  } finally {
    savingSettings.value = false;
  }
}

watch(selectedUser, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  try { await state.loadUserData(value); } catch (_) { /* 可见错误由共享状态承载 */ }
});

onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "ar-app-page__card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VToolbar, {
          density: "comfortable",
          class: "ar-app-page__toolbar"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              rounded: "lg",
              size: "40",
              class: "ms-3 me-3"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, { icon: "mdi-brain" })
              ]),
              _: 1
            }),
            _createElementVNode("div", _hoisted_2, [
              _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-h6" }, "Agent榜单中心", -1)),
              _createElementVNode("div", _hoisted_3, "最近生成：" + _toDisplayString(formatTime(generatedAt.value)), 1)
            ]),
            (boardStatus.value !== 'success')
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  color: statusMeta.value.color,
                  variant: "tonal",
                  size: "small",
                  class: "ar-app-page__status ms-3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: statusMeta.value.icon,
                      size: "16",
                      class: "mr-1"
                    }, null, 8, ["icon"]),
                    _createTextVNode(_toDisplayString(statusMeta.value.text), 1)
                  ]),
                  _: 1
                }, 8, ["color"]))
              : _createCommentVNode("", true),
            _createVNode(_component_VSpacer),
            (_unref(users).length > 1)
              ? (_openBlock(), _createBlock(_component_VSelect, {
                  key: 1,
                  modelValue: _unref(selectedUser),
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (_isRef(selectedUser) ? (selectedUser).value = $event : null)),
                  items: _unref(users),
                  label: "用户",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "ar-app-page__user",
                  "aria-label": "切换推荐用户"
                }, null, 8, ["modelValue", "items"]))
              : _createCommentVNode("", true),
            _createVNode(_component_VBtn, {
              icon: "mdi-refresh",
              variant: "text",
              loading: _unref(loading).action === 'refresh' || _unref(loading).data,
              disabled: _unref(isRunning) || !_unref(selectedUser),
              "aria-label": "刷新榜单",
              onClick: refreshBoard
            }, null, 8, ["loading", "disabled"]),
            _createVNode(_component_VBtn, {
              icon: "mdi-cog-outline",
              variant: "text",
              "aria-label": "打开设置",
              onClick: openSettings
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        (_unref(loading).options && !initialized.value)
          ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
              _createVNode(_component_VSkeletonLoader, {
                type: "article, article, article",
                width: "100%"
              })
            ]))
          : (!_unref(users).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
                _createVNode(_component_VEmptyState, {
                  icon: "mdi-account-alert-outline",
                  title: "尚未配置参与用户",
                  text: "请先打开设置，选择参与推荐用户和默认用户。"
                }, {
                  actions: _withCtx(() => [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-cog-outline",
                      onClick: openSettings
                    }, {
                      default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                        _createTextVNode("打开设置", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]))
            : (_openBlock(), _createElementBlock("div", _hoisted_6, [
                (stateMessage.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: ['agent_failed', 'validation_failed'].includes(boardStatus.value) ? 'error' : 'warning',
                      variant: "tonal",
                      class: "ar-app-page__alert"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(stateMessage.value), 1)
                      ]),
                      _: 1
                    }, 8, ["type"]))
                  : _createCommentVNode("", true),
                _createElementVNode("main", _hoisted_7, [
                  _createElementVNode("section", _hoisted_8, [
                    _createElementVNode("div", _hoisted_9, [
                      _cache[6] || (_cache[6] = _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "text-subtitle-1 font-weight-bold" }, "个性化 Top 10"),
                        _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "保持 Agent 最终顺序，仅展示通过安全校验的候选")
                      ], -1)),
                      _createVNode(_component_VChip, {
                        size: "small",
                        variant: "outlined"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(recommendations.value.length) + " / 10", 1)
                        ]),
                        _: 1
                      })
                    ]),
                    (_unref(loading).data)
                      ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
                          key: 0,
                          type: "list-item-avatar-three-line@5"
                        }))
                      : (!recommendations.value.length)
                        ? (_openBlock(), _createBlock(_component_VEmptyState, {
                            key: 1,
                            icon: "mdi-format-list-numbered",
                            title: "推荐榜单尚未生成",
                            text: "点击刷新，Agent 将基于当前用户订阅与 MP 发现候选生成榜单。"
                          }))
                        : (_openBlock(), _createElementBlock("div", _hoisted_10, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recommendations.value, (item) => {
                              return (_openBlock(), _createElementBlock("article", {
                                key: item.candidate_id,
                                class: "ar-app-page__item"
                              }, [
                                _createElementVNode("div", {
                                  class: _normalizeClass(["ar-app-page__rank", { 'ar-app-page__rank--top': item.rank <= 3 }])
                                }, _toDisplayString(item.rank), 3),
                                _createElementVNode("div", _hoisted_11, [
                                  (posterSource(item))
                                    ? (_openBlock(), _createBlock(_component_VImg, {
                                        key: 0,
                                        src: posterSource(item),
                                        alt: `${item.title} 海报`,
                                        cover: ""
                                      }, {
                                        error: _withCtx(() => [
                                          _createElementVNode("div", _hoisted_12, [
                                            _createVNode(_component_VIcon, {
                                              icon: "mdi-image-off-outline",
                                              size: "30"
                                            })
                                          ])
                                        ]),
                                        _: 1
                                      }, 8, ["src", "alt"]))
                                    : (_openBlock(), _createBlock(_component_VIcon, {
                                        key: 1,
                                        icon: "mdi-image-off-outline",
                                        size: "30"
                                      }))
                                ]),
                                _createElementVNode("div", _hoisted_13, [
                                  _createElementVNode("div", _hoisted_14, [
                                    _createElementVNode("div", _hoisted_15, _toDisplayString(item.title), 1),
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
                                  _createElementVNode("div", _hoisted_16, _toDisplayString(item.year || '年份未知') + " · " + _toDisplayString(sourceLabel(item)), 1),
                                  _createElementVNode("div", _hoisted_17, "推荐：" + _toDisplayString(item.reason || item.summary), 1),
                                  _createElementVNode("div", _hoisted_18, "简介：" + _toDisplayString(item.summary), 1),
                                  _createElementVNode("div", _hoisted_19, [
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.match_tags || [], (tag) => {
                                      return (_openBlock(), _createBlock(_component_VChip, {
                                        key: tag,
                                        size: "x-small",
                                        variant: "outlined"
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(tag), 1)
                                        ]),
                                        _: 2
                                      }, 1024))
                                    }), 128)),
                                    _createVNode(_component_VChip, {
                                      size: "x-small",
                                      color: "primary",
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode("置信度 " + _toDisplayString(item.confidence) + "%", 1)
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ])
                                ]),
                                _createElementVNode("div", _hoisted_20, [
                                  _createVNode(RecommendationActions, {
                                    item: item,
                                    "loading-action": _unref(loading).action,
                                    size: "small",
                                    onSubscribe: subscribeItem,
                                    onArchive: archiveItem
                                  }, null, 8, ["item", "loading-action"])
                                ])
                              ]))
                            }), 128))
                          ]))
                  ])
                ])
              ]))
      ]),
      _: 1
    }),
    _createVNode(_component_VDialog, {
      modelValue: settingsDialog.value,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((settingsDialog).value = $event)),
      "max-width": "1160",
      persistent: savingSettings.value
    }, {
      default: _withCtx(() => [
        _createVNode(Config, {
          api: __props.api,
          "initial-config": _unref(options).config || {},
          onSave: saveSettings,
          onClose: _cache[1] || (_cache[1] = $event => (settingsDialog.value = false))
        }, null, 8, ["api", "initial-config"])
      ]),
      _: 1
    }, 8, ["modelValue", "persistent"]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((snackbar.value.show) = $event)),
      color: snackbar.value.color,
      timeout: "5000"
    }, _createSlots({
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(snackbar.value.message) + " ", 1)
      ]),
      _: 2
    }, [
      (snackbar.value.undo)
        ? {
            name: "actions",
            fn: _withCtx(() => [
              _createVNode(_component_VBtn, {
                variant: "text",
                onClick: undoArchive
              }, {
                default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                  _createTextVNode("撤销", -1)
                ]))]),
                _: 1
              })
            ]),
            key: "0"
          }
        : undefined
    ]), 1032, ["modelValue", "color"])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-42c87556"]]);

export { AppPage as default };
