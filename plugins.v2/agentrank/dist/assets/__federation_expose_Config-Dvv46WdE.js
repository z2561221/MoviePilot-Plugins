import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "ar-config" };
const _hoisted_2 = { class: "ar-config__body" };
const _hoisted_3 = { class: "ar-config__nav" };
const _hoisted_4 = { class: "ar-config__content" };
const _hoisted_5 = { class: "ar-config__subtabs" };
const _hoisted_6 = {
  class: "ar-config__subtab ar-config__subtab--active",
  type: "button"
};
const _hoisted_7 = {
  key: 0,
  class: "ar-config__pane"
};
const _hoisted_8 = {
  key: 1,
  class: "ar-config__pane"
};
const _hoisted_9 = {
  key: 2,
  class: "ar-config__pane"
};

const {computed,reactive,ref,watch} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const defaults = {
  enabled: false,
  schedule_enabled: false,
  cron: '0 8 * * *',
  notify: true,
};
const form = reactive({ ...defaults });
const activeMain = ref('overview');

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical' },
  { key: 'filter', title: '条件筛选', icon: 'mdi-filter-outline' },
  { key: 'board', title: '榜单列表', icon: 'mdi-format-list-numbered' },
  { key: 'advanced', title: '高级选项', icon: 'mdi-shield-cog-outline' },
];
const currentTitle = computed(
  () => mainTabs.find(item => item.key === activeMain.value)?.title || '运行总览',
);

watch(
  () => props.initialConfig,
  value => Object.assign(form, defaults, value || {}),
  { immediate: true, deep: true },
);

function saveConfig() {
  emit('save', { ...form });
}

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "ar-config__card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "ar-config__header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-brain",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              label: "启用插件"
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                _createTextVNode("Agent榜单中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
              default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                _createTextVNode("配置用户画像、发现来源与推荐行为", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_2, [
          _createElementVNode("nav", _hoisted_3, [
            _createVNode(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "ar-config__nav-list py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "ar-config__nav-item",
                    onClick: $event => (activeMain.value = item.key)
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["active", "onClick"])
                }), 64))
              ]),
              _: 1
            })
          ]),
          _createElementVNode("section", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _createElementVNode("button", _hoisted_6, _toDisplayString(currentTitle.value), 1)
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", {
              class: _normalizeClass(["ar-config__window", { 'ar-config__window--overview': activeMain.value === 'overview' }])
            }, [
              (activeMain.value === 'overview')
                ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                    _cache[9] || (_cache[9] = _createElementVNode("div", { class: "text-subtitle-2 text-primary mb-3" }, "运行链路", -1)),
                    _createVNode(_component_VAlert, {
                      type: "info",
                      variant: "tonal",
                      icon: "mdi-transit-connection-variant"
                    }, {
                      default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                        _createTextVNode(" 读取订阅 → 拉取发现候选 → Agent画像排序 → 校验并更新榜单 ", -1)
                      ]))]),
                      _: 1
                    }),
                    _cache[10] || (_cache[10] = _createElementVNode("div", { class: "text-subtitle-2 mt-5 mb-2" }, "当前状态", -1)),
                    _createVNode(_component_VChip, {
                      color: "info",
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                        _createTextVNode("骨架已就绪", -1)
                      ]))]),
                      _: 1
                    })
                  ]))
                : (activeMain.value === 'basic')
                  ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                      _cache[11] || (_cache[11] = _createElementVNode("div", { class: "text-subtitle-2 text-primary mb-3" }, "基础设置", -1)),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.schedule_enabled,
                                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.schedule_enabled) = $event)),
                                color: "success",
                                label: "周期运行",
                                "hide-details": "",
                                inset: ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.cron,
                                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.cron) = $event)),
                                label: "运行周期",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.notify,
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.notify) = $event)),
                                color: "info",
                                label: "发送通知",
                                "hide-details": "",
                                inset: ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_9, [
                      _createVNode(_component_VAlert, {
                        type: "info",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                          _createTextVNode("该配置区将在对应实施阶段完成。", -1)
                        ]))]),
                        _: 1
                      })
                    ]))
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "ar-config__actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[4] || (_cache[4] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                _createTextVNode(" 保存配置 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-aa12e2e9"]]);

export { Config as default };
