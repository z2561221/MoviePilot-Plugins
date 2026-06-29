import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-CWxZXtbF.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,normalizeStyle:_normalizeStyle,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = {
  key: 2,
  class: "dc-section dc-section--archive"
};
const _hoisted_2 = { class: "dc-section-title mb-2" };
const _hoisted_3 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_4 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_5 = { class: "dc-history-info" };
const _hoisted_6 = { class: "dc-history-title" };
const _hoisted_7 = { class: "dc-history-meta" };
const _hoisted_8 = { class: "text-caption text-medium-emphasis" };
const _hoisted_9 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_10 = {
  key: 0,
  class: "dc-section"
};
const _hoisted_11 = { class: "dc-stats-grid" };
const _hoisted_12 = { class: "dc-stat-card" };
const _hoisted_13 = { class: "dc-stat-value" };
const _hoisted_14 = { class: "dc-stat-card" };
const _hoisted_15 = { class: "dc-stat-value" };
const _hoisted_16 = { class: "dc-stat-label" };
const _hoisted_17 = {
  key: 1,
  class: "dc-section"
};
const _hoisted_18 = { class: "dc-rank-grid" };
const _hoisted_19 = { class: "dc-rank-head" };
const _hoisted_20 = ["onClick"];
const _hoisted_21 = { class: "dc-rank-title" };
const _hoisted_22 = {
  key: 0,
  class: "dc-rank-wish"
};
const _hoisted_23 = {
  key: 1,
  class: "dc-rank-empty"
};
const _hoisted_24 = { class: "dc-section" };
const _hoisted_25 = { class: "dc-section-title mb-2 dc-title-with-chips" };
const _hoisted_26 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_27 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_28 = { class: "dc-history-info" };
const _hoisted_29 = { class: "dc-history-title" };
const _hoisted_30 = { class: "dc-history-meta" };
const _hoisted_31 = { class: "text-caption text-medium-emphasis" };
const _hoisted_32 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_33 = { class: "dc-section" };
const _hoisted_34 = { class: "dc-section-title mb-2" };
const _hoisted_35 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_36 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_37 = ["onClick"];
const _hoisted_38 = { class: "dc-history-info" };
const _hoisted_39 = { class: "dc-history-title" };
const _hoisted_40 = { class: "dc-history-meta" };
const _hoisted_41 = { class: "text-caption text-medium-emphasis" };
const _hoisted_42 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_43 = { class: "dc-section" };
const _hoisted_44 = { class: "dc-section-title mb-2" };
const _hoisted_45 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_46 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_47 = { class: "dc-history-info" };
const _hoisted_48 = { class: "dc-history-title" };
const _hoisted_49 = { class: "dc-history-meta" };
const _hoisted_50 = { class: "text-caption text-medium-emphasis" };
const _hoisted_51 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_52 = {
  key: 2,
  class: "d-flex justify-center mt-2"
};
const _hoisted_53 = { class: "d-flex align-center mx-2 text-caption text-medium-emphasis" };
const _hoisted_54 = { class: "dc-section" };
const _hoisted_55 = { class: "dc-section-title mb-2" };
const _hoisted_56 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_57 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_58 = { class: "dc-history-info" };
const _hoisted_59 = { class: "dc-history-title" };
const _hoisted_60 = { class: "dc-history-meta" };
const _hoisted_61 = { class: "text-caption text-medium-emphasis" };
const _hoisted_62 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_63 = { class: "dc-dialog-poster" };
const _hoisted_64 = { class: "dc-dialog-info" };
const _hoisted_65 = { class: "dc-dialog-title" };
const _hoisted_66 = { class: "dc-dialog-meta" };

