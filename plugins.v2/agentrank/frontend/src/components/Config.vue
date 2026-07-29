<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getHostApi, getPluginApi, postPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

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
}

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
}

const legacyAgentPromptDefaults = new Set([
  '请综合用户订阅画像、榜单权重与候选特征排序，优先推荐真正贴合用户口味、同时兼顾质量、新鲜感与题材多样性的作品。推荐理由和作品简介要轻松诙谐、机灵自然，避免套话、低俗表达与剧透。',
  '以用户真实订阅记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要点明用户偏好与作品题材、主创、地区、年代或风格之间的具体联系，避免空泛夸赞。',
  '以用户真实播放记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要点明用户偏好与作品题材、主创、地区、年代或风格之间的具体联系，避免空泛夸赞。',
  '以用户真实播放记录和明确偏好为首要依据，优先选择能找到多项具体匹配证据、且能补充用户片单的新作品。除题材、主创、地区、年代和风格外，可从情绪体验、认知满足、叙事投入、熟悉与新奇的平衡、节奏与完成感五类观看动机辅助排序。稳定动机必须由至少两条相互独立的播放证据支持，或由一项用户明确添加的偏好支持；单一样本不得形成稳定结论，弃看只能作为弱负向信号。不得推断人格、焦虑、孤独、疾病、创伤等敏感心理状态。观看动机只能作为软排序信号，不得生成硬过滤条件。评分、热度和经典地位只能作为辅助信号，不能单独支撑高排名；相关性明显不足时宁可少推。推荐理由要用自然的内容语言说明具体匹配，不输出心理诊断或心理学术语，也避免空泛夸赞。',
])

const form = reactive(structuredClone(defaults))
const activeMain = ref('overview')
const activeProfile = ref('playback')
const activeStrategy = ref('sources')
const activeAdvanced = ref('runtime')
const loading = ref(false)
const status = ref({ state: 'stopped', validation_errors: [], playback: null, enablement: null })
const overview = ref(null)
const availableIdentities = ref([])
const availableLibraries = ref({})
const sourceOptions = ref([])
const moviePilotUsers = ref([])
const accessLoading = ref(false)
const accessError = ref('')
const loadError = ref('')
const runtimeDefaults = ref(structuredClone(defaults))
const clearProfileSwitch = ref(false)
const clearProfileDialog = ref(false)
const clearProfileLoading = ref(false)
const actionFeedback = reactive({ show: false, message: '', color: 'success' })
const promptEditor = reactive({ open: false, key: '', draft: '' })
const dataActionLoading = ref('')
const learningResetDialog = ref(false)
const fullResetDialog = ref(false)
const fullResetStage = ref('prepare')
const fullResetPhrase = ref('')
const fullResetConfirmation = ref(null)

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '集中设置服务、计划、入口、动作与通知。' },
  { key: 'profile', title: '画像学习', icon: 'mdi-account-heart-outline', desc: '管理播放画像与画像学习策略。' },
  { key: 'strategy', title: '推荐策略', icon: 'mdi-compass-outline', desc: '选择 MoviePilot 内置发现来源并设置排序权重。' },
  { key: 'advanced', title: '高级选项', icon: 'mdi-shield-check-outline', desc: '管理画像重建、历史上限和安全边界。' },
]

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
]

const sourceMeta = {
  douban: { title: '豆瓣发现', subtitle: '热门电影、剧集与动画', icon: 'mdi-alpha-d-circle-outline' },
  tmdb_movies: { title: 'TMDB电影', subtitle: '高热度电影候选', icon: 'mdi-movie-open-star-outline' },
  tmdb_tv: { title: 'TMDB剧集', subtitle: '高热度剧集候选', icon: 'mdi-television-classic' },
  bangumi: { title: 'Bangumi', subtitle: '动画与番剧候选', icon: 'mdi-animation-outline' },
  anilist: { title: 'AniList', subtitle: '趋势动画与本季热门', icon: 'mdi-alpha-a-circle-outline' },
}

const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知内选择', value: 'notify' },
  { title: '自动订阅前几名', value: 'auto_subscribe' },
]
const profileTabs = [
  { key: 'playback', title: '播放画像', icon: 'mdi-play-circle-outline' },
  { key: 'policy', title: '画像策略', icon: 'mdi-brain' },
]
const strategyTabs = [
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical' },
]
const advancedTabs = [
  { key: 'runtime', title: '运行参数', icon: 'mdi-cog-outline' },
  { key: 'access', title: '访问控制', icon: 'mdi-account-lock-outline' },
  { key: 'data', title: '数据管理', icon: 'mdi-database-cog-outline' },
  { key: 'prompt', title: '提示设置', icon: 'mdi-text-box-edit-outline' },
]
const promptDefinitions = [
  { key: 'profile_prompt', title: '画像理解规则', icon: 'mdi-account-search-outline', purpose: '控制 Agent 如何从播放事实和人工标签归纳稳定偏好与观看动机。' },
  { key: 'ranking_prompt', title: '榜单推荐策略', icon: 'mdi-sort-variant', purpose: '控制冻结候选池内的相关性、新鲜感、多样性和最终排序。' },
  { key: 'copy_prompt', title: '推荐文案风格', icon: 'mdi-text-box-edit-outline', purpose: '控制推荐理由和作品简介的表达风格，不改变候选和安全校验。' },
  { key: 'critic_prompt', title: 'CinePilot Agent 扩展提示词', icon: 'mdi-message-text-outline', purpose: '控制反馈理解、逐条评论和对话的表达重点；不能覆盖人设、安全边界和写操作确认。' },
]
const retentionDefinitions = [
  { key: 'candidate_snapshot_limit', title: '候选快照', hint: '每个画像保留的冻结候选批次', max: 500 },
  { key: 'feedback_event_limit', title: '反馈事件', hint: '点赞、点踩、忽略和评论事实', max: 100000 },
  { key: 'feedback_queue_limit', title: '理解队列', hint: '待处理、重试和失败任务', max: 100000 },
  { key: 'conversation_message_limit', title: '对话消息', hint: 'CinePilot Agent 会话消息', max: 100000 },
  { key: 'attribution_record_limit', title: '结果归因', hint: '订阅、入库和播放观察', max: 100000 },
  { key: 'analysis_record_limit', title: '分析记录', hint: '结构化推荐分析与修订', max: 100000 },
]

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0])
const currentSubTabs = computed(() => (
  activeMain.value === 'basic' ? []
    : activeMain.value === 'profile' ? profileTabs
      : activeMain.value === 'strategy' ? strategyTabs
        : activeMain.value === 'advanced' ? advancedTabs
          : []
))
const activePromptDefinition = computed(() => promptDefinitions.find(item => item.key === promptEditor.key) || promptDefinitions[0])
const selectedProfileId = computed(() => form.default_profile_id || form.emby_identities[0]?.profile_id || '')
const selectedIdentity = computed(() => form.emby_identities.find(identity => identity.profile_id === selectedProfileId.value) || null)
const profileAccessOptions = computed(() => form.emby_identities.map(identity => ({
  title: `${identity.username} · ${identity.server_name}`,
  value: identity.profile_id,
})))
const serverOptions = computed(() => {
  const names = [...new Set(availableIdentities.value.map(identity => identity.server_name).filter(Boolean))]
  return names.map(name => ({ title: name, value: name }))
})
const selectedServerName = computed({
  get: () => selectedIdentity.value?.server_name || '',
  set: serverName => {
    const identity = availableIdentities.value.find(item => item.server_name === serverName)
    form.emby_identities = identity ? [identity] : []
    form.default_profile_id = identity?.profile_id || ''
  },
})
const userOptions = computed(() => availableIdentities.value
  .filter(identity => identity.server_name === selectedServerName.value)
  .map(identity => ({ title: identity.username, value: identity.profile_id })))
