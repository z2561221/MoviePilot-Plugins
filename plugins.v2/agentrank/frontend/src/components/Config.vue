<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi, postPluginApi } from './api'

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
  year_weight: 0.3,
  rating_weight: 0.7,
  heat_weight: 0.6,
  freshness_weight: 0.5,
  similarity_weight: 0.8,
}

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
}

const form = reactive(structuredClone(defaults))
const activeMain = ref('overview')
const activeAdvanced = ref('runtime')
const loading = ref(false)
const status = ref({ state: 'stopped', validation_errors: [], playback: null, enablement: null })
const overview = ref(null)
const availableIdentities = ref([])
const availableLibraries = ref({})
const sourceOptions = ref([])
const loadError = ref('')
const runtimeDefaults = ref(structuredClone(defaults))
const clearProfileSwitch = ref(false)
const clearProfileDialog = ref(false)
const clearProfileLoading = ref(false)
const actionFeedback = reactive({ show: false, message: '', color: 'success' })

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '选择 Emby 服务实例、用户、内容库和运行周期。' },
  { key: 'playback', title: '播放画像', icon: 'mdi-play-circle-outline', desc: 'Playback Reporting 是插件运行的强制依赖。' },
  { key: 'sources', title: '发现来源', icon: 'mdi-compass-outline', desc: '选择 MoviePilot 内置发现来源。' },
  { key: 'weights', title: '权重设置', icon: 'mdi-tune-vertical', desc: '设置 Agent 排序时十项偏好权重。' },
  { key: 'filter', title: '条件筛选', icon: 'mdi-filter-outline', desc: '限制媒体类型、候选数量和置信度。' },
  { key: 'board', title: '榜单行为', icon: 'mdi-format-list-numbered', desc: '选择仅更新、通知确认或自动订阅。' },
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

const mediaTypeOptions = [
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
  { title: '动漫', value: 'anime' },
]
const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知内选择', value: 'notify' },
  { title: '自动订阅前几名', value: 'auto_subscribe' },
]
const advancedTabs = [
  { key: 'runtime', title: '运行设置', icon: 'mdi-cog-outline' },
  { key: 'prompt', title: '提示设置', icon: 'mdi-text-box-edit-outline' },
]

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0])
const selectedProfileId = computed(() => form.default_profile_id || form.emby_identities[0]?.profile_id || '')
const selectedIdentity = computed(() => form.emby_identities.find(identity => identity.profile_id === selectedProfileId.value) || null)
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
const runtimeStateText = computed(() => ({ ready: '运行中', blocked: '已阻断', stopped: '已停用' })[status.value.state] || status.value.state || '未知')
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
      title: key,
      subtitle: 'MoviePilot 来源',
      icon: 'mdi-database-outline',
    }),
  }))
})

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
const exclusionLabels = { invalid_or_unrecognized: '无效或未识别', watched: '已观看', watched_completed: '已看完', library: '已入库', subscribed: '已订阅', archived: '已忽略', negative_keyword: '排除关键词' }
const mediaTypeLabels = { movie: '电影', tv: '剧集', anime: '动漫' }
const languageLabels = { zh: '中文', ja: '日语', ko: '韩语', en: '英语', fr: '法语', de: '德语', es: '西班牙语', it: '意大利语', ru: '俄语', th: '泰语' }
const sortLabels = { 'popularity.desc': '热度降序', 'vote_average.desc': '评分降序', 'primary_release_date.desc': '上映日期降序', 'first_air_date.desc': '首播日期降序' }
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
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function stageStatus(step) {
  const value = latestMetrics.value.stage_status?.[step.key] || ''
  return stageLabels[value] || value
}

