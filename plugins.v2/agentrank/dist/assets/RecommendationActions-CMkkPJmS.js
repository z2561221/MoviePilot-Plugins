import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi, p as postPluginApi, _ as _export_sfc } from './_plugin-vue_export-helper-BGNRvR24.js';

const {computed: computed$1,reactive,ref: ref$1} = await importShared('vue');

const OPTIONS_CACHE_TTL_MS = 5 * 60 * 1000;
const PROFILE_CACHE_TTL_MS = 60 * 1000;
const cacheByApi = new WeakMap();
const fallbackCache = createSharedCache();

function createSharedCache() {
  return {
    options: null,
    optionsUpdatedAt: 0,
    optionsRequest: null,
    profiles: new Map(),
  }
}

function sharedCacheFor(api) {
  if (!api || !['object', 'function'].includes(typeof api)) return fallbackCache
  if (!cacheByApi.has(api)) cacheByApi.set(api, createSharedCache());
  return cacheByApi.get(api)
}

function isFresh(updatedAt, ttl) {
  return updatedAt > 0 && Date.now() - updatedAt < ttl
}

function emptyBoard(profileId, username = '') {
  return {
    profile_id: profileId,
    username,
    run_id: '',
    status: 'idle',
    recommendations: [],
    generated_at: '',
    message: '尚未生成榜单',
  }
}

function emptyProfile(profileId, username = '') {
  return {
    profile_id: profileId,
    username,
    summary: '',
    tags: [],
    negative_tags: [],
    playback_count: 0,
    run_id: '',
    generated_at: '',
  }
}

/**
 * 统一管理 AgentRank Emby identity 选择、只读数据与变更动作。
 */
