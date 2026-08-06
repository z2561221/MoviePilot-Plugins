import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-D7T2o8L8.js';
import Page from './__federation_expose_Page-CfuTKxF9.js';
import { _ as _export_sfc, g as getPluginConfig, s as savePluginConfig } from './_plugin-vue_export-helper-Cd7yiqDA.js';

const {openBlock:_openBlock,createBlock:_createBlock,resolveComponent:_resolveComponent,createCommentVNode:_createCommentVNode,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "dc-app-page" };

const {ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'DoubanCenter' },
},
  setup(__props) {

const props = __props;

const settingsDialog = ref(false);
const loadingSettings = ref(false);
const savingSettings = ref(false);
const settingsConfig = ref({});
const pageKey = ref(0);
const snackbar = ref({ show: false, message: '', color: 'success' });

async function openSettings() {
  loadingSettings.value = true;
  try {
    settingsConfig.value = await getPluginConfig(props.api);
    settingsDialog.value = true;
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置加载失败', color: 'error' };
  } finally {
    loadingSettings.value = false;
  }
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
    snackbar.value = { show: true, message: error?.message || '设置保存失败', color: 'error' };
  } finally {
    savingSettings.value = false;
  }
}

return (_ctx, _cache) => {
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("main", _hoisted_1, [
    (_openBlock(), _createBlock(Page, {
      key: `${props.pluginId}-${props.navKey}-${pageKey.value}`,
      api: props.api,
      "native-subscribe": props.nativeSubscribe,
      "app-page": "",
      "show-settings": "",
      onSwitch: openSettings
    }, null, 8, ["api", "native-subscribe"])),
    _createVNode(_component_VDialog, {
      modelValue: settingsDialog.value,
      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((settingsDialog).value = $event)),
      "max-width": "1160",
      persistent: savingSettings.value || loadingSettings.value
    }, {
      default: _withCtx(() => [
        (loadingSettings.value)
          ? (_openBlock(), _createBlock(_component_VProgressLinear, {
              key: 0,
              indeterminate: "",
              color: "primary"
            }))
          : _createCommentVNode("", true),
        (!loadingSettings.value)
          ? (_openBlock(), _createBlock(Config, {
              key: 1,
              api: props.api,
              "initial-config": settingsConfig.value,
              onSave: saveSettings,
              onClose: _cache[0] || (_cache[0] = $event => (settingsDialog.value = false))
            }, null, 8, ["api", "initial-config"]))
          : _createCommentVNode("", true)
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
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c4d3ed84"]]);

export { AppPage as default };