function stageDuration(step) {
  const value = Number(latestMetrics.value.stage_ms?.[step.key])
  if (!Number.isFinite(value) || value < 0) return ''
  if (value < 1000) return `${Math.round(value)} 毫秒`
  return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)} 秒`
}

function runStatusText(value) { return stageLabels[value] || value || '未知' }

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

function applyConfig(value) {
  const next = cloneConfig(value)
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
  form.media_types = Array.isArray(next.media_types) ? [...next.media_types] : [...defaults.media_types]
  form.exclude_keywords = Array.isArray(next.exclude_keywords) ? [...next.exclude_keywords] : []
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true })
async function loadOverview(profileId = selectedProfileId.value) {
  if (!props.api?.get || !profileId) {
    overview.value = null
    return
  }
  overview.value = await getPluginApi(props.api, 'overview', { profile_id: profileId })
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
    await loadOverview(optionsData?.default_profile_id || selectedProfileId.value)
  } catch (error) {
    loadError.value = error?.message || '运行信息加载失败'
  } finally {
    loading.value = false
  }
}

function saveConfig() {
  const payload = cloneConfig(form)
  delete payload._validation_errors
  emit('save', payload)
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

function restoreAgentPrompt() {
  form.agent_prompt = runtimeDefaults.value.agent_prompt || defaults.agent_prompt
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
          <div class="ar-config__subtabs">
            <button v-if="activeMain !== 'advanced'" class="ar-config__subtab ar-config__subtab--active" type="button">
              <VIcon :icon="currentMain.icon" size="18" class="mr-1" />{{ currentMain.title }}
            </button>
            <button
              v-for="item in activeMain === 'advanced' ? advancedTabs : []"
              :key="item.key"
              class="ar-config__subtab"
              :class="{ 'ar-config__subtab--active': activeAdvanced === item.key }"
              type="button"
              @click="activeAdvanced = item.key"
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
              </VRow>
              <VAlert type="info" variant="tonal" class="mt-4">Emby 画像身份由服务实例与用户组成；画像只同步所选用户在所选内容库中的 Playback Reporting 记录，未安装或不可访问时插件保持停用。</VAlert>
            </div>

            <div v-show="activeMain === 'playback'" class="ar-config__pane">
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
                  <VChip v-if="currentPlayback?.source" size="x-small" variant="outlined">{{ currentPlayback.source }}</VChip>
                  <VChip v-if="currentPlayback?.confidence" size="x-small" variant="outlined">{{ currentPlayback.confidence }}</VChip>
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

            <div v-show="activeMain === 'sources'" class="ar-config__pane">
              <div class="ar-config__section-title">发现来源</div>
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

            <div v-show="activeMain === 'weights'" class="ar-config__pane">
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

            <div v-show="activeMain === 'filter'" class="ar-config__pane">
              <div class="ar-config__section-title">条件筛选</div>
              <VRow>
                <VCol cols="12" md="6"><VSelect v-model="form.media_types" :items="mediaTypeOptions" label="媒体类型" multiple chips density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.candidate_pool_size" type="number" min="10" max="500" label="候选池数量" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="8">
                  <div class="text-caption mb-1">置信度阈值 {{ Math.round(form.confidence_threshold * 100) }}%</div>
                  <VSlider v-model="form.confidence_threshold" :min="0" :max="1" :step="0.05" color="primary" hide-details thumb-label />
                </VCol>
                <VCol cols="12"><VCombobox v-model="form.exclude_keywords" label="排除关键词" multiple chips closable-chips density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
            </div>

            <div v-show="activeMain === 'board'" class="ar-config__pane">
              <div class="ar-config__section-title">榜单行为</div>
              <VRow>
                <VCol cols="12" md="6"><VSelect v-model="form.action_mode" :items="actionOptions" label="动作模式" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="3"><VTextField v-model.number="form.auto_subscribe_top_n" type="number" min="0" :max="form.auto_subscribe_limit" label="自动订阅前几名" density="compact" variant="outlined" hide-details :disabled="form.action_mode !== 'auto_subscribe'" /></VCol>
                <VCol cols="12" md="3"><VTextField v-model.number="form.auto_subscribe_limit" type="number" min="0" max="10" label="安全上限" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12"><VSwitch v-model="form.notify" color="info" label="发送通知" hide-details inset :disabled="form.action_mode === 'update'" /></VCol>
              </VRow>
              <VAlert :type="form.action_mode === 'auto_subscribe' ? 'warning' : 'info'" variant="tonal" class="mt-4">
                {{ form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、置信度、识别 ID 和重复订阅。' : 'Telegram 通知以海报轮播展示榜单，可自由加入待订阅清单，最终确认后再逐项执行安全检查。' }}
              </VAlert>
            </div>

            <div v-show="activeMain === 'advanced'" class="ar-config__pane">
              <template v-if="activeAdvanced === 'runtime'">
                <div class="ar-config__section-title">运行设置</div>
                <VRow>
                  <VCol cols="12" md="4"><VSwitch v-model="form.discovery_page_enabled" color="success" label="开启发现页" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.profile_cache_enabled" color="success" label="画像缓存" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.rebuild_profile_each_run" color="warning" label="每次重建" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.minimum_samples" type="number" min="1" max="100" label="最少样本" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.history_limit" type="number" min="1" max="200" label="历史上限" density="compact" variant="outlined" hide-details /></VCol>
                </VRow>
                <VAlert type="info" variant="tonal" class="mt-4">画像缓存开启且关闭每次重建时，Agent 会在播放快照未变化时复用当前画像；每次重建开启或缓存关闭时，按冻结的 Playback Reporting 快照重新生成。</VAlert>
                <div class="ar-config__danger-row mt-4">
                  <div>
                    <div class="ar-config__danger-title">清除画像</div>
                    <div class="ar-config__hint">清除默认画像身份“{{ selectedIdentity?.username || '未选择' }}”的画像与榜单，不影响 MoviePilot 订阅和归档。</div>
                  </div>
                  <VSwitch
                    v-model="clearProfileSwitch"
                    color="error"
                    label="清除画像"
                    hide-details
                    inset
                    :disabled="clearProfileLoading"
                    @update:model-value="requestClearProfile"
                  />
                </div>
              </template>
              <template v-else>
                <div class="d-flex align-center mb-3">
                  <div class="ar-config__section-title mb-0">提示设置</div>
                  <VSpacer />
                  <VBtn variant="text" color="primary" prepend-icon="mdi-restore" size="small" @click="restoreAgentPrompt">恢复默认</VBtn>
                </div>
                <VTextarea
                  v-model="form.agent_prompt"
                  label="Agent排序提示词"
                  variant="outlined"
                  rows="12"
                  counter="4000"
                  maxlength="4000"
                  auto-grow
                  hide-details="auto"
                />
                <VAlert type="info" variant="tonal" class="mt-4">该提示词只调整冻结候选池内的排序与文案风格；画像生成提示、只读工具边界和 JSON 输出协议由插件固定保留。</VAlert>
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
.ar-config__metric-list { display: flex; flex-wrap: wrap; gap: 4px 10px; max-height: 64px; overflow: hidden; font-size: 11px; }
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
.ar-config__danger-row { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 12px 14px; border: 1px solid rgba(var(--v-theme-error), .32); border-radius: 10px; background: rgba(var(--v-theme-error), .045); }
.ar-config__danger-title { color: rgb(var(--v-theme-error)); font-size: 13px; font-weight: 700; }
.ar-config__danger-row :deep(.v-switch) { flex: 0 0 auto; }
.ar-config__actions { flex: 0 0 auto; padding: 10px 18px; }
@media (max-width: 760px) {
  .ar-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .ar-config__card { height: min(860px, calc(100dvh - 16px)); }
  .ar-config__header :deep(.v-card-subtitle) { max-width: 100%; }
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
  .ar-config__danger-row { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 390px) {
  .ar-config { width: 100%; padding: 2px; }
  .ar-config__header { padding-inline: 12px; }
  .ar-config__header-state .v-chip { display: none; }
  .ar-config__nav-item { min-width: 88px; }
  .ar-config__pane { padding: 12px; }
  .ar-config__actions { flex-wrap: wrap; padding-inline: 12px; }
}
@media (max-height: 760px) { .ar-config__window--overview { overflow-y: auto; } }
</style>
