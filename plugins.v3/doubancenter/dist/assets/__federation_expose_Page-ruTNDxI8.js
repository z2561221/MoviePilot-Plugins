import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, t as toPosterThumbnail, a as getPluginApi, p as postPluginApi } from './api-ilAfCmvf.js';
import { u as useRankMediaActions, s as sourceDescriptor } from './useRankMediaActions-JayhEIdr.js';

const {resolveComponent:_resolveComponent$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,withCtx:_withCtx$2,createVNode:_createVNode$2,toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$2} = await importShared('vue');



const _sfc_main$2 = {
  __name: 'PageActionDialog',
  props: {
  page: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VImg = _resolveComponent$2("VImg");
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VAvatar = _resolveComponent$2("VAvatar");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$2("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$2("VCardItem");
  const _component_VDivider = _resolveComponent$2("VDivider");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createBlock$2(_component_VDialog, {
    "model-value": __props.page.showDialog,
    "max-width": "420",
    "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (__props.page.showDialog = $event))
  }, {
    default: _withCtx$2(() => [
      _createVNode$2(_component_VCard, {
        rounded: "lg",
        class: "dc-action-dialog"
      }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_VCardItem, { class: "pa-3" }, {
            prepend: _withCtx$2(() => [
              _createVNode$2(_component_VAvatar, {
                size: "36",
                rounded: "md",
                class: "mr-2"
              }, {
                default: _withCtx$2(() => [
                  (__props.page.dialogPoster())
                    ? (_openBlock$2(), _createBlock$2(_component_VImg, {
                        key: 0,
                        src: __props.page.dialogPoster()
                      }, null, 8, ["src"]))
                    : (_openBlock$2(), _createBlock$2(_component_VIcon, {
                        key: 1,
                        icon: "mdi-filmstrip"
                      }))
                ]),
                _: 1
              })
            ]),
            default: _withCtx$2(() => [
              _createVNode$2(_component_VCardTitle, { class: "text-body-1 font-weight-bold pa-0" }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(__props.page.dialogItem?.item?.title || ''), 1)
                ]),
                _: 1
              }),
              _createVNode$2(_component_VCardSubtitle, { class: "text-caption pa-0" }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(__props.page.dialogItem?.rk ? __props.page.rankNameOf(__props.page.dialogItem.rk, __props.page.dialogItem.item) : ''), 1)
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$2(_component_VDivider),
          (__props.page.dialogResolveError)
            ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "mx-3 mt-3",
                text: __props.page.dialogResolveError
              }, null, 8, ["text"]))
            : _createCommentVNode$2("", true),
          _createVNode$2(_component_VCardActions, { class: "pa-3 pt-2 dc-dialog-actions" }, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                color: "primary",
                "prepend-icon": "mdi-plus-circle-outline",
                class: "dc-dialog-action text-none",
                disabled: __props.page.dialogResolving,
                onClick: __props.page.doSubscribe
              }, {
                default: _withCtx$2(() => [...(_cache[1] || (_cache[1] = [
                  _createTextVNode$2("订阅", -1)
                ]))]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-movie-open-outline",
                class: "dc-dialog-action dc-dialog-action--tmdb text-none",
                loading: __props.page.dialogResolving,
                disabled: __props.page.dialogResolving || !__props.page.tmdbIdOf(__props.page.dialogItem?.item),
                onClick: __props.page.doOpenTmdb
              }, {
                default: _withCtx$2(() => [...(_cache[2] || (_cache[2] = [
                  _createTextVNode$2("TMDB", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled", "onClick"]),
              _createVNode$2(_component_VBtn, {
                href: __props.page.sourceButtonHref() || undefined,
                target: "_blank",
                rel: "noopener noreferrer",
                variant: "tonal",
                color: __props.page.sourceButtonColor(),
                "prepend-icon": __props.page.sourceButtonIcon(),
                disabled: !__props.page.sourceButtonUrl(),
                class: "dc-dialog-action text-none",
                onClick: __props.page.openSource
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(__props.page.sourceButtonLabel()), 1)
                ]),
                _: 1
              }, 8, ["href", "color", "prepend-icon", "disabled", "onClick"])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value"]))
}
}

};
const PageActionDialog = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-13facbe6"]]);

const {toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1,createTextVNode:_createTextVNode$1,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,resolveComponent:_resolveComponent$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,withCtx:_withCtx$1,createVNode:_createVNode$1,normalizeStyle:_normalizeStyle,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1$1 = {
  key: 0,
  class: "dc-section dc-section--archive"
};
const _hoisted_2$1 = { class: "dc-section-title mb-2" };
const _hoisted_3$1 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_4$1 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_5$1 = { class: "dc-history-info" };
const _hoisted_6$1 = { class: "dc-history-title" };
const _hoisted_7 = { class: "dc-history-meta" };
const _hoisted_8 = { class: "text-caption text-medium-emphasis" };
const _hoisted_9 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_10 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_11 = {
  key: 2,
  class: "dc-pagination"
};
const _hoisted_12 = { class: "dc-pagination-label" };
const _hoisted_13 = {
  key: 0,
  class: "dc-section dc-section--stats"
};
const _hoisted_14 = { class: "dc-stats-grid" };
const _hoisted_15 = { class: "dc-stat-card" };
const _hoisted_16 = { class: "dc-stat-value" };
const _hoisted_17 = { class: "dc-stat-card" };
const _hoisted_18 = { class: "dc-stat-value" };
const _hoisted_19 = { class: "dc-stat-label" };
const _hoisted_20 = {
  key: 1,
  class: "dc-section dc-section--rank"
};
const _hoisted_21 = { class: "dc-rank-grid dc-rank-grid--snapshot" };
const _hoisted_22 = { class: "dc-rank-head" };
const _hoisted_23 = ["onClick"];
const _hoisted_24 = { class: "dc-rank-title" };
const _hoisted_25 = {
  key: 0,
  class: "dc-rank-wish"
};
const _hoisted_26 = {
  key: 1,
  class: "dc-rank-empty"
};
const _hoisted_27 = { class: "dc-section dc-section--blacklist" };
const _hoisted_28 = { class: "dc-section-title mb-2 dc-title-with-chips" };
const _hoisted_29 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_30 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_31 = { class: "dc-history-info" };
const _hoisted_32 = { class: "dc-history-title" };
const _hoisted_33 = { class: "dc-history-meta" };
const _hoisted_34 = { class: "text-caption text-medium-emphasis" };
const _hoisted_35 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_36 = { class: "dc-section dc-section--observe" };
const _hoisted_37 = { class: "dc-section-title mb-2" };
const _hoisted_38 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_39 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_40 = ["onClick"];
const _hoisted_41 = { class: "dc-history-info" };
const _hoisted_42 = { class: "dc-history-title" };
const _hoisted_43 = { class: "dc-history-meta" };
const _hoisted_44 = { class: "text-caption text-medium-emphasis" };
const _hoisted_45 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_46 = { class: "dc-section dc-section--history" };
const _hoisted_47 = { class: "dc-section-title mb-2" };
const _hoisted_48 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_49 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_50 = { class: "dc-history-info" };
const _hoisted_51 = { class: "dc-history-title" };
const _hoisted_52 = { class: "dc-history-meta" };
const _hoisted_53 = { class: "text-caption text-medium-emphasis" };
const _hoisted_54 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_55 = {
  key: 2,
  class: "d-flex justify-center mt-2"
};
const _hoisted_56 = { class: "d-flex align-center mx-2 text-caption text-medium-emphasis" };
const _hoisted_57 = { class: "dc-section dc-section--logs" };
const _hoisted_58 = { class: "dc-section-title mb-2" };
const _hoisted_59 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_60 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_61 = { class: "dc-history-info" };
const _hoisted_62 = { class: "dc-history-title" };
const _hoisted_63 = { class: "dc-history-meta" };
const _hoisted_64 = { class: "text-caption text-medium-emphasis" };
const _hoisted_65 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};


const _sfc_main$1 = {
  __name: 'PageContent',
  props: {
  page: { type: Object, required: true },
},
  setup(__props) {



return (_ctx, _cache) => {
  const _component_VImg = _resolveComponent$1("VImg");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VAvatar = _resolveComponent$1("VAvatar");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VBtn = _resolveComponent$1("VBtn");

  return (__props.page.archivePage)
    ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        _createElementVNode$1("div", _hoisted_2$1, [
          _cache[4] || (_cache[4] = _createTextVNode$1("归档记录 ", -1)),
          _createElementVNode$1("span", _hoisted_3$1, "（共 " + _toDisplayString$1(__props.page.archiveData.total || 0) + " 条）", 1)
        ]),
        (__props.page.archiveData.items && __props.page.archiveData.items.length)
          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_4$1, [
              (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.archiveData.items, (item, i) => {
                return (_openBlock$1(), _createElementBlock$1("div", {
                  key: item.id || i,
                  class: "dc-history-row dc-archive-row"
                }, [
                  _createVNode$1(_component_VAvatar, {
                    rounded: "sm",
                    class: "dc-history-poster mr-2 flex-shrink-0",
                    color: __props.page.archiveColor(item),
                    variant: "tonal"
                  }, {
                    default: _withCtx$1(() => [
                      (__props.page.archivePoster(item))
                        ? (_openBlock$1(), _createBlock$1(_component_VImg, {
                            key: 0,
                            src: __props.page.archivePoster(item),
                            cover: ""
                          }, null, 8, ["src"]))
                        : (_openBlock$1(), _createBlock$1(_component_VIcon, {
                            key: 1,
                            icon: __props.page.archiveIcon(item),
                            size: "14"
                          }, null, 8, ["icon"]))
                    ]),
                    _: 2
                  }, 1032, ["color"]),
                  _createElementVNode$1("div", _hoisted_5$1, [
                    _createElementVNode$1("div", _hoisted_6$1, _toDisplayString$1(__props.page.archiveTitle(item)), 1),
                    _createElementVNode$1("div", _hoisted_7, [
                      _createVNode$1(_component_VChip, {
                        size: "x-small",
                        color: __props.page.archiveColor(item),
                        variant: "tonal",
                        class: "mr-1"
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(_toDisplayString$1(__props.page.archiveSourceName(item)), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      (__props.page.archiveRankName(item))
                        ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                            key: 0,
                            size: "x-small",
                            style: _normalizeStyle(__props.page.rankChipStyle(__props.page.archiveRankKey(item))),
                            variant: "tonal",
                            class: "dc-rank-chip mr-1"
                          }, {
                            default: _withCtx$1(() => [
                              _createTextVNode$1(_toDisplayString$1(__props.page.archiveRankName(item)), 1)
                            ]),
                            _: 2
                          }, 1032, ["style"]))
                        : _createCommentVNode$1("", true),
                      _createElementVNode$1("span", _hoisted_8, _toDisplayString$1(__props.page.archiveTime(item) ? __props.page.archiveTime(item).split(' ')[0] : ''), 1),
                      (item.archived_at)
                        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_9, "归档 " + _toDisplayString$1(item.archived_at.split(' ')[0]), 1))
                        : _createCommentVNode$1("", true)
                    ])
                  ]),
                  _createVNode$1(_component_VChip, {
                    size: "x-small",
                    color: __props.page.archiveColor(item),
                    variant: "tonal",
                    class: "dc-row-status"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(__props.page.archiveStatus(item)), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"]),
                  _createVNode$1(_component_VBtn, {
                    icon: "mdi-restore",
                    variant: "text",
                    size: "x-small",
                    color: "primary",
                    class: "dc-row-action",
                    loading: __props.page.actionKey === __props.page.rowKey('archive-restore', item, i),
                    onClick: $event => (__props.page.restoreArchive(item, i))
                  }, null, 8, ["loading", "onClick"]),
                  _createVNode$1(_component_VBtn, {
                    icon: "mdi-delete-outline",
                    variant: "text",
                    size: "x-small",
                    color: "error",
                    class: "dc-row-action",
                    loading: __props.page.actionKey === __props.page.rowKey('archive-delete', item, i),
                    onClick: $event => (__props.page.deleteArchive(item, i))
                  }, null, 8, ["loading", "onClick"])
                ]))
              }), 128))
            ]))
          : (!__props.page.loading)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_10, "暂无归档记录"))
            : _createCommentVNode$1("", true),
        (__props.page.archiveData.total_pages > 1)
          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_11, [
              _createVNode$1(_component_VBtn, {
                icon: "mdi-chevron-left",
                variant: "text",
                size: "x-small",
                title: "上一页",
                "aria-label": "上一页",
                disabled: __props.page.archiveData.page <= 1,
                onClick: _cache[0] || (_cache[0] = $event => (__props.page.goArchivePage(__props.page.archiveData.page - 1)))
              }, null, 8, ["disabled"]),
              _createElementVNode$1("span", _hoisted_12, _toDisplayString$1(__props.page.archiveData.page) + " / " + _toDisplayString$1(__props.page.archiveData.total_pages), 1),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-chevron-right",
                variant: "text",
                size: "x-small",
                title: "下一页",
                "aria-label": "下一页",
                disabled: __props.page.archiveData.page >= __props.page.archiveData.total_pages,
                onClick: _cache[1] || (_cache[1] = $event => (__props.page.goArchivePage(__props.page.archiveData.page + 1)))
              }, null, 8, ["disabled"])
            ]))
          : _createCommentVNode$1("", true)
      ]))
    : (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 1 }, [
        (__props.page.stats)
          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_13, [
              _cache[7] || (_cache[7] = _createElementVNode$1("div", { class: "dc-section-title mb-2" }, "订阅统计", -1)),
              _createElementVNode$1("div", _hoisted_14, [
                _createElementVNode$1("div", _hoisted_15, [
                  _createElementVNode$1("div", _hoisted_16, _toDisplayString$1(__props.page.stats.total || 0), 1),
                  _cache[5] || (_cache[5] = _createElementVNode$1("div", { class: "dc-stat-label" }, "总订阅数", -1))
                ]),
                _createElementVNode$1("div", _hoisted_17, [
                  _createElementVNode$1("div", _hoisted_18, _toDisplayString$1(__props.page.stats.month_new || 0), 1),
                  _cache[6] || (_cache[6] = _createElementVNode$1("div", { class: "dc-stat-label" }, "本月新增", -1))
                ]),
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList((__props.page.stats.rank_stats || []), (item) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: item.key,
                    class: "dc-stat-card"
                  }, [
                    _createElementVNode$1("div", {
                      class: "dc-stat-value",
                      style: _normalizeStyle({ color: __props.page.rankColorOf(item.key) })
                    }, _toDisplayString$1(item.count), 5),
                    _createElementVNode$1("div", _hoisted_19, _toDisplayString$1(item.name || __props.page.rankNameOf(item.key)), 1)
                  ]))
                }), 128))
              ])
            ]))
          : _createCommentVNode$1("", true),
        (__props.page.rankHistory && Object.keys(__props.page.rankHistory).length)
          ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_20, [
              _cache[8] || (_cache[8] = _createElementVNode$1("div", { class: "dc-section-title mb-2" }, [
                _createTextVNode$1("榜单快照 "),
                _createElementVNode$1("span", { class: "text-caption font-weight-regular text-medium-emphasis" }, "（点击条目订阅或打开来源）")
              ], -1)),
              _createElementVNode$1("div", _hoisted_21, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(Object.entries(__props.page.rankHistory), ([key, items]) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: key,
                    class: "dc-rank-card"
                  }, [
                    _createElementVNode$1("div", _hoisted_22, [
                      _createVNode$1(_component_VIcon, {
                        icon: "mdi-format-list-numbered",
                        size: "15",
                        style: _normalizeStyle(__props.page.rankIconStyle(key)),
                        class: "mr-1"
                      }, null, 8, ["style"]),
                      _createElementVNode$1("span", null, _toDisplayString$1(__props.page.rankNameOf(key, items?.[0])), 1)
                    ]),
                    (items && items.length)
                      ? (_openBlock$1(true), _createElementBlock$1(_Fragment, { key: 0 }, _renderList(items.slice(0, 5), (item, i) => {
                          return (_openBlock$1(), _createElementBlock$1("div", {
                            key: `${key}-${i}`,
                            class: "dc-rank-row",
                            title: "订阅 / 打开详情",
                            onClick: $event => (__props.page.showActionDialog(key, item))
                          }, [
                            _createVNode$1(_component_VAvatar, {
                              rounded: "sm",
                              class: "dc-rank-poster"
                            }, {
                              default: _withCtx$1(() => [
                                (item.poster)
                                  ? (_openBlock$1(), _createBlock$1(_component_VImg, {
                                      key: 0,
                                      src: __props.page.toPosterThumbnail(item.poster),
                                      cover: ""
                                    }, null, 8, ["src"]))
                                  : (_openBlock$1(), _createBlock$1(_component_VIcon, {
                                      key: 1,
                                      icon: "mdi-filmstrip",
                                      size: "13"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode$1("span", _hoisted_24, _toDisplayString$1(item.title || ''), 1),
                            (key === 'coming' && item.wish_count)
                              ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_25, _toDisplayString$1(item.wish_count), 1))
                              : _createCommentVNode$1("", true)
                          ], 8, _hoisted_23))
                        }), 128))
                      : (_openBlock$1(), _createElementBlock$1("div", _hoisted_26, "暂无榜单数据"))
                  ]))
                }), 128))
              ])
            ]))
          : _createCommentVNode$1("", true),
        _createElementVNode$1("div", _hoisted_27, [
          _createElementVNode$1("div", _hoisted_28, [
            _cache[9] || (_cache[9] = _createTextVNode$1(" 黑名拦截 ", -1)),
            _createElementVNode$1("span", _hoisted_29, "（关键词 " + _toDisplayString$1(__props.page.blacklistKeywords.length) + " 个，最近命中 " + _toDisplayString$1(__props.page.blacklistEntries.length) + " 条）", 1),
            (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.blacklistKeywords, (word, i) => {
              return (_openBlock$1(), _createBlock$1(_component_VChip, {
                key: `${word}-${i}`,
                size: "x-small",
                color: "error",
                variant: "tonal",
                class: "dc-blacklist-chip"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(word), 1)
                ]),
                _: 2
              }, 1024))
            }), 128))
          ]),
          (__props.page.blacklistEntries && __props.page.blacklistEntries.length)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_30, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.blacklistEntries, (item, i) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: i,
                    class: "dc-history-row dc-status-row"
                  }, [
                    _createVNode$1(_component_VAvatar, {
                      size: "28",
                      class: "mr-2 flex-shrink-0",
                      color: "error",
                      variant: "tonal"
                    }, {
                      default: _withCtx$1(() => [
                        _createVNode$1(_component_VIcon, {
                          icon: "mdi-block-helper",
                          size: "14"
                        })
                      ]),
                      _: 1
                    }),
                    _createElementVNode$1("div", _hoisted_31, [
                      _createElementVNode$1("div", _hoisted_32, _toDisplayString$1(item.title || '未命名条目'), 1),
                      _createElementVNode$1("div", _hoisted_33, [
                        _createElementVNode$1("span", _hoisted_34, _toDisplayString$1(item.time || ''), 1)
                      ])
                    ]),
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      color: "error",
                      variant: "tonal",
                      class: "dc-row-status"
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(item.detail || item.reason || '黑名拦截'), 1)
                      ]),
                      _: 2
                    }, 1024),
                    _createVNode$1(_component_VBtn, {
                      icon: "mdi-delete-outline",
                      variant: "text",
                      size: "x-small",
                      color: "error",
                      class: "dc-row-action",
                      loading: __props.page.actionKey === __props.page.rowKey('log', item, i),
                      onClick: $event => (__props.page.deleteAntiCheatLog(item, i))
                    }, null, 8, ["loading", "onClick"])
                  ]))
                }), 128))
              ]))
            : (!__props.page.loading)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_35, "暂无被黑名单筛选的条目"))
              : _createCommentVNode$1("", true)
        ]),
        _createElementVNode$1("div", _hoisted_36, [
          _createElementVNode$1("div", _hoisted_37, [
            _cache[10] || (_cache[10] = _createTextVNode$1("观察队列 ", -1)),
            _createElementVNode$1("span", _hoisted_38, "（待自动订阅 " + _toDisplayString$1(__props.page.pendingObservations.length) + " 条）", 1)
          ]),
          (__props.page.pendingObservations && __props.page.pendingObservations.length)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_39, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.pendingObservations, (item, i) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: i,
                    class: "dc-history-row dc-status-row dc-history-row--clickable",
                    onClick: $event => (__props.page.showActionDialog(item.rank_key, item))
                  }, [
                    _createVNode$1(_component_VAvatar, {
                      size: "28",
                      class: "mr-2 flex-shrink-0",
                      color: "warning",
                      variant: "tonal"
                    }, {
                      default: _withCtx$1(() => [
                        _createVNode$1(_component_VIcon, {
                          icon: "mdi-clock-outline",
                          size: "14"
                        })
                      ]),
                      _: 1
                    }),
                    _createElementVNode$1("div", _hoisted_41, [
                      _createElementVNode$1("div", _hoisted_42, _toDisplayString$1(item.title), 1),
                      _createElementVNode$1("div", _hoisted_43, [
                        _createVNode$1(_component_VChip, {
                          size: "x-small",
                          style: _normalizeStyle(__props.page.rankChipStyle(item.rank_key)),
                          variant: "tonal",
                          class: "dc-rank-chip mr-1"
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(item.rank_name || __props.page.rankNameOf(item.rank_key, item)), 1)
                          ]),
                          _: 2
                        }, 1032, ["style"]),
                        _createElementVNode$1("span", _hoisted_44, "观察 " + _toDisplayString$1(item.elapsed_days || 0) + " / " + _toDisplayString$1(item.observe_days || 0) + " 天", 1)
                      ])
                    ]),
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      color: "warning",
                      variant: "tonal",
                      class: "dc-row-status"
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1("剩余 " + _toDisplayString$1(item.remaining_days || 0) + " 天", 1)
                      ]),
                      _: 2
                    }, 1024),
                    _createVNode$1(_component_VBtn, {
                      icon: "mdi-delete-outline",
                      variant: "text",
                      size: "x-small",
                      color: "error",
                      class: "dc-row-action",
                      loading: __props.page.actionKey === __props.page.rowKey('obs', item, i),
                      onClick: _withModifiers($event => (__props.page.deleteObservation(item, i)), ["stop"])
                    }, null, 8, ["loading", "onClick"])
                  ], 8, _hoisted_40))
                }), 128))
              ]))
            : (!__props.page.loading)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_45, "暂无观察期条目"))
              : _createCommentVNode$1("", true)
        ]),
        _createElementVNode$1("div", _hoisted_46, [
          _createElementVNode$1("div", _hoisted_47, [
            _cache[11] || (_cache[11] = _createTextVNode$1("订阅历史 ", -1)),
            _createElementVNode$1("span", _hoisted_48, "（共 " + _toDisplayString$1(__props.page.historyData.total) + " 条）", 1)
          ]),
          (__props.page.historyData.items && __props.page.historyData.items.length)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_49, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.historyData.items, (item, i) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: i,
                    class: "dc-history-row dc-status-row"
                  }, [
                    _createVNode$1(_component_VAvatar, {
                      rounded: "sm",
                      class: "dc-history-poster mr-2 flex-shrink-0"
                    }, {
                      default: _withCtx$1(() => [
                        (item.poster)
                          ? (_openBlock$1(), _createBlock$1(_component_VImg, {
                              key: 0,
                              src: __props.page.toPosterThumbnail(item.poster),
                              cover: ""
                            }, null, 8, ["src"]))
                          : (_openBlock$1(), _createBlock$1(_component_VIcon, {
                              key: 1,
                              icon: "mdi-filmstrip",
                              size: "14"
                            }))
                      ]),
                      _: 2
                    }, 1024),
                    _createElementVNode$1("div", _hoisted_50, [
                      _createElementVNode$1("div", _hoisted_51, _toDisplayString$1(item.title), 1),
                      _createElementVNode$1("div", _hoisted_52, [
                        _createVNode$1(_component_VChip, {
                          size: "x-small",
                          style: _normalizeStyle(__props.page.rankChipStyle(item.rank_key)),
                          variant: "tonal",
                          class: "dc-rank-chip mr-1"
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(item.rank_name || __props.page.rankNameOf(item.rank_key, item)), 1)
                          ]),
                          _: 2
                        }, 1032, ["style"]),
                        _createElementVNode$1("span", _hoisted_53, _toDisplayString$1(item.time ? item.time.split(' ')[0] : ''), 1)
                      ])
                    ]),
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      color: item.status === 'failed' ? 'error' : 'success',
                      variant: "tonal",
                      class: "dc-row-status"
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(item.status === 'failed' ? '订阅失败' : '订阅成功'), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"]),
                    _createVNode$1(_component_VBtn, {
                      icon: "mdi-delete-outline",
                      variant: "text",
                      size: "x-small",
                      color: "error",
                      class: "dc-row-action",
                      loading: __props.page.actionKey === __props.page.rowKey('sub', item, i),
                      onClick: $event => (__props.page.deleteSubscribeHistory(item, i))
                    }, null, 8, ["loading", "onClick"])
                  ]))
                }), 128))
              ]))
            : (!__props.page.loading)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_54, "暂无订阅记录"))
              : _createCommentVNode$1("", true),
          (__props.page.historyData.total_pages > 1)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_55, [
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  size: "x-small",
                  disabled: __props.page.historyData.page <= 1,
                  class: "mx-1",
                  onClick: _cache[2] || (_cache[2] = $event => (__props.page.goPage(__props.page.historyData.page - 1)))
                }, {
                  default: _withCtx$1(() => [...(_cache[12] || (_cache[12] = [
                    _createTextVNode$1("上一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createElementVNode$1("span", _hoisted_56, _toDisplayString$1(__props.page.historyData.page) + " / " + _toDisplayString$1(__props.page.historyData.total_pages), 1),
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  size: "x-small",
                  disabled: __props.page.historyData.page >= __props.page.historyData.total_pages,
                  class: "mx-1",
                  onClick: _cache[3] || (_cache[3] = $event => (__props.page.goPage(__props.page.historyData.page + 1)))
                }, {
                  default: _withCtx$1(() => [...(_cache[13] || (_cache[13] = [
                    _createTextVNode$1("下一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]))
            : _createCommentVNode$1("", true)
        ]),
        _createElementVNode$1("div", _hoisted_57, [
          _createElementVNode$1("div", _hoisted_58, [
            _cache[14] || (_cache[14] = _createTextVNode$1("观察日志 ", -1)),
            _createElementVNode$1("span", _hoisted_59, "（最近 " + _toDisplayString$1(__props.page.cheatLogs.length) + " 条）", 1)
          ]),
          (__props.page.cheatLogs && __props.page.cheatLogs.length)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_60, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(__props.page.cheatLogs.slice().reverse(), (log, i) => {
                  return (_openBlock$1(), _createElementBlock$1("div", {
                    key: i,
                    class: "dc-history-row dc-status-row"
                  }, [
                    _createVNode$1(_component_VAvatar, {
                      rounded: "sm",
                      class: "dc-history-poster mr-2 flex-shrink-0"
                    }, {
                      default: _withCtx$1(() => [
                        (log.poster)
                          ? (_openBlock$1(), _createBlock$1(_component_VImg, {
                              key: 0,
                              src: __props.page.toPosterThumbnail(log.poster),
                              cover: ""
                            }, null, 8, ["src"]))
                          : (_openBlock$1(), _createBlock$1(_component_VIcon, {
                              key: 1,
                              icon: "mdi-filmstrip",
                              size: "14"
                            }))
                      ]),
                      _: 2
                    }, 1024),
                    _createElementVNode$1("div", _hoisted_61, [
                      _createElementVNode$1("div", _hoisted_62, _toDisplayString$1(log.title), 1),
                      _createElementVNode$1("div", _hoisted_63, [
                        _createVNode$1(_component_VChip, {
                          size: "x-small",
                          style: _normalizeStyle(__props.page.rankChipStyle(log.rank_key)),
                          variant: "tonal",
                          class: "dc-rank-chip mr-1"
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(log.rank_name || log.rank_key || '观察日志'), 1)
                          ]),
                          _: 2
                        }, 1032, ["style"]),
                        _createElementVNode$1("span", _hoisted_64, _toDisplayString$1(log.time ? log.time.split(' ')[0] : ''), 1)
                      ])
                    ]),
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      color: "warning",
                      variant: "tonal",
                      class: "dc-row-status"
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(log.reason || '观察日志'), 1)
                      ]),
                      _: 2
                    }, 1024),
                    _createVNode$1(_component_VBtn, {
                      icon: "mdi-delete-outline",
                      variant: "text",
                      size: "x-small",
                      color: "error",
                      class: "dc-row-action",
                      loading: __props.page.actionKey === __props.page.rowKey('log', log, i),
                      onClick: $event => (__props.page.deleteAntiCheatLog(log, i))
                    }, null, 8, ["loading", "onClick"])
                  ]))
                }), 128))
              ]))
            : (!__props.page.loading)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_65, "暂无观察日志"))
              : _createCommentVNode$1("", true)
        ])
      ], 64))
}
}

};
const PageContent = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-b9bc81df"]]);

