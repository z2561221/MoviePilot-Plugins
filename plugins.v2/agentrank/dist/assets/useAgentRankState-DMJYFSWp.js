import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-BKA7AlB8.js';

const {computed,reactive,ref} = await importShared('vue');

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

  const users = computed(() => options.value.users || []);
  const isRunning = computed(() => board.value?.status === 'running' || loading.action === 'refresh');

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

export { useAgentRankState as u };
