import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { p as postPluginApi, g as getPluginApi, _ as _export_sfc } from './_plugin-vue_export-helper-Z-mQLghu.js';

const {computed: computed$1,reactive,ref: ref$1,watch} = await importShared('vue');

const OPTIONS_CACHE_TTL_MS = 5 * 60 * 1000;
const PROFILE_CACHE_TTL_MS = 60 * 1000;
const ACTIVITY_LIMIT = 50;
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
    revision: 0,
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

function emptyConversation() {
  return { thread: null, messages: [], commands: [] }
}

function emptyPendingCenter(profileId = '') {
  return {
    profile_id: profileId,
    items: [],
    counts: { proposal: 0, question: 0, command: 0 },
    total: 0,
  }
}

function emptyAttribution(profileId = '') {
  return { profile_id: profileId, records: [] }
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
  const operations = reactive({});
  const analyses = reactive({});
  const activity = ref$1([]);
  const conversation = ref$1(emptyConversation());
  const pendingCenter = ref$1(emptyPendingCenter());
  const processedCenter = ref$1({ ...emptyPendingCenter(), view: 'resolved' });
  const attribution = ref$1(emptyAttribution());
  const exportedData = ref$1(null);
  const fullResetConfirmation = ref$1(null);
  const secondaryProfileId = ref$1('');
  const pendingFeedbackRequests = new Map();

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

  function operationState(key) {
    const name = String(key || 'unknown');
    if (!operations[name]) {
      operations[name] = {
        loading: false,
        error: null,
        retry: null,
        updatedAt: 0,
        sequence: 0,
      };
    }
    return operations[name]
  }

  function clearOperationError(key) {
    const state = operationState(key);
    state.error = null;
    state.retry = null;
    if (error.value && !Object.values(operations).some(item => item.error === error.value)) {
      error.value = null;
    }
  }

  async function retryOperation(key) {
    const retry = operationState(key).retry;
    if (typeof retry !== 'function') return null
    return retry()
  }

  async function runOperation(key, task, retry, settings = {}) {
    const state = operationState(key);
    const sequence = state.sequence + 1;
    state.sequence = sequence;
    const legacyLoading = settings.legacyLoading || '';
    const actionKey = settings.actionKey || '';
    state.loading = true;
    state.error = null;
    state.retry = null;
    if (legacyLoading) loading[legacyLoading] = true;
    if (actionKey) loading.action = actionKey;
    if (settings.globalError !== false) error.value = null;
    const isCurrent = () => state.sequence === sequence;
    try {
      const result = await task({ isCurrent, sequence });
      if (isCurrent()) state.updatedAt = Date.now();
      return result
    } catch (err) {
      if (isCurrent()) {
        state.error = err;
        state.retry = typeof retry === 'function' ? retry : null;
        if (settings.globalError !== false) error.value = err;
      }
      if (settings.throwOnError === false) return settings.fallback ?? null
      throw err
    } finally {
      if (isCurrent()) {
        state.loading = false;
        if (legacyLoading) loading[legacyLoading] = false;
        if (actionKey && loading.action === actionKey) loading.action = '';
      }
    }
  }

  function recordActivity(kind, result) {
    const entry = {
      kind,
      event: result?.event || null,
      queue_status: result?.queue_status || '',
      queue_job: result?.queue_job || null,
      recorded_at: new Date().toISOString(),
    };
    activity.value = [entry, ...activity.value].slice(0, ACTIVITY_LIMIT);
    return entry
  }

  function ensureSecondaryScope(profileId = selectedProfileId.value) {
    const target = String(profileId || '');
    if (secondaryProfileId.value === target) return
    secondaryProfileId.value = target;
    Object.entries(operations).forEach(([key, state]) => {
      if (key === 'options') return
      state.sequence += 1;
      state.loading = false;
      state.error = null;
      state.retry = null;
      state.updatedAt = 0;
    });
    loading.data = false;
    loading.action = '';
    error.value = null;
    feedback.value = null;
    const username = identities.value.find(identity => identity.profile_id === target)?.username || '';
    overview.value = null;
    board.value = emptyBoard(target, username);
    profile.value = emptyProfile(target, username);
    history.value = [];
    historyMeta.value = { total: 0, page: 1, page_size: 15 };
    Object.keys(analyses).forEach(key => delete analyses[key]);
    activity.value = [];
    conversation.value = emptyConversation();
    pendingCenter.value = emptyPendingCenter(target);
    processedCenter.value = { ...emptyPendingCenter(target), view: 'resolved' };
    attribution.value = emptyAttribution(target);
    exportedData.value = null;
    fullResetConfirmation.value = null;
  }

  function requireCurrentProfile(profileId) {
    if (profileId && selectedProfileId.value === profileId) return profileId
    const scopeError = new Error('画像身份已切换，请在当前身份下重新操作');
    scopeError.code = 'profile_scope_changed';
    throw scopeError
  }

  function activeProfileScope() {
    const target = selectedProfileId.value;
    ensureSecondaryScope(target);
    return target
  }

  function retryForProfile(profileId, retry) {
    return () => {
      requireCurrentProfile(profileId);
      return retry()
    }
  }

  function invalidateProfileCache(profileId = selectedProfileId.value) {
    if (!profileId) return
    const entry = profileCacheEntry(profileId);
    entry.updatedAt = 0;
  }

  async function refreshProfileAfterMutation(profileId = selectedProfileId.value) {
    invalidateProfileCache(profileId);
    if (selectedProfileId.value !== profileId) return
    await Promise.allSettled([loadProfileData(profileId, { force: true })]);
  }

  function applyOptions(value) {
    options.value = value || options.value;
    const candidates = identities.value.map(identity => identity.profile_id);
    if (!candidates.includes(selectedProfileId.value)) {
      selectedProfileId.value = options.value.default_profile_id || options.value.config?.default_profile_id || candidates[0] || '';
    }
    ensureSecondaryScope(selectedProfileId.value);
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
          void runOperation(
            'options',
            async ({ isCurrent }) => {
              const value = await fetchOptions();
              return isCurrent() ? applyOptions(value) : value
            },
            () => loadOptions({ force: true }),
            { globalError: false, throwOnError: false, fallback: cached },
          );
        }
        return cached
      }
    }
    return runOperation(
      'options',
      async ({ isCurrent }) => {
        const value = await fetchOptions();
        return isCurrent() ? applyOptions(value) : value
      },
      () => loadOptions({ force: true }),
      { legacyLoading: cached ? '' : 'options' },
    )
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
    requireCurrentProfile(profileId);
    ensureSecondaryScope(profileId);
    const entry = profileCacheEntry(profileId);
    const cached = entry.value;
    if (cached) {
      applyProfileData(cached, profileId);
      if (!force) {
        if (!isFresh(entry.updatedAt, PROFILE_CACHE_TTL_MS)) {
          void runOperation(
            'profile',
            async ({ isCurrent }) => {
              const value = await fetchProfileData(profileId, entry);
              if (isCurrent() && selectedProfileId.value === profileId) applyProfileData(value, profileId);
              return value
            },
            retryForProfile(profileId, () => loadProfileData(profileId, { force: true })),
            { globalError: false, throwOnError: false, fallback: cached },
          );
        }
        return cached
      }
    }
    return runOperation(
      'profile',
      async ({ isCurrent }) => {
        const value = await fetchProfileData(profileId, entry);
        if (!isCurrent() || selectedProfileId.value !== profileId) return value
        return applyProfileData(value, profileId)
      },
      retryForProfile(profileId, () => loadProfileData(profileId, { force: true })),
      { legacyLoading: cached ? '' : 'data' },
    )
  }

  async function loadHistory(page = 1, pageSize = 15) {
    const targetProfile = activeProfileScope();
    if (!targetProfile) return []
    return runOperation(
      'history',
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'run-history', {
          profile_id: targetProfile,
          page,
          page_size: pageSize,
        });
        if (!isCurrent() || selectedProfileId.value !== targetProfile) return result?.items || []
        history.value = result?.items || [];
        historyMeta.value = {
          total: result?.total || 0,
          page: result?.page || page,
          page_size: result?.page_size || pageSize,
        };
        return history.value
      },
      retryForProfile(targetProfile, () => loadHistory(page, pageSize)),
      { globalError: false },
    )
  }

  async function runAction(path, payload, label, loadingKey = path) {
    if (loading.action) return null
    feedback.value = null;
    const execute = async ({ isCurrent }) => {
      const result = await postPluginApi(api, path, payload);
      if (isCurrent()) feedback.value = { ok: true, message: `${label}已完成`, result };
      return result
    };
    try {
      const retry = () => runAction(path, payload, label, loadingKey);
      return await runOperation(
        loadingKey,
        execute,
        payload?.profile_id ? retryForProfile(payload.profile_id, retry) : retry,
        { actionKey: loadingKey },
      )
    } catch (err) {
      if (operationState(loadingKey).error === err) {
        feedback.value = { ok: false, message: err?.message || `${label}失败` };
      }
      throw err
    }
  }

  async function refresh() {
    const targetProfile = activeProfileScope();
    const result = await runAction('refresh', { profile_id: targetProfile }, '刷新');
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function archive(candidateId) {
    const targetProfile = activeProfileScope();
    const result = await runAction('archive', { profile_id: targetProfile, candidate_id: candidateId }, '忽略');
    if (result && selectedProfileId.value === targetProfile) recordActivity('ignore', result);
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  function requestId(prefix = 'request') {
    if (globalThis.crypto?.randomUUID) return `${prefix}:${globalThis.crypto.randomUUID()}`
    return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2)}`
  }

  function feedbackRequestId() {
    return requestId('feedback')
  }

  async function reactToRecommendation(kind, candidateId) {
    const targetProfile = activeProfileScope();
    const requestedAction = String(kind || '').trim().toLowerCase();
    if (!['like', 'dislike'].includes(requestedAction)) throw new Error('未知的榜单反馈类型')
    const currentBoard = board.value || emptyBoard(targetProfile);
    const currentItem = currentBoard.recommendations?.find(entry => entry.candidate_id === candidateId);
    const action = currentItem?.feedback_kind === requestedAction ? 'neutral' : requestedAction;
    const requestScope = [
      targetProfile,
      currentBoard.run_id || '',
      currentBoard.revision || 0,
      candidateId,
      action,
    ].join('|');
    if (!pendingFeedbackRequests.has(requestScope)) {
      pendingFeedbackRequests.set(requestScope, feedbackRequestId());
    }
    let result;
    try {
      result = await runAction(
        'feedback',
        {
          profile_id: targetProfile,
          candidate_id: candidateId,
          kind: action,
          idempotency_key: pendingFeedbackRequests.get(requestScope),
          run_id: currentBoard.run_id || '',
          board_revision: currentBoard.revision || 1,
        },
        action === 'neutral' ? '取消反馈' : action === 'like' ? '点赞' : '点踩',
        `feedback:${requestedAction}:${candidateId}`,
      );
    } catch (error) {
      if (['board_run_conflict', 'board_revision_conflict'].includes(error?.code)) {
        pendingFeedbackRequests.delete(requestScope);
        await refreshProfileAfterMutation(targetProfile);
      }
      throw error
    }
    if (!result) return null
    pendingFeedbackRequests.delete(requestScope);
    if (selectedProfileId.value === targetProfile) recordActivity(action, result);
    if (result?.board_changed) {
      await refreshProfileAfterMutation(targetProfile);
      return result
    }
    const effectiveKind = result?.event?.kind || action;
    if (currentItem) currentItem.feedback_kind = effectiveKind === 'neutral' ? '' : effectiveKind;
    currentBoard.revision = Number(result?.board_revision || currentBoard.revision || 1);
    return result
  }

  async function restore(candidateId) {
    const targetProfile = activeProfileScope();
    const result = await runAction('restore', { profile_id: targetProfile, candidate_id: candidateId }, '恢复');
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function deleteArchive(candidateId) {
    const targetProfile = activeProfileScope();
    const result = await runAction('archive/delete', { profile_id: targetProfile, candidate_id: candidateId }, '删除归档');
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function clearProfile() {
    const targetProfile = activeProfileScope();
    const result = await runAction('profile/clear', { profile_id: targetProfile, confirm: true }, '清除画像');
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function updateProfileTag(kind, action, tag) {
    const targetProfile = activeProfileScope();
    const actionLabel = action === 'remove' ? '归档标签' : action === 'restore' ? '恢复标签' : '添加标签';
    const result = await runAction('profile/tags', { profile_id: targetProfile, kind, action, tag }, actionLabel);
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function subscribe(candidateId) {
    const targetProfile = activeProfileScope();
    const result = await runAction('subscribe', { profile_id: targetProfile, candidate_id: candidateId }, '订阅');
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function recordNativeDrawerOpened(candidateId) {
    const targetProfile = activeProfileScope();
    const result = await runAction(
      'attribution/native-drawer-opened',
      { profile_id: targetProfile, candidate_id: candidateId },
      '记录原生订阅交互',
      `attribution:native:${candidateId}`,
    );
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  function currentAnalysis(candidateId) {
    return analyses[candidateId] || null
  }

  async function loadAnalysis(candidateId, analysisId) {
    const targetProfile = activeProfileScope();
    const targetCandidate = String(candidateId || '').trim();
    const targetAnalysis = String(analysisId || '').trim();
    if (!targetProfile || !targetCandidate || !targetAnalysis) return null
    const key = `analysis:${targetCandidate}`;
    return runOperation(
      key,
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'analysis', {
          profile_id: targetProfile,
          candidate_id: targetCandidate,
          analysis_id: targetAnalysis,
        });
        if (isCurrent() && selectedProfileId.value === targetProfile) analyses[targetCandidate] = result;
        return result
      },
      retryForProfile(targetProfile, () => loadAnalysis(targetCandidate, targetAnalysis)),
      { globalError: false },
    )
  }

  async function commentOnAnalysis(candidateId, comment, idempotencyKey = requestId('analysis-comment')) {
    const targetProfile = activeProfileScope();
    const currentBoard = board.value || emptyBoard(targetProfile);
    const item = currentBoard.recommendations?.find(value => value.candidate_id === candidateId);
    if (!item?.analysis_id) throw new Error('当前推荐分析不可用，请刷新榜单后重试')
    const payload = {
      profile_id: targetProfile,
      candidate_id: candidateId,
      analysis_id: item.analysis_id,
      comment,
      idempotency_key: idempotencyKey,
      run_id: currentBoard.run_id || '',
      board_revision: currentBoard.revision || 1,
    };
    const result = await runAction(
      'analysis/comment',
      payload,
      '评论',
      `analysis-comment:${candidateId}`,
    );
    if (!result) return null
    if (selectedProfileId.value === targetProfile) recordActivity('analysis_comment', result);
    invalidateProfileCache(targetProfile);
    return result
  }

  async function loadConversation() {
    const targetProfile = activeProfileScope();
    if (!targetProfile) return emptyConversation()
    return runOperation(
      'conversation',
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'conversation', { profile_id: targetProfile }) || emptyConversation();
        if (isCurrent() && selectedProfileId.value === targetProfile) conversation.value = result;
        return result
      },
      retryForProfile(targetProfile, loadConversation),
      { globalError: false },
    )
  }

  async function sendConversationMessage(content, idempotencyKey = requestId('conversation')) {
    const targetProfile = activeProfileScope();
    const payload = {
      profile_id: targetProfile,
      content,
      idempotency_key: idempotencyKey,
    };
    return runOperation(
      'conversation:send',
      async ({ isCurrent }) => {
        const result = await postPluginApi(api, 'conversation/messages', payload) || emptyConversation();
        if (isCurrent() && selectedProfileId.value === targetProfile) conversation.value = result;
        return result
      },
      retryForProfile(targetProfile, () => sendConversationMessage(content, idempotencyKey)),
      { globalError: false },
    )
  }

  async function retryConversationMessage(messageId) {
    const targetProfile = activeProfileScope();
    const payload = { profile_id: targetProfile, message_id: messageId };
    return runOperation(
      `conversation:retry:${messageId}`,
      async ({ isCurrent }) => {
        const result = await postPluginApi(api, 'conversation/messages/retry', payload) || emptyConversation();
        if (isCurrent() && selectedProfileId.value === targetProfile) conversation.value = result;
        return result
      },
      retryForProfile(targetProfile, () => retryConversationMessage(messageId)),
      { globalError: false },
    )
  }

  async function respondConversationCommand(commandId, action) {
    const targetProfile = activeProfileScope();
    const payload = { profile_id: targetProfile, command_id: commandId, action };
    const result = await runOperation(
      `conversation-command:${commandId}`,
      () => postPluginApi(api, 'conversation/commands/respond', payload),
      retryForProfile(targetProfile, () => respondConversationCommand(commandId, action)),
      { globalError: false },
    );
    if (selectedProfileId.value === targetProfile) {
      await Promise.allSettled([loadConversation(), loadPendingCenter()]);
    }
    invalidateProfileCache(targetProfile);
    return result
  }

  async function loadPendingCenter(view = 'pending') {
    const targetProfile = activeProfileScope();
    if (!targetProfile) return emptyPendingCenter()
    const scope = view === 'resolved' ? 'resolved' : 'pending';
    return runOperation(
      `pending:${scope}`,
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'pending', {
          profile_id: targetProfile,
          view: scope,
        }) || emptyPendingCenter(targetProfile);
        if (isCurrent() && selectedProfileId.value === targetProfile) {
          if (scope === 'resolved') processedCenter.value = result;
          else pendingCenter.value = result;
        }
        return result
      },
      retryForProfile(targetProfile, () => loadPendingCenter(scope)),
      { globalError: false },
    )
  }

  async function respondPending(item, action, options = {}) {
    const targetProfile = activeProfileScope();
    const payload = {
      profile_id: targetProfile,
      item_type: item?.item_type,
      item_id: item?.item_id,
      action,
      option_id: options.optionId || '',
      custom_answer: options.customAnswer || '',
      idempotency_key: options.idempotencyKey || requestId('pending'),
    };
    const key = `pending:${item?.item_type || 'item'}:${item?.item_id || 'unknown'}`;
    const result = await runOperation(
      key,
      () => postPluginApi(api, 'pending/respond', payload),
      retryForProfile(targetProfile, () => respondPending(item, action, { ...options, idempotencyKey: payload.idempotency_key })),
      { globalError: false },
    );
    if (selectedProfileId.value === targetProfile) {
      await Promise.allSettled([
        loadPendingCenter('pending'),
        loadPendingCenter('resolved'),
        loadConversation(),
      ]);
    }
    invalidateProfileCache(targetProfile);
    return result
  }

  async function loadAttribution() {
    const targetProfile = activeProfileScope();
    if (!targetProfile) return emptyAttribution()
    return runOperation(
      'attribution',
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'attribution', {
          profile_id: targetProfile,
        }) || emptyAttribution(targetProfile);
        if (isCurrent() && selectedProfileId.value === targetProfile) attribution.value = result;
        return result
      },
      retryForProfile(targetProfile, loadAttribution),
      { globalError: false },
    )
  }

  async function verifyAttribution() {
    const targetProfile = activeProfileScope();
    const payload = { profile_id: targetProfile };
    const result = await runOperation(
      'attribution:verify',
      () => postPluginApi(api, 'attribution/verify', payload),
      retryForProfile(targetProfile, verifyAttribution),
      { globalError: false },
    );
    if (selectedProfileId.value === targetProfile) await Promise.allSettled([loadAttribution()]);
    invalidateProfileCache(targetProfile);
    return result
  }

  async function loadDataExport() {
    const targetProfile = activeProfileScope();
    if (!targetProfile) return null
    return runOperation(
      'data:export',
      async ({ isCurrent }) => {
        const result = await getPluginApi(api, 'data/export', {
          profile_id: targetProfile,
        });
        if (isCurrent() && selectedProfileId.value === targetProfile) exportedData.value = result;
        return result
      },
      retryForProfile(targetProfile, loadDataExport),
      { globalError: false },
    )
  }

  function clearLearningViews() {
    Object.keys(analyses).forEach(key => delete analyses[key]);
    activity.value = [];
    conversation.value = emptyConversation();
    pendingCenter.value = emptyPendingCenter(selectedProfileId.value);
    processedCenter.value = { ...emptyPendingCenter(selectedProfileId.value), view: 'resolved' };
    attribution.value = emptyAttribution(selectedProfileId.value);
    exportedData.value = null;
    fullResetConfirmation.value = null;
  }

  async function resetLearning(confirm = false) {
    const targetProfile = activeProfileScope();
    const payload = { profile_id: targetProfile, confirm: confirm === true };
    const result = await runOperation(
      'data:reset-learning',
      () => postPluginApi(api, 'data/reset/learning', payload),
      retryForProfile(targetProfile, () => resetLearning(confirm)),
      { globalError: false },
    );
    if (selectedProfileId.value === targetProfile) clearLearningViews();
    sharedCache.profiles.delete(targetProfile);
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  async function prepareFullReset() {
    const targetProfile = activeProfileScope();
    const payload = { profile_id: targetProfile };
    return runOperation(
      'data:reset-full-prepare',
      async ({ isCurrent }) => {
        const result = await postPluginApi(api, 'data/reset/full/prepare', payload);
        if (isCurrent() && selectedProfileId.value === targetProfile) fullResetConfirmation.value = result;
        return result
      },
      retryForProfile(targetProfile, prepareFullReset),
      { globalError: false },
    )
  }

  async function resetFull(confirmationToken = '') {
    const targetProfile = activeProfileScope();
    const token = confirmationToken || fullResetConfirmation.value?.confirmation_token || '';
    const payload = {
      profile_id: targetProfile,
      confirmation_token: token,
    };
    const result = await runOperation(
      'data:reset-full',
      () => postPluginApi(api, 'data/reset/full', payload),
      retryForProfile(targetProfile, () => resetFull(token)),
      { globalError: false },
    );
    if (selectedProfileId.value === targetProfile) clearLearningViews();
    sharedCache.profiles.delete(targetProfile);
    await refreshProfileAfterMutation(targetProfile);
    return result
  }

  watch(selectedProfileId, value => ensureSecondaryScope(value), { flush: 'sync' });

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
    operations,
    analyses,
    activity,
    conversation,
    pendingCenter,
    processedCenter,
    attribution,
    exportedData,
    fullResetConfirmation,
    isRunning,
    operationState,
    clearOperationError,
    retryOperation,
    loadOptions,
    loadProfileData,
    loadHistory,
    refresh,
    archive,
    reactToRecommendation,
    restore,
    deleteArchive,
    clearProfile,
    updateProfileTag,
    subscribe,
    recordNativeDrawerOpened,
    currentAnalysis,
    loadAnalysis,
    commentOnAnalysis,
    loadConversation,
    sendConversationMessage,
    retryConversationMessage,
    respondConversationCommand,
    loadPendingCenter,
    respondPending,
    loadAttribution,
    verifyAttribution,
    loadDataExport,
    resetLearning,
    prepareFullReset,
    resetFull,
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
  emits: ['subscribe', 'archive', 'like', 'dislike', 'native-subscribe-opened'],
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
const likePressed = computed(() => props.item?.feedback_kind === 'like');
const dislikePressed = computed(() => props.item?.feedback_kind === 'dislike');
const likeLoading = computed(() => props.loadingAction === `feedback:like:${props.item?.candidate_id}`);
const dislikeLoading = computed(() => props.loadingAction === `feedback:dislike:${props.item?.candidate_id}`);
const actionBusy = computed(() => Boolean(props.loadingAction));

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
    if (result?.success === true) {
      emit('native-subscribe-opened', props.item?.candidate_id);
      return
    }
    if (result?.code === 'PERMISSION_DENIED') return
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
          disabled: actionBusy.value && __props.loadingAction !== 'subscribe',
          "aria-label": "订阅",
          onClick: handleSubscribe
        }), {
          default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "订阅", -1)
          ]))]),
          _: 1
        }, 16, ["size", "loading", "disabled"])
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
          default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
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
          disabled: actionBusy.value && __props.loadingAction !== 'archive',
          "aria-label": "忽略",
          onClick: _cache[0] || (_cache[0] = $event => (emit('archive', __props.item.candidate_id)))
        }), {
          default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "忽略", -1)
          ]))]),
          _: 1
        }, 16, ["size", "loading", "disabled"])
      ]),
      _: 1
    }),
    _createVNode(_component_VTooltip, {
      text: likePressed.value ? '已点赞' : '点赞',
      location: "top"
    }, {
      activator: _withCtx(({ props: tooltipProps }) => [
        _createVNode(_component_VBtn, _mergeProps(tooltipProps, {
          size: __props.size,
          variant: "tonal",
          color: likePressed.value ? 'primary' : 'default',
          class: "ar-actions__button text-none",
          "prepend-icon": likePressed.value ? 'mdi-thumb-up' : 'mdi-thumb-up-outline',
          loading: likeLoading.value,
          disabled: actionBusy.value && !likeLoading.value,
          "aria-label": likePressed.value ? '已点赞' : '点赞',
          "aria-pressed": likePressed.value ? 'true' : 'false',
          onClick: _cache[1] || (_cache[1] = $event => (emit('like', __props.item.candidate_id)))
        }), {
          default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "点赞", -1)
          ]))]),
          _: 1
        }, 16, ["size", "color", "prepend-icon", "loading", "disabled", "aria-label", "aria-pressed"])
      ]),
      _: 1
    }, 8, ["text"]),
    _createVNode(_component_VTooltip, {
      text: dislikePressed.value ? '已点踩' : '点踩',
      location: "top"
    }, {
      activator: _withCtx(({ props: tooltipProps }) => [
        _createVNode(_component_VBtn, _mergeProps(tooltipProps, {
          size: __props.size,
          variant: "tonal",
          color: dislikePressed.value ? 'primary' : 'default',
          class: "ar-actions__button text-none",
          "prepend-icon": dislikePressed.value ? 'mdi-thumb-down' : 'mdi-thumb-down-outline',
          loading: dislikeLoading.value,
          disabled: actionBusy.value && !dislikeLoading.value,
          "aria-label": dislikePressed.value ? '已点踩' : '点踩',
          "aria-pressed": dislikePressed.value ? 'true' : 'false',
          onClick: _cache[2] || (_cache[2] = $event => (emit('dislike', __props.item.candidate_id)))
        }), {
          default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
            _createElementVNode("span", { class: "ar-actions__label" }, "点踩", -1)
          ]))]),
          _: 1
        }, 16, ["size", "color", "prepend-icon", "loading", "disabled", "aria-label", "aria-pressed"])
      ]),
      _: 1
    }, 8, ["text"])
  ], 8, _hoisted_1))
}
}

};
const RecommendationActions = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ed420796"]]);

export { RecommendationActions as R, useAgentRankState as u };
