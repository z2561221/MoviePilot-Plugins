import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi, p as postPluginApi, _ as _export_sfc } from './_plugin-vue_export-helper-CgBm1oih.js';

const {computed: computed$1,reactive,ref} = await importShared('vue');

/**
 * 统一管理 AgentRank 用户选择、只读数据与变更动作。
 */
function useAgentRankState(api) {
  const options = ref({ users: [], available_users: [], default_user: '', config: {} });
  const selectedUser = ref('');
  const overview = ref(null);
  const board = ref(null);
  const profile = ref(null);
  const history = ref([]);
  const historyMeta = ref({ total: 0, page: 1, page_size: 15 });
  const loading = reactive({ options: false, data: false, action: '' });
  const error = ref(null);
  const feedback = ref(null);

  const users = computed$1(() => options.value.users || []);
  const isRunning = computed$1(() => board.value?.status === 'running' || loading.action === 'refresh');

  async function loadOptions() {
    loading.options = true;
    error.value = null;
    try {
      options.value = (await getPluginApi(api, 'config/options')) || options.value;
      const candidates = options.value.users || [];
      if (!candidates.includes(selectedUser.value)) {
        selectedUser.value = options.value.default_user || candidates[0] || '';
      }
      return options.value
    } catch (err) {
      error.value = err;
      throw err
    } finally {
      loading.options = false;
    }
  }

  async function loadUserData(username = selectedUser.value) {
    if (!username) return null
    loading.data = true;
    error.value = null;
    try {
      const params = { username };
      const [overviewData, boardData, profileData, historyData] = await Promise.all([
        getPluginApi(api, 'overview', params),
        getPluginApi(api, 'board', params),
        getPluginApi(api, 'profile', params),
        getPluginApi(api, 'run-history', params),
      ]);
      overview.value = overviewData;
      board.value = boardData;
      profile.value = profileData;
      history.value = historyData?.items || [];
      historyMeta.value = {
        total: historyData?.total || history.value.length,
        page: historyData?.page || 1,
        page_size: historyData?.page_size || 15,
      };
      return overviewData
    } catch (err) {
      error.value = err;
      throw err
    } finally {
      loading.data = false;
    }
  }

  async function loadHistory(page = 1, pageSize = 15) {
    if (!selectedUser.value) return []
    const result = await getPluginApi(api, 'run-history', {
      username: selectedUser.value,
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
    const result = await runAction('refresh', { username: selectedUser.value }, '刷新');
    await loadUserData();
    return result
  }

  async function archive(candidateId) {
    const result = await runAction(
      'archive',
      { username: selectedUser.value, candidate_id: candidateId },
      '忽略',
    );
    await loadUserData();
    return result
  }

  async function restore(candidateId) {
    const result = await runAction(
      'restore',
      { username: selectedUser.value, candidate_id: candidateId },
      '恢复',
    );
    await loadUserData();
    return result
  }

  async function deleteArchive(candidateId) {
    const result = await runAction(
      'archive/delete',
      { username: selectedUser.value, candidate_id: candidateId },
      '删除归档',
    );
    await loadUserData();
    return result
  }

  async function clearProfile() {
    const result = await runAction(
      'profile/clear',
      { username: selectedUser.value, confirm: true },
      '清除画像',
    );
    await loadUserData();
    return result
  }

  async function subscribe(candidateId) {
    const result = await runAction(
      'subscribe',
      { username: selectedUser.value, candidate_id: candidateId },
      '订阅',
    );
    await loadUserData();
    return result
  }

  return {
    options,
    users,
    selectedUser,
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
    loadUserData,
    loadHistory,
    refresh,
    archive,
    restore,
    deleteArchive,
    clearProfile,
    subscribe,
  }
}

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = ["aria-label"];

const {computed} = await importShared('vue');



const _sfc_main = {
  __name: 'RecommendationActions',
  props: {
  item: { type: Object, required: true },
  loadingAction: { type: String, default: '' },
  size: { type: String, default: 'x-small' },
},
  emits: ['subscribe', 'archive'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const sourceIds = computed(() => props.item?.source_ids || {});
const tmdbId = computed(() => sourceIds.value.tmdb || '');
const doubanId = computed(() => sourceIds.value.douban || '');
const bangumiId = computed(() => sourceIds.value.bangumi || '');
const prefersBangumi = computed(() => props.item?.media_type === 'anime' && bangumiId.value);
const sourceLabel = computed(() => prefersBangumi.value || (!doubanId.value && bangumiId.value) ? 'Bgm' : '豆瓣');
const sourceId = computed(() => sourceLabel.value === 'Bgm' ? bangumiId.value : doubanId.value);
const sourceColor = computed(() => sourceLabel.value === 'Bgm' ? '#F838A0' : '#08B810');

function openExternal(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer');
}

function openTmdb() {
  if (!tmdbId.value) return
  const mediaPath = props.item?.media_type === 'movie' ? 'movie' : 'tv';
  openExternal(`https://www.themoviedb.org/${mediaPath}/${encodeURIComponent(tmdbId.value)}`);
}

function openSource() {
  if (!sourceId.value) return
  if (sourceLabel.value === 'Bgm') {
    openExternal(`https://bgm.tv/subject/${encodeURIComponent(sourceId.value)}`);
    return
  }
  openExternal(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${encodeURIComponent(sourceId.value)}?from=mdouban&open=app`);
}

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");

  return (_openBlock(), _createElementBlock("div", {
    class: "ar-actions",
    role: "group",
    "aria-label": `${__props.item.title} 操作`
  }, [
    _createVNode(_component_VBtn, {
      size: __props.size,
      variant: "tonal",
      color: "primary",
      class: "ar-actions__button text-none",
      loading: __props.loadingAction === 'subscribe',
      onClick: _cache[0] || (_cache[0] = $event => (emit('subscribe', __props.item.candidate_id)))
    }, {
      default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
        _createTextVNode("订阅", -1)
      ]))]),
      _: 1
    }, 8, ["size", "loading"]),
    _createVNode(_component_VBtn, {
      size: __props.size,
      variant: "tonal",
      color: "info",
      class: "ar-actions__button text-none",
      disabled: !tmdbId.value,
      onClick: openTmdb
    }, {
      default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
        _createTextVNode("TMDB", -1)
      ]))]),
      _: 1
    }, 8, ["size", "disabled"]),
    _createVNode(_component_VBtn, {
      size: __props.size,
      variant: "tonal",
      color: sourceColor.value,
      class: "ar-actions__button text-none",
      disabled: !sourceId.value,
      onClick: openSource
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(sourceLabel.value), 1)
      ]),
      _: 1
    }, 8, ["size", "color", "disabled"]),
    _createVNode(_component_VBtn, {
      size: __props.size,
      variant: "tonal",
      color: "default",
      class: "ar-actions__button text-none",
      loading: __props.loadingAction === 'archive',
      onClick: _cache[1] || (_cache[1] = $event => (emit('archive', __props.item.candidate_id)))
    }, {
      default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
        _createTextVNode("忽略", -1)
      ]))]),
      _: 1
    }, 8, ["size", "loading"])
  ], 8, _hoisted_1))
}
}

};
const RecommendationActions = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ab00d0e5"]]);

export { RecommendationActions as R, useAgentRankState as u };
