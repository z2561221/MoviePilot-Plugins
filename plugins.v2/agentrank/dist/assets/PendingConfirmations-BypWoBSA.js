import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-Z-mQLghu.js';

const {unref:_unref$3,resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,createElementVNode:_createElementVNode$3,toDisplayString:_toDisplayString$3,createTextVNode:_createTextVNode$3,withCtx:_withCtx$3,openBlock:_openBlock$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3,createElementBlock:_createElementBlock$2,withModifiers:_withModifiers$2,mergeProps:_mergeProps$1,renderList:_renderList$2,Fragment:_Fragment$2} = await importShared('vue');


const _hoisted_1$3 = { class: "ar-analysis__heading" };
const _hoisted_2$3 = { class: "ar-analysis__subtitle" };
const _hoisted_3$3 = {
  key: 0,
  class: "ar-analysis__state"
};
const _hoisted_4$3 = {
  key: 3,
  class: "ar-analysis__sections"
};
const _hoisted_5$2 = { class: "ar-analysis__section-head" };
const _hoisted_6$2 = { class: "ar-analysis__section-copy" };
const _hoisted_7$2 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_8$2 = ["onClick"];
const _hoisted_9$2 = { class: "ar-analysis__row-main" };
const _hoisted_10$1 = { class: "ar-analysis__row-meta" };
const _hoisted_11 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_12 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { class: "ar-analysis__row-main" };
const _hoisted_15 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_16 = {
  key: 0,
  class: "ar-analysis__list"
};
const _hoisted_17 = ["onClick"];
const _hoisted_18 = { class: "ar-analysis__row-main" };
const _hoisted_19 = {
  key: 1,
  class: "ar-analysis__empty"
};
const _hoisted_20 = { class: "ar-analysis__provenance" };

const {computed: computed$3,watch: watch$3} = await importShared('vue');

const {useDisplay: useDisplay$3} = await importShared('vuetify');