const {ref,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const loading = ref(false);
const stats = ref(null);
const historyData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
const archiveData = ref({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
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
const dialogItem = ref(null);
const showDialog = ref(false);

const rankColors = {
  coming: 'primary',
  tv_real_time: 'teal',
  tv_chinese: 'orange-darken-1',
  tv_global: 'deep-purple',
  movie_weekly: 'pink',
  bangumi: 'brown',
  unknown: 'grey',
};
const rankNames = {
  coming: '即将上映',
  tv_real_time: '实时热门',
  tv_chinese: '华语口碑',
  tv_global: '全球口碑',
  movie_weekly: '电影口碑',
  bangumi: 'BangumiTV',
  unknown: '未归类',
};

function queryString(params) {
  return Object.entries(params || {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}

function normalizeApiData(value) {
  if (value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, 'success')) return value
  return value?.data && !Array.isArray(value?.data) ? value.data : value
}

function rowKey(prefix, item, index) {
  return `${prefix}:${item?.id || item?.unique || item?.time || item?.tmdbid || item?.title || index}`
}

function mediaIdOf(media) {
  if (media?.tmdb_id) return `tmdb:${media.tmdb_id}`
  if (media?.douban_id) return `douban:${media.douban_id}`
  if (media?.bangumi_id) return `bangumi:${media.bangumi_id}`
  if (media?.media_id && media?.mediaid_prefix) return `${media.mediaid_prefix}:${media.media_id}`
  return ''
}

function bangumiIdOf(rk, item) {
  if (item?.bangumi_id || item?.bangumiid) return item.bangumi_id || item.bangumiid
  if (rk === 'bangumi' && item?.douban_id) return item.douban_id
  const match = String(item?.link || '').match(/(?:bgm\.tv|bangumi\.tv)\/subject\/(\d+)/);
  return match ? match[1] : ''
}

function mediaTypeOf(rk, item) {
  const type = item?.media_type || item?.mtype || item?.type || '';
  if (type === '电影' || type === 'movie') return 'movie'
  if (type === '电视剧' || type === 'tv') return 'tv'
  return rk === 'movie_weekly' ? 'movie' : 'tv'
}

async function resolveRankMedia(rk, item) {
  const mediaType = mediaTypeOf(rk, item);
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  });
  const res = normalizeApiData(await getPluginApi(props.api, `resolve_media?${params}`));
  if (res?.success === false) throw new Error(res?.message || '媒体识别失败')
  const media = res?.data && !Array.isArray(res.data) ? res.data : res;
  if (!media || typeof media !== 'object') throw new Error('媒体识别失败')
  const merged = { ...item, ...media };
  merged.title = media.title || media.name || item?.title || item?.name || '';
  merged.name = media.name || media.title || item?.name || item?.title || '';
  merged.year = media.year || item?.year || '';
  merged.type = media.type || (mediaType === 'movie' ? '电影' : '电视剧');
  merged.tmdb_id = media.tmdb_id || media.tmdbid || item?.tmdb_id || item?.tmdbid || null;
  merged.tmdbid = media.tmdbid || media.tmdb_id || item?.tmdbid || item?.tmdb_id || null;
  merged.douban_id = media.douban_id || media.doubanid || item?.douban_id || item?.doubanid || null;
  merged.doubanid = media.doubanid || media.douban_id || item?.doubanid || item?.douban_id || null;
  merged.bangumi_id = media.bangumi_id || media.bangumiid || bangumiIdOf(rk, item) || null;
  merged.bangumiid = media.bangumiid || media.bangumi_id || bangumiIdOf(rk, item) || null;
  if (!merged.mediaid_prefix || !merged.media_id) {
    const mediaId = mediaIdOf(merged);
    if (mediaId) {
      const [prefix, id] = mediaId.split(':');
      merged.mediaid_prefix = merged.mediaid_prefix || prefix;
      merged.media_id = merged.media_id || id;
    }
  }
  return merged
}

async function loadAll() {
  loading.value = true;
  try {
    const [s, h, c, p, r, cfg, a] = await Promise.all([
      getPluginApi(props.api, 'stats'),
      getPluginApi(props.api, `subscribe_history?page=${historyData.value.page}&page_size=${historyData.value.page_size}`),
      getPluginApi(props.api, 'anti_cheat_logs'),
      getPluginApi(props.api, 'pending_observations'),
      getPluginApi(props.api, 'rank_history'),
      getPluginApi(props.api, 'config'),
      getPluginApi(props.api, `archive_records?page=${archiveData.value.page}&page_size=${archiveData.value.page_size}`),
    ]);
    if (s) stats.value = s;
    if (h) historyData.value = h;
    if (c) {
      const logs = Array.isArray(c) ? c : [];
      cheatLogs.value = logs.filter(log => !log || log.reason !== '黑名单关键词').slice(-5);
      blacklistEntries.value = logs.filter(log => log && log.reason === '黑名单关键词').slice().reverse().slice(0, 5);
    }
    if (p) pendingObservations.value = p;
    if (r) rankHistory.value = r;
    if (cfg) {
      configData.value = cfg;
      blacklistKeywords.value = String(cfg.blacklist_keywords || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
    }
    if (a) archiveData.value = a;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function goPage(p) {
  if (p < 1 || p > historyData.value.total_pages) return
  historyData.value.page = p;
  await loadAll();
}

async function loadArchive() {
  const data = await getPluginApi(props.api, `archive_records?page=${archiveData.value.page}&page_size=${archiveData.value.page_size}`);
  if (data) archiveData.value = data;
}

async function openArchivePage() {
  archivePage.value = true;
  await loadArchive();
}

function closeArchivePage() {
  archivePage.value = false;
}

async function runDelete(path, body, key, successText) {
  if (actionKey.value) return
  actionKey.value = key;
  actionMessage.value = '';
  actionOk.value = true;
  try {
    const qs = queryString(body);
    const res = await postPluginApi(props.api, qs ? `${path}?${qs}` : path, {});
    actionOk.value = !!(res && res.success);
    actionMessage.value = (res && res.message) || (actionOk.value ? successText : '操作失败');
    await loadAll();
  } catch (e) {
    actionOk.value = false;
    actionMessage.value = e?.message || '操作失败';
  } finally {
    actionKey.value = '';
  }
}

async function deleteObservation(item, index) {
  await runDelete('delete_observation', { unique: item?.unique || '', rank_key: item?.rank_key || '', title: item?.title || '' }, rowKey('obs', item, index), '已删除观察条目');
}

async function deleteSubscribeHistory(item, index) {
  await runDelete('delete_subscribe_history', { time: item?.time || '', title: item?.title || '', tmdbid: item?.tmdbid || '' }, rowKey('sub', item, index), '已删除订阅历史');
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

function showActionDialog(rk, item) {
  dialogItem.value = { rk, item };
  showDialog.value = true;
}

function dialogPoster() {
  const item = dialogItem.value?.item || {};
  return item.poster || item.poster_path || item.cover || ''
}

async function subscribeViaNativeDialog(rk, item) {
  const media = await resolveRankMedia(rk, item);
  await props.nativeSubscribe(media);
  actionOk.value = true;
  actionMessage.value = '已打开 MP 原生订阅窗口';
}

async function subscribeRankItem(rk, item) {
  const mediaType = mediaTypeOf(rk, item);
  const params = queryString({
    tmdb_id: item?.tmdbid || item?.tmdb_id || '',
    bangumi_id: bangumiIdOf(rk, item),
    media_type: mediaType,
    title: item?.title || item?.name || '',
    year: item?.year || '',
  });
  const res = await postPluginApi(props.api, `subscribe?${params}`, {});
  if (!res?.success) throw new Error(res?.message || '订阅失败')
  actionOk.value = true;
  actionMessage.value = res?.message || `${item.title || ''} 已添加订阅`;
  await loadAll();
}

async function doSubscribe() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  showDialog.value = false;
  actionMessage.value = '';
  actionOk.value = true;
  try {
    if (props.nativeSubscribe) await subscribeViaNativeDialog(rk, item);
    else await subscribeRankItem(rk, item);
  } catch (e) {
    actionOk.value = false;
    actionMessage.value = `订阅失败: ${e?.message || e}`;
  }
}

function doOpenSource() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  showDialog.value = false;
  const link = item?.link || '';
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) {
    if (link) window.open(link, '_blank');
    return
  }
  const subjectId = item?.douban_id || item?.doubanid || '';
  if (subjectId) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${subjectId}?from=mdouban&open=app`, '_blank');
    return
  }
  const match = link.match(/subject\/(\d+)/);
  if (match && (link.includes('douban.com') || link.includes('doubanapp'))) {
    window.open(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${match[1]}?from=mdouban&open=app`, '_blank');
    return
  }
  if (link) window.open(link, '_blank');
}

function sourceButtonColor() {
  if (!dialogItem.value) return 'primary'
  const { rk, item } = dialogItem.value;
  const link = String(item?.link || '');
  if (rk === 'bangumi' || link.includes('bgm.tv') || link.includes('bangumi.tv')) return '#F838A0'
  if (link.includes('douban') || item?.douban_id || item?.doubanid) return '#08B810'
  return 'primary'
}

function doOpenTmdb() {
  if (!dialogItem.value) return
  const { rk, item } = dialogItem.value;
  const tmdbId = item?.tmdbid || item?.tmdb_id || '';
  if (!tmdbId) return
  const mediaType = mediaTypeOf(rk, item);
  const url = mediaType === 'movie' ? `https://www.themoviedb.org/movie/${tmdbId}` : `https://www.themoviedb.org/tv/${tmdbId}`;
  showDialog.value = false;
  window.open(url, '_blank');
}

onMounted(loadAll);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "dc-page"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, { class: "dc-page-header" }, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-book-open-page-variant-outline" })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-refresh",
            class: "text-none me-1",
            loading: loading.value,
            onClick: _cache[0] || (_cache[0] = $event => (archivePage.value ? loadArchive() : loadAll()))
          }, {
            default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": archivePage.value ? 'mdi-arrow-left' : 'mdi-archive-outline',
            class: "text-none me-1",
            color: archivePage.value ? 'primary' : undefined,
            onClick: _cache[1] || (_cache[1] = $event => (archivePage.value ? closeArchivePage() : openArchivePage()))
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(archivePage.value ? '返回' : '归档'), 1)
            ]),
            _: 1
          }, 8, ["prepend-icon", "color"]),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            class: "text-none me-1",
            onClick: _cache[2] || (_cache[2] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
              _createTextVNode("设置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            icon: "mdi-close",
            variant: "text",
            size: "small",
            onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
          })
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, null, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(archivePage.value ? '豆瓣中心 · 归档记录' : '豆瓣中心 · 运行详情'), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, null, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(archivePage.value ? '删除进入归档，支持恢复或彻底删除' : '榜单刷新 -> 黑名筛选 -> 观察队列 -> 订阅记录'), 1)
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "pa-3 dc-flow" }, {
        default: _withCtx(() => [
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                key: 0,
                indeterminate: "",
                color: "primary",
                class: "d-block mx-auto my-6"
              }))
            : _createCommentVNode("", true),
          (actionMessage.value)
            ? (_openBlock(), _createElementBlock("div", {
                key: 1,
                class: _normalizeClass(["dc-action-message", actionOk.value ? 'text-success' : 'text-error'])
              }, _toDisplayString(actionMessage.value), 3))
            : _createCommentVNode("", true),
          (!loading.value && archivePage.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                _createElementVNode("div", _hoisted_2, [
                  _cache[9] || (_cache[9] = _createTextVNode("归档记录 ", -1)),
                  _createElementVNode("span", _hoisted_3, "（共 " + _toDisplayString(archiveData.value.total || 0) + " 条）", 1)
                ]),
                (archiveData.value.items && archiveData.value.items.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveData.value.items, (item, i) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.id || i,
                          class: "dc-history-row dc-status-row"
                        }, [
                          _createVNode(_component_VAvatar, {
                            size: "28",
                            class: "mr-2 flex-shrink-0",
                            color: "primary",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-archive-outline",
                                size: "14"
                              })
                            ]),
                            _: 1
                          }),
                          _createElementVNode("div", _hoisted_5, [
                            _createElementVNode("div", _hoisted_6, _toDisplayString(item.title || '未命名条目'), 1),
                            _createElementVNode("div", _hoisted_7, [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: "primary",
                                variant: "tonal",
                                class: "mr-1"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.source_name || item.source || '归档'), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createElementVNode("span", _hoisted_8, _toDisplayString(item.archived_at ? item.archived_at.split(' ')[0] : ''), 1)
                            ])
                          ]),
                          _createVNode(_component_VBtn, {
                            icon: "mdi-restore",
                            variant: "text",
                            size: "x-small",
                            color: "primary",
                            class: "dc-row-action",
                            loading: actionKey.value === rowKey('archive-restore', item, i),
                            onClick: $event => (restoreArchive(item, i))
                          }, null, 8, ["loading", "onClick"]),
                          _createVNode(_component_VBtn, {
                            icon: "mdi-delete-outline",
                            variant: "text",
                            size: "x-small",
                            color: "error",
                            class: "dc-row-action",
                            loading: actionKey.value === rowKey('archive-delete', item, i),
                            onClick: $event => (deleteArchive(item, i))
                          }, null, 8, ["loading", "onClick"])
                        ]))
                      }), 128))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_9, "暂无归档记录"))
              ]))
            : (!loading.value)
              ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                  (stats.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_10, [
                        _cache[12] || (_cache[12] = _createElementVNode("div", { class: "dc-section-title mb-2" }, "订阅统计", -1)),
                        _createElementVNode("div", _hoisted_11, [
                          _createElementVNode("div", _hoisted_12, [
                            _createElementVNode("div", _hoisted_13, _toDisplayString(stats.value.total || 0), 1),
                            _cache[10] || (_cache[10] = _createElementVNode("div", { class: "dc-stat-label" }, "总订阅数", -1))
                          ]),
                          _createElementVNode("div", _hoisted_14, [
                            _createElementVNode("div", _hoisted_15, _toDisplayString(stats.value.month_new || 0), 1),
                            _cache[11] || (_cache[11] = _createElementVNode("div", { class: "dc-stat-label" }, "本月新增", -1))
                          ]),
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(stats.value.rank_dist, (count, key) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: key,
                              class: "dc-stat-card"
                            }, [
                              _createElementVNode("div", {
                                class: "dc-stat-value",
                                style: _normalizeStyle({ color: `rgb(var(--v-theme-${rankColors[key] || 'primary'}))` })
                              }, _toDisplayString(count), 5),
                              _createElementVNode("div", _hoisted_16, _toDisplayString(rankNames[key] || key), 1)
                            ]))
                          }), 128))
                        ])
                      ]))
                    : _createCommentVNode("", true),
                  (rankHistory.value && Object.keys(rankHistory.value).length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                        _cache[13] || (_cache[13] = _createElementVNode("div", { class: "dc-section-title mb-2" }, [
                          _createTextVNode("榜单快照 "),
                          _createElementVNode("span", { class: "text-caption font-weight-regular text-medium-emphasis" }, "（点击条目订阅或打开来源）")
                        ], -1)),
                        _createElementVNode("div", _hoisted_18, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(Object.entries(rankHistory.value), ([key, items]) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: key,
                              class: "dc-rank-card"
                            }, [
                              _createElementVNode("div", _hoisted_19, [
                                _createVNode(_component_VIcon, {
                                  icon: "mdi-format-list-numbered",
                                  size: "15",
                                  color: rankColors[key] || 'primary',
                                  class: "mr-1"
                                }, null, 8, ["color"]),
                                _createElementVNode("span", null, _toDisplayString(rankNames[key] || key), 1)
                              ]),
                              (items && items.length)
                                ? (_openBlock(true), _createElementBlock(_Fragment, { key: 0 }, _renderList(items.slice(0, 5), (item, i) => {
                                    return (_openBlock(), _createElementBlock("div", {
                                      key: `${key}-${i}`,
                                      class: "dc-rank-row",
                                      title: "订阅 / 打开详情",
                                      onClick: $event => (showActionDialog(key, item))
                                    }, [
                                      _createVNode(_component_VAvatar, {
                                        size: "20",
                                        rounded: "sm",
                                        class: "dc-rank-poster"
                                      }, {
                                        default: _withCtx(() => [
                                          (item.poster)
                                            ? (_openBlock(), _createBlock(_component_VImg, {
                                                key: 0,
                                                src: item.poster,
                                                cover: ""
                                              }, null, 8, ["src"]))
                                            : (_openBlock(), _createBlock(_component_VIcon, {
                                                key: 1,
                                                icon: "mdi-filmstrip",
                                                size: "13"
                                              }))
                                        ]),
                                        _: 2
                                      }, 1024),
                                      _createElementVNode("span", _hoisted_21, _toDisplayString(item.title || ''), 1),
                                      (key === 'coming' && item.wish_count)
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_22, _toDisplayString(item.wish_count), 1))
                                        : _createCommentVNode("", true)
                                    ], 8, _hoisted_20))
                                  }), 128))
                                : (_openBlock(), _createElementBlock("div", _hoisted_23, "暂无榜单数据"))
                            ]))
                          }), 128))
                        ])
                      ]))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_24, [
                    _createElementVNode("div", _hoisted_25, [
                      _cache[14] || (_cache[14] = _createTextVNode(" 黑名拦截 ", -1)),
                      _createElementVNode("span", _hoisted_26, "（关键词 " + _toDisplayString(blacklistKeywords.value.length) + " 个，最近命中 " + _toDisplayString(blacklistEntries.value.length) + " 条）", 1),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(blacklistKeywords.value, (word, i) => {
                        return (_openBlock(), _createBlock(_component_VChip, {
                          key: `${word}-${i}`,
                          size: "x-small",
                          color: "error",
                          variant: "tonal",
                          class: "dc-blacklist-chip"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(word), 1)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                    ]),
                    (blacklistEntries.value && blacklistEntries.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(blacklistEntries.value, (item, i) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: i,
                              class: "dc-history-row dc-status-row"
                            }, [
                              _createVNode(_component_VAvatar, {
                                size: "28",
                                class: "mr-2 flex-shrink-0",
                                color: "error",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-block-helper",
                                    size: "14"
                                  })
                                ]),
                                _: 1
                              }),
                              _createElementVNode("div", _hoisted_28, [
                                _createElementVNode("div", _hoisted_29, _toDisplayString(item.title || '未命名条目'), 1),
                                _createElementVNode("div", _hoisted_30, [
                                  _createElementVNode("span", _hoisted_31, _toDisplayString(item.time || ''), 1)
                                ])
                              ]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: "error",
                                variant: "tonal",
                                class: "dc-row-status"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.detail || item.reason || '黑名单关键词'), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                variant: "text",
                                size: "x-small",
                                color: "error",
                                class: "dc-row-action",
                                loading: actionKey.value === rowKey('log', item, i),
                                onClick: $event => (deleteAntiCheatLog(item, i))
                              }, null, 8, ["loading", "onClick"])
                            ]))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_32, "暂无被黑名单筛选的条目"))
                  ]),
                  _createElementVNode("div", _hoisted_33, [
                    _createElementVNode("div", _hoisted_34, [
                      _cache[15] || (_cache[15] = _createTextVNode("观察队列 ", -1)),
                      _createElementVNode("span", _hoisted_35, "（待自动订阅 " + _toDisplayString(pendingObservations.value.length) + " 条）", 1)
                    ]),
                    (pendingObservations.value && pendingObservations.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_36, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pendingObservations.value, (item, i) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: i,
                              class: "dc-history-row dc-status-row dc-history-row--clickable",
                              onClick: $event => (showActionDialog(item.rank_key, item))
                            }, [
                              _createVNode(_component_VAvatar, {
                                size: "28",
                                class: "mr-2 flex-shrink-0",
                                color: "warning",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-clock-outline",
                                    size: "14"
                                  })
                                ]),
                                _: 1
                              }),
                              _createElementVNode("div", _hoisted_38, [
                                _createElementVNode("div", _hoisted_39, _toDisplayString(item.title), 1),
                                _createElementVNode("div", _hoisted_40, [
                                  _createVNode(_component_VChip, {
                                    size: "x-small",
                                    color: rankColors[item.rank_key] || 'primary',
                                    variant: "tonal",
                                    class: "mr-1"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(item.rank_name), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["color"]),
                                  _createElementVNode("span", _hoisted_41, "观察 " + _toDisplayString(item.elapsed_days || 0) + " / " + _toDisplayString(item.observe_days || 0) + " 天", 1)
                                ])
                              ]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: "warning",
                                variant: "tonal",
                                class: "dc-row-status"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode("剩余 " + _toDisplayString(item.remaining_days || 0) + " 天", 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                variant: "text",
                                size: "x-small",
                                color: "error",
                                class: "dc-row-action",
                                loading: actionKey.value === rowKey('obs', item, i),
                                onClick: _withModifiers($event => (deleteObservation(item, i)), ["stop"])
                              }, null, 8, ["loading", "onClick"])
                            ], 8, _hoisted_37))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_42, "暂无观察期条目"))
                  ]),
                  _createElementVNode("div", _hoisted_43, [
                    _createElementVNode("div", _hoisted_44, [
                      _cache[16] || (_cache[16] = _createTextVNode("订阅历史 ", -1)),
                      _createElementVNode("span", _hoisted_45, "（共 " + _toDisplayString(historyData.value.total) + " 条）", 1)
                    ]),
                    (historyData.value.items && historyData.value.items.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_46, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyData.value.items, (item, i) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: i,
                              class: "dc-history-row dc-status-row"
                            }, [
                              _createVNode(_component_VAvatar, {
                                size: "28",
                                class: "mr-2 flex-shrink-0"
                              }, {
                                default: _withCtx(() => [
                                  (item.poster)
                                    ? (_openBlock(), _createBlock(_component_VImg, {
                                        key: 0,
                                        src: item.poster
                                      }, null, 8, ["src"]))
                                    : (_openBlock(), _createBlock(_component_VIcon, {
                                        key: 1,
                                        icon: "mdi-filmstrip",
                                        size: "14"
                                      }))
                                ]),
                                _: 2
                              }, 1024),
                              _createElementVNode("div", _hoisted_47, [
                                _createElementVNode("div", _hoisted_48, _toDisplayString(item.title), 1),
                                _createElementVNode("div", _hoisted_49, [
                                  _createVNode(_component_VChip, {
                                    size: "x-small",
                                    color: rankColors[item.rank_key] || 'primary',
                                    variant: "tonal",
                                    class: "mr-1"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(item.rank_name), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["color"]),
                                  _createElementVNode("span", _hoisted_50, _toDisplayString(item.time ? item.time.split(' ')[0] : ''), 1)
                                ])
                              ]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: item.status === 'failed' ? 'error' : 'success',
                                variant: "tonal",
                                class: "dc-row-status"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.status === 'failed' ? '订阅失败' : '订阅成功'), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"]),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                variant: "text",
                                size: "x-small",
                                color: "error",
                                class: "dc-row-action",
                                loading: actionKey.value === rowKey('sub', item, i),
                                onClick: $event => (deleteSubscribeHistory(item, i))
                              }, null, 8, ["loading", "onClick"])
                            ]))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_51, "暂无订阅记录")),
                    (historyData.value.total_pages > 1)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_52, [
                          _createVNode(_component_VBtn, {
                            variant: "text",
                            size: "x-small",
                            disabled: historyData.value.page <= 1,
                            class: "mx-1",
                            onClick: _cache[4] || (_cache[4] = $event => (goPage(historyData.value.page - 1)))
                          }, {
                            default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                              _createTextVNode("上一页", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled"]),
                          _createElementVNode("span", _hoisted_53, _toDisplayString(historyData.value.page) + " / " + _toDisplayString(historyData.value.total_pages), 1),
                          _createVNode(_component_VBtn, {
                            variant: "text",
                            size: "x-small",
                            disabled: historyData.value.page >= historyData.value.total_pages,
                            class: "mx-1",
                            onClick: _cache[5] || (_cache[5] = $event => (goPage(historyData.value.page + 1)))
                          }, {
                            default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                              _createTextVNode("下一页", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled"])
                        ]))
                      : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("div", _hoisted_54, [
                    _createElementVNode("div", _hoisted_55, [
                      _cache[19] || (_cache[19] = _createTextVNode("观察日志 ", -1)),
                      _createElementVNode("span", _hoisted_56, "（最近 " + _toDisplayString(cheatLogs.value.length) + " 条）", 1)
                    ]),
                    (cheatLogs.value && cheatLogs.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_57, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cheatLogs.value.slice().reverse(), (log, i) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: i,
                              class: "dc-history-row dc-status-row"
                            }, [
                              _createVNode(_component_VAvatar, {
                                size: "28",
                                class: "mr-2 flex-shrink-0"
                              }, {
                                default: _withCtx(() => [
                                  (log.poster)
                                    ? (_openBlock(), _createBlock(_component_VImg, {
                                        key: 0,
                                        src: log.poster
                                      }, null, 8, ["src"]))
                                    : (_openBlock(), _createBlock(_component_VIcon, {
                                        key: 1,
                                        icon: "mdi-filmstrip",
                                        size: "14"
                                      }))
                                ]),
                                _: 2
                              }, 1024),
                              _createElementVNode("div", _hoisted_58, [
                                _createElementVNode("div", _hoisted_59, _toDisplayString(log.title), 1),
                                _createElementVNode("div", _hoisted_60, [
                                  _createVNode(_component_VChip, {
                                    size: "x-small",
                                    color: rankColors[log.rank_key] || 'primary',
                                    variant: "tonal",
                                    class: "mr-1"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(log.rank_name || log.rank_key || '观察日志'), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["color"]),
                                  _createElementVNode("span", _hoisted_61, _toDisplayString(log.time ? log.time.split(' ')[0] : ''), 1)
                                ])
                              ]),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: "warning",
                                variant: "tonal",
                                class: "dc-row-status"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(log.reason || '观察日志'), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VBtn, {
                                icon: "mdi-delete-outline",
                                variant: "text",
                                size: "x-small",
                                color: "error",
                                class: "dc-row-action",
                                loading: actionKey.value === rowKey('log', log, i),
                                onClick: $event => (deleteAntiCheatLog(log, i))
                              }, null, 8, ["loading", "onClick"])
                            ]))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_62, "暂无观察日志"))
                  ])
                ], 64))
              : _createCommentVNode("", true)
        ]),
        _: 1
      }),
      _createVNode(_component_VDialog, {
        modelValue: showDialog.value,
        "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((showDialog).value = $event)),
        "max-width": "420"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCard, { class: "dc-action-dialog" }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, { class: "dc-dialog-body" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_63, [
                    (dialogPoster())
                      ? (_openBlock(), _createBlock(_component_VImg, {
                          key: 0,
                          src: dialogPoster(),
                          cover: ""
                        }, null, 8, ["src"]))
                      : (_openBlock(), _createBlock(_component_VIcon, {
                          key: 1,
                          icon: "mdi-filmstrip",
                          size: "26"
                        }))
                  ]),
                  _createElementVNode("div", _hoisted_64, [
                    _createElementVNode("div", _hoisted_65, _toDisplayString(dialogItem.value?.item?.title || '选择操作'), 1),
                    _createElementVNode("div", _hoisted_66, _toDisplayString(dialogItem.value?.item?.year || rankNames[dialogItem.value?.rk] || ''), 1)
                  ])
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              _createVNode(_component_VCardActions, { class: "dc-dialog-actions" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VBtn, {
                    color: sourceButtonColor(),
                    variant: "text",
                    "prepend-icon": "mdi-open-in-new",
                    onClick: doOpenSource
                  }, {
                    default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                      _createTextVNode("豆瓣", -1)
                    ]))]),
                    _: 1
                  }, 8, ["color"]),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "text",
                    "prepend-icon": "mdi-database-search-outline",
                    disabled: !(dialogItem.value?.item?.tmdbid || dialogItem.value?.item?.tmdb_id),
                    onClick: doOpenTmdb
                  }, {
                    default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                      _createTextVNode("TMDB", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_VSpacer),
                  _createVNode(_component_VBtn, {
                    color: "success",
                    variant: "flat",
                    "prepend-icon": "mdi-plus-circle-outline",
                    onClick: doSubscribe
                  }, {
                    default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                      _createTextVNode("订阅", -1)
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
      }, 8, ["modelValue"])
    ]),
    _: 1
  }))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-23f9f425"]]);

export { Page as default };
