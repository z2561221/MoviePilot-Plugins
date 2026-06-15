import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-DyVawm7J.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "dm-page" };
const _hoisted_2 = { class: "pa-3" };
const _hoisted_3 = {
  key: 3,
  class: "text-center text-medium-emphasis py-8"
};
const _hoisted_4 = { class: "text-caption text-no-wrap" };
const _hoisted_5 = ["title"];
const _hoisted_6 = ["title"];
const _hoisted_7 = { class: "d-flex ga-1" };

const {ref,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const records = ref([]);
const loading = ref(true);
const error = ref('');
const actionMsg = ref('');

async function loadHistory() {
  loading.value = true;
  error.value = '';
  try {
    const resp = await getPluginApi(props.api, 'rename_history');
    records.value = Array.isArray(resp) ? resp : [];
  } catch (e) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function doRecovery(hash) {
  actionMsg.value = '';
  try {
    const resp = await postPluginApi(props.api, 'recovery_torrent', { hash });
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败');
    if (resp?.code === 0) await loadHistory();
  } catch (e) {
    actionMsg.value = e?.message || '恢复失败';
  }
}

async function doDelete(hash) {
  actionMsg.value = '';
  try {
    const resp = await postPluginApi(props.api, 'delete_rename_history', { hash });
    actionMsg.value = resp?.msg || '已删除';
    if (resp?.code === 0) await loadHistory();
  } catch (e) {
    actionMsg.value = e?.message || '删除失败';
  }
}

onMounted(loadHistory);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTable = _resolveComponent("VTable");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "dm-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-rename-box",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-h6" }, "下载管理 · 重命名历史", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: loadHistory,
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (actionMsg.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: actionMsg.value.includes('成功') || actionMsg.value.includes('已') ? 'success' : 'error',
            variant: "tonal",
            class: "mb-3",
            closable: "",
            density: "compact"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(actionMsg.value), 1)
            ]),
            _: 1
          }, 8, ["type"]))
        : _createCommentVNode("", true),
      (error.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            type: "error",
            variant: "tonal",
            class: "mb-3",
            density: "compact"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(error.value), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (loading.value)
        ? (_openBlock(), _createBlock(_component_VProgressCircular, {
            key: 2,
            indeterminate: "",
            color: "primary",
            class: "d-block mx-auto my-8"
          }))
        : (records.value.length === 0)
          ? (_openBlock(), _createElementBlock("div", _hoisted_3, [
              _createVNode(_component_VIcon, {
                icon: "mdi-history",
                size: "48",
                color: "grey-lighten-1",
                class: "mb-2"
              }),
              _cache[5] || (_cache[5] = _createElementVNode("div", null, "暂无重命名记录", -1))
            ]))
          : (_openBlock(), _createBlock(_component_VTable, {
              key: 4,
              density: "compact",
              class: "dm-table"
            }, {
              default: _withCtx(() => [
                _cache[8] || (_cache[8] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", { class: "text-caption" }, "时间"),
                    _createElementVNode("th", { class: "text-caption" }, "原始名称"),
                    _createElementVNode("th", { class: "text-caption" }, "重命名后"),
                    _createElementVNode("th", { class: "text-caption" }, "状态"),
                    _createElementVNode("th", { class: "text-caption" }, "操作")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (r) => {
                    return (_openBlock(), _createElementBlock("tr", {
                      key: r.hash
                    }, [
                      _createElementVNode("td", _hoisted_4, _toDisplayString(r.time), 1),
                      _createElementVNode("td", {
                        class: "text-caption",
                        style: {"max-width":"240px","overflow":"hidden","text-overflow":"ellipsis","white-space":"nowrap"},
                        title: r.original_name
                      }, _toDisplayString(r.original_name), 9, _hoisted_5),
                      _createElementVNode("td", {
                        class: "text-caption",
                        style: {"max-width":"240px","overflow":"hidden","text-overflow":"ellipsis","white-space":"nowrap"},
                        title: r.after_name
                      }, _toDisplayString(r.after_name), 9, _hoisted_6),
                      _createElementVNode("td", null, [
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          color: r.success ? 'success' : 'error',
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(r.success ? '成功' : (r.reason || '失败')), 1)
                          ]),
                          _: 2
                        }, 1032, ["color"])
                      ]),
                      _createElementVNode("td", null, [
                        _createElementVNode("div", _hoisted_7, [
                          (r.success)
                            ? (_openBlock(), _createBlock(_component_VBtn, {
                                key: 0,
                                size: "x-small",
                                variant: "tonal",
                                color: "warning",
                                onClick: $event => (doRecovery(r.hash))
                              }, {
                                default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                                  _createTextVNode("恢复", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick"]))
                            : _createCommentVNode("", true),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            color: "error",
                            onClick: $event => (doDelete(r.hash))
                          }, {
                            default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                              _createTextVNode("删除", -1)
                            ]))]),
                            _: 1
                          }, 8, ["onClick"])
                        ])
                      ])
                    ]))
                  }), 128))
                ])
              ]),
              _: 1
            }))
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-9b4a25e1"]]);

export { Page as default };
