import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-MvqT7xFW.js';
import Page from './__federation_expose_Page-B8J-1gaA.js';
import { _ as _export_sfc, s as savePluginConfig } from './_plugin-vue_export-helper-Z-mQLghu.js';

const {openBlock:_openBlock,createBlock:_createBlock,createVNode:_createVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = ["data-nav-key", "data-plugin-id"];

const {ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
},
  setup(__props) {

const props = __props;

const settingsDialog = ref(false);
const savingSettings = ref(false);
const settingsConfig = ref({});
const pageKey = ref(0);
const snackbar = ref({ show: false, message: '', color: 'success' });

function openSettings(config = {}) {
  settingsConfig.value = { ...(config || {}) };
  settingsDialog.value = true;
}

async function saveSettings(config) {
  savingSettings.value = true;
  try {
    await savePluginConfig(props.api, config);
    settingsConfig.value = { ...(config || {}) };
    settingsDialog.value = false;
    pageKey.value += 1;
    snackbar.value = { show: true, message: '设置已保存', color: 'success' };
  } catch (error) {
    snackbar.value = {
      show: true,
      message: error?.message || '设置保存失败',
      color: 'error',
    };
  } finally {
    savingSettings.value = false;
  }
}

return (_ctx, _cache) => {
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", {
    class: "ar-app-page",
    "data-nav-key": __props.navKey,
    "data-plugin-id": __props.pluginId
  }, [
    (_openBlock(), _createBlock(Page, {
      key: pageKey.value,
      api: __props.api,
      "native-subscribe": __props.nativeSubscribe,
      "show-close": false,
      onSwitch: openSettings
    }, null, 8, ["api", "native-subscribe"])),
    _createVNode(_component_VDialog, {
      modelValue: settingsDialog.value,
      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((settingsDialog).value = $event)),
      "max-width": "1160",
      persistent: savingSettings.value
    }, {
      default: _withCtx(() => [
        _createVNode(Config, {
          api: __props.api,
          "initial-config": settingsConfig.value,
          onSave: saveSettings,
          onClose: _cache[0] || (_cache[0] = $event => (settingsDialog.value = false))
        }, null, 8, ["api", "initial-config"])
      ]),
      _: 1
    }, 8, ["modelValue", "persistent"]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((snackbar.value.show) = $event)),
      color: snackbar.value.color,
      timeout: "5000"
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(snackbar.value.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ], 8, _hoisted_1))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-7509d169"]]);

export { AppPage as default };
