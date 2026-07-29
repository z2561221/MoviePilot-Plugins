import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi, a as getHostApi } from './_plugin-vue_export-helper-Z-mQLghu.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass,createCommentVNode:_createCommentVNode,createBlock:_createBlock,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "ar-config" };
const _hoisted_2 = { class: "ar-config__header-state" };
const _hoisted_3 = { class: "ar-config__body" };
const _hoisted_4 = {
  class: "ar-config__nav",
  "aria-label": "Agent榜单配置导航"
};
const _hoisted_5 = { class: "ar-config__content" };
const _hoisted_6 = {
  key: 0,
  class: "ar-config__subtabs"
};
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "ar-config__pane ar-config__pane--overview" };
const _hoisted_9 = { class: "ar-config__pipeline" };
const _hoisted_10 = { class: "ar-config__step-copy" };
const _hoisted_11 = { class: "ar-config__overview-grid" };
const _hoisted_12 = { class: "ar-config__overview-panel" };
const _hoisted_13 = { class: "ar-config__panel-head" };
const _hoisted_14 = { class: "ar-config__stats" };
const _hoisted_15 = { class: "ar-config__hint" };
const _hoisted_16 = { class: "ar-config__overview-panel" };
const _hoisted_17 = { class: "ar-config__panel-head" };
const _hoisted_18 = { class: "ar-config__hint" };
const _hoisted_19 = { class: "ar-config__tag-row" };
const _hoisted_20 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_21 = { class: "ar-config__overview-panel" };
const _hoisted_22 = { class: "ar-config__panel-head" };
const _hoisted_23 = { class: "ar-config__metric-list" };
const _hoisted_24 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_25 = { class: "ar-config__overview-panel" };
const _hoisted_26 = { class: "ar-config__panel-head" };
const _hoisted_27 = { class: "ar-config__metric-columns" };
const _hoisted_28 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_29 = {
  key: 0,
  class: "ar-config__empty"
};
const _hoisted_30 = {
  key: 0,
  class: "ar-config__source-errors"
};
const _hoisted_31 = { class: "ar-config__overview-foot" };
const _hoisted_32 = { class: "ar-config__pane" };
const _hoisted_33 = { class: "text-caption mb-1" };
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
const _hoisted_41 = { class: "ar-config__danger-row mt-4" };
const _hoisted_42 = { class: "ar-config__hint" };
const _hoisted_43 = { class: "ar-config__pane" };
const _hoisted_44 = { class: "ar-config__source-grid" };
const _hoisted_45 = { class: "ar-config__pane" };
const _hoisted_46 = { class: "ar-config__weight-grid" };
const _hoisted_47 = { class: "d-flex align-center mb-1" };
const _hoisted_48 = { class: "text-body-2 font-weight-medium" };
const _hoisted_49 = { class: "ar-config__default" };
const _hoisted_50 = { class: "ar-config__pane" };
const _hoisted_51 = { class: "ar-config__inline-alert" };
const _hoisted_52 = {
  key: 1,
  class: "ar-config__loading-state"
};
const _hoisted_53 = {
  key: 2,
  class: "ar-config__access-list"
};
const _hoisted_54 = { class: "ar-config__access-user" };
const _hoisted_55 = {
  key: 0,
  class: "ar-config__empty-state"
};
const _hoisted_56 = { class: "ar-config__retention-grid" };
const _hoisted_57 = { class: "ar-config__hint" };
const _hoisted_58 = { class: "ar-config__data-actions" };
const _hoisted_59 = { class: "ar-config__data-row" };
const _hoisted_60 = { class: "ar-config__data-row" };
const _hoisted_61 = { class: "ar-config__data-row ar-config__data-row--danger" };
const _hoisted_62 = { class: "ar-config__prompt-list" };
const _hoisted_63 = { class: "ar-config__prompt-copy" };
const _hoisted_64 = { class: "ar-config__prompt-title" };
const _hoisted_65 = { class: "ar-config__prompt-purpose" };
const _hoisted_66 = { class: "ar-config__prompt-summary" };
const _hoisted_67 = { class: "ar-config__hint mt-2" };

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
  year_weight: 0.9,
  rating_weight: 0.9,
  heat_weight: 0.9,
  freshness_weight: 0.9,
  similarity_weight: 0.9,
};

const defaults = {
  enabled: false,
  discovery_page_enabled: true,
  onlyonce: false,
  schedule_enabled: true,
  cron: '5 18 * * *',
  emby_identities: [],
  default_profile_id: '',
  profile_access_map: {},
  emby_library_ids: null,
  discovery_sources: {
    douban: true,
    tmdb_movies: true,
    tmdb_tv: true,
    bangumi: true,
    anilist: true,
  },
  weights: { ...weightDefaults },
  minimum_samples: 5,
  candidate_pool_size: 100,
  confidence_threshold: 0.6,
  action_mode: 'notify',
  notify: true,
  auto_subscribe_top_n: 0,
  auto_subscribe_limit: 10,
  history_limit: 50,
  candidate_snapshot_limit: 20,
  feedback_event_limit: 1000,
  feedback_queue_limit: 200,
  conversation_message_limit: 200,
  attribution_record_limit: 500,
  analysis_record_limit: 500,
  profile_cache_enabled: true,
  rebuild_profile_each_run: false,
  playback_enabled: true,
  playback_recent_days: 90,
  playback_completion_threshold: 0.85,
  playback_abandon_minutes: 20,
  playback_cache_days: 7,
  profile_prompt: '基于用户真实播放记录和明确偏好，归纳稳定的内容偏好与观看动机。除题材、主创、地区、年代和风格外，可观察情绪体验、认知满足、叙事投入、熟悉与新奇的平衡、节奏与完成感。稳定结论必须由至少两条相互独立的播放证据支持，或由一项用户明确添加的偏好支持；单一样本不得形成稳定结论，弃看只能作为弱负向信号。',
  ranking_prompt: '以用户画像、真实播放证据和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。兼顾相关性、新鲜感与题材多样性；评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名，相关性明显不足时宁可少推。',
  copy_prompt: '推荐理由要用自然、具体、克制的内容语言说明用户偏好与作品事实之间的匹配，不输出心理诊断或心理学术语，也避免空泛夸赞。作品简介只概括作品本身，不剧透；推荐理由和简介都要总结为语义完整的短句。',
  critic_prompt: '先复述用户可核对的内容偏好，再区分已确认事实、当前推测和仍待确认的信息。发现证据冲突时要明确承认不确定性并优先提出具体澄清问题；回复保持自然、具体、克制，尊重用户纠正，不把单次反馈写成稳定结论。',
};

