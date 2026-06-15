import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

function unwrapResponse(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(`plugin/DoubanCenter/${path}`);
  return unwrapResponse(response)
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "dc-dashboard" };
const _hoisted_2 = { class: "dc-timeline-wrap" };
const _hoisted_3 = {
  key: 0,
  class: "text-center py-12"
};
const _hoisted_4 = {
  key: 1,
  class: "text-center py-12"
};
const _hoisted_5 = { class: "text-body-1 text-error mt-2" };
const _hoisted_6 = {
  key: 2,
  class: "text-center py-12"
};
const _hoisted_7 = {
  key: 3,
  class: "dc-timeline"
};
const _hoisted_8 = { class: "dc-month-header" };
const _hoisted_9 = { class: "dc-month-label" };
const _hoisted_10 = { class: "dc-poster-row" };
const _hoisted_11 = ["href", "title"];
const _hoisted_12 = { class: "dc-poster-placeholder" };

const {ref,computed,onMounted,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const folioData = ref({});
const loading = ref(true);
const error = ref('');

const pcMonth = ref(3);
const pcNum = ref(50);
const mobileMonth = ref(2);
const mobileNum = ref(15);

const isMobile = computed(() => {
  if (typeof navigator === 'undefined') return false
  return /Mobile|Android|iPhone|iPad/i.test(navigator.userAgent)
});

const limitMonth = computed(() => isMobile.value ? mobileMonth.value : pcMonth.value);
const limitNum = computed(() => isMobile.value ? mobileNum.value : pcNum.value);

const timelineGroups = computed(() => {
  const data = folioData.value;
  if (!data || typeof data !== 'object') return []

  const entries = Object.entries(data)
    .filter(([_, v]) => v && typeof v === 'object' && v.timestamp)
    .map(([key, val]) => ({ key, ...val }))
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  const groups = [];
  let currentMonth = null;
  let currentGroup = null;

  for (const entry of entries) {
    const date = new Date(entry.timestamp);
    const monthKey = `${date.getFullYear()}-${date.getMonth() + 1}`;

    if (monthKey !== currentMonth) {
      if (groups.length >= limitMonth.value) break
      currentMonth = monthKey;
      currentGroup = {
        month: date.getMonth() + 1,
        year: date.getFullYear(),
        label: `${date.getFullYear()}年${date.getMonth() + 1}月`,
        items: [],
      };
      groups.push(currentGroup);
    }

    if (currentGroup.items.length < limitNum.value) {
      const poster = entry.poster_path || '';
      const w200 = poster.replace('/original/', '/w200/');
      currentGroup.items.push({
        key: entry.key,
        subject_name: entry.subject_name || entry.key,
        subject_id: entry.subject_id,
        timestamp: entry.timestamp,
        poster: w200,
        type: entry.type || '',
      });
    }
  }

  return groups
});

async function loadData() {
  loading.value = true;
  error.value = '';
  try {
    if (!props.api || !props.api.get) {
      error.value = 'API 未就绪，请刷新页面重试';
      return
    }
    const resp = await getPluginApi(props.api, 'folio_data');
    folioData.value = resp || {};
  } catch (e) {
    error.value = '加载数据失败: ' + (e?.message || String(e));
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function loadConfig() {
  try {
    if (!props.api || !props.api.get) return
    const resp = await getPluginApi(props.api, 'config');
    if (resp) {
      pcMonth.value = resp.folio_pc_month || 3;
      pcNum.value = resp.folio_pc_num || 50;
      mobileMonth.value = resp.folio_mobile_month || 2;
      mobileNum.value = resp.folio_mobile_num || 15;
    }
  } catch (e) {
    // ignore
  }
}

onMounted(async () => {
  await loadConfig();
  await loadData();
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "dc-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-book-open-page-variant-outline",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-h6" }, "豆瓣档案 · 时间线", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          size: "small",
          "prepend-icon": "mdi-refresh",
          class: "text-none me-2",
          onClick: loadData,
          loading: loading.value
        }, {
          default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-cog-outline",
          class: "text-none",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (loading.value)
        ? (_openBlock(), _createElementBlock("div", _hoisted_3, [
            _createVNode(_component_VProgressCircular, {
              indeterminate: "",
              color: "primary",
              size: "40"
            }),
            _cache[5] || (_cache[5] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mt-3" }, "加载中...", -1))
          ]))
        : (error.value)
          ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
              _createVNode(_component_VIcon, {
                icon: "mdi-alert-circle-outline",
                size: "48",
                color: "error"
              }),
              _createElementVNode("div", _hoisted_5, _toDisplayString(error.value), 1)
            ]))
          : (timelineGroups.value.length === 0)
            ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                _createVNode(_component_VIcon, {
                  icon: "mdi-book-open-page-variant-outline",
                  size: "64",
                  color: "grey-lighten-1"
                }),
                _cache[6] || (_cache[6] = _createElementVNode("div", { class: "text-h6 text-medium-emphasis mt-3" }, "暂无观影档案", -1)),
                _cache[7] || (_cache[7] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mt-1" }, " 开始播放媒体库中的内容后，观影记录将自动同步到豆瓣并在此展示。 ", -1))
              ]))
            : (_openBlock(), _createElementBlock("div", _hoisted_7, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timelineGroups.value, (group, gi) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: gi,
                    class: "dc-month-group"
                  }, [
                    _createElementVNode("div", _hoisted_8, [
                      _createElementVNode("span", _hoisted_9, _toDisplayString(group.label), 1),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        color: "primary",
                        variant: "tonal",
                        class: "ml-2"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(" 看过 " + _toDisplayString(group.items.length) + " 部 ", 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _createElementVNode("div", _hoisted_10, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                        return (_openBlock(), _createElementBlock("a", {
                          key: item.key,
                          href: `https://www.douban.com/doubanapp/dispatch?uri=/movie/${item.subject_id}?from=mdouban&open=app`,
                          target: "_blank",
                          class: "dc-poster-link",
                          title: `${item.subject_name}\n${item.timestamp}`
                        }, [
                          _createVNode(_component_VCard, {
                            class: "dc-poster-card",
                            variant: "outlined"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VImg, {
                                src: item.poster,
                                width: isMobile.value ? 44 : 66,
                                height: isMobile.value ? 66 : 99,
                                cover: "",
                                "aspect-ratio": "2/3",
                                class: "dc-poster-img"
                              }, {
                                placeholder: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_12, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-movie-open-outline",
                                      size: "24",
                                      color: "grey-lighten-1"
                                    })
                                  ])
                                ]),
                                _: 1
                              }, 8, ["src", "width", "height"])
                            ]),
                            _: 2
                          }, 1024)
                        ], 8, _hoisted_11))
                      }), 128))
                    ])
                  ]))
                }), 128))
              ]))
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5f83d2c4"]]);

export { Page as default };