const selectedUserProfileId = computed({
  get: () => selectedProfileId.value,
  set: profileId => {
    const identity = availableIdentities.value.find(item => item.profile_id === profileId)
    form.emby_identities = identity ? [identity] : []
    form.default_profile_id = identity?.profile_id || ''
    if (identity && !Object.prototype.hasOwnProperty.call(form.emby_library_ids || {}, identity.profile_id)) {
      form.emby_library_ids = { ...(form.emby_library_ids || {}), [identity.profile_id]: (availableLibraries.value[identity.profile_id] || []).map(item => item.id) }
    }
    loadOverview(identity?.profile_id || '')
  },
})
const libraryOptions = computed(() => (availableLibraries.value[selectedProfileId.value] || []).map(item => ({
  title: item.name,
  value: item.id,
})))
const selectedLibraryIds = computed({
  get: () => {
    const profileId = selectedProfileId.value
    if (!profileId) return []
    if (Object.prototype.hasOwnProperty.call(form.emby_library_ids || {}, profileId)) return form.emby_library_ids[profileId] || []
    return libraryOptions.value.map(item => item.value)
  },
  set: libraryIds => {
    if (!selectedProfileId.value) return
    form.emby_library_ids = { ...(form.emby_library_ids || {}), [selectedProfileId.value]: [...(libraryIds || [])] }
  },
})
const latestMetrics = computed(() => overview.value?.latest_run?.metrics || {})
const currentPlayback = computed(() => overview.value?.playback || status.value.playback || null)
const currentEnablement = computed(() => overview.value?.enablement || status.value.enablement || null)
const runtimeStateText = computed(() => ({ ready: '运行中', blocked: '已阻断', stopped: '已停用' })[status.value.state] || '未知状态')
const runtimeStateColor = computed(() => ({ ready: 'success', blocked: 'error', stopped: 'default' })[status.value.state] || 'warning')
const playbackMappingRate = computed(() => {
  const mapped = Number(currentPlayback.value?.mapped_count || 0)
  const total = mapped + Number(currentPlayback.value?.unmapped_count || 0)
  return total ? `${Math.round((mapped / total) * 100)}%` : '-'
})
const candidateSourceEntries = computed(() => Object.entries(latestMetrics.value.candidate_source_counts || {}).map(([key, value]) => [sourceLabel(key), value]))
const candidateExclusionEntries = computed(() => Object.entries(latestMetrics.value.candidate_exclusion_counts || {}).map(([key, value]) => [exclusionLabel(key), value]))
const sourceErrorEntries = computed(() => Object.entries(latestMetrics.value.source_errors || {}))
const sourceErrorsText = computed(() => sourceErrorEntries.value.map(([key, value]) => `${sourceLabel(key)}：${value}`).join('；'))
const retrievalFilterEntries = computed(() => Object.entries(overview.value?.profile?.filters || {}).map(([key, value]) => [filterLabel(key), formatFilterValue(key, value)]))
const pipelineSteps = [
  { key: 'probe', title: '探测依赖' },
  { key: 'playback_snapshot', title: '冻结播放' },
  { key: 'profile', title: '生成画像' },
  { key: 'candidate', title: '冻结候选' },
  { key: 'ranking', title: '池内排序' },
  { key: 'save', title: '校验保存' },
]

const sourceDefs = computed(() => {
  const runtimeOptions = sourceOptions.value.filter(item => item && item.available !== false)
  const keys = runtimeOptions.length
    ? runtimeOptions.map(item => item.key)
    : Object.keys(defaults.discovery_sources)
  return keys.map(key => ({
    key,
    ...(sourceMeta[key] || {
      title: '其他来源',
      subtitle: 'MoviePilot 内置来源',
      icon: 'mdi-database-outline',
    }),
  }))
})

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
}
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
}
const sourceLabels = { douban: '豆瓣发现', tmdb: 'TMDB', tmdb_recommend: 'TMDB 推荐', tmdb_movies: 'TMDB 电影', tmdb_tv: 'TMDB 剧集', bangumi: 'Bangumi', anilist: 'AniList' }
const exclusionLabels = { invalid_or_unrecognized: '无效或未识别', watched: '已观看', watched_completed: '已看完', library: '已入库', subscribed: '已订阅', disliked: '已点踩', archived: '已忽略', negative_keyword: '避雷命中', ambiguous_playback_count: '播放次数误写为看完次数', unsupported_playback_claim: '观看经历无法回溯' }
const mediaTypeLabels = { movie: '电影', tv: '剧集', anime: '动漫' }
const languageLabels = { zh: '中文', ja: '日语', ko: '韩语', en: '英语', fr: '法语', de: '德语', es: '西班牙语', it: '意大利语', ru: '俄语', th: '泰语' }
const sortLabels = { 'popularity.desc': '热度降序', 'vote_average.desc': '评分降序', 'primary_release_date.desc': '上映日期降序', 'first_air_date.desc': '首播日期降序' }
function sourceLabel(value) { return sourceLabels[value] || '其他来源' }
function exclusionLabel(value) { return exclusionLabels[value] || '其他排除原因' }
function filterLabel(value) { return filterLabels[value] || '其他条件' }
function formatFilterValue(key, value) {
  if (key === 'media_types' && Array.isArray(value)) return value.map(item => mediaTypeLabels[item] || '其他类型')
  if ((key === 'original_languages' || key === 'languages') && Array.isArray(value)) return value.map(item => {
    const legacyLabel = languageLabels[item] || item
    return languageLabels[item] ? legacyLabel : '其他语言'
  })
  if (key === 'sort_by') return sortLabels[value] || '其他排序'
  return value
}
function formatDateTime(value) {
  if (!value) return '尚未同步'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function subTabActive(key) {
  if (activeMain.value === 'profile') return activeProfile.value === key
  if (activeMain.value === 'strategy') return activeStrategy.value === key
  return activeAdvanced.value === key
}

function selectSubTab(key) {
  if (activeMain.value === 'profile') activeProfile.value = key
  else if (activeMain.value === 'strategy') activeStrategy.value = key
  else activeAdvanced.value = key
}

function stageStatus(step) {
  const value = latestMetrics.value.stage_status?.[step.key] || ''
  return stageLabels[value] || '未记录'
}

function stageDuration(step) {
  const value = Number(latestMetrics.value.stage_ms?.[step.key])
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
  const next = cloneConfig(value)
  const legacyPrompt = String(next.agent_prompt || '').trim()
  if (legacyPrompt && !legacyAgentPromptDefaults.has(legacyPrompt)) {
    if (!next.profile_prompt) next.profile_prompt = legacyPrompt
    if (!next.ranking_prompt) next.ranking_prompt = legacyPrompt
  }
  delete next.agent_prompt
  Object.assign(form, cloneConfig(defaults), next)
  form.playback_enabled = true
  form.weights = { ...weightDefaults, ...(next.weights || {}) }
  const sourceKeys = new Set([
    ...Object.keys(defaults.discovery_sources),
    ...Object.keys(next.discovery_sources || {}),
    ...sourceOptions.value.map(item => item.key),
  ])
  form.discovery_sources = Object.fromEntries(
    [...sourceKeys].map(key => [
      key,
      Boolean(next.discovery_sources?.[key] ?? defaults.discovery_sources[key] ?? false),
    ]),
  )
  form.emby_identities = Array.isArray(next.emby_identities)
    ? next.emby_identities.filter(identity => identity?.profile_id)
    : []
  form.default_profile_id = next.default_profile_id || form.emby_identities[0]?.profile_id || ''
  form.emby_library_ids = next.emby_library_ids && typeof next.emby_library_ids === 'object'
    ? cloneConfig(next.emby_library_ids)
    : {}
  form.profile_access_map = next.profile_access_map && typeof next.profile_access_map === 'object'
    ? Object.fromEntries(Object.entries(next.profile_access_map).map(([userId, profileIds]) => [
      String(userId),
      Array.isArray(profileIds) ? [...profileIds] : [],
    ]))
    : {}
  delete form.media_types
  delete form.exclude_keywords
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true })
async function loadOverview(profileId = selectedProfileId.value) {
  if (!props.api?.get || !profileId) {
    overview.value = null
    return
  }
  overview.value = await getPluginApi(props.api, 'overview', { profile_id: profileId })
}