const legacyAgentPromptDefaults = new Set([
  '请综合用户订阅画像、榜单权重与候选特征排序，优先推荐真正贴合用户口味、同时兼顾质量、新鲜感与题材多样性的作品。推荐理由和作品简介要轻松诙谐、机灵自然，避免套话、低俗表达与剧透。',
  '以用户真实订阅记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要点明用户偏好与作品题材、主创、地区、年代或风格之间的具体联系，避免空泛夸赞。',
  '以用户真实播放记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要点明用户偏好与作品题材、主创、地区、年代或风格之间的具体联系，避免空泛夸赞。',
  '以用户真实播放记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。除题材、主创、地区、年代和风格外，可从情绪体验、认知满足、叙事投入、熟悉与新奇的平衡、节奏与完成感五类观看动机辅助排序。稳定动机必须由至少两条相互独立的播放证据支持，或由一项用户明确添加的偏好支持；单一样本不得形成稳定结论，弃看只能作为弱负向信号。不得推断人格、焦虑、孤独、疾病、创伤等敏感心理状态。观看动机只能作为软排序信号，不得生成硬过滤条件。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要用自然的内容语言说明具体匹配，不输出心理诊断或心理学术语，也避免空泛夸赞。',
]);

const form = reactive(structuredClone(defaults));
const activeMain = ref('overview');
const activeProfile = ref('playback');
const activeStrategy = ref('sources');
const activeAdvanced = ref('runtime');
const loading = ref(false);
const status = ref({ state: 'stopped', validation_errors: [], playback: null, enablement: null });
const overview = ref(null);
const availableIdentities = ref([]);
const availableLibraries = ref({});
const sourceOptions = ref([]);
const moviePilotUsers = ref([]);
const accessLoading = ref(false);
const accessError = ref('');
const loadError = ref('');
const runtimeDefaults = ref(structuredClone(defaults));
const clearProfileSwitch = ref(false);
const clearProfileDialog = ref(false);
const clearProfileLoading = ref(false);
const actionFeedback = reactive({ show: false, message: '', color: 'success' });
const promptEditor = reactive({ open: false, key: '', draft: '' });
const dataActionLoading = ref('');
const learningResetDialog = ref(false);
const fullResetDialog = ref(false);
const fullResetStage = ref('prepare');
const fullResetPhrase = ref('');
const fullResetConfirmation = ref(null);

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '集中设置服务、计划、入口、动作与通知。' },
  { key: 'profile', title: '画像学习', icon: 'mdi-account-heart-outline', desc: '管理播放画像与画像学习策略。' },
  { key: 'strategy', title: '推荐策略', icon: 'mdi-compass-outline', desc: '选择 MoviePilot 内置发现来源并设置排序权重。' },
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

const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知内选择', value: 'notify' },
  { title: '自动订阅前几名', value: 'auto_subscribe' },
];
const profileTabs = [
  { key: 'playback', title: '播放画像', icon: 'mdi-play-circle-outline' },
  { key: 'policy', title: '画像策略', icon: 'mdi-brain' },
];
const strategyTabs = [
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical' },
];
const advancedTabs = [
  { key: 'runtime', title: '运行参数', icon: 'mdi-cog-outline' },
  { key: 'access', title: '访问控制', icon: 'mdi-account-lock-outline' },
  { key: 'data', title: '数据管理', icon: 'mdi-database-cog-outline' },
  { key: 'prompt', title: '提示设置', icon: 'mdi-text-box-edit-outline' },
];
const promptDefinitions = [
  { key: 'profile_prompt', title: '画像理解规则', icon: 'mdi-account-search-outline', purpose: '控制 Agent 如何从播放事实和人工标签归纳稳定偏好与观看动机。' },
  { key: 'ranking_prompt', title: '榜单推荐策略', icon: 'mdi-sort-variant', purpose: '控制冻结候选池内的相关性、新鲜感、多样性和最终排序。' },
  { key: 'copy_prompt', title: '推荐文案风格', icon: 'mdi-text-box-edit-outline', purpose: '控制推荐理由和作品简介的表达风格，不改变候选和安全校验。' },
  { key: 'critic_prompt', title: 'CinePilot Agent 扩展提示词', icon: 'mdi-message-text-outline', purpose: '控制反馈理解、逐条评论和对话的表达重点；不能覆盖人设、安全边界和写操作确认。' },
];
const retentionDefinitions = [
  { key: 'candidate_snapshot_limit', title: '候选快照', hint: '每个画像保留的冻结候选批次', max: 500 },
  { key: 'feedback_event_limit', title: '反馈事件', hint: '点赞、点踩、忽略和评论事实', max: 100000 },
  { key: 'feedback_queue_limit', title: '理解队列', hint: '待处理、重试和失败任务', max: 100000 },
  { key: 'conversation_message_limit', title: '对话消息', hint: 'CinePilot Agent 会话消息', max: 100000 },
  { key: 'attribution_record_limit', title: '结果归因', hint: '订阅、入库和播放观察', max: 100000 },
  { key: 'analysis_record_limit', title: '分析记录', hint: '结构化推荐分析与修订', max: 100000 },
];

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0]);
const currentSubTabs = computed(() => (
  activeMain.value === 'basic' ? []
    : activeMain.value === 'profile' ? profileTabs
      : activeMain.value === 'strategy' ? strategyTabs
        : activeMain.value === 'advanced' ? advancedTabs
          : []
));
const activePromptDefinition = computed(() => promptDefinitions.find(item => item.key === promptEditor.key) || promptDefinitions[0]);
const selectedProfileId = computed(() => form.default_profile_id || form.emby_identities[0]?.profile_id || '');
const selectedIdentity = computed(() => form.emby_identities.find(identity => identity.profile_id === selectedProfileId.value) || null);
const profileAccessOptions = computed(() => form.emby_identities.map(identity => ({
  title: `${identity.username} · ${identity.server_name}`,
  value: identity.profile_id,
})));
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
const runtimeStateText = computed(() => ({ ready: '运行中', blocked: '已阻断', stopped: '已停用' })[status.value.state] || '未知状态');
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
      title: '其他来源',
      subtitle: 'MoviePilot 内置来源',
      icon: 'mdi-database-outline',
    }),
  }))
});

function displayValue(value) {
  if (Array.isArray(value)) return value.join('、') || '无'
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => `${filterLabel(key)}：${item}`).join('、') || '无'
  return String(value ?? '') || '无'
}

