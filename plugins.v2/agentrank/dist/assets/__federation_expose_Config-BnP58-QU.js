import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-BGNRvR24.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,createBlock:_createBlock,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "ar-config" };
const _hoisted_2 = { class: "ar-config__header-state" };
const _hoisted_3 = { class: "ar-config__body" };
const _hoisted_4 = {
  class: "ar-config__nav",
  "aria-label": "Agent榜单配置导航"
};
const _hoisted_5 = { class: "ar-config__content" };
const _hoisted_6 = { class: "ar-config__subtabs" };
const _hoisted_7 = {
  key: 0,
  class: "ar-config__subtab ar-config__subtab--active",
  type: "button"
};
const _hoisted_8 = ["onClick"];
const _hoisted_9 = { class: "ar-config__pane ar-config__pane--overview" };
const _hoisted_10 = { class: "ar-config__pipeline" };
const _hoisted_11 = { class: "ar-config__step-copy" };
const _hoisted_12 = { class: "ar-config__overview-grid" };
const _hoisted_13 = { class: "ar-config__overview-panel" };
const _hoisted_14 = { class: "ar-config__panel-head" };
const _hoisted_15 = { class: "ar-config__stats" };
const _hoisted_16 = { class: "ar-config__hint" };
const _hoisted_17 = { class: "ar-config__overview-panel" };
const _hoisted_18 = { class: "ar-config__panel-head" };
const _hoisted_19 = { class: "ar-config__hint" };
const _hoisted_20 = { class: "ar-config__tag-row" };
const _hoisted_21 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_22 = { class: "ar-config__overview-panel" };
const _hoisted_23 = { class: "ar-config__panel-head" };
const _hoisted_24 = { class: "ar-config__metric-list" };
const _hoisted_25 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_26 = { class: "ar-config__overview-panel" };
const _hoisted_27 = { class: "ar-config__panel-head" };
const _hoisted_28 = { class: "ar-config__metric-columns" };
const _hoisted_29 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_30 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_31 = {
  key: 0,
  class: "ar-config__source-errors"
};
const _hoisted_32 = { class: "ar-config__overview-foot" };
const _hoisted_33 = { class: "ar-config__pane" };
const _hoisted_34 = { class: "ar-config__pane" };
const _hoisted_35 = { class: "d-flex align-center mb-3" };
const _hoisted_36 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_37 = { class: "mt-1" };
const _hoisted_38 = {
  key: 0,
  class: "text-caption mt-1"
};
const _hoisted_39 = { class: "text-caption mb-1" };
const _hoisted_40 = { class: "ar-config__pane" };
const _hoisted_41 = { class: "ar-config__source-grid" };
const _hoisted_42 = { class: "ar-config__pane" };
const _hoisted_43 = { class: "ar-config__weight-grid" };
const _hoisted_44 = { class: "d-flex align-center mb-1" };
const _hoisted_45 = { class: "text-body-2 font-weight-medium" };
const _hoisted_46 = { class: "ar-config__default" };
const _hoisted_47 = { class: "ar-config__pane" };
const _hoisted_48 = { class: "text-caption mb-1" };
const _hoisted_49 = { class: "ar-config__pane" };
const _hoisted_50 = { class: "ar-config__pane" };
const _hoisted_51 = { class: "ar-config__danger-row mt-4" };
const _hoisted_52 = { class: "ar-config__hint" };
const _hoisted_53 = { class: "d-flex align-center mb-3" };

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const weightDefaults = {
  type_weight: 0.8,
  theme_weight: 0.8,
  actor_weight: 0.5,
  director_weight: 0.4,
  region_weight: 0.4,
  year_weight: 0.3,
  rating_weight: 0.7,
  heat_weight: 0.6,
  freshness_weight: 0.5,
  similarity_weight: 0.8,
};

const defaults = {
  enabled: false,
  discovery_page_enabled: true,
  onlyonce: false,
  schedule_enabled: false,
  cron: '0 8 * * *',
  emby_identities: [],
  default_profile_id: '',
  emby_library_ids: null,
  discovery_sources: {
    douban: true,
    tmdb_movies: true,
    tmdb_tv: true,
    bangumi: true,
    anilist: true,
  },
  weights: { ...weightDefaults },
  media_types: ['movie', 'tv', 'anime'],
  minimum_samples: 5,
  candidate_pool_size: 50,
  confidence_threshold: 0.6,
  exclude_keywords: [],
  action_mode: 'notify',
  notify: true,
  auto_subscribe_top_n: 0,
  auto_subscribe_limit: 10,
  history_limit: 50,
  profile_cache_enabled: true,
  rebuild_profile_each_run: false,
  playback_enabled: true,
  playback_recent_days: 60,
  playback_completion_threshold: 0.85,
  playback_abandon_minutes: 20,
  playback_cache_days: 7,
  agent_prompt: '以用户真实播放记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要点明用户偏好与作品题材、主创、地区、年代或风格之间的具体联系，避免空泛夸赞。',
};

const form = reactive(structuredClone(defaults));
const activeMain = ref('overview');
const activeAdvanced = ref('runtime');
const loading = ref(false);
const status = ref({ state: 'stopped', validation_errors: [], playback: null, enablement: null });
const overview = ref(null);
const availableIdentities = ref([]);
const availableLibraries = ref({});
const sourceOptions = ref([]);
const loadError = ref('');
const runtimeDefaults = ref(structuredClone(defaults));
const clearProfileSwitch = ref(false);
const clearProfileDialog = ref(false);
const clearProfileLoading = ref(false);
const actionFeedback = reactive({ show: false, message: '', color: 'success' });

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '选择 Emby 服务实例、用户、内容库和运行周期。' },
  { key: 'playback', title: '播放画像', icon: 'mdi-play-circle-outline', desc: 'Playback Reporting 是插件运行的强制依赖。' },
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline', desc: '选择 MoviePilot 内置发现来源。' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical', desc: '设置 Agent 排序时十项偏好权重。' },
  { key: 'filter', title: '条件筛选', icon: 'mdi-filter-outline', desc: '限制媒体类型、候选数量和置信度。' },
  { key: 'board', title: '榜单行为', icon: 'mdi-format-list-numbered', desc: '选择仅更新、通知确认或自动订阅。' },
  { key: 'advanced', title: '高级选项', icon: 'mdi-shield-check-outline', desc: '管理画像重建、历史上限和安全边界。' },
];