const _sfc_main$3 = {
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

const candidateId = computed$3(() => String(props.item?.candidate_id || ''));
const analysis = computed$3(() => props.state.currentAnalysis(candidateId.value));
const operation = computed$3(() => props.state.operationState(`analysis:${candidateId.value}`));

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

watch$3(
  () => [props.modelValue, props.item?.analysis_id],
  ([open]) => { if (open) load(); },
  { immediate: true },
);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VSpacer = _resolveComponent$3("VSpacer");
  const _component_VChip = _resolveComponent$3("VChip");
  const _component_VBtn = _resolveComponent$3("VBtn");
  const _component_VToolbar = _resolveComponent$3("VToolbar");
  const _component_VDivider = _resolveComponent$3("VDivider");
  const _component_VProgressCircular = _resolveComponent$3("VProgressCircular");
  const _component_VAlert = _resolveComponent$3("VAlert");
  const _component_VEmptyState = _resolveComponent$3("VEmptyState");
  const _component_VTooltip = _resolveComponent$3("VTooltip");
  const _component_VCardText = _resolveComponent$3("VCardText");
  const _component_VCard = _resolveComponent$3("VCard");
  const _component_VDialog = _resolveComponent$3("VDialog");

  return (_openBlock$3(), _createBlock$3(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$3(smAndDown),
    "max-width": "780",
    scrollable: "",
    "onUpdate:modelValue": _cache[3] || (_cache[3] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$3(() => [
      _createVNode$3(_component_VCard, { class: "ar-analysis" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VToolbar, {
            density: "compact",
            class: "ar-analysis__toolbar"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VIcon, {
                icon: "mdi-text-box-search-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode$3("div", _hoisted_1$3, [
                _cache[4] || (_cache[4] = _createElementVNode$3("div", { class: "ar-analysis__title" }, "Agent分析", -1)),
                _createElementVNode$3("div", _hoisted_2$3, _toDisplayString$3(__props.item?.title || '当前推荐'), 1)
              ]),
              _createVNode$3(_component_VSpacer),
              (analysis.value)
                ? (_openBlock$3(), _createBlock$3(_component_VChip, {
                    key: 0,
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    class: "me-1"
                  }, {
                    default: _withCtx$3(() => [
                      _createTextVNode$3(_toDisplayString$3(analysis.value.support_percentage) + "% ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$3("", true),
              _createVNode$3(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭 Agent 分析",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$3(_component_VDivider),
          _createVNode$3(_component_VCardText, { class: "ar-analysis__body" }, {
            default: _withCtx$3(() => [
              (operation.value.loading)
                ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_3$3, [
                    _createVNode$3(_component_VProgressCircular, {
                      indeterminate: "",
                      color: "primary"
                    })
                  ]))
                : (operation.value.error)
                  ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
                      key: 1,
                      type: "error",
                      variant: "tonal"
                    }, {
                      append: _withCtx$3(() => [
                        _createVNode$3(_component_VBtn, {
                          variant: "text",
                          size: "small",
                          onClick: _cache[0] || (_cache[0] = $event => (props.state.retryOperation('analysis:' + candidateId.value)))
                        }, {
                          default: _withCtx$3(() => [...(_cache[5] || (_cache[5] = [
                            _createTextVNode$3("重试", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      default: _withCtx$3(() => [
                        _createTextVNode$3(_toDisplayString$3(operation.value.error.message) + " ", 1)
                      ]),
                      _: 1
                    }))
                  : (!analysis.value)
                    ? (_openBlock$3(), _createBlock$3(_component_VEmptyState, {
                        key: 2,
                        icon: "mdi-text-box-remove-outline",
                        title: "分析暂不可用"
                      }))
                    : (_openBlock$3(), _createElementBlock$2("div", _hoisted_4$3, [
                        _createElementVNode$3("section", {
                          class: "ar-analysis__summary",
                          onClick: _cache[2] || (_cache[2] = $event => (requestComment('推荐判断', analysis.value.reason || analysis.value.summary)))
                        }, [
                          _createElementVNode$3("div", _hoisted_5$2, [
                            _createElementVNode$3("div", null, [
                              _cache[6] || (_cache[6] = _createElementVNode$3("div", { class: "ar-analysis__section-title" }, "推荐判断", -1)),
                              _createElementVNode$3("div", _hoisted_6$2, _toDisplayString$3(analysis.value.reason || analysis.value.summary), 1)
                            ]),
                            _createVNode$3(_component_VTooltip, { text: "评论这条判断" }, {
                              activator: _withCtx$3(({ props: tooltipProps }) => [
                                _createVNode$3(_component_VBtn, _mergeProps$1(tooltipProps, {
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
                        _createElementVNode$3("section", null, [
                          _cache[7] || (_cache[7] = _createElementVNode$3("div", { class: "ar-analysis__section-title" }, "匹配证据", -1)),
                          (analysis.value.positive_evidence?.length)
                            ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_7$2, [
                                (_openBlock$3(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(analysis.value.positive_evidence, (evidence, index) => {
                                  return (_openBlock$3(), _createElementBlock$2("div", {
                                    key: `positive-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence)))
                                  }, [
                                    _createVNode$3(_component_VIcon, {
                                      icon: "mdi-check-circle-outline",
                                      color: "success",
                                      size: "20"
                                    }),
                                    _createElementVNode$3("div", _hoisted_9$2, [
                                      _createElementVNode$3("div", null, _toDisplayString$3(evidenceText(evidence)), 1),
                                      _createElementVNode$3("div", _hoisted_10$1, "贡献 " + _toDisplayString$3(evidence.contribution_units) + " · 证据 " + _toDisplayString$3(evidence.user_refs?.length || 0) + " 项", 1)
                                    ]),
                                    _createVNode$3(_component_VTooltip, { text: "评论这条证据" }, {
                                      activator: _withCtx$3(({ props: tooltipProps }) => [
                                        _createVNode$3(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论匹配证据 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence))), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_8$2))
                                }), 128))
                              ]))
                            : (_openBlock$3(), _createElementBlock$2("div", _hoisted_11, "没有足够的正向具体证据。"))
                        ]),
                        _createElementVNode$3("section", null, [
                          _cache[8] || (_cache[8] = _createElementVNode$3("div", { class: "ar-analysis__section-title" }, "反向证据", -1)),
                          (analysis.value.counter_evidence?.length)
                            ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_12, [
                                (_openBlock$3(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(analysis.value.counter_evidence, (evidence, index) => {
                                  return (_openBlock$3(), _createElementBlock$2("div", {
                                    key: `counter-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`反向证据 ${index + 1}`, evidenceText(evidence)))
                                  }, [
                                    _createVNode$3(_component_VIcon, {
                                      icon: "mdi-alert-circle-outline",
                                      color: "warning",
                                      size: "20"
                                    }),
                                    _createElementVNode$3("div", _hoisted_14, _toDisplayString$3(evidenceText(evidence)), 1),
                                    _createVNode$3(_component_VTooltip, { text: "评论这条证据" }, {
                                      activator: _withCtx$3(({ props: tooltipProps }) => [
                                        _createVNode$3(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论反向证据 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`反向证据 ${index + 1}`, evidenceText(evidence))), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_13))
                                }), 128))
                              ]))
                            : (_openBlock$3(), _createElementBlock$2("div", _hoisted_15, "未发现需要特别提示的反向证据。"))
                        ]),
                        _createElementVNode$3("section", null, [
                          _cache[9] || (_cache[9] = _createElementVNode$3("div", { class: "ar-analysis__section-title" }, "不确定点", -1)),
                          (analysis.value.uncertainties?.length)
                            ? (_openBlock$3(), _createElementBlock$2("div", _hoisted_16, [
                                (_openBlock$3(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(analysis.value.uncertainties, (uncertainty, index) => {
                                  return (_openBlock$3(), _createElementBlock$2("div", {
                                    key: `uncertainty-${index}`,
                                    class: "ar-analysis__row",
                                    onClick: $event => (requestComment(`不确定点 ${index + 1}`, uncertainty))
                                  }, [
                                    _createVNode$3(_component_VIcon, {
                                      icon: "mdi-help-circle-outline",
                                      color: "info",
                                      size: "20"
                                    }),
                                    _createElementVNode$3("div", _hoisted_18, _toDisplayString$3(uncertainty), 1),
                                    _createVNode$3(_component_VTooltip, { text: "评论这条判断" }, {
                                      activator: _withCtx$3(({ props: tooltipProps }) => [
                                        _createVNode$3(_component_VBtn, _mergeProps$1({ ref_for: true }, tooltipProps, {
                                          icon: "mdi-comment-edit-outline",
                                          variant: "text",
                                          size: "small",
                                          "aria-label": `评论不确定点 ${index + 1}`,
                                          onClick: _withModifiers$2($event => (requestComment(`不确定点 ${index + 1}`, uncertainty)), ["stop"])
                                        }), null, 16, ["aria-label", "onClick"])
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ], 8, _hoisted_17))
                                }), 128))
                              ]))
                            : (_openBlock$3(), _createElementBlock$2("div", _hoisted_19, "当前没有额外不确定点。"))
                        ]),
                        _createElementVNode$3("div", _hoisted_20, [
                          _createElementVNode$3("span", null, "选择：" + _toDisplayString$3(analysis.value.selection_source === 'agent' ? 'Agent排序' : '安全候选补位'), 1),
                          _createElementVNode$3("span", null, "策略：" + _toDisplayString$3(analysis.value.policy_version), 1),
                          _createElementVNode$3("span", null, "记忆版本：" + _toDisplayString$3(analysis.value.memory_revision), 1)
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
const AgentAnalysisDialog = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-24c1291e"]]);

const {unref:_unref$2,resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,withCtx:_withCtx$2,createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createTextVNode:_createTextVNode$2,createElementBlock:_createElementBlock$1,renderList:_renderList$1,Fragment:_Fragment$1,normalizeClass:_normalizeClass,withModifiers:_withModifiers$1,withKeys:_withKeys$1} = await importShared('vue');


const _hoisted_1$2 = { class: "ar-chat__subtitle" };
const _hoisted_2$2 = {
  key: 1,
  class: "ar-chat__empty"
};
const _hoisted_3$2 = { class: "ar-chat__content" };
const _hoisted_4$2 = { class: "ar-chat__meta" };
const _hoisted_5$1 = { key: 0 };
const _hoisted_6$1 = {
  key: 0,
  class: "ar-chat__failure"
};
const _hoisted_7$1 = {
  key: 2,
  class: "ar-chat__commands"
};
const _hoisted_8$1 = { class: "ar-chat__command-main" };
const _hoisted_9$1 = { class: "ar-chat__command-actions" };
const _hoisted_10 = { class: "ar-chat__composer" };

const {computed: computed$2,nextTick,ref: ref$2,watch: watch$2} = await importShared('vue');

const {useDisplay: useDisplay$2} = await importShared('vuetify');



const _sfc_main$2 = {
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
const draft = ref$2('');
const localError = ref$2('');
const messageList = ref$2(null);

const messages = computed$2(() => props.state.conversation.value?.messages || []);
const commands = computed$2(() => props.state.conversation.value?.commands || []);
const pendingCommands = computed$2(() => commands.value.filter(item => item.status === 'pending_confirmation'));
const conversationOperation = computed$2(() => props.state.operationState('conversation'));
const sendOperation = computed$2(() => props.state.operationState('conversation:send'));
const canSend = computed$2(() => draft.value.trim().length > 0 && !sendOperation.value.loading);

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
    localError.value = error?.message || '待确认操作失败';
  }
}

watch$2(() => props.modelValue, open => { if (open) load(); }, { immediate: true });
watch$2(() => messages.value.length, () => { if (props.modelValue) scrollToEnd(); });

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VAvatar = _resolveComponent$2("VAvatar");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VBadge = _resolveComponent$2("VBadge");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VToolbar = _resolveComponent$2("VToolbar");
  const _component_VDivider = _resolveComponent$2("VDivider");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VTextarea = _resolveComponent$2("VTextarea");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createBlock$2(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$2(smAndDown),
    "max-width": "820",
    scrollable: "",
    "onUpdate:modelValue": _cache[2] || (_cache[2] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$2(() => [
      _createVNode$2(_component_VCard, { class: "ar-chat" }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_VToolbar, {
            density: "compact",
            class: "ar-chat__toolbar"
          }, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_VAvatar, {
                color: "primary",
                variant: "tonal",
                size: "34",
                class: "ms-3 me-3"
              }, {
                default: _withCtx$2(() => [
                  _createVNode$2(_component_VIcon, { icon: "mdi-forum-outline" })
                ]),
                _: 1
              }),
              _createElementVNode$2("div", null, [
                _cache[3] || (_cache[3] = _createElementVNode$2("div", { class: "ar-chat__title" }, "专属影评师", -1)),
                _createElementVNode$2("div", _hoisted_1$2, _toDisplayString$2(props.state.selectedUsername.value || '当前画像'), 1)
              ]),
              _createVNode$2(_component_VSpacer),
              (pendingCommands.value.length)
                ? (_openBlock$2(), _createBlock$2(_component_VBadge, {
                    key: 0,
                    content: pendingCommands.value.length,
                    color: "warning",
                    inline: ""
                  }, {
                    default: _withCtx$2(() => [
                      _createVNode$2(_component_VIcon, {
                        icon: "mdi-inbox-outline",
                        size: "20"
                      })
                    ]),
                    _: 1
                  }, 8, ["content"]))
                : _createCommentVNode$2("", true),
              _createVNode$2(_component_VBtn, {
                icon: "mdi-refresh",
                variant: "text",
                "aria-label": "刷新影评师对话",
                loading: conversationOperation.value.loading,
                onClick: load
              }, null, 8, ["loading"]),
              _createVNode$2(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭影评师对话",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$2(_component_VDivider),
          _createElementVNode$2("div", {
            ref_key: "messageList",
            ref: messageList,
            class: "ar-chat__messages"
          }, [
            (conversationOperation.value.error)
              ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                  key: 0,
                  type: "error",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  append: _withCtx$2(() => [
                    _createVNode$2(_component_VBtn, {
                      variant: "text",
                      size: "small",
                      onClick: _cache[0] || (_cache[0] = $event => (props.state.retryOperation('conversation')))
                    }, {
                      default: _withCtx$2(() => [...(_cache[4] || (_cache[4] = [
                        _createTextVNode$2("重试", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(conversationOperation.value.error.message) + " ", 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode$2("", true),
            (!messages.value.length && !conversationOperation.value.loading)
              ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_2$2, [
                  _createVNode$2(_component_VIcon, {
                    icon: "mdi-forum-outline",
                    size: "34",
                    color: "primary"
                  }),
                  _cache[5] || (_cache[5] = _createElementVNode$2("span", null, "还没有对话记录", -1))
                ]))
              : _createCommentVNode$2("", true),
            (_openBlock$2(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(messages.value, (message) => {
              return (_openBlock$2(), _createElementBlock$1("div", {
                key: message.message_id,
                class: _normalizeClass(["ar-chat__message", `ar-chat__message--${message.role}`])
              }, [
                _createElementVNode$2("div", {
                  class: _normalizeClass(["ar-chat__bubble", { 'ar-chat__bubble--failed': message.status === 'failed' }])
                }, [
                  _createElementVNode$2("div", _hoisted_3$2, _toDisplayString$2(message.content), 1),
                  _createElementVNode$2("div", _hoisted_4$2, [
                    _createElementVNode$2("span", null, _toDisplayString$2(formatTime(message.created_at)), 1),
                    (message.role === 'assistant' && (message.provider || message.model))
                      ? (_openBlock$2(), _createElementBlock$1("span", _hoisted_5$1, _toDisplayString$2([message.provider, message.model].filter(Boolean).join(' · ')), 1))
                      : _createCommentVNode$2("", true)
                  ]),
                  (message.status === 'failed')
                    ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_6$1, [
                        _createElementVNode$2("span", null, _toDisplayString$2(message.error_message || '消息处理失败'), 1),
                        _createVNode$2(_component_VBtn, {
                          size: "x-small",
                          variant: "text",
                          "prepend-icon": "mdi-refresh",
                          onClick: $event => (retryMessage(message.message_id))
                        }, {
                          default: _withCtx$2(() => [...(_cache[6] || (_cache[6] = [
                            _createTextVNode$2("重试", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    : _createCommentVNode$2("", true)
                ], 2)
              ], 2))
            }), 128)),
            (pendingCommands.value.length)
              ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_7$1, [
                  _cache[9] || (_cache[9] = _createElementVNode$2("div", { class: "ar-chat__commands-title" }, "待确认操作", -1)),
                  (_openBlock$2(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(pendingCommands.value, (command) => {
                    return (_openBlock$2(), _createElementBlock$1("div", {
                      key: command.command_id,
                      class: "ar-chat__command"
                    }, [
                      _createElementVNode$2("div", _hoisted_8$1, [
                        _createElementVNode$2("strong", null, _toDisplayString$2(command.title), 1),
                        _createElementVNode$2("span", null, _toDisplayString$2(command.preview), 1)
                      ]),
                      _createElementVNode$2("div", _hoisted_9$1, [
                        _createVNode$2(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          onClick: $event => (respondCommand(command, 'reject'))
                        }, {
                          default: _withCtx$2(() => [...(_cache[7] || (_cache[7] = [
                            _createTextVNode$2("拒绝", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"]),
                        _createVNode$2(_component_VBtn, {
                          size: "small",
                          color: "primary",
                          variant: "tonal",
                          disabled: command.requires_superuser,
                          onClick: $event => (respondCommand(command, 'confirm'))
                        }, {
                          default: _withCtx$2(() => [...(_cache[8] || (_cache[8] = [
                            _createTextVNode$2("确认", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled", "onClick"])
                      ])
                    ]))
                  }), 128))
                ]))
              : _createCommentVNode$2("", true)
          ], 512),
          _createVNode$2(_component_VDivider),
          _createElementVNode$2("div", _hoisted_10, [
            _createVNode$2(_component_VTextarea, {
              modelValue: draft.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((draft).value = $event)),
              label: "给专属影评师留言",
              density: "compact",
              variant: "outlined",
              rows: "2",
              "auto-grow": "",
              "max-rows": "5",
              maxlength: "1000",
              "hide-details": "",
              onKeydown: _withKeys$1(_withModifiers$1(send, ["exact","prevent"]), ["enter"])
            }, null, 8, ["modelValue", "onKeydown"]),
            _createVNode$2(_component_VBtn, {
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
            ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                key: 0,
                type: "error",
                variant: "tonal",
                density: "compact",
                class: "ar-chat__composer-error"
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(localError.value || sendOperation.value.error?.message), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$2("", true)
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const CriticChatDialog = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-66f09ab8"]]);

const {unref:_unref$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString$1,withCtx:_withCtx$1,withModifiers:_withModifiers,withKeys:_withKeys,createTextVNode:_createTextVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1} = await importShared('vue');


const _hoisted_1$1 = { class: "ar-comment__heading" };
const _hoisted_2$1 = { class: "ar-comment__subtitle" };
const _hoisted_3$1 = { class: "ar-comment__label" };
const _hoisted_4$1 = { class: "ar-comment__judgment" };

const {computed: computed$1,ref: ref$1,watch: watch$1} = await importShared('vue');

const {useDisplay: useDisplay$1} = await importShared('vuetify');



const _sfc_main$1 = {
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
const comment = ref$1('');
const localError = ref$1('');

const candidateId = computed$1(() => String(props.item?.candidate_id || ''));
const operation = computed$1(() => props.state.operationState(`analysis-comment:${candidateId.value}`));
const canSubmit = computed$1(() => comment.value.trim().length >= 2 && !operation.value.loading);

watch$1(
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
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VToolbar = _resolveComponent$1("VToolbar");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VTextarea = _resolveComponent$1("VTextarea");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$1(smAndDown),
    "max-width": "620",
    "onUpdate:modelValue": _cache[1] || (_cache[1] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCard, { class: "ar-comment" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VToolbar, {
            density: "compact",
            class: "ar-comment__toolbar"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VIcon, {
                icon: "mdi-comment-edit-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode$1("div", _hoisted_1$1, [
                _cache[2] || (_cache[2] = _createElementVNode$1("div", { class: "ar-comment__title" }, "评论 Agent 判断", -1)),
                _createElementVNode$1("div", _hoisted_2$1, _toDisplayString$1(__props.item?.title || '当前推荐'), 1)
              ]),
              _createVNode$1(_component_VSpacer),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭评论窗口",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardText, { class: "ar-comment__body" }, {
            default: _withCtx$1(() => [
              _createElementVNode$1("div", _hoisted_3$1, _toDisplayString$1(__props.judgment?.label || 'Agent判断'), 1),
              _createElementVNode$1("div", _hoisted_4$1, _toDisplayString$1(__props.judgment?.content || '当前判断内容未返回'), 1),
              _createVNode$1(_component_VTextarea, {
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
                onKeydown: _withKeys(_withModifiers(submit, ["ctrl","prevent"]), ["enter"])
              }, null, 8, ["modelValue", "onKeydown"]),
              (localError.value || operation.value.error)
                ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                    key: 0,
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    class: "mt-2"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(localError.value || operation.value.error?.message), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true)
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardActions, { class: "ar-comment__actions" }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VSpacer),
              _createVNode$1(_component_VBtn, {
                variant: "text",
                onClick: close
              }, {
                default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                  _createTextVNode$1("取消", -1)
                ]))]),
                _: 1
              }),
              _createVNode$1(_component_VBtn, {
                color: "primary",
                variant: "flat",
                "prepend-icon": "mdi-send-outline",
                loading: operation.value.loading,
                disabled: !canSubmit.value,
                onClick: submit
              }, {
                default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
                  _createTextVNode$1("提交评论", -1)
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
const FeedbackCommentDialog = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-ad9ce515"]]);

const {unref:_unref,resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,mergeProps:_mergeProps} = await importShared('vue');


const _hoisted_1 = { class: "ar-pending__subtitle" };
const _hoisted_2 = {
  key: 1,
  class: "ar-pending__state"
};
const _hoisted_3 = {
  key: 3,
  class: "ar-pending__list"
};
const _hoisted_4 = { class: "ar-pending__item-head" };
const _hoisted_5 = { class: "ar-pending__item-title" };
const _hoisted_6 = { class: "ar-pending__summary" };
const _hoisted_7 = {
  key: 0,
  class: "ar-pending__details"
};
const _hoisted_8 = {
  key: 1,
  class: "ar-pending__answer"
};
const _hoisted_9 = { class: "ar-pending__actions" };

const {computed,reactive,ref,watch} = await importShared('vue');

const {useDisplay} = await importShared('vuetify');



const _sfc_main = {
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
const answers = reactive({});
const localError = ref('');

const items = computed(() => props.state.pendingCenter.value?.items || []);
const operation = computed(() => props.state.operationState('pending'));
const typeLabels = { proposal: '偏好提案', question: '需要回答', command: '操作确认' };
const reminderLabels = { unselected: '未设置', in_1_day: '1天后', in_3_days: '3天后', in_7_days: '7天后', never: '不提醒' };
const reminderOptions = [
  { value: 'in_1_day', title: '1天后提醒' },
  { value: 'in_3_days', title: '3天后提醒' },
  { value: 'in_7_days', title: '7天后提醒' },
  { value: 'never', title: '不提醒' },
];

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
  catch (error) { localError.value = error?.message || '待确认项目读取失败'; }
}

async function respond(item, action, options = {}) {
  localError.value = '';
  try {
    await props.state.respondPending(item, action, options);
    emit('changed');
  } catch (error) {
    localError.value = error?.message || '待确认操作失败';
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

watch(() => props.modelValue, open => { if (open) load(); }, { immediate: true });

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VRadio = _resolveComponent("VRadio");
  const _component_VRadioGroup = _resolveComponent("VRadioGroup");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VMenu = _resolveComponent("VMenu");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createBlock(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref(smAndDown),
    "max-width": "820",
    scrollable: "",
    "onUpdate:modelValue": _cache[0] || (_cache[0] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCard, { class: "ar-pending" }, {
        default: _withCtx(() => [
          _createVNode(_component_VToolbar, {
            density: "compact",
            class: "ar-pending__toolbar"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-inbox-outline",
                color: "primary",
                class: "ms-4 me-3"
              }),
              _createElementVNode("div", null, [
                _cache[1] || (_cache[1] = _createElementVNode("div", { class: "ar-pending__title" }, "待确认", -1)),
                _createElementVNode("div", _hoisted_1, _toDisplayString(items.value.length) + " 项待处理", 1)
              ]),
              _createVNode(_component_VSpacer),
              _createVNode(_component_VBtn, {
                icon: "mdi-refresh",
                variant: "text",
                "aria-label": "刷新待确认项目",
                loading: operation.value.loading,
                onClick: load
              }, null, 8, ["loading"]),
              _createVNode(_component_VBtn, {
                icon: "mdi-close",
                variant: "text",
                "aria-label": "关闭待确认窗口",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode(_component_VDivider),
          _createVNode(_component_VCardText, { class: "ar-pending__body" }, {
            default: _withCtx(() => [
              (localError.value || operation.value.error)
                ? (_openBlock(), _createBlock(_component_VAlert, {
                    key: 0,
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    class: "mb-3"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(localError.value || operation.value.error?.message), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode("", true),
              (operation.value.loading && !items.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
                    _createVNode(_component_VProgressCircular, {
                      indeterminate: "",
                      color: "primary"
                    })
                  ]))
                : (!items.value.length)
                  ? (_openBlock(), _createBlock(_component_VEmptyState, {
                      key: 2,
                      icon: "mdi-check-all",
                      title: "当前没有待确认项目"
                    }))
                  : (_openBlock(), _createElementBlock("div", _hoisted_3, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(items.value, (item) => {
                        return (_openBlock(), _createElementBlock("section", {
                          key: `${item.item_type}:${item.item_id}`,
                          class: "ar-pending__item"
                        }, [
                          _createElementVNode("div", _hoisted_4, [
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: "primary",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(typeLabels[item.item_type] || '待确认'), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", null, _toDisplayString(formatTime(item.created_at)), 1),
                            _createVNode(_component_VSpacer),
                            (item.reminder_policy && item.reminder_policy !== 'unselected')
                              ? (_openBlock(), _createBlock(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  variant: "outlined"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(reminderLabels[item.reminder_policy] || '已设置提醒'), 1)
                                  ]),
                                  _: 2
                                }, 1024))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_5, _toDisplayString(item.title), 1),
                          _createElementVNode("div", _hoisted_6, _toDisplayString(item.summary), 1),
                          (item.detail_lines?.length)
                            ? (_openBlock(), _createElementBlock("ul", _hoisted_7, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.detail_lines, (line) => {
                                  return (_openBlock(), _createElementBlock("li", { key: line }, _toDisplayString(line), 1))
                                }), 128))
                              ]))
                            : _createCommentVNode("", true),
                          (item.item_type === 'question')
                            ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                                _createVNode(_component_VRadioGroup, {
                                  modelValue: answerState(item).optionId,
                                  "onUpdate:modelValue": $event => ((answerState(item).optionId) = $event),
                                  density: "compact",
                                  "hide-details": ""
                                }, {
                                  default: _withCtx(() => [
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.options || [], (option) => {
                                      return (_openBlock(), _createBlock(_component_VRadio, {
                                        key: option.option_id,
                                        label: option.label,
                                        value: option.option_id
                                      }, null, 8, ["label", "value"]))
                                    }), 128))
                                  ]),
                                  _: 2
                                }, 1032, ["modelValue", "onUpdate:modelValue"]),
                                (item.allow_custom_answer)
                                  ? (_openBlock(), _createBlock(_component_VTextField, {
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
                                  : _createCommentVNode("", true)
                              ]))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_9, [
                            _createVNode(_component_VMenu, null, {
                              activator: _withCtx(({ props: menuProps }) => [
                                _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, menuProps, {
                                  size: "small",
                                  variant: "text",
                                  "append-icon": "mdi-chevron-down"
                                }), {
                                  default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                                    _createTextVNode("稍后", -1)
                                  ]))]),
                                  _: 1
                                }, 16)
                              ]),
                              default: _withCtx(() => [
                                _createVNode(_component_VList, { density: "compact" }, {
                                  default: _withCtx(() => [
                                    (_openBlock(), _createElementBlock(_Fragment, null, _renderList(reminderOptions, (reminder) => {
                                      return _createVNode(_component_VListItem, {
                                        key: reminder.value,
                                        title: reminder.title,
                                        onClick: $event => (respond(item, 'remind', { reminderPolicy: reminder.value }))
                                      }, null, 8, ["title", "onClick"])
                                    }), 64))
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "text",
                              color: "error",
                              onClick: $event => (respond(item, 'reject'))
                            }, {
                              default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
                                _createTextVNode("拒绝", -1)
                              ]))]),
                              _: 1
                            }, 8, ["onClick"]),
                            (item.item_type === 'question')
                              ? (_openBlock(), _createBlock(_component_VBtn, {
                                  key: 0,
                                  size: "small",
                                  color: "primary",
                                  variant: "tonal",
                                  loading: itemOperation(item).loading,
                                  onClick: $event => (answerQuestion(item))
                                }, {
                                  default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                                    _createTextVNode("回答", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "onClick"]))
                              : (_openBlock(), _createBlock(_component_VBtn, {
                                  key: 1,
                                  size: "small",
                                  color: "primary",
                                  variant: "tonal",
                                  loading: itemOperation(item).loading,
                                  disabled: item.requires_superuser,
                                  onClick: $event => (respond(item, 'confirm'))
                                }, {
                                  default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                                    _createTextVNode("确认", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "disabled", "onClick"]))
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
const PendingConfirmations = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-f32ba1ea"]]);

export { AgentAnalysisDialog as A, CriticChatDialog as C, FeedbackCommentDialog as F, PendingConfirmations as P };
