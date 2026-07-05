import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as apiGet, b as apiPost } from './_plugin-vue_export-helper-DFDyaOGw.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "toolkit-page pa-4" };
const _hoisted_2 = { class: "d-flex align-center mb-2" };
const _hoisted_3 = { class: "text-h6" };
const _hoisted_4 = { class: "module-desc" };
const _hoisted_5 = { class: "mt-3" };
const _hoisted_6 = { class: "d-flex align-center" };
const _hoisted_7 = { class: "text-caption mx-1" };
const _hoisted_8 = { class: "history-mobile" };
const _hoisted_9 = { class: "history-mobile-main" };
const _hoisted_10 = { class: "history-mobile-title" };
const _hoisted_11 = { class: "history-mobile-summary" };
const _hoisted_12 = { class: "history-mobile-meta" };
const _hoisted_13 = {
  key: 0,
  class: "text-center text-medium-emphasis py-6"
};
const _hoisted_14 = { key: 0 };

const {ref,onMounted,computed} = await importShared('vue');

const pageSize = 10;


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: Object, default: () => ({}) } },
  emits: ['close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const status = ref(null);
const history = ref([]);
const total = ref(0);
const loadingModule = ref('');
const result = ref(null);
const page = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)));
const pagedHistory = computed(() => history.value || []);

const modules = computed(() => [
  {
    key: 'library_cleanup',
    title: '清理库存',
    icon: 'mdi-delete-sweep-outline',
    color: 'error',
    action: '立即执行',
    mode: '周期 + 按需',
    desc: '唯一支持后台周期运行的模块，手动执行也会遵循自动删除策略。',
    meta: [
      `周期：${status.value?.modules?.library_cleanup?.enabled ? '开启' : '关闭'}`,
      `自动删除：${status.value?.modules?.library_cleanup?.auto_delete ? '开启' : '关闭'}`,
      `Cron：${status.value?.modules?.library_cleanup?.cron || '未设置'}`,
    ],
  },
  {
    key: 'check_missing',
    title: '扫描缺集',
    icon: 'mdi-magnify-scan',
    color: 'primary',
    action: '立即扫描',
    mode: '按需单次',
    desc: '扫描配置路径，按已存在季检查缺集，不注册后台周期服务。',
    meta: [
      `路径：${status.value?.modules?.check_missing?.paths || 0} 个`,
      `上次结果：${status.value?.modules?.check_missing?.last_count || 0} 条`,
      '后台周期：无',
    ],
  },
  {
    key: 'tmdb_cache',
    title: '清理TMDB',
    icon: 'mdi-database-refresh-outline',
    color: 'warning',
    action: '立即清理',
    mode: '按需单次',
    desc: '查询并清理 Redis 中的 TMDB 缓存，不注册后台周期服务。',
    meta: [
      `缓存键：${status.value?.modules?.tmdb_cache?.keys || 0}`,
      `大小：${((status.value?.modules?.tmdb_cache?.size_kb || 0) / 1024).toFixed(2)} MB`,
      status.value?.modules?.tmdb_cache?.error ? `错误：${status.value.modules.tmdb_cache.error}` : '后台周期：无',
    ],
  },
]);

async function load() {
  try {
    status.value = await apiGet(props.api, 'plugin/LocalToolkit/local_toolkit/status');
    const hist = await apiGet(props.api, `plugin/LocalToolkit/local_toolkit/history?page=${page.value}&page_size=${pageSize}`);
    history.value = hist.items || [];
    total.value = hist.total || 0;
  } catch (e) {
    result.value = { success: false, message: String(e) };
  }
}