const weightDefs = [
  { key: 'type_weight', title: '媒体类型', icon: 'mdi-movie-open-outline' },
  { key: 'theme_weight', title: '题材主题', icon: 'mdi-tag-multiple-outline' },
  { key: 'actor_weight', title: '演员偏好', icon: 'mdi-account-star-outline' },
  { key: 'director_weight', title: '导演偏好', icon: 'mdi-chair-rolling' },
  { key: 'region_weight', title: '地区偏好', icon: 'mdi-earth' },
  { key: 'year_weight', title: '年代偏好', icon: 'mdi-calendar-range' },
  { key: 'rating_weight', title: '口碑评分', icon: 'mdi-star-outline' },
  { key: 'heat_weight', title: '当前热度', icon: 'mdi-fire' },
  { key: 'freshness_weight', title: '新鲜程度', icon: 'mdi-sprout-outline' },
  { key: 'similarity_weight', title: '画像相似', icon: 'mdi-vector-link' },
];

const sourceMeta = {
  douban: { title: '豆瓣发现', subtitle: '热门电影、剧集与动画', icon: 'mdi-alpha-d-circle-outline' },
  tmdb_movies: { title: 'TMDB电影', subtitle: '高热度电影候选', icon: 'mdi-movie-open-star-outline' },
  tmdb_tv: { title: 'TMDB剧集', subtitle: '高热度剧集候选', icon: 'mdi-television-classic' },
  bangumi: { title: 'Bangumi', subtitle: '动画与番剧候选', icon: 'mdi-animation-outline' },
  anilist: { title: 'AniList', subtitle: '趋势动画与本季热门', icon: 'mdi-alpha-a-circle-outline' },
};

const mediaTypeOptions = [
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
  { title: '动漫', value: 'anime' },
];
const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知内选择', value: 'notify' },
  { title: '自动订阅前几名', value: 'auto_subscribe' },
];
const advancedTabs = [
  { key: 'runtime', title: '运行设置', icon: 'mdi-cog-outline' },
  { key: 'prompt', title: '提示设置', icon: 'mdi-text-box-edit-outline' },
];

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
const selectedProfileId = computed(() => form.default_profile_id || form.emby_identities[0]?.profile_id || '');
const selectedIdentity = computed(() => form.emby_identities.find(identity => identity.profile_id === selectedProfileId.value) || null);
const serverOptions = computed(() => {
  const names = [...new Set(availableIdentities.value.map(identity => identity.server_name).filter(Boolean))];
  return names.map(name => ({ title: name, value: name }))
});
const selectedServerName = computed({
  get: () => selectedIdentity.value?.server_name || '',
  set: serverName => {
    const identity = availableIdentities.value.find(item => item.server_name === serverName);
    form.emby_identities = identity ? [identity] : [];
    form.default_profile_id = identity?.profile_id || '';
  },
});
const userOptions = computed(() => availableIdentities.value
  .filter(identity => identity.server_name === selectedServerName.value)
  .map(identity => ({ title: identity.username, value: identity.profile_id })));
const selectedUserProfileId = computed({
  get: () => selectedProfileId.value,
  set: profileId => {
    const identity = availableIdentities.value.find(item => item.profile_id === profileId);
    form.emby_identities = identity ? [identity] : [];
    form.default_profile_id = identity?.profile_id || '';
    if (identity && !Object.prototype.hasOwnProperty.call(form.emby_library_ids || {}, identity.profile_id)) {
      form.emby_library_ids = { ...(form.emby_library_ids || {}), [identity.profile_id]: (availableLibraries.value[identity.profile_id] || []).map(item => item.id) };
    }
    loadOverview(identity?.profile_id || '');
  },
});
const libraryOptions = computed(() => (availableLibraries.value[selectedProfileId.value] || []).map(item => ({
  title: item.name,
  value: item.id,
})));
const selectedLibraryIds = computed({
  get: () => {
    const profileId = selectedProfileId.value;
    if (!profileId) return []
    if (Object.prototype.hasOwnProperty.call(form.emby_library_ids || {}, profileId)) return form.emby_library_ids[profileId] || []
    return libraryOptions.value.map(item => item.value)
  },
  set: libraryIds => {
    if (!selectedProfileId.value) return
    form.emby_library_ids = { ...(form.emby_library_ids || {}), [selectedProfileId.value]: [...(libraryIds || [])] };
  },
});
const latestMetrics = computed(() => overview.value?.latest_run?.metrics || {});
const currentPlayback = computed(() => overview.value?.playback || status.value.playback || null);
const currentEnablement = computed(() => overview.value?.enablement || status.value.enablement || null);
const runtimeStateText = computed(() => ({ ready: '运行中', blocked: '已阻断', stopped: '已停用' })[status.value.state] || status.value.state || '未知');
const runtimeStateColor = computed(() => ({ ready: 'success', blocked: 'error', stopped: 'default' })[status.value.state] || 'warning');
const playbackMappingRate = computed(() => {
  const mapped = Number(currentPlayback.value?.mapped_count || 0);
  const total = mapped + Number(currentPlayback.value?.unmapped_count || 0);
  return total ? `${Math.round((mapped / total) * 100)}%` : '-'
});
const candidateSourceEntries = computed(() => Object.entries(latestMetrics.value.candidate_source_counts || {}).map(([key, value]) => [sourceLabel(key), value]));
const candidateExclusionEntries = computed(() => Object.entries(latestMetrics.value.candidate_exclusion_counts || {}).map(([key, value]) => [exclusionLabel(key), value]));
const sourceErrorEntries = computed(() => Object.entries(latestMetrics.value.source_errors || {}));
const sourceErrorsText = computed(() => sourceErrorEntries.value.map(([key, value]) => `${sourceLabel(key)}：${value}`).join('；'));
const retrievalFilterEntries = computed(() => Object.entries(overview.value?.profile?.filters || {}).map(([key, value]) => [filterLabel(key), formatFilterValue(key, value)]));
const pipelineSteps = [
  { key: 'probe', title: '探测依赖' },
  { key: 'playback_snapshot', title: '冻结播放' },
  { key: 'profile', title: '生成画像' },
  { key: 'candidate', title: '冻结候选' },
  { key: 'ranking', title: '池内排序' },
  { key: 'save', title: '校验保存' },
];

