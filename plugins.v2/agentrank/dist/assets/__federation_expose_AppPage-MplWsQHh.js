import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi } from './api-DsxprKU3.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,Fragment:_Fragment,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "ar-app-page pa-4" };
const _hoisted_2 = { class: "pa-5" };

const {onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
},
  emits: ['action'],
  setup(__props) {

const props = __props;


const loading = ref(true);
const status = ref({ state: 'idle', message: '等待加载' });

async function loadStatus() {
  loading.value = true;
  try {
    status.value = (await getPluginApi(props.api, 'status')) || status.value;
  } catch (error) {
    status.value = { state: 'error', message: error?.message || '状态加载失败' };
  } finally {
    loading.value = false;
  }
}

onMounted(loadStatus);

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
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "ar-app-page__card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, null, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              rounded: "lg"
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
              loading: loading.value,
              "aria-label": "刷新榜单状态",
              onClick: loadStatus
            }, null, 8, ["loading"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
                _createTextVNode("Agent榜单中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
              default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
                _createTextVNode("从 MoviePilot 发现候选中生成个性化 Top 10", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_2, [
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
                key: 0,
                type: "article, article"
              }))
            : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(status.value.message), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VEmptyState, {
                  icon: "mdi-format-list-numbered",
                  title: "推荐榜单尚未生成",
                  text: "完成后端推荐链路后，这里将展示固定单列 Top 10。"
                })
              ], 64))
        ])
      ]),
      _: 1
    })
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c32790c3"]]);

export { AppPage as default };
