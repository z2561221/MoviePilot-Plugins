import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState, R as RecommendationActions } from './RecommendationActions-CJIORH39.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-Z-mQLghu.js';

const {unref:_unref$4,resolveComponent:_resolveComponent$4,createVNode:_createVNode$4,createElementVNode:_createElementVNode$4,toDisplayString:_toDisplayString$4,createTextVNode:_createTextVNode$4,withCtx:_withCtx$4,openBlock:_openBlock$4,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$4,createElementBlock:_createElementBlock$3,withModifiers:_withModifiers$2,mergeProps:_mergeProps$1,renderList:_renderList$3,Fragment:_Fragment$3} = await importShared('vue');


const _hoisted_1$4 = { class: "ar-analysis__heading" };
const _hoisted_2$4 = { class: "ar-analysis__subtitle" };
const _hoisted_3$4 = {
  key: 0,
  class: "ar-analysis__state"
};
const _hoisted_4$4 = {
  key: 3,
  class: "ar-analysis__sections"
};
const _hoisted_5$3 = { class: "ar-analysis__section-head" };
const _hoisted_6$3 = { class: "ar-analysis__section-copy" };
const _hoisted_7$3 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_8$3 = ["onClick"];
const _hoisted_9$3 = { class: "ar-analysis__row-main" };
const _hoisted_10$2 = { class: "ar-analysis__row-meta" };
const _hoisted_11$2 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_12$2 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_13$1 = ["onClick"];
const _hoisted_14$1 = { class: "ar-analysis__row-main" };
const _hoisted_15$1 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_16$1 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_17$1 = ["onClick"];
const _hoisted_18$1 = { class: "ar-analysis__row-main" };
const _hoisted_19$1 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_20$1 = { class: "ar-analysis__provenance" };

const {computed: computed$4,watch: watch$4} = await importShared('vue');

const {useDisplay: useDisplay$3} = await importShared('vuetify');