const sourceDefs = computed(() => {
  const runtimeOptions = sourceOptions.value.filter(item => item && item.available !== false);
  const keys = runtimeOptions.length
    ? runtimeOptions.map(item => item.key)
    : Object.keys(defaults.discovery_sources);
  return keys.map(key => ({
    key,
    ...(sourceMeta[key] || {
      title: key,
      subtitle: 'MoviePilot 来源',
      icon: 'mdi-database-outline',
    }),
  }))
});

function displayValue(value) {
  if (Array.isArray(value)) return value.join('、') || '无'
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}:${item}`).join('、') || '无'
  return String(value ?? '') || '无'
}

const stageLabels = {
  ready: '已就绪', generated: '已生成', reused: '已复用', cached: '已缓存', saved: '已保存', success: '已完成', pending: '等待中', running: '运行中', stopped: '已停止', disabled: '已停用',
  playback_unavailable: '播放数据不可用', emby_unavailable: 'Emby 不可用', permission_error: '权限不足', transient_error: '临时错误', unavailable: '不可用', configuration_error: '配置错误',
  sample_insufficient: '播放样本不足', candidate_insufficient: '候选数量不足', recommendation_incomplete: '推荐榜单不足',
  profile_agent_failed: '画像 Agent 调用失败', profile_validation_failed: '画像输出校验失败', profile_save_failed: '画像保存失败',
  candidate_failed: '候选采集失败', candidate_filter_failed: '候选过滤失败', candidate_snapshot_failed: '候选快照失败',
  ranking_agent_failed: '排序 Agent 调用失败', ranking_validation_failed: '排序输出校验失败', ranking_save_failed: '榜单保存失败',
  subscription_partial_failed: '部分订阅失败', validation_failed: '输出校验失败', agent_failed: 'Agent 调用失败', failed: '失败', blocked: '已阻断',
};
const filterLabels = {
  media_types: '媒体类型',
  genre_ids: '题材',
  genres: '题材',
  keyword_ids: '关键词',
  original_languages: '语言',
  languages: '语言',
  year_min: '最早年份',
  year_max: '最晚年份',
  release_year_min: '最早年份',
  release_year_max: '最晚年份',
  rating_min: '最低评分',
  vote_count_min: '最低票数',
  sort_by: '排序方式',
};
const sourceLabels = { douban: '豆瓣发现', tmdb: 'TMDB', tmdb_recommend: 'TMDB 推荐', tmdb_movies: 'TMDB 电影', tmdb_tv: 'TMDB 剧集', bangumi: 'Bangumi', anilist: 'AniList' };
const exclusionLabels = { invalid_or_unrecognized: '无效或未识别', watched: '已观看', watched_completed: '已看完', library: '已入库', subscribed: '已订阅', archived: '已忽略', negative_keyword: '排除关键词' };
const mediaTypeLabels = { movie: '电影', tv: '剧集', anime: '动漫' };
const languageLabels = { zh: '中文', ja: '日语', ko: '韩语', en: '英语', fr: '法语', de: '德语', es: '西班牙语', it: '意大利语', ru: '俄语', th: '泰语' };
const sortLabels = { 'popularity.desc': '热度降序', 'vote_average.desc': '评分降序', 'primary_release_date.desc': '上映日期降序', 'first_air_date.desc': '首播日期降序' };
function sourceLabel(value) { return sourceLabels[value] || value }
function exclusionLabel(value) { return exclusionLabels[value] || value }
function filterLabel(value) { return filterLabels[value] || value }
function formatFilterValue(key, value) {
  if (key === 'media_types' && Array.isArray(value)) return value.map(item => mediaTypeLabels[item] || item)
  if ((key === 'original_languages' || key === 'languages') && Array.isArray(value)) return value.map(item => languageLabels[item] || item)
  if (key === 'sort_by') return sortLabels[value] || value
  return value
}
function formatDateTime(value) {
  if (!value) return '尚未同步'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function stageStatus(step) {
  const value = latestMetrics.value.stage_status?.[step.key] || '';
  return stageLabels[value] || value
}

function stageDuration(step) {
  const value = Number(latestMetrics.value.stage_ms?.[step.key]);
  if (!Number.isFinite(value) || value < 0) return ''
  if (value < 1000) return `${Math.round(value)} 毫秒`
  return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)} 秒`
}

function runStatusText(value) { return stageLabels[value] || value || '未知' }

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

