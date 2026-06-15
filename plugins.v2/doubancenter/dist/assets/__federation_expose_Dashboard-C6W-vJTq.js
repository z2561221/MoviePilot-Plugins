import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_2 = {
  key: 2,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_3 = {
  key: 3,
  class: "dc-timeline"
};
const _hoisted_4 = { class: "dc-month-head" };
const _hoisted_5 = { class: "dc-month-label" };
const _hoisted_6 = { class: "dc-posters" };
const _hoisted_7 = ["href", "title"];
const _hoisted_8 = { class: "dc-placeholder" };

const {ref,computed,onMounted,onUnmounted} = await importShared('vue');



const _sfc_main = {
  __name: 'Dashboard',
  props: {
  config: { type: Object, default: () => ({}) },
  api: { type: [Object, Function], default: null },
},
  setup(__props) {

const props = __props;

const attrs = computed(() => props.config?.attrs || {});
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
      currentGroup = { month: date.getMonth() + 1, year: date.getFullYear(), label: `${date.getFullYear()}年${date.getMonth() + 1}月`, items: [] };
      groups.push(currentGroup);
    }
    if (currentGroup.items.length < limitNum.value) {
      const poster = entry.poster_path || '';
      currentGroup.items.push({
        key: entry.key, subject_name: entry.subject_name || entry.key,
        subject_id: entry.subject_id, timestamp: entry.timestamp,
        poster: poster.replace('/original/', '/w200/'), type: entry.type || '',
      });
    }
  }
  return groups
});

let _timer = null;

function unwrap(resp) {
  const d = resp?.data ?? resp;
  return (d && typeof d === 'object' && 'data' in d) ? d.data : d
}

async function loadData() {
  loading.value = true;
  error.value = '';
  try {
    if (!props.api?.get) { error.value = 'API未就绪'; return }
    const resp = await props.api.get('plugin/DoubanCenter/folio_data');
    folioData.value = unwrap(resp) || {};
  } catch (e) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadConfig() {
  try {
    if (!props.api?.get) return
    const resp = await props.api.get('plugin/DoubanCenter/config');
    const cfg = unwrap(resp);
    if (cfg) {
      pcMonth.value = cfg.folio_pc_month || 3;
      pcNum.value = cfg.folio_pc_num || 50;
      mobileMonth.value = cfg.folio_mobile_month || 2;
      mobileNum.value = cfg.folio_mobile_num || 15;
    }
  } catch (e) { /* ignore */ }
}

onMounted(async () => {
  await loadConfig();
  await loadData();
  if (attrs.value?.refresh) {
    _timer = setInterval(loadData, attrs.value.refresh * 1000);
  }
});

onUnmounted(() => {
  if (_timer) { clearInterval(_timer); _timer = null; }
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardText = _resolveComponent("VCardText");

  return (_openBlock(), _createBlock(_component_VCard, {
    class: _normalizeClass(["dc-dash", attrs.value.border !== false ? 'elevation-4' : '']),
    rounded: "lg"
  }, {
    default: _withCtx(() => [
      (attrs.value.title)
        ? (_openBlock(), _createBlock(_component_VCardItem, {
            key: 0,
            class: "pb-1"
          }, {
            prepend: _withCtx(() => [
              _createVNode(_component_VAvatar, {
                color: "primary",
                variant: "tonal",
                size: "36",
                rounded: "lg"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-book-open-page-variant-outline",
                    size: "20"
                  })
                ]),
                _: 1
              })
            ]),
            default: _withCtx(() => [
              _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(attrs.value.title), 1)
                ]),
                _: 1
              }),
              (attrs.value.subtitle)
                ? (_openBlock(), _createBlock(_component_VCardSubtitle, {
                    key: 0,
                    class: "text-caption"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(attrs.value.subtitle), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode("", true)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (attrs.value.title)
        ? (_openBlock(), _createBlock(_component_VDivider, { key: 1 }))
        : _createCommentVNode("", true),
      _createVNode(_component_VCardText, { class: "pa-3" }, {
        default: _withCtx(() => [
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                key: 0,
                indeterminate: "",
                color: "primary",
                size: "32",
                class: "d-block mx-auto my-4"
              }))
            : (error.value)
              ? (_openBlock(), _createElementBlock("div", _hoisted_1, _toDisplayString(error.value), 1))
              : (timelineGroups.value.length === 0)
                ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-book-open-page-variant-outline",
                      size: "32",
                      color: "grey-lighten-1",
                      class: "mb-1"
                    }),
                    _cache[0] || (_cache[0] = _createElementVNode("div", null, "暂无观影档案", -1))
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_3, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timelineGroups.value, (group, gi) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: gi,
                        class: "dc-month"
                      }, [
                        _createElementVNode("div", _hoisted_4, [
                          _createElementVNode("span", _hoisted_5, _toDisplayString(group.label), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: "primary",
                            variant: "tonal",
                            class: "ml-1"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode("看过 " + _toDisplayString(group.items.length) + " 部", 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _createElementVNode("div", _hoisted_6, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                            return (_openBlock(), _createElementBlock("a", {
                              key: item.key,
                              href: 'https://www.douban.com/doubanapp/dispatch?uri=/movie/' + item.subject_id + '?from=mdouban&open=app',
                              target: "_blank",
                              class: "dc-poster-link",
                              title: item.subject_name + '\n' + item.timestamp
                            }, [
                              _createVNode(_component_VCard, {
                                class: "dc-poster-card",
                                variant: "outlined"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VImg, {
                                    src: item.poster,
                                    width: isMobile.value ? 44 : 64,
                                    height: isMobile.value ? 66 : 96,
                                    cover: "",
                                    "aspect-ratio": "2/3"
                                  }, {
                                    placeholder: _withCtx(() => [
                                      _createElementVNode("div", _hoisted_8, [
                                        _createVNode(_component_VIcon, {
                                          icon: "mdi-movie-open-outline",
                                          size: "18",
                                          color: "grey-lighten-1"
                                        })
                                      ])
                                    ]),
                                    _: 1
                                  }, 8, ["src", "width", "height"])
                                ]),
                                _: 2
                              }, 1024)
                            ], 8, _hoisted_7))
                          }), 128))
                        ])
                      ]))
                    }), 128))
                  ]))
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["class"]))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-27337eeb"]]);

export { Dashboard as default };