const {reactive,ref} = await importShared('vue');

const INITIAL_LOAD_TIMEOUT_MS = 8000;

const rankNames = {
  coming: '即将上映',
  tv_real_time: '实时热门',
  tv_chinese: '华语口碑',
  tv_global: '全球口碑',
  movie_weekly: '电影口碑',
  bangumi: 'BangumiTV',
  douban_wish: '豆瓣想看',
  unknown: '未归类',
};

const rankIconColors = {
  coming: '#f97316',
  tv_real_time: '#06b6d4',
  tv_chinese: '#eab308',
  tv_global: '#ef4444',
  movie_weekly: '#ec4899',
  bangumi: '#8b5cf6',
  douban_wish: '#10b981',
  unknown: '#94a3b8',
};

function usePageRuntime({ api, pluginId, nativeSubscribe }) {
  const loading = ref(false);
  const stats = ref(null);
  const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  const archiveData = ref({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  const archivePage = ref(false);
  const cheatLogs = ref([]);
  const pendingObservations = ref([]);
  const rankHistory = ref({});
  const configData = ref({});
  const blacklistKeywords = ref([]);
  const blacklistEntries = ref([]);
  const actionKey = ref('');
  const actionMessage = ref('');
  const actionOk = ref(true);
  const loadError = ref('');
  const dialogItem = ref(null);
  const showDialog = ref(false);
  const dialogResolving = ref(false);
  const dialogResolveError = ref('');
  const dialogResolveToken = ref(0);

  function rankColorOf(key) {
    return rankIconColors[key] || rankIconColors.unknown
  }

  function rankIconStyle(key) {
    return { color: rankColorOf(key) }
  }

  function rankNameOf(key, item = null) {
    if (item?.rank_name) return item.rank_name
    const option = (configData.value?.rank_options || []).find(entry => entry?.value === key);
    return option?.title || rankNames[key] || key
  }

  function rankChipStyle(key) {
    const color = rankColorOf(key);
    return { color, backgroundColor: `${color}1f`, borderColor: `${color}73` }
  }

  function rowKey(prefix, item, index) {
    return `${prefix}:${item?.id || item?.unique || item?.time || item?.tmdbid || item?.title || index}`
  }

  function archiveRecord(item) {
    return item?.record && typeof item.record === 'object' ? item.record : {}
  }

  function archiveSourceName(item) {
    return item?.source_name || item?.source || '归档'
  }

  function archivePoster(item) {
    const record = archiveRecord(item);
    return toPosterThumbnail(item?.poster || record.poster || record.cover)
  }

  function archiveRankKey(item) {
    const record = archiveRecord(item);
    return item?.rank_key || record.rank_key || ''
  }

  function archiveRankName(item) {
    const key = archiveRankKey(item);
    const record = archiveRecord(item);
    return item?.rank_name || record.rank_name || rankNameOf(key, record) || key
  }

  function archiveTime(item) {
    const record = archiveRecord(item);
    return item?.time || record.time || record.first_seen || item?.archived_at || ''
  }

  function archiveTitle(item) {
    const record = archiveRecord(item);
    return item?.title || record.title || '未命名条目'
  }

  function archiveStatus(item) {
    const record = archiveRecord(item);
    return item?.display_status || record.display_status || record.detail || item?.detail || record.reason || item?.reason || archiveSourceName(item)
  }

  function archiveColor(item) {
    const source = item?.source || '';
    const reason = item?.reason || archiveRecord(item).reason || '';
    if (archiveSourceName(item) === '黑名拦截' || reason === '黑名拦截') return 'error'
    if (source === 'subscribe_history') return archiveStatus(item) === '订阅失败' ? 'error' : 'success'
    if (source === 'observation' || source === 'anti_cheat_log') return 'warning'
    return 'primary'
  }

  function archiveIcon(item) {
    const source = item?.source || '';
    const reason = item?.reason || archiveRecord(item).reason || '';
    if (archiveSourceName(item) === '黑名拦截' || reason === '黑名拦截') return 'mdi-block-helper'
    if (source === 'observation') return 'mdi-clock-outline'
    if (source === 'subscribe_history') return 'mdi-filmstrip'
    if (source === 'anti_cheat_log') return 'mdi-eye-check-outline'
    return 'mdi-archive-outline'
  }

  const {
    mediaTypeOf,
    normalizeApiData,
    queryString,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  } = useRankMediaActions({ api, pluginId, rankNameOf });

  async function loadAll() {
    loading.value = true;
    loadError.value = '';
    const requests = [
      { label: '订阅统计', path: 'stats', apply: value => { if (value) stats.value = value; } },
      {
        label: '订阅历史',
        path: `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`,
        apply: value => { if (value) historyData.value = value; },
      },
      { label: '观察日志', path: 'anti_cheat_logs', apply: value => {
        if (value) {
          const logs = Array.isArray(value) ? value : [];
          cheatLogs.value = logs.filter(log => !log || !['黑名拦截', '黑名单关键词'].includes(log.reason)).slice(-5);
          blacklistEntries.value = logs.filter(log => log && ['黑名拦截', '黑名单关键词'].includes(log.reason)).slice().reverse().slice(0, 5);
        }
      } },
      { label: '观察队列', path: 'pending_observations', apply: value => { if (value) pendingObservations.value = value; } },
      { label: '榜单快照', path: 'rank_history', apply: value => { if (value) rankHistory.value = value; } },
      { label: '运行配置', path: 'config', apply: value => {
        if (value) {
          configData.value = value;
          blacklistKeywords.value = String(value.blacklist_keywords || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
        }
      } },
    ];
    const results = await Promise.allSettled(requests.map(async request => {
      const response = await getPluginApi(api(), pluginId(), request.path, { timeoutMs: INITIAL_LOAD_TIMEOUT_MS });
      if (response?.success === false) throw new Error(response.message || `${request.label}加载失败`)
      request.apply(normalizeApiData(response));
    }));
    const failed = [];
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        failed.push(requests[index].label);
        console.error(`[DoubanCenter] ${requests[index].label}加载失败`, result.reason);
      }
    });
    loadError.value = failed.length ? `部分数据加载失败：${failed.join('、')}` : '';
    loading.value = false;
  }

  async function loadArchive() {
    loading.value = true;
    loadError.value = '';
    try {
      const fetchPage = async page => {
        const response = await getPluginApi(api(), pluginId(), `archive_records?page=${page}&page_size=${archiveData.value.page_size}`, { timeoutMs: INITIAL_LOAD_TIMEOUT_MS });
        if (response?.success === false) throw new Error(response.message || '归档记录加载失败')
        return normalizeApiData(response)
      };
      let data = await fetchPage(archiveData.value.page);
      const lastPage = Math.max(Number(data?.total_pages) || 0, 1);
      if ((Number(data?.page) || 1) > lastPage) data = await fetchPage(lastPage);
      if (data) archiveData.value = data;
    } catch (error) {
      loadError.value = '归档记录加载失败';
      console.error('[DoubanCenter] 归档记录加载失败', error);
    } finally {
      loading.value = false;
    }
  }

  async function openArchivePage() {
    archivePage.value = true;
    await loadArchive();
  }

  function closeArchivePage() {
    archivePage.value = false;
  }

  async function goPage(page) {
    if (page < 1 || page > historyData.value.total_pages) return
    historyData.value.page = page;
    await loadAll();
  }

  async function goArchivePage(page) {
    if (page < 1 || page > archiveData.value.total_pages || page === archiveData.value.page) return
    archiveData.value.page = page;
    await loadArchive();
  }

  async function runDelete(path, body, key, successText) {
    if (actionKey.value) return
    actionKey.value = key;
    actionMessage.value = '';
    actionOk.value = true;
    try {
      const qs = queryString(body);
      const response = await postPluginApi(api(), pluginId(), qs ? `${path}?${qs}` : path, {});
      actionOk.value = !!response?.success;
      actionMessage.value = response?.message || (actionOk.value ? successText : '操作失败');
      if (archivePage.value) await loadArchive();
      else await loadAll();
    } catch (error) {
      actionOk.value = false;
      actionMessage.value = error?.message || '操作失败';
    } finally {
      actionKey.value = '';
    }
  }

  async function deleteObservation(item, index) {
    await runDelete('delete_observation', { unique: item?.unique || '', rank_key: item?.rank_key || '', title: item?.title || '' }, rowKey('obs', item, index), '已删除观察条目');
  }

  async function deleteSubscribeHistory(item, index) {
    await runDelete('delete_subscribe_history', {
      time: item?.time || '',
      title: item?.title || '',
      media_source: item?.media_source || '',
      media_id: item?.media_id || '',
      tmdbid: item?.tmdbid || '',
    }, rowKey('sub', item, index), '已删除订阅历史');
  }

  async function deleteAntiCheatLog(item, index) {
    await runDelete('delete_anti_cheat_log', { time: item?.time || '', title: item?.title || '', reason: item?.reason || '' }, rowKey('log', item, index), '已删除观察日志');
  }

  async function restoreArchive(item, index) {
    await runDelete('restore_archive', { archive_id: item?.id || '' }, rowKey('archive-restore', item, index), '已恢复归档记录');
  }

  async function deleteArchive(item, index) {
    await runDelete('delete_archive', { archive_id: item?.id || '' }, rowKey('archive-delete', item, index), '已删除归档记录');
  }

  async function showActionDialog(rk, item) {
    const token = ++dialogResolveToken.value;
    dialogItem.value = { rk, item: { ...(item || {}) } };
    dialogResolveError.value = '';
    showDialog.value = true;
    if (tmdbIdOf(item)) return
    dialogResolving.value = true;
    try {
      const media = await resolveRankMedia(rk, item);
      if (token !== dialogResolveToken.value) return
      dialogItem.value = { rk, item: media };
      if (!tmdbIdOf(media)) dialogResolveError.value = '未找到对应的 TMDB 条目';
    } catch (error) {
      if (token === dialogResolveToken.value) dialogResolveError.value = error?.message || 'TMDB 识别失败';
    } finally {
      if (token === dialogResolveToken.value) dialogResolving.value = false;
    }
  }

  function dialogPoster() {
    const item = dialogItem.value?.item || {};
    return toPosterThumbnail(item.poster || item.poster_path || item.cover)
  }

  async function subscribeViaNativeDialog(rk, item) {
    const media = await resolveRankMedia(rk, item);
    await nativeSubscribe()(media);
    actionOk.value = true;
    actionMessage.value = '已打开 MP 原生订阅窗口';
  }

  async function subscribeRankItem(rk, item) {
    const response = await requestRankSubscription(rk, item);
    if (!response?.success) throw new Error(response?.message || '订阅失败')
    actionOk.value = true;
    actionMessage.value = response?.message || `${item.title || ''} 已添加订阅`;
    await loadAll();
  }

  async function doSubscribe() {
    if (!dialogItem.value || dialogResolving.value) return
    const { rk, item } = dialogItem.value;
    showDialog.value = false;
    actionMessage.value = '';
    actionOk.value = true;
    try {
      if (nativeSubscribe()) await subscribeViaNativeDialog(rk, item);
      else await subscribeRankItem(rk, item);
    } catch (error) {
      actionOk.value = false;
      actionMessage.value = `订阅失败: ${error?.message || error}`;
    }
  }

  function sourceButtonDescriptor() {
    if (!dialogItem.value) return { color: 'primary', icon: 'mdi-link-variant', label: '详情', url: '', appUrl: '' }
    const { rk, item } = dialogItem.value;
    return sourceDescriptor(rk, item, configData.value)
  }

  function sourceButtonColor() {
    return sourceButtonDescriptor().color
  }

  function sourceButtonIcon() {
    return sourceButtonDescriptor().icon
  }

  function sourceButtonLabel() {
    return sourceButtonDescriptor().label
  }

  function sourceButtonUrl() {
    return sourceButtonDescriptor().url
  }

  function sourceButtonAppUrl() {
    return sourceButtonDescriptor().appUrl || ''
  }

  function sourceButtonHref() {
    return sourceButtonAppUrl() || sourceButtonUrl()
  }

  function openSource(event) {
    const appUrl = sourceButtonAppUrl();
    if (!appUrl) {
      showDialog.value = false;
      return
    }
    event?.preventDefault?.();
    showDialog.value = false;
    window.open(appUrl, '_blank');
  }

  function doOpenTmdb() {
    if (!dialogItem.value) return
    const { rk, item } = dialogItem.value;
    const tmdbId = tmdbIdOf(item);
    if (!tmdbId) return
    const mediaType = mediaTypeOf(rk, item);
    const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`;
    showDialog.value = false;
    window.open(url, '_blank');
  }

  return reactive({
    loading, stats, historyData, archiveData, archivePage, cheatLogs, pendingObservations,
    rankHistory, blacklistKeywords, blacklistEntries, actionKey, actionMessage, actionOk,
    loadError, dialogItem, showDialog, dialogResolving, dialogResolveError,
    rankColorOf, rankIconStyle, rankNameOf, rankChipStyle, rowKey, archiveSourceName,
    archivePoster, archiveRankKey, archiveRankName, archiveTime, archiveTitle, archiveStatus,
    archiveColor, archiveIcon, loadAll, loadArchive, openArchivePage, closeArchivePage,
    goPage, goArchivePage, deleteObservation, deleteSubscribeHistory, deleteAntiCheatLog,
    restoreArchive, deleteArchive, showActionDialog, dialogPoster, doSubscribe,
    sourceButtonColor, sourceButtonIcon, sourceButtonLabel, sourceButtonUrl, sourceButtonHref,
    openSource, doOpenTmdb, tmdbIdOf, toPosterThumbnail,
  })
}

const {unref:_unref,resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "dc-page-heading" };
const _hoisted_2 = { class: "text-h6" };
const _hoisted_3 = { class: "text-caption text-medium-emphasis" };
const _hoisted_4 = { class: "dc-page-toolbar-actions" };
const _hoisted_5 = { class: "dc-toolbar-label" };
const _hoisted_6 = { class: "dc-load-alert__content" };

const {onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DoubanCenter' },
  nativeSubscribe: { type: Function, default: null },
  appPage: { type: Boolean, default: false },
  showSettings: { type: Boolean, default: false },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const page = usePageRuntime({
  api: () => props.api,
  pluginId: () => props.pluginId,
  nativeSubscribe: () => props.nativeSubscribe,
});

onMounted(page.loadAll);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: _normalizeClass(["dc-page", { 'dc-page--app': props.appPage, 'dc-page--archive': _unref(page).archivePage }])
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VToolbar, {
        density: "comfortable",
        class: "dc-page-toolbar"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            class: "ms-3 me-2 dc-page-avatar",
            style: {"display":"flex !important","width":"32px","height":"32px","min-width":"32px"}
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-book-open-page-variant-outline" })
            ]),
            _: 1
          }),
          _createElementVNode("div", _hoisted_1, [
            _createElementVNode("div", _hoisted_2, _toDisplayString(_unref(page).archivePage ? '豆瓣中心 · 归档记录' : '豆瓣中心 · 运行详情'), 1),
            _createElementVNode("div", _hoisted_3, _toDisplayString(_unref(page).archivePage ? '删除进入归档，支持恢复或彻底删除' : '榜单刷新 -> 黑名筛选 -> 观察队列 -> 订阅记录'), 1)
          ]),
          _createVNode(_component_VSpacer),
          _createElementVNode("div", _hoisted_4, [
            _createVNode(_component_VBtn, {
              variant: "text",
              size: "small",
              class: "text-none dc-toolbar-action",
              title: "刷新",
              "aria-label": "刷新",
              loading: _unref(page).loading,
              onClick: _cache[0] || (_cache[0] = $event => (_unref(page).archivePage ? _unref(page).loadArchive() : _unref(page).loadAll()))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-refresh",
                  size: "18",
                  class: "dc-toolbar-icon"
                }),
                _cache[5] || (_cache[5] = _createElementVNode("span", { class: "dc-toolbar-label" }, "刷新", -1))
              ]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              variant: "text",
              size: "small",
              class: "text-none dc-toolbar-action",
              title: _unref(page).archivePage ? '返回' : '归档',
              "aria-label": _unref(page).archivePage ? '返回' : '归档',
              color: _unref(page).archivePage ? 'primary' : undefined,
              onClick: _cache[1] || (_cache[1] = $event => (_unref(page).archivePage ? _unref(page).closeArchivePage() : _unref(page).openArchivePage()))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: _unref(page).archivePage ? 'mdi-arrow-left' : 'mdi-archive-outline',
                  size: "18",
                  class: "dc-toolbar-icon"
                }, null, 8, ["icon"]),
                _createElementVNode("span", _hoisted_5, _toDisplayString(_unref(page).archivePage ? '返回' : '归档'), 1)
              ]),
              _: 1
            }, 8, ["title", "aria-label", "color"]),
            (props.showSettings || !props.appPage)
              ? (_openBlock(), _createBlock(_component_VBtn, {
                  key: 0,
                  variant: "text",
                  size: "small",
                  class: "text-none dc-toolbar-action",
                  title: "设置",
                  "aria-label": "设置",
                  onClick: _cache[2] || (_cache[2] = $event => (emit('switch')))
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-cog-outline",
                      size: "18",
                      class: "dc-toolbar-icon"
                    }),
                    _cache[6] || (_cache[6] = _createElementVNode("span", { class: "dc-toolbar-label" }, "设置", -1))
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (!props.appPage)
              ? (_openBlock(), _createBlock(_component_VBtn, {
                  key: 1,
                  icon: "",
                  variant: "text",
                  size: "small",
                  class: "dc-toolbar-action",
                  title: "关闭",
                  "aria-label": "关闭",
                  onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-close",
                      size: "18",
                      class: "dc-toolbar-icon"
                    })
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true)
          ])
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      (_unref(page).loading)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true),
      _createVNode(_component_VCardText, { class: "pa-3 dc-flow" }, {
        default: _withCtx(() => [
          (_unref(page).loadError)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "dc-load-alert"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_6, [
                    _createElementVNode("span", null, _toDisplayString(_unref(page).loadError), 1),
                    _createVNode(_component_VBtn, {
                      variant: "text",
                      size: "x-small",
                      "prepend-icon": "mdi-refresh",
                      class: "text-none",
                      loading: _unref(page).loading,
                      onClick: _cache[4] || (_cache[4] = $event => (_unref(page).archivePage ? _unref(page).loadArchive() : _unref(page).loadAll()))
                    }, {
                      default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                        _createTextVNode("重试", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (_unref(page).actionMessage)
            ? (_openBlock(), _createElementBlock("div", {
                key: 1,
                class: _normalizeClass(["dc-action-message", _unref(page).actionOk ? 'text-success' : 'text-error'])
              }, _toDisplayString(_unref(page).actionMessage), 3))
            : _createCommentVNode("", true),
          _createVNode(PageContent, { page: _unref(page) }, null, 8, ["page"])
        ]),
        _: 1
      }),
      _createVNode(PageActionDialog, { page: _unref(page) }, null, 8, ["page"])
    ]),
    _: 1
  }, 8, ["class"]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-3293d466"]]);

export { Page as default };