function applyConfig(value) {
  const next = cloneConfig(value);
  Object.assign(form, cloneConfig(defaults), next);
  form.playback_enabled = true;
  form.weights = { ...weightDefaults, ...(next.weights || {}) };
  const sourceKeys = new Set([
    ...Object.keys(defaults.discovery_sources),
    ...Object.keys(next.discovery_sources || {}),
    ...sourceOptions.value.map(item => item.key),
  ]);
  form.discovery_sources = Object.fromEntries(
    [...sourceKeys].map(key => [
      key,
      Boolean(next.discovery_sources?.[key] ?? defaults.discovery_sources[key] ?? false),
    ]),
  );
  form.emby_identities = Array.isArray(next.emby_identities)
    ? next.emby_identities.filter(identity => identity?.profile_id)
    : [];
  form.default_profile_id = next.default_profile_id || form.emby_identities[0]?.profile_id || '';
  form.emby_library_ids = next.emby_library_ids && typeof next.emby_library_ids === 'object'
    ? cloneConfig(next.emby_library_ids)
    : {};
  form.media_types = Array.isArray(next.media_types) ? [...next.media_types] : [...defaults.media_types];
  form.exclude_keywords = Array.isArray(next.exclude_keywords) ? [...next.exclude_keywords] : [];
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true });
async function loadOverview(profileId = selectedProfileId.value) {
  if (!props.api?.get || !profileId) {
    overview.value = null;
    return
  }
  overview.value = await getPluginApi(props.api, 'overview', { profile_id: profileId });
}

async function loadRuntime() {
  if (!props.api?.get) return
  loading.value = true;
  loadError.value = '';
  try {
    const [statusData, optionsData] = await Promise.all([
      getPluginApi(props.api, 'status'),
      getPluginApi(props.api, 'config/options'),
    ]);
    status.value = statusData || status.value;
    availableIdentities.value = Array.isArray(optionsData?.emby_identities) ? optionsData.emby_identities : [];
    availableLibraries.value = optionsData?.emby_libraries && typeof optionsData.emby_libraries === 'object' ? optionsData.emby_libraries : {};
    sourceOptions.value = Array.isArray(optionsData?.source_options) ? optionsData.source_options : [];
    runtimeDefaults.value = { ...structuredClone(defaults), ...(optionsData?.defaults || {}) };
    applyConfig(optionsData?.config || props.initialConfig);
    await loadOverview(optionsData?.default_profile_id || selectedProfileId.value);
  } catch (error) {
    loadError.value = error?.message || '运行信息加载失败';
  } finally {
    loading.value = false;
  }
}

function saveConfig() {
  const payload = cloneConfig(form);
  delete payload._validation_errors;
  emit('save', payload);
}

async function syncPlayback() {
  if (!props.api?.post || !selectedProfileId.value) return
  loading.value = true;
  try {
    const snapshot = await postPluginApi(props.api, 'playback/sync', { profile_id: selectedProfileId.value });
    status.value = { ...status.value, playback: snapshot };
    await loadOverview(selectedProfileId.value);
    actionFeedback.show = true;
    actionFeedback.color = snapshot?.status === 'ready' || snapshot?.status === 'cached' ? 'success' : 'warning';
    actionFeedback.message = snapshot?.message || '播放画像同步完成';
  } catch (error) {
    actionFeedback.show = true;
    actionFeedback.color = 'error';
    actionFeedback.message = error?.message || '播放画像同步失败';
  } finally {
    loading.value = false;
  }
}

function playbackStatusText(snapshot) {
  const labels = {
    idle: '尚未同步',
    ready: '已就绪',
    cached: '使用最近快照',
    not_installed: '未安装 Playback Reporting',
    permission_error: 'Playback Reporting 权限不足',
    transient_error: '服务暂时不可用',
    emby_unavailable: 'Emby 服务不可用',
  };
  return labels[snapshot?.status] || snapshot?.status || '尚未同步'
}

function restoreAgentPrompt() {
  form.agent_prompt = runtimeDefaults.value.agent_prompt || defaults.agent_prompt;
}

function requestClearProfile(value) {
  if (!value) return
  if (!selectedProfileId.value) {
    clearProfileSwitch.value = false;
    actionFeedback.show = true;
    actionFeedback.color = 'warning';
    actionFeedback.message = '请先选择默认 Emby 画像身份';
    return
  }
  clearProfileDialog.value = true;
}

function cancelClearProfile() {
  clearProfileDialog.value = false;
  clearProfileSwitch.value = false;
}

async function confirmClearProfile() {
  clearProfileLoading.value = true;
  try {
    await postPluginApi(props.api, 'profile/clear', { profile_id: selectedProfileId.value, confirm: true });
    actionFeedback.color = 'success';
    actionFeedback.message = `${selectedIdentity.value?.username || selectedProfileId.value} 的画像与榜单已清除`;
    await loadOverview(selectedProfileId.value);
  } catch (error) {
    actionFeedback.color = 'error';
    actionFeedback.message = error?.message || '清除画像失败';
  } finally {
    actionFeedback.show = true;
    clearProfileLoading.value = false;
    clearProfileDialog.value = false;
    clearProfileSwitch.value = false;
  }
}