const stageLabels = {
  ready: '已就绪', generated: '已生成', reused: '已复用', cached: '已缓存', saved: '已保存', success: '已完成', pending: '等待中', running: '运行中', stopped: '已停止', disabled: '已停用',
  playback_unavailable: '播放数据不可用', emby_unavailable: 'Emby 不可用', permission_error: '权限不足', transient_error: '临时错误', unavailable: '不可用', configuration_error: '配置错误',
  sample_insufficient: '播放样本不足', candidate_insufficient: '候选数量不足', recommendation_incomplete: '推荐榜单不足',
  profile_agent_failed: '画像 Agent 调用失败', profile_validation_failed: '画像输出校验失败', profile_save_failed: '画像保存失败',
  candidate_failed: '候选采集失败', candidate_filter_failed: '候选过滤失败', candidate_snapshot_failed: '候选快照失败',
  ranking_agent_failed: '排序 Agent 调用失败', ranking_validation_failed: '排序输出校验失败', ranking_save_failed: '榜单保存失败',
  subscription_partial_failed: '部分订阅失败', validation_failed: '输出校验失败', agent_failed: 'Agent 调用失败', runtime_exception: '运行异常', failed: '失败', blocked: '已阻断',
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
const exclusionLabels = { invalid_or_unrecognized: '无效或未识别', watched: '已观看', watched_completed: '已看完', library: '已入库', subscribed: '已订阅', disliked: '已点踩', archived: '已忽略', negative_keyword: '避雷命中', ambiguous_playback_count: '播放次数误写为看完次数', unsupported_playback_claim: '观看经历无法回溯' };
const mediaTypeLabels = { movie: '电影', tv: '剧集', anime: '动漫' };
const languageLabels = { zh: '中文', ja: '日语', ko: '韩语', en: '英语', fr: '法语', de: '德语', es: '西班牙语', it: '意大利语', ru: '俄语', th: '泰语' };
const sortLabels = { 'popularity.desc': '热度降序', 'vote_average.desc': '评分降序', 'primary_release_date.desc': '上映日期降序', 'first_air_date.desc': '首播日期降序' };
function sourceLabel(value) { return sourceLabels[value] || '其他来源' }
function exclusionLabel(value) { return exclusionLabels[value] || '其他排除原因' }
function filterLabel(value) { return filterLabels[value] || '其他条件' }
function formatFilterValue(key, value) {
  if (key === 'media_types' && Array.isArray(value)) return value.map(item => mediaTypeLabels[item] || '其他类型')
  if ((key === 'original_languages' || key === 'languages') && Array.isArray(value)) return value.map(item => {
    const legacyLabel = languageLabels[item] || item;
    return languageLabels[item] ? legacyLabel : '其他语言'
  })
  if (key === 'sort_by') return sortLabels[value] || '其他排序'
  return value
}
function formatDateTime(value) {
  if (!value) return '尚未同步'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '时间未知' : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function subTabActive(key) {
  if (activeMain.value === 'profile') return activeProfile.value === key
  if (activeMain.value === 'strategy') return activeStrategy.value === key
  return activeAdvanced.value === key
}

function selectSubTab(key) {
  if (activeMain.value === 'profile') activeProfile.value = key;
  else if (activeMain.value === 'strategy') activeStrategy.value = key;
  else activeAdvanced.value = key;
}

function stageStatus(step) {
  const value = latestMetrics.value.stage_status?.[step.key] || '';
  return stageLabels[value] || '未记录'
}

function stageDuration(step) {
  const value = Number(latestMetrics.value.stage_ms?.[step.key]);
  if (!Number.isFinite(value) || value < 0) return ''
  if (value < 1000) return `${Math.round(value)} 毫秒`
  return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)} 秒`
}

function runStatusText(value) { return stageLabels[value] || '运行异常' }

function playbackSourceLabel(value) {
  return ({ playback_reporting: '播放记录服务', emby_native: '播放记录服务', unavailable: '不可用' })[value] || '播放记录服务'
}

function playbackConfidenceLabel(value) {
  return ({ high: '高', medium: '中', low: '低' })[value] || '未评估'
}

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

function applyConfig(value) {
  const next = cloneConfig(value);
  const legacyPrompt = String(next.agent_prompt || '').trim();
  if (legacyPrompt && !legacyAgentPromptDefaults.has(legacyPrompt)) {
    if (!next.profile_prompt) next.profile_prompt = legacyPrompt;
    if (!next.ranking_prompt) next.ranking_prompt = legacyPrompt;
  }
  delete next.agent_prompt;
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
  form.profile_access_map = next.profile_access_map && typeof next.profile_access_map === 'object'
    ? Object.fromEntries(Object.entries(next.profile_access_map).map(([userId, profileIds]) => [
      String(userId),
      Array.isArray(profileIds) ? [...profileIds] : [],
    ]))
    : {};
  delete form.media_types;
  delete form.exclude_keywords;
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true });
async function loadOverview(profileId = selectedProfileId.value) {
  if (!props.api?.get || !profileId) {
    overview.value = null;
    return
  }
  overview.value = await getPluginApi(props.api, 'overview', { profile_id: profileId });
}

async function loadMoviePilotUsers() {
  if (!props.api?.get) return
  accessLoading.value = true;
  accessError.value = '';
  try {
    const users = await getHostApi(props.api, 'user/');
    moviePilotUsers.value = (Array.isArray(users) ? users : [])
      .filter(user => user?.id != null && user?.is_active !== false)
      .map(user => ({
        id: String(user.id),
        name: String(user.name || `用户 ${user.id}`),
        is_superuser: user.is_superuser === true,
      }))
      .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'));
  } catch (error) {
    accessError.value = error?.message || 'MoviePilot 用户列表加载失败';
  } finally {
    accessLoading.value = false;
  }
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
    await Promise.all([
      loadOverview(optionsData?.default_profile_id || selectedProfileId.value),
      loadMoviePilotUsers(),
    ]);
  } catch (error) {
    loadError.value = error?.message || '运行信息加载失败';
  } finally {
    loading.value = false;
  }
}

function saveConfig() {
  const payload = cloneConfig(form);
  const configuredProfiles = new Set(payload.emby_identities.map(identity => identity.profile_id));
  payload.profile_access_map = Object.fromEntries(
    Object.entries(payload.profile_access_map || {})
      .map(([userId, profileIds]) => [
        String(userId),
        [...new Set((profileIds || []).filter(profileId => configuredProfiles.has(profileId)))],
      ])
      .filter(([, profileIds]) => profileIds.length),
  );
  delete payload._validation_errors;
  emit('save', payload);
}

function setProfileAccess(userId, profileIds) {
  const key = String(userId);
  const allowed = new Set(form.emby_identities.map(identity => identity.profile_id));
  const selected = [...new Set((profileIds || []).filter(profileId => allowed.has(profileId)))];
  const next = { ...(form.profile_access_map || {}) };
  if (selected.length) next[key] = selected;
  else delete next[key];
  form.profile_access_map = next;
}

function showActionFeedback(color, message) {
  actionFeedback.color = color;
  actionFeedback.message = message;
  actionFeedback.show = true;
}

async function exportProfileData() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'export';
  try {
    const data = await getPluginApi(props.api, 'data/export', { profile_id: selectedProfileId.value });
    const content = JSON.stringify(data, null, 2);
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const label = String(selectedIdentity.value?.username || selectedProfileId.value).replace(/[^A-Za-z0-9._-]+/g, '_');
    anchor.href = href;
    anchor.download = `agentrank-${label || 'profile'}-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(href);
    showActionFeedback('success', '脱敏数据已导出');
  } catch (error) {
    showActionFeedback('error', error?.message || '数据导出失败');
  } finally {
    dataActionLoading.value = '';
  }
}

