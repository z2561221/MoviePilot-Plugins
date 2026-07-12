import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState } from './useAgentRankState-DMJYFSWp.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-BKA7AlB8.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = {
  key: 3,
  class: "ar-dashboard__list"
};
const _hoisted_2 = { class: "ar-dashboard__rank" };
const _hoisted_3 = { class: "ar-dashboard__poster" };
const _hoisted_4 = { class: "ar-dashboard__poster-error" };
const _hoisted_5 = { class: "ar-dashboard__main" };
const _hoisted_6 = { class: "font-weight-medium text-truncate" };
const _hoisted_7 = { class: "text-caption text-medium-emphasis text-truncate" };

const {computed,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
},
  setup(__props) {

const props = __props;
const state = useAgentRankState(props.api);

const topItems = computed(() => (state.board.value?.recommendations || []).slice(0, 5));
const fullBoardHref = computed(() => {
  const pluginId = String(props.config?.id || 'AgentRank').trim() || 'AgentRank';
  return `#/plugin-app/${encodeURIComponent(pluginId)}/main`
});
const status = computed(() => state.board.value?.status || 'idle');
const generatedAt = computed(() => state.board.value?.generated_at || '');
const statusMeta = computed(() => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
}[status.value] || { text: status.value, color: 'info' }));

function formatTime(value) {
  if (!value) return '尚未生成'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function initialize() {
  try {
    await state.loadOptions();
    if (props.config?.default_user && state.users.value.includes(props.config.default_user)) {
      state.selectedUser.value = props.config.default_user;
    }
    if (state.selectedUser.value) await state.loadUserData();
  } catch (_) { /* 卡片内显示共享错误 */ }
}

async function refreshBoard() {
  try { await state.refresh(); } catch (_) { /* 卡片内显示共享错误 */ }
}

function openFullBoard() {
  window.location.hash = fullBoardHref.value.slice(1);
}

onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    variant: "flat",
    class: "ar-dashboard"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, null, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            size: "38"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-brain" })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            icon: "mdi-refresh",
            variant: "text",
            size: "small",
            disabled: !__props.allowRefresh || _unref(state).isRunning.value,
            loading: _unref(state).loading.action === 'refresh' || _unref(state).loading.data,
            "aria-label": "刷新仪表板",
            onClick: refreshBoard
          }, null, 8, ["disabled", "loading"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "text-subtitle-1 font-weight-bold" }, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("Agent榜单中心 · Top 5", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(formatTime(generatedAt.value)) + " · " + _toDisplayString(statusMeta.value.text), 1)
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "ar-dashboard__content" }, {
        default: _withCtx(() => [
          (_unref(state).loading.data)
            ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
                key: 0,
                type: "list-item-three-line@3"
              }))
            : (_unref(state).error.value)
              ? (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "error",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(_unref(state).error.value.message), 1)
                  ]),
                  _: 1
                }))
              : (!topItems.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 2,
                    icon: "mdi-format-list-numbered",
                    title: "推荐榜单尚未生成",
                    text: "打开完整榜单或点击刷新开始生成。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_1, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(topItems.value, (item) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: item.candidate_id,
                        class: "ar-dashboard__item"
                      }, [
                        _createElementVNode("div", _hoisted_2, _toDisplayString(item.rank), 1),
                        _createElementVNode("div", _hoisted_3, [
                          (item.poster_path)
                            ? (_openBlock(), _createBlock(_component_VImg, {
                                key: 0,
                                src: item.poster_path,
                                alt: `${item.title} 海报`,
                                cover: "",
                                eager: ""
                              }, {
                                error: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_4, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-image-off-outline",
                                      size: "18"
                                    })
                                  ])
                                ]),
                                _: 1
                              }, 8, ["src", "alt"]))
                            : (_openBlock(), _createBlock(_component_VIcon, {
                                key: 1,
                                icon: "mdi-image-off-outline",
                                size: "18"
                              }))
                        ]),
                        _createElementVNode("div", _hoisted_5, [
                          _createElementVNode("div", _hoisted_6, _toDisplayString(item.title), 1),
                          _createElementVNode("div", _hoisted_7, _toDisplayString(item.summary), 1)
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
                        }, 1024)
                      ]))
                    }), 128))
                  ]))
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardActions, null, {
        default: _withCtx(() => [
          _createVNode(_component_VChip, {
            size: "small",
            variant: "tonal",
            color: statusMeta.value.color
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(statusMeta.value.text), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            variant: "text",
            color: "primary",
            "prepend-icon": "mdi-open-in-new",
            onClick: openFullBoard
          }, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("完整榜单", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-dfaa3a49"]]);

export { Dashboard as default };
