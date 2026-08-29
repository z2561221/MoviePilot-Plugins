import { computed, nextTick, reactive, ref, watch } from 'vue'
import { getPluginApi } from '../api'

const defaults = {
  enabled: false,
  cron: '0 8 * * *',
  notify: false,
  proxy: false,
  onlyonce: false,
  rsshub_domain: 'https://rsshub.ddsrem.com',
  rank_configs: {
    coming: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_real_time: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_chinese: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    tv_global: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    movie_weekly: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
    bangumi: { enabled: false, count: 1, wish_count: '', air_days: '', vote: '', year: '', regions: [] },
  },
  region_filters: [],
  genre_filters: [],
  resolution_filters: [],
  custom_rss_addrs: '',
  custom_ranks: [],
  folio_enabled: true,
  folio_private: true,
  folio_first: true,
  folio_notify: false,
  folio_exclude_live_tv: true,
  folio_user: '',
  folio_exclude: '',
  folio_cookie: '',
  wish_enabled: false,
  wish_cron: '*/30 * * * *',
  wish_user: '',
  wish_notify: false,
  wish_onlyonce: false,
  wish_max_pages: 1,
  wish_days: 7,
  dashboard_rank_keys: [],
  discovery_page_enabled: false,
  blacklist_keywords: '',
  observe_days: 0,
  observe_rank_keys: ['coming', 'tv_real_time'],
}

const dateModeOptions = [
  { title: '提前订阅', value: 'future' },
  { title: '近期上映', value: 'recent' },
]