async function confirmLearningReset() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'learning';
  try {
    await postPluginApi(props.api, 'data/reset/learning', {
      profile_id: selectedProfileId.value,
      confirm: true,
    });
    learningResetDialog.value = false;
    await loadOverview(selectedProfileId.value);
    showActionFeedback('success', '学习数据已重置，播放记录、榜单、归档和人工标签已保留');
  } catch (error) {
    showActionFeedback('error', error?.message || '学习重置失败');
  } finally {
    dataActionLoading.value = '';
  }
}

function openFullReset() {
  fullResetStage.value = 'prepare';
  fullResetPhrase.value = '';
  fullResetConfirmation.value = null;
  fullResetDialog.value = true;
}

function closeFullReset() {
  if (dataActionLoading.value) return
  fullResetDialog.value = false;
  fullResetStage.value = 'prepare';
  fullResetPhrase.value = '';
  fullResetConfirmation.value = null;
}

async function prepareFullReset() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'full-prepare';
  try {
    fullResetConfirmation.value = await postPluginApi(props.api, 'data/reset/full/prepare', {
      profile_id: selectedProfileId.value,
    });
    fullResetStage.value = 'confirm';
  } catch (error) {
    showActionFeedback('error', error?.message || '无法准备彻底重置');
  } finally {
    dataActionLoading.value = '';
  }
}

