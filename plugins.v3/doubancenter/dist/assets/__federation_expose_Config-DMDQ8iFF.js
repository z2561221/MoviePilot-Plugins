import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as getPluginApi } from './api-ilAfCmvf.js';

const {createElementVNode:_createElementVNode$4,resolveComponent:_resolveComponent$4,createVNode:_createVNode$4,withCtx:_withCtx$4,vShow:_vShow$3,withDirectives:_withDirectives$3,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4} = await importShared('vue');


const _hoisted_1$4 = { class: "dc-pane" };


const _sfc_main$4 = {
  __name: 'ConfigDashboardPane',
  props: {
  config: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent$4("VAlert");
  const _component_VSelect = _resolveComponent$4("VSelect");
  const _component_VCol = _resolveComponent$4("VCol");
  const _component_VSwitch = _resolveComponent$4("VSwitch");
  const _component_VRow = _resolveComponent$4("VRow");

  return _withDirectives$3((_openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
    _cache[2] || (_cache[2] = _createElementVNode$4("div", { class: "dc-section-title" }, "仪表盘选择", -1)),
    _createVNode$4(_component_VAlert, {
      type: "info",
      variant: "tonal",
      density: "compact",
      class: "mb-2",
      text: "仪表盘最多显示 6 个已启用榜单；开启发现页后，保存并刷新 MP 页面即可从左侧「发现」分组进入豆瓣中心。"
    }),
    _createVNode$4(_component_VRow, null, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx$4(() => [
            _createVNode$4(_component_VSelect, {
              modelValue: __props.config.form.dashboard_rank_keys,
              "onUpdate:modelValue": [
                _cache[0] || (_cache[0] = $event => ((__props.config.form.dashboard_rank_keys) = $event)),
                __props.config.limitDashboardRanks
              ],
              label: "选择要显示的榜单（最多 6 个）",
              items: __props.config.rankDefs.filter(rank => __props.config.form.rank_configs?.[rank.key]?.enabled).map(rank => ({ title: rank.name, value: rank.key })),
              multiple: "",
              chips: "",
              clearable: "",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue", "items", "onUpdate:modelValue"])
          ]),
          _: 1
        }),
        _createVNode$4(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx$4(() => [
            _createVNode$4(_component_VSwitch, {
              modelValue: __props.config.form.discovery_page_enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.config.form.discovery_page_enabled) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "开启发现页"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ], 512)), [
    [_vShow$3, __props.config.activeSub === 'view']
  ])
}
}

};
const ConfigDashboardPane = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-bc0addd1"]]);

const {createElementVNode:_createElementVNode$3,resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,withCtx:_withCtx$3,toDisplayString:_toDisplayString$3,vShow:_vShow$2,withDirectives:_withDirectives$2,Fragment:_Fragment$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3} = await importShared('vue');


const _hoisted_1$3 = { class: "dc-pane" };
const _hoisted_2$3 = { class: "dc-wish-status mt-3" };
const _hoisted_3$3 = { class: "dc-kv" };
const _hoisted_4$3 = { class: "dc-kv" };
const _hoisted_5$3 = { class: "dc-kv" };
const _hoisted_6$3 = { class: "dc-kv" };
const _hoisted_7$2 = { class: "dc-pane" };


const _sfc_main$3 = {
  __name: 'ConfigFolioPane',
  props: {
  config: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VSwitch = _resolveComponent$3("VSwitch");
  const _component_VCol = _resolveComponent$3("VCol");
  const _component_VCronField = _resolveComponent$3("VCronField");
  const _component_VTextField = _resolveComponent$3("VTextField");
  const _component_VRow = _resolveComponent$3("VRow");
  const _component_VAlert = _resolveComponent$3("VAlert");

  return (_openBlock$3(), _createElementBlock$3(_Fragment$3, null, [
    _withDirectives$2(_createElementVNode$3("div", _hoisted_1$3, [
      _cache[18] || (_cache[18] = _createElementVNode$3("div", { class: "dc-section-title" }, "同步想看", -1)),
      _createVNode$3(_component_VRow, null, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "3"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.wish_enabled,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((__props.config.form.wish_enabled) = $event)),
                color: "success",
                inset: "",
                "hide-details": "",
                label: "启用想看同步"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "3"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.wish_onlyonce,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.config.form.wish_onlyonce) = $event)),
                color: "warning",
                inset: "",
                "hide-details": "",
                label: "立即运行一次"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "3"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VCronField, {
                modelValue: __props.config.form.wish_cron,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.config.form.wish_cron) = $event)),
                label: "独立同步周期",
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "3"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VTextField, {
                modelValue: __props.config.form.wish_days,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.config.form.wish_days) = $event)),
                modelModifiers: { number: true },
                label: "最近天数",
                type: "number",
                min: "0",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "默认 7 天",
                "persistent-hint": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$3(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "8"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VTextField, {
                modelValue: __props.config.form.wish_user,
                "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((__props.config.form.wish_user) = $event)),
                label: "豆瓣用户 ID",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "读取该用户的动态 feed，仅处理「想看」条目",
                "persistent-hint": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.wish_notify,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((__props.config.form.wish_notify) = $event)),
                color: "info",
                inset: "",
                "hide-details": "",
                label: "发送通知"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$3(_component_VAlert, {
        class: "mt-3",
        type: "info",
        variant: "tonal",
        density: "compact",
        text: "通过豆瓣动态 feed 同步，首次只建立最近天数内的基线；后续周期只处理最近天数内新增的想看。"
      }),
      _createElementVNode$3("div", _hoisted_2$3, [
        _createElementVNode$3("div", _hoisted_3$3, [
          _cache[14] || (_cache[14] = _createElementVNode$3("span", null, "队列待处理", -1)),
          _createElementVNode$3("strong", null, _toDisplayString$3(__props.config.overview?.cards?.folio?.wish?.queue || 0), 1)
        ]),
        _createElementVNode$3("div", _hoisted_4$3, [
          _cache[15] || (_cache[15] = _createElementVNode$3("span", null, "失败记录", -1)),
          _createElementVNode$3("strong", null, _toDisplayString$3(__props.config.overview?.cards?.folio?.wish?.failed || 0), 1)
        ]),
        _createElementVNode$3("div", _hoisted_5$3, [
          _cache[16] || (_cache[16] = _createElementVNode$3("span", null, "最近运行", -1)),
          _createElementVNode$3("strong", null, _toDisplayString$3(__props.config.overview?.cards?.folio?.wish?.last_run || '尚未运行'), 1)
        ]),
        _createElementVNode$3("div", _hoisted_6$3, [
          _cache[17] || (_cache[17] = _createElementVNode$3("span", null, "状态错误", -1)),
          _createElementVNode$3("strong", null, _toDisplayString$3(__props.config.overview?.cards?.folio?.wish?.last_error || '无'), 1)
        ])
      ])
    ], 512), [
      [_vShow$2, __props.config.activeSub === 'wish']
    ]),
    _withDirectives$2(_createElementVNode$3("div", _hoisted_7$2, [
      _cache[19] || (_cache[19] = _createElementVNode$3("div", { class: "dc-section-title" }, "同步观影", -1)),
      _createVNode$3(_component_VRow, null, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.folio_enabled,
                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.config.form.folio_enabled) = $event)),
                color: "success",
                inset: "",
                "hide-details": "",
                label: "启用豆瓣时间"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.folio_private,
                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((__props.config.form.folio_private) = $event)),
                color: "info",
                inset: "",
                "hide-details": "",
                label: "仅自己可见"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.folio_first,
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.config.form.folio_first) = $event)),
                color: "info",
                inset: "",
                "hide-details": "",
                label: "不标记第一集"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$3(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.folio_notify,
                "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((__props.config.form.folio_notify) = $event)),
                color: "info",
                inset: "",
                "hide-details": "",
                label: "发送通知"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VSwitch, {
                modelValue: __props.config.form.folio_exclude_live_tv,
                "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((__props.config.form.folio_exclude_live_tv) = $event)),
                color: "info",
                inset: "",
                "hide-details": "",
                label: "排除电视直播源"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$3(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "6"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VTextField, {
                modelValue: __props.config.form.folio_user,
                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((__props.config.form.folio_user) = $event)),
                label: "媒体库用户名（多个以 , 分隔）",
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$3(_component_VCol, {
            cols: "12",
            md: "6"
          }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VTextField, {
                modelValue: __props.config.form.folio_exclude,
                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((__props.config.form.folio_exclude) = $event)),
                label: "路径排除关键词（多个以 , 分隔）",
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
      _createVNode$3(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$3(() => [
          _createVNode$3(_component_VCol, { cols: "12" }, {
            default: _withCtx$3(() => [
              _createVNode$3(_component_VTextField, {
                modelValue: __props.config.form.folio_cookie,
                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((__props.config.form.folio_cookie) = $event)),
                label: "豆瓣 Cookie（留空从 CookieCloud 获取）",
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ], 512), [
      [_vShow$2, __props.config.activeSub === 'sync']
    ])
  ], 64))
}
}

};
const ConfigFolioPane = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-e6efa55c"]]);

const {createElementVNode:_createElementVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,toDisplayString:_toDisplayString$2,resolveComponent:_resolveComponent$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$1,createVNode:_createVNode$2,withCtx:_withCtx$2} = await importShared('vue');


const _hoisted_1$2 = { class: "dc-pane dc-pane--overview" };
const _hoisted_2$2 = { class: "dc-overview-section mb-3" };
const _hoisted_3$2 = { class: "dc-flow" };
const _hoisted_4$2 = { class: "dc-flow-label" };
const _hoisted_5$2 = {
  key: 0,
  class: "dc-flow-row"
};
const _hoisted_6$2 = {
  key: 1,
  class: "dc-flow-sub"
};
const _hoisted_7$1 = { class: "dc-flow-sub-label" };
const _hoisted_8$1 = { class: "dc-flow-row dc-flow-row--sub" };
const _hoisted_9$1 = { class: "dc-stat-grid mb-3" };
const _hoisted_10$1 = { class: "d-flex align-center ga-2 mb-1" };
const _hoisted_11$1 = { class: "text-caption text-medium-emphasis" };
const _hoisted_12$1 = { class: "text-subtitle-1 font-weight-bold" };
const _hoisted_13$1 = { class: "text-caption text-medium-emphasis" };
const _hoisted_14$1 = { class: "dc-overview-grid" };
const _hoisted_15$1 = { class: "dc-overview-section" };
const _hoisted_16$1 = { class: "dc-kv" };
const _hoisted_17$1 = { class: "dc-kv" };
const _hoisted_18$1 = { class: "dc-kv" };
const _hoisted_19$1 = { class: "dc-overview-section" };
const _hoisted_20$1 = { class: "dc-kv" };
const _hoisted_21$1 = { class: "dc-kv" };
const _hoisted_22$1 = { class: "dc-kv" };


const _sfc_main$2 = {
  __name: 'ConfigOverviewPane',
  props: {
  config: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VAvatar = _resolveComponent$2("VAvatar");

  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    _createElementVNode$2("div", _hoisted_2$2, [
      _cache[0] || (_cache[0] = _createElementVNode$2("div", { class: "dc-section-title d-flex align-center" }, [
        _createElementVNode$2("span", null, "运行链路")
      ], -1)),
      _createElementVNode$2("div", _hoisted_3$2, [
        (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2((__props.config.overview?.flows || []), (flow) => {
          return (_openBlock$2(), _createElementBlock$2("div", {
            key: flow.label,
            class: "dc-flow-block"
          }, [
            _createElementVNode$2("div", _hoisted_4$2, _toDisplayString$2(flow.label), 1),
            (flow.steps?.length)
              ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_5$2, [
                  (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(flow.steps, (step, index) => {
                    return (_openBlock$2(), _createElementBlock$2(_Fragment$2, {
                      key: `${flow.label}-${step}`
                    }, [
                      _createElementVNode$2("span", null, _toDisplayString$2(step), 1),
                      (index < flow.steps.length - 1)
                        ? (_openBlock$2(), _createBlock$2(_component_VIcon, {
                            key: 0,
                            icon: "mdi-arrow-right",
                            size: "15"
                          }))
                        : _createCommentVNode$1("", true)
                    ], 64))
                  }), 128))
                ]))
              : (flow.flows?.length)
                ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_6$2, [
                    (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(flow.flows, (subFlow) => {
                      return (_openBlock$2(), _createElementBlock$2("div", {
                        key: `${flow.label}-${subFlow.label}`,
                        class: "dc-flow-sub-block"
                      }, [
                        _createElementVNode$2("div", _hoisted_7$1, _toDisplayString$2(subFlow.label), 1),
                        _createElementVNode$2("div", _hoisted_8$1, [
                          (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(subFlow.steps, (step, index) => {
                            return (_openBlock$2(), _createElementBlock$2(_Fragment$2, {
                              key: `${subFlow.label}-${step}`
                            }, [
                              _createElementVNode$2("span", null, _toDisplayString$2(step), 1),
                              (index < subFlow.steps.length - 1)
                                ? (_openBlock$2(), _createBlock$2(_component_VIcon, {
                                    key: 0,
                                    icon: "mdi-arrow-right",
                                    size: "15"
                                  }))
                                : _createCommentVNode$1("", true)
                            ], 64))
                          }), 128))
                        ])
                      ]))
                    }), 128))
                  ]))
                : _createCommentVNode$1("", true)
          ]))
        }), 128))
      ])
    ]),
    _createElementVNode$2("div", _hoisted_9$1, [
      (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.config.overviewCards, (card) => {
        return (_openBlock$2(), _createElementBlock$2("div", {
          key: card.title,
          class: "dc-stat"
        }, [
          _createElementVNode$2("div", _hoisted_10$1, [
            _createVNode$2(_component_VAvatar, {
              color: card.color,
              variant: "tonal",
              size: "28",
              rounded: "lg"
            }, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_VIcon, {
                  icon: card.icon,
                  size: "17"
                }, null, 8, ["icon"])
              ]),
              _: 2
            }, 1032, ["color"]),
            _createElementVNode$2("div", _hoisted_11$1, _toDisplayString$2(card.title), 1)
          ]),
          _createElementVNode$2("div", _hoisted_12$1, _toDisplayString$2(card.value), 1),
          _createElementVNode$2("div", _hoisted_13$1, _toDisplayString$2(card.desc), 1)
        ]))
      }), 128))
    ]),
    _createElementVNode$2("div", _hoisted_14$1, [
      _createElementVNode$2("div", _hoisted_15$1, [
        _cache[4] || (_cache[4] = _createElementVNode$2("div", { class: "dc-section-title" }, "待关注", -1)),
        _createElementVNode$2("div", _hoisted_16$1, [
          _cache[1] || (_cache[1] = _createElementVNode$2("span", null, "观察队列", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.attention?.pending_observations || 0), 1)
        ]),
        _createElementVNode$2("div", _hoisted_17$1, [
          _cache[2] || (_cache[2] = _createElementVNode$2("span", null, "防刷日志", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.attention?.anti_cheat_logs || 0), 1)
        ]),
        _createElementVNode$2("div", _hoisted_18$1, [
          _cache[3] || (_cache[3] = _createElementVNode$2("span", null, "黑名命中", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.attention?.blacklist_hits || 0), 1)
        ])
      ]),
      _createElementVNode$2("div", _hoisted_19$1, [
        _cache[8] || (_cache[8] = _createElementVNode$2("div", { class: "dc-section-title" }, "治理概况", -1)),
        _createElementVNode$2("div", _hoisted_20$1, [
          _cache[5] || (_cache[5] = _createElementVNode$2("span", null, "忽略条目", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.governance?.ignored_observations || 0), 1)
        ]),
        _createElementVNode$2("div", _hoisted_21$1, [
          _cache[6] || (_cache[6] = _createElementVNode$2("span", null, "订阅记录", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.governance?.subscribe_records || 0), 1)
        ]),
        _createElementVNode$2("div", _hoisted_22$1, [
          _cache[7] || (_cache[7] = _createElementVNode$2("span", null, "防刷日志", -1)),
          _createElementVNode$2("strong", null, _toDisplayString$2(__props.config.overview?.governance?.anti_cheat_logs || 0), 1)
        ])
      ])
    ])
  ]))
}
}

};
const ConfigOverviewPane = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-40d428e8"]]);

