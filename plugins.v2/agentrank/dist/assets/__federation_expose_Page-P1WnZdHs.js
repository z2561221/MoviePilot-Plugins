import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useAgentRankState, R as RecommendationActions } from './RecommendationActions-CMkkPJmS.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-BGNRvR24.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1 = { class: "ar-page" };
const _hoisted_2 = { class: "ar-page__summary-bar" };
const _hoisted_3 = { class: "ar-page__stat-value" };
const _hoisted_4 = { class: "ar-page__stat-label" };
const _hoisted_5 = {
  class: "ar-page__tabs",
  "aria-label": "详情视图"
};
const _hoisted_6 = ["aria-current", "onClick"];
const _hoisted_7 = { class: "ar-page__content" };
const _hoisted_8 = { class: "ar-page__pane" };
const _hoisted_9 = { class: "ar-page__section-head" };
const _hoisted_10 = {
  key: 1,
  class: "ar-page__ranking"
};
const _hoisted_11 = { class: "ar-page__poster" };
const _hoisted_12 = { class: "ar-page__poster-error" };
const _hoisted_13 = { class: "ar-page__rank-main" };
const _hoisted_14 = { class: "ar-page__title-row" };
const _hoisted_15 = { class: "ar-page__media-title" };
const _hoisted_16 = { class: "ar-page__meta-row" };
const _hoisted_17 = { class: "ar-page__rank-copy" };
const _hoisted_18 = { class: "ar-page__rank-copy ar-page__rank-copy--muted" };
const _hoisted_19 = {
  key: 0,
  class: "ar-page__match-tags"
};
const _hoisted_20 = { class: "ar-page__rank-actions" };
const _hoisted_21 = { class: "ar-page__pane" };
const _hoisted_22 = { class: "ar-page__section-head" };
const _hoisted_23 = { class: "ar-page__profile-summary-panel" };
const _hoisted_24 = { class: "ar-page__profile-label" };
const _hoisted_25 = { class: "ar-page__profile-summary" };
const _hoisted_26 = { class: "ar-page__profile-metrics" };
const _hoisted_27 = { class: "ar-page__profile-groups" };
const _hoisted_28 = { class: "ar-page__profile-group" };
const _hoisted_29 = { class: "ar-page__profile-label" };
const _hoisted_30 = { class: "ar-page__chips" };
const _hoisted_31 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_32 = { class: "ar-page__tag-editor" };
const _hoisted_33 = { class: "ar-page__profile-group" };
const _hoisted_34 = { class: "ar-page__profile-label ar-page__profile-label--negative" };
const _hoisted_35 = { class: "ar-page__chips" };
const _hoisted_36 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_37 = { class: "ar-page__tag-editor" };
const _hoisted_38 = { class: "ar-page__profile-group" };
const _hoisted_39 = { class: "ar-page__profile-label" };
const _hoisted_40 = { class: "ar-page__chips" };
const _hoisted_41 = {
  key: 0,
  class: "ar-page__tag-count"
};
const _hoisted_42 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_43 = { class: "ar-page__pane" };
const _hoisted_44 = { class: "ar-page__section-head" };
const _hoisted_45 = {
  key: 1,
  class: "ar-page__archive-list"
};
const _hoisted_46 = { class: "ar-page__archive-rank" };
const _hoisted_47 = { class: "ar-page__pane" };
const _hoisted_48 = { class: "ar-page__section-head" };
const _hoisted_49 = { class: "ar-page__history-list" };
const _hoisted_50 = { class: "ar-page__history-head" };
const _hoisted_51 = { class: "ar-page__history-time" };
const _hoisted_52 = { key: 0 };
const _hoisted_53 = { class: "ar-page__history-message" };
const _hoisted_54 = { class: "ar-page__history-metrics" };
const _hoisted_55 = {
  key: 0,
  class: "ar-page__history-pipeline"
};
const _hoisted_56 = { class: "ar-page__history-footer" };
const _hoisted_57 = {
  key: 1,
  class: "ar-page__history-details"
};

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');

const historyPageSize = 10;


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const state = useAgentRankState(props.api);