async function confirmFullReset() {
  if (fullResetPhrase.value !== '彻底重置' || !fullResetConfirmation.value?.confirmation_token || dataActionLoading.value) return
  dataActionLoading.value = 'full-reset';
  try {
    await postPluginApi(props.api, 'data/reset/full', {
      profile_id: selectedProfileId.value,
      confirmation_token: fullResetConfirmation.value.confirmation_token,
    });
    fullResetDialog.value = false;
    fullResetStage.value = 'prepare';
    fullResetPhrase.value = '';
    fullResetConfirmation.value = null;
    await loadOverview(selectedProfileId.value);
    showActionFeedback('success', 'AgentRank 当前画像数据已彻底重置，MoviePilot 订阅和媒体库未受影响');
  } catch (error) {
    showActionFeedback('error', error?.message || '彻底重置失败');
  } finally {
    dataActionLoading.value = '';
  }
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

function promptSummary(key) {
  return String(form[key] || '').replace(/\s+/g, ' ').trim() || '尚未设置'
}

function openPromptEditor(definition) {
  promptEditor.key = definition.key;
  promptEditor.draft = String(form[definition.key] || defaults[definition.key] || '');
  promptEditor.open = true;
}

function restorePromptEditor() {
  const key = promptEditor.key;
  promptEditor.draft = String(runtimeDefaults.value[key] || defaults[key] || '');
}

function cancelPromptEditor() {
  promptEditor.open = false;
  promptEditor.key = '';
  promptEditor.draft = '';
}

function applyPromptEditor() {
  const value = promptEditor.draft.trim();
  if (!value || value.length > 4000) return
  form[promptEditor.key] = value;
  cancelPromptEditor();
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
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSlider = _resolveComponent("VSlider");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VExpansionPanelTitle = _resolveComponent("VExpansionPanelTitle");
  const _component_VExpansionPanelText = _resolveComponent("VExpansionPanelText");
  const _component_VExpansionPanel = _resolveComponent("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent("VExpansionPanels");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VTextarea = _resolveComponent("VTextarea");
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
              default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
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
            (currentSubTabs.value.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(currentSubTabs.value, (item) => {
                    return (_openBlock(), _createElementBlock("button", {
                      key: item.key,
                      class: _normalizeClass(["ar-config__subtab", { 'ar-config__subtab--active': subTabActive(item.key) }]),
                      type: "button",
                      onClick: $event => (selectSubTab(item.key))
                    }, [
                      _createVNode(_component_VIcon, {
                        icon: item.icon,
                        size: "18",
                        class: "mr-1"
                      }, null, 8, ["icon"]),
                      _createTextVNode(_toDisplayString(item.title), 1)
                    ], 10, _hoisted_7))
                  }), 128))
                ]))
              : _createCommentVNode("", true),
            _createVNode(_component_VDivider),
            _createElementVNode("div", {
              class: _normalizeClass(["ar-config__window", { 'ar-config__window--overview': activeMain.value === 'overview' }])
            }, [
              _withDirectives(_createElementVNode("div", _hoisted_8, [
                _cache[46] || (_cache[46] = _createElementVNode("div", { class: "ar-config__section-title" }, "运行链路步骤", -1)),
                _createElementVNode("div", _hoisted_9, [
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
                      _createElementVNode("div", _hoisted_10, [
                        _createElementVNode("span", null, _toDisplayString(step.title), 1),
                        _createElementVNode("small", null, [
                          _createTextVNode(_toDisplayString(stageStatus(step)), 1),
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
                        _cache[34] || (_cache[34] = _createElementVNode("strong", null, "Playback Reporting 硬依赖未满足", -1)),
                        _createTextVNode("：" + _toDisplayString(currentEnablement.value.message || '插件无法启用'), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_11, [
                  _createElementVNode("div", _hoisted_12, [
                    _createElementVNode("div", _hoisted_13, [
                      _cache[35] || (_cache[35] = _createElementVNode("span", null, "播放样本", -1)),
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
                    _createElementVNode("div", _hoisted_14, [
                      _createElementVNode("span", null, [
                        _cache[36] || (_cache[36] = _createTextVNode("样本 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.sample_count || 0), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[37] || (_cache[37] = _createTextVNode("映射 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.mapped_count || 0), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[38] || (_cache[38] = _createTextVNode("映射率 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(playbackMappingRate.value), 1)
                      ]),
                      _createElementVNode("span", null, [
                        _cache[39] || (_cache[39] = _createTextVNode("未映射 ", -1)),
                        _createElementVNode("strong", null, _toDisplayString(currentPlayback.value?.unmapped_count || 0), 1)
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_15, _toDisplayString(selectedIdentity.value?.username || '未选择用户') + " · " + _toDisplayString(formatDateTime(currentPlayback.value?.synced_at)), 1)
                  ]),
                  _createElementVNode("div", _hoisted_16, [
                    _createElementVNode("div", _hoisted_17, [
                      _cache[40] || (_cache[40] = _createElementVNode("span", null, "画像版本", -1)),
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
                    _createElementVNode("div", _hoisted_18, "检索解析版本 " + _toDisplayString(overview.value?.profile?.retrieval_resolution_version || '-') + " · 播放证据 " + _toDisplayString(overview.value?.profile?.playback_count || 0) + " 条", 1),
                    _createElementVNode("div", _hoisted_19, [
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
                        ? (_openBlock(), _createElementBlock("span", _hoisted_20, "暂无排序标签"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_21, [
                    _createElementVNode("div", _hoisted_22, [
                      _cache[41] || (_cache[41] = _createElementVNode("span", null, "检索计划", -1)),
                      _createElementVNode("small", null, _toDisplayString(retrievalFilterEntries.value.length) + " 项过滤", 1)
                    ]),
                    _createElementVNode("div", _hoisted_23, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(retrievalFilterEntries.value, ([key, value]) => {
                        return (_openBlock(), _createElementBlock("span", { key: key }, [
                          _createElementVNode("b", null, _toDisplayString(key), 1),
                          _createTextVNode(_toDisplayString(displayValue(value)), 1)
                        ]))
                      }), 128)),
                      (!retrievalFilterEntries.value.length)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_24, "暂无已解析过滤条件"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_25, [
                    _createElementVNode("div", _hoisted_26, [
                      _cache[42] || (_cache[42] = _createElementVNode("span", null, "冻结候选", -1)),
                      _createElementVNode("small", null, _toDisplayString(latestMetrics.value.candidate_count || 0) + " 项", 1)
                    ]),
                    _createElementVNode("div", _hoisted_27, [
                      _createElementVNode("div", null, [
                        _cache[43] || (_cache[43] = _createElementVNode("small", null, "候选来源", -1)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidateSourceEntries.value, ([key, value]) => {
                          return (_openBlock(), _createElementBlock("span", { key: key }, [
                            _createTextVNode(_toDisplayString(key) + " ", 1),
                            _createElementVNode("b", null, _toDisplayString(value), 1)
                          ]))
                        }), 128)),
                        (!candidateSourceEntries.value.length)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_28, "暂无统计"))
                          : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("div", null, [
                        _cache[44] || (_cache[44] = _createElementVNode("small", null, "排除统计", -1)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidateExclusionEntries.value, ([key, value]) => {
                          return (_openBlock(), _createElementBlock("span", { key: key }, [
                            _createTextVNode(_toDisplayString(key) + " ", 1),
                            _createElementVNode("b", null, _toDisplayString(value), 1)
                          ]))
                        }), 128)),
                        (!candidateExclusionEntries.value.length)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_29, "暂无统计"))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    (sourceErrorEntries.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_30, [
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
                _createElementVNode("div", _hoisted_31, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-shield-refresh-outline",
                    size: "17",
                    color: "primary"
                  }),
                  _cache[45] || (_cache[45] = _createElementVNode("span", null, "Agent、候选或保存失败时保留旧画像与旧榜单，不执行订阅。", -1)),
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
              _withDirectives(_createElementVNode("div", _hoisted_32, [
                _cache[48] || (_cache[48] = _createElementVNode("div", { class: "ar-config__section-title" }, "基础设置", -1)),
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
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.discovery_page_enabled,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.discovery_page_enabled) = $event)),
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
                        _createVNode(_component_VSelect, {
                          modelValue: form.action_mode,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.action_mode) = $event)),
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
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.auto_subscribe_top_n,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.auto_subscribe_top_n) = $event)),
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
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.auto_subscribe_limit,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.auto_subscribe_limit) = $event)),
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
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.notify,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.notify) = $event)),
                          color: "info",
                          label: "发送通知",
                          "hide-details": "",
                          inset: "",
                          disabled: form.action_mode === 'update'
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "8"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_33, "订阅门槛 · 最低支持度 " + _toDisplayString(Math.round(form.confidence_threshold * 100)) + "%", 1),
                        _createVNode(_component_VSlider, {
                          modelValue: form.confidence_threshold,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.confidence_threshold) = $event)),
                          min: 0,
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
                    _createTextVNode("Emby 画像身份由服务实例与用户组成；画像只同步所选用户在所选内容库中的 Playback Reporting 记录，未安装或不可访问时插件保持停用。", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: form.action_mode === 'auto_subscribe' ? 'warning' : 'info',
                  variant: "tonal",
                  class: "mt-3"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、最低支持度、识别 ID 和重复订阅。' : '最低支持度只限制订阅，不过滤榜单；通知模式由用户在消息中确认后执行。'), 1)
                  ]),
                  _: 1
                }, 8, ["type"])
              ], 512), [
                [_vShow, activeMain.value === 'basic']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_34, [
                _createElementVNode("div", _hoisted_35, [
                  _cache[50] || (_cache[50] = _createElementVNode("div", { class: "ar-config__section-title mb-0" }, "播放画像", -1)),
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
                    default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
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
                              _createTextVNode(_toDisplayString(playbackSourceLabel(currentPlayback.value.source)), 1)
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
                              _createTextVNode(_toDisplayString(playbackConfidenceLabel(currentPlayback.value.confidence)), 1)
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
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.playback_recent_days) = $event)),
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
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.playback_abandon_minutes) = $event)),
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
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.playback_cache_days) = $event)),
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
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.playback_completion_threshold) = $event)),
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
                  default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
                    _createTextVNode("播放样本只来自 Playback Reporting；未就绪时插件保持停用，不会切换到其他画像来源。", -1)
                  ]))]),
                  _: 1
                })
              ], 512), [
                [_vShow, activeMain.value === 'profile' && activeProfile.value === 'playback']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_40, [
                _cache[54] || (_cache[54] = _createElementVNode("div", { class: "ar-config__section-title" }, "画像策略", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.profile_cache_enabled,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.profile_cache_enabled) = $event)),
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
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.rebuild_profile_each_run) = $event)),
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
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.minimum_samples) = $event)),
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
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mt-4"
                }, {
                  default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                    _createTextVNode("画像缓存开启且关闭每次重建时，会在播放快照未变化时复用当前画像；每次重建开启或缓存关闭时，按冻结的 Playback Reporting 快照重新生成。媒体类型由播放事实、明确反馈和可撤销画像标签学习；偏好标签与避雷标签是用户修正画像的统一入口。", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_41, [
                  _createElementVNode("div", null, [
                    _cache[53] || (_cache[53] = _createElementVNode("div", { class: "ar-config__danger-title" }, "清除画像", -1)),
                    _createElementVNode("div", _hoisted_42, "清除默认画像身份“" + _toDisplayString(selectedIdentity.value?.username || '未选择') + "”的画像与榜单，不影响 MoviePilot 订阅和归档。", 1)
                  ]),
                  _createVNode(_component_VSwitch, {
                    modelValue: clearProfileSwitch.value,
                    "onUpdate:modelValue": [
                      _cache[20] || (_cache[20] = $event => ((clearProfileSwitch).value = $event)),
                      requestClearProfile
                    ],
                    color: "error",
                    label: "清除画像",
                    "hide-details": "",
                    inset: "",
                    disabled: clearProfileLoading.value
                  }, null, 8, ["modelValue", "disabled"])
                ])
              ], 512), [
                [_vShow, activeMain.value === 'profile' && activeProfile.value === 'policy']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_43, [
                _cache[56] || (_cache[56] = _createElementVNode("div", { class: "ar-config__section-title" }, "发现来源", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                    _createTextVNode("来源列表会探测已适配的 MoviePilot 能力（包括 AniList）；宿主未来新增但未声明统一契约的来源不会被自动执行，需完成安全适配后才会显示。", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_44, [
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
                [_vShow, activeMain.value === 'strategy' && activeStrategy.value === 'sources']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_45, [
                _cache[58] || (_cache[58] = _createElementVNode("div", { class: "ar-config__section-title" }, "权重设置", -1)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [...(_cache[57] || (_cache[57] = [
                    _createTextVNode("Config 是权重唯一写入口；数值越高，Agent 排序时越重视该维度。", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_46, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(weightDefs, (weight) => {
                    return _createElementVNode("div", {
                      key: weight.key,
                      class: "ar-config__weight-item"
                    }, [
                      _createElementVNode("div", _hoisted_47, [
                        _createVNode(_component_VIcon, {
                          icon: weight.icon,
                          size: "18",
                          color: "primary",
                          class: "mr-2"
                        }, null, 8, ["icon"]),
                        _createElementVNode("span", _hoisted_48, _toDisplayString(weight.title), 1),
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
                      _createElementVNode("div", _hoisted_49, "默认 " + _toDisplayString(weightDefaults[weight.key].toFixed(1)), 1)
                    ])
                  }), 64))
                ])
              ], 512), [
                [_vShow, activeMain.value === 'strategy' && activeStrategy.value === 'weights']
              ]),
              _withDirectives(_createElementVNode("div", _hoisted_50, [
                (activeAdvanced.value === 'runtime')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _cache[60] || (_cache[60] = _createElementVNode("div", { class: "ar-config__section-title" }, "运行参数", -1)),
                      _createVNode(_component_VRow, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.candidate_pool_size,
                                "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.candidate_pool_size) = $event)),
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
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VTextField, {
                                modelValue: form.history_limit,
                                "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.history_limit) = $event)),
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
                        default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                          _createTextVNode("候选池数量控制每轮冻结候选容量；它是运行参数，不代表内容偏好，也不会改变最低支持度的订阅边界。", -1)
                        ]))]),
                        _: 1
                      })
                    ], 64))
                  : (activeAdvanced.value === 'access')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                        _cache[65] || (_cache[65] = _createElementVNode("div", { class: "ar-config__section-title" }, "访问控制", -1)),
                        _createVNode(_component_VAlert, {
                          type: "info",
                          variant: "tonal",
                          density: "compact",
                          class: "mb-4"
                        }, {
                          default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                            _createTextVNode(" 超级用户始终可访问全部已配置画像；普通用户只有在此明确授权后才能读取或操作对应画像。 ", -1)
                          ]))]),
                          _: 1
                        }),
                        (accessError.value)
                          ? (_openBlock(), _createBlock(_component_VAlert, {
                              key: 0,
                              type: "error",
                              variant: "tonal",
                              density: "compact",
                              class: "mb-4"
                            }, {
                              default: _withCtx(() => [
                                _createElementVNode("div", _hoisted_51, [
                                  _createElementVNode("span", null, _toDisplayString(accessError.value), 1),
                                  _createVNode(_component_VBtn, {
                                    variant: "text",
                                    size: "small",
                                    "prepend-icon": "mdi-refresh",
                                    loading: accessLoading.value,
                                    onClick: loadMoviePilotUsers
                                  }, {
                                    default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
                                      _createTextVNode("重试", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["loading"])
                                ])
                              ]),
                              _: 1
                            }))
                          : _createCommentVNode("", true),
                        (accessLoading.value && !moviePilotUsers.value.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_52, [
                              _createVNode(_component_VProgressCircular, {
                                indeterminate: "",
                                color: "primary",
                                size: "28"
                              }),
                              _cache[63] || (_cache[63] = _createElementVNode("span", null, "正在读取 MoviePilot 用户", -1))
                            ]))
                          : (_openBlock(), _createElementBlock("div", _hoisted_53, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(moviePilotUsers.value.filter(item => !item.is_superuser), (user) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: user.id,
                                  class: "ar-config__access-row"
                                }, [
                                  _createVNode(_component_VAvatar, {
                                    color: "info",
                                    variant: "tonal",
                                    size: "36"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VIcon, {
                                        icon: "mdi-account-outline",
                                        size: "20"
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _createElementVNode("div", _hoisted_54, [
                                    _createElementVNode("strong", null, _toDisplayString(user.name), 1),
                                    _createElementVNode("small", null, "MoviePilot 用户 " + _toDisplayString(user.id), 1)
                                  ]),
                                  _createVNode(_component_VSelect, {
                                    "model-value": form.profile_access_map[user.id] || [],
                                    items: profileAccessOptions.value,
                                    label: "允许访问的画像",
                                    multiple: "",
                                    chips: "",
                                    "closable-chips": "",
                                    density: "compact",
                                    variant: "outlined",
                                    "hide-details": "",
                                    disabled: !profileAccessOptions.value.length,
                                    "onUpdate:modelValue": $event => (setProfileAccess(user.id, $event))
                                  }, null, 8, ["model-value", "items", "disabled", "onUpdate:modelValue"])
                                ]))
                              }), 128)),
                              (!moviePilotUsers.value.some(item => !item.is_superuser))
                                ? (_openBlock(), _createElementBlock("div", _hoisted_55, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-account-check-outline",
                                      size: "28",
                                      color: "primary"
                                    }),
                                    _cache[64] || (_cache[64] = _createElementVNode("span", null, "当前没有需要单独授权的普通用户", -1))
                                  ]))
                                : _createCommentVNode("", true)
                            ]))
                      ], 64))
                    : (activeAdvanced.value === 'data')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                          _cache[73] || (_cache[73] = _createElementVNode("div", { class: "ar-config__section-title" }, "数据保留", -1)),
                          _createElementVNode("div", _hoisted_56, [
                            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(retentionDefinitions, (item) => {
                              return _createElementVNode("div", {
                                key: item.key,
                                class: "ar-config__retention-item"
                              }, [
                                _createVNode(_component_VTextField, {
                                  modelValue: form[item.key],
                                  "onUpdate:modelValue": $event => ((form[item.key]) = $event),
                                  modelModifiers: { number: true },
                                  label: item.title,
                                  type: "number",
                                  min: "1",
                                  max: item.max,
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "max"]),
                                _createElementVNode("div", _hoisted_57, _toDisplayString(item.hint), 1)
                              ])
                            }), 64))
                          ]),
                          _cache[74] || (_cache[74] = _createElementVNode("div", { class: "ar-config__hint mt-2" }, "保留上限随“保存配置”生效，已有数据会在运行时按前缀安全裁剪。", -1)),
                          _cache[75] || (_cache[75] = _createElementVNode("div", { class: "ar-config__section-title mt-5" }, "数据操作", -1)),
                          _createElementVNode("div", _hoisted_58, [
                            _createElementVNode("div", _hoisted_59, [
                              _createVNode(_component_VAvatar, {
                                color: "info",
                                variant: "tonal",
                                size: "38"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-download-outline",
                                    size: "21"
                                  })
                                ]),
                                _: 1
                              }),
                              _cache[67] || (_cache[67] = _createElementVNode("div", null, [
                                _createElementVNode("strong", null, "导出脱敏数据"),
                                _createElementVNode("small", null, "画像、反馈、记忆、分析、对话和归因")
                              ], -1)),
                              _createVNode(_component_VBtn, {
                                variant: "tonal",
                                color: "info",
                                "prepend-icon": "mdi-download-outline",
                                loading: dataActionLoading.value === 'export',
                                disabled: !selectedProfileId.value,
                                onClick: exportProfileData
                              }, {
                                default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                                  _createTextVNode("导出", -1)
                                ]))]),
                                _: 1
                              }, 8, ["loading", "disabled"])
                            ]),
                            _createElementVNode("div", _hoisted_60, [
                              _createVNode(_component_VAvatar, {
                                color: "warning",
                                variant: "tonal",
                                size: "38"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-brain",
                                    size: "21"
                                  })
                                ]),
                                _: 1
                              }),
                              _cache[69] || (_cache[69] = _createElementVNode("div", null, [
                                _createElementVNode("strong", null, "学习重置"),
                                _createElementVNode("small", null, "清除反馈学习、确认记忆、对话与归因")
                              ], -1)),
                              _createVNode(_component_VBtn, {
                                variant: "tonal",
                                color: "warning",
                                "prepend-icon": "mdi-backup-restore",
                                disabled: !selectedProfileId.value,
                                onClick: _cache[23] || (_cache[23] = $event => (learningResetDialog.value = true))
                              }, {
                                default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                                  _createTextVNode("重置", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled"])
                            ]),
                            _createElementVNode("div", _hoisted_61, [
                              _createVNode(_component_VAvatar, {
                                color: "error",
                                variant: "tonal",
                                size: "38"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-delete-alert-outline",
                                    size: "21"
                                  })
                                ]),
                                _: 1
                              }),
                              _cache[71] || (_cache[71] = _createElementVNode("div", null, [
                                _createElementVNode("strong", null, "彻底重置"),
                                _createElementVNode("small", null, "删除当前画像下全部 AgentRank 自有数据")
                              ], -1)),
                              _createVNode(_component_VBtn, {
                                variant: "tonal",
                                color: "error",
                                "prepend-icon": "mdi-delete-alert-outline",
                                disabled: !selectedProfileId.value,
                                onClick: openFullReset
                              }, {
                                default: _withCtx(() => [...(_cache[70] || (_cache[70] = [
                                  _createTextVNode("重置", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled"])
                            ])
                          ]),
                          _createVNode(_component_VAlert, {
                            type: "info",
                            variant: "tonal",
                            density: "compact",
                            class: "mt-4"
                          }, {
                            default: _withCtx(() => [...(_cache[72] || (_cache[72] = [
                              _createTextVNode("两类重置都不会删除 MoviePilot 订阅、订阅任务或媒体库文件。", -1)
                            ]))]),
                            _: 1
                          })
                        ], 64))
                      : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                          _cache[79] || (_cache[79] = _createElementVNode("div", { class: "ar-config__section-title" }, "提示设置", -1)),
                          _createElementVNode("div", _hoisted_62, [
                            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(promptDefinitions, (definition) => {
                              return _createElementVNode("div", {
                                key: definition.key,
                                class: "ar-config__prompt-row"
                              }, [
                                _createVNode(_component_VAvatar, {
                                  color: "primary",
                                  variant: "tonal",
                                  size: "38",
                                  rounded: "lg"
                                }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_VIcon, {
                                      icon: definition.icon,
                                      size: "20"
                                    }, null, 8, ["icon"])
                                  ]),
                                  _: 2
                                }, 1024),
                                _createElementVNode("div", _hoisted_63, [
                                  _createElementVNode("div", _hoisted_64, _toDisplayString(definition.title), 1),
                                  _createElementVNode("div", _hoisted_65, _toDisplayString(definition.purpose), 1),
                                  _createElementVNode("div", _hoisted_66, _toDisplayString(promptSummary(definition.key)), 1)
                                ]),
                                _createVNode(_component_VBtn, {
                                  variant: "tonal",
                                  color: "primary",
                                  size: "small",
                                  "prepend-icon": "mdi-pencil-outline",
                                  onClick: $event => (openPromptEditor(definition))
                                }, {
                                  default: _withCtx(() => [...(_cache[76] || (_cache[76] = [
                                    _createTextVNode("编辑", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick"])
                              ])
                            }), 64))
                          ]),
                          _createVNode(_component_VExpansionPanels, {
                            variant: "accordion",
                            class: "mt-4 ar-config__fixed-rules"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VExpansionPanel, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VExpansionPanelTitle, null, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VIcon, {
                                        icon: "mdi-shield-lock-outline",
                                        color: "primary",
                                        size: "20",
                                        class: "me-2"
                                      }),
                                      _cache[77] || (_cache[77] = _createTextVNode(" 固定安全规则（只读） ", -1))
                                    ]),
                                    _: 1
                                  }),
                                  _createVNode(_component_VExpansionPanelText, null, {
                                    default: _withCtx(() => [...(_cache[78] || (_cache[78] = [
                                      _createElementVNode("ul", { class: "ar-config__rule-list" }, [
                                        _createElementVNode("li", null, "Agent 只能读取本轮受限工具数据，不能订阅、写数据、改配置或调用消息与文件能力。"),
                                        _createElementVNode("li", null, "已删除标签进入归档，画像和排序不得恢复、引用或换用近义标签规避。"),
                                        _createElementVNode("li", null, "观看动机只能作为软排序信号；不得推断人格、焦虑、孤独、疾病或创伤，也不得输出心理诊断。"),
                                        _createElementVNode("li", null, "画像与榜单必须返回插件规定的 JSON Schema，额外字段和非法候选会被拒绝。"),
                                        _createElementVNode("li", null, "推荐理由和简介必须各自总结为三十字内的完整短句，禁止按字符截断。"),
                                        _createElementVNode("li", null, "成功生成的最终榜单固定保存五条；排序校验未满时只从冻结候选池安全补位。")
                                      ], -1)
                                    ]))]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              })
                            ]),
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
              onClick: _cache[24] || (_cache[24] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[80] || (_cache[80] = [
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
              default: _withCtx(() => [...(_cache[81] || (_cache[81] = [
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
      modelValue: promptEditor.open,
      "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((promptEditor.open) = $event)),
      width: "min(720px, calc(100vw - 24px))",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "ar-config__prompt-dialog" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, null, {
              prepend: _withCtx(() => [
                _createVNode(_component_VAvatar, {
                  color: "primary",
                  variant: "tonal",
                  size: "40",
                  rounded: "lg"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: activePromptDefinition.value.icon,
                      size: "21"
                    }, null, 8, ["icon"])
                  ]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, null, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(activePromptDefinition.value.title), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "ar-config__prompt-dialog-subtitle" }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(activePromptDefinition.value.purpose), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "ar-config__prompt-dialog-body" }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextarea, {
                  modelValue: promptEditor.draft,
                  "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((promptEditor.draft) = $event)),
                  label: "提示词内容",
                  variant: "outlined",
                  rows: "12",
                  counter: "4000",
                  maxlength: "4000",
                  "auto-grow": "",
                  "hide-details": "auto"
                }, null, 8, ["modelValue"]),
                _cache[82] || (_cache[82] = _createElementVNode("div", { class: "ar-config__prompt-dialog-hint" }, "应用后只更新当前表单，点击配置页“保存配置”后才会持久化。", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  "prepend-icon": "mdi-restore",
                  onClick: restorePromptEditor
                }, {
                  default: _withCtx(() => [...(_cache[83] || (_cache[83] = [
                    _createTextVNode("恢复默认", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: cancelPromptEditor
                }, {
                  default: _withCtx(() => [...(_cache[84] || (_cache[84] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  disabled: !promptEditor.draft.trim() || promptEditor.draft.length > 4000,
                  onClick: applyPromptEditor
                }, {
                  default: _withCtx(() => [...(_cache[85] || (_cache[85] = [
                    _createTextVNode("应用", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
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
              default: _withCtx(() => [...(_cache[86] || (_cache[86] = [
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
                  default: _withCtx(() => [...(_cache[87] || (_cache[87] = [
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
                  default: _withCtx(() => [...(_cache[88] || (_cache[88] = [
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
    _createVNode(_component_VDialog, {
      modelValue: learningResetDialog.value,
      "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((learningResetDialog).value = $event)),
      "max-width": "520",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[89] || (_cache[89] = [
                _createTextVNode("重置学习数据？", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createTextVNode(" 将清除“" + _toDisplayString(selectedIdentity.value?.username || selectedProfileId.value) + "”的反馈学习、已确认记忆、待处理项、CinePilot Agent 对话和结果归因。当前画像、榜单、忽略归档、人工标签与播放记录会保留。 ", 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  disabled: dataActionLoading.value === 'learning',
                  onClick: _cache[28] || (_cache[28] = $event => (learningResetDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[90] || (_cache[90] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  color: "warning",
                  variant: "flat",
                  loading: dataActionLoading.value === 'learning',
                  onClick: confirmLearningReset
                }, {
                  default: _withCtx(() => [...(_cache[91] || (_cache[91] = [
                    _createTextVNode("确认重置", -1)
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
    _createVNode(_component_VDialog, {
      modelValue: fullResetDialog.value,
      "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((fullResetDialog).value = $event)),
      "max-width": "540",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[92] || (_cache[92] = [
                _createTextVNode("彻底重置 AgentRank 数据", -1)
              ]))]),
              _: 1
            }),
            (fullResetStage.value === 'prepare')
              ? (_openBlock(), _createBlock(_component_VCardText, { key: 0 }, {
                  default: _withCtx(() => [...(_cache[93] || (_cache[93] = [
                    _createTextVNode(" 第一步将为当前 MoviePilot 用户签发一次性短时确认令牌。继续后仍需输入确认词，期间不会删除任何数据。 ", -1)
                  ]))]),
                  _: 1
                }))
              : (_openBlock(), _createBlock(_component_VCardText, { key: 1 }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VAlert, {
                      type: "error",
                      variant: "tonal",
                      density: "compact",
                      class: "mb-4"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 此操作会删除“" + _toDisplayString(selectedIdentity.value?.username || selectedProfileId.value) + "”下的画像、榜单、归档、反馈、记忆、分析、对话、归因和运行历史，且无法撤销。 ", 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VTextField, {
                      modelValue: fullResetPhrase.value,
                      "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((fullResetPhrase).value = $event)),
                      label: "输入“彻底重置”确认",
                      density: "compact",
                      variant: "outlined",
                      autocomplete: "off",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createElementVNode("div", _hoisted_67, "确认令牌有效至 " + _toDisplayString(formatDateTime(fullResetConfirmation.value?.expires_at)) + "，且仅限当前登录用户使用。", 1)
                  ]),
                  _: 1
                })),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  disabled: Boolean(dataActionLoading.value),
                  onClick: closeFullReset
                }, {
                  default: _withCtx(() => [...(_cache[94] || (_cache[94] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VSpacer),
                (fullResetStage.value === 'prepare')
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      color: "error",
                      variant: "tonal",
                      loading: dataActionLoading.value === 'full-prepare',
                      onClick: prepareFullReset
                    }, {
                      default: _withCtx(() => [...(_cache[95] || (_cache[95] = [
                        _createTextVNode("继续", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]))
                  : (_openBlock(), _createBlock(_component_VBtn, {
                      key: 1,
                      color: "error",
                      variant: "flat",
                      loading: dataActionLoading.value === 'full-reset',
                      disabled: fullResetPhrase.value !== '彻底重置',
                      onClick: confirmFullReset
                    }, {
                      default: _withCtx(() => [...(_cache[96] || (_cache[96] = [
                        _createTextVNode("确认彻底重置", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]))
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
      "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((actionFeedback.show) = $event)),
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-42695bba"]]);

export { Config as default };
