import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, t as toPosterThumbnail, a as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-Cd7yiqDA.js';
import { s as sourceDescriptor } from './source-Y0YpQdE1.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,normalizeClass:_normalizeClass,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeStyle:_normalizeStyle,unref:_unref,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "dc-page-heading" };
const _hoisted_2 = { class: "text-h6" };
const _hoisted_3 = { class: "text-caption text-medium-emphasis" };
const _hoisted_4 = { class: "dc-page-toolbar-actions" };
const _hoisted_5 = { class: "dc-toolbar-label" };
const _hoisted_6 = { class: "dc-load-alert__content" };
const _hoisted_7 = {
  key: 2,
  class: "dc-section dc-section--archive"
};
const _hoisted_8 = { class: "dc-section-title mb-2" };
const _hoisted_9 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_10 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_11 = { class: "dc-history-info" };
const _hoisted_12 = { class: "dc-history-title" };
const _hoisted_13 = { class: "dc-history-meta" };
const _hoisted_14 = { class: "text-caption text-medium-emphasis" };
const _hoisted_15 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_16 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_17 = {
  key: 0,
  class: "dc-section dc-section--stats"
};
const _hoisted_18 = { class: "dc-stats-grid" };
const _hoisted_19 = { class: "dc-stat-card" };
const _hoisted_20 = { class: "dc-stat-value" };
const _hoisted_21 = { class: "dc-stat-card" };
const _hoisted_22 = { class: "dc-stat-value" };
const _hoisted_23 = { class: "dc-stat-label" };
const _hoisted_24 = {
  key: 1,
  class: "dc-section dc-section--rank"
};
const _hoisted_25 = { class: "dc-rank-grid dc-rank-grid--snapshot" };
const _hoisted_26 = { class: "dc-rank-head" };
const _hoisted_27 = ["onClick"];
const _hoisted_28 = { class: "dc-rank-title" };
const _hoisted_29 = {
  key: 0,
  class: "dc-rank-wish"
};
const _hoisted_30 = {
  key: 1,
  class: "dc-rank-empty"
};
const _hoisted_31 = { class: "dc-section dc-section--blacklist" };
const _hoisted_32 = { class: "dc-section-title mb-2 dc-title-with-chips" };
const _hoisted_33 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_34 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_35 = { class: "dc-history-info" };
const _hoisted_36 = { class: "dc-history-title" };
const _hoisted_37 = { class: "dc-history-meta" };
const _hoisted_38 = { class: "text-caption text-medium-emphasis" };
const _hoisted_39 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_40 = { class: "dc-section dc-section--observe" };
const _hoisted_41 = { class: "dc-section-title mb-2" };
const _hoisted_42 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_43 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_44 = ["onClick"];
const _hoisted_45 = { class: "dc-history-info" };
const _hoisted_46 = { class: "dc-history-title" };
const _hoisted_47 = { class: "dc-history-meta" };
const _hoisted_48 = { class: "text-caption text-medium-emphasis" };
const _hoisted_49 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_50 = { class: "dc-section dc-section--history" };
const _hoisted_51 = { class: "dc-section-title mb-2" };
const _hoisted_52 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_53 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_54 = { class: "dc-history-info" };
const _hoisted_55 = { class: "dc-history-title" };
const _hoisted_56 = { class: "dc-history-meta" };
const _hoisted_57 = { class: "text-caption text-medium-emphasis" };
const _hoisted_58 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};
const _hoisted_59 = {
  key: 2,
  class: "d-flex justify-center mt-2"
};
const _hoisted_60 = { class: "d-flex align-center mx-2 text-caption text-medium-emphasis" };
const _hoisted_61 = { class: "dc-section dc-section--logs" };
const _hoisted_62 = { class: "dc-section-title mb-2" };
const _hoisted_63 = { class: "text-caption font-weight-regular text-medium-emphasis" };
const _hoisted_64 = {
  key: 0,
  class: "dc-history-list"
};
const _hoisted_65 = { class: "dc-history-info" };
const _hoisted_66 = { class: "dc-history-title" };
const _hoisted_67 = { class: "dc-history-meta" };
const _hoisted_68 = { class: "text-caption text-medium-emphasis" };
const _hoisted_69 = {
  key: 1,
  class: "text-center text-medium-emphasis py-4 text-caption"
};

