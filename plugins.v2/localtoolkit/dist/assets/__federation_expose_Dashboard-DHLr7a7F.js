import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as apiGet } from './_plugin-vue_export-helper-CufXJ4_7.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString} = await importShared('vue');


const _hoisted_1 = { class: "dash-row" };
const _hoisted_2 = { class: "dash-row" };
const _hoisted_3 = { class: "dash-row" };

const {ref,onMounted} = await importShared('vue');

const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: false },
},
  setup(__props) {

const props = __props;
const status = ref(null);
const loading = ref(false);
async function load() {
  loading.value = true;
  try {
    status.value = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/status');
  } catch(e) {
  } finally {
    loading.value = false;
  }
}
onMounted(load);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    class: "toolkit-dashboard",
    variant: "flat"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, null, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "teal",
            variant: "tonal",
            rounded: "lg"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-tools" })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          (__props.allowRefresh)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 0,
                icon: "mdi-refresh",
                variant: "text",
                size: "small",
                loading: loading.value,
                onClick: load
              }, null, 8, ["loading"]))
            : _createCommentVNode("", true)
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, null, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("工具中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("清理库存 / 扫描缺集 / 清理TMDB", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCardText, null, {
        default: _withCtx(() => [
          _createElementVNode("div", _hoisted_1, [
            _cache[2] || (_cache[2] = _createElementVNode("span", null, "清库存周期", -1)),
            _createElementVNode("strong", null, _toDisplayString(status.value?.modules?.library_cleanup?.enabled ? '开启' : '关闭'), 1)
          ]),
          _createElementVNode("div", _hoisted_2, [
            _cache[3] || (_cache[3] = _createElementVNode("span", null, "查漏路径", -1)),
            _createElementVNode("strong", null, _toDisplayString(status.value?.modules?.check_missing?.paths || 0) + " 个", 1)
          ]),
          _createElementVNode("div", _hoisted_3, [
            _cache[4] || (_cache[4] = _createElementVNode("span", null, "TMDB缓存", -1)),
            _createElementVNode("strong", null, _toDisplayString(status.value?.modules?.tmdb_cache?.keys || 0) + " 键", 1)
          ])
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-64680cb7"]]);

export { Dashboard as default };
