import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi } from './_plugin-vue_export-helper-DyVawm7J.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "dm-config" };
const _hoisted_2 = { class: "dm-body" };
const _hoisted_3 = { class: "dm-nav" };
const _hoisted_4 = { class: "dm-content" };
const _hoisted_5 = { class: "dm-subtabs" };
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "dm-window" };
const _hoisted_8 = { class: "dm-pane" };
const _hoisted_9 = { class: "dm-pane" };
const _hoisted_10 = { class: "dm-pane" };
const _hoisted_11 = { class: "dm-pane" };
const _hoisted_12 = { class: "dm-pane" };
const _hoisted_13 = { class: "dm-pane" };
const _hoisted_14 = { class: "dm-pane" };
const _hoisted_15 = { class: "dm-hint" };
const _hoisted_16 = { class: "dm-hint" };
const _hoisted_17 = { class: "dm-pane" };
const _hoisted_18 = { class: "dm-pane" };

const {reactive,ref,computed,watch,onMounted} = await importShared('vue');


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

const form = reactive({});
const activeMain = ref('transfer');
const activeSub = ref('basic');
const downloaderItems = ref([]);
const siteItems = ref([]);

onMounted(async () => {
  try {
    const [dlResp, siteResp] = await Promise.all([
      getPluginApi(props.api, 'downloaders'),
      getPluginApi(props.api, 'sites'),
    ]);
    if (dlResp) {
      downloaderItems.value = dlResp;
    }
    if (siteResp) {
      siteItems.value = siteResp;
    }
  } catch (e) {
    console.error('获取列表失败:', e);
  }
});

const defaults = {
  enabled: false, transfer_enabled: true, delay_minutes: 25, onlyonce: false, notify: false,
  transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 60,
  fromdownloader: '', todownloader: '', frompath: '', topath: '',
  fromtorrentpath: '', nopaths: '', nolabels: '', includelabels: '', includecategory: '',
  transferemptylabel: false, add_torrent_tags: '⏩转种',
  deletesource: false, deleteduplicate: false,
  remainoldcat: false, remainoldtag: false,
  rename_enabled: true,
  rename_movie_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}',
  rename_tv_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}',
  rename_exclude_dirs: '',
  tag_enabled: true, tag_siteprefix: '🏠', tag_tracker_mappings_str: '',
  iyuu_enabled: false, iyuu_cron: '', iyuu_onlyonce: false,
  iyuu_token: '', iyuu_downloaders: [], iyuu_auto_downloader: '',
  iyuu_sites: [], iyuu_nolabels: '', iyuu_nopaths: '',
  iyuu_size: 0, iyuu_auto_category: false,
  iyuu_labelsafterseed: '已整理,辅种', iyuu_categoryafterseed: '',
  iyuu_clearcache: false,
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
};

const mainTabs = [
  { key: 'transfer', title: '转移做种', icon: 'mdi-transfer', desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'iyuu', title: 'IYUU辅种', icon: 'mdi-seed-plus', desc: '基于 IYUU API 自动辅种，铺种后自动打站点标签。' },
  { key: 'rename', title: '种子重命名', icon: 'mdi-rename-box', desc: '转移后自动根据 TMDB 信息重命名种子名称。' },
  { key: 'tag', title: '站点标签', icon: 'mdi-tag-multiple', desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'seed', title: '做种校验', icon: 'mdi-check-circle-outline', desc: '统一控制跳过校验和自动开始做种，按需触发。' },
];

