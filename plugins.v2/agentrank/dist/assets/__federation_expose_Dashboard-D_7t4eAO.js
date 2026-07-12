import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi } from './_plugin-vue_export-helper-DOB58Uqo.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString} = await importShared('vue');


const {onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
},
  setup(__props) {

const props = __props;
const loading = ref(true);
const status = ref({});

async function loadStatus() {
  loading.value = true;
  try {
    status.value = (await getPluginApi(props.api, 'status')) || {};
  } finally {
    loading.value = false;
  }
}

onMounted(loadStatus);

return (_ctx, _cache) => {
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    variant: "flat",
    class: "ar-dashboard"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, null, {
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            icon: "mdi-refresh",
            variant: "text",
            size: "small",
            disabled: !__props.allowRefresh,
            loading: loading.value,
            "aria-label": "刷新仪表板",
            onClick: loadStatus
          }, null, 8, ["disabled", "loading"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "text-subtitle-1 font-weight-bold" }, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("Agent榜单中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("个性化推荐 Top 5", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, null, {
        default: _withCtx(() => [
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
                key: 0,
                type: "list-item-three-line"
              }))
            : (_openBlock(), _createBlock(_component_VAlert, {
                key: 1,
                type: "info",
                variant: "tonal"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(status.value.message || '推荐榜单尚未生成'), 1)
                ]),
                _: 1
              }))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c49c8d0a"]]);

export { Dashboard as default };