const {ref,onMounted} = await importShared('vue');

const INITIAL_LOAD_TIMEOUT_MS = 8000;


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  appPage: { type: Boolean, default: false },
  showSettings: { type: Boolean, default: false },
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
const loadError = ref('');
const dialogItem = ref(null);
const showDialog = ref(false);
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
  return {
    color,
    backgroundColor: `${color}1f`,
    borderColor: `${color}73`,
  }
}

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
  if (source === 'observation') return 'warning'
  if (source === 'anti_cheat_log') return 'warning'
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
    const value = await getPluginApi(props.api, request.path, { timeoutMs: INITIAL_LOAD_TIMEOUT_MS });
    request.apply(value);
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
    const data = await getPluginApi(
      props.api,
      `archive_records?page=${archiveData.value.page}&page_size=${archiveData.value.page_size}`,
      { timeoutMs: INITIAL_LOAD_TIMEOUT_MS },
    );
    if (data) archiveData.value = data;
  } catch (e) {
    loadError.value = '归档记录加载失败';
    console.error('[DoubanCenter] 归档记录加载失败', e);
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

async function goPage(p) {
  if (p < 1 || p > historyData.value.total_pages) return
  historyData.value.page = p;
  await loadAll();
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
  return toPosterThumbnail(item.poster || item.poster_path || item.cover)
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
    rank_key: rk,
    rank_name: item?.rank_name || rankNameOf(rk, item),
    source_link: item?.link || '',
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

function sourceButtonColor() {
  if (!dialogItem.value) return 'primary'
  const { rk, item } = dialogItem.value;
  return sourceDescriptor(rk, item, configData.value).color
}

function sourceButtonIcon() {
  if (!dialogItem.value) return 'mdi-link-variant'
  const { rk, item } = dialogItem.value;
  return sourceDescriptor(rk, item, configData.value).icon
}

function sourceButtonLabel() {
  if (!dialogItem.value) return '详情'
  const { rk, item } = dialogItem.value;
  return sourceDescriptor(rk, item, configData.value).label
}

function sourceButtonUrl() {
  if (!dialogItem.value) return ''
  const { rk, item } = dialogItem.value;
  return sourceDescriptor(rk, item, configData.value).url
}

function sourceButtonAppUrl() {
  if (!dialogItem.value) return ''
  const { rk, item } = dialogItem.value;
  return sourceDescriptor(rk, item, configData.value).appUrl || ''
}

function sourceButtonHref() {
  const webUrl = sourceButtonUrl();
  return sourceButtonAppUrl() || webUrl
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
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: _normalizeClass(["dc-page", { 'dc-page--app': props.appPage }])
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
            class: "ms-3 me-2 dc-page-avatar"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-book-open-page-variant-outline" })
            ]),
            _: 1
          }),
          _createElementVNode("div", _hoisted_1, [
            _createElementVNode("div", _hoisted_2, _toDisplayString(archivePage.value ? '豆瓣中心 · 归档记录' : '豆瓣中心 · 运行详情'), 1),
            _createElementVNode("div", _hoisted_3, _toDisplayString(archivePage.value ? '删除进入归档，支持恢复或彻底删除' : '榜单刷新 -> 黑名筛选 -> 观察队列 -> 订阅记录'), 1)
          ]),
          _createVNode(_component_VSpacer),
          _createElementVNode("div", _hoisted_4, [
            _createVNode(_component_VBtn, {
              variant: "text",
              size: "small",
              class: "text-none dc-toolbar-action",
              title: "刷新",
              "aria-label": "刷新",
              loading: loading.value,
              onClick: _cache[0] || (_cache[0] = $event => (archivePage.value ? loadArchive() : loadAll()))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-refresh",
                  size: "18",
                  class: "dc-toolbar-icon"
                }),
                _cache[8] || (_cache[8] = _createElementVNode("span", { class: "dc-toolbar-label" }, "刷新", -1))
              ]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              variant: "text",
              size: "small",
              class: "text-none dc-toolbar-action",
              title: archivePage.value ? '返回' : '归档',
              "aria-label": archivePage.value ? '返回' : '归档',
              color: archivePage.value ? 'primary' : undefined,
              onClick: _cache[1] || (_cache[1] = $event => (archivePage.value ? closeArchivePage() : openArchivePage()))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: archivePage.value ? 'mdi-arrow-left' : 'mdi-archive-outline',
                  size: "18",
                  class: "dc-toolbar-icon"
                }, null, 8, ["icon"]),
                _createElementVNode("span", _hoisted_5, _toDisplayString(archivePage.value ? '返回' : '归档'), 1)
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
                    _cache[9] || (_cache[9] = _createElementVNode("span", { class: "dc-toolbar-label" }, "设置", -1))
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
      (loading.value)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true),
      _createVNode(_component_VCardText, { class: "pa-3 dc-flow" }, {
        default: _withCtx(() => [
          (loadError.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "dc-load-alert"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_6, [
                    _createElementVNode("span", null, _toDisplayString(loadError.value), 1),
                    _createVNode(_component_VBtn, {
                      variant: "text",
                      size: "x-small",
                      "prepend-icon": "mdi-refresh",
                      class: "text-none",
                      loading: loading.value,
                      onClick: _cache[4] || (_cache[4] = $event => (archivePage.value ? loadArchive() : loadAll()))
                    }, {
                      default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
                        _createTextVNode("重试", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (actionMessage.value)
            ? (_openBlock(), _createElementBlock("div", {
                key: 1,
                class: _normalizeClass(["dc-action-message", actionOk.value ? 'text-success' : 'text-error'])
              }, _toDisplayString(actionMessage.value), 3))
            : _createCommentVNode("", true),
          (archivePage.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                _createElementVNode("div", _hoisted_8, [
                  _cache[11] || (_cache[11] = _createTextVNode("归档记录 ", -1)),
                  _createElementVNode("span", _hoisted_9, "（共 " + _toDisplayString(archiveData.value.total || 0) + " 条）", 1)
                ]),
                (archiveData.value.items && archiveData.value.items.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_10, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(archiveData.value.items, (item, i) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.id || i,
                          class: "dc-history-row dc-archive-row"
                        }, [
                          _createVNode(_component_VAvatar, {
                            rounded: "sm",
                            class: "dc-history-poster mr-2 flex-shrink-0",
                            color: archiveColor(item),
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              (archivePoster(item))
                                ? (_openBlock(), _createBlock(_component_VImg, {
                                    key: 0,
                                    src: archivePoster(item),
                                    cover: ""
                                  }, null, 8, ["src"]))
                                : (_openBlock(), _createBlock(_component_VIcon, {
                                    key: 1,
                                    icon: archiveIcon(item),
                                    size: "14"
                                  }, null, 8, ["icon"]))
                            ]),
                            _: 2
                          }, 1032, ["color"]),
                          _createElementVNode("div", _hoisted_11, [
                            _createElementVNode("div", _hoisted_12, _toDisplayString(archiveTitle(item)), 1),
                            _createElementVNode("div", _hoisted_13, [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                color: archiveColor(item),
                                variant: "tonal",
                                class: "mr-1"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(archiveSourceName(item)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"]),
                              (archiveRankName(item))
                                ? (_openBlock(), _createBlock(_component_VChip, {
                                    key: 0,
                                    size: "x-small",
                                    style: _normalizeStyle(rankChipStyle(archiveRankKey(item))),
                                    variant: "tonal",
                                    class: "dc-rank-chip mr-1"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(archiveRankName(item)), 1)
                                    ]),
                                    _: 2
                                  }, 1032, ["style"]))
                                : _createCommentVNode("", true),
                              _createElementVNode("span", _hoisted_14, _toDisplayString(archiveTime(item) ? archiveTime(item).split(' ')[0] : ''), 1),
                              (item.archived_at)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_15, "归档 " + _toDisplayString(item.archived_at.split(' ')[0]), 1))
                                : _createCommentVNode("", true)
                            ])
                          ]),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: archiveColor(item),
                            variant: "tonal",
                            class: "dc-row-status"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(archiveStatus(item)), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"]),
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
                  : (!loading.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_16, "暂无归档记录"))
                    : _createCommentVNode("", true)
              ]))
            : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                (stats.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                      _cache[14] || (_cache[14] = _createElementVNode("div", { class: "dc-section-title mb-2" }, "订阅统计", -1)),
                      _createElementVNode("div", _hoisted_18, [
                        _createElementVNode("div", _hoisted_19, [
                          _createElementVNode("div", _hoisted_20, _toDisplayString(stats.value.total || 0), 1),
                          _cache[12] || (_cache[12] = _createElementVNode("div", { class: "dc-stat-label" }, "总订阅数", -1))
                        ]),
                        _createElementVNode("div", _hoisted_21, [
                          _createElementVNode("div", _hoisted_22, _toDisplayString(stats.value.month_new || 0), 1),
                          _cache[13] || (_cache[13] = _createElementVNode("div", { class: "dc-stat-label" }, "本月新增", -1))
                        ]),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((stats.value.rank_stats || []), (item) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: item.key,
                            class: "dc-stat-card"
                          }, [
                            _createElementVNode("div", {
                              class: "dc-stat-value",
                              style: _normalizeStyle({ color: rankColorOf(item.key) })
                            }, _toDisplayString(item.count), 5),
                            _createElementVNode("div", _hoisted_23, _toDisplayString(item.name || rankNameOf(item.key)), 1)
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true),
                (rankHistory.value && Object.keys(rankHistory.value).length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
                      _cache[15] || (_cache[15] = _createElementVNode("div", { class: "dc-section-title mb-2" }, [
                        _createTextVNode("榜单快照 "),
                        _createElementVNode("span", { class: "text-caption font-weight-regular text-medium-emphasis" }, "（点击条目订阅或打开来源）")
                      ], -1)),
                      _createElementVNode("div", _hoisted_25, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(Object.entries(rankHistory.value), ([key, items]) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: key,
                            class: "dc-rank-card"
                          }, [
                            _createElementVNode("div", _hoisted_26, [
                              _createVNode(_component_VIcon, {
                                icon: "mdi-format-list-numbered",
                                size: "15",
                                style: _normalizeStyle(rankIconStyle(key)),
                                class: "mr-1"
                              }, null, 8, ["style"]),
                              _createElementVNode("span", null, _toDisplayString(rankNameOf(key, items?.[0])), 1)
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
                                      rounded: "sm",
                                      class: "dc-rank-poster"
                                    }, {
                                      default: _withCtx(() => [
                                        (item.poster)
                                          ? (_openBlock(), _createBlock(_component_VImg, {
                                              key: 0,
                                              src: _unref(toPosterThumbnail)(item.poster),
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
                                    _createElementVNode("span", _hoisted_28, _toDisplayString(item.title || ''), 1),
                                    (key === 'coming' && item.wish_count)
                                      ? (_openBlock(), _createElementBlock("span", _hoisted_29, _toDisplayString(item.wish_count), 1))
                                      : _createCommentVNode("", true)
                                  ], 8, _hoisted_27))
                                }), 128))
                              : (_openBlock(), _createElementBlock("div", _hoisted_30, "暂无榜单数据"))
                          ]))
                        }), 128))
                      ])
                    ]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_31, [
                  _createElementVNode("div", _hoisted_32, [
                    _cache[16] || (_cache[16] = _createTextVNode(" 黑名拦截 ", -1)),
                    _createElementVNode("span", _hoisted_33, "（关键词 " + _toDisplayString(blacklistKeywords.value.length) + " 个，最近命中 " + _toDisplayString(blacklistEntries.value.length) + " 条）", 1),
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
                    ? (_openBlock(), _createElementBlock("div", _hoisted_34, [
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
                            _createElementVNode("div", _hoisted_35, [
                              _createElementVNode("div", _hoisted_36, _toDisplayString(item.title || '未命名条目'), 1),
                              _createElementVNode("div", _hoisted_37, [
                                _createElementVNode("span", _hoisted_38, _toDisplayString(item.time || ''), 1)
                              ])
                            ]),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              color: "error",
                              variant: "tonal",
                              class: "dc-row-status"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.detail || item.reason || '黑名拦截'), 1)
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
                    : (!loading.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_39, "暂无被黑名单筛选的条目"))
                      : _createCommentVNode("", true)
                ]),
                _createElementVNode("div", _hoisted_40, [
                  _createElementVNode("div", _hoisted_41, [
                    _cache[17] || (_cache[17] = _createTextVNode("观察队列 ", -1)),
                    _createElementVNode("span", _hoisted_42, "（待自动订阅 " + _toDisplayString(pendingObservations.value.length) + " 条）", 1)
                  ]),
                  (pendingObservations.value && pendingObservations.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_43, [
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
                            _createElementVNode("div", _hoisted_45, [
                              _createElementVNode("div", _hoisted_46, _toDisplayString(item.title), 1),
                              _createElementVNode("div", _hoisted_47, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  style: _normalizeStyle(rankChipStyle(item.rank_key)),
                                  variant: "tonal",
                                  class: "dc-rank-chip mr-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.rank_name || rankNameOf(item.rank_key, item)), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["style"]),
                                _createElementVNode("span", _hoisted_48, "观察 " + _toDisplayString(item.elapsed_days || 0) + " / " + _toDisplayString(item.observe_days || 0) + " 天", 1)
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
                          ], 8, _hoisted_44))
                        }), 128))
                      ]))
                    : (!loading.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_49, "暂无观察期条目"))
                      : _createCommentVNode("", true)
                ]),
                _createElementVNode("div", _hoisted_50, [
                  _createElementVNode("div", _hoisted_51, [
                    _cache[18] || (_cache[18] = _createTextVNode("订阅历史 ", -1)),
                    _createElementVNode("span", _hoisted_52, "（共 " + _toDisplayString(historyData.value.total) + " 条）", 1)
                  ]),
                  (historyData.value.items && historyData.value.items.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_53, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(historyData.value.items, (item, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-history-row dc-status-row"
                          }, [
                            _createVNode(_component_VAvatar, {
                              rounded: "sm",
                              class: "dc-history-poster mr-2 flex-shrink-0"
                            }, {
                              default: _withCtx(() => [
                                (item.poster)
                                  ? (_openBlock(), _createBlock(_component_VImg, {
                                      key: 0,
                                      src: _unref(toPosterThumbnail)(item.poster),
                                      cover: ""
                                    }, null, 8, ["src"]))
                                  : (_openBlock(), _createBlock(_component_VIcon, {
                                      key: 1,
                                      icon: "mdi-filmstrip",
                                      size: "14"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("div", _hoisted_54, [
                              _createElementVNode("div", _hoisted_55, _toDisplayString(item.title), 1),
                              _createElementVNode("div", _hoisted_56, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  style: _normalizeStyle(rankChipStyle(item.rank_key)),
                                  variant: "tonal",
                                  class: "dc-rank-chip mr-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.rank_name || rankNameOf(item.rank_key, item)), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["style"]),
                                _createElementVNode("span", _hoisted_57, _toDisplayString(item.time ? item.time.split(' ')[0] : ''), 1)
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
                    : (!loading.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_58, "暂无订阅记录"))
                      : _createCommentVNode("", true),
                  (historyData.value.total_pages > 1)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_59, [
                        _createVNode(_component_VBtn, {
                          variant: "text",
                          size: "x-small",
                          disabled: historyData.value.page <= 1,
                          class: "mx-1",
                          onClick: _cache[5] || (_cache[5] = $event => (goPage(historyData.value.page - 1)))
                        }, {
                          default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                            _createTextVNode("上一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"]),
                        _createElementVNode("span", _hoisted_60, _toDisplayString(historyData.value.page) + " / " + _toDisplayString(historyData.value.total_pages), 1),
                        _createVNode(_component_VBtn, {
                          variant: "text",
                          size: "x-small",
                          disabled: historyData.value.page >= historyData.value.total_pages,
                          class: "mx-1",
                          onClick: _cache[6] || (_cache[6] = $event => (goPage(historyData.value.page + 1)))
                        }, {
                          default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                            _createTextVNode("下一页", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled"])
                      ]))
                    : _createCommentVNode("", true)
                ]),
                _createElementVNode("div", _hoisted_61, [
                  _createElementVNode("div", _hoisted_62, [
                    _cache[21] || (_cache[21] = _createTextVNode("观察日志 ", -1)),
                    _createElementVNode("span", _hoisted_63, "（最近 " + _toDisplayString(cheatLogs.value.length) + " 条）", 1)
                  ]),
                  (cheatLogs.value && cheatLogs.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_64, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cheatLogs.value.slice().reverse(), (log, i) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: i,
                            class: "dc-history-row dc-status-row"
                          }, [
                            _createVNode(_component_VAvatar, {
                              rounded: "sm",
                              class: "dc-history-poster mr-2 flex-shrink-0"
                            }, {
                              default: _withCtx(() => [
                                (log.poster)
                                  ? (_openBlock(), _createBlock(_component_VImg, {
                                      key: 0,
                                      src: _unref(toPosterThumbnail)(log.poster),
                                      cover: ""
                                    }, null, 8, ["src"]))
                                  : (_openBlock(), _createBlock(_component_VIcon, {
                                      key: 1,
                                      icon: "mdi-filmstrip",
                                      size: "14"
                                    }))
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("div", _hoisted_65, [
                              _createElementVNode("div", _hoisted_66, _toDisplayString(log.title), 1),
                              _createElementVNode("div", _hoisted_67, [
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  style: _normalizeStyle(rankChipStyle(log.rank_key)),
                                  variant: "tonal",
                                  class: "dc-rank-chip mr-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(log.rank_name || log.rank_key || '观察日志'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["style"]),
                                _createElementVNode("span", _hoisted_68, _toDisplayString(log.time ? log.time.split(' ')[0] : ''), 1)
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
                    : (!loading.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_69, "暂无观察日志"))
                      : _createCommentVNode("", true)
                ])
              ], 64))
        ]),
        _: 1
      }),
      _createVNode(_component_VDialog, {
        modelValue: showDialog.value,
        "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((showDialog).value = $event)),
        "max-width": "420"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCard, {
            rounded: "lg",
            class: "dc-action-dialog"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, { class: "pa-3" }, {
                prepend: _withCtx(() => [
                  _createVNode(_component_VAvatar, {
                    size: "36",
                    rounded: "md",
                    class: "mr-2"
                  }, {
                    default: _withCtx(() => [
                      (dialogPoster())
                        ? (_openBlock(), _createBlock(_component_VImg, {
                            key: 0,
                            src: dialogPoster()
                          }, null, 8, ["src"]))
                        : (_openBlock(), _createBlock(_component_VIcon, {
                            key: 1,
                            icon: "mdi-filmstrip"
                          }))
                    ]),
                    _: 1
                  })
                ]),
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-body-1 font-weight-bold pa-0" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(dialogItem.value?.item?.title || ''), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCardSubtitle, { class: "text-caption pa-0" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(dialogItem.value?.rk ? rankNameOf(dialogItem.value.rk, dialogItem.value.item) : ''), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              _createVNode(_component_VCardActions, { class: "pa-3 pt-2 dc-dialog-actions" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-plus-circle-outline",
                    class: "dc-dialog-action text-none",
                    onClick: doSubscribe
                  }, {
                    default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                      _createTextVNode("订阅", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    "prepend-icon": "mdi-movie-open-outline",
                    class: "dc-dialog-action dc-dialog-action--tmdb text-none",
                    disabled: !(dialogItem.value?.item?.tmdbid || dialogItem.value?.item?.tmdb_id),
                    onClick: doOpenTmdb
                  }, {
                    default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                      _createTextVNode("TMDB", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_VBtn, {
                    href: sourceButtonHref() || undefined,
                    target: "_blank",
                    rel: "noopener noreferrer",
                    variant: "tonal",
                    color: sourceButtonColor(),
                    "prepend-icon": sourceButtonIcon(),
                    disabled: !sourceButtonUrl(),
                    class: "dc-dialog-action text-none",
                    onClick: openSource
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(sourceButtonLabel()), 1)
                    ]),
                    _: 1
                  }, 8, ["href", "color", "prepend-icon", "disabled"])
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
  }, 8, ["class"]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5e63e9e8"]]);

export { Page as default };
