import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Page from './__federation_expose_Page-CYd2uEg9.js';

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {


const emit = __emit;

return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(Page, {
    api: __props.api,
    "plugin-id": __props.pluginId,
    onClose: _cache[0] || (_cache[0] = $event => (emit('close'))),
    onSwitch: _cache[1] || (_cache[1] = $event => (emit('switch', $event)))
  }, null, 8, ["api", "plugin-id"]))
}
}

};

export { _sfc_main as default };