const {createElementVNode:_createElementVNode$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,withCtx:_withCtx$1,vShow:_vShow$1,withDirectives:_withDirectives$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode,renderList:_renderList$1,Fragment:_Fragment$1,createElementBlock:_createElementBlock$1,withModifiers:_withModifiers,Transition:_Transition,normalizeClass:_normalizeClass$1} = await importShared('vue');


const _hoisted_1$1 = { class: "dc-pane" };
const _hoisted_2$1 = { class: "dc-pane" };
const _hoisted_3$1 = { class: "dc-rank-list-heading" };
const _hoisted_4$1 = { class: "dc-rank-list-summary text-caption text-medium-emphasis" };
const _hoisted_5$1 = { class: "dc-rank-list-1col" };
const _hoisted_6$1 = { class: "dc-rank-card-summary" };
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "dc-rank-summary-title" };
const _hoisted_9 = { class: "dc-rank-summary-meta" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { key: 1 };
const _hoisted_12 = { key: 2 };
const _hoisted_13 = { key: 3 };
const _hoisted_14 = { class: "dc-rank-actions" };
const _hoisted_15 = {
  key: 0,
  class: "dc-rank-card-details"
};
const _hoisted_16 = { class: "dc-rank-detail-toolbar" };
const _hoisted_17 = {
  key: 0,
  class: "dc-rank-route-hint text-caption text-medium-emphasis"
};
const _hoisted_18 = {
  key: 0,
  class: "dc-custom-rank-route-row"
};
const _hoisted_19 = { class: "dc-rank-card-body" };
const _hoisted_20 = { class: "dc-rank-field dc-rank-field--count" };
const _hoisted_21 = {
  key: 0,
  class: "dc-rank-field dc-rank-field--vote"
};
const _hoisted_22 = {
  key: 1,
  class: "dc-rank-field dc-rank-field--threshold"
};
const _hoisted_23 = {
  key: 2,
  class: "dc-rank-field dc-rank-field--threshold"
};
const _hoisted_24 = {
  key: 3,
  class: "dc-rank-field dc-rank-field--days"
};
const _hoisted_25 = {
  key: 1,
  class: "dc-custom-ranks-empty text-caption text-medium-emphasis"
};
const _hoisted_26 = { class: "dc-pane" };


const _sfc_main$1 = {
  __name: 'ConfigRankPane',
  props: {
  config: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VCol = _resolveComponent$1("VCol");
  const _component_VCronField = _resolveComponent$1("VCronField");
  const _component_VRow = _resolveComponent$1("VRow");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VTooltip = _resolveComponent$1("VTooltip");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VCheckbox = _resolveComponent$1("VCheckbox");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VCombobox = _resolveComponent$1("VCombobox");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");
  const _component_VTextarea = _resolveComponent$1("VTextarea");

  return (_openBlock$1(), _createElementBlock$1(_Fragment$1, null, [
    _withDirectives$1(_createElementVNode$1("div", _hoisted_1$1, [
      _cache[9] || (_cache[9] = _createElementVNode$1("div", { class: "dc-section-title" }, "基础设置", -1)),
      _createVNode$1(_component_VRow, null, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VSwitch, {
                modelValue: __props.config.form.onlyonce,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((__props.config.form.onlyonce) = $event)),
                color: "warning",
                inset: "",
                "hide-details": "",
                label: "立即运行一次"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode$1(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCronField, {
                modelValue: __props.config.form.cron,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.config.form.cron) = $event)),
                label: "运行周期",
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
      _createVNode$1(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCol, { cols: "12" }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VTextField, {
                modelValue: __props.config.form.rsshub_domain,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.config.form.rsshub_domain) = $event)),
                label: "RSSHub 域名",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "默认 https://rsshub.ddsrem.com，所有榜单共用",
                "persistent-hint": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$1(_component_VAlert, {
        class: "mt-3",
        type: "info",
        variant: "tonal",
        density: "compact",
        text: "订阅用户名统一为「豆瓣中心」。即将上映支持评分、地区、想看筛选；空或 0 表示不限。"
      })
    ], 512), [
      [_vShow$1, __props.config.activeSub === 'basic']
    ]),
    _withDirectives$1(_createElementVNode$1("div", _hoisted_2$1, [
      _createElementVNode$1("div", _hoisted_3$1, [
        _createElementVNode$1("div", null, [
          _cache[10] || (_cache[10] = _createElementVNode$1("div", { class: "dc-section-title mb-1" }, "榜单列表", -1)),
          _createElementVNode$1("div", _hoisted_4$1, "已启用 " + _toDisplayString$1(__props.config.enabledRankCount) + " 个 · 自定义 " + _toDisplayString$1(__props.config.customRankCount) + " 个", 1)
        ]),
        _createVNode$1(_component_VBtn, {
          icon: "",
          size: "small",
          variant: "tonal",
          color: "primary",
          "aria-label": "新增自定义榜单",
          onClick: __props.config.addCustomRank
        }, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_VIcon, {
              icon: "mdi-plus",
              size: "20"
            }),
            _createVNode$1(_component_VTooltip, {
              activator: "parent",
              location: "top"
            }, {
              default: _withCtx$1(() => [...(_cache[11] || (_cache[11] = [
                _createTextVNode$1("新增自定义榜单", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["onClick"])
      ]),
      _createVNode$1(_component_VAlert, {
        type: "info",
        variant: "tonal",
        density: "compact",
        class: "mb-3",
        text: "每个榜单独立控制；即将上映按提前天数筛选，其他榜单按最近天数筛选，自定义榜单可选择日期方向。空或 0 表示不限。"
      }),
      (__props.config.customRankError)
        ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            density: "compact",
            class: "mb-2",
            text: __props.config.customRankError
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      _createElementVNode$1("div", _hoisted_5$1, [
        (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(__props.config.rankDefs, (rank) => {
          return (_openBlock$1(), _createElementBlock$1("div", {
            key: rank.key,
            class: _normalizeClass$1(["dc-rank-card", { 'dc-rank-card--on': __props.config.form.rank_configs[rank.key]?.enabled, 'dc-rank-card--expanded': __props.config.isExpanded(rank.key) }])
          }, [
            _createElementVNode$1("div", _hoisted_6$1, [
              _createVNode$1(_component_VBtn, {
                icon: "",
                "aria-label": `${__props.config.isExpanded(rank.key) ? '收起' : '展开'}${rank.name}`,
                variant: "text",
                size: "small",
                class: "dc-rank-expand",
                onClick: $event => (__props.config.toggleRank(rank.key))
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VIcon, {
                    icon: __props.config.isExpanded(rank.key) ? 'mdi-chevron-down' : 'mdi-chevron-right',
                    size: "20"
                  }, null, 8, ["icon"])
                ]),
                _: 2
              }, 1032, ["aria-label", "onClick"]),
              _createVNode$1(_component_VCheckbox, {
                modelValue: __props.config.form.rank_configs[rank.key].enabled,
                "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].enabled) = $event),
                color: "primary",
                "hide-details": "",
                density: "compact",
                class: "dc-rank-check",
                "aria-label": `启用${rank.name}`
              }, null, 8, ["modelValue", "onUpdate:modelValue", "aria-label"]),
              _createElementVNode$1("div", {
                class: "dc-rank-summary-main",
                onClick: $event => (__props.config.toggleRank(rank.key))
              }, [
                _createElementVNode$1("div", _hoisted_8, [
                  _createElementVNode$1("span", null, _toDisplayString$1(rank.name), 1),
                  (rank.custom)
                    ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                        key: 0,
                        size: "x-small",
                        color: "primary",
                        variant: "tonal"
                      }, {
                        default: _withCtx$1(() => [...(_cache[12] || (_cache[12] = [
                          _createTextVNode$1("自定义", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true)
                ]),
                _createElementVNode$1("div", _hoisted_9, [
                  _createElementVNode$1("span", null, "数量 " + _toDisplayString$1(__props.config.form.rank_configs[rank.key]?.count || '不限'), 1),
                  (rank.filters.includes('vote'))
                    ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_10, "评分 " + _toDisplayString$1(__props.config.form.rank_configs[rank.key]?.vote || '不限'), 1))
                    : _createCommentVNode("", true),
                  _createElementVNode$1("span", null, "地区 " + _toDisplayString$1((__props.config.form.rank_configs[rank.key]?.regions || []).join('、') || '不限'), 1),
                  (rank.filters.includes('year'))
                    ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_11, "年份 " + _toDisplayString$1(__props.config.form.rank_configs[rank.key]?.year || '不限'), 1))
                    : _createCommentVNode("", true),
                  (rank.filters.includes('wish_count'))
                    ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_12, "想看 " + _toDisplayString$1(__props.config.form.rank_configs[rank.key]?.wish_count || '不限'), 1))
                    : _createCommentVNode("", true),
                  (rank.filters.includes('air_days'))
                    ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_13, _toDisplayString$1(__props.config.rankDateSummary(rank)), 1))
                    : _createCommentVNode("", true)
                ])
              ], 8, _hoisted_7),
              _createElementVNode$1("div", _hoisted_14, [
                (rank.custom)
                  ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                      key: 0,
                      icon: "",
                      variant: "flat",
                      color: "error",
                      class: "dc-delete-rank",
                      "aria-label": `删除${rank.name || '自定义榜单'}`,
                      onClick: _withModifiers($event => (__props.config.requestRemoveCustomRank(rank)), ["stop"])
                    }, {
                      default: _withCtx$1(() => [
                        _createVNode$1(_component_VIcon, {
                          icon: "mdi-delete-outline",
                          size: "20"
                        }),
                        _createVNode$1(_component_VTooltip, {
                          activator: "parent",
                          location: "top"
                        }, {
                          default: _withCtx$1(() => [...(_cache[13] || (_cache[13] = [
                            _createTextVNode$1("删除自定义榜单", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["aria-label", "onClick"]))
                  : _createCommentVNode("", true)
              ])
            ]),
            _createVNode$1(_Transition, { name: "dc-rank-details" }, {
              default: _withCtx$1(() => [
                (__props.config.isExpanded(rank.key))
                  ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_15, [
                      _createElementVNode$1("div", _hoisted_16, [
                        _createVNode$1(_component_VCheckbox, {
                          modelValue: __props.config.form.rank_configs[rank.key].enabled,
                          "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].enabled) = $event),
                          label: "自动订阅",
                          color: "primary",
                          "hide-details": "",
                          density: "compact",
                          class: "dc-rank-detail-enable"
                        }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                        (!rank.custom)
                          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_17, "路由：" + _toDisplayString$1(rank.route), 1))
                          : _createCommentVNode("", true)
                      ]),
                      (rank.custom)
                        ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_18, [
                            _createVNode$1(_component_VTextField, {
                              ref_for: true,
                              ref: element => __props.config.setNameInputRef(rank.key, element),
                              modelValue: rank.model.name,
                              "onUpdate:modelValue": $event => ((rank.model.name) = $event),
                              label: "榜单名称",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              class: "dc-custom-rank-name"
                            }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                            _createVNode$1(_component_VTextField, {
                              modelValue: rank.model.route,
                              "onUpdate:modelValue": $event => ((rank.model.route) = $event),
                              label: "路由",
                              placeholder: "/example/rsshub/route?foo=bar",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              class: "dc-custom-rank-route"
                            }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                            _createVNode$1(_component_VSelect, {
                              modelValue: rank.model.date_mode,
                              "onUpdate:modelValue": $event => ((rank.model.date_mode) = $event),
                              items: __props.config.dateModeOptions,
                              label: "日期方向",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              class: "dc-custom-rank-date-mode"
                            }, null, 8, ["modelValue", "onUpdate:modelValue", "items"])
                          ]))
                        : _createCommentVNode("", true),
                      _createElementVNode$1("div", _hoisted_19, [
                        _createElementVNode$1("div", _hoisted_20, [
                          _createVNode$1(_component_VTextField, {
                            modelValue: __props.config.form.rank_configs[rank.key].count,
                            "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].count) = $event),
                            modelModifiers: { number: true },
                            label: "数量",
                            placeholder: "0 不限",
                            type: "number",
                            min: "0",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": "",
                            class: "dc-rank-input"
                          }, null, 8, ["modelValue", "onUpdate:modelValue"])
                        ]),
                        (rank.filters.includes('vote'))
                          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_21, [
                              _createVNode$1(_component_VTextField, {
                                modelValue: __props.config.form.rank_configs[rank.key].vote,
                                "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].vote) = $event),
                                modelModifiers: { number: true },
                                label: "评分",
                                placeholder: "0 不限",
                                type: "number",
                                min: "0",
                                max: "10",
                                step: "0.1",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "dc-rank-input"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"])
                            ]))
                          : _createCommentVNode("", true),
                        _createVNode$1(_component_VCombobox, {
                          modelValue: __props.config.form.rank_configs[rank.key].regions,
                          "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].regions) = $event),
                          items: [],
                          label: "地区",
                          placeholder: "自定义填写",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          clearable: "",
                          "hide-details": "",
                          density: "compact",
                          variant: "outlined",
                          class: "dc-rank-regions"
                        }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                        (rank.filters.includes('year'))
                          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_22, [
                              _createVNode$1(_component_VTextField, {
                                modelValue: __props.config.form.rank_configs[rank.key].year,
                                "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].year) = $event),
                                modelModifiers: { number: true },
                                label: "年份",
                                placeholder: "0 不限",
                                type: "number",
                                min: "0",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "dc-rank-input"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"])
                            ]))
                          : _createCommentVNode("", true),
                        (rank.filters.includes('wish_count'))
                          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_23, [
                              _createVNode$1(_component_VTextField, {
                                modelValue: __props.config.form.rank_configs[rank.key].wish_count,
                                "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].wish_count) = $event),
                                modelModifiers: { number: true },
                                label: "想看",
                                placeholder: "0 不限",
                                type: "number",
                                min: "0",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "dc-rank-input"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"])
                            ]))
                          : _createCommentVNode("", true),
                        (rank.filters.includes('air_days'))
                          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_24, [
                              _createVNode$1(_component_VTextField, {
                                modelValue: __props.config.form.rank_configs[rank.key].air_days,
                                "onUpdate:modelValue": $event => ((__props.config.form.rank_configs[rank.key].air_days) = $event),
                                modelModifiers: { number: true },
                                label: __props.config.rankDateLabel(rank),
                                placeholder: "0 不限",
                                type: "number",
                                min: "0",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "dc-rank-input"
                              }, null, 8, ["modelValue", "onUpdate:modelValue", "label"])
                            ]))
                          : _createCommentVNode("", true)
                      ])
                    ]))
                  : _createCommentVNode("", true)
              ]),
              _: 2
            }, 1024)
          ], 2))
        }), 128))
      ]),
      (!__props.config.form.custom_ranks.length)
        ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_25, "尚未添加自定义榜单"))
        : _createCommentVNode("", true),
      _createVNode$1(_component_VDialog, {
        "model-value": __props.config.deleteDialog,
        "max-width": "420",
        "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => (__props.config.deleteDialog = $event))
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCard, null, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardTitle, { class: "text-body-1" }, {
                default: _withCtx$1(() => [...(_cache[14] || (_cache[14] = [
                  _createTextVNode$1("删除自定义榜单", -1)
                ]))]),
                _: 1
              }),
              _createVNode$1(_component_VCardText, null, {
                default: _withCtx$1(() => [
                  _createTextVNode$1("确定删除「" + _toDisplayString$1(__props.config.deleteTarget?.name || '未命名榜单') + "」吗？相关订阅、历史和运行条目不会被删除。", 1)
                ]),
                _: 1
              }),
              _createVNode$1(_component_VCardActions, null, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VSpacer),
                  _createVNode$1(_component_VBtn, {
                    variant: "text",
                    onClick: _cache[3] || (_cache[3] = $event => (__props.config.deleteDialog = false))
                  }, {
                    default: _withCtx$1(() => [...(_cache[15] || (_cache[15] = [
                      _createTextVNode$1("取消", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode$1(_component_VBtn, {
                    color: "error",
                    variant: "tonal",
                    onClick: _cache[4] || (_cache[4] = $event => (__props.config.removeCustomRank(__props.config.deleteTarget?.key)))
                  }, {
                    default: _withCtx$1(() => [...(_cache[16] || (_cache[16] = [
                      _createTextVNode$1("删除", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["model-value"])
    ], 512), [
      [_vShow$1, __props.config.activeSub === 'list']
    ]),
    _withDirectives$1(_createElementVNode$1("div", _hoisted_26, [
      _cache[17] || (_cache[17] = _createElementVNode$1("div", { class: "dc-section-title" }, "观察设置", -1)),
      _createVNode$1(_component_VRow, null, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCol, {
            cols: "12",
            md: "8"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VSelect, {
                modelValue: __props.config.form.observe_rank_keys,
                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.config.form.observe_rank_keys) = $event)),
                items: __props.config.rankDefs.map(rank => ({ title: rank.name, value: rank.key })),
                label: "观察榜单",
                multiple: "",
                chips: "",
                clearable: "",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "被选中的榜单会先进入观察队列，达到观察期后再订阅",
                "persistent-hint": ""
              }, null, 8, ["modelValue", "items"])
            ]),
            _: 1
          }),
          _createVNode$1(_component_VCol, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VTextField, {
                modelValue: __props.config.form.observe_days,
                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((__props.config.form.observe_days) = $event)),
                modelModifiers: { number: true },
                label: "观察期（天）",
                type: "number",
                min: "0",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "新条目在榜 N 天后才订阅，0 为不启用",
                "persistent-hint": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$1(_component_VRow, { class: "mt-2" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCol, { cols: "12" }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VTextarea, {
                modelValue: __props.config.form.blacklist_keywords,
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.config.form.blacklist_keywords) = $event)),
                label: "黑名单关键词（一行一个）",
                rows: "3",
                "auto-grow": "",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                hint: "标题包含任一关键词则跳过订阅。支持片段匹配，如输入「综艺」会匹配所有含「综艺」的剧名",
                "persistent-hint": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ], 512), [
      [_vShow$1, __props.config.activeSub === 'filter']
    ])
  ], 64))
}
}

};
const ConfigRankPane = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-d5135b53"]]);

const {computed,nextTick,reactive,ref,watch} = await importShared('vue');

const defaults = {
  enabled: false,
  cron: '0 8 * * *',
  notify: false,
  proxy: false,
  onlyonce: false,
  rsshub_domain: 'https://rsshub.ddsrem.com',
  rank_configs: {
    coming: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_real_time: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_chinese: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_global: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    movie_weekly: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    bangumi: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
  },
  region_filters: [],
  genre_filters: [],
  resolution_filters: [],
  custom_rss_addrs: '',
  custom_ranks: [],
  folio_enabled: true,
  folio_private: true,
  folio_first: true,
  folio_notify: false,
  folio_exclude_live_tv: true,
  folio_user: '',
  folio_exclude: '',
  folio_cookie: '',
  wish_enabled: false,
  wish_cron: '*/30 * * * *',
  wish_user: '',
  wish_notify: false,
  wish_onlyonce: false,
  wish_max_pages: 1,
  wish_days: 7,
  dashboard_rank_keys: [],
  discovery_page_enabled: false,
  blacklist_keywords: '',
  observe_days: 0,
  observe_rank_keys: ['coming', 'tv_real_time'],
};

const dateModeOptions = [
  { title: '提前订阅', value: 'future' },
  { title: '近期上映', value: 'recent' },
];

const builtinRankDefs = [
  { key: 'coming', name: '即将上映', route: '/douban/tv/coming', date_mode: 'future', filters: ['vote', 'wish_count', 'air_days'] },
  { key: 'tv_real_time', name: '实时热门', route: '/douban/list/tv_real_time_hotest', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'tv_chinese', name: '华语口碑', route: '/douban/list/tv_chinese_best_weekly', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'tv_global', name: '全球口碑', route: '/douban/list/tv_global_best_weekly', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'movie_weekly', name: '电影口碑', route: '/douban/list/movie_weekly_best', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'bangumi', name: 'BangumiTV', route: '/bangumi.tv/anime/followrank', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
];

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '运行链路、模块状态和待关注事项。' },
  { key: 'rank', title: '榜单订阅', icon: 'mdi-trophy-outline', desc: '内置与自定义榜单统一订阅到豆瓣中心。' },
  { key: 'folio', title: '豆瓣时间', icon: 'mdi-book-clock-outline', desc: '追剧观影自动同步进度到豆瓣时间线。' },
  { key: 'dashboard', title: '仪表显示', icon: 'mdi-view-dashboard-outline', desc: '时间线 + 榜单排行双面板。' },
];

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  rank: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'list', title: '榜单列表', icon: 'mdi-format-list-bulleted' },
    { key: 'filter', title: '订阅观察', icon: 'mdi-shield-search' },
  ],
  folio: [
    { key: 'wish', title: '同步想看', icon: 'mdi-heart-plus-outline' },
    { key: 'sync', title: '同步观影', icon: 'mdi-sync' },
  ],
  dashboard: [{ key: 'view', title: '仪表盘选择', icon: 'mdi-view-dashboard-outline' }],
};

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function customRankKey() {
  return `custom_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function normalizeDateMode(value) {
  return value === 'future' ? 'future' : 'recent'
}

function validCustomRoute(route) {
  const value = String(route || '').trim();
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('#')) return false
  try {
    return new URL(value, 'https://rsshub.local').origin === 'https://rsshub.local'
  } catch {
    return false
  }
}

function useConfigForm({ api, pluginId, initialConfig, emit }) {
  const form = reactive({});
  const activeMain = ref('overview');
  const activeSub = ref('overview');
  const overview = ref(null);
  const loadingOverview = ref(false);
  const customRankError = ref('');
  const expandedRankKeys = ref(new Set());
  const deleteTarget = ref(null);
  const deleteDialog = ref(false);
  const nameInputRefs = new Map();

  const rankDefs = computed(() => [
    ...builtinRankDefs,
    ...(Array.isArray(form.custom_ranks) ? form.custom_ranks : []).map(rank => ({
      ...rank,
      model: rank,
      custom: true,
      filters: ['vote', 'year', 'air_days'],
    })),
  ]);
  const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
  const currentSubs = computed(() => subTabs[activeMain.value] || []);
  const enabledRankCount = computed(() => rankDefs.value.filter(rank => form.rank_configs?.[rank.key]?.enabled).length);
  const customRankCount = computed(() => rankDefs.value.filter(rank => rank.custom).length);
  const overviewCards = computed(() => {
    const cards = overview.value?.cards || {};
    return [
      {
        title: '榜单订阅',
        icon: 'mdi-rss',
        color: cards.rss?.enabled ? 'success' : 'warning',
        value: `${cards.rss?.enabled || 0}/${cards.rss?.total || rankDefs.value.length}`,
        desc: cards.rss?.last_refresh ? `最近刷新 ${cards.rss.last_refresh}` : '等待 RSS 刷新',
      },
      {
        title: '订阅记录',
        icon: 'mdi-playlist-check',
        color: cards.subscribe?.enabled ? 'primary' : 'default',
        value: `${cards.subscribe?.total || 0} 条`,
        desc: `本月新增 ${cards.subscribe?.month_new || 0} 条`,
      },
      {
        title: '归档治理',
        icon: 'mdi-shield-check-outline',
        color: cards.observe?.pending ? 'warning' : 'success',
        value: `${cards.observe?.pending || 0} 待观察`,
        desc: `观察期 ${cards.observe?.days || 0} 天，已忽略 ${cards.observe?.ignored || 0}`,
      },
      {
        title: '豆瓣时间',
        icon: 'mdi-book-clock-outline',
        color: cards.folio?.enabled ? 'success' : 'default',
        value: `${cards.folio?.items || 0} 条`,
        desc: cards.folio?.user ? `用户 ${cards.folio.user}` : '未配置用户',
      },
    ]
  });

  function rankDateLabel(rank) {
    return normalizeDateMode(rank?.date_mode) === 'future' ? '提前天数' : '最近天数'
  }

  function rankDateSummary(rank) {
    const days = form.rank_configs?.[rank.key]?.air_days;
    const prefix = normalizeDateMode(rank?.date_mode) === 'future' ? '提前' : '最近';
    return `${prefix} ${Number(days) > 0 ? `${days} 天` : '不限'}`
  }

  function addCustomRank() {
    customRankError.value = '';
    const key = customRankKey();
    form.custom_ranks.push({ key, name: '', route: '', date_mode: 'recent' });
    form.rank_configs[key] = { enabled: false, count: 1, vote: '', year: '', air_days: '', regions: [] };
    expandedRankKeys.value = new Set([...expandedRankKeys.value, key]);
    activeMain.value = 'rank';
    activeSub.value = 'list';
    nextTick(() => nameInputRefs.get(key)?.focus?.());
  }

  function setNameInputRef(key, value) {
    if (value) nameInputRefs.set(key, value);
    else nameInputRefs.delete(key);
  }

  function toggleRank(key) {
    const next = new Set(expandedRankKeys.value);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    expandedRankKeys.value = next;
  }

  function isExpanded(key) {
    return expandedRankKeys.value.has(key)
  }

  function requestRemoveCustomRank(rank) {
    deleteTarget.value = rank;
    deleteDialog.value = true;
  }

  function removeCustomRank(key) {
    customRankError.value = '';
    form.custom_ranks = form.custom_ranks.filter(rank => rank.key !== key);
    delete form.rank_configs[key];
    form.dashboard_rank_keys = (form.dashboard_rank_keys || []).filter(value => value !== key);
    form.observe_rank_keys = (form.observe_rank_keys || []).filter(value => value !== key);
    expandedRankKeys.value = new Set([...expandedRankKeys.value].filter(value => value !== key));
    deleteTarget.value = null;
    deleteDialog.value = false;
  }

  function validateCustomRanks() {
    const seen = new Set(builtinRankDefs.map(rank => rank.key));
    for (const rank of form.custom_ranks || []) {
      const key = String(rank?.key || '').trim();
      if (!key || seen.has(key)) return '自定义榜单标识重复或无效'
      if (!String(rank?.name || '').trim()) return '请填写自定义榜单名称'
      if (!validCustomRoute(rank?.route)) return 'RSSHub 路由必须是以 / 开头的相对路径'
      if (!dateModeOptions.some(item => item.value === rank?.date_mode)) return '请选择自定义榜单的日期方向'
      seen.add(key);
    }
    return ''
  }

  function normalizeInitialConfig(value) {
    const normalized = Object.assign({}, cloneConfig(defaults), cloneConfig(value));
    normalized.custom_ranks = Array.isArray(normalized.custom_ranks)
      ? normalized.custom_ranks.filter(rank => isPlainObject(rank)).map(rank => ({
        key: String(rank.key || ''),
        name: String(rank.name || ''),
        route: String(rank.route || ''),
        date_mode: normalizeDateMode(rank.date_mode),
      }))
      : [];
    if (!isPlainObject(normalized.rank_configs)) normalized.rank_configs = {};
    const allRanks = [...builtinRankDefs, ...normalized.custom_ranks.map(rank => ({ ...rank, filters: ['vote', 'year', 'air_days'] }))];
    for (const rank of allRanks) {
      normalized.rank_configs[rank.key] = {
        ...(defaults.rank_configs[rank.key] || { enabled: false, count: 1, vote: '', year: '' }),
        ...(isPlainObject(normalized.rank_configs[rank.key]) ? normalized.rank_configs[rank.key] : {}),
      };
      const rankConfig = normalized.rank_configs[rank.key];
      rankConfig.regions = Array.isArray(rankConfig.regions)
        ? [...new Set(rankConfig.regions.map(item => String(item || '').trim()).filter(Boolean))]
        : [];
      const rawCount = rankConfig.count;
      rankConfig.count = rawCount === undefined || rawCount === null || rawCount === '' ? 1 : (Number(rawCount) === 0 ? '' : rawCount);
      for (const field of ['vote', 'year', 'wish_count', 'air_days']) {
        if (rankConfig[field] === undefined || rankConfig[field] === null || Number(rankConfig[field]) === 0) rankConfig[field] = '';
      }
      delete rankConfig.media_type;
    }
    if (!Array.isArray(normalized.dashboard_rank_keys)) normalized.dashboard_rank_keys = [];
    normalized.dashboard_rank_keys = [...new Set(normalized.dashboard_rank_keys.map(item => String(item || '').trim()).filter(Boolean))].slice(0, 6);
    if (!Array.isArray(normalized.observe_rank_keys)) normalized.observe_rank_keys = [...defaults.observe_rank_keys];
    return normalized
  }

  function saveConfig() {
    customRankError.value = validateCustomRanks();
    if (customRankError.value) {
      activeMain.value = 'rank';
      activeSub.value = 'list';
      return
    }
    emit('save', {
      ...form,
      custom_ranks: (form.custom_ranks || []).map(rank => ({
        key: String(rank.key || '').trim(),
        name: String(rank.name || '').trim(),
        route: String(rank.route || '').trim(),
        date_mode: normalizeDateMode(rank.date_mode),
      })),
      rank_configs: Object.fromEntries(Object.entries(form.rank_configs || {}).map(([key, config]) => [key, {
        ...cloneConfig(config),
        regions: Array.isArray(config?.regions) ? [...new Set(config.regions.map(value => String(value || '').trim()).filter(Boolean))] : [],
      }])),
      region_filters: [],
      genre_filters: [],
      resolution_filters: [],
      custom_rss_addrs: '',
    });
  }

  function limitDashboardRanks() {
    form.dashboard_rank_keys = [...new Set((form.dashboard_rank_keys || []).map(value => String(value || '').trim()).filter(Boolean))].slice(0, 6);
  }

  function selectMain(key) {
    if (activeMain.value === key) return
    activeMain.value = key;
    activeSub.value = subTabs[key]?.[0]?.key || '';
  }

  async function loadOverview() {
    loadingOverview.value = true;
    try {
      const response = await getPluginApi(api(), pluginId(), 'overview');
      if (response?.success === false) throw new Error(response.message || '总览加载失败')
      const data = response?.data ?? response;
      if (data?.code === 0 || data?.cards) overview.value = data;
    } catch (error) {
      console.error('加载豆瓣中心总览失败:', error);
    } finally {
      loadingOverview.value = false;
    }
  }

  watch(initialConfig, value => {
    Object.keys(form).forEach(key => delete form[key]);
    Object.assign(form, normalizeInitialConfig(value));
  }, { immediate: true, deep: true });

  return reactive({
    form,
    activeMain,
    activeSub,
    overview,
    loadingOverview,
    customRankError,
    deleteTarget,
    deleteDialog,
    rankDefs,
    mainTabs,
    currentMain,
    currentSubs,
    enabledRankCount,
    customRankCount,
    overviewCards,
    dateModeOptions,
    rankDateLabel,
    rankDateSummary,
    addCustomRank,
    setNameInputRef,
    toggleRank,
    isExpanded,
    requestRemoveCustomRank,
    removeCustomRank,
    saveConfig,
    limitDashboardRanks,
    selectMain,
    loadOverview,
  })
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,unref:_unref,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createBlock:_createBlock,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "dc-config" };
const _hoisted_2 = { class: "dc-body" };
const _hoisted_3 = { class: "dc-nav" };
const _hoisted_4 = { class: "dc-content" };
const _hoisted_5 = { class: "dc-subtabs" };
const _hoisted_6 = ["onClick"];

const {onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DoubanCenter' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const config = useConfigForm({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: () => props.initialConfig,
  emit,
});

onMounted(config.loadOverview);

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
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "dc-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "dc-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg",
              class: "dc-header-avatar"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-book-open-page-variant-outline",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: _unref(config).form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref(config).form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              class: "dc-enable-switch",
              label: _unref(config).form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6 dc-header-title" }, {
              default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                _createTextVNode("豆瓣中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption dc-header-subtitle" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(_unref(config).currentMain.desc), 1)
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
              class: "py-2 dc-nav-list"
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(config).mainTabs, (item) => {
                  return (_openBlock(), _createBlock(_component_VListItem, {
                    key: item.key,
                    active: _unref(config).activeMain === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "dc-nav-item",
                    onClick: $event => (_unref(config).selectMain(item.key))
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon,
                        class: "dc-nav-icon"
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, { class: "dc-nav-title" }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["active", "onClick"]))
                }), 128))
              ]),
              _: 1
            })
          ]),
          _createElementVNode("section", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(config).currentSubs, (sub) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: sub.key,
                  type: "button",
                  class: _normalizeClass(["dc-subtab", { 'dc-subtab--active': _unref(config).activeSub === sub.key }]),
                  onClick: $event => (_unref(config).activeSub = sub.key)
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
            _createElementVNode("div", {
              class: _normalizeClass(["dc-window", { 'dc-window--overview': _unref(config).activeMain === 'overview' }])
            }, [
              _withDirectives(_createVNode(ConfigOverviewPane, { config: _unref(config) }, null, 8, ["config"]), [
                [_vShow, _unref(config).activeSub === 'overview']
              ]),
              _createVNode(ConfigRankPane, { config: _unref(config) }, null, 8, ["config"]),
              _createVNode(ConfigFolioPane, { config: _unref(config) }, null, 8, ["config"]),
              _createVNode(ConfigDashboardPane, { config: _unref(config) }, null, 8, ["config"])
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "dc-actions" }, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              class: "dc-action-btn",
              onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              class: "dc-action-btn dc-action-btn--save",
              onClick: _unref(config).saveConfig
            }, {
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode("保存配置", -1)
              ]))]),
              _: 1
            }, 8, ["onClick"])
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2e190982"]]);

export { Config as default };