onMounted(loadRuntime);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VAutocomplete = _resolveComponent("VAutocomplete");
  const _component_VCronField = _resolveComponent("VCronField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSlider = _resolveComponent("VSlider");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "ar-config__card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "ar-config__header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-brain",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_VChip, {
                color: runtimeStateColor.value,
                variant: "tonal",
                size: "small"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(runtimeStateText.value), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode(_component_VSwitch, {
                modelValue: form.enabled,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
                color: "success",
                "hide-details": "",
                inset: "",
                label: "启用插件"
              }, null, 8, ["modelValue"])
            ])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                _createTextVNode("Agent榜单中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, null, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(currentMain.value.desc), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_3, [
          _createElementVNode("nav", _hoisted_4, [
            _createVNode(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "ar-config__nav-list py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(mainTabs, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeMain.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    class: "ar-config__nav-item",
                    onClick: $event => (activeMain.value = item.key)
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["active", "onClick"])
                }), 64))
              ]),
              _: 1
            })
          ]),
          _createElementVNode("section", _hoisted_5, [
            _createElementVNode("div", _hoisted_6, [
              (activeMain.value !== 'advanced')
                ? (_openBlock(), _createElementBlock("button", _hoisted_7, [
                    _createVNode(_component_VIcon, {
                      icon: currentMain.value.icon,
                      size: "18",
                      class: "mr-1"
                    }, null, 8, ["icon"]),
                    _createTextVNode(_toDisplayString(currentMain.value.title), 1)
                  ]))
                : _createCommentVNode("", true),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(activeMain.value === 'advanced' ? advancedTabs : [], (item) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: item.key,
                  class: _normalizeClass(["ar-config__subtab", { 'ar-config__subtab--active': activeAdvanced.value === item.key }]),
                  type: "button",
                  onClick: $event => (activeAdvanced.value = item.key)
                }, [
                  _createVNode(_component_VIcon, {
                    icon: item.icon,
                    size: "18",
                    class: "mr-1"
                  }, null, 8, ["icon"]),
                  _createTextVNode(_toDisplayString(item.title), 1)
                ], 10, _hoisted_8))
              }), 128))
            ]),
            _createVNode(_component_VDivider),
            _createElementVNode("div", {
              class: _normalizeClass(["ar-config__window", { 'ar-config__window--overview': activeMain.value === 'overview' }])
            }, [
              _withDirectives(_createElementVNode("div", _hoisted_9, [
                _cache[42] || (_cache[42] = _createElementVNode("div", { class: "ar-config__section-title" }, "运行链路步骤", -1)),
                _createElementVNode("div", _hoisted_10, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(pipelineSteps, (step, index) => {
                    return _createElementVNode("div", {
                      key: step.key,
                      class: "ar-config__step"
                    }, [
                      _createVNode(_component_VAvatar, {
                        size: "28",
                        color: "primary",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(index + 1), 1)
                        ]),
                        _: 2
                      }, 1024),
                      _createElementVNode("div", _hoisted_11, [
                        _createElementVNode("span", null, _toDisplayString(step.title), 1),
                        _createElementVNode("small", null, [
                          _createTextVNode(_toDisplayString(stageStatus(step) || '待运行'), 1),
                          (stageDuration(step))
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                _createTextVNode(" · " + _toDisplayString(stageDuration(step)), 1)
                              ], 64))
                            : _createCommentVNode("", true)
                        ])
                      ])
                    ])
                  }), 64))
                ]),
                (currentEnablement.value && !currentEnablement.value.allowed && currentEnablement.value.status !== 'disabled')
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      density: "compact",
                      class: "mt-3",
                      icon: "mdi-alert-octagon-outline"
                    }, {
                      default: _withCtx(() => [
                        _cache[30] || (_cache[30] = _createElementVNode("strong", null, "Playback Reporting 硬依赖未满足", -1)),
                        _createTextVNode("：" + _toDisplayString(currentEnablement.value.message || '插件无法启用'), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_12, [
                  _createElementVNode("div", _hoisted_13, [
                    _createElementVNode("div", _hoisted_14, [
                      _cache[31] || (_cache[31] = _createElementVNode("span", null, "播放样本", -1)),
                      _createVNode(_component_VChip, {
                        color: ['ready', 'cached'].includes(currentPlayback.value?.status) ? 'success' : 'warning',
                        variant: "tonal",
                        size: "x-small"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(playbackStatusText(currentPlayback.value)), 1)
                        ]),
                        _: 1
                      }, 8, ["color"])
                    ]),
                    _createElementVNode("div", _hoisted_15, [
                      _createElementVNode("span", null, [
                        _cache[32] || (_cache[32] = _createTextVNode("样本 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.sample_count || 0), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[33] || (_cache[33] = _createTextVNode("映射 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.mapped_count || 0), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[34] || (_cache[34] = _createTextVNode("映射率 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(playbackMappingRate.value), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[35] || (_cache[35] = _createTextVNode("未映射 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.unmapped_count || 0), 1)
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_16, _toDisplayString(selectedIdentity.value?.username || '未选择用户') + " · " + _toDisplayString(formatDateTime(currentPlayback.value?.synced_at)), 1)
                  ]),
                  _createElementVNode("div", _hoisted_17, [
                    _createElementVNode("div", _hoisted_18, [
                      _cache[36] || (_cache[36] = _createElementVNode("span", null, "画像版本", -1)),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "outlined"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("结构 " + _toDisplayString(overview.value?.profile?.schema_version || '-'), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _createElementVNode("div", _hoisted_19, "检索解析版本 " + _toDisplayString(overview.value?.profile?.retrieval_resolution_version || '-') + " · 播放证据 " + _toDisplayString(overview.value?.profile?.playback_count || 0) + " 条", 1),
                    _createElementVNode("div", _hoisted_20, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overview.value?.profile?.ranking_tags || [], (tag) => {
                        return (_openBlock(), _createBlock(_component_VChip, {
                          key: tag,
                          size: "x-small",
                          variant: "tonal",
                          color: "primary"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(tag), 1)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128)),
                      (!(overview.value?.profile?.ranking_tags || []).length)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_21, "暂无排序标签"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_22, [
                    _createElementVNode("div", _hoisted_23, [
                      _cache[37] || (_cache[37] = _createElementVNode("span", null, "检索计划", -1)),
                      _createElementVNode("small", null, _toDisplayString(retrievalFilterEntries.value.length) + " 项过滤", 1)
                    ]),
                    _createElementVNode("div", _hoisted_24, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(retrievalFilterEntries.value, ([key, value]) => {
                        return (_openBlock(), _createElementBlock("span", { key: key }, [
                          _createElementVNode("b", null, _toDisplayString(key), 1),
                          _createTextVNode(_toDisplayString(displayValue(value)), 1)
                        ]))
                      }), 128)),
                      (!retrievalFilterEntries.value.length)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_25, "暂无已解析过滤条件"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_26, [
                    _createElementVNode("div", _hoisted_27, [
                      _cache[38] || (_cache[38] = _createElementVNode("span", null, "冻结候选", -1)),
                      _createElementVNode("small", null, _toDisplayString(latestMetrics.value.candidate_count || 0) + " 项", 1)
                    ]),
                    _createElementVNode("div", _hoisted_28, [
                      _createElementVNode("div", null, [
                        _cache[39] || (_cache[39] = _createElementVNode("small", null, "候选来源", -1)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidateSourceEntries.value, ([key, value]) => {
                          return (_openBlock(), _createElementBlock("span", { key: key }, [
                            _createTextVNode(_toDisplayString(key) + " ", 1),
                            _createElementVNode("b", null, _toDisplayString(value), 1)
                          ]))
                        }), 128)),
                        (!candidateSourceEntries.value.length)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_29, "暂无统计"))
                          : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("div", null, [
                        _cache[40] || (_cache[40] = _createElementVNode("small", null, "排除统计", -1)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidateExclusionEntries.value, ([key, value]) => {
                          return (_openBlock(), _createElementBlock("span", { key: key }, [
                            _createTextVNode(_toDisplayString(key) + " ", 1),
                            _createElementVNode("b", null, _toDisplayString(value), 1)
                          ]))
                        }), 128)),
                        (!candidateExclusionEntries.value.length)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_30, "暂无统计"))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    (sourceErrorEntries.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_31, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-alert-circle-outline",
                            size: "15",
                            color: "warning"
                          }),
                          _createElementVNode("span", null, _toDisplayString(sourceErrorsText.value), 1)
                        ]))
                      : _createCommentVNode("", true)
                  ])
                ]),
                (loadError.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 1,
                      type: "error",
                      variant: "tonal",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(loadError.value), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                (status.value.validation_errors?.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 2,
                      type: "warning",
                      variant: "tonal",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.validation_errors, (item) => {
                          return (_openBlock(), _createElementBlock("div", { key: item }, _toDisplayString(item), 1))
                        }), 128))
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_32, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-shield-refresh-outline",
                    size: "17",
                    color: "primary"
                  }),
                  _cache[41] || (_cache[41] = _createElementVNode("span", null, "Agent、候选或保存失败时保留旧画像与旧榜单，不执行订阅。", -1)),
                  (overview.value?.latest_run?.status)
                    ? (_openBlock(), _createBlock(_component_VChip, {
                        key: 0,
                        size: "x-small",
                        variant: "outlined"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("最近运行 " + _toDisplayString(runStatusText(overview.value.latest_run.status)), 1)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode("", true)
                ])
              ], 512), [
                [_vShow, activeMain.value === 'overview']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_33, [
                _cache[44] || (_cache[44] = _createElementVNode("div", { class: "ar-config__section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: selectedServerName.value,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((selectedServerName).value = $event)),
                          items: serverOptions.value,
                          label: "媒体库（Emby 服务实例）",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "items"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: selectedUserProfileId.value,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((selectedUserProfileId).value = $event)),
                          items: userOptions.value,
                          label: "用户",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !selectedServerName.value
                        }, null, 8, ["modelValue", "items", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VAutocomplete, {
                          modelValue: selectedLibraryIds.value,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((selectedLibraryIds).value = $event)),
                          items: libraryOptions.value,
                          label: "内容库筛选",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !selectedUserProfileId.value
                        }, null, 8, ["modelValue", "items", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.onlyonce,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.onlyonce) = $event)),
                          color: "warning",
                          label: "立即运行一次",
                          "hide-details": "",
                          inset: "",
                          disabled: !form.enabled || !form.emby_identities.length || currentEnablement.value?.allowed === false
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.schedule_enabled,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.schedule_enabled) = $event)),
                          color: "success",
                          label: "周期运行",
                          "hide-details": "",
                          inset: ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCronField, {
                          modelValue: form.cron,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.cron) = $event)),
                          label: "运行周期",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: !form.schedule_enabled
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                    _createTextVNode("Emby 画像身份由服务实例与用户组成；画像只同步所选用户在所选内容库中的 Playback Reporting 记录，未安装或不可访问时插件保持停用。", -1)
                  ]))]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_34, [
                _createElementVNode("div", _hoisted_35, [
                  _cache[46] || (_cache[46] = _createElementVNode("div", { class: "ar-config__section-title mb-0" }, "播放画像", -1)),
                  _createVNode(_component_VSpacer),
                  _createVNode(_component_VBtn, {
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-sync",
                    loading: loading.value,
                    disabled: !form.enabled || !selectedProfileId.value,
                    onClick: syncPlayback
                  }, {
                    default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                      _createTextVNode("同步数据", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled"])
                ]),
                _createVNode(_component_VAlert, {
                  type: ['ready', 'cached'].includes(currentPlayback.value?.status) ? 'success' : currentEnablement.value?.allowed === false ? 'error' : 'info',
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_36, [
                      _createElementVNode("strong", null, _toDisplayString(playbackStatusText(currentPlayback.value)), 1),
                      (currentPlayback.value?.source)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 0,
                            size: "x-small",
                            variant: "outlined"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(currentPlayback.value.source), 1)
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode("", true),
                      (currentPlayback.value?.confidence)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 1,
                            size: "x-small",
                            variant: "outlined"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(currentPlayback.value.confidence), 1)
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode("", true)
                    ]),
                    _createElementVNode("div", _hoisted_37, _toDisplayString(currentEnablement.value?.message || currentPlayback.value?.message || 'Playback Reporting 是硬依赖；未安装或无权限时插件无法开启。'), 1),
                    (currentPlayback.value?.synced_at)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_38, "最近同步：" + _toDisplayString(formatDateTime(currentPlayback.value.synced_at)) + " · 样本 " + _toDisplayString(currentPlayback.value.sample_count || 0) + " · 已映射 " + _toDisplayString(currentPlayback.value.mapped_count || 0) + " · 未映射 " + _toDisplayString(currentPlayback.value.unmapped_count || 0), 1))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }, 8, ["type"]),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.playback_recent_days,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.playback_recent_days) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "3650",
                          label: "回溯天数",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.playback_abandon_minutes,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.playback_abandon_minutes) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "240",
                          label: "弃看分钟",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.playback_cache_days,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.playback_cache_days) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "1",
                          max: "30",
                          label: "快照天数",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_39, "完播阈值 " + _toDisplayString(Math.round(form.playback_completion_threshold * 100)) + "%", 1),
                        _createVNode(_component_VSlider, {
                          modelValue: form.playback_completion_threshold,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.playback_completion_threshold) = $event)),
                          min: 0.5,
                          max: 1,
                          step: 0.05,
                          color: "primary",
                          "hide-details": "",
                          "thumb-label": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                    _createTextVNode("播放样本只来自 Playback Reporting；未就绪时插件保持停用，不会切换到其他画像来源。", -1)
                  ]))]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'playback']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_40, [
                _cache[48] || (_cache[48] = _createElementVNode("div", { class: "ar-config__section-title" }, "发现来源", -1)),
                _createElementVNode("div", _hoisted_41, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceDefs.value, (source) => {
                    return (_openBlock(), _createBlock(_component_VCard, {
                      key: source.key,
                      variant: "outlined",
                      class: "ar-config__source-card"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCardItem, null, {
                          prepend: _withCtx(() => [
                            _createVNode(_component_VAvatar, {
                              color: "primary",
                              variant: "tonal",
                              size: "36"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VIcon, {
                                  icon: source.icon
                                }, null, 8, ["icon"])
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          append: _withCtx(() => [
                            _createVNode(_component_VSwitch, {
                              modelValue: form.discovery_sources[source.key],
                              "onUpdate:modelValue": $event => ((form.discovery_sources[source.key]) = $event),
                              color: "success",
                              "hide-details": "",
                              inset: "",
                              "aria-label": `启用${source.title}`
                            }, null, 8, ["modelValue", "onUpdate:modelValue", "aria-label"])
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(source.title), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VCardSubtitle, null, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(source.subtitle), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024))
                  }), 128))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'sources']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_42, [
                _cache[50] || (_cache[50] = _createElementVNode("div", { class: "ar-config__section-title" }, "权重设置", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                    _createTextVNode("Config 是权重唯一写入口；数值越高，Agent 排序时越重视该维度。", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_43, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(weightDefs, (weight) => {
                    return _createElementVNode("div", {
                      key: weight.key,
                      class: "ar-config__weight-item"
                    }, [
                      _createElementVNode("div", _hoisted_44, [
                        _createVNode(_component_VIcon, {
                          icon: weight.icon,
                          size: "18",
                          color: "primary",
                          class: "mr-2"
                        }, null, 8, ["icon"]),
                        _createElementVNode("span", _hoisted_45, _toDisplayString(weight.title), 1),
                        _createVNode(_component_VSpacer),
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          variant: "tonal",
                          color: "primary"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(Number(form.weights[weight.key]).toFixed(1)), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _createVNode(_component_VSlider, {
                        modelValue: form.weights[weight.key],
                        "onUpdate:modelValue": $event => ((form.weights[weight.key]) = $event),
                        min: 0,
                        max: 1,
                        step: 0.1,
                        color: "primary",
                        "hide-details": "",
                        "thumb-label": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createElementVNode("div", _hoisted_46, "默认 " + _toDisplayString(weightDefaults[weight.key].toFixed(1)), 1)
                    ])
                  }), 64))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'weights']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_47, [
                _cache[51] || (_cache[51] = _createElementVNode("div", { class: "ar-config__section-title" }, "条件筛选", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.media_types,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.media_types) = $event)),
                          items: mediaTypeOptions,
                          label: "媒体类型",
                          multiple: "",
                          chips: "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.candidate_pool_size,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.candidate_pool_size) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "10",
                          max: "500",
                          label: "候选池数量",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_48, "置信度阈值 " + _toDisplayString(Math.round(form.confidence_threshold * 100)) + "%", 1),
                        _createVNode(_component_VSlider, {
                          modelValue: form.confidence_threshold,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.confidence_threshold) = $event)),
                          min: 0,
                          max: 1,
                          step: 0.05,
                          color: "primary",
                          "hide-details": "",
                          "thumb-label": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCombobox, {
                          modelValue: form.exclude_keywords,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.exclude_keywords) = $event)),
                          label: "排除关键词",
                          multiple: "",
                          chips: "",
                          "closable-chips": "",
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
                [_vShow, activeMain.value === 'filter']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_49, [
                _cache[52] || (_cache[52] = _createElementVNode("div", { class: "ar-config__section-title" }, "榜单行为", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.action_mode,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.action_mode) = $event)),
                          items: actionOptions,
                          label: "动作模式",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.auto_subscribe_top_n,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.auto_subscribe_top_n) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "0",
                          max: form.auto_subscribe_limit,
                          label: "自动订阅前几名",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          disabled: form.action_mode !== 'auto_subscribe'
                        }, null, 8, ["modelValue", "max", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.auto_subscribe_limit,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.auto_subscribe_limit) = $event)),
                          modelModifiers: { number: true },
                          type: "number",
                          min: "0",
                          max: "10",
                          label: "安全上限",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.notify) = $event)),
                          color: "info",
                          label: "发送通知",
                          "hide-details": "",
                          inset: "",
                          disabled: form.action_mode === 'update'
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: form.action_mode === 'auto_subscribe' ? 'warning' : 'info',
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、置信度、识别 ID 和重复订阅。' : 'Telegram 通知以海报轮播展示榜单，可自由加入待订阅清单，最终确认后再逐项执行安全检查。'), 1)
                  ]),
                  _: 1
                }, 8, ["type"])
              ], 512), [
                [_vShow, activeMain.value === 'board']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_50, [
                (activeAdvanced.value === 'runtime')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _cache[55] || (_cache[55] = _createElementVNode("div", { class: "ar-config__section-title" }, "运行设置", -1)),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.discovery_page_enabled,
                                "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.discovery_page_enabled) = $event)),
                                color: "success",
                                label: "开启发现页",
                                "hide-details": "",
                                inset: ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.profile_cache_enabled,
                                "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.profile_cache_enabled) = $event)),
                                color: "success",
                                label: "画像缓存",
                                "hide-details": "",
                                inset: ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VSwitch, {
                                modelValue: form.rebuild_profile_each_run,
                                "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.rebuild_profile_each_run) = $event)),
                                color: "warning",
                                label: "每次重建",
                                "hide-details": "",
                                inset: ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.minimum_samples,
                                "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.minimum_samples) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                max: "100",
                                label: "最少样本",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.history_limit,
                                "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.history_limit) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                max: "200",
                                label: "历史上限",
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
                      _createVNode(_component_VAlert, {
                        type: "info",
                        variant: "tonal",
                        class: "mt-4"
                      }, {
                        default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                          _createTextVNode("画像缓存开启且关闭每次重建时，Agent 会在播放快照未变化时复用当前画像；每次重建开启或缓存关闭时，按冻结的 Playback Reporting 快照重新生成。", -1)
                        ]))]),
                        _: 1
                      }),
                      _createElementVNode("div", _hoisted_51, [
                        _createElementVNode("div", null, [
                          _cache[54] || (_cache[54] = _createElementVNode("div", { class: "ar-config__danger-title" }, "清除画像", -1)),
                          _createElementVNode("div", _hoisted_52, "清除默认画像身份“" + _toDisplayString(selectedIdentity.value?.username || '未选择') + "”的画像与榜单，不影响 MoviePilot 订阅和归档。", 1)
                        ]),
                        _createVNode(_component_VSwitch, {
                          modelValue: clearProfileSwitch.value,
                          "onUpdate:modelValue": [
                            _cache[24] || (_cache[24] = $event => ((clearProfileSwitch).value = $event)),
                            requestClearProfile
                          ],
                          color: "error",
                          label: "清除画像",
                          "hide-details": "",
                          inset: "",
                          disabled: clearProfileLoading.value
                        }, null, 8, ["modelValue", "disabled"])
                      ])
                    ], 64))
                  : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createElementVNode("div", _hoisted_53, [
                        _cache[57] || (_cache[57] = _createElementVNode("div", { class: "ar-config__section-title mb-0" }, "提示设置", -1)),
                        _createVNode(_component_VSpacer),
                        _createVNode(_component_VBtn, {
                          variant: "text",
                          color: "primary",
                          "prepend-icon": "mdi-restore",
                          size: "small",
                          onClick: restoreAgentPrompt
                        }, {
                          default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                            _createTextVNode("恢复默认", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _createVNode(_component_VTextarea, {
                        modelValue: form.agent_prompt,
                        "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.agent_prompt) = $event)),
                        label: "Agent排序提示词",
                        variant: "outlined",
                        rows: "12",
                        counter: "4000",
                        maxlength: "4000",
                        "auto-grow": "",
                        "hide-details": "auto"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_VAlert, {
                        type: "info",
                        variant: "tonal",
                        class: "mt-4"
                      }, {
                        default: _withCtx(() => [...(_cache[58] || (_cache[58] = [
                          _createTextVNode("该提示词只调整冻结候选池内的排序与文案风格；画像生成提示、只读工具边界和 JSON 输出协议由插件固定保留。", -1)
                        ]))]),
                        _: 1
                      })
                    ], 64))
              ], 512), [
                [_vShow, activeMain.value === 'advanced']
              ])
            ], 2)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, { class: "ar-config__actions" }, {
          default: _withCtx(() => [
            (loading.value)
              ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                  key: 0,
                  indeterminate: "",
                  size: "20",
                  width: "2",
                  color: "primary"
                }))
              : _createCommentVNode("", true),
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[26] || (_cache[26] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                _createTextVNode("保存配置", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDialog, {
      modelValue: clearProfileDialog.value,
      "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((clearProfileDialog).value = $event)),
      "max-width": "480",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                _createTextVNode("清除用户画像？", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createTextVNode(" 将清除“" + _toDisplayString(selectedIdentity.value?.username || selectedProfileId.value) + "”的画像与当前榜单。MoviePilot 订阅、订阅任务、忽略归档和插件配置不会被删除。 ", 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  disabled: clearProfileLoading.value,
                  onClick: cancelClearProfile
                }, {
                  default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  loading: clearProfileLoading.value,
                  onClick: confirmClearProfile
                }, {
                  default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
                    _createTextVNode("确认清除", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VSnackbar, {
      modelValue: actionFeedback.show,
      "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((actionFeedback.show) = $event)),
      color: actionFeedback.color
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(actionFeedback.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-8ed77881"]]);

export { Config as default };