const builtinRankDefs = [
  { key: 'coming', name: '即将上映', route: '/douban/tv/coming', date_mode: 'future', filters: ['vote', 'wish_count', 'air_days'] },
  { key: 'tv_real_time', name: '实时热门', route: '/douban/list/tv_real_time_hotest', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'tv_chinese', name: '华语口碑', route: '/douban/list/tv_chinese_best_weekly', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'tv_global', name: '全球口碑', route: '/douban/list/tv_global_best_weekly', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'movie_weekly', name: '电影口碑', route: '/douban/list/movie_weekly_best', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
  { key: 'bangumi', name: 'BangumiTV', route: '/bangumi.tv/anime/followrank', date_mode: 'recent', filters: ['vote', 'year', 'air_days'] },
]

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '运行链路、模块状态和待关注事项。' },
  { key: 'rank', title: '榜单订阅', icon: 'mdi-trophy-outline', desc: '内置与自定义榜单统一订阅到豆瓣中心。' },
  { key: 'folio', title: '豆瓣时间', icon: 'mdi-book-clock-outline', desc: '追剧观影自动同步进度到豆瓣时间线。' },
  { key: 'dashboard', title: '仪表显示', icon: 'mdi-view-dashboard-outline', desc: '时间线 + 榜单排行双面板。' },
]

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  rank: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'list', title: '榜单列表', icon: 'mdi-format-list-bulleted' },
    { key: 'filter', title: '订阅观察', icon: 'mdi-shield-search' },
  ],
  folio: [
    { key: 'wish', title: '同步想看', icon: 'mdi-heart-plus-outline' },
    { key: 'sync', title: '同步观影', icon: 'mdi-sync' },
  ],
  dashboard: [{ key: 'view', title: '仪表盘选择', icon: 'mdi-view-dashboard-outline' }],
}

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function customRankKey() {
  return `custom_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function normalizeDateMode(value) {
  return value === 'future' ? 'future' : 'recent'
}

function validCustomRoute(route) {
  const value = String(route || '').trim()
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('#')) return false
  try {
    return new URL(value, 'https://rsshub.local').origin === 'https://rsshub.local'
  } catch {
    return false
  }
}

export function useConfigForm({ api, pluginId, initialConfig, emit }) {
  const form = reactive({})
  const activeMain = ref('overview')
  const activeSub = ref('overview')
  const overview = ref(null)
  const loadingOverview = ref(false)
  const customRankError = ref('')
  const expandedRankKeys = ref(new Set())
  const deleteTarget = ref(null)
  const deleteDialog = ref(false)
  const nameInputRefs = new Map()

  const rankDefs = computed(() => [
    ...builtinRankDefs,
    ...(Array.isArray(form.custom_ranks) ? form.custom_ranks : []).map(rank => ({
      ...rank,
      model: rank,
      custom: true,
      filters: ['vote', 'year', 'air_days'],
    })),
  ])
  const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0])
  const currentSubs = computed(() => subTabs[activeMain.value] || [])
  const enabledRankCount = computed(() => rankDefs.value.filter(rank => form.rank_configs?.[rank.key]?.enabled).length)
  const customRankCount = computed(() => rankDefs.value.filter(rank => rank.custom).length)
  const overviewCards = computed(() => {
    const cards = overview.value?.cards || {}
    return [
      {
        title: '榜单订阅',
        icon: 'mdi-rss',
        color: cards.rss?.enabled ? 'success' : 'warning',
        value: `${cards.rss?.enabled || 0}/${cards.rss?.total || rankDefs.value.length}`,
        desc: cards.rss?.last_refresh ? `最近刷新 ${cards.rss.last_refresh}` : '等待 RSS 刷新',
      },
      {
        title: '订阅记录',
        icon: 'mdi-playlist-check',
        color: cards.subscribe?.enabled ? 'primary' : 'default',
        value: `${cards.subscribe?.total || 0} 条`,
        desc: `本月新增 ${cards.subscribe?.month_new || 0} 条`,
      },
      {
        title: '归档治理',
        icon: 'mdi-shield-check-outline',
        color: cards.observe?.pending ? 'warning' : 'success',
        value: `${cards.observe?.pending || 0} 待观察`,
        desc: `观察期 ${cards.observe?.days || 0} 天，已忽略 ${cards.observe?.ignored || 0}`,
      },
      {
        title: '豆瓣时间',
        icon: 'mdi-book-clock-outline',
        color: cards.folio?.enabled ? 'success' : 'default',
        value: `${cards.folio?.items || 0} 条`,
        desc: cards.folio?.user ? `用户 ${cards.folio.user}` : '未配置用户',
      },
    ]
  })

  function rankDateLabel(rank) {
    return normalizeDateMode(rank?.date_mode) === 'future' ? '提前天数' : '最近天数'
  }

  function rankDateSummary(rank) {
    const days = form.rank_configs?.[rank.key]?.air_days
    const prefix = normalizeDateMode(rank?.date_mode) === 'future' ? '提前' : '最近'
    return `${prefix} ${Number(days) > 0 ? `${days} 天` : '不限'}`
  }

  function addCustomRank() {
    customRankError.value = ''
    const key = customRankKey()
    form.custom_ranks.push({ key, name: '', route: '', date_mode: 'recent' })
    form.rank_configs[key] = { enabled: false, count: 1, vote: '', year: '', air_days: '', regions: [] }
    expandedRankKeys.value = new Set([...expandedRankKeys.value, key])
    activeMain.value = 'rank'
    activeSub.value = 'list'
    nextTick(() => nameInputRefs.get(key)?.focus?.())
  }

  function setNameInputRef(key, value) {
    if (value) nameInputRefs.set(key, value)
    else nameInputRefs.delete(key)
  }

  function toggleRank(key) {
    const next = new Set(expandedRankKeys.value)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    expandedRankKeys.value = next
  }

  function isExpanded(key) {
    return expandedRankKeys.value.has(key)
  }

  function requestRemoveCustomRank(rank) {
    deleteTarget.value = rank
    deleteDialog.value = true
  }

  function removeCustomRank(key) {
    customRankError.value = ''
    form.custom_ranks = form.custom_ranks.filter(rank => rank.key !== key)
    delete form.rank_configs[key]
    form.dashboard_rank_keys = (form.dashboard_rank_keys || []).filter(value => value !== key)
    form.observe_rank_keys = (form.observe_rank_keys || []).filter(value => value !== key)
    expandedRankKeys.value = new Set([...expandedRankKeys.value].filter(value => value !== key))
    deleteTarget.value = null
    deleteDialog.value = false
  }

  function validateCustomRanks() {
    const seen = new Set(builtinRankDefs.map(rank => rank.key))
    for (const rank of form.custom_ranks || []) {
      const key = String(rank?.key || '').trim()
      if (!key || seen.has(key)) return '自定义榜单标识重复或无效'
      if (!String(rank?.name || '').trim()) return '请填写自定义榜单名称'
      if (!validCustomRoute(rank?.route)) return 'RSSHub 路由必须是以 / 开头的相对路径'
      if (!dateModeOptions.some(item => item.value === rank?.date_mode)) return '请选择自定义榜单的日期方向'
      seen.add(key)
    }
    return ''
  }

  function normalizeInitialConfig(value) {
    const normalized = Object.assign({}, cloneConfig(defaults), cloneConfig(value))
    normalized.custom_ranks = Array.isArray(normalized.custom_ranks)
      ? normalized.custom_ranks.filter(rank => isPlainObject(rank)).map(rank => ({
        key: String(rank.key || ''),
        name: String(rank.name || ''),
        route: String(rank.route || ''),
        date_mode: normalizeDateMode(rank.date_mode),
      }))
      : []
    if (!isPlainObject(normalized.rank_configs)) normalized.rank_configs = {}
    const allRanks = [...builtinRankDefs, ...normalized.custom_ranks.map(rank => ({ ...rank, filters: ['vote', 'year', 'air_days'] }))]
    for (const rank of allRanks) {
      normalized.rank_configs[rank.key] = {
        ...(defaults.rank_configs[rank.key] || { enabled: false, count: 1, vote: '', year: '' }),
        ...(isPlainObject(normalized.rank_configs[rank.key]) ? normalized.rank_configs[rank.key] : {}),
      }
      const rankConfig = normalized.rank_configs[rank.key]
      rankConfig.regions = Array.isArray(rankConfig.regions)
        ? [...new Set(rankConfig.regions.map(item => String(item || '').trim()).filter(Boolean))]
        : []
      const rawCount = rankConfig.count
      rankConfig.count = rawCount === undefined || rawCount === null || rawCount === '' ? 1 : (Number(rawCount) === 0 ? '' : rawCount)
      for (const field of ['vote', 'year', 'wish_count', 'air_days']) {
        if (rankConfig[field] === undefined || rankConfig[field] === null || Number(rankConfig[field]) === 0) rankConfig[field] = ''
      }
      delete rankConfig.media_type
    }
    if (!Array.isArray(normalized.dashboard_rank_keys)) normalized.dashboard_rank_keys = []
    normalized.dashboard_rank_keys = [...new Set(normalized.dashboard_rank_keys.map(item => String(item || '').trim()).filter(Boolean))].slice(0, 6)
    if (!Array.isArray(normalized.observe_rank_keys)) normalized.observe_rank_keys = [...defaults.observe_rank_keys]
    return normalized
  }

  function saveConfig() {
    customRankError.value = validateCustomRanks()
    if (customRankError.value) {
      activeMain.value = 'rank'
      activeSub.value = 'list'
      return
    }
    emit('save', {
      ...form,
      custom_ranks: (form.custom_ranks || []).map(rank => ({
        key: String(rank.key || '').trim(),
        name: String(rank.name || '').trim(),
        route: String(rank.route || '').trim(),
        date_mode: normalizeDateMode(rank.date_mode),
      })),
      rank_configs: Object.fromEntries(Object.entries(form.rank_configs || {}).map(([key, config]) => [key, {
        ...cloneConfig(config),
        regions: Array.isArray(config?.regions) ? [...new Set(config.regions.map(value => String(value || '').trim()).filter(Boolean))] : [],
      }])),
      region_filters: [],
      genre_filters: [],
      resolution_filters: [],
      custom_rss_addrs: '',
    })
  }

  function limitDashboardRanks() {
    form.dashboard_rank_keys = [...new Set((form.dashboard_rank_keys || []).map(value => String(value || '').trim()).filter(Boolean))].slice(0, 6)
  }

  function selectMain(key) {
    if (activeMain.value === key) return
    activeMain.value = key
    activeSub.value = subTabs[key]?.[0]?.key || ''
  }

  async function loadOverview() {
    loadingOverview.value = true
    try {
      const response = await getPluginApi(api(), pluginId(), 'overview')
      if (response?.success === false) throw new Error(response.message || '总览加载失败')
      const data = response?.data ?? response
      if (data?.code === 0 || data?.cards) overview.value = data
    } catch (error) {
      console.error('加载豆瓣中心总览失败:', error)
    } finally {
      loadingOverview.value = false
    }
  }

  watch(initialConfig, value => {
    Object.keys(form).forEach(key => delete form[key])
    Object.assign(form, normalizeInitialConfig(value))
  }, { immediate: true, deep: true })

  return reactive({
    form,
    activeMain,
    activeSub,
    overview,
    loadingOverview,
    customRankError,
    deleteTarget,
    deleteDialog,
    rankDefs,
    mainTabs,
    currentMain,
    currentSubs,
    enabledRankCount,
    customRankCount,
    overviewCards,
    dateModeOptions,
    rankDateLabel,
    rankDateSummary,
    addCustomRank,
    setNameInputRef,
    toggleRank,
    isExpanded,
    requestRemoveCustomRank,
    removeCustomRank,
    saveConfig,
    limitDashboardRanks,
    selectMain,
    loadOverview,
  })
}