function useAgentRankState(api) {
  const sharedCache = sharedCacheFor(api);
  const options = ref$1({ emby_identities: [], default_profile_id: '', config: {} });
  const selectedProfileId = ref$1('');
  const overview = ref$1(null);
  const board = ref$1(null);
  const profile = ref$1(null);
  const history = ref$1([]);
  const historyMeta = ref$1({ total: 0, page: 1, page_size: 15 });
  const loading = reactive({ options: false, data: false, action: '' });
  const error = ref$1(null);
  const feedback = ref$1(null);

  const identities = computed$1(() => {
    const configured = options.value.config?.emby_identities;
    return Array.isArray(configured) ? configured : (options.value.emby_identities || [])
  });
  const identityOptions = computed$1(() => identities.value.map(identity => ({
    title: [identity.username, identity.server_name].filter(Boolean).join(' · '),
    value: identity.profile_id,
  })));
  const selectedIdentity = computed$1(() => identities.value.find(identity => identity.profile_id === selectedProfileId.value) || null);
  const selectedUsername = computed$1(() => overview.value?.username || selectedIdentity.value?.username || '');
  const isRunning = computed$1(() => board.value?.status === 'running' || loading.action === 'refresh');

  function applyOptions(value) {
    options.value = value || options.value;
    const candidates = identities.value.map(identity => identity.profile_id);
    if (!candidates.includes(selectedProfileId.value)) {
      selectedProfileId.value = options.value.default_profile_id || options.value.config?.default_profile_id || candidates[0] || '';
    }
    return options.value
  }

  function fetchOptions() {
    if (!sharedCache.optionsRequest) {
      sharedCache.optionsRequest = getPluginApi(api, 'config/options')
        .then(value => {
          sharedCache.options = value;
          sharedCache.optionsUpdatedAt = Date.now();
          return value
        })
        .finally(() => { sharedCache.optionsRequest = null; });
    }
    return sharedCache.optionsRequest
  }

  async function loadOptions({ force = false } = {}) {
    const cached = sharedCache.options;
    if (cached) {
      applyOptions(cached);
      if (!force) {
        if (!isFresh(sharedCache.optionsUpdatedAt, OPTIONS_CACHE_TTL_MS)) {
          void fetchOptions().then(applyOptions).catch(() => {});
        }
        return cached
      }
    }
    loading.options = !cached;
    error.value = null;
    try {
      return applyOptions(await fetchOptions())
    } catch (err) {
      error.value = err;
      throw err
    } finally {
      loading.options = false;
    }
  }

  function profileCacheEntry(profileId) {
    if (!sharedCache.profiles.has(profileId)) {
      sharedCache.profiles.set(profileId, { value: null, updatedAt: 0, request: null });
    }
    return sharedCache.profiles.get(profileId)
  }

  function applyProfileData(data, profileId) {
    const username = selectedIdentity.value?.username || '';
    const overviewData = data || { profile_id: profileId, username };
    const recentHistory = Array.isArray(overviewData.history)
      ? overviewData.history
      : overviewData.latest_run ? [overviewData.latest_run] : [];
    overview.value = overviewData;
    board.value = overviewData.board || emptyBoard(profileId, username);
    profile.value = overviewData.profile || emptyProfile(profileId, username);
    history.value = recentHistory;
    historyMeta.value = {
      total: Number(overviewData.history_total ?? recentHistory.length),
      page: 1,
      page_size: 15,
    };
    return overviewData
  }

  function fetchProfileData(profileId, entry) {
    if (!entry.request) {
      entry.request = getPluginApi(api, 'overview', { profile_id: profileId })
        .then(value => {
          entry.value = value;
          entry.updatedAt = Date.now();
          return value
        })
        .finally(() => { entry.request = null; });
    }
    return entry.request
  }

  async function loadProfileData(profileId = selectedProfileId.value, { force = false } = {}) {
    if (!profileId) return null
    const entry = profileCacheEntry(profileId);
    const cached = entry.value;
    if (cached) {
      applyProfileData(cached, profileId);
      if (!force) {
        if (!isFresh(entry.updatedAt, PROFILE_CACHE_TTL_MS)) {
          void fetchProfileData(profileId, entry)
            .then(value => {
              if (selectedProfileId.value === profileId) applyProfileData(value, profileId);
            })
            .catch(() => {});
        }
        return cached
      }
    }
    loading.data = !cached;
    error.value = null;
    try {
      const value = await fetchProfileData(profileId, entry);
      if (selectedProfileId.value !== profileId) return value
      return applyProfileData(value, profileId)
    } catch (err) {
      error.value = err;
      throw err
    } finally {
      loading.data = false;
    }
  }

  async function loadHistory(page = 1, pageSize = 15) {
    if (!selectedProfileId.value) return []
    const result = await getPluginApi(api, 'run-history', {
      profile_id: selectedProfileId.value,
      page,
      page_size: pageSize,
    });
    history.value = result?.items || [];
    historyMeta.value = {
      total: result?.total || 0,
      page: result?.page || page,
      page_size: result?.page_size || pageSize,
    };
    return history.value
  }

  async function runAction(path, payload, label) {
    if (loading.action) return null
    loading.action = path;
    error.value = null;
    feedback.value = null;
    try {
      const result = await postPluginApi(api, path, payload);
      feedback.value = { ok: true, message: `${label}已完成`, result };
      return result
    } catch (err) {
      error.value = err;
      feedback.value = { ok: false, message: err?.message || `${label}失败` };
      throw err
    } finally {
      loading.action = '';
    }
  }

  async function refresh() {
    const result = await runAction('refresh', { profile_id: selectedProfileId.value }, '刷新');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function archive(candidateId) {
    const result = await runAction('archive', { profile_id: selectedProfileId.value, candidate_id: candidateId }, '忽略');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function restore(candidateId) {
    const result = await runAction('restore', { profile_id: selectedProfileId.value, candidate_id: candidateId }, '恢复');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function deleteArchive(candidateId) {
    const result = await runAction('archive/delete', { profile_id: selectedProfileId.value, candidate_id: candidateId }, '删除归档');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function clearProfile() {
    const result = await runAction('profile/clear', { profile_id: selectedProfileId.value, confirm: true }, '清除画像');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function updateProfileTag(kind, action, tag) {
    const result = await runAction('profile/tags', { profile_id: selectedProfileId.value, kind, action, tag }, action === 'add' ? '添加标签' : '删除标签');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  async function subscribe(candidateId) {
    const result = await runAction('subscribe', { profile_id: selectedProfileId.value, candidate_id: candidateId }, '订阅');
    await loadProfileData(selectedProfileId.value, { force: true });
    return result
  }

  return {
    options,
    identities,
    identityOptions,
    selectedProfileId,
    selectedIdentity,
    selectedUsername,
    overview,
    board,
    profile,
    history,
    historyMeta,
    loading,
    error,
    feedback,
    isRunning,
    loadOptions,
    loadProfileData,
    loadHistory,
    refresh,
    archive,
    restore,
    deleteArchive,
    clearProfile,
    updateProfileTag,
    subscribe,
  }
}

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,mergeProps:_mergeProps,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = ["aria-label"];

const {computed,inject,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'RecommendationActions',
  props: {
  item: { type: Object, required: true },
  loadingAction: { type: String, default: '' },
  size: { type: String, default: 'x-small' },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['subscribe', 'archive'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const injectedNativeSubscribe = inject('moviepilot:nativeSubscribe', null);
const nativeSubscribePending = ref(false);

function firstId(...values) {
  for (const value of values) {
    if (value === null || value === undefined) continue
    const text = String(value).trim();
    if (text && text !== '0') return text
  }
  return ''
}

const sourceIds = computed(() => {
  const raw = props.item?.source_ids || {};
  const value = { ...raw };
  const aliases = {
    tmdb: ['tmdb', 'tmdb_id', 'tmdbid', 'themoviedb', 'themoviedb_id'],
    douban: ['douban', 'douban_id', 'doubanid'],
    bangumi: ['bangumi', 'bangumi_id', 'bangumiid', 'bgm', 'bgm_id'],
    anilist: ['anilist', 'anilist_id', 'anilistid'],
  };
  Object.entries(aliases).forEach(([canonical, names]) => {
    if (firstId(value[canonical])) return
    const match = names.map(name => value[name]).find(valueForAlias => firstId(valueForAlias));
    if (match !== undefined) value[canonical] = match;
  });
  Object.entries(aliases).forEach(([canonical, names]) => {
    if (firstId(value[canonical])) return
    const match = [props.item?.[canonical], ...names.map(name => props.item?.[name])]
      .find(valueForAlias => firstId(valueForAlias));
    if (match !== undefined) value[canonical] = match;
  });
  return value
});

const tmdbId = computed(() => firstId(sourceIds.value.tmdb));
const doubanId = computed(() => firstId(sourceIds.value.douban));
const bangumiId = computed(() => firstId(sourceIds.value.bangumi));
const anilistId = computed(() => firstId(sourceIds.value.anilist));
const nativeSubscribe = computed(() => props.nativeSubscribe || injectedNativeSubscribe);
const nativeMediaType = computed(() => props.item?.media_type === 'movie' ? '电影' : '电视剧');

const nativeMedia = computed(() => {
  const sourceId = tmdbId.value || doubanId.value || bangumiId.value || anilistId.value;
  const source = tmdbId.value
    ? 'themoviedb'
    : doubanId.value
      ? 'douban'
      : bangumiId.value
        ? 'bangumi'
        : anilistId.value
          ? 'anilist'
          : '';
  const media = {
    title: String(props.item?.title || props.item?.name || '').trim(),
    name: String(props.item?.title || props.item?.name || '').trim(),
    type: nativeMediaType.value,
    media_type: props.item?.media_type || '',
    year: props.item?.year ? String(props.item.year) : '',
    poster_path: String(props.item?.poster_path || '').trim(),
  };
  if (source && sourceId) {
    media.source = source;
    media.media_source = source;
    media.mediaid_prefix = source;
    media.media_id = sourceId;
  }
  if (tmdbId.value) {
    media.tmdb_id = tmdbId.value;
    media.tmdbid = tmdbId.value;
  }
  if (doubanId.value) {
    media.douban_id = doubanId.value;
    media.doubanid = doubanId.value;
  }
  if (bangumiId.value) {
    media.bangumi_id = bangumiId.value;
    media.bangumiid = bangumiId.value;
  }
  if (anilistId.value) {
    media.anilist_id = anilistId.value;
    media.anilistid = anilistId.value;
  }
  return media
});

function openExternal(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer');
}

function openTmdb() {
  if (!tmdbId.value) return
  const mediaPath = props.item?.media_type === 'movie' ? 'movie' : 'tv';
  openExternal(`https://www.themoviedb.org/${mediaPath}/${encodeURIComponent(tmdbId.value)}`);
}

/** 先调用宿主原生订阅，旧宿主或无效媒体才回退插件安全链。 */
async function handleSubscribe() {
  if (nativeSubscribePending.value) return
  const callback = nativeSubscribe.value;
  if (typeof callback !== 'function') {
    emit('subscribe', props.item?.candidate_id);
    return
  }
  nativeSubscribePending.value = true;
  try {
    const result = await callback(nativeMedia.value);
    if (result?.success === true || result?.code === 'PERMISSION_DENIED') return
    emit('subscribe', props.item?.candidate_id);
  } catch (_) {
    emit('subscribe', props.item?.candidate_id);
  } finally {
    nativeSubscribePending.value = false;
  }
}

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTooltip = _resolveComponent("VTooltip");

  return (_openBlock(), _createElementBlock("div", {
    class: "ar-actions",
    role: "group",
    "aria-label": `${__props.item.title} 操作`
  }, [
    _createVNode(_component_VTooltip, {
      text: "订阅",
      location: "top"
    }, {
      activator: _withCtx(({ props: tooltipProps }) => [
        _createVNode(_component_VBtn, _mergeProps(tooltipProps, {
          size: __props.size,
          variant: "tonal",
          color: "primary",
          class: "ar-actions__button text-none",
          "prepend-icon": "mdi-bookmark-plus-outline",
          loading: __props.loadingAction === 'subscribe' || nativeSubscribePending.value,
          "aria-label": "订阅",
          onClick: handleSubscribe
        }), {
          default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "订阅", -1)
          ]))]),
          _: 1
        }, 16, ["size", "loading"])
      ]),
      _: 1
    }),
    _createVNode(_component_VTooltip, {
      text: "打开 TMDB",
      location: "top"
    }, {
      activator: _withCtx(({ props: tooltipProps }) => [
        _createVNode(_component_VBtn, _mergeProps(tooltipProps, {
          size: __props.size,
          "prepend-icon": "mdi-movie-open-outline",
          variant: "tonal",
          class: "ar-actions__button ar-actions__button--tmdb text-none",
          disabled: !tmdbId.value,
          "aria-label": "打开 TMDB",
          onClick: openTmdb
        }), {
          default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "TMDB", -1)
          ]))]),
          _: 1
        }, 16, ["size", "disabled"])
      ]),
      _: 1
    }),
    _createVNode(_component_VTooltip, {
      text: "忽略",
      location: "top"
    }, {
      activator: _withCtx(({ props: tooltipProps }) => [
        _createVNode(_component_VBtn, _mergeProps(tooltipProps, {
          size: __props.size,
          variant: "tonal",
          color: "default",
          class: "ar-actions__button text-none",
          "prepend-icon": "mdi-eye-off-outline",
          loading: __props.loadingAction === 'archive',
          "aria-label": "忽略",
          onClick: _cache[0] || (_cache[0] = $event => (emit('archive', __props.item.candidate_id)))
        }), {
          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "忽略", -1)
          ]))]),
          _: 1
        }, 16, ["size", "loading"])
      ]),
      _: 1
    })
  ], 8, _hoisted_1))
}
}

};
const RecommendationActions = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c928d13d"]]);

export { RecommendationActions as R, useAgentRankState as u };