async function loadMoviePilotUsers() {
  if (!props.api?.get) return
  accessLoading.value = true
  accessError.value = ''
  try {
    const users = await getHostApi(props.api, 'user/')
    moviePilotUsers.value = (Array.isArray(users) ? users : [])
      .filter(user => user?.id != null && user?.is_active !== false)
      .map(user => ({
        id: String(user.id),
        name: String(user.name || `用户 ${user.id}`),
        is_superuser: user.is_superuser === true,
      }))
      .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
  } catch (error) {
    accessError.value = error?.message || 'MoviePilot 用户列表加载失败'
  } finally {
    accessLoading.value = false
  }
}

async function loadRuntime() {
  if (!props.api?.get) return
  loading.value = true
  loadError.value = ''
  try {
    const [statusData, optionsData] = await Promise.all([
      getPluginApi(props.api, 'status'),
      getPluginApi(props.api, 'config/options'),
    ])
    status.value = statusData || status.value
    availableIdentities.value = Array.isArray(optionsData?.emby_identities) ? optionsData.emby_identities : []
    availableLibraries.value = optionsData?.emby_libraries && typeof optionsData.emby_libraries === 'object' ? optionsData.emby_libraries : {}
    sourceOptions.value = Array.isArray(optionsData?.source_options) ? optionsData.source_options : []
    runtimeDefaults.value = { ...structuredClone(defaults), ...(optionsData?.defaults || {}) }
    applyConfig(optionsData?.config || props.initialConfig)
    await Promise.all([
      loadOverview(optionsData?.default_profile_id || selectedProfileId.value),
      loadMoviePilotUsers(),
    ])
  } catch (error) {
    loadError.value = error?.message || '运行信息加载失败'
  } finally {
    loading.value = false
  }
}

function saveConfig() {
  const payload = cloneConfig(form)
  const configuredProfiles = new Set(payload.emby_identities.map(identity => identity.profile_id))
  payload.profile_access_map = Object.fromEntries(
    Object.entries(payload.profile_access_map || {})
      .map(([userId, profileIds]) => [
        String(userId),
        [...new Set((profileIds || []).filter(profileId => configuredProfiles.has(profileId)))],
      ])
      .filter(([, profileIds]) => profileIds.length),
  )
  delete payload._validation_errors
  emit('save', payload)
}

function setProfileAccess(userId, profileIds) {
  const key = String(userId)
  const allowed = new Set(form.emby_identities.map(identity => identity.profile_id))
  const selected = [...new Set((profileIds || []).filter(profileId => allowed.has(profileId)))]
  const next = { ...(form.profile_access_map || {}) }
  if (selected.length) next[key] = selected
  else delete next[key]
  form.profile_access_map = next
}

function showActionFeedback(color, message) {
  actionFeedback.color = color
  actionFeedback.message = message
  actionFeedback.show = true
}