const activeTab = ref('board');
const snackbar = ref({ show: false, message: '', color: 'success' });
const historyPage = ref(1);
const initialized = ref(false);
const expandedCopyKeys = ref(new Set());
const expandedHistoryKeys = ref(new Set());
const tagDrafts = reactive({ positive: '', negative: '' });
const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 10) || []);
const archiveEntries = computed(() => state.overview.value?.archive?.entries || []);
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)));
const positiveTags = computed(() => state.profile.value?.tags || []);
const negativeTags = computed(() => state.profile.value?.negative_tags || []);
const profileStats = computed(() => [
  { label: '播放样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-database-check-outline' },
  { label: '偏好标签', value: positiveTags.value.length, suffix: '个', icon: 'mdi-heart-outline' },
  { label: '避雷标签', value: negativeTags.value.length, suffix: '个', icon: 'mdi-shield-alert-outline' },
]);
const boardMatchTags = computed(() => {
  const counts = new Map();
  recommendations.value.forEach(item => {
    const tags = item.match_tags || [];
    tags.forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
    .slice(0, 10)
    .map(([tag, count]) => ({ tag, count }))
});
const profileRunId = computed(() => String(state.profile.value?.run_id || '').slice(0, 8) || '—');
const detailStats = computed(() => [
  { label: '榜单条目', value: recommendations.value.length, suffix: '部', icon: 'mdi-format-list-numbered' },
  { label: '画像样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-account-heart-outline' },
  { label: '忽略归档', value: archiveEntries.value.length, suffix: '部', icon: 'mdi-archive-outline' },
]);

const statusMetaFor = status => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
  profile_agent_failed: { text: '画像生成失败', color: 'error' },
  profile_validation_failed: { text: '画像校验失败', color: 'error' },
  candidate_failed: { text: '候选采集失败', color: 'error' },
  candidate_filter_failed: { text: '候选过滤失败', color: 'error' },
  candidate_snapshot_failed: { text: '候选快照失败', color: 'error' },
  ranking_agent_failed: { text: '排序生成失败', color: 'error' },
  ranking_validation_failed: { text: '排序校验失败', color: 'error' },
  ranking_save_failed: { text: '榜单保存失败', color: 'error' },
  runtime_exception: { text: '运行异常', color: 'error' },
  }[status] || { text: '运行异常', color: 'error' });

const historyStageLabels = {
  probe: '依赖探测',
  playback_snapshot: '冻结播放',
  profile: '生成画像',
  candidate: '冻结候选',
  ranking: 'Agent排序',
  save: '保存榜单',
};
const historyStageStatusLabels = {
  ready: '完成', generated: '已生成', reused: '复用', cached: '使用缓存', saved: '已保存',
  success: '成功', pending: '等待', running: '进行中', stopped: '停止', failed: '失败',
  sample_insufficient: '样本不足', candidate_insufficient: '候选不足',
  recommendation_incomplete: '榜单不足', agent_failed: 'Agent失败',
  validation_failed: '校验失败', subscription_partial_failed: '部分订阅失败',
  profile_agent_failed: '画像生成失败', profile_validation_failed: '画像校验失败',
  candidate_failed: '候选采集失败', candidate_filter_failed: '候选过滤失败',
  candidate_snapshot_failed: '候选快照失败', ranking_agent_failed: '排序生成失败',
  ranking_validation_failed: '排序校验失败', ranking_save_failed: '榜单保存失败', runtime_exception: '运行异常',
};
const historySourceLabels = {
  douban: '豆瓣', tmdb: 'TMDB', tmdb_movies: 'TMDB电影', tmdb_tv: 'TMDB剧集',
  tmdb_recommend: 'TMDB相关', bangumi: 'Bangumi', anilist: 'AniList',
};
const historyExclusionLabels = {
  invalid_or_unrecognized: '未识别', watched: '已观看', watched_completed: '已看完', library: '已入库',
  subscribed: '已订阅', archived: '已忽略', negative_keyword: '排除词',
  ambiguous_playback_count: '播放次数误写为看完次数',
  unsupported_playback_claim: '观看经历无法回溯',
};

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'archive', title: '忽略归档', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
];

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return ({ movie: '电影', tv: '剧集', anime: '动漫' })[value] || '其他类型'
}