const _sfc_main$4 = {
  __name: 'AgentAnalysisDialog',
  props: {
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
  item: { type: Object, default: null },
},
  emits: ['update:modelValue', 'comment'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const { smAndDown } = useDisplay$3();

const candidateId = computed$4(() => String(props.item?.candidate_id || ''));
const analysis = computed$4(() => props.state.currentAnalysis(candidateId.value));
const operation = computed$4(() => props.state.operationState(`analysis:${candidateId.value}`));

const dimensionLabels = {
  type: '类型', theme: '题材', actor: '演员', director: '主创', region: '地区',
  year: '年代', rating: '评分', heat: '热度', freshness: '新鲜感', similarity: '相似性',
};

function close() {
  emit('update:modelValue', false);
}

function evidenceText(evidence) {
  const dimension = dimensionLabels[evidence?.dimension] || evidence?.dimension || '内容特征';
  const relation = evidence?.direction === 'negative' ? '存在冲突' : '具体匹配';
  return `${dimension}：${evidence?.user_value || '偏好未注明'} 与 ${evidence?.candidate_value || '作品特征未注明'} ${relation}`
}

function requestComment(label, content) {
  emit('comment', { label, content: String(content || '').trim() });
}

async function load() {
  if (!props.modelValue || !candidateId.value || !props.item?.analysis_id) return
  try {
    await props.state.loadAnalysis(candidateId.value, props.item.analysis_id);
  } catch (_) {
    // 共享状态保存可见错误和重试动作。
  }
}

watch$4(
  () => [props.modelValue, props.item?.analysis_id],
  ([open]) => { if (open) load(); },
  { immediate: true },
);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$4("VIcon");
  const _component_VSpacer = _resolveComponent$4("VSpacer");
  const _component_VChip = _resolveComponent$4("VChip");
  const _component_VBtn = _resolveComponent$4("VBtn");
  const _component_VToolbar = _resolveComponent$4("VToolbar");
  const _component_VDivider = _resolveComponent$4("VDivider");
  const _component_VProgressCircular = _resolveComponent$4("VProgressCircular");
  const _component_VAlert = _resolveComponent$4("VAlert");
  const _component_VEmptyState = _resolveComponent$4("VEmptyState");
  const _component_VTooltip = _resolveComponent$4("VTooltip");
  const _component_VCardText = _resolveComponent$4("VCardText");
  const _component_VCard = _resolveComponent$4("VCard");
  const _component_VDialog = _resolveComponent$4("VDialog");

  return (_openBlock$4(), _createBlock$4(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$4(smAndDown),
    "max-width": "780",
    scrollable: "",
    "onUpdate:modelValue": _cache[3] || (_cache[3] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$4(() => [
      _createVNode$4(_component_VCard, { class: "ar-analysis" }, {
        default: _withCtx$4(() => [
          _createVNode$4(_component_VToolbar, {
            density: "compact",
            class: "ar-analysis__toolbar"
          }, {
            default: _withCtx$4(() => [
              _createVNode$4(_component_VIcon, {
                icon: "mdi-text-box-search-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode$4("div", _hoisted_1$4, [
                _cache[4] || (_cache[4] = _createElementVNode$4("div", { class: "ar-analysis__title" }, "Agent分析", -1)),
                _createElementVNode$4("div", _hoisted_2$4, _toDisplayString$4(__props.item?.title || '当前推荐'), 1)
              ]),
              _createVNode$4(_component_VSpacer),
              (analysis.value)
                ? (_openBlock$4(), _createBlock$4(_component_VChip, {
                    key: 0,
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    class: "me-1"
                  }, {
                    default: _withCtx$4(() => [
                      _createTextVNode$4(_toDisplayString$4(analysis.value.support_percentage) + "% ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$4("", true),
              _createVNode$4(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭 Agent 分析",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$4(_component_VDivider),
          _createVNode$4(_component_VCardText, { class: "ar-analysis__body" }, {
            default: _withCtx$4(() => [
              (operation.value.loading)
                ? (_openBlock$4(), _createElementBlock$3("div", _hoisted_3$4, [
                    _createVNode$4(_component_VProgressCircular, {
                      indeterminate: "",
                      color: "primary"
                    })
                  ]))
                : (operation.value.error)
                  ? (_openBlock$4(), _createBlock$4(_component_VAlert, {
                      key: 1,
                      type: "error",
                      variant: "tonal"
                    }, {
                      append: _withCtx$4(() => [
                        _createVNode$4(_component_VBtn, {
                          variant: "text",
                          size: "small",
                          onClick: _cache[0] || (_cache[0] = $event => (props.state.retryOperation('analysis:' + candidateId.value)))
                        }, {
                          default: _withCtx$4(() => [...(_cache[5] || (_cache[5] = [
                            _createTextVNode$4("重试", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      default: _withCtx$4(() => [
                        _createTextVNode$4(_toDisplayString$4(operation.value.error.message) + " ", 1)
                      ]),
                      _: 1
                    }))
                  : (!analysis.value)
                    ? (_openBlock$4(), _createBlock$4(_component_VEmptyState, {
                        key: 2,
                        icon: "mdi-text-box-remove-outline",
                        title: "分析暂不可用"
                      }))
                    : (_openBlock$4(), _createElementBlock$3("div", _hoisted_4$4, [
                        _createElementVNode$4("section", {
                          class: "ar-analysis__summary",
                          onClick: _cache[2] || (_cache[2] = $event => (requestComment('推荐判断', analysis.value.reason || analysis.value.summary)))
                        }, [
                          _createElementVNode$4("div", _hoisted_5$3, [
                            _createElementVNode$4("div", null, [
                              _cache[6] || (_cache[6] = _createElementVNode$4("div", { class: "ar-analysis__section-title" }, "推荐判断", -1)),
                              _createElementVNode$4("div", _hoisted_6$3, _toDisplayString$4(analysis.value.reason || analysis.value.summary), 1)
                            ]),
                            _createVNode$4(_component_VTooltip, { text: "评论这条判断" }, {
                              activator: _withCtx$4(({ props: tooltipProps }) => [
                                _createVNode$4(_component_VBtn, _mergeProps$1(tooltipProps, {
                                  icon: "mdi-comment-edit-outline",
                                  variant: "text",
                                  "aria-label": "评论推荐判断",
                                  onClick: _cache[1] || (_cache[1] = _withModifiers$2($event => (requestComment('推荐判断', analysis.value.reason || analysis.value.summary)), ["stop"]))
                                }), null, 16)
                              ]),
                              _: 1
                            })
                          ])
                        ]),
                        _createElementVNode$4("section", null, [
                          _cache[7] || (_cache[7] = _createElementVNode$4("div", { class: "ar-analysis__section-title" }, "匹配证据", -1)),
                          (analysis.value.positive_evidence?.length)
                            ? (_openBlock$4(), _createElementBlock$3("div", _hoisted_7$3, [
                                (_openBlock$4(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(analysis.value.positive_evidence, (evidence, index) => {
                                  return (_openBlock$4(), _createElementBlock$3("div", {
                                    key: `positive-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence)))
                                  }, [
                                    _createVNode$4(_component_VIcon, {
                                      icon: "mdi-check-circle-outline",
                                      color: "success",
                                      size: "20"
                                    }),
                                    _createElementVNode$4("div", _hoisted_9$3, [
                                      _createElementVNode$4("div", null, _toDisplayString$4(evidenceText(evidence)), 1),
                                      _createElementVNode$4("div", _hoisted_10$2, "贡献 " + _toDisplayString$4(evidence.contribution_units) + " · 证据 " + _toDisplayString$4(evidence.user_refs?.length || 0) + " 项", 1)
                                    ]),
                                    _createVNode$4(_component_VTooltip, { text: "评论这条证据" }, {
                                      activator: _withCtx$4(({ props: tooltipProps }) => [
                                        _createVNode$4(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论匹配证据 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence))), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_8$3))
                                }), 128))
                              ]))
                            : (_openBlock$4(), _createElementBlock$3("div", _hoisted_11$2, "没有足够的正向具体证据。"))
                        ]),
                        _createElementVNode$4("section", null, [
                          _cache[8] || (_cache[8] = _createElementVNode$4("div", { class: "ar-analysis__section-title" }, "反向证据", -1)),
                          (analysis.value.counter_evidence?.length)
                            ? (_openBlock$4(), _createElementBlock$3("div", _hoisted_12$2, [
                                (_openBlock$4(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(analysis.value.counter_evidence, (evidence, index) => {
                                  return (_openBlock$4(), _createElementBlock$3("div", {
                                    key: `counter-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`反向证据 ${index + 1}`, evidenceText(evidence)))
                                  }, [
                                    _createVNode$4(_component_VIcon, {
                                      icon: "mdi-alert-circle-outline",
                                      color: "warning",
                                      size: "20"
                                    }),
                                    _createElementVNode$4("div", _hoisted_14$1, _toDisplayString$4(evidenceText(evidence)), 1),
                                    _createVNode$4(_component_VTooltip, { text: "评论这条证据" }, {
                                      activator: _withCtx$4(({ props: tooltipProps }) => [
                                        _createVNode$4(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论反向证据 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`反向证据 ${index + 1}`, evidenceText(evidence))), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_13$1))
                                }), 128))
                              ]))
                            : (_openBlock$4(), _createElementBlock$3("div", _hoisted_15$1, "未发现需要特别提示的反向证据。"))
                        ]),
                        _createElementVNode$4("section", null, [
                          _cache[9] || (_cache[9] = _createElementVNode$4("div", { class: "ar-analysis__section-title" }, "不确定点", -1)),
                          (analysis.value.uncertainties?.length)
                            ? (_openBlock$4(), _createElementBlock$3("div", _hoisted_16$1, [
                                (_openBlock$4(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(analysis.value.uncertainties, (uncertainty, index) => {
                                  return (_openBlock$4(), _createElementBlock$3("div", {
                                    key: `uncertainty-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`不确定点 ${index + 1}`, uncertainty))
                                  }, [
                                    _createVNode$4(_component_VIcon, {
                                      icon: "mdi-help-circle-outline",
                                      color: "info",
                                      size: "20"
                                    }),
                                    _createElementVNode$4("div", _hoisted_18$1, _toDisplayString$4(uncertainty), 1),
                                    _createVNode$4(_component_VTooltip, { text: "评论这条判断" }, {
                                      activator: _withCtx$4(({ props: tooltipProps }) => [
                                        _createVNode$4(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论不确定点 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`不确定点 ${index + 1}`, uncertainty)), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_17$1))
                                }), 128))
                              ]))
                            : (_openBlock$4(), _createElementBlock$3("div", _hoisted_19$1, "当前没有额外不确定点。"))
                        ]),
                        _createElementVNode$4("div", _hoisted_20$1, [
                          _createElementVNode$4("span", null, "选择：" + _toDisplayString$4(analysis.value.selection_source === 'agent' ? 'Agent排序' : '安全候选补位'), 1),
                          _createElementVNode$4("span", null, "策略：" + _toDisplayString$4(analysis.value.policy_version), 1),
                          _createElementVNode$4("span", null, "记忆版本：" + _toDisplayString$4(analysis.value.memory_revision), 1)
                        ])
                      ]))
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const AgentAnalysisDialog = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-24c1291e"]]);

const {unref:_unref$3,resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,withCtx:_withCtx$3,createElementVNode:_createElementVNode$3,toDisplayString:_toDisplayString$3,openBlock:_openBlock$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3,createTextVNode:_createTextVNode$3,createElementBlock:_createElementBlock$2,renderList:_renderList$2,Fragment:_Fragment$2,normalizeClass:_normalizeClass$1,withModifiers:_withModifiers$1,withKeys:_withKeys$2} = await importShared('vue');


const _hoisted_1$3 = { class: "ar-chat__subtitle" };
const _hoisted_2$3 = {
  key: 1,
  class: "ar-chat__empty"
};
const _hoisted_3$3 = { class: "ar-chat__content" };
const _hoisted_4$3 = { class: "ar-chat__meta" };
const _hoisted_5$2 = { key: 0 };
const _hoisted_6$2 = { key: 1 };
const _hoisted_7$2 = { key: 2 };
const _hoisted_8$2 = {
  key: 0,
  class: "ar-chat__failure"
};
const _hoisted_9$2 = {
  key: 2,
  class: "ar-chat__commands"
};
const _hoisted_10$1 = { class: "ar-chat__command-main" };
const _hoisted_11$1 = { class: "ar-chat__command-actions" };
const _hoisted_12$1 = { class: "ar-chat__composer" };

const {computed: computed$3,nextTick,onUnmounted,ref: ref$3,watch: watch$3} = await importShared('vue');

const {useDisplay: useDisplay$2} = await importShared('vuetify');


const frontendTimeoutMs = 100000;


const _sfc_main$3 = {
  __name: 'CriticChatDialog',
  props: {
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
},
  emits: ['update:modelValue', 'pending-change'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const { smAndDown } = useDisplay$2();
const draft = ref$3('');
const localError = ref$3('');
const messageList = ref$3(null);
const pollTimer = ref$3(null);
const pollDeadline = ref$3(0);
const messages = computed$3(() => props.state.conversation.value?.messages || []);
const commands = computed$3(() => props.state.conversation.value?.commands || []);
const pendingCommands = computed$3(() => commands.value.filter(item => item.status === 'pending_confirmation'));
const conversationOperation = computed$3(() => props.state.operationState('conversation'));
const sendOperation = computed$3(() => props.state.operationState('conversation:send'));
const canSend = computed$3(() => draft.value.trim().length > 0 && !sendOperation.value.loading);
const hasPendingMessages = computed$3(() => messages.value.some(item => ['queued', 'processing'].includes(item.status)));

function stopPolling() {
  if (pollTimer.value) clearTimeout(pollTimer.value);
  pollTimer.value = null;
  pollDeadline.value = 0;
}

function markFrontendTimeout() {
  const current = props.state.conversation.value || {};
  props.state.conversation.value = {
    ...current,
    messages: (current.messages || []).map(message => (
      ['queued', 'processing'].includes(message.status)
        ? {
            ...message,
            status: 'retryable_failed',
            error_code: 'frontend_timeout',
            error_message: 'CinePilot Agent 响应超时，消息已保留，可重试',
          }
        : message
    )),
  };
}

async function pollConversation() {
  if (!props.modelValue || !hasPendingMessages.value) {
    stopPolling();
    return
  }
  if (Date.now() >= pollDeadline.value) {
    markFrontendTimeout();
    stopPolling();
    return
  }
  try { await props.state.loadConversation(); } catch (_) { /* 保留共享可重试错误。 */ }
  if (!hasPendingMessages.value) {
    stopPolling();
    await scrollToEnd();
    return
  }
  pollTimer.value = setTimeout(pollConversation, 1500);
}

function startPolling() {
  stopPolling();
  if (!hasPendingMessages.value || !props.modelValue) return
  pollDeadline.value = Date.now() + frontendTimeoutMs;
  pollTimer.value = setTimeout(pollConversation, 500);
}

function close() {
  emit('update:modelValue', false);
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}

async function scrollToEnd() {
  await nextTick();
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight;
}

async function load() {
  try {
    await Promise.all([props.state.loadConversation(), props.state.loadPendingCenter()]);
    await scrollToEnd();
    startPolling();
  } catch (_) {
    // 共享状态保存可见错误和重试动作。
  }
}

async function send() {
  const value = draft.value.trim();
  if (!value) return
  localError.value = '';
  try {
    await props.state.sendConversationMessage(value);
    draft.value = '';
    emit('pending-change');
    await scrollToEnd();
    startPolling();
  } catch (error) {
    localError.value = error?.message || '消息发送失败，草稿已保留';
    try { await props.state.loadConversation(); } catch (_) { /* 对话读取错误由共享状态展示。 */ }
    await scrollToEnd();
  }
}

async function retryMessage(messageId) {
  localError.value = '';
  try {
    await props.state.retryConversationMessage(messageId);
    emit('pending-change');
    await scrollToEnd();
    startPolling();
  } catch (error) {
    localError.value = error?.message || '重试失败';
    try { await props.state.loadConversation(); } catch (_) { /* 对话读取错误由共享状态展示。 */ }
  }
}

async function respondCommand(command, action) {
  localError.value = '';
  try {
    await props.state.respondConversationCommand(command.command_id, action);
    emit('pending-change');
  } catch (error) {
    localError.value = error?.message || '待执行操作失败';
  }
}

watch$3(() => props.modelValue, open => { if (open) load(); else stopPolling(); }, { immediate: true });
watch$3(() => messages.value.length, () => { if (props.modelValue) scrollToEnd(); });
onUnmounted(stopPolling);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VAvatar = _resolveComponent$3("VAvatar");
  const _component_VSpacer = _resolveComponent$3("VSpacer");
  const _component_VBadge = _resolveComponent$3("VBadge");
  const _component_VBtn = _resolveComponent$3("VBtn");
  const _component_VToolbar = _resolveComponent$3("VToolbar");
  const _component_VDivider = _resolveComponent$3("VDivider");
  const _component_VAlert = _resolveComponent$3("VAlert");
  const _component_VTextarea = _resolveComponent$3("VTextarea");
  const _component_VCard = _resolveComponent$3("VCard");
  const _component_VDialog = _resolveComponent$3("VDialog");

  return (_openBlock$3(), _createBlock$3(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$3(smAndDown),
    "max-width": "820",
    scrollable: "",
    "onUpdate:modelValue": _cache[2] || (_cache[2] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$3(() => [
      _createVNode$3(_component_VCard, { class: "ar-chat" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VToolbar, {
            density: "compact",
            class: "ar-chat__toolbar"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VAvatar, {
                color: "primary",
                variant: "tonal",
                size: "34",
                class: "ms-3 me-3"
              }, {
                default: _withCtx$3(() => [
                  _createVNode$3(_component_VIcon, { icon: "mdi-forum-outline" })
                ]),
                _: 1
              }),
              _createElementVNode$3("div", null, [
                _cache[3] || (_cache[3] = _createElementVNode$3("div", { class: "ar-chat__title" }, "CinePilot Agent", -1)),
                _createElementVNode$3("div", _hoisted_1$3, _toDisplayString$3(props.state.selectedUsername.value || '当前画像'), 1)
              ]),
              _createVNode$3(_component_VSpacer),
              (pendingCommands.value.length)
                ? (_openBlock$3(), _createBlock$3(_component_VBadge, {
                    key: 0,
                    content: pendingCommands.value.length,
                    color: "warning",
                    inline: ""
                  }, {
                    default: _withCtx$3(() => [
                      _createVNode$3(_component_VIcon, {
                        icon: "mdi-inbox-outline",
                        size: "20"
                      })
                    ]),
                    _: 1
                  }, 8, ["content"]))
                : _createCommentVNode$3("", true),
              _createVNode$3(_component_VBtn, {
                icon: "mdi-refresh",
                variant: "text",
                "aria-label": "刷新 CinePilot Agent 对话",
                loading: conversationOperation.value.loading,
                onClick: load
              }, null, 8, ["loading"]),
              _createVNode$3(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭 CinePilot Agent 对话",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$3(_component_VDivider),
          _createElementVNode$3("div", {
            ref_key: "messageList",
            ref: messageList,
            class: "ar-chat__messages"
          }, [
            (conversationOperation.value.error)
              ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
                  key: 0,
                  type: "error",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  append: _withCtx$3(() => [
                    _createVNode$3(_component_VBtn, {
                      variant: "text",
                      size: "small",
                      onClick: _cache[0] || (_cache[0] = $event => (props.state.retryOperation('conversation')))
                    }, {
                      default: _withCtx$3(() => [...(_cache[4] || (_cache[4] = [
                        _createTextVNode$3("重试", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  default: _withCtx$3(() => [
                    _createTextVNode$3(_toDisplayString$3(conversationOperation.value.error.message) + " ", 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode$3("", true),
            (!messages.value.length && !conversationOperation.value.loading)
              ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_2$3, [
                  _createVNode$3(_component_VIcon, {
                    icon: "mdi-forum-outline",
                    size: "34",
                    color: "primary"
                  }),
                  _cache[5] || (_cache[5] = _createElementVNode$3("span", null, "还没有对话记录", -1))
                ]))
              : _createCommentVNode$3("", true),
            (_openBlock$3(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(messages.value, (message) => {
              return (_openBlock$3(), _createElementBlock$2("div", {
                key: message.message_id,
                class: _normalizeClass$1(["ar-chat__message", `ar-chat__message--${message.role}`])
              }, [
                _createElementVNode$3("div", {
                  class: _normalizeClass$1(["ar-chat__bubble", { 'ar-chat__bubble--failed': ['failed', 'retryable_failed'].includes(message.status) }])
                }, [
                  _createElementVNode$3("div", _hoisted_3$3, _toDisplayString$3(message.content), 1),
                  _createElementVNode$3("div", _hoisted_4$3, [
                    _createElementVNode$3("span", null, _toDisplayString$3(formatTime(message.created_at)), 1),
                    (message.role === 'assistant' && (message.provider || message.model))
                      ? (_openBlock$3(), _createElementBlock$2("span", _hoisted_5$2, _toDisplayString$3([message.provider, message.model].filter(Boolean).join(' · ')), 1))
                      : _createCommentVNode$3("", true),
                    (message.role === 'user' && message.status === 'queued')
                      ? (_openBlock$3(), _createElementBlock$2("span", _hoisted_6$2, "已受理"))
                      : (message.role === 'user' && message.status === 'processing')
                        ? (_openBlock$3(), _createElementBlock$2("span", _hoisted_7$2, "处理中"))
                        : _createCommentVNode$3("", true)
                  ]),
                  (['failed', 'retryable_failed'].includes(message.status))
                    ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_8$2, [
                        _createElementVNode$3("span", null, _toDisplayString$3(message.error_message || '消息处理失败'), 1),
                        _createVNode$3(_component_VBtn, {
                          size: "x-small",
                          variant: "text",
                          "prepend-icon": "mdi-refresh",
                          onClick: $event => (retryMessage(message.message_id))
                        }, {
                          default: _withCtx$3(() => [...(_cache[6] || (_cache[6] = [
                            _createTextVNode$3("重试", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    : _createCommentVNode$3("", true)
                ], 2)
              ], 2))
            }), 128)),
            (pendingCommands.value.length)
              ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_9$2, [
                  _cache[9] || (_cache[9] = _createElementVNode$3("div", { class: "ar-chat__commands-title" }, "待执行操作", -1)),
                  (_openBlock$3(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(pendingCommands.value, (command) => {
                    return (_openBlock$3(), _createElementBlock$2("div", {
                      key: command.command_id,
                      class: "ar-chat__command"
                    }, [
                      _createElementVNode$3("div", _hoisted_10$1, [
                        _createElementVNode$3("strong", null, _toDisplayString$3(command.title), 1),
                        _createElementVNode$3("span", null, _toDisplayString$3(command.preview), 1)
                      ]),
                      _createElementVNode$3("div", _hoisted_11$1, [
                        _createVNode$3(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          onClick: $event => (respondCommand(command, 'reject'))
                        }, {
                          default: _withCtx$3(() => [...(_cache[7] || (_cache[7] = [
                            _createTextVNode$3("拒绝执行", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"]),
                        _createVNode$3(_component_VBtn, {
                          size: "small",
                          color: "primary",
                          variant: "tonal",
                          disabled: command.requires_superuser,
                          onClick: $event => (respondCommand(command, 'confirm'))
                        }, {
                          default: _withCtx$3(() => [...(_cache[8] || (_cache[8] = [
                            _createTextVNode$3("确认执行", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled", "onClick"])
                      ])
                    ]))
                  }), 128))
                ]))
              : _createCommentVNode$3("", true)
          ], 512),
          _createVNode$3(_component_VDivider),
          _createElementVNode$3("div", _hoisted_12$1, [
            _createVNode$3(_component_VTextarea, {
              modelValue: draft.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((draft).value = $event)),
              label: "给 CinePilot Agent 留言",
              density: "compact",
              variant: "outlined",
              rows: "2",
              "auto-grow": "",
              "max-rows": "5",
              maxlength: "1000",
              "hide-details": "",
              onKeydown: _withKeys$2(_withModifiers$1(send, ["exact","prevent"]), ["enter"])
            }, null, 8, ["modelValue", "onKeydown"]),
            _createVNode$3(_component_VBtn, {
              icon: "mdi-send",
              color: "primary",
              variant: "flat",
              "aria-label": "发送消息",
              loading: sendOperation.value.loading,
              disabled: !canSend.value,
              onClick: send
            }, null, 8, ["loading", "disabled"])
          ]),
          (localError.value || sendOperation.value.error)
            ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
                key: 0,
                type: "error",
                variant: "tonal",
                density: "compact",
                class: "ar-chat__composer-error"
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(_toDisplayString$3(localError.value || sendOperation.value.error?.message), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$3("", true)
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const CriticChatDialog = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-c43dd21a"]]);

const {unref:_unref$2,resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2,withCtx:_withCtx$2,withModifiers:_withModifiers,withKeys:_withKeys$1,createTextVNode:_createTextVNode$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2} = await importShared('vue');


const _hoisted_1$2 = { class: "ar-comment__heading" };
const _hoisted_2$2 = { class: "ar-comment__subtitle" };
const _hoisted_3$2 = { class: "ar-comment__label" };
const _hoisted_4$2 = { class: "ar-comment__judgment" };

const {computed: computed$2,ref: ref$2,watch: watch$2} = await importShared('vue');

const {useDisplay: useDisplay$1} = await importShared('vuetify');



const _sfc_main$2 = {
  __name: 'FeedbackCommentDialog',
  props: {
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
  item: { type: Object, default: null },
  judgment: { type: Object, default: null },
},
  emits: ['update:modelValue', 'submitted'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const { smAndDown } = useDisplay$1();
const comment = ref$2('');
const localError = ref$2('');

const candidateId = computed$2(() => String(props.item?.candidate_id || ''));
const operation = computed$2(() => props.state.operationState(`analysis-comment:${candidateId.value}`));
const canSubmit = computed$2(() => comment.value.trim().length >= 2 && !operation.value.loading);

watch$2(
  () => [props.modelValue, props.judgment?.label, props.item?.candidate_id],
  ([open]) => {
    if (!open) return
    comment.value = '';
    localError.value = '';
    props.state.clearOperationError(`analysis-comment:${candidateId.value}`);
  },
);

function close() {
  emit('update:modelValue', false);
}

async function submit() {
  const value = comment.value.trim();
  if (value.length < 2) {
    localError.value = '请写下需要纠正的具体内容';
    return
  }
  const label = String(props.judgment?.label || 'Agent判断');
  try {
    const result = await props.state.commentOnAnalysis(candidateId.value, `【${label}】${value}`);
    emit('submitted', result);
    close();
  } catch (error) {
    localError.value = error?.message || '评论提交失败';
  }
}

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VToolbar = _resolveComponent$2("VToolbar");
  const _component_VDivider = _resolveComponent$2("VDivider");
  const _component_VTextarea = _resolveComponent$2("VTextarea");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VCardText = _resolveComponent$2("VCardText");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createBlock$2(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$2(smAndDown),
    "max-width": "620",
    "onUpdate:modelValue": _cache[1] || (_cache[1] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$2(() => [
      _createVNode$2(_component_VCard, { class: "ar-comment" }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_VToolbar, {
            density: "compact",
            class: "ar-comment__toolbar"
          }, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_VIcon, {
                icon: "mdi-comment-edit-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode$2("div", _hoisted_1$2, [
                _cache[2] || (_cache[2] = _createElementVNode$2("div", { class: "ar-comment__title" }, "评论 Agent 判断", -1)),
                _createElementVNode$2("div", _hoisted_2$2, _toDisplayString$2(__props.item?.title || '当前推荐'), 1)
              ]),
              _createVNode$2(_component_VSpacer),
              _createVNode$2(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭评论窗口",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$2(_component_VDivider),
          _createVNode$2(_component_VCardText, { class: "ar-comment__body" }, {
            default: _withCtx$2(() => [
              _createElementVNode$2("div", _hoisted_3$2, _toDisplayString$2(__props.judgment?.label || 'Agent判断'), 1),
              _createElementVNode$2("div", _hoisted_4$2, _toDisplayString$2(__props.judgment?.content || '当前判断内容未返回'), 1),
              _createVNode$2(_component_VTextarea, {
                modelValue: comment.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((comment).value = $event)),
                label: "你的评论",
                placeholder: "指出哪里不准确，并写下你真实的偏好或原因",
                density: "compact",
                variant: "outlined",
                rows: "4",
                "auto-grow": "",
                maxlength: "1000",
                counter: "",
                class: "mt-4",
                onKeydown: _withKeys$1(_withModifiers(submit, ["ctrl","prevent"]), ["enter"])
              }, null, 8, ["modelValue", "onKeydown"]),
              (localError.value || operation.value.error)
                ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                    key: 0,
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    class: "mt-2"
                  }, {
                    default: _withCtx$2(() => [
                      _createTextVNode$2(_toDisplayString$2(localError.value || operation.value.error?.message), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$2("", true)
            ]),
            _: 1
          }),
          _createVNode$2(_component_VDivider),
          _createVNode$2(_component_VCardActions, { class: "ar-comment__actions" }, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_VSpacer),
              _createVNode$2(_component_VBtn, {
                variant: "text",
                onClick: close
              }, {
                default: _withCtx$2(() => [...(_cache[3] || (_cache[3] = [
                  _createTextVNode$2("取消", -1)
                ]))]),
                _: 1
              }),
              _createVNode$2(_component_VBtn, {
                color: "primary",
                variant: "flat",
                "prepend-icon": "mdi-send-outline",
                loading: operation.value.loading,
                disabled: !canSubmit.value,
                onClick: submit
              }, {
                default: _withCtx$2(() => [...(_cache[4] || (_cache[4] = [
                  _createTextVNode$2("提交评论", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const FeedbackCommentDialog = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-ad9ce515"]]);

const {unref:_unref$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString$1,withCtx:_withCtx$1,createTextVNode:_createTextVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createElementBlock:_createElementBlock$1,renderList:_renderList$1,Fragment:_Fragment$1} = await importShared('vue');


const _hoisted_1$1 = { class: "ar-pending__subtitle" };
const _hoisted_2$1 = {
  key: 1,
  class: "ar-pending__state"
};
const _hoisted_3$1 = {
  key: 3,
  class: "ar-pending__list"
};
const _hoisted_4$1 = { class: "ar-pending__item-head" };
const _hoisted_5$1 = { class: "ar-pending__item-title" };
const _hoisted_6$1 = { class: "ar-pending__summary" };
const _hoisted_7$1 = {
  key: 0,
  class: "ar-pending__details"
};
const _hoisted_8$1 = {
  key: 1,
  class: "ar-pending__answer"
};
const _hoisted_9$1 = { class: "ar-pending__actions" };

const {computed: computed$1,reactive: reactive$1,ref: ref$1,watch: watch$1} = await importShared('vue');

const {useDisplay} = await importShared('vuetify');



const _sfc_main$1 = {
  __name: 'PendingConfirmations',
  props: {
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
},
  emits: ['update:modelValue', 'changed'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const { smAndDown } = useDisplay();
const answers = reactive$1({});
const localError = ref$1('');

const items = computed$1(() => props.state.pendingCenter.value?.items || []);
const operation = computed$1(() => props.state.operationState('pending'));
const typeLabels = { proposal: '偏好提案', question: '偏好问询', command: '执行确认' };

function close() {
  emit('update:modelValue', false);
}

function answerState(item) {
  if (!answers[item.item_id]) answers[item.item_id] = { optionId: '', customAnswer: '' };
  return answers[item.item_id]
}

function itemOperation(item) {
  return props.state.operationState(`pending:${item.item_type}:${item.item_id}`)
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}

async function load() {
  localError.value = '';
  try { await props.state.loadPendingCenter(); }
  catch (error) { localError.value = error?.message || '待处理项目读取失败'; }
}

async function respond(item, action, options = {}) {
  localError.value = '';
  try {
    await props.state.respondPending(item, action, options);
    emit('changed');
  } catch (error) {
    localError.value = error?.message || '待处理操作失败';
  }
}

function answerQuestion(item) {
  const answer = answerState(item);
  const customAnswer = answer.customAnswer.trim();
  if (!answer.optionId && !customAnswer) {
    localError.value = '请选择一个答案或填写自定义回答';
    return
  }
  respond(item, 'answer', { optionId: customAnswer ? '' : answer.optionId, customAnswer });
}

watch$1(() => props.modelValue, open => { if (open) load(); }, { immediate: true });

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VToolbar = _resolveComponent$1("VToolbar");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VProgressCircular = _resolveComponent$1("VProgressCircular");
  const _component_VEmptyState = _resolveComponent$1("VEmptyState");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VRadio = _resolveComponent$1("VRadio");
  const _component_VRadioGroup = _resolveComponent$1("VRadioGroup");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$1(smAndDown),
    "max-width": "820",
    scrollable: "",
    "onUpdate:modelValue": _cache[0] || (_cache[0] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCard, { class: "ar-pending" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VToolbar, {
            density: "compact",
            class: "ar-pending__toolbar"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VIcon, {
                icon: "mdi-inbox-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode$1("div", null, [
                _cache[1] || (_cache[1] = _createElementVNode$1("div", { class: "ar-pending__title" }, "待处理", -1)),
                _createElementVNode$1("div", _hoisted_1$1, _toDisplayString$1(items.value.length) + " 项待处理", 1)
              ]),
              _createVNode$1(_component_VSpacer),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-refresh",
                variant: "text",
                "aria-label": "刷新待处理项目",
                loading: operation.value.loading,
                onClick: load
              }, null, 8, ["loading"]),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭待处理窗口",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardText, { class: "ar-pending__body" }, {
            default: _withCtx$1(() => [
              (localError.value || operation.value.error)
                ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                    key: 0,
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    class: "mb-3"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(localError.value || operation.value.error?.message), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true),
              (operation.value.loading && !items.value.length)
                ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, [
                    _createVNode$1(_component_VProgressCircular, {
                      indeterminate: "",
                      color: "primary"
                    })
                  ]))
                : (!items.value.length)
                  ? (_openBlock$1(), _createBlock$1(_component_VEmptyState, {
                      key: 2,
                      icon: "mdi-check-all",
                      title: "当前没有待处理项目"
                    }))
                  : (_openBlock$1(), _createElementBlock$1("div", _hoisted_3$1, [
                      (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(items.value, (item) => {
                        return (_openBlock$1(), _createElementBlock$1("section", {
                          key: `${item.item_type}:${item.item_id}`,
                          class: "ar-pending__item"
                        }, [
                          _createElementVNode$1("div", _hoisted_4$1, [
                            _createVNode$1(_component_VChip, {
                              size: "x-small",
                              color: "primary",
                              variant: "tonal"
                            }, {
                              default: _withCtx$1(() => [
                                _createTextVNode$1(_toDisplayString$1(typeLabels[item.item_type] || '待处理'), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode$1("span", null, _toDisplayString$1(formatTime(item.created_at)), 1),
                            _createVNode$1(_component_VSpacer)
                          ]),
                          _createElementVNode$1("div", _hoisted_5$1, _toDisplayString$1(item.title), 1),
                          _createElementVNode$1("div", _hoisted_6$1, _toDisplayString$1(item.summary), 1),
                          (item.detail_lines?.length)
                            ? (_openBlock$1(), _createElementBlock$1("ul", _hoisted_7$1, [
                                (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(item.detail_lines, (line) => {
                                  return (_openBlock$1(), _createElementBlock$1("li", { key: line }, _toDisplayString$1(line), 1))
                                }), 128))
                              ]))
                            : _createCommentVNode$1("", true),
                          (item.item_type === 'question')
                            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_8$1, [
                                _createVNode$1(_component_VRadioGroup, {
                                  modelValue: answerState(item).optionId,
                                  "onUpdate:modelValue": $event => ((answerState(item).optionId) = $event),
                                  density: "compact",
                                  "hide-details": ""
                                }, {
                                  default: _withCtx$1(() => [
                                    (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(item.options || [], (option) => {
                                      return (_openBlock$1(), _createBlock$1(_component_VRadio, {
                                        key: option.option_id,
                                        label: option.label,
                                        value: option.option_id
                                      }, null, 8, ["label", "value"]))
                                    }), 128))
                                  ]),
                                  _: 2
                                }, 1032, ["modelValue", "onUpdate:modelValue"]),
                                (item.allow_custom_answer)
                                  ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                                      key: 0,
                                      modelValue: answerState(item).customAnswer,
                                      "onUpdate:modelValue": $event => ((answerState(item).customAnswer) = $event),
                                      label: "自定义回答",
                                      density: "compact",
                                      variant: "outlined",
                                      "hide-details": "",
                                      maxlength: "1000",
                                      class: "mt-2"
                                    }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                                  : _createCommentVNode$1("", true)
                              ]))
                            : _createCommentVNode$1("", true),
                          _createElementVNode$1("div", _hoisted_9$1, [
                            (item.item_type === 'question')
                              ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                                  key: 0,
                                  size: "small",
                                  variant: "text",
                                  onClick: $event => (respond(item, 'close'))
                                }, {
                                  default: _withCtx$1(() => [...(_cache[2] || (_cache[2] = [
                                    _createTextVNode$1("关闭问询", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick"]))
                              : (_openBlock$1(), _createBlock$1(_component_VBtn, {
                                  key: 1,
                                  size: "small",
                                  variant: "text",
                                  color: "error",
                                  onClick: $event => (respond(item, 'reject'))
                                }, {
                                  default: _withCtx$1(() => [
                                    _createTextVNode$1(_toDisplayString$1(item.item_type === 'proposal' ? '拒绝采纳' : '拒绝执行'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["onClick"])),
                            (item.item_type === 'question')
                              ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                                  key: 2,
                                  size: "small",
                                  color: "primary",
                                  variant: "tonal",
                                  loading: itemOperation(item).loading,
                                  onClick: $event => (answerQuestion(item))
                                }, {
                                  default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                                    _createTextVNode$1("提交回答", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"]))
                              : (_openBlock$1(), _createBlock$1(_component_VBtn, {
                                  key: 3,
                                  size: "small",
                                  color: "primary",
                                  variant: "tonal",
                                  loading: itemOperation(item).loading,
                                  disabled: item.requires_superuser,
                                  onClick: $event => (respond(item, 'confirm'))
                                }, {
                                  default: _withCtx$1(() => [
                                    _createTextVNode$1(_toDisplayString$1(item.item_type === 'proposal' ? '确认采纳' : '确认执行'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["loading", "disabled", "onClick"]))
                          ])
                        ]))
                      }), 128))
                    ]))
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const PendingConfirmations = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-bf0cdd89"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,mergeProps:_mergeProps,vShow:_vShow,withDirectives:_withDirectives,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1 = { class: "ar-page" };
const _hoisted_2 = { class: "ar-page__summary-bar" };
const _hoisted_3 = { class: "ar-page__stat-value" };
const _hoisted_4 = { class: "ar-page__stat-label" };
const _hoisted_5 = {
  class: "ar-page__tabs",
  "aria-label": "详情视图"
};
const _hoisted_6 = { class: "ar-page__content" };
const _hoisted_7 = { class: "ar-page__pane" };
const _hoisted_8 = { class: "ar-page__section-head" };
const _hoisted_9 = {
  key: 1,
  class: "ar-page__ranking"
};
const _hoisted_10 = { class: "ar-page__poster" };
const _hoisted_11 = { class: "ar-page__poster-error" };
const _hoisted_12 = { class: "ar-page__rank-main" };
const _hoisted_13 = { class: "ar-page__title-row" };
const _hoisted_14 = { class: "ar-page__media-title" };
const _hoisted_15 = { class: "ar-page__meta-row" };
const _hoisted_16 = { class: "ar-page__rank-copy" };
const _hoisted_17 = { class: "ar-page__copy-text ar-page__copy-text--reason" };
const _hoisted_18 = { class: "ar-page__rank-copy ar-page__rank-copy--muted" };
const _hoisted_19 = { class: "ar-page__copy-text ar-page__copy-text--intro" };
const _hoisted_20 = {
  key: 0,
  class: "ar-page__match-tags"
};
const _hoisted_21 = { class: "ar-page__rank-actions" };
const _hoisted_22 = { class: "ar-page__pane" };
const _hoisted_23 = { class: "ar-page__section-head" };
const _hoisted_24 = { class: "ar-page__profile-summary-panel" };
const _hoisted_25 = { class: "ar-page__profile-label" };
const _hoisted_26 = { class: "ar-page__profile-summary" };
const _hoisted_27 = { class: "ar-page__profile-metrics" };
const _hoisted_28 = { class: "ar-page__profile-groups" };
const _hoisted_29 = { class: "ar-page__profile-group" };
const _hoisted_30 = { class: "ar-page__profile-label" };
const _hoisted_31 = { class: "ar-page__chips" };
const _hoisted_32 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_33 = { class: "ar-page__tag-editor" };
const _hoisted_34 = { class: "ar-page__profile-group" };
const _hoisted_35 = { class: "ar-page__profile-label ar-page__profile-label--negative" };
const _hoisted_36 = { class: "ar-page__chips" };
const _hoisted_37 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_38 = { class: "ar-page__tag-editor" };
const _hoisted_39 = { class: "ar-page__profile-group" };
const _hoisted_40 = { class: "ar-page__profile-label" };
const _hoisted_41 = { class: "ar-page__chips" };
const _hoisted_42 = {
  key: 0,
  class: "ar-page__tag-count"
};
const _hoisted_43 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_44 = { class: "ar-page__profile-group ar-page__profile-group--archived" };
const _hoisted_45 = { class: "ar-page__profile-label ar-page__profile-label--archived" };
const _hoisted_46 = { class: "ar-page__chips" };
const _hoisted_47 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_48 = { class: "ar-page__pane" };
const _hoisted_49 = { class: "ar-page__section-head" };
const _hoisted_50 = {
  key: 1,
  class: "ar-page__archive-list"
};
const _hoisted_51 = { class: "ar-page__archive-rank" };
const _hoisted_52 = { class: "ar-page__pane" };
const _hoisted_53 = { class: "ar-page__section-head" };
const _hoisted_54 = { class: "ar-page__history-list" };
const _hoisted_55 = { class: "ar-page__history-head" };
const _hoisted_56 = { class: "ar-page__history-time" };
const _hoisted_57 = { key: 0 };
const _hoisted_58 = { class: "ar-page__history-message" };
const _hoisted_59 = { class: "ar-page__history-metrics" };
const _hoisted_60 = { class: "ar-page__history-model" };
const _hoisted_61 = {
  key: 0,
  class: "ar-page__history-pipeline"
};
const _hoisted_62 = { class: "ar-page__history-footer" };
const _hoisted_63 = {
  key: 1,
  class: "ar-page__history-details"
};
const _hoisted_64 = {
  key: 0,
  class: "ar-page__history-call-row"
};
const _hoisted_65 = { class: "ar-page__history-agent-calls" };
const _hoisted_66 = { class: "ar-page__history-agent-head" };
const _hoisted_67 = {
  key: 0,
  class: "ar-page__history-agent-error"
};

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');

const historyPageSize = 10;


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  showClose: { type: Boolean, default: true },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const state = useAgentRankState(props.api);

const activeTab = ref('board');
const snackbar = ref({ show: false, message: '', color: 'success' });
const historyPage = ref(1);
const initialized = ref(false);
const expandedHistoryKeys = ref(new Set());
const tagDrafts = reactive({ positive: '', negative: '' });
const analysisDialog = ref(false);
const commentDialog = ref(false);
const criticDialog = ref(false);
const pendingDialog = ref(false);
const selectedAnalysisItem = ref(null);
const selectedJudgment = ref(null);
const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 5) || []);
const archiveEntries = computed(() => state.overview.value?.archive?.entries || []);
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)));
const positiveTags = computed(() => state.profile.value?.tags || []);
const negativeTags = computed(() => state.profile.value?.negative_tags || []);
const archivedProfileTags = computed(() => state.profile.value?.archived_profile_tags || []);
const profileStats = computed(() => [
  { label: '播放样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-database-check-outline' },
  { label: '偏好标签', value: positiveTags.value.length, suffix: '个', icon: 'mdi-heart-outline' },
  { label: '避雷标签', value: negativeTags.value.length, suffix: '个', icon: 'mdi-shield-alert-outline' },
]);
const boardMatchTags = computed(() => {
  const counts = new Map();
  recommendations.value.forEach(item => {
    const tags = item.match_tags || [];
    tags.forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
    .slice(0, 10)
    .map(([tag, count]) => ({ tag, count }))
});
const profileRunId = computed(() => String(state.profile.value?.run_id || '').slice(0, 8) || '—');
const detailStats = computed(() => [
  { label: '榜单条目', value: recommendations.value.length, suffix: '部', icon: 'mdi-format-list-numbered' },
  { label: '画像样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-account-heart-outline' },
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
  profile_agent_failed: { text: '画像生成失败', color: 'error' },
  profile_validation_failed: { text: '画像校验失败', color: 'error' },
  policy_failed: { text: '策略生成失败', color: 'error' },
  policy_superseded: { text: '策略已过期', color: 'warning' },
  candidate_failed: { text: '候选采集失败', color: 'error' },
  candidate_filter_failed: { text: '候选过滤失败', color: 'error' },
  candidate_snapshot_failed: { text: '候选快照失败', color: 'error' },
  ranking_agent_failed: { text: '排序生成失败', color: 'error' },
  ranking_validation_failed: { text: '排序校验失败', color: 'error' },
  ranking_save_failed: { text: '榜单保存失败', color: 'error' },
  runtime_exception: { text: '运行异常', color: 'error' },
  }[status] || { text: '运行异常', color: 'error' });

const historyStageLabels = {
  probe: '依赖探测',
  playback_snapshot: '冻结播放',
  policy: '确定策略',
  profile: '生成画像',
  candidate: '冻结候选',
  ranking: 'Agent排序',
  save: '保存榜单',
};
const historyStageStatusLabels = {
  ready: '完成', generated: '已生成', reused: '复用', cached: '使用缓存', saved: '已保存',
  success: '成功', pending: '等待', running: '进行中', stopped: '停止', failed: '失败',
  sample_insufficient: '样本不足', candidate_insufficient: '候选不足',
  recommendation_incomplete: '榜单不足', agent_failed: 'Agent失败',
  validation_failed: '校验失败', subscription_partial_failed: '部分订阅失败',
  profile_agent_failed: '画像生成失败', profile_validation_failed: '画像校验失败',
  policy_failed: '策略生成失败',
  policy_superseded: '偏好已更新，请重新生成',
  candidate_failed: '候选采集失败', candidate_filter_failed: '候选过滤失败',
  candidate_snapshot_failed: '候选快照失败', ranking_agent_failed: '排序生成失败',
  ranking_validation_failed: '排序校验失败', ranking_save_failed: '榜单保存失败', runtime_exception: '运行异常',
};
const historySourceLabels = {
  douban: '豆瓣', tmdb: 'TMDB', tmdb_movies: 'TMDB电影', tmdb_tv: 'TMDB剧集',
  tmdb_recommend: 'TMDB相关', bangumi: 'Bangumi', anilist: 'AniList',
};
const historyExclusionLabels = {
  invalid_or_unrecognized: '未识别', watched: '已观看', watched_completed: '已看完', library: '已入库',
  subscribed: '已订阅', disliked: '已点踩', archived: '已忽略', negative_keyword: '排除词',
  ambiguous_playback_count: '播放次数误写为看完次数',
  unsupported_playback_claim: '观看经历无法回溯',
};
const profileCacheReasonLabels = {
  disabled: '缓存已关闭',
  forced_rebuild: '本轮强制重建',
  missing: '没有可复用画像',
  profile_schema_changed: '画像结构已升级',
  retrieval_resolution_changed: '检索规则已升级',
  playback_changed: '播放记录已变化',
};
const rankingFallbackReasonLabels = {
  ranking_agent_failed: '排序调用失败',
  ranking_validation_failed: '排序格式失败',
  refill_agent_failed: '补选调用失败',
  refill_validation_failed: '补选格式失败',
  refill_insufficient: '补选数量不足',
  ranking_insufficient: '排序数量不足',
};
const historyValidationDropLabels = {
  unknown_candidate: '候选不在冻结池',
  duplicate_candidate: '候选重复',
  disliked_candidate: '已点踩',
  archived_candidate: '已忽略',
  subscribed_candidate: '已订阅',
  legacy_evidence_schema: '仍使用旧支持度字段',
  invalid_confidence: '支持度无效',
  summary_too_long: '简介超过30字',
  reason_too_long: '推荐理由超过30字',
  invalid_summary: '简介语义不完整',
  invalid_reason: '推荐理由不可信',
  ambiguous_playback_count: '播放次数误写为看完次数',
  unsupported_playback_claim: '观看经历无法回溯',
  unsupported_candidate_claim: '作品信息无法回溯',
  insufficient_match_evidence: '具体匹配证据不足',
  insufficient_verified_evidence: '可验证正向证据不足',
};
const historyAgentStageLabels = {
  profile: '画像',
  ranking: '排序',
  refill: '补选',
};
const historyAgentStatusLabels = {
  completed: '完成',
  validation_failed: '校验失败',
  failed: '调用失败',
  pending: '未完成',
};
const historyAgentSourceLabels = {
  agent_tokens: 'Agent Tokens',
  moviepilot_system: 'MoviePilot 系统',
  mixed: '混合来源',
  unknown: '来源未返回',
};

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'archive', title: '忽略归档', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return ({ movie: '电影', tv: '剧集', anime: '动漫' })[value] || '其他类型'
}

function historyKey(run) { return `${run?.run_id || ''}:${run?.finished_at || run?.started_at || ''}` }
function isHistoryExpanded(run) { return expandedHistoryKeys.value.has(historyKey(run)) }
function toggleHistory(run) {
  const key = historyKey(run);
  const next = new Set(expandedHistoryKeys.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedHistoryKeys.value = next;
}
function formatDuration(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)}毫秒`
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}秒`
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds ? `${minutes}分${seconds}秒` : `${minutes}分钟`
}
function historyStages(run) {
  const metrics = run?.metrics || {};
  return (Array.isArray(metrics.stage_order) ? metrics.stage_order : []).map(key => ({
    key,
    title: historyStageLabels[key] || '其他阶段',
    status: historyStageStatusLabels[metrics.stage_status?.[key]] || '未记录',
    duration: formatDuration(metrics.stage_ms?.[key]),
    failed: /failed|error|insufficient|validation/i.test(String(metrics.stage_status?.[key] || '')),
  }))
}
function translateHistoryError(value) {
  let text = String(value || '');
  text = text
    .replace(/^playback probe:/i, '播放探测：')
    .replace(/^playback:/i, '播放快照：')
    .replace(/^profile:/i, '画像阶段：')
    .replace(/^candidate:/i, '候选阶段：')
    .replace(/^ranking:/i, '排序阶段：')
    .replace(/^refill:/i, '补选阶段：')
    .replace(/Agent output must be one JSON object:\s*Expecting value/gi, 'Agent 输出不是有效的 JSON 对象：内容为空或格式错误')
    .replace(/Agent output must be one JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent output must be text/gi, 'Agent 输出不是文本')
    .replace(/Expecting value/gi, '内容为空或格式错误')
    .replace(/Extra data/gi, '存在多余内容')
    .replace(/Invalid control character/gi, '包含无效控制字符')
    .replace(/Unterminated string/gi, '字符串未闭合')
    .replace(/profile_validation_failed/gi, '画像校验失败')
    .replace(/policy_superseded/gi, '偏好已更新，请重新生成')
    .replace(/ranking_validation_failed/gi, '排序校验失败')
    .replace(/candidate_insufficient/gi, '候选不足')
    .replace(/recommendation_incomplete/gi, '榜单不足')
    .replace(/ambiguous_playback_count/gi, '播放次数误写为看完次数')
    .replace(/unsupported_playback_claim/gi, '观看经历无法回溯')
    .replace(/Agent did not produce a JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent did not produce text output/gi, 'Agent 输出不是文本');
  return text
}
function historyErrorText(run) {
  const errors = Array.isArray(run?.errors) ? run.errors : [];
  if (errors.length) {
    return errors.map(error => translateHistoryError(String(error)
      .replace(/^profile attempt\s+(\d+):/i, '画像第 $1 次：')
      .replace(/^refill attempt\s+(\d+):/i, '补选第 $1 次：')
      .replace(/^attempt\s+(\d+):/i, '排序第 $1 次：')
      .replace(/^profile:/i, '画像阶段：')
      .replace(/^candidate:/i, '候选阶段：')
      .replace(/^ranking:/i, '排序阶段：')
      .replace(/^refill:/i, '补选阶段：'))).join('；')
  }
  return translateHistoryError(run?.message || '本轮没有错误')
}
function historySourceText(run) {
  const sources = run?.metrics?.candidate_source_counts || run?.metrics?.fetched_source_counts || {};
  return Object.entries(sources).map(([key, value]) => `${historySourceLabels[key] || '其他来源'} ${value}`).join('、') || '无来源统计'
}
function historyExclusionText(run) {
  const exclusions = run?.metrics?.candidate_exclusion_counts || {};
  return Object.entries(exclusions).map(([key, value]) => `${historyExclusionLabels[key] || '其他排除原因'} ${value}`).join('、') || '无'
}
function historyPlaybackStatus(value) {
  return ({ ready: '已就绪', cached: '使用缓存', disabled: '已停用', error: '失败', transient_error: '临时错误' })[value] || '状态未知'
}
function historyCandidateTimingText(run) {
  const metrics = run?.metrics || {};
  const parts = [
    ['召回', metrics.candidate_recall_ms],
    ['标准化', metrics.candidate_normalize_ms],
    ['识别', metrics.candidate_recognition_ms],
    ['筛选', metrics.candidate_filter_ms],
    ['快照', metrics.candidate_snapshot_ms],
  ].filter(([, value]) => Number.isFinite(Number(value)));
  return parts.length ? parts.map(([label, value]) => `${label} ${formatDuration(value)}`).join('；') : '未记录'
}
function historyCandidateProcessingText(run) {
  const counts = run?.metrics?.candidate_processing_counts || {};
  const parts = [
    ['召回', counts.raw],
    ['识别输入', counts.recognition_input],
    ['识别成功', counts.recognized],
    ['最终入选', counts.accepted],
  ].filter(([, value]) => Number.isFinite(Number(value)));
  return parts.length ? parts.map(([label, value]) => `${label} ${value} 条`).join('；') : '未记录'
}
function historyProfileCacheText(run) {
  const metrics = run?.metrics || {};
  if (metrics.profile_cache_status === 'hit') return '命中，复用现有画像'
  const reason = profileCacheReasonLabels[metrics.profile_cache_miss_reason];
  if (reason) return `未命中，${reason}`
  return metrics.profile_cache_status ? '未命中，原因未记录' : '未记录'
}
function historyPolicyText(run) {
  const metrics = run?.metrics || {};
  const version = String(metrics.policy_version || '').trim();
  if (!version) return '未记录'
  return `${version}；记忆版本 ${Number(metrics.policy_memory_revision || 0)}；证据 ${Number(metrics.policy_evidence_count || 0)} 项`
}
function historyAgentCalls(run) {
  const calls = Array.isArray(run?.metrics?.agent_provenance) ? run.metrics.agent_provenance : [];
  return calls.map((item, index) => {
    const provider = String(item?.selected_provider_name || item?.provider || '').trim();
    const model = String(item?.model || '').trim();
    const source = String(item?.source || 'unknown').trim();
    const status = String(item?.status || 'pending').trim();
    const attempt = Number(item?.attempt || 1);
    const modelCalls = Number(item?.model_call_count || 0);
    return {
      key: `${item?.stage || item?.role || 'agent'}:${item?.attempt || index + 1}:${index}`,
      stage: historyAgentStageLabels[item?.stage] || historyAgentStageLabels[item?.role] || 'Agent',
      attempt: Number.isFinite(attempt) ? Math.max(1, attempt) : 1,
      provider: provider || (source === 'moviepilot_system' ? 'MoviePilot 系统' : source === 'agent_tokens' ? 'Agent Tokens' : '供应商未返回'),
      model: model && model !== 'unknown' ? model : '模型来源未返回',
      source: historyAgentSourceLabels[source] || '来源未返回',
      duration: formatDuration(item?.duration_ms),
      modelCalls: Number.isFinite(modelCalls) ? Math.max(0, modelCalls) : 0,
      status: historyAgentStatusLabels[status] || '状态未返回',
      failed: status === 'failed' || status === 'validation_failed',
      failure: item?.failure_reason ? translateHistoryError(item.failure_reason) : '',
    }
  })
}
function historyModelText(run) {
  const callLabels = historyAgentCalls(run)
    .filter(item => item.model !== '模型来源未返回')
    .map(item => `${item.provider} · ${item.model}`);
  const uniqueCallLabels = [...new Set(callLabels)];
  if (uniqueCallLabels.length) return uniqueCallLabels.join(' / ')
  const provider = String(run?.metrics?.agent_provider || '').trim();
  const model = String(run?.metrics?.agent_model || '').trim();
  if (model && model !== 'unknown') return provider ? `${provider} · ${model}` : model
  return '模型来源未返回'
}
function historyRankingText(run) {
  const metrics = run?.metrics || {};
  const valid = Number(metrics.ranking_valid_count);
  const reserve = Number(metrics.ranking_reserve_count);
  const refill = Number(metrics.refill_agent_calls || 0);
  const fallback = Number(metrics.ranking_fallback_count || 0);
  const fallbackReason = rankingFallbackReasonLabels[metrics.ranking_fallback_reason] || '安全候选补位';
  if (!Number.isFinite(valid)) return '未记录'
  return `校验通过 ${valid} 条；备用 ${Number.isFinite(reserve) ? reserve : 0} 条；补选 ${refill} 次${fallback ? `；保底 ${fallback} 条（${fallbackReason}）` : ''}`
}
function historyValidationDropText(run) {
  const summarize = values => {
    if (!Array.isArray(values) || !values.length) return ''
    const counts = new Map();
    values.forEach(value => {
      const code = String(value || '').trim();
      if (code) counts.set(code, (counts.get(code) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([code, count]) => `${historyValidationDropLabels[code] || '其他校验原因'} ${count}`)
      .join('、')
  };
  const initial = summarize(run?.metrics?.validation_drops);
  const refill = summarize(run?.metrics?.refill_drops);
  const parts = [];
  if (initial) parts.push(`首轮：${initial}`);
  if (refill) parts.push(`补选：${refill}`);
  return parts.join('；') || '无'
}
function historySelectionSourceText(run) {
  const metrics = run?.metrics || {};
  const counts = metrics.selection_source_counts || {};
  const agent = Number(metrics.agent_selected_count ?? counts.agent ?? 0);
  const fallback = Number(metrics.safe_fallback_selected_count ?? counts.safe_fallback ?? 0);
  return `Agent 选择 ${agent} 条；安全补位 ${fallback} 条`
}

async function initialize() {
  try {
    await state.loadOptions();
    if (state.selectedProfileId.value) {
      await Promise.all([state.loadProfileData(), state.loadPendingCenter()]);
    }
  } catch (_) {
    // 共享状态承载错误。
  } finally {
    initialized.value = true;
  }
}

async function runAction(action, successMessage) {
  try {
    const result = await action();
    snackbar.value = { show: true, message: result?.message || successMessage, color: 'success' };
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' };
  }
}

async function changeHistoryPage(page) {
  historyPage.value = page;
  try { await state.loadHistory(page, historyPageSize); } catch (_) { /* 错误已保存 */ }
}

async function addProfileTag(kind) {
  const tag = String(tagDrafts[kind] || '').trim();
  if (!tag) return
  await runAction(
    () => state.updateProfileTag(kind, 'add', tag),
    kind === 'positive' ? '偏好标签已添加' : '避雷标签已添加',
  );
  tagDrafts[kind] = '';
}

async function removeProfileTag(kind, tag) {
  await runAction(
    () => state.updateProfileTag(kind, 'remove', tag),
    kind === 'positive' ? '偏好标签已归档' : '避雷标签已归档',
  );
}

async function restoreProfileTag(item) {
  await runAction(
    () => state.updateProfileTag(item.kind, 'restore', item.tag),
    item.kind === 'positive' ? '偏好标签已恢复' : '避雷标签已恢复',
  );
}

function openAnalysis(item) {
  selectedAnalysisItem.value = item;
  selectedJudgment.value = null;
  analysisDialog.value = true;
}

function openAnalysisComment(judgment) {
  selectedJudgment.value = judgment;
  commentDialog.value = true;
}

function showFeedbackResult(message) {
  snackbar.value = { show: true, message, color: 'success' };
}

watch(state.selectedProfileId, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  historyPage.value = 1;
  try { await Promise.all([state.loadProfileData(value), state.loadPendingCenter()]); } catch (_) { /* 错误已保存 */ }
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
  const _component_VBadge = _resolveComponent("VBadge");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
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
        _cache[25] || (_cache[25] = _createElementVNode("div", { class: "ar-page__heading" }, [
          _createElementVNode("div", { class: "ar-page__title" }, "Agent榜单中心"),
          _createElementVNode("div", { class: "ar-page__subtitle" }, "推荐结果、用户画像与运行记录")
        ], -1)),
        _createVNode(_component_VSpacer),
        (_unref(state).identities.value.length > 1)
          ? (_openBlock(), _createBlock(_component_VSelect, {
              key: 0,
              modelValue: _unref(state).selectedProfileId.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref(state).selectedProfileId.value) = $event)),
              items: _unref(state).identityOptions.value,
              "item-title": "title",
              "item-value": "value",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              label: "Emby 用户",
              class: "ar-page__identity",
              "aria-label": "切换 Emby 画像身份"
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
          icon: "mdi-forum-outline",
          variant: "text",
          "aria-label": "打开 CinePilot Agent",
          onClick: _cache[2] || (_cache[2] = $event => (criticDialog.value = true))
        }),
        _createVNode(_component_VBadge, {
          content: _unref(state).pendingCenter.value?.total || 0,
          "model-value": Boolean(_unref(state).pendingCenter.value?.total),
          color: "warning",
          class: "ar-page__pending-badge"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VBtn, {
              icon: "mdi-inbox-outline",
              variant: "text",
              "aria-label": "打开待处理中心",
              onClick: _cache[3] || (_cache[3] = $event => (pendingDialog.value = true))
            })
          ]),
          _: 1
        }, 8, ["content", "model-value"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-cog-outline",
          variant: "text",
          "aria-label": "打开设置",
          onClick: _cache[4] || (_cache[4] = $event => (emit('switch', _unref(state).options.value?.config || {})))
        }),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 1,
              icon: "mdi-close",
              variant: "text",
              "aria-label": "关闭详情",
              class: "me-2",
              onClick: _cache[5] || (_cache[5] = $event => (emit('close')))
            }))
          : _createCommentVNode("", true)
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
      (_unref(state).isRunning.value)
        ? (_openBlock(), _createBlock(_component_VChip, {
            key: 0,
            color: "primary",
            variant: "tonal",
            size: "small",
            "prepend-icon": "mdi-loading",
            class: "ar-page__runtime-chip"
          }, {
            default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
              _createTextVNode(" 正在生成 ", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode("", true)
    ]),
    _createElementVNode("nav", _hoisted_5, [
      _createVNode(_component_VList, {
        density: "compact",
        nav: "",
        class: "ar-page__tab-list"
      }, {
        default: _withCtx(() => [
          (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
            return _createVNode(_component_VListItem, {
              key: tab.key,
              active: activeTab.value === tab.key,
              color: "primary",
              rounded: "lg",
              class: "ar-page__tab",
              "aria-current": activeTab.value === tab.key ? 'page' : undefined,
              onClick: $event => (activeTab.value = tab.key)
            }, {
              prepend: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: tab.icon,
                  size: "18"
                }, null, 8, ["icon"])
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VListItemTitle, null, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(tab.title), 1)
                  ]),
                  _: 2
                }, 1024)
              ]),
              _: 2
            }, 1032, ["active", "aria-current", "onClick"])
          }), 64))
        ]),
        _: 1
      })
    ]),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_6, [
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
            _withDirectives(_createElementVNode("section", _hoisted_7, [
              _createElementVNode("div", _hoisted_8, [
                _cache[27] || (_cache[27] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "个性推荐榜单"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "Agent 根据订阅画像，从发现候选中挑出的前5名。")
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
                    text: "点击右上角刷新，根据播放画像生成前5名。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_9, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recommendations.value, (item) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: item.candidate_id,
                        class: "ar-page__rank-item"
                      }, [
                        _createElementVNode("div", {
                          class: _normalizeClass(["ar-page__rank", { 'ar-page__rank--top': item.rank <= 3 }])
                        }, _toDisplayString(item.rank), 3),
                        _createElementVNode("div", _hoisted_10, [
                          (item.poster_path)
                            ? (_openBlock(), _createBlock(_component_VImg, {
                                key: 0,
                                src: item.poster_path,
                                alt: `${item.title} 海报`,
                                cover: ""
                              }, {
                                error: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_11, [
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
                        _createElementVNode("div", _hoisted_12, [
                          _createElementVNode("div", _hoisted_13, [
                            _createElementVNode("div", _hoisted_14, _toDisplayString(item.title), 1),
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
                          _createElementVNode("div", _hoisted_15, [
                            _createElementVNode("span", null, _toDisplayString(item.year || '年份未知'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_16, [
                            _cache[28] || (_cache[28] = _createElementVNode("span", { class: "ar-page__copy-label" }, "推荐：", -1)),
                            _createElementVNode("span", _hoisted_17, _toDisplayString(item.reason || item.summary || '等待 Agent 补充推荐理由'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_18, [
                            _cache[29] || (_cache[29] = _createElementVNode("span", { class: "ar-page__copy-label" }, "简介：", -1)),
                            _createElementVNode("span", _hoisted_19, _toDisplayString(item.summary || '暂无简介'), 1)
                          ]),
                          (item.match_tags?.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.match_tags, (tag) => {
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
                                }), 128))
                              ]))
                            : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("div", _hoisted_21, [
                          _createVNode(_component_VTooltip, { text: "查看 Agent 分析" }, {
                            activator: _withCtx(({ props: tooltipProps }) => [
                              _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, tooltipProps, {
                                icon: "mdi-text-box-search-outline",
                                variant: "text",
                                size: "small",
                                "aria-label": `查看 ${item.title} 的 Agent 分析`,
                                disabled: !item.analysis_id,
                                onClick: $event => (openAnalysis(item))
                              }), null, 16, ["aria-label", "disabled", "onClick"])
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: "primary",
                            variant: "tonal",
                            class: "ar-page__support"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(item.support?.percentage ?? '—') + _toDisplayString(item.support ? '%' : ''), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(RecommendationActions, {
                            item: item,
                            "loading-action": _unref(state).loading.action,
                            "native-subscribe": __props.nativeSubscribe,
                            size: "small",
                            onLike: _cache[6] || (_cache[6] = candidateId => runAction(() => _unref(state).reactToRecommendation('like', candidateId), '已记录点赞')),
                            onDislike: _cache[7] || (_cache[7] = candidateId => runAction(() => _unref(state).reactToRecommendation('dislike', candidateId), '已记录点踩')),
                            onSubscribe: _cache[8] || (_cache[8] = candidateId => runAction(() => _unref(state).subscribe(candidateId), '订阅操作已完成')),
                            onNativeSubscribeOpened: _cache[9] || (_cache[9] = candidateId => runAction(() => _unref(state).recordNativeDrawerOpened(candidateId), '已打开订阅设置')),
                            onArchive: _cache[10] || (_cache[10] = candidateId => runAction(() => _unref(state).archive(candidateId), '已忽略推荐'))
                          }, null, 8, ["item", "loading-action", "native-subscribe"])
                        ])
                      ]))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'board']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_22, [
              _createElementVNode("div", _hoisted_23, [
                _cache[30] || (_cache[30] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "用户画像"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "用播放样本描述偏好、避雷方向与本轮榜单命中。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal",
                  "prepend-icon": "mdi-clock-outline"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(formatTime(_unref(state).profile.value?.generated_at)), 1)
                  ]),
                  _: 1
                })
              ]),
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
                        default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                          _createTextVNode("画像摘要", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode(_component_VCardSubtitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode("Emby 用户 " + _toDisplayString(_unref(state).selectedUsername.value || '—') + " · 运行 " + _toDisplayString(profileRunId.value), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VDivider),
                  _createVNode(_component_VCardText, { class: "ar-page__profile-body" }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_24, [
                        _createElementVNode("div", _hoisted_25, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-text-box-search-outline",
                            size: "18"
                          }),
                          _cache[32] || (_cache[32] = _createTextVNode("口味摘要", -1))
                        ]),
                        _createElementVNode("div", _hoisted_26, _toDisplayString(_unref(state).profile.value?.summary || '尚未生成用户画像'), 1)
                      ]),
                      _createElementVNode("div", _hoisted_27, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(profileStats.value, (stat) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: stat.label,
                            class: "ar-page__profile-metric"
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: stat.icon,
                              color: "primary",
                              size: "19"
                            }, null, 8, ["icon"]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, [
                                _createTextVNode(_toDisplayString(stat.value), 1),
                                _createElementVNode("span", null, _toDisplayString(stat.suffix), 1)
                              ]),
                              _createElementVNode("small", null, _toDisplayString(stat.label), 1)
                            ])
                          ]))
                        }), 128))
                      ]),
                      _createElementVNode("div", _hoisted_28, [
                        _createElementVNode("div", _hoisted_29, [
                          _createElementVNode("div", _hoisted_30, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-heart-outline",
                              size: "18"
                            }),
                            _cache[33] || (_cache[33] = _createTextVNode("偏好标签", -1))
                          ]),
                          _createElementVNode("div", _hoisted_31, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(positiveTags.value, (tag) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: tag,
                                color: "primary",
                                variant: "tonal",
                                size: "small",
                                closable: "",
                                "onClick:close": $event => (removeProfileTag('positive', tag))
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(tag), 1)
                                ]),
                                _: 2
                              }, 1032, ["onClick:close"]))
                            }), 128)),
                            (!positiveTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_32, "暂无偏好标签"))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_33, [
                            _createVNode(_component_VTextField, {
                              modelValue: tagDrafts.positive,
                              "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((tagDrafts.positive) = $event)),
                              label: "添加偏好标签",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              maxlength: "20",
                              onKeyup: _cache[12] || (_cache[12] = _withKeys($event => (addProfileTag('positive')), ["enter"]))
                            }, null, 8, ["modelValue"]),
                            _createVNode(_component_VBtn, {
                              color: "primary",
                              variant: "tonal",
                              size: "small",
                              loading: _unref(state).loading.action === 'profile/tags',
                              onClick: _cache[13] || (_cache[13] = $event => (addProfileTag('positive')))
                            }, {
                              default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                                _createTextVNode("添加", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading"])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_34, [
                          _createElementVNode("div", _hoisted_35, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-shield-alert-outline",
                              size: "18"
                            }),
                            _cache[35] || (_cache[35] = _createTextVNode("避雷标签", -1))
                          ]),
                          _createElementVNode("div", _hoisted_36, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(negativeTags.value, (tag) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: tag,
                                color: "error",
                                variant: "tonal",
                                size: "small",
                                closable: "",
                                "onClick:close": $event => (removeProfileTag('negative', tag))
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(tag), 1)
                                ]),
                                _: 2
                              }, 1032, ["onClick:close"]))
                            }), 128)),
                            (!negativeTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_37, "暂无避雷标签"))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_38, [
                            _createVNode(_component_VTextField, {
                              modelValue: tagDrafts.negative,
                              "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((tagDrafts.negative) = $event)),
                              label: "添加避雷标签",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              maxlength: "20",
                              onKeyup: _cache[15] || (_cache[15] = _withKeys($event => (addProfileTag('negative')), ["enter"]))
                            }, null, 8, ["modelValue"]),
                            _createVNode(_component_VBtn, {
                              color: "error",
                              variant: "tonal",
                              size: "small",
                              loading: _unref(state).loading.action === 'profile/tags',
                              onClick: _cache[16] || (_cache[16] = $event => (addProfileTag('negative')))
                            }, {
                              default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                                _createTextVNode("添加", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading"])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_39, [
                          _createElementVNode("div", _hoisted_40, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-target-account",
                              size: "18"
                            }),
                            _cache[37] || (_cache[37] = _createTextVNode("本轮命中", -1))
                          ]),
                          _createElementVNode("div", _hoisted_41, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(boardMatchTags.value, (item) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: item.tag,
                                color: "info",
                                variant: "tonal",
                                size: "small"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.tag), 1),
                                  (item.count > 1)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_42, "×" + _toDisplayString(item.count), 1))
                                    : _createCommentVNode("", true)
                                ]),
                                _: 2
                              }, 1024))
                            }), 128)),
                            (!boardMatchTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_43, "暂无命中标签"))
                              : _createCommentVNode("", true)
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_44, [
                          _createElementVNode("div", _hoisted_45, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-archive-outline",
                              size: "18"
                            }),
                            _cache[38] || (_cache[38] = _createTextVNode("归档标签", -1))
                          ]),
                          _createElementVNode("div", _hoisted_46, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archivedProfileTags.value, (item) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: `${item.kind}:${item.tag}`,
                                class: "ar-page__archived-tag"
                              }, [
                                _createVNode(_component_VChip, {
                                  color: item.kind === 'negative' ? 'error' : 'primary',
                                  variant: "outlined",
                                  size: "small"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.tag) + " · " + _toDisplayString(item.kind === 'negative' ? '避雷' : '偏好'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"]),
                                _createVNode(_component_VTooltip, { text: "恢复标签" }, {
                                  activator: _withCtx(({ props: tooltipProps }) => [
                                    _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, tooltipProps, {
                                      icon: "mdi-restore",
                                      variant: "text",
                                      size: "x-small",
                                      "aria-label": "恢复标签",
                                      loading: _unref(state).loading.action === 'profile/tags',
                                      onClick: $event => (restoreProfileTag(item))
                                    }), null, 16, ["loading", "onClick"])
                                  ]),
                                  _: 2
                                }, 1024)
                              ]))
                            }), 128)),
                            (!archivedProfileTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_47, "暂无归档标签"))
                              : _createCommentVNode("", true)
                          ])
                        ])
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
            _withDirectives(_createElementVNode("section", _hoisted_48, [
              _createElementVNode("div", _hoisted_49, [
                _cache[39] || (_cache[39] = _createElementVNode("div", null, [
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
                : (_openBlock(), _createElementBlock("div", _hoisted_50, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveEntries.value, (entry) => {
                      return (_openBlock(), _createBlock(_component_VCard, {
                        key: entry.candidate_id,
                        variant: "outlined",
                        class: "ar-page__archive-card"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardItem, null, {
                            prepend: _withCtx(() => [
                              _createElementVNode("div", _hoisted_51, "#" + _toDisplayString(entry.original_rank), 1)
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
                                default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
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
            _withDirectives(_createElementVNode("section", _hoisted_52, [
              _createElementVNode("div", _hoisted_53, [
                _cache[41] || (_cache[41] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "运行历史"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "按结果、耗时、阶段和候选统计查看每次运行。")
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
                    _createElementVNode("div", _hoisted_54, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(state).history.value, (run) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: historyKey(run),
                          class: "ar-page__history-item"
                        }, [
                          _createElementVNode("div", _hoisted_55, [
                            _createElementVNode("div", _hoisted_56, [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-clock-outline",
                                size: "17",
                                color: "primary"
                              }),
                              _createElementVNode("strong", null, _toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                              (run.metrics?.elapsed_ms)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_57, "耗时 " + _toDisplayString(formatDuration(run.metrics.elapsed_ms)), 1))
                                : _createCommentVNode("", true)
                            ]),
                            _createVNode(_component_VChip, {
                              size: "small",
                              color: statusMetaFor(run.status).color,
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(statusMetaFor(run.status).text), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_58, [
                            _cache[42] || (_cache[42] = _createElementVNode("span", { class: "ar-page__history-message-label" }, "结果：", -1)),
                            _createTextVNode(_toDisplayString(translateHistoryError(run.message || '本轮运行已记录')), 1)
                          ]),
                          _createElementVNode("div", _hoisted_59, [
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.candidate_count ?? 0), 1),
                              _cache[43] || (_cache[43] = _createElementVNode("span", null, "候选条目", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.final_count ?? 0), 1),
                              _cache[44] || (_cache[44] = _createElementVNode("span", null, "安全推荐", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", _hoisted_60, _toDisplayString(historyModelText(run)), 1),
                              _cache[45] || (_cache[45] = _createElementVNode("span", null, "供应商 / 模型", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.subscription_success_count ?? 0), 1),
                              _cache[46] || (_cache[46] = _createElementVNode("span", null, "自动订阅", -1))
                            ])
                          ]),
                          (historyStages(run).length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_61, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyStages(run), (stage) => {
                                  return (_openBlock(), _createElementBlock("div", {
                                    key: stage.key,
                                    class: _normalizeClass(["ar-page__history-stage", { 'ar-page__history-stage--failed': stage.failed }])
                                  }, [
                                    _createVNode(_component_VIcon, {
                                      icon: stage.failed ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline',
                                      color: stage.failed ? 'error' : 'success',
                                      size: "17"
                                    }, null, 8, ["icon", "color"]),
                                    _createElementVNode("div", null, [
                                      _createElementVNode("strong", null, _toDisplayString(stage.title), 1),
                                      _createElementVNode("small", null, _toDisplayString(stage.status) + " · " + _toDisplayString(stage.duration), 1)
                                    ])
                                  ], 2))
                                }), 128))
                              ]))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", {
                            class: _normalizeClass(["ar-page__history-error", { 'ar-page__history-error--ok': !run.errors?.length && run.status === 'success' }])
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: run.errors?.length ? 'mdi-alert-outline' : 'mdi-information-outline',
                              size: "16"
                            }, null, 8, ["icon"]),
                            _createElementVNode("span", null, _toDisplayString(historyErrorText(run)), 1)
                          ], 2),
                          _createElementVNode("div", _hoisted_62, [
                            _createElementVNode("span", null, "来源：" + _toDisplayString(historySourceText(run)), 1),
                            _createVNode(_component_VBtn, {
                              size: "x-small",
                              variant: "text",
                              "append-icon": isHistoryExpanded(run) ? 'mdi-chevron-up' : 'mdi-chevron-down',
                              onClick: $event => (toggleHistory(run))
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(isHistoryExpanded(run) ? '收起细节' : '查看细节'), 1)
                              ]),
                              _: 2
                            }, 1032, ["append-icon", "onClick"])
                          ]),
                          (isHistoryExpanded(run))
                            ? (_openBlock(), _createElementBlock("div", _hoisted_63, [
                                _createElementVNode("div", null, [
                                  _cache[47] || (_cache[47] = _createElementVNode("span", null, "运行编号", -1)),
                                  _createElementVNode("code", null, _toDisplayString(run.run_id || '—'), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[48] || (_cache[48] = _createElementVNode("span", null, "模型调用", -1)),
                                  _createElementVNode("span", null, _toDisplayString(run.metrics?.model_call_count ?? run.metrics?.agent_calls ?? 0) + " 次；画像任务 " + _toDisplayString(run.metrics?.profile_agent_calls ?? 0) + " 次；排序任务 " + _toDisplayString(run.metrics?.ranking_agent_calls ?? 0) + " 次", 1)
                                ]),
                                (historyAgentCalls(run).length)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_64, [
                                      _cache[49] || (_cache[49] = _createElementVNode("span", null, "调用明细", -1)),
                                      _createElementVNode("div", _hoisted_65, [
                                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyAgentCalls(run), (call) => {
                                          return (_openBlock(), _createElementBlock("div", {
                                            key: call.key,
                                            class: _normalizeClass(["ar-page__history-agent-call", { 'ar-page__history-agent-call--failed': call.failed }])
                                          }, [
                                            _createElementVNode("div", _hoisted_66, [
                                              _createElementVNode("strong", null, _toDisplayString(call.stage) + " · 第 " + _toDisplayString(call.attempt) + " 次", 1),
                                              _createElementVNode("span", null, _toDisplayString(call.status), 1)
                                            ]),
                                            _createElementVNode("div", null, _toDisplayString(call.provider) + " · " + _toDisplayString(call.model), 1),
                                            _createElementVNode("small", null, _toDisplayString(call.source) + " · " + _toDisplayString(call.duration) + " · 模型调用 " + _toDisplayString(call.modelCalls) + " 次", 1),
                                            (call.failure)
                                              ? (_openBlock(), _createElementBlock("small", _hoisted_67, _toDisplayString(call.failure), 1))
                                              : _createCommentVNode("", true)
                                          ], 2))
                                        }), 128))
                                      ])
                                    ]))
                                  : _createCommentVNode("", true),
                                _createElementVNode("div", null, [
                                  _cache[50] || (_cache[50] = _createElementVNode("span", null, "画像缓存", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyProfileCacheText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[51] || (_cache[51] = _createElementVNode("span", null, "排序策略", -1)),
                                  _createElementVNode("code", null, _toDisplayString(historyPolicyText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[52] || (_cache[52] = _createElementVNode("span", null, "播放快照", -1)),
                                  _createElementVNode("span", null, _toDisplayString(run.metrics?.playback_count ?? 0) + " 条，" + _toDisplayString(historyPlaybackStatus(run.metrics?.playback_status)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[53] || (_cache[53] = _createElementVNode("span", null, "候选耗时", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyCandidateTimingText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[54] || (_cache[54] = _createElementVNode("span", null, "候选处理", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyCandidateProcessingText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[55] || (_cache[55] = _createElementVNode("span", null, "排序校验", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyRankingText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[56] || (_cache[56] = _createElementVNode("span", null, "校验丢弃", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyValidationDropText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[57] || (_cache[57] = _createElementVNode("span", null, "选择来源", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historySelectionSourceText(run)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[58] || (_cache[58] = _createElementVNode("span", null, "候选排除", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyExclusionText(run)), 1)
                                ])
                              ]))
                            : _createCommentVNode("", true)
                        ]))
                      }), 128))
                    ]),
                    _createVNode(_component_VPagination, {
                      modelValue: historyPage.value,
                      "onUpdate:modelValue": [
                        _cache[17] || (_cache[17] = $event => ((historyPage).value = $event)),
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
    _createVNode(AgentAnalysisDialog, {
      modelValue: analysisDialog.value,
      "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((analysisDialog).value = $event)),
      state: _unref(state),
      item: selectedAnalysisItem.value,
      onComment: openAnalysisComment
    }, null, 8, ["modelValue", "state", "item"]),
    _createVNode(FeedbackCommentDialog, {
      modelValue: commentDialog.value,
      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((commentDialog).value = $event)),
      state: _unref(state),
      item: selectedAnalysisItem.value,
      judgment: selectedJudgment.value,
      onSubmitted: _cache[20] || (_cache[20] = $event => (showFeedbackResult('评论已记录，Agent 将异步重新理解')))
    }, null, 8, ["modelValue", "state", "item", "judgment"]),
    _createVNode(CriticChatDialog, {
      modelValue: criticDialog.value,
      "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((criticDialog).value = $event)),
      state: _unref(state),
      onPendingChange: _unref(state).loadPendingCenter
    }, null, 8, ["modelValue", "state", "onPendingChange"]),
    _createVNode(PendingConfirmations, {
      modelValue: pendingDialog.value,
      "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((pendingDialog).value = $event)),
      state: _unref(state),
      onChanged: _cache[23] || (_cache[23] = $event => (showFeedbackResult('待处理项目已更新')))
    }, null, 8, ["modelValue", "state"]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((snackbar.value.show) = $event)),
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-b8c3e946"]]);

export { Page as default };