async function exportProfileData() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'export'
  try {
    const data = await getPluginApi(props.api, 'data/export', { profile_id: selectedProfileId.value })
    const content = JSON.stringify(data, null, 2)
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    const label = String(selectedIdentity.value?.username || selectedProfileId.value).replace(/[^A-Za-z0-9._-]+/g, '_')
    anchor.href = href
    anchor.download = `agentrank-${label || 'profile'}-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(href)
    showActionFeedback('success', '脱敏数据已导出')
  } catch (error) {
    showActionFeedback('error', error?.message || '数据导出失败')
  } finally {
    dataActionLoading.value = ''
  }
}

async function confirmLearningReset() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'learning'
  try {
    await postPluginApi(props.api, 'data/reset/learning', {
      profile_id: selectedProfileId.value,
      confirm: true,
    })
    learningResetDialog.value = false
    await loadOverview(selectedProfileId.value)
    showActionFeedback('success', '学习数据已重置，播放记录、榜单、归档和人工标签已保留')
  } catch (error) {
    showActionFeedback('error', error?.message || '学习重置失败')
  } finally {
    dataActionLoading.value = ''
  }
}

function openFullReset() {
  fullResetStage.value = 'prepare'
  fullResetPhrase.value = ''
  fullResetConfirmation.value = null
  fullResetDialog.value = true
}

function closeFullReset() {
  if (dataActionLoading.value) return
  fullResetDialog.value = false
  fullResetStage.value = 'prepare'
  fullResetPhrase.value = ''
  fullResetConfirmation.value = null
}

async function prepareFullReset() {
  if (!selectedProfileId.value || dataActionLoading.value) return
  dataActionLoading.value = 'full-prepare'
  try {
    fullResetConfirmation.value = await postPluginApi(props.api, 'data/reset/full/prepare', {
      profile_id: selectedProfileId.value,
    })
    fullResetStage.value = 'confirm'
  } catch (error) {
    showActionFeedback('error', error?.message || '无法准备彻底重置')
  } finally {
    dataActionLoading.value = ''
  }
}

async function confirmFullReset() {
  if (fullResetPhrase.value !== '彻底重置' || !fullResetConfirmation.value?.confirmation_token || dataActionLoading.value) return
  dataActionLoading.value = 'full-reset'
  try {
    await postPluginApi(props.api, 'data/reset/full', {
      profile_id: selectedProfileId.value,
      confirmation_token: fullResetConfirmation.value.confirmation_token,
    })
    fullResetDialog.value = false
    fullResetStage.value = 'prepare'
    fullResetPhrase.value = ''
    fullResetConfirmation.value = null
    await loadOverview(selectedProfileId.value)
    showActionFeedback('success', 'AgentRank 当前画像数据已彻底重置，MoviePilot 订阅和媒体库未受影响')
  } catch (error) {
    showActionFeedback('error', error?.message || '彻底重置失败')
  } finally {
    dataActionLoading.value = ''
  }
}

async function syncPlayback() {
  if (!props.api?.post || !selectedProfileId.value) return
  loading.value = true
  try {
    const snapshot = await postPluginApi(props.api, 'playback/sync', { profile_id: selectedProfileId.value })
    status.value = { ...status.value, playback: snapshot }
    await loadOverview(selectedProfileId.value)
    actionFeedback.show = true
    actionFeedback.color = snapshot?.status === 'ready' || snapshot?.status === 'cached' ? 'success' : 'warning'
    actionFeedback.message = snapshot?.message || '播放画像同步完成'
  } catch (error) {
    actionFeedback.show = true
    actionFeedback.color = 'error'
    actionFeedback.message = error?.message || '播放画像同步失败'
  } finally {
    loading.value = false
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
  }
  return labels[snapshot?.status] || snapshot?.status || '尚未同步'
}

function promptSummary(key) {
  return String(form[key] || '').replace(/\s+/g, ' ').trim() || '尚未设置'
}

function openPromptEditor(definition) {
  promptEditor.key = definition.key
  promptEditor.draft = String(form[definition.key] || defaults[definition.key] || '')
  promptEditor.open = true
}

function restorePromptEditor() {
  const key = promptEditor.key
  promptEditor.draft = String(runtimeDefaults.value[key] || defaults[key] || '')
}

function cancelPromptEditor() {
  promptEditor.open = false
  promptEditor.key = ''
  promptEditor.draft = ''
}

function applyPromptEditor() {
  const value = promptEditor.draft.trim()
  if (!value || value.length > 4000) return
  form[promptEditor.key] = value
  cancelPromptEditor()
}

function requestClearProfile(value) {
  if (!value) return
  if (!selectedProfileId.value) {
    clearProfileSwitch.value = false
    actionFeedback.show = true
    actionFeedback.color = 'warning'
    actionFeedback.message = '请先选择默认 Emby 画像身份'
    return
  }
  clearProfileDialog.value = true
}

function cancelClearProfile() {
  clearProfileDialog.value = false
  clearProfileSwitch.value = false
}

async function confirmClearProfile() {
  clearProfileLoading.value = true
  try {
    await postPluginApi(props.api, 'profile/clear', { profile_id: selectedProfileId.value, confirm: true })
    actionFeedback.color = 'success'
    actionFeedback.message = `${selectedIdentity.value?.username || selectedProfileId.value} 的画像与榜单已清除`
    await loadOverview(selectedProfileId.value)
  } catch (error) {
    actionFeedback.color = 'error'
    actionFeedback.message = error?.message || '清除画像失败'
  } finally {
    actionFeedback.show = true
    clearProfileLoading.value = false
    clearProfileDialog.value = false
    clearProfileSwitch.value = false
  }
}

onMounted(loadRuntime)
</script>

<template>
  <div class="ar-config">
    <VCard flat class="ar-config__card">
      <VCardItem class="ar-config__header">
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-brain" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">Agent榜单中心</VCardTitle>
        <VCardSubtitle>{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <div class="ar-config__header-state">
            <VChip :color="runtimeStateColor" variant="tonal" size="small">{{ runtimeStateText }}</VChip>
            <VSwitch v-model="form.enabled" color="success" hide-details inset label="启用插件" />
          </div>
        </template>
      </VCardItem>
      <VDivider />

      <div class="ar-config__body">
        <nav class="ar-config__nav" aria-label="Agent榜单配置导航">
          <VList density="comfortable" nav class="ar-config__nav-list py-2">
            <VListItem
              v-for="item in mainTabs"
              :key="item.key"
              :active="activeMain === item.key"
              color="primary"
              rounded="lg"
              class="ar-config__nav-item"
              @click="activeMain = item.key"
            >
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>

        <section class="ar-config__content">
          <div v-if="currentSubTabs.length" class="ar-config__subtabs">
            <button
              v-for="item in currentSubTabs"
              :key="item.key"
              class="ar-config__subtab"
              :class="{ 'ar-config__subtab--active': subTabActive(item.key) }"
              type="button"
              @click="selectSubTab(item.key)"
            >
              <VIcon :icon="item.icon" size="18" class="mr-1" />{{ item.title }}
            </button>
          </div>
          <VDivider />

          <div class="ar-config__window" :class="{ 'ar-config__window--overview': activeMain === 'overview' }">
            <div v-show="activeMain === 'overview'" class="ar-config__pane ar-config__pane--overview">
              <div class="ar-config__section-title">运行链路步骤</div>
              <div class="ar-config__pipeline">
                <div v-for="(step, index) in pipelineSteps" :key="step.key" class="ar-config__step">
                  <VAvatar size="28" color="primary" variant="tonal">{{ index + 1 }}</VAvatar>
                  <div class="ar-config__step-copy">
                    <span>{{ step.title }}</span>
                    <small>{{ stageStatus(step) || '待运行' }}<template v-if="stageDuration(step)"> · {{ stageDuration(step) }}</template></small>
                  </div>
                </div>
              </div>
              <VAlert
                v-if="currentEnablement && !currentEnablement.allowed && currentEnablement.status !== 'disabled'"
                type="error"
                variant="tonal"
                density="compact"
                class="mt-3"
                icon="mdi-alert-octagon-outline"
              >
                <strong>Playback Reporting 硬依赖未满足</strong>：{{ currentEnablement.message || '插件无法启用' }}
              </VAlert>
              <div class="ar-config__overview-grid">
                <div class="ar-config__overview-panel">
                  <div class="ar-config__panel-head">
                    <span>播放样本</span>
                    <VChip :color="['ready', 'cached'].includes(currentPlayback?.status) ? 'success' : 'warning'" variant="tonal" size="x-small">{{ playbackStatusText(currentPlayback) }}</VChip>
                  </div>
                  <div class="ar-config__stats">
                    <span>样本 <strong>{{ currentPlayback?.sample_count || 0 }}</strong></span>
                    <span>映射 <strong>{{ currentPlayback?.mapped_count || 0 }}</strong></span>
                    <span>映射率 <strong>{{ playbackMappingRate }}</strong></span>
                    <span>未映射 <strong>{{ currentPlayback?.unmapped_count || 0 }}</strong></span>
                  </div>
                  <div class="ar-config__hint">{{ selectedIdentity?.username || '未选择用户' }} · {{ formatDateTime(currentPlayback?.synced_at) }}</div>
                </div>
                <div class="ar-config__overview-panel">
                  <div class="ar-config__panel-head"><span>画像版本</span><VChip size="x-small" variant="outlined">结构 {{ overview?.profile?.schema_version || '-' }}</VChip></div>
                  <div class="ar-config__hint">检索解析版本 {{ overview?.profile?.retrieval_resolution_version || '-' }} · 播放证据 {{ overview?.profile?.playback_count || 0 }} 条</div>
                  <div class="ar-config__tag-row">
                    <VChip v-for="tag in overview?.profile?.ranking_tags || []" :key="tag" size="x-small" variant="tonal" color="primary">{{ tag }}</VChip>
                    <span v-if="!(overview?.profile?.ranking_tags || []).length" class="ar-config__empty">暂无排序标签</span>
                  </div>
                </div>
                <div class="ar-config__overview-panel">
                  <div class="ar-config__panel-head"><span>检索计划</span><small>{{ retrievalFilterEntries.length }} 项过滤</small></div>
                  <div class="ar-config__metric-list">
                    <span v-for="([key, value]) in retrievalFilterEntries" :key="key"><b>{{ key }}</b>{{ displayValue(value) }}</span>
                    <span v-if="!retrievalFilterEntries.length" class="ar-config__empty">暂无已解析过滤条件</span>
                  </div>
                </div>
                <div class="ar-config__overview-panel">
                  <div class="ar-config__panel-head"><span>冻结候选</span><small>{{ latestMetrics.candidate_count || 0 }} 项</small></div>
                  <div class="ar-config__metric-columns">
                    <div>
                      <small>候选来源</small>
                      <span v-for="([key, value]) in candidateSourceEntries" :key="key">{{ key }} <b>{{ value }}</b></span>
                      <span v-if="!candidateSourceEntries.length" class="ar-config__empty">暂无统计</span>
                    </div>
                    <div>
                      <small>排除统计</small>
                      <span v-for="([key, value]) in candidateExclusionEntries" :key="key">{{ key }} <b>{{ value }}</b></span>
                      <span v-if="!candidateExclusionEntries.length" class="ar-config__empty">暂无统计</span>
                    </div>
                  </div>
                  <div v-if="sourceErrorEntries.length" class="ar-config__source-errors">
                    <VIcon icon="mdi-alert-circle-outline" size="15" color="warning" />
                    <span>{{ sourceErrorsText }}</span>
                  </div>
                </div>
              </div>
              <VAlert v-if="loadError" type="error" variant="tonal" class="mt-3">{{ loadError }}</VAlert>
              <VAlert v-if="status.validation_errors?.length" type="warning" variant="tonal" class="mt-3">
                <div v-for="item in status.validation_errors" :key="item">{{ item }}</div>
              </VAlert>
              <div class="ar-config__overview-foot">
                <VIcon icon="mdi-shield-refresh-outline" size="17" color="primary" />
                <span>Agent、候选或保存失败时保留旧画像与旧榜单，不执行订阅。</span>
                <VChip v-if="overview?.latest_run?.status" size="x-small" variant="outlined">最近运行 {{ runStatusText(overview.latest_run.status) }}</VChip>
              </div>
            </div>

            <div v-show="activeMain === 'basic'" class="ar-config__pane">
              <div class="ar-config__section-title">基础设置</div>
              <VRow>
                <VCol cols="12" md="4"><VSelect v-model="selectedServerName" :items="serverOptions" label="媒体库（Emby 服务实例）" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VSelect v-model="selectedUserProfileId" :items="userOptions" label="用户" density="compact" variant="outlined" hide-details :disabled="!selectedServerName" /></VCol>
                <VCol cols="12" md="4"><VAutocomplete v-model="selectedLibraryIds" :items="libraryOptions" label="内容库筛选" multiple chips closable-chips density="compact" variant="outlined" hide-details :disabled="!selectedUserProfileId" /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.onlyonce" color="warning" label="立即运行一次" hide-details inset :disabled="!form.enabled || !form.emby_identities.length || currentEnablement?.allowed === false" /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.schedule_enabled" color="success" label="周期运行" hide-details inset /></VCol>
                <VCol cols="12" md="4"><VCronField v-model="form.cron" label="运行周期" density="compact" variant="outlined" hide-details :disabled="!form.schedule_enabled" /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.discovery_page_enabled" color="success" label="开启发现页" hide-details inset /></VCol>
                <VCol cols="12" md="4"><VSelect v-model="form.action_mode" :items="actionOptions" label="动作模式" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.auto_subscribe_top_n" type="number" min="0" :max="form.auto_subscribe_limit" label="自动订阅前几名" density="compact" variant="outlined" hide-details :disabled="form.action_mode !== 'auto_subscribe'" /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.auto_subscribe_limit" type="number" min="0" max="10" label="安全上限" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.notify" color="info" label="发送通知" hide-details inset :disabled="form.action_mode === 'update'" /></VCol>
                <VCol cols="12" md="8">
                  <div class="text-caption mb-1">订阅门槛 · 最低支持度 {{ Math.round(form.confidence_threshold * 100) }}%</div>
                  <VSlider v-model="form.confidence_threshold" :min="0" :max="1" :step="0.05" color="primary" hide-details thumb-label />
                </VCol>
              </VRow>
              <VAlert type="info" variant="tonal" class="mt-4">Emby 画像身份由服务实例与用户组成；画像只同步所选用户在所选内容库中的 Playback Reporting 记录，未安装或不可访问时插件保持停用。</VAlert>
              <VAlert :type="form.action_mode === 'auto_subscribe' ? 'warning' : 'info'" variant="tonal" class="mt-3">
                {{ form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、最低支持度、识别 ID 和重复订阅。' : '最低支持度只限制订阅，不过滤榜单；通知模式由用户在消息中确认后执行。' }}
              </VAlert>
            </div>

            <div v-show="activeMain === 'profile' && activeProfile === 'playback'" class="ar-config__pane">
              <div class="d-flex align-center mb-3">
                <div class="ar-config__section-title mb-0">播放画像</div>
                <VSpacer />
                <VBtn size="small" variant="tonal" color="primary" prepend-icon="mdi-sync" :loading="loading" :disabled="!form.enabled || !selectedProfileId" @click="syncPlayback">同步数据</VBtn>
              </div>
              <VAlert
                :type="['ready', 'cached'].includes(currentPlayback?.status) ? 'success' : currentEnablement?.allowed === false ? 'error' : 'info'"
                variant="tonal"
                class="mb-4"
              >
                <div class="d-flex align-center flex-wrap ga-2">
                  <strong>{{ playbackStatusText(currentPlayback) }}</strong>
                  <VChip v-if="currentPlayback?.source" size="x-small" variant="outlined">{{ playbackSourceLabel(currentPlayback.source) }}</VChip>
                  <VChip v-if="currentPlayback?.confidence" size="x-small" variant="outlined">{{ playbackConfidenceLabel(currentPlayback.confidence) }}</VChip>
                </div>
                <div class="mt-1">{{ currentEnablement?.message || currentPlayback?.message || 'Playback Reporting 是硬依赖；未安装或无权限时插件无法开启。' }}</div>
                <div v-if="currentPlayback?.synced_at" class="text-caption mt-1">最近同步：{{ formatDateTime(currentPlayback.synced_at) }} · 样本 {{ currentPlayback.sample_count || 0 }} · 已映射 {{ currentPlayback.mapped_count || 0 }} · 未映射 {{ currentPlayback.unmapped_count || 0 }}</div>
              </VAlert>
              <VRow>
                <VCol cols="12" md="4"><VTextField v-model.number="form.playback_recent_days" type="number" min="1" max="3650" label="回溯天数" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.playback_abandon_minutes" type="number" min="1" max="240" label="弃看分钟" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.playback_cache_days" type="number" min="1" max="30" label="快照天数" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12">
                  <div class="text-caption mb-1">完播阈值 {{ Math.round(form.playback_completion_threshold * 100) }}%</div>
                  <VSlider v-model="form.playback_completion_threshold" :min="0.5" :max="1" :step="0.05" color="primary" hide-details thumb-label />
                </VCol>
              </VRow>
              <VAlert type="info" variant="tonal" class="mt-4">播放样本只来自 Playback Reporting；未就绪时插件保持停用，不会切换到其他画像来源。</VAlert>
            </div>

            <div v-show="activeMain === 'profile' && activeProfile === 'policy'" class="ar-config__pane">
              <div class="ar-config__section-title">画像策略</div>
              <VRow>
                <VCol cols="12" md="4"><VSwitch v-model="form.profile_cache_enabled" color="success" label="画像缓存" hide-details inset /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.rebuild_profile_each_run" color="warning" label="每次重建" hide-details inset /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.minimum_samples" type="number" min="1" max="100" label="最少样本" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
              <VAlert type="info" variant="tonal" class="mt-4">画像缓存开启且关闭每次重建时，会在播放快照未变化时复用当前画像；每次重建开启或缓存关闭时，按冻结的 Playback Reporting 快照重新生成。媒体类型由播放事实、明确反馈和可撤销画像标签学习；偏好标签与避雷标签是用户修正画像的统一入口。</VAlert>
              <div class="ar-config__danger-row mt-4">
                <div>
                  <div class="ar-config__danger-title">清除画像</div>
                  <div class="ar-config__hint">清除默认画像身份“{{ selectedIdentity?.username || '未选择' }}”的画像与榜单，不影响 MoviePilot 订阅和归档。</div>
                </div>
                <VSwitch v-model="clearProfileSwitch" color="error" label="清除画像" hide-details inset :disabled="clearProfileLoading" @update:model-value="requestClearProfile" />
              </div>
            </div>

            <div v-show="activeMain === 'strategy' && activeStrategy === 'sources'" class="ar-config__pane">
              <div class="ar-config__section-title">发现来源</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-4">来源列表会探测已适配的 MoviePilot 能力（包括 AniList）；宿主未来新增但未声明统一契约的来源不会被自动执行，需完成安全适配后才会显示。</VAlert>
              <div class="ar-config__source-grid">
                <VCard v-for="source in sourceDefs" :key="source.key" variant="outlined" class="ar-config__source-card">
                  <VCardItem>
                    <template #prepend><VAvatar color="primary" variant="tonal" size="36"><VIcon :icon="source.icon" /></VAvatar></template>
                    <VCardTitle class="text-subtitle-2">{{ source.title }}</VCardTitle>
                    <VCardSubtitle>{{ source.subtitle }}</VCardSubtitle>
                    <template #append><VSwitch v-model="form.discovery_sources[source.key]" color="success" hide-details inset :aria-label="`启用${source.title}`" /></template>
                  </VCardItem>
                </VCard>
              </div>
            </div>

            <div v-show="activeMain === 'strategy' && activeStrategy === 'weights'" class="ar-config__pane">
              <div class="ar-config__section-title">权重设置</div>
              <VAlert type="info" variant="tonal" class="mb-4">Config 是权重唯一写入口；数值越高，Agent 排序时越重视该维度。</VAlert>
              <div class="ar-config__weight-grid">
                <div v-for="weight in weightDefs" :key="weight.key" class="ar-config__weight-item">
                  <div class="d-flex align-center mb-1">
                    <VIcon :icon="weight.icon" size="18" color="primary" class="mr-2" />
                    <span class="text-body-2 font-weight-medium">{{ weight.title }}</span>
                    <VSpacer />
                    <VChip size="x-small" variant="tonal" color="primary">{{ Number(form.weights[weight.key]).toFixed(1) }}</VChip>
                  </div>
                  <VSlider v-model="form.weights[weight.key]" :min="0" :max="1" :step="0.1" color="primary" hide-details thumb-label />
                  <div class="ar-config__default">默认 {{ weightDefaults[weight.key].toFixed(1) }}</div>
                </div>
              </div>
            </div>

            <div v-show="activeMain === 'advanced'" class="ar-config__pane">
              <template v-if="activeAdvanced === 'runtime'">
                <div class="ar-config__section-title">运行参数</div>
                <VRow>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.candidate_pool_size" type="number" min="10" max="500" label="候选池数量" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.history_limit" type="number" min="1" max="200" label="历史上限" density="compact" variant="outlined" hide-details /></VCol>
                </VRow>
                <VAlert type="info" variant="tonal" class="mt-4">候选池数量控制每轮冻结候选容量；它是运行参数，不代表内容偏好，也不会改变最低支持度的订阅边界。</VAlert>
              </template>
              <template v-else-if="activeAdvanced === 'access'">
                <div class="ar-config__section-title">访问控制</div>
                <VAlert type="info" variant="tonal" density="compact" class="mb-4">
                  超级用户始终可访问全部已配置画像；普通用户只有在此明确授权后才能读取或操作对应画像。
                </VAlert>
                <VAlert v-if="accessError" type="error" variant="tonal" density="compact" class="mb-4">
                  <div class="ar-config__inline-alert">
                    <span>{{ accessError }}</span>
                    <VBtn variant="text" size="small" prepend-icon="mdi-refresh" :loading="accessLoading" @click="loadMoviePilotUsers">重试</VBtn>
                  </div>
                </VAlert>
                <div v-if="accessLoading && !moviePilotUsers.length" class="ar-config__loading-state">
                  <VProgressCircular indeterminate color="primary" size="28" />
                  <span>正在读取 MoviePilot 用户</span>
                </div>
                <div v-else class="ar-config__access-list">
                  <div
                    v-for="user in moviePilotUsers.filter(item => !item.is_superuser)"
                    :key="user.id"
                    class="ar-config__access-row"
                  >
                    <VAvatar color="info" variant="tonal" size="36"><VIcon icon="mdi-account-outline" size="20" /></VAvatar>
                    <div class="ar-config__access-user">
                      <strong>{{ user.name }}</strong>
                      <small>MoviePilot 用户 {{ user.id }}</small>
                    </div>
                    <VSelect
                      :model-value="form.profile_access_map[user.id] || []"
                      :items="profileAccessOptions"
                      label="允许访问的画像"
                      multiple
                      chips
                      closable-chips
                      density="compact"
                      variant="outlined"
                      hide-details
                      :disabled="!profileAccessOptions.length"
                      @update:model-value="setProfileAccess(user.id, $event)"
                    />
                  </div>
                  <div v-if="!moviePilotUsers.some(item => !item.is_superuser)" class="ar-config__empty-state">
                    <VIcon icon="mdi-account-check-outline" size="28" color="primary" />
                    <span>当前没有需要单独授权的普通用户</span>
                  </div>
                </div>
              </template>
              <template v-else-if="activeAdvanced === 'data'">
                <div class="ar-config__section-title">数据保留</div>
                <div class="ar-config__retention-grid">
                  <div v-for="item in retentionDefinitions" :key="item.key" class="ar-config__retention-item">
                    <VTextField
                      v-model.number="form[item.key]"
                      :label="item.title"
                      type="number"
                      min="1"
                      :max="item.max"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                    <div class="ar-config__hint">{{ item.hint }}</div>
                  </div>
                </div>
                <div class="ar-config__hint mt-2">保留上限随“保存配置”生效，已有数据会在运行时按前缀安全裁剪。</div>

                <div class="ar-config__section-title mt-5">数据操作</div>
                <div class="ar-config__data-actions">
                  <div class="ar-config__data-row">
                    <VAvatar color="info" variant="tonal" size="38"><VIcon icon="mdi-download-outline" size="21" /></VAvatar>
                    <div><strong>导出脱敏数据</strong><small>画像、反馈、记忆、分析、对话和归因</small></div>
                    <VBtn variant="tonal" color="info" prepend-icon="mdi-download-outline" :loading="dataActionLoading === 'export'" :disabled="!selectedProfileId" @click="exportProfileData">导出</VBtn>
                  </div>
                  <div class="ar-config__data-row">
                    <VAvatar color="warning" variant="tonal" size="38"><VIcon icon="mdi-brain" size="21" /></VAvatar>
                    <div><strong>学习重置</strong><small>清除反馈学习、确认记忆、对话与归因</small></div>
                    <VBtn variant="tonal" color="warning" prepend-icon="mdi-backup-restore" :disabled="!selectedProfileId" @click="learningResetDialog = true">重置</VBtn>
                  </div>
                  <div class="ar-config__data-row ar-config__data-row--danger">
                    <VAvatar color="error" variant="tonal" size="38"><VIcon icon="mdi-delete-alert-outline" size="21" /></VAvatar>
                    <div><strong>彻底重置</strong><small>删除当前画像下全部 AgentRank 自有数据</small></div>
                    <VBtn variant="tonal" color="error" prepend-icon="mdi-delete-alert-outline" :disabled="!selectedProfileId" @click="openFullReset">重置</VBtn>
                  </div>
                </div>
                <VAlert type="info" variant="tonal" density="compact" class="mt-4">两类重置都不会删除 MoviePilot 订阅、订阅任务或媒体库文件。</VAlert>
              </template>
              <template v-else>
                <div class="ar-config__section-title">提示设置</div>
                <div class="ar-config__prompt-list">
                  <div v-for="definition in promptDefinitions" :key="definition.key" class="ar-config__prompt-row">
                    <VAvatar color="primary" variant="tonal" size="38" rounded="lg">
                      <VIcon :icon="definition.icon" size="20" />
                    </VAvatar>
                    <div class="ar-config__prompt-copy">
                      <div class="ar-config__prompt-title">{{ definition.title }}</div>
                      <div class="ar-config__prompt-purpose">{{ definition.purpose }}</div>
                      <div class="ar-config__prompt-summary">{{ promptSummary(definition.key) }}</div>
                    </div>
                    <VBtn variant="tonal" color="primary" size="small" prepend-icon="mdi-pencil-outline" @click="openPromptEditor(definition)">编辑</VBtn>
                  </div>
                </div>
                <VExpansionPanels variant="accordion" class="mt-4 ar-config__fixed-rules">
                  <VExpansionPanel>
                    <VExpansionPanelTitle>
                      <VIcon icon="mdi-shield-lock-outline" color="primary" size="20" class="me-2" />
                      固定安全规则（只读）
                    </VExpansionPanelTitle>
                    <VExpansionPanelText>
                      <ul class="ar-config__rule-list">
                        <li>Agent 只能读取本轮受限工具数据，不能订阅、写数据、改配置或调用消息与文件能力。</li>
                        <li>已删除标签进入归档，画像和排序不得恢复、引用或换用近义标签规避。</li>
                        <li>观看动机只能作为软排序信号；不得推断人格、焦虑、孤独、疾病或创伤，也不得输出心理诊断。</li>
                        <li>画像与榜单必须返回插件规定的 JSON Schema，额外字段和非法候选会被拒绝。</li>
                        <li>推荐理由和简介必须各自总结为三十字内的完整短句，禁止按字符截断。</li>
                        <li>成功生成的最终榜单固定保存五条；排序校验未满时只从冻结候选池安全补位。</li>
                      </ul>
                    </VExpansionPanelText>
                  </VExpansionPanel>
                </VExpansionPanels>
              </template>
            </div>
          </div>
        </section>
      </div>

      <VDivider />
      <VCardActions class="ar-config__actions">
        <VProgressCircular v-if="loading" indeterminate size="20" width="2" color="primary" />
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>

    <VDialog v-model="promptEditor.open" width="min(720px, calc(100vw - 24px))" persistent>
      <VCard class="ar-config__prompt-dialog">
        <VCardItem>
          <template #prepend>
            <VAvatar color="primary" variant="tonal" size="40" rounded="lg">
              <VIcon :icon="activePromptDefinition.icon" size="21" />
            </VAvatar>
          </template>
          <VCardTitle>{{ activePromptDefinition.title }}</VCardTitle>
          <VCardSubtitle class="ar-config__prompt-dialog-subtitle">{{ activePromptDefinition.purpose }}</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="ar-config__prompt-dialog-body">
          <VTextarea
            v-model="promptEditor.draft"
            label="提示词内容"
            variant="outlined"
            rows="12"
            counter="4000"
            maxlength="4000"
            auto-grow
            hide-details="auto"
          />
          <div class="ar-config__prompt-dialog-hint">应用后只更新当前表单，点击配置页“保存配置”后才会持久化。</div>
        </VCardText>
        <VDivider />
        <VCardActions>
          <VBtn variant="text" prepend-icon="mdi-restore" @click="restorePromptEditor">恢复默认</VBtn>
          <VSpacer />
          <VBtn variant="text" @click="cancelPromptEditor">取消</VBtn>
          <VBtn color="primary" variant="flat" :disabled="!promptEditor.draft.trim() || promptEditor.draft.length > 4000" @click="applyPromptEditor">应用</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="clearProfileDialog" max-width="480" persistent>
      <VCard>
        <VCardTitle>清除用户画像？</VCardTitle>
        <VCardText>
          将清除“{{ selectedIdentity?.username || selectedProfileId }}”的画像与当前榜单。MoviePilot 订阅、订阅任务、忽略归档和插件配置不会被删除。
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="clearProfileLoading" @click="cancelClearProfile">取消</VBtn>
          <VBtn color="error" variant="flat" :loading="clearProfileLoading" @click="confirmClearProfile">确认清除</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="learningResetDialog" max-width="520" persistent>
      <VCard>
        <VCardTitle>重置学习数据？</VCardTitle>
        <VCardText>
          将清除“{{ selectedIdentity?.username || selectedProfileId }}”的反馈学习、已确认记忆、待处理项、CinePilot Agent 对话和结果归因。当前画像、榜单、忽略归档、人工标签与播放记录会保留。
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="dataActionLoading === 'learning'" @click="learningResetDialog = false">取消</VBtn>
          <VBtn color="warning" variant="flat" :loading="dataActionLoading === 'learning'" @click="confirmLearningReset">确认重置</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="fullResetDialog" max-width="540" persistent>
      <VCard>
        <VCardTitle>彻底重置 AgentRank 数据</VCardTitle>
        <VCardText v-if="fullResetStage === 'prepare'">
          第一步将为当前 MoviePilot 用户签发一次性短时确认令牌。继续后仍需输入确认词，期间不会删除任何数据。
        </VCardText>
        <VCardText v-else>
          <VAlert type="error" variant="tonal" density="compact" class="mb-4">
            此操作会删除“{{ selectedIdentity?.username || selectedProfileId }}”下的画像、榜单、归档、反馈、记忆、分析、对话、归因和运行历史，且无法撤销。
          </VAlert>
          <VTextField
            v-model="fullResetPhrase"
            label="输入“彻底重置”确认"
            density="compact"
            variant="outlined"
            autocomplete="off"
            hide-details
          />
          <div class="ar-config__hint mt-2">确认令牌有效至 {{ formatDateTime(fullResetConfirmation?.expires_at) }}，且仅限当前登录用户使用。</div>
        </VCardText>
        <VCardActions>
          <VBtn variant="text" :disabled="Boolean(dataActionLoading)" @click="closeFullReset">取消</VBtn>
          <VSpacer />
          <VBtn
            v-if="fullResetStage === 'prepare'"
            color="error"
            variant="tonal"
            :loading="dataActionLoading === 'full-prepare'"
            @click="prepareFullReset"
          >继续</VBtn>
          <VBtn
            v-else
            color="error"
            variant="flat"
            :loading="dataActionLoading === 'full-reset'"
            :disabled="fullResetPhrase !== '彻底重置'"
            @click="confirmFullReset"
          >确认彻底重置</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
    <VSnackbar v-model="actionFeedback.show" :color="actionFeedback.color">{{ actionFeedback.message }}</VSnackbar>
  </div>
</template>

<style scoped>
.ar-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; overflow-x: hidden; }
.ar-config__card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; overflow: hidden; border-radius: 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.ar-config__header { padding: 14px 18px; }
.ar-config__header :deep(.v-card-subtitle) { max-width: min(560px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ar-config__header-state { display: flex; align-items: center; gap: 10px; }
.ar-config__body { flex: 1 1 auto; min-height: 0; display: flex; }
.ar-config__nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.ar-config__nav-list { width: 100%; }
.ar-config__nav-item { margin: 2px 8px; }
.ar-config__content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.ar-config__subtabs { flex: 0 0 auto; display: flex; padding: 8px 12px; }
.ar-config__subtab { display: inline-flex; align-items: center; padding: 6px 14px; border: 0; border-radius: 8px; background: transparent; color: rgba(var(--v-theme-on-surface), .68); font-size: 13px; font-weight: 600; white-space: nowrap; cursor: pointer; }
.ar-config__subtab--active { background: rgba(var(--v-theme-primary), .14); color: rgb(var(--v-theme-primary)); }
.ar-config__window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.ar-config__window--overview { overflow-y: hidden; }
.ar-config__pane { min-height: 100%; padding: 18px 20px; }
.ar-config__pane--overview { padding: 12px 16px; }
.ar-config__section-title { color: rgb(var(--v-theme-primary)); font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.ar-config__pipeline { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 10px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); }
.ar-config__step { display: flex; align-items: center; gap: 7px; min-width: 0; font-size: 12px; font-weight: 500; }
.ar-config__step-copy { min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
.ar-config__step-copy span, .ar-config__step-copy small { overflow-wrap: anywhere; white-space: normal; }
.ar-config__step-copy small { color: rgba(var(--v-theme-on-surface), .55); font-size: 10px; font-weight: 400; }
.ar-config__overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.ar-config__overview-panel { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .015); }
.ar-config__panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; font-size: 13px; font-weight: 600; }
.ar-config__panel-head small { color: rgba(var(--v-theme-on-surface), .55); font-size: 11px; font-weight: 400; }
.ar-config__stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 4px; font-size: 12px; }
.ar-config__stats strong { color: rgb(var(--v-theme-primary)); }
.ar-config__tag-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; max-height: 46px; overflow: hidden; }
.ar-config__metric-list { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 11px; }
.ar-config__metric-list span { display: inline-flex; gap: 4px; }
.ar-config__metric-list b { color: rgba(var(--v-theme-on-surface), .62); font-weight: 500; }
.ar-config__metric-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.ar-config__metric-columns > div { display: flex; flex-direction: column; gap: 2px; min-width: 0; font-size: 11px; }
.ar-config__metric-columns small { color: rgba(var(--v-theme-on-surface), .55); margin-bottom: 2px; }
.ar-config__metric-columns span { display: flex; justify-content: space-between; gap: 8px; overflow-wrap: anywhere; }
.ar-config__empty { color: rgba(var(--v-theme-on-surface), .48); font-size: 11px; }
.ar-config__source-errors { display: flex; align-items: flex-start; gap: 5px; margin-top: 6px; color: rgb(var(--v-theme-warning)); font-size: 10px; line-height: 1.35; }
.ar-config__overview-foot { display: flex; align-items: center; gap: 7px; margin-top: 10px; color: rgba(var(--v-theme-on-surface), .62); font-size: 11px; }
.ar-config__overview-foot .v-chip { margin-left: auto; }
.ar-config__source-card { border-radius: 8px; }
.ar-config__hint, .ar-config__default { color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; line-height: 1.5; }
.ar-config__source-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.ar-config__weight-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 20px; }
.ar-config__weight-item { padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; }
.ar-config__default { margin-top: -2px; text-align: right; }
.ar-config__prompt-list { display: flex; flex-direction: column; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.ar-config__prompt-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 12px 14px; }
.ar-config__prompt-row + .ar-config__prompt-row { border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.ar-config__prompt-copy { min-width: 0; }
.ar-config__prompt-title { font-size: 13px; font-weight: 700; }
.ar-config__prompt-purpose { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; line-height: 1.45; }
.ar-config__prompt-summary { display: -webkit-box; margin-top: 5px; overflow: hidden; color: rgba(var(--v-theme-on-surface), .78); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.ar-config__fixed-rules { border-radius: 8px; overflow: hidden; }
.ar-config__rule-list { margin: 0; padding-left: 20px; color: rgba(var(--v-theme-on-surface), .72); font-size: 12px; line-height: 1.7; }
.ar-config__prompt-dialog { max-height: min(760px, calc(100dvh - 24px)); overflow: hidden; }
.ar-config__prompt-dialog-subtitle { white-space: normal; overflow-wrap: anywhere; }
.ar-config__prompt-dialog-body { overflow-y: auto; }
.ar-config__prompt-dialog-hint { margin-top: 8px; color: rgba(var(--v-theme-on-surface), .6); font-size: 12px; line-height: 1.5; }
.ar-config__inline-alert { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ar-config__loading-state, .ar-config__empty-state { min-height: 180px; display: flex; align-items: center; justify-content: center; gap: 10px; color: rgba(var(--v-theme-on-surface), .62); font-size: 13px; }
.ar-config__access-list, .ar-config__data-actions { display: flex; flex-direction: column; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.ar-config__access-row { display: grid; grid-template-columns: auto minmax(120px, .7fr) minmax(240px, 1.3fr); align-items: center; gap: 12px; padding: 12px 14px; }
.ar-config__access-row + .ar-config__access-row, .ar-config__data-row + .ar-config__data-row { border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.ar-config__access-user, .ar-config__data-row > div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ar-config__access-user strong, .ar-config__data-row strong { font-size: 13px; }
.ar-config__access-user small, .ar-config__data-row small { color: rgba(var(--v-theme-on-surface), .6); font-size: 11px; line-height: 1.4; overflow-wrap: anywhere; }
.ar-config__retention-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.ar-config__retention-item { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.ar-config__data-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 12px 14px; }
.ar-config__data-row--danger { background: rgba(var(--v-theme-error), .025); }
.ar-config__danger-row { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 12px 14px; border: 1px solid rgba(var(--v-theme-error), .32); border-radius: 10px; background: rgba(var(--v-theme-error), .045); }
.ar-config__danger-title { color: rgb(var(--v-theme-error)); font-size: 13px; font-weight: 700; }
.ar-config__danger-row :deep(.v-switch) { flex: 0 0 auto; }
.ar-config__actions { flex: 0 0 auto; padding: 10px 18px; }
@media (max-width: 760px) {
  .ar-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .ar-config__card { height: min(860px, calc(100dvh - 16px)); }
  .ar-config__header :deep(.v-card-subtitle) {
    max-width: 100%;
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .ar-config__header-state { gap: 4px; }
  .ar-config__body { flex-direction: column; }
  .ar-config__nav { width: 100%; flex: 0 0 auto; border-right: 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .ar-config__nav::-webkit-scrollbar { display: none; }
  .ar-config__nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .ar-config__nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }
  .ar-config__subtabs { overflow-x: auto; }
  .ar-config__window--overview { overflow-y: auto; }
  .ar-config__pipeline { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ar-config__overview-grid, .ar-config__source-grid, .ar-config__weight-grid { grid-template-columns: 1fr; }
  .ar-config__prompt-row { grid-template-columns: auto minmax(0, 1fr); }
  .ar-config__prompt-row > .v-btn { grid-column: 2; justify-self: end; }
  .ar-config__access-row { grid-template-columns: auto minmax(0, 1fr); }
  .ar-config__access-row > .v-select { grid-column: 1 / -1; }
  .ar-config__retention-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ar-config__prompt-dialog { max-height: calc(100dvh - 16px); }
  .ar-config__danger-row { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 390px) {
  .ar-config { width: 100%; padding: 2px; }
  .ar-config__header { padding-inline: 12px; }
  .ar-config__header-state .v-chip { display: none; }
  .ar-config__nav-item { min-width: 88px; }
  .ar-config__pane { padding: 12px; }
  .ar-config__actions { flex-wrap: wrap; padding-inline: 12px; }
  .ar-config__retention-grid { grid-template-columns: 1fr; }
  .ar-config__data-row { grid-template-columns: auto minmax(0, 1fr); }
  .ar-config__data-row > .v-btn { grid-column: 2; justify-self: end; }
}
@media (max-height: 760px) { .ar-config__window--overview { overflow-y: auto; } }
</style>