async function run(moduleKey) {
  loadingModule.value = moduleKey;
  try {
    result.value = await apiPost(props.api, `plugin/LocalToolkit/local_toolkit/run/${moduleKey}`);
  } catch (e) {
    result.value = { success: false, message: String(e) };
  } finally {
    loadingModule.value = '';
    await load();
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value--;
    load();
  }
}
function nextPage() {
  if (page.value < totalPages.value) {
    page.value++;
    load();
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
  const _component_VCard = _resolveComponent("VCard");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VTable = _resolveComponent("VTable");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      class: "hero mb-4",
      variant: "flat"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, null, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "teal",
              variant: "tonal",
              rounded: "lg",
              size: "48"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-tools",
                  size: "28"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-refresh",
              onClick: load
            }, {
              default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode("刷新", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              icon: "mdi-close",
              onClick: _cache[0] || (_cache[0] = $event => (emit('close'))),
              class: "ml-1"
            })
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
                _createTextVNode("工具中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
              default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                _createTextVNode("清理库存保留周期运行；扫描缺集与清理TMDB改为按需单次执行。", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (result.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: result.value.success !== false ? 'success' : 'error',
          variant: "tonal",
          class: "mb-4",
          text: result.value.message || result.value.summary || JSON.stringify(result.value)
        }, null, 8, ["type", "text"]))
      : _createCommentVNode("", true),
    _createVNode(_component_VRow, { class: "mb-4" }, {
      default: _withCtx(() => [
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(modules.value, (item) => {
          return (_openBlock(), _createBlock(_component_VCol, {
            key: item.key,
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCard, {
                class: "module-card",
                color: item.color,
                variant: "tonal"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardText, null, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_2, [
                        _createVNode(_component_VIcon, {
                          icon: item.icon,
                          size: "24",
                          class: "mr-2"
                        }, null, 8, ["icon"]),
                        _createElementVNode("div", null, [
                          _createElementVNode("div", _hoisted_3, _toDisplayString(item.title), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: item.color,
                            variant: "flat"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(item.mode), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ])
                      ]),
                      _createElementVNode("div", _hoisted_4, _toDisplayString(item.desc), 1),
                      _createElementVNode("div", _hoisted_5, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.meta, (m) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: m,
                            class: "module-meta"
                          }, _toDisplayString(m), 1))
                        }), 128))
                      ]),
                      _createVNode(_component_VBtn, {
                        class: "mt-4",
                        block: "",
                        color: item.color,
                        variant: "flat",
                        "prepend-icon": item.icon,
                        loading: loadingModule.value === item.key,
                        onClick: $event => (run(item.key))
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.action), 1)
                        ]),
                        _: 2
                      }, 1032, ["color", "prepend-icon", "loading", "onClick"])
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1032, ["color"])
            ]),
            _: 2
          }, 1024))
        }), 128))
      ]),
      _: 1
    }),
    _createVNode(_component_VCard, {
      class: "history-card",
      variant: "flat"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, null, {
          append: _withCtx(() => [
            _createElementVNode("div", _hoisted_6, [
              _createVNode(_component_VBtn, {
                size: "x-small",
                variant: "tonal",
                icon: "mdi-chevron-left",
                disabled: page.value <= 1,
                onClick: prevPage,
                class: "mr-1"
              }, null, 8, ["disabled"]),
              _createElementVNode("span", _hoisted_7, _toDisplayString(page.value) + " / " + _toDisplayString(totalPages.value), 1),
              _createVNode(_component_VBtn, {
                size: "x-small",
                variant: "tonal",
                icon: "mdi-chevron-right",
                disabled: page.value >= totalPages.value,
                onClick: nextPage
              }, null, 8, ["disabled"])
            ])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode("运行历史", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
              default: _withCtx(() => [
                _createTextVNode("每页 10 条，共 " + _toDisplayString(total.value || 0) + " 条记录。", 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_8, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedHistory.value, (h, i) => {
            return (_openBlock(), _createElementBlock("div", {
              key: `mobile-${(page.value - 1) * pageSize + i}`,
              class: "history-mobile-item"
            }, [
              _createElementVNode("div", _hoisted_9, [
                _createElementVNode("div", _hoisted_10, _toDisplayString(h.module_name), 1),
                _createVNode(_component_VChip, {
                  size: "x-small",
                  color: h.status === 'success' ? 'success' : 'error',
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(h.status), 1)
                  ]),
                  _: 2
                }, 1032, ["color"])
              ]),
              _createElementVNode("div", _hoisted_11, _toDisplayString(h.summary), 1),
              _createElementVNode("div", _hoisted_12, [
                _createElementVNode("span", null, _toDisplayString(h.time), 1),
                _createElementVNode("span", null, _toDisplayString(h.duration) + "s", 1)
              ])
            ]))
          }), 128)),
          (!pagedHistory.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_13, "暂无运行历史"))
            : _createCommentVNode("", true)
        ]),
        _createVNode(_component_VTable, {
          class: "history-table",
          density: "compact"
        }, {
          default: _withCtx(() => [
            _cache[6] || (_cache[6] = _createElementVNode("thead", null, [
              _createElementVNode("tr", null, [
                _createElementVNode("th", null, "时间"),
                _createElementVNode("th", null, "模块"),
                _createElementVNode("th", null, "状态"),
                _createElementVNode("th", null, "摘要"),
                _createElementVNode("th", null, "耗时")
              ])
            ], -1)),
            _createElementVNode("tbody", null, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedHistory.value, (h, i) => {
                return (_openBlock(), _createElementBlock("tr", {
                  key: (page.value - 1) * pageSize + i
                }, [
                  _createElementVNode("td", null, _toDisplayString(h.time), 1),
                  _createElementVNode("td", null, _toDisplayString(h.module_name), 1),
                  _createElementVNode("td", null, [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      color: h.status === 'success' ? 'success' : 'error',
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(h.status), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"])
                  ]),
                  _createElementVNode("td", null, _toDisplayString(h.summary), 1),
                  _createElementVNode("td", null, _toDisplayString(h.duration) + "s", 1)
                ]))
              }), 128)),
              (!pagedHistory.value.length)
                ? (_openBlock(), _createElementBlock("tr", _hoisted_14, [...(_cache[5] || (_cache[5] = [
                    _createElementVNode("td", {
                      colspan: "5",
                      class: "text-center text-medium-emphasis py-6"
                    }, "暂无运行历史", -1)
                  ]))]))
                : _createCommentVNode("", true)
            ])
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d97a1624"]]);

export { Page as default };
