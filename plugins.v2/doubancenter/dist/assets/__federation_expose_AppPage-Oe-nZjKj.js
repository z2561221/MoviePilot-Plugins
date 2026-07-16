import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Page from './__federation_expose_Page-B9oL1NiP.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-C4gmM98O.js';

const {openBlock:_openBlock,createBlock:_createBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "dc-app-page" };


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'DoubanCenter' },
},
  setup(__props) {

const props = __props;

return (_ctx, _cache) => {
  return (_openBlock(), _createElementBlock("main", _hoisted_1, [
    (_openBlock(), _createBlock(Page, {
      key: `${props.pluginId}-${props.navKey}`,
      api: props.api,
      "app-page": ""
    }, null, 8, ["api"]))
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-50106498"]]);

export { AppPage as default };