const subTabs = {
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-variant' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  iyuu: [
    { key: 'iyuu_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'iyuu_filter', title: '筛选条件', icon: 'mdi-filter-variant' },
    { key: 'iyuu_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  rename: [{ key: 'format', title: '命名格式', icon: 'mdi-format-text' }],
  tag: [{ key: 'mapping', title: 'Tracker 映射', icon: 'mdi-link-variant' }],
  seed: [{ key: 'seed_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
};

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0]);
const currentSubs = computed(() => subTabs[activeMain.value] || []);

watch(() => props.initialConfig, v => {
  Object.keys(form).forEach(k => delete form[k]);
  Object.assign(form, defaults, v || {});
}, { immediate: true, deep: true });

function saveConfig() { emit('save', { ...form }); }
function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key;
  activeSub.value = subTabs[key]?.[0]?.key || '';
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
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "dm-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "dm-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "success",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-download",
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
              label: form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                _createTextVNode("下载中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(currentMain.value.desc), 1)
              ]),
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
              class: "py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "dm-nav-item",
                    onClick: $event => (selectMain(item.key))
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
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(currentSubs.value, (sub) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: sub.key,
                  type: "button",
                  class: _normalizeClass(["dm-subtab", { 'dm-subtab--active': activeSub.value === sub.key }]),
                  onClick: $event => (activeSub.value = sub.key)
                }, [
                  _createVNode(_component_VIcon, {
                    icon: sub.icon,
                    size: "18",
                    class: "mr-1"
                  }, null, 8, ["icon"]),
                  _createTextVNode(_toDisplayString(sub.title), 1)
                ], 10, _hoisted_6))
              }), 128))
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", _hoisted_7, [
              _withDirectives(_createElementVNode("div", _hoisted_8, [
                _cache[49] || (_cache[49] = _createElementVNode("div", { class: "dm-section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.fromdownloader,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.fromdownloader) = $event)),
                          label: "源下载器",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          items: downloaderItems.value,
                          hint: "选择源下载器",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.todownloader,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.todownloader) = $event)),
                          label: "目的下载器",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          items: downloaderItems.value,
                          hint: "选择目的下载器",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.frompath,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.frompath) = $event)),
                          label: "源数据文件根路径",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "源下载器中数据的根路径",
                          "persistent-hint": ""
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
                          modelValue: form.topath,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.topath) = $event)),
                          label: "目的数据文件根路径",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "目标下载器中数据的根路径",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.fromtorrentpath,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.fromtorrentpath) = $event)),
                          label: "源种子文件路径",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "如 BT_backup，留空自动获取",
                          "persistent-hint": ""
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
                          modelValue: form.add_torrent_tags,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.add_torrent_tags) = $event)),
                          label: "添加种子标签",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "多个以逗号分隔",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.transfer_enabled,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.transfer_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用转移做种"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.notify) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "发送通知"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.onlyonce,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.onlyonce) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.delay_minutes,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.delay_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "延迟时间（分钟）",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "下载完成后延迟 N 分钟再转移",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.transfer_fallback_enabled,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.transfer_fallback_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "转移做种兜底服务"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.transfer_fallback_interval_minutes,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.transfer_fallback_interval_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "兜底间隔（分钟）",
                          type: "number",
                          min: "1",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !form.transfer_fallback_enabled,
                          hint: "事件漏触发时按此间隔扫描，默认60分钟",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_9, [
                _cache[50] || (_cache[50] = _createElementVNode("div", { class: "dm-section-title" }, "筛选条件", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.includelabels,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.includelabels) = $event)),
                          label: "转移种子标签（逗号分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "仅转移包含这些标签的种子",
                          "persistent-hint": ""
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
                          modelValue: form.nolabels,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.nolabels) = $event)),
                          label: "不转移种子标签（逗号分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "跳过包含这些标签的种子",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.includecategory,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.includecategory) = $event)),
                          label: "转移种子分类（逗号分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "仅转移这些分类的种子",
                          "persistent-hint": ""
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
                          modelValue: form.transferemptylabel,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.transferemptylabel) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "转移无标签种子"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.nopaths,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.nopaths) = $event)),
                          label: "不转移数据文件目录（每行一个）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "3"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_10, [
                _cache[51] || (_cache[51] = _createElementVNode("div", { class: "dm-section-title" }, "高级选项", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.deletesource,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.deletesource) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "删除源种子"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.deleteduplicate,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.deleteduplicate) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "删除重复种子"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.remainoldcat,
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.remainoldcat) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "保留原分类"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.remainoldtag,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.remainoldtag) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "保留原标签"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'advanced']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_11, [
                _cache[52] || (_cache[52] = _createElementVNode("div", { class: "dm-section-title" }, "IYUU 辅种设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.iyuu_enabled,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.iyuu_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用辅种"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.iyuu_onlyonce,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.iyuu_onlyonce) = $event)),
                          color: "warning",
                          inset: "",
                          "hide-details": "",
                          label: "立即运行一次"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.iyuu_clearcache,
                          "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.iyuu_clearcache) = $event)),
                          color: "error",
                          inset: "",
                          "hide-details": "",
                          label: "清除缓存后运行"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.iyuu_token,
                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.iyuu_token) = $event)),
                          label: "IYUU Token",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "在 https://iyuu.cn 获取",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.iyuu_cron,
                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.iyuu_cron) = $event)),
                          label: "执行周期",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.iyuu_downloaders,
                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((form.iyuu_downloaders) = $event)),
                          label: "辅种下载器",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          items: downloaderItems.value,
                          multiple: "",
                          chips: "",
                          clearable: "",
                          hint: "选择辅种目标下载器",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.iyuu_auto_downloader,
                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((form.iyuu_auto_downloader) = $event)),
                          label: "主辅分离",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          items: downloaderItems.value,
                          clearable: "",
                          hint: "辅种专用下载器（可选）",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.iyuu_sites,
                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((form.iyuu_sites) = $event)),
                          label: "辅种站点",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          items: siteItems.value,
                          multiple: "",
                          chips: "",
                          clearable: "",
                          hint: "选择允许辅种的站点，留空表示全部站点",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.iyuu_size,
                          "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((form.iyuu_size) = $event)),
                          modelModifiers: { number: true },
                          label: "辅种体积大于(GB)",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "只有大于该值的才辅种",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'iyuu_basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_12, [
                _cache[53] || (_cache[53] = _createElementVNode("div", { class: "dm-section-title" }, "辅种筛选", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.iyuu_nolabels,
                          "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((form.iyuu_nolabels) = $event)),
                          label: "不辅种标签（逗号分隔）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "跳过包含这些标签的种子",
                          "persistent-hint": ""
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
                          modelValue: form.iyuu_labelsafterseed,
                          "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((form.iyuu_labelsafterseed) = $event)),
                          label: "辅种后增加标签",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "逗号分隔，默认：已整理,辅种",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.iyuu_categoryafterseed,
                          "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((form.iyuu_categoryafterseed) = $event)),
                          label: "辅种后增加分类",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "设置辅种种子的分类",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.iyuu_nopaths,
                          "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => ((form.iyuu_nopaths) = $event)),
                          label: "不辅种数据文件目录（每行一个）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "3"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'iyuu_filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_13, [
                _cache[54] || (_cache[54] = _createElementVNode("div", { class: "dm-section-title" }, "辅种高级选项", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.iyuu_auto_category,
                          "onUpdate:modelValue": _cache[35] || (_cache[35] = $event => ((form.iyuu_auto_category) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "分类复用(QB有效)"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'iyuu_advanced']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_14, [
                _cache[55] || (_cache[55] = _createElementVNode("div", { class: "dm-section-title" }, "重命名设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.rename_enabled,
                          "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => ((form.rename_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用重命名"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.rename_movie_format,
                          "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((form.rename_movie_format) = $event)),
                          label: "电影命名格式 (Jinja2)",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "2"
                        }, null, 8, ["modelValue"]),
                        _createElementVNode("div", _hoisted_15, "可用变量: " + _toDisplayString(_ctx.title) + ", " + _toDisplayString(_ctx.year) + ", " + _toDisplayString(_ctx.original_name), 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.rename_tv_format,
                          "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((form.rename_tv_format) = $event)),
                          label: "电视剧命名格式 (Jinja2)",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "2"
                        }, null, 8, ["modelValue"]),
                        _createElementVNode("div", _hoisted_16, "可用变量: " + _toDisplayString(_ctx.title) + ", " + _toDisplayString(_ctx.year) + ", " + _toDisplayString(_ctx.season_episode) + ", " + _toDisplayString(_ctx.original_name), 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.rename_exclude_dirs,
                          "onUpdate:modelValue": _cache[39] || (_cache[39] = $event => ((form.rename_exclude_dirs) = $event)),
                          label: "排除目录（每行一个）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'format']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_17, [
                _cache[57] || (_cache[57] = _createElementVNode("div", { class: "dm-section-title" }, "站点标签设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.tag_enabled,
                          "onUpdate:modelValue": _cache[40] || (_cache[40] = $event => ((form.tag_enabled) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用站点标签"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.tag_siteprefix,
                          "onUpdate:modelValue": _cache[41] || (_cache[41] = $event => ((form.tag_siteprefix) = $event)),
                          label: "站点标签前缀",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: form.tag_tracker_mappings_str,
                          "onUpdate:modelValue": _cache[42] || (_cache[42] = $event => ((form.tag_tracker_mappings_str) = $event)),
                          label: "Tracker 映射（每行: 域名 -> 映射域名）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          rows: "4"
                        }, null, 8, ["modelValue"]),
                        _cache[56] || (_cache[56] = _createElementVNode("div", { class: "dm-hint" }, "例: tracker.example.com -> example", -1))
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'mapping']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_18, [
                _cache[59] || (_cache[59] = _createElementVNode("div", { class: "dm-section-title" }, "做种校验设置", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [...(_cache[58] || (_cache[58] = [
                    _createTextVNode("做种校验采用按需触发：仅在转移做种、IYUU铺种或手动补刀添加种子后启动。队列为空后自动停止。", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.seed_autostart,
                          "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((form.seed_autostart) = $event)),
                          color: "success",
                          inset: "",
                          "hide-details": "",
                          label: "启用自动开始做种"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.seed_skipverify,
                          "onUpdate:modelValue": _cache[44] || (_cache[44] = $event => ((form.seed_skipverify) = $event)),
                          color: "info",
                          inset: "",
                          "hide-details": "",
                          label: "跳过校验(QB有效)"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, { class: "mt-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.seed_check_interval,
                          "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((form.seed_check_interval) = $event)),
                          modelModifiers: { number: true },
                          label: "校验检查间隔（秒）",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "建议 60 秒",
                          "persistent-hint": ""
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
                          modelValue: form.seed_max_wait_minutes,
                          "onUpdate:modelValue": _cache[46] || (_cache[46] = $event => ((form.seed_max_wait_minutes) = $event)),
                          modelModifiers: { number: true },
                          label: "最大等待时间（分钟）",
                          type: "number",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          hint: "超时后移出队列",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeSub.value === 'seed_basic']
              ])
            ])
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "dm-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[47] || (_cache[47] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
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
              default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                _createTextVNode("保存配置", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ae8e3cd0"]]);

export { Config as default };