function copyKey(item, field) { return `${item?.candidate_id || item?.rank || ''}:${field}` }
function isCopyExpanded(item, field) { return expandedCopyKeys.value.has(copyKey(item, field)) }
function toggleCopy(item, field) {
  const key = copyKey(item, field);
  const next = new Set(expandedCopyKeys.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedCopyKeys.value = next;
}

function historyKey(run) { return `${run?.run_id || ''}:${run?.finished_at || run?.started_at || ''}` }
function isHistoryExpanded(run) { return expandedHistoryKeys.value.has(historyKey(run)) }
function toggleHistory(run) {
  const key = historyKey(run);
  const next = new Set(expandedHistoryKeys.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedHistoryKeys.value = next;
}
function formatDuration(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)} 毫秒`
  return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} 秒`
}
function historyStages(run) {
  const metrics = run?.metrics || {};
  return (Array.isArray(metrics.stage_order) ? metrics.stage_order : []).map(key => ({
    key,
    title: historyStageLabels[key] || '其他阶段',
    status: historyStageStatusLabels[metrics.stage_status?.[key]] || '未记录',
    duration: formatDuration(metrics.stage_ms?.[key]),
    failed: /failed|error|insufficient|validation/i.test(String(metrics.stage_status?.[key] || '')),
  }))
}
function translateHistoryError(value) {
  let text = String(value || '');
  text = text
    .replace(/^playback probe:/i, '播放探测：')
    .replace(/^playback:/i, '播放快照：')
    .replace(/^profile:/i, '画像阶段：')
    .replace(/^candidate:/i, '候选阶段：')
    .replace(/^ranking:/i, '排序阶段：')
    .replace(/^refill:/i, '补选阶段：')
    .replace(/Agent output must be one JSON object:\s*Expecting value/gi, 'Agent 输出不是有效的 JSON 对象：内容为空或格式错误')
    .replace(/Agent output must be one JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent output must be text/gi, 'Agent 输出不是文本')
    .replace(/Expecting value/gi, '内容为空或格式错误')
    .replace(/Extra data/gi, '存在多余内容')
    .replace(/Invalid control character/gi, '包含无效控制字符')
    .replace(/Unterminated string/gi, '字符串未闭合')
    .replace(/profile_validation_failed/gi, '画像校验失败')
    .replace(/ranking_validation_failed/gi, '排序校验失败')
    .replace(/candidate_insufficient/gi, '候选不足')
    .replace(/recommendation_incomplete/gi, '榜单不足')
    .replace(/ambiguous_playback_count/gi, '播放次数误写为看完次数')
    .replace(/unsupported_playback_claim/gi, '观看经历无法回溯')
    .replace(/Agent did not produce a JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent did not produce text output/gi, 'Agent 输出不是文本');
  return text
}
function historyErrorText(run) {
  const errors = Array.isArray(run?.errors) ? run.errors : [];
  if (errors.length) {
    return errors.map(error => translateHistoryError(String(error)
      .replace(/^profile attempt\s+(\d+):/i, '画像第 $1 次：')
      .replace(/^refill attempt\s+(\d+):/i, '补选第 $1 次：')
      .replace(/^attempt\s+(\d+):/i, '排序第 $1 次：')
      .replace(/^profile:/i, '画像阶段：')
      .replace(/^candidate:/i, '候选阶段：')
      .replace(/^ranking:/i, '排序阶段：')
      .replace(/^refill:/i, '补选阶段：'))).join('；')
  }
  return translateHistoryError(run?.message || '本轮没有错误')
}
function historySourceText(run) {
  const sources = run?.metrics?.candidate_source_counts || run?.metrics?.fetched_source_counts || {};
  return Object.entries(sources).map(([key, value]) => `${historySourceLabels[key] || '其他来源'} ${value}`).join('、') || '无来源统计'
}
function historyExclusionText(run) {
  const exclusions = run?.metrics?.candidate_exclusion_counts || {};
  return Object.entries(exclusions).map(([key, value]) => `${historyExclusionLabels[key] || '其他排除原因'} ${value}`).join('、') || '无'
}
function historyPlaybackStatus(value) {
  return ({ ready: '已就绪', cached: '使用缓存', disabled: '已停用', error: '失败', transient_error: '临时错误' })[value] || '状态未知'
}

async function initialize() {
  try {
    await state.loadOptions();
    if (state.selectedProfileId.value) await state.loadProfileData();
  } catch (_) {
    // 共享状态承载错误。
  } finally {
    initialized.value = true;
  }
}

async function runAction(action, successMessage) {
  try {
    await action();
    snackbar.value = { show: true, message: successMessage, color: 'success' };
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' };
  }
}

async function changeHistoryPage(page) {
  historyPage.value = page;
  try { await state.loadHistory(page, historyPageSize); } catch (_) { /* 错误已保存 */ }
}

async function addProfileTag(kind) {
  const tag = String(tagDrafts[kind] || '').trim();
  if (!tag) return
  await runAction(
    () => state.updateProfileTag(kind, 'add', tag),
    kind === 'positive' ? '偏好标签已添加' : '避雷标签已添加',
  );
  tagDrafts[kind] = '';
}

async function removeProfileTag(kind, tag) {
  await runAction(
    () => state.updateProfileTag(kind, 'remove', tag),
    kind === 'positive' ? '偏好标签已删除' : '避雷标签已删除',
  );
}

watch(state.selectedProfileId, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  historyPage.value = 1;
  try { await state.loadProfileData(value); } catch (_) { /* 错误已保存 */ }
});

watch(activeTab, async value => {
  if (value === 'history') await changeHistoryPage(1);
});

onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSkeletonLoader = _resolveComponent("VSkeletonLoader");
  const _component_VEmptyState = _resolveComponent("VEmptyState");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "ar-page__toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VAvatar, {
          color: "primary",
          variant: "tonal",
          size: "42",
          rounded: "lg",
          class: "ar-page__brand ms-4 me-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VIcon, {
              icon: "mdi-brain",
              size: "24"
            })
          ]),
          _: 1
        }),
        _cache[14] || (_cache[14] = _createElementVNode("div", { class: "ar-page__heading" }, [
          _createElementVNode("div", { class: "ar-page__title" }, "Agent榜单中心"),
          _createElementVNode("div", { class: "ar-page__subtitle" }, "推荐结果、用户画像与运行记录")
        ], -1)),
        _createVNode(_component_VSpacer),
        (_unref(state).identities.value.length > 1)
          ? (_openBlock(), _createBlock(_component_VSelect, {
              key: 0,
              modelValue: _unref(state).selectedProfileId.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref(state).selectedProfileId.value) = $event)),
              items: _unref(state).identityOptions.value,
              "item-title": "title",
              "item-value": "value",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              label: "Emby 用户",
              class: "ar-page__identity",
              "aria-label": "切换 Emby 画像身份"
            }, null, 8, ["modelValue", "items"]))
          : _createCommentVNode("", true),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          loading: _unref(state).loading.action === 'refresh' || _unref(state).loading.data,
          disabled: _unref(state).isRunning.value,
          "aria-label": "刷新详情",
          onClick: _cache[1] || (_cache[1] = $event => (runAction(_unref(state).refresh, '榜单刷新已完成')))
        }, null, 8, ["loading", "disabled"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-cog-outline",
          variant: "text",
          "aria-label": "打开设置",
          onClick: _cache[2] || (_cache[2] = $event => (emit('switch')))
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          "aria-label": "关闭详情",
          class: "me-2",
          onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(detailStats.value, (stat) => {
        return (_openBlock(), _createElementBlock("div", {
          key: stat.label,
          class: "ar-page__stat"
        }, [
          _createVNode(_component_VIcon, {
            icon: stat.icon,
            color: "primary",
            size: "20"
          }, null, 8, ["icon"]),
          _createElementVNode("div", null, [
            _createElementVNode("div", _hoisted_3, [
              _createTextVNode(_toDisplayString(stat.value), 1),
              _createElementVNode("span", null, _toDisplayString(stat.suffix), 1)
            ]),
            _createElementVNode("div", _hoisted_4, _toDisplayString(stat.label), 1)
          ])
        ]))
      }), 128)),
      (_unref(state).isRunning.value)
        ? (_openBlock(), _createBlock(_component_VChip, {
            key: 0,
            color: "primary",
            variant: "tonal",
            size: "small",
            "prepend-icon": "mdi-loading",
            class: "ar-page__runtime-chip"
          }, {
            default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
              _createTextVNode(" 正在生成 ", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode("", true)
    ]),
    _createElementVNode("nav", _hoisted_5, [
      (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
        return _createElementVNode("button", {
          key: tab.key,
          type: "button",
          class: _normalizeClass(["ar-page__tab", { 'ar-page__tab--active': activeTab.value === tab.key }]),
          "aria-current": activeTab.value === tab.key ? 'page' : undefined,
          onClick: $event => (activeTab.value = tab.key)
        }, [
          _createVNode(_component_VIcon, {
            icon: tab.icon,
            size: "17",
            class: "ar-page__tab-icon"
          }, null, 8, ["icon"]),
          _createElementVNode("span", null, _toDisplayString(tab.title), 1)
        ], 10, _hoisted_6)
      }), 64))
    ]),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_7, [
      (_unref(state).error.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            class: "mb-3"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(_unref(state).error.value.message), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (_unref(state).loading.data)
        ? (_openBlock(), _createBlock(_component_VSkeletonLoader, {
            key: 1,
            type: "list-item-avatar-three-line@5"
          }))
        : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
            _withDirectives(_createElementVNode("section", _hoisted_8, [
              _createElementVNode("div", _hoisted_9, [
                _cache[16] || (_cache[16] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "个性推荐榜单"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "Agent 根据订阅画像，从发现候选中挑出的前10名。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  color: "primary",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(recommendations.value.length) + " 部", 1)
                  ]),
                  _: 1
                })
              ]),
              (!recommendations.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-format-list-numbered",
                    title: "推荐榜单尚未生成",
                    text: "点击右上角刷新，根据播放画像生成前10名。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_10, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recommendations.value, (item) => {
                      return (_openBlock(), _createElementBlock("article", {
                        key: item.candidate_id,
                        class: "ar-page__rank-item"
                      }, [
                        _createElementVNode("div", {
                          class: _normalizeClass(["ar-page__rank", { 'ar-page__rank--top': item.rank <= 3 }])
                        }, _toDisplayString(item.rank), 3),
                        _createElementVNode("div", _hoisted_11, [
                          (item.poster_path)
                            ? (_openBlock(), _createBlock(_component_VImg, {
                                key: 0,
                                src: item.poster_path,
                                alt: `${item.title} 海报`,
                                cover: ""
                              }, {
                                error: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_12, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-image-off-outline",
                                      size: "26"
                                    })
                                  ])
                                ]),
                                _: 1
                              }, 8, ["src", "alt"]))
                            : (_openBlock(), _createBlock(_component_VIcon, {
                                key: 1,
                                icon: "mdi-image-off-outline",
                                size: "26"
                              }))
                        ]),
                        _createElementVNode("div", _hoisted_13, [
                          _createElementVNode("div", _hoisted_14, [
                            _createElementVNode("div", _hoisted_15, _toDisplayString(item.title), 1),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(mediaTypeLabel(item.media_type)), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _createElementVNode("div", _hoisted_16, [
                            _createElementVNode("span", null, _toDisplayString(item.year || '年份未知'), 1)
                          ]),
                          _createElementVNode("div", _hoisted_17, [
                            _cache[17] || (_cache[17] = _createElementVNode("span", { class: "ar-page__copy-label" }, "推荐：", -1)),
                            _createElementVNode("span", {
                              class: _normalizeClass(["ar-page__copy-text ar-page__copy-text--reason", { 'ar-page__copy-text--expanded': isCopyExpanded(item, 'reason') }])
                            }, _toDisplayString(item.reason || item.summary || '等待 Agent 补充推荐理由'), 3),
                            (item.reason || item.summary)
                              ? (_openBlock(), _createBlock(_component_VBtn, {
                                  key: 0,
                                  size: "x-small",
                                  variant: "text",
                                  class: "ar-page__copy-toggle",
                                  onClick: $event => (toggleCopy(item, 'reason'))
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(isCopyExpanded(item, 'reason') ? '收起' : '展开'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["onClick"]))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_18, [
                            _cache[18] || (_cache[18] = _createElementVNode("span", { class: "ar-page__copy-label" }, "简介：", -1)),
                            _createElementVNode("span", {
                              class: _normalizeClass(["ar-page__copy-text ar-page__copy-text--intro", { 'ar-page__copy-text--expanded': isCopyExpanded(item, 'summary') }])
                            }, _toDisplayString(item.summary || '暂无简介'), 3),
                            (item.summary)
                              ? (_openBlock(), _createBlock(_component_VBtn, {
                                  key: 0,
                                  size: "x-small",
                                  variant: "text",
                                  class: "ar-page__copy-toggle",
                                  onClick: $event => (toggleCopy(item, 'summary'))
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(isCopyExpanded(item, 'summary') ? '收起' : '展开'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["onClick"]))
                              : _createCommentVNode("", true)
                          ]),
                          (item.match_tags?.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_19, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.match_tags, (tag) => {
                                  return (_openBlock(), _createBlock(_component_VChip, {
                                    key: tag,
                                    size: "x-small",
                                    variant: "outlined"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(tag), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                }), 128))
                              ]))
                            : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("div", _hoisted_20, [
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: "primary",
                            variant: "tonal",
                            class: "ar-page__confidence"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(item.confidence) + "%", 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(RecommendationActions, {
                            item: item,
                            "loading-action": _unref(state).loading.action,
                            "native-subscribe": __props.nativeSubscribe,
                            size: "small",
                            onSubscribe: _cache[4] || (_cache[4] = candidateId => runAction(() => _unref(state).subscribe(candidateId), '订阅操作已完成')),
                            onArchive: _cache[5] || (_cache[5] = candidateId => runAction(() => _unref(state).archive(candidateId), '已忽略推荐'))
                          }, null, 8, ["item", "loading-action", "native-subscribe"])
                        ])
                      ]))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'board']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_21, [
              _createElementVNode("div", _hoisted_22, [
                _cache[19] || (_cache[19] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "用户画像"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "用播放样本描述偏好、避雷方向与本轮榜单命中。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal",
                  "prepend-icon": "mdi-clock-outline"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(formatTime(_unref(state).profile.value?.generated_at)), 1)
                  ]),
                  _: 1
                })
              ]),
              _createVNode(_component_VCard, {
                variant: "outlined",
                class: "ar-page__section-card"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardItem, { class: "ar-page__profile-head" }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VAvatar, {
                        color: "primary",
                        variant: "tonal",
                        size: "44"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VIcon, { icon: "mdi-account-heart-outline" })
                        ]),
                        _: 1
                      })
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VCardTitle, { class: "text-subtitle-1 font-weight-bold" }, {
                        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                          _createTextVNode("画像摘要", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode(_component_VCardSubtitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode("Emby 用户 " + _toDisplayString(_unref(state).selectedUsername.value || '—') + " · 运行 " + _toDisplayString(profileRunId.value), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VDivider),
                  _createVNode(_component_VCardText, { class: "ar-page__profile-body" }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_23, [
                        _createElementVNode("div", _hoisted_24, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-text-box-search-outline",
                            size: "18"
                          }),
                          _cache[21] || (_cache[21] = _createTextVNode("口味摘要", -1))
                        ]),
                        _createElementVNode("div", _hoisted_25, _toDisplayString(_unref(state).profile.value?.summary || '尚未生成用户画像'), 1)
                      ]),
                      _createElementVNode("div", _hoisted_26, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(profileStats.value, (stat) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: stat.label,
                            class: "ar-page__profile-metric"
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: stat.icon,
                              color: "primary",
                              size: "19"
                            }, null, 8, ["icon"]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, [
                                _createTextVNode(_toDisplayString(stat.value), 1),
                                _createElementVNode("span", null, _toDisplayString(stat.suffix), 1)
                              ]),
                              _createElementVNode("small", null, _toDisplayString(stat.label), 1)
                            ])
                          ]))
                        }), 128))
                      ]),
                      _createElementVNode("div", _hoisted_27, [
                        _createElementVNode("div", _hoisted_28, [
                          _createElementVNode("div", _hoisted_29, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-heart-outline",
                              size: "18"
                            }),
                            _cache[22] || (_cache[22] = _createTextVNode("偏好标签", -1))
                          ]),
                          _createElementVNode("div", _hoisted_30, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(positiveTags.value, (tag) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: tag,
                                color: "primary",
                                variant: "tonal",
                                size: "small",
                                closable: "",
                                "onClick:close": $event => (removeProfileTag('positive', tag))
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(tag), 1)
                                ]),
                                _: 2
                              }, 1032, ["onClick:close"]))
                            }), 128)),
                            (!positiveTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_31, "暂无偏好标签"))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_32, [
                            _createVNode(_component_VTextField, {
                              modelValue: tagDrafts.positive,
                              "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((tagDrafts.positive) = $event)),
                              label: "添加偏好标签",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              maxlength: "20",
                              onKeyup: _cache[7] || (_cache[7] = _withKeys($event => (addProfileTag('positive')), ["enter"]))
                            }, null, 8, ["modelValue"]),
                            _createVNode(_component_VBtn, {
                              color: "primary",
                              variant: "tonal",
                              size: "small",
                              loading: _unref(state).loading.action === 'profile/tags',
                              onClick: _cache[8] || (_cache[8] = $event => (addProfileTag('positive')))
                            }, {
                              default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                                _createTextVNode("添加", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading"])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_33, [
                          _createElementVNode("div", _hoisted_34, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-shield-alert-outline",
                              size: "18"
                            }),
                            _cache[24] || (_cache[24] = _createTextVNode("避雷标签", -1))
                          ]),
                          _createElementVNode("div", _hoisted_35, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(negativeTags.value, (tag) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: tag,
                                color: "error",
                                variant: "tonal",
                                size: "small",
                                closable: "",
                                "onClick:close": $event => (removeProfileTag('negative', tag))
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(tag), 1)
                                ]),
                                _: 2
                              }, 1032, ["onClick:close"]))
                            }), 128)),
                            (!negativeTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_36, "暂无避雷标签"))
                              : _createCommentVNode("", true)
                          ]),
                          _createElementVNode("div", _hoisted_37, [
                            _createVNode(_component_VTextField, {
                              modelValue: tagDrafts.negative,
                              "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((tagDrafts.negative) = $event)),
                              label: "添加避雷标签",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": "",
                              maxlength: "20",
                              onKeyup: _cache[10] || (_cache[10] = _withKeys($event => (addProfileTag('negative')), ["enter"]))
                            }, null, 8, ["modelValue"]),
                            _createVNode(_component_VBtn, {
                              color: "error",
                              variant: "tonal",
                              size: "small",
                              loading: _unref(state).loading.action === 'profile/tags',
                              onClick: _cache[11] || (_cache[11] = $event => (addProfileTag('negative')))
                            }, {
                              default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                                _createTextVNode("添加", -1)
                              ]))]),
                              _: 1
                            }, 8, ["loading"])
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_38, [
                          _createElementVNode("div", _hoisted_39, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-target-account",
                              size: "18"
                            }),
                            _cache[26] || (_cache[26] = _createTextVNode("本轮命中", -1))
                          ]),
                          _createElementVNode("div", _hoisted_40, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(boardMatchTags.value, (item) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: item.tag,
                                color: "info",
                                variant: "tonal",
                                size: "small"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.tag), 1),
                                  (item.count > 1)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_41, "×" + _toDisplayString(item.count), 1))
                                    : _createCommentVNode("", true)
                                ]),
                                _: 2
                              }, 1024))
                            }), 128)),
                            (!boardMatchTags.value.length)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_42, "暂无命中标签"))
                              : _createCommentVNode("", true)
                          ])
                        ])
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ], 512), [
              [_vShow, activeTab.value === 'profile']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_43, [
              _createElementVNode("div", _hoisted_44, [
                _cache[27] || (_cache[27] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "忽略归档"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "保留被忽略条目的原排名，可随时恢复推荐。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(archiveEntries.value.length) + " 部", 1)
                  ]),
                  _: 1
                })
              ]),
              (!archiveEntries.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-archive-outline",
                    title: "暂无忽略记录",
                    text: "榜单中点击忽略后，条目会出现在这里。"
                  }))
                : (_openBlock(), _createElementBlock("div", _hoisted_45, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveEntries.value, (entry) => {
                      return (_openBlock(), _createBlock(_component_VCard, {
                        key: entry.candidate_id,
                        variant: "outlined",
                        class: "ar-page__archive-card"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardItem, null, {
                            prepend: _withCtx(() => [
                              _createElementVNode("div", _hoisted_46, "#" + _toDisplayString(entry.original_rank), 1)
                            ]),
                            append: _withCtx(() => [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                color: "primary",
                                class: "mr-1",
                                "prepend-icon": "mdi-backup-restore",
                                onClick: $event => (runAction(() => _unref(state).restore(entry.candidate_id), '推荐已恢复'))
                              }, {
                                default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                                  _createTextVNode("恢复", -1)
                                ]))]),
                                _: 1
                              }, 8, ["onClick"]),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                size: "small",
                                variant: "text",
                                color: "error",
                                "aria-label": `删除归档 ${entry.candidate_id}`,
                                onClick: $event => (runAction(() => _unref(state).deleteArchive(entry.candidate_id), '归档记录已删除'))
                              }, null, 8, ["aria-label", "onClick"])
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_VCardTitle, { class: "text-subtitle-2 font-weight-bold" }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(entry.recommendation?.title || entry.candidate_id), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardSubtitle, null, {
                                default: _withCtx(() => [
                                  _createTextVNode("忽略于 " + _toDisplayString(formatTime(entry.archived_at)), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024),
                          (entry.recommendation?.summary)
                            ? (_openBlock(), _createBlock(_component_VCardText, {
                                key: 0,
                                class: "ar-page__archive-summary"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(entry.recommendation.summary), 1)
                                ]),
                                _: 2
                              }, 1024))
                            : _createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]))
            ], 512), [
              [_vShow, activeTab.value === 'archive']
            ]),
            _withDirectives(_createElementVNode("section", _hoisted_47, [
              _createElementVNode("div", _hoisted_48, [
                _cache[29] || (_cache[29] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "ar-page__section-title" }, "运行历史"),
                  _createElementVNode("div", { class: "ar-page__section-desc" }, "按结果、耗时、阶段和候选统计查看每次运行。")
                ], -1)),
                _createVNode(_component_VChip, {
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(_unref(state).historyMeta.value.total || 0) + " 次", 1)
                  ]),
                  _: 1
                })
              ]),
              (!_unref(state).history.value.length)
                ? (_openBlock(), _createBlock(_component_VEmptyState, {
                    key: 0,
                    icon: "mdi-history",
                    title: "暂无运行记录",
                    text: "榜单生成后，这里会记录每次执行结果。"
                  }))
                : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                    _createElementVNode("div", _hoisted_49, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(state).history.value, (run) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: historyKey(run),
                          class: "ar-page__history-item"
                        }, [
                          _createElementVNode("div", _hoisted_50, [
                            _createElementVNode("div", _hoisted_51, [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-clock-outline",
                                size: "17",
                                color: "primary"
                              }),
                              _createElementVNode("strong", null, _toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                              (run.metrics?.elapsed_ms)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_52, "耗时 " + _toDisplayString(formatDuration(run.metrics.elapsed_ms)), 1))
                                : _createCommentVNode("", true)
                            ]),
                            _createVNode(_component_VChip, {
                              size: "small",
                              color: statusMetaFor(run.status).color,
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(statusMetaFor(run.status).text), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"])
                          ]),
                          _createElementVNode("div", _hoisted_53, [
                            _cache[30] || (_cache[30] = _createElementVNode("span", { class: "ar-page__history-message-label" }, "结果：", -1)),
                            _createTextVNode(_toDisplayString(translateHistoryError(run.message || '本轮运行已记录')), 1)
                          ]),
                          _createElementVNode("div", _hoisted_54, [
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.candidate_count ?? 0), 1),
                              _cache[31] || (_cache[31] = _createElementVNode("span", null, "候选条目", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.final_count ?? 0), 1),
                              _cache[32] || (_cache[32] = _createElementVNode("span", null, "安全推荐", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.agent_calls ?? 0), 1),
                              _cache[33] || (_cache[33] = _createElementVNode("span", null, "模型调用", -1))
                            ]),
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(run.metrics?.subscription_success_count ?? 0), 1),
                              _cache[34] || (_cache[34] = _createElementVNode("span", null, "自动订阅", -1))
                            ])
                          ]),
                          (historyStages(run).length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_55, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyStages(run), (stage) => {
                                  return (_openBlock(), _createElementBlock("div", {
                                    key: stage.key,
                                    class: _normalizeClass(["ar-page__history-stage", { 'ar-page__history-stage--failed': stage.failed }])
                                  }, [
                                    _createVNode(_component_VIcon, {
                                      icon: stage.failed ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline',
                                      color: stage.failed ? 'error' : 'success',
                                      size: "17"
                                    }, null, 8, ["icon", "color"]),
                                    _createElementVNode("div", null, [
                                      _createElementVNode("strong", null, _toDisplayString(stage.title), 1),
                                      _createElementVNode("small", null, _toDisplayString(stage.status) + " · " + _toDisplayString(stage.duration), 1)
                                    ])
                                  ], 2))
                                }), 128))
                              ]))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", {
                            class: _normalizeClass(["ar-page__history-error", { 'ar-page__history-error--ok': !run.errors?.length && run.status === 'success' }])
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: run.errors?.length ? 'mdi-alert-outline' : 'mdi-information-outline',
                              size: "16"
                            }, null, 8, ["icon"]),
                            _createElementVNode("span", null, _toDisplayString(historyErrorText(run)), 1)
                          ], 2),
                          _createElementVNode("div", _hoisted_56, [
                            _createElementVNode("span", null, "来源：" + _toDisplayString(historySourceText(run)), 1),
                            _createVNode(_component_VBtn, {
                              size: "x-small",
                              variant: "text",
                              "append-icon": isHistoryExpanded(run) ? 'mdi-chevron-up' : 'mdi-chevron-down',
                              onClick: $event => (toggleHistory(run))
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(isHistoryExpanded(run) ? '收起细节' : '查看细节'), 1)
                              ]),
                              _: 2
                            }, 1032, ["append-icon", "onClick"])
                          ]),
                          (isHistoryExpanded(run))
                            ? (_openBlock(), _createElementBlock("div", _hoisted_57, [
                                _createElementVNode("div", null, [
                                  _cache[35] || (_cache[35] = _createElementVNode("span", null, "运行编号", -1)),
                                  _createElementVNode("code", null, _toDisplayString(run.run_id || '—'), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[36] || (_cache[36] = _createElementVNode("span", null, "画像调用", -1)),
                                  _createElementVNode("span", null, _toDisplayString(run.metrics?.profile_agent_calls ?? 0) + " 次；排序 " + _toDisplayString(run.metrics?.ranking_agent_calls ?? 0) + " 次", 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[37] || (_cache[37] = _createElementVNode("span", null, "播放快照", -1)),
                                  _createElementVNode("span", null, _toDisplayString(run.metrics?.playback_count ?? 0) + " 条，" + _toDisplayString(historyPlaybackStatus(run.metrics?.playback_status)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[38] || (_cache[38] = _createElementVNode("span", null, "候选排除", -1)),
                                  _createElementVNode("span", null, _toDisplayString(historyExclusionText(run)), 1)
                                ])
                              ]))
                            : _createCommentVNode("", true)
                        ]))
                      }), 128))
                    ]),
                    _createVNode(_component_VPagination, {
                      modelValue: historyPage.value,
                      "onUpdate:modelValue": [
                        _cache[12] || (_cache[12] = $event => ((historyPage).value = $event)),
                        changeHistoryPage
                      ],
                      length: historyPages.value,
                      density: "compact",
                      "total-visible": "7",
                      class: "mt-3"
                    }, null, 8, ["modelValue", "length"])
                  ], 64)),
              _createElementVNode("span", { class: "d-none" }, "page_size=" + _toDisplayString(historyPageSize))
            ], 512), [
              [_vShow, activeTab.value === 'history']
            ])
          ], 64))
    ]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((snackbar.value.show) = $event)),
      color: snackbar.value.color
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-827eba3e"]]);

export { Page as default };
