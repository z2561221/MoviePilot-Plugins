<script setup>
import './form-layout.css'
import { reactive, ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getPluginApi, postPluginJsonApi, isApiRequestCancellation, getManagementPermission } from './api'
import SyncDeletePane from './SyncDeletePane.vue'
import AutoDeletePane from './AutoDeletePane.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
})

const canManage = ref(false)
const permissionError = ref('')
const permissionStatus = ref('loading')


const emit = defineEmits(['close', 'switch'])
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)
const postJsonApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options)

const form = reactive({})
const editingPiecesCredentials = ref(false)
const saving = ref(false)
const saveNotice = ref('')
const saveProblem = ref(false)
let savedDraft = {}
let resourceVersion = 0
let configMounted = false
const activeMain = ref('overview')
const activeSub = ref('overview')
const downloaderItems = ref([])
const downloaderRequest = ref(null)
const siteItems = ref([])
const overview = ref(null)
const autoDeletePane = ref(null)
const autoDeleteVisited = ref(false)
const syncDeleteVisited = ref(false)
const reviewDialog = ref(false)
const reviewPane = ref(null)
const cleanupDownloaders = ref([])
const cleanupScan = ref(null)
const cleanupKeep = reactive({})
const cleanupScanning = ref(false)
const cleanupExecuting = ref(false)
const cleanupDialog = ref(false)
const cleanupMessage = ref('')
const cleanupStatus = ref('info')
const completionDownloaders = ref([])
const completionScan = ref(null)
const completionKeep = reactive({})
const completionScanning = ref(false)
const completionExecuting = ref(false)
const completionTask = ref(null)
const completionDialog = ref(false)
const completionMessage = ref('')
const completionStatus = ref('info')
const monitorResetting = ref('')
const monitorMessage = ref('')
const monitorMessageStatus = ref('info')
const uploadSiteItems = ref([])
const uploadScanningSites = ref(false)
const uploadActionRunning = ref('')
const uploadMessage = ref('')
const uploadMessageStatus = ref('info')
const uploadRestoreDialog = ref(false)
const UPLOAD_STATUS_REFRESH_INTERVAL_MS = 30_000
let uploadStatusRefreshTimer = null
let uploadStatusRefreshPending = false
let uploadSiteRulesSaveTail = Promise.resolve()
let uploadSiteRulesRevision = 0
let uploadSiteScanTail = Promise.resolve()
let configDraftRevision = 0
let configDisposed = false

function configRequestScope() {
  const revision = configDraftRevision
  const pluginId = props.pluginId
  const api = props.api
  return () => !configDisposed && revision === configDraftRevision
    && pluginId === props.pluginId && api === props.api
}

function resetConfigRequests() {
  editingPiecesCredentials.value = false
  saving.value = false
  saveNotice.value = ''
  reviewDialog.value = false
  uploadActionRunning.value = ''
  uploadScanningSites.value = false
  uploadMessage.value = ''
  cleanupScanning.value = false
  cleanupExecuting.value = false
  cleanupDialog.value = false
  cleanupScan.value = null
  cleanupMessage.value = ''
  completionScanning.value = false
  completionExecuting.value = false
  completionTask.value = null
  completionDialog.value = false
  completionScan.value = null
  completionMessage.value = ''
  monitorResetting.value = ''
  monitorMessage.value = ''
}

async function refreshOverview() {
  const owns = configRequestScope()
  const response = await getApi('overview')
  if (!owns()) return
  if (response?.code === 0 || response?.cards) overview.value = response
}

function closeReview() {
  reviewDialog.value = false
  void refreshOverview().catch(() => {})
}

function loadConfigResources() {
  const { api, pluginId } = props
  const version = ++resourceVersion
  const owns = () => !configDisposed && api === props.api && pluginId === props.pluginId && version === resourceVersion
  for (const [path, target] of [['downloaders', downloaderItems], ['sites', siteItems], ['overview', overview]]) {
    const pending = getApi(path, { feedback: 'silent' })
    if (path === 'downloaders') downloaderRequest.value = pending
    pending.then(value => {
      if (owns() && value) target.value = value
    }).catch(error => {
      if (owns() && !isApiRequestCancellation(error)) console.error('读取配置页数据失败', path, error)
    })
  }
}
onMounted(() => {
  configMounted = true
  loadConfigResources()
})

const defaults = {
  sync_delete_enabled: false, sync_delete_servers: [], sync_delete_local_paths: '',
  sync_delete_cloud_paths: '', sync_delete_storage: '115网盘Plus', sync_delete_source_paths: '',
  sync_delete_source_aliases: '',
  sync_delete_exclude_paths: '', sync_delete_source: true, sync_delete_torrents: true,
  sync_delete_cloud: true, sync_delete_records: true, sync_delete_force_cloud: false,
  sync_delete_notify: true, sync_delete_library_deleted: false,
  enabled: false, transfer_enabled: true, delay_minutes: 25, onlyonce: false, notify: false,
  transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 60,
  fromdownloader: '', todownloader: '', frompath: '', topath: '',
  fromtorrentpath: '', nopaths: '', nolabels: '', includelabels: '', includecategory: '',
  transferemptylabel: false, add_torrent_tags: '⏩转种',
  deletesource: false, deleteduplicate: false,
  remainoldcat: false, remainoldtag: false,
  rename_enabled: true,
  rename_movie_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}',
  rename_tv_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}',
  rename_exclude_dirs: '',
  tag_enabled: true, tag_siteprefix: '🏠', tag_tracker_mappings_str: '',
  tag_official_enabled: false, tag_official_prefix: '🏅',
  tag_official_mappings: [
    '观众:Audies|ADE|ADWeb|ADAudio|ADeBook|ADMusic', '憨憨:HHWEB', '青蛙:FROG|FROGE|FROGWeb|CatEDU',
    '我堡:OurBits|OurTV', '猫站:PTerWEB|PTer|PTerMV|PTerTV', '高清杜比:QHstudIo|Dream', '朋友:FRDS',
    '猪猪:PigoWeb|PigoHD|PigoNF|PigoAD', 'Sunny:Sunny', '馒头:MTeam|MWEB',
  ].join('\n'),
  iyuu_enabled: false, iyuu_cron: '', iyuu_onlyonce: false,
  iyuu_token: '', iyuu_downloaders: [], iyuu_auto_downloader: '',
  pieces_site_keys: '',
  pieces_torrent_paths: '', reseed_max_additions: 20,
  iyuu_sites: [], iyuu_nolabels: '', iyuu_nopaths: '',
  iyuu_size: 0, iyuu_auto_category: false,
  iyuu_labelsafterseed: '已整理,辅种', iyuu_categoryafterseed: '',
  iyuu_clearcache: false,
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
  speed_monitor_enabled: false, speed_monitor_downloaders: [], speed_monitor_mode: 'auto',
  speed_monitor_exclude_categories: '',
  speed_monitor_tolerance: 1.5, speed_monitor_min_samples: 5,
  speed_monitor_interval_seconds: 30, speed_monitor_grace_minutes: 10,
  speed_monitor_consecutive_abnormal_samples: 2,
  speed_monitor_manual_speed_bps: {}, speed_monitor_floor_speed_bps: {},
  speed_monitor_notification_type: 'Plugin',
  upload_limit_enabled: false, upload_limit_downloaders: [],
  upload_limit_downloader_limits_kib: {}, upload_limit_site_rules: {},
  upload_limit_grace_minutes: 30,
}

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看下载中心各模块的完整运行链路。' },
  { key: 'monitor', title: '速度监控', icon: 'mdi-speedometer', desc: '按下载器建立稳健基准，识别未在预计时间内完成的下载任务。' },
  { key: 'transfer', title: '转移做种', icon: 'mdi-transfer', desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'iyuu', title: 'IYUU铺种', icon: 'mdi-seed-plus', desc: '优先通过 IYUU 匹配，Pieces 按已配置站点补查缺口。' },
  { key: 'rename', title: '命名补刀', icon: 'mdi-rename-box', desc: '转移后自动根据 TMDB 信息命名种子，并支持失败补刀。' },
  { key: 'tag', title: '站点标签', icon: 'mdi-tag-multiple', desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'seed', title: '做种校验', icon: 'mdi-check-circle-outline', desc: '统一控制跳过校验和自动开始做种，按需触发。' },
  { key: 'sync_delete', title: '同步删除', icon: 'mdi-delete-outline', desc: '接收 Emby 删除通知，同步清理媒体、源文件和本插件关联种子。' },
  { key: 'auto_delete', title: '自动删除', icon: 'mdi-delete-clock-outline', desc: '按规则先暂停调试，确认后自动删种；支持一个或多个下载器。' },
  { key: 'upload', title: '上传限速', icon: 'mdi-upload-network-outline', desc: '设置下载器全局上传上限，并按需限制指定站点的合计上传速度。' },
]

const subTabs = {
  auto_delete: [
    { key: 'auto_delete_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'auto_delete_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'auto_delete_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  sync_delete: [
    { key: 'sync_delete_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'sync_delete_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'sync_delete_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  upload: [
    { key: 'upload_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'upload_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'upload_status', title: '运行状态', icon: 'mdi-pulse' },
  ],
  monitor: [
    { key: 'monitor_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'monitor_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'monitor_status', title: '运行状态', icon: 'mdi-pulse' },
  ],
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  iyuu: [
    { key: 'iyuu_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'iyuu_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
    { key: 'iyuu_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  rename: [
    { key: 'rename_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'rename_filter', title: '条件筛选', icon: 'mdi-filter-variant' },
  ],
  tag: [
    { key: 'tag_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'tag_repair', title: '补全标签', icon: 'mdi-tag-plus-outline' },
    { key: 'tag_advanced', title: '标签清理', icon: 'mdi-tag-remove-outline' },
  ],
  seed: [
    { key: 'seed_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'seed_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const selectedToDownloaderType = computed(() => {
  const selected = downloaderItems.value.find(item => item.value === form.todownloader)
  return selected?.type || ''
})
const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'))
const tagCleanupDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)))
const tagCompletionDownloaderItems = computed(() => tagCleanupDownloaderItems.value)
const monitorDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)))
const uploadDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)))
const uploadSelectedDownloaders = computed(() => {
  const selected = new Set(form.upload_limit_downloaders || [])
  return uploadDownloaderItems.value.filter(item => selected.has(item.value))
})
const uploadMissingLimits = computed(() => uploadSelectedDownloaders.value.filter(
  item => !uploadDownloaderLimit(item.value),
))
const uploadLimit = computed(() => overview.value?.upload_limit || {})
const uploadLimitDownloaderRows = computed(() => uploadLimit.value.downloaders || [])
const uploadLimitSiteRows = computed(() => uploadLimit.value.sites || [])
const uploadSiteRuleRows = computed(() => Object.entries(form.upload_limit_site_rules || {})
  .map(([name, rule]) => ({ name, limit_kib: Number(rule?.limit_kib || 0) || null }))
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')))
const speedMonitor = computed(() => overview.value?.speed_monitor || {})
const speedBaselines = computed(() => speedMonitor.value.baselines || [])
const speedThresholdSuggestions = computed(() => {
  const configured = new Set(form.speed_monitor_downloaders || [])
  const selected = speedBaselines.value.filter(
    item => configured.has(item.downloader_id) && item.threshold_suggestion?.ready,
  )
  const tolerance = selected
    .map(item => Number(item.threshold_suggestion.tolerance || 0))
    .filter(value => value > 0)
  const grace = selected
    .map(item => Number(item.threshold_suggestion.grace_minutes || 0))
    .filter(value => value > 0)
  return {
    tolerance: tolerance.length ? Math.max(...tolerance) : null,
    grace_minutes: grace.length ? Math.max(...grace) : null,
  }
})
const speedThresholdSuggestionRows = computed(() => {
  const suggestions = speedThresholdSuggestions.value
  const rows = [
    {
      key: 'speed_monitor_interval_seconds',
      label: '活跃扫描间隔',
      currentValue: Number(form.speed_monitor_interval_seconds || 0),
      suggestedValue: 30,
      format: value => `${value} 秒`,
    },
    {
      key: 'speed_monitor_grace_minutes',
      label: '启动宽限',
      currentValue: Number(form.speed_monitor_grace_minutes || 0),
      suggestedValue: suggestions.grace_minutes,
      format: value => `${value} 分钟`,
    },
    {
      key: 'speed_monitor_tolerance',
      label: '允许时长倍数',
      currentValue: Number(form.speed_monitor_tolerance || 0),
      suggestedValue: suggestions.tolerance,
      format: value => `${Number(value).toFixed(1)} 倍`,
    },
    {
      key: 'speed_monitor_consecutive_abnormal_samples',
      label: '连续异常次数',
      currentValue: Number(form.speed_monitor_consecutive_abnormal_samples || 0),
      suggestedValue: 2,
      format: value => `${value} 次`,
    },
    {
      key: 'speed_monitor_min_samples',
      label: '可信样本门槛',
      currentValue: Number(form.speed_monitor_min_samples || 0),
      suggestedValue: 5,
      format: value => `${value} 条`,
    },
  ]
  return rows.map(row => ({
    ...row,
    current: row.format(row.currentValue),
    suggested: row.suggestedValue == null ? '—' : row.format(row.suggestedValue),
    available: row.suggestedValue != null && row.currentValue !== row.suggestedValue,
  }))
})
function applySpeedThresholdSuggestion(row) {
  if (!row?.available) return
  form[row.key] = row.suggestedValue
}
function applyAllSpeedThresholdSuggestions() {
  speedThresholdSuggestionRows.value
    .filter(row => row.available)
    .forEach(applySpeedThresholdSuggestion)
}
const speedMonitorStatus = computed(() => {
  const status = speedMonitor.value.service_status
  return {
    disabled: { label: '未启用', color: 'default' },
    idle: { label: '空闲', color: 'primary' },
    running: { label: '监控中', color: 'success' },
    error: { label: '状态异常', color: 'error' },
  }[status] || { label: '空闲', color: 'primary' }
})
const notificationTypeItems = [
  { title: '插件', value: 'Plugin' },
  { title: '资源下载', value: 'Download' },
  { title: '整理入库', value: 'Organize' },
  { title: '订阅', value: 'Subscribe' },
  { title: '站点', value: 'SiteMessage' },
  { title: '媒体服务器', value: 'MediaServer' },
  { title: '手动处理', value: 'Manual' },
  { title: '智能体', value: 'Agent' },
  { title: '其它', value: 'Other' },
]
const monitorModeItems = [
  { title: '自动稳健基准', value: 'auto' },
  { title: '手动最低速度', value: 'manual' },
]
const uploadLimitStatus = computed(() => {
  const status = uploadLimit.value.service_status
  return {
    disabled: { label: '未启用', color: 'default' },
    starting: { label: '启动中', color: 'info' },
    running: { label: '分配中', color: 'success' },
    degraded: { label: '部分异常', color: 'warning' },
    error: { label: '状态异常', color: 'error' },
  }[status] || { label: '未启用', color: 'default' }
})
const cleanupGroups = computed(() => cleanupScan.value?.downloaders || [])
const cleanupAutoRemovedCount = computed(() => cleanupScan.value?.auto_removed?.length || 0)
const cleanupRemovals = computed(() => {
  const removals = []
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) {
      if (!cleanupKeep[tagSelectionKey(group.name, item.tag)]) {
        removals.push({ downloader: group.name, tag: item.tag, hashes: [...(item.hashes || [])] })
      }
    }
  }
  return removals
})
const cleanupRemovalAssociations = computed(() => cleanupRemovals.value.reduce((total, item) => total + item.hashes.length, 0))
const completionGroups = computed(() => completionScan.value?.downloaders || [])
const completionRepairs = computed(() => {
  const repairs = []
  for (const group of completionGroups.value) {
    for (const item of group.tags || []) {
      if (completionKeep[tagCompletionSelectionKey(group.name, item.kind, item.tag)]) {
        repairs.push({ downloader: group.name, kind: item.kind, tag: item.tag, hashes: [...(item.hashes || [])] })
      }
    }
  }
  return repairs
})
const completionSelections = computed(() => completionRepairs.value.map(({ downloader, kind, tag }) => ({ downloader, kind, tag })))
const completionRepairAssociations = computed(() => completionRepairs.value.reduce((total, item) => total + item.hashes.length, 0))
const runtimeFlows = [
  {
    label: '速度监控',
    steps: ['下载任务', '监控会话', '有效采样', '阈值判定', '告警通知', '异常处置'],
  },
  {
    label: '转移做种',
    steps: ['下载完成', '延迟等待', '目标转移', '公共链路'],
  },
  {
    label: 'IYUU铺种',
    steps: ['任务触发', '资源查询', '辅种下载', '公共链路'],
  },
  {
    label: '公共链路',
    steps: ['命名处理', '站点标签', '做种校验'],
  },
  {
    label: '上传限速',
    steps: ['全局限速', '站点识别', '按需设限', '合计限速', '动态调速', '停用恢复'],
  },
  {
    label: '兜底补刀',
    steps: ['异常命名', '兜底补刀', '失败计数', '归档恢复'],
  },
  {
    label: '同步删除',
    steps: ['删除事件', '关联历史', '核验范围', '按配置清理', '结果记录'],
  },
  {
    label: '自动删除',
    steps: ['周期扫描', '有效采样', '暂停调试', '人工确认', '正式删种'],
  },
]
const syncDeletePending = computed(() => Number(overview.value?.modules?.find(item => item.key === 'sync_delete')?.pending || 0))
watch(() => props.initialConfig, v => {
  configDraftRevision++
  uploadSiteRulesRevision++
  resetConfigRequests()
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, JSON.parse(JSON.stringify({ ...defaults, ...v })))
  delete form.pieces_sites
  delete form.pieces_enabled
  delete form.reseed_mode
  for (const key of ['sync_delete_servers', 'speed_monitor_downloaders', 'upload_limit_downloaders']) form[key] ??= []
  for (const key of ['speed_monitor_manual_speed_bps', 'speed_monitor_floor_speed_bps', 'upload_limit_downloader_limits_kib', 'upload_limit_site_rules']) form[key] ??= {}
  form.pieces_site_keys ??= ''
  savedDraft = JSON.parse(JSON.stringify(form))
}, { immediate: true, deep: true, flush: 'sync' })
watch(() => [props.pluginId, props.api], () => {
  configDraftRevision++
  uploadSiteRulesRevision++
  resetConfigRequests()
  overview.value = null
  downloaderItems.value = []
  siteItems.value = []
  uploadSiteItems.value = []
  if (configMounted) loadConfigResources()
}, { flush: 'sync' })

function buildConfigPayload(stored, draft) {
  const payload = { ...stored }
  // The host replaces the whole config. Keep live values for untouched fields,
  // including settings already persisted by the auto-delete and site-rule editors.
  for (const [key, value] of Object.entries(draft)) {
    if (key.startsWith('auto_delete_') || key === 'upload_limit_site_rules') continue
    if (JSON.stringify(value) !== JSON.stringify(savedDraft[key]) || (!(key in stored) && key in defaults)) {
      payload[key] = value
    }
  }
  delete payload.pieces_sites
  delete payload.pieces_enabled
  delete payload.reseed_mode
  const mappings = value => String(value || '').split('\n').filter(line => line.split('#').some(part => part.trim())).join('\n')
  return {
    ...payload,
    sync_delete_force_cloud: false,
    sync_delete_library_deleted: false,
    sync_delete_local_paths: mappings(payload.sync_delete_local_paths),
    sync_delete_cloud_paths: mappings(payload.sync_delete_cloud_paths),
    sync_delete_source_aliases: mappings(payload.sync_delete_source_aliases),
  }
}

async function readStoredConfig() {
  const stored = await getApi('', { feedback: 'silent' })
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) throw new Error('无法读取当前配置')
  return stored
}

async function saveConfig() {
  if (!canManage.value || saving.value || autoDeletePane.value?.busy) return
  const owns = configRequestScope()
  const draft = JSON.parse(JSON.stringify(form))
  saving.value = true
  saveNotice.value = ''
  saveProblem.value = false
  let autoSaved = false
  let written = false
  try {
    if (autoDeletePane.value?.dirty) {
      if (!await autoDeletePane.value.save()) {
        if (!owns()) return
        if (autoDeletePane.value?.missingSourcePaths) {
          selectMain('auto_delete')
          activeSub.value = 'auto_delete_advanced'
        }
        throw new Error(autoDeletePane.value?.error || '自动删除设置未保存')
      }
      autoSaved = true
    }
    await uploadSiteScanTail
    await flushUploadSiteRulesSave()
    if (!owns()) return

    const stored = await readStoredConfig()
    if (!owns() || !canManage.value) return
    const edited = 'pieces_sites' in stored || 'pieces_enabled' in stored || Object.keys(draft).some(key => !key.startsWith('auto_delete_')
      && key !== 'upload_limit_site_rules' && JSON.stringify(draft[key]) !== JSON.stringify(savedDraft[key]))
    const payload = edited ? buildConfigPayload(stored, draft) : stored
    const changed = Object.keys(payload).some(key => JSON.stringify(payload[key]) !== JSON.stringify(stored[key]))
    if (changed) {
      const result = await props.api.put(`plugin/${props.pluginId}`, payload, { feedback: 'silent' })
      if (result?.success !== true) throw new Error(result?.message || '宿主未确认保存')
    }
    if (!owns()) return
    written = true
    if (form.pieces_site_keys === draft.pieces_site_keys) editingPiecesCredentials.value = false
    // A confirmed one-shot must not be submitted again if readback fails.
    for (const key of ['onlyonce', 'iyuu_onlyonce']) {
      if (payload[key] && form[key] === draft[key]) form[key] = false
      if (payload[key]) draft[key] = false
    }
    savedDraft = JSON.parse(JSON.stringify({ ...draft, ...payload, onlyonce: false, iyuu_onlyonce: false }))
    const latest = changed ? await readStoredConfig() : stored
    if (!owns()) return
    const refreshed = { ...defaults, ...latest }
    for (const key of new Set([...Object.keys(draft), ...Object.keys(refreshed)])) {
      if (JSON.stringify(form[key]) !== JSON.stringify(draft[key]) && !key.startsWith('auto_delete_')) continue
      if (key in refreshed) form[key] = refreshed[key]
      else delete form[key]
    }
    savedDraft = JSON.parse(JSON.stringify(refreshed))
    const pendingDraft = autoDeletePane.value?.dirty || Object.keys(form).some(key => !key.startsWith('auto_delete_')
      && JSON.stringify(form[key]) !== JSON.stringify(savedDraft[key]))
    saveNotice.value = pendingDraft ? '配置已保存，还有新修改待保存' : '配置已保存'
    void refreshOverview().catch(() => {})
  } catch (error) {
    if (!owns()) return
    saveProblem.value = true
    const reason = draft.pieces_site_keys ? '保存未确认，请检查配置后重试。' : error?.message || '保存未确认，请检查后重试。'
    saveNotice.value = written ? '配置已保存，未能回读最新状态。'
      : autoSaved ? `自动删除设置已保存，其他配置未确认：${reason}` : reason
  } finally {
    if (owns()) saving.value = false
  }
}

watch(() => autoDeletePane.value?.error, (current, previous) => {
  if (!current && previous && saveProblem.value && saveNotice.value === previous) saveNotice.value = ''
})

function selectMain(key) {
  if (activeMain.value === key) return
  if (key === 'auto_delete') autoDeleteVisited.value = true
  if (key === 'sync_delete') syncDeleteVisited.value = true
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || ''
}

function formatSpeed(value) {
  const speed = Number(value || 0)
  if (!speed) return '未建立'
  if (speed >= 1024 * 1024) return `${(speed / 1024 / 1024).toFixed(2)} MiB/s`
  return `${(speed / 1024).toFixed(1)} KiB/s`
}

function speedMiB(mapping, downloaderId) {
  const speed = Number(mapping?.[downloaderId] || 0)
  return speed > 0 ? Number((speed / 1024 / 1024).toFixed(3)) : null
}

function setSpeedMiB(field, downloaderId, value) {
  const mapping = { ...(form[field] || {}) }
  const speed = Number(value)
  if (Number.isFinite(speed) && speed > 0 && speed <= 102400) {
    mapping[downloaderId] = speed * 1024 * 1024
  } else {
    delete mapping[downloaderId]
  }
  form[field] = mapping
}

function uploadDownloaderLimit(downloaderId) {
  const value = Number(form.upload_limit_downloader_limits_kib?.[downloaderId] || 0)
  return value > 0 ? value : null
}

function setUploadDownloaderLimit(downloaderId, value) {
  const mapping = { ...(form.upload_limit_downloader_limits_kib || {}) }
  const normalized = Number(value)
  if (Number.isFinite(normalized) && normalized > 0) mapping[downloaderId] = Math.floor(normalized)
  else delete mapping[downloaderId]
  form.upload_limit_downloader_limits_kib = mapping
}

function formatUploadRate(value) {
  const speed = Number(value || 0)
  if (speed >= 1024 * 1024) return `${(speed / 1024 / 1024).toFixed(2)} MiB/s`
  return `${(speed / 1024).toFixed(1)} KiB/s`
}

function cloneUploadSiteRules(rules = form.upload_limit_site_rules) {
  return Object.fromEntries(Object.entries(rules || {}).map(([name, rule]) => [name, { ...rule }]))
}

function queueUploadSiteRulesSave(rules) {
  const snapshot = cloneUploadSiteRules(rules)
  const revision = ++uploadSiteRulesRevision
  const draftRevision = configDraftRevision
  const pluginId = props.pluginId
  const api = props.api
  const ownsDraft = () => !configDisposed && draftRevision === configDraftRevision && pluginId === props.pluginId
  uploadSiteRulesSaveTail = uploadSiteRulesSaveTail.catch(() => undefined).then(async () => {
    if (!ownsDraft()) return null
    const response = await postPluginJsonApi(api, pluginId, 'upload_limit_site_rules_update', { rules: snapshot })
    if (!ownsDraft()) return null
    if (response?.code !== 0) throw new Error(response?.msg || '站点策略保存失败')
    if (revision === uploadSiteRulesRevision) {
      form.upload_limit_site_rules = cloneUploadSiteRules(response?.rules || snapshot)
      uploadMessageStatus.value = 'success'
      uploadMessage.value = response?.msg || '站点策略已立即生效'
    }
    return response
  }).catch(error => {
    if (isApiRequestCancellation(error)) throw error
    if (!ownsDraft()) return null
    if (revision === uploadSiteRulesRevision) {
      uploadMessageStatus.value = 'error'
      uploadMessage.value = error?.message || '站点策略保存失败'
    }
    throw error
  })
  void uploadSiteRulesSaveTail.catch(() => undefined)
  return uploadSiteRulesSaveTail
}

async function flushUploadSiteRulesSave() {
  await uploadSiteRulesSaveTail
}

function setUploadSiteRule(siteName, value) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  const current = rules[siteName] || { limit_kib: 0 }
  const limit = Number(value)
  current.limit_kib = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 0
  rules[siteName] = current
  form.upload_limit_site_rules = rules
  queueUploadSiteRulesSave(rules)
}

function removeUploadSiteRule(siteName) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  delete rules[siteName]
  form.upload_limit_site_rules = rules
  queueUploadSiteRulesSave(rules)
}

async function clearUploadSiteRules() {
  const owns = configRequestScope()
  uploadActionRunning.value = 'site-rules'
  uploadMessage.value = ''
  const previousRules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  form.upload_limit_site_rules = {}
  try {
    const response = await queueUploadSiteRulesSave({})
    if (!owns() || !response) return
    form.upload_limit_site_rules = {}
    uploadMessageStatus.value = 'success'
    uploadMessage.value = '站点策略已清空并立即生效；所有任务仅受下载器全局上限约束'
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    form.upload_limit_site_rules = previousRules
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '站点策略清空失败'
  } finally {
    if (owns()) uploadActionRunning.value = ''
  }
}

function applyUploadStatus(response) {
  if (!response || (response.code !== 0 && !response.service_status)) return
  overview.value = { ...(overview.value || {}), upload_limit: response }
}

async function refreshUploadLimitStatus({ silent = false } = {}) {
  const owns = configRequestScope()
  if (!silent) {
    uploadActionRunning.value = 'refresh'
    uploadMessage.value = ''
  }
  try {
    const response = await getApi(
      'upload_limit_status',
      silent ? { feedback: 'silent' } : {},
    )
    if (!owns()) return
    applyUploadStatus(response)
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    if (silent) console.error('上传限速状态自动刷新失败:', error)
    else {
      uploadMessageStatus.value = 'error'
      uploadMessage.value = error?.message || '状态刷新失败'
    }
  } finally {
    if (!silent && owns()) uploadActionRunning.value = ''
  }
}

function isUploadStatusVisible() {
  return activeMain.value === 'upload'
    && activeSub.value === 'upload_status'
    && document.visibilityState === 'visible'
}

async function refreshVisibleUploadLimitStatus() {
  if (!isUploadStatusVisible() || uploadStatusRefreshPending || uploadActionRunning.value) return
  uploadStatusRefreshPending = true
  try {
    await refreshUploadLimitStatus({ silent: true })
  } finally {
    uploadStatusRefreshPending = false
  }
}

function stopUploadStatusAutoRefresh() {
  if (!uploadStatusRefreshTimer) return
  window.clearInterval(uploadStatusRefreshTimer)
  uploadStatusRefreshTimer = null
}

function syncUploadStatusAutoRefresh() {
  stopUploadStatusAutoRefresh()
  if (!isUploadStatusVisible()) return
  void refreshVisibleUploadLimitStatus()
  uploadStatusRefreshTimer = window.setInterval(refreshVisibleUploadLimitStatus, UPLOAD_STATUS_REFRESH_INTERVAL_MS)
}

watch([activeMain, activeSub], syncUploadStatusAutoRefresh, { flush: 'post' })
watch([activeSub, canManage], () => { editingPiecesCredentials.value = false }, { flush: 'sync' })

onMounted(() => {
  document.addEventListener('visibilitychange', syncUploadStatusAutoRefresh)
  syncUploadStatusAutoRefresh()
})

onBeforeUnmount(stopUploadStatusAutoRefresh)
onBeforeUnmount(() => {
  configDisposed = true
  configDraftRevision++
  document.removeEventListener('visibilitychange', syncUploadStatusAutoRefresh)
})

async function scanUploadSites() {
  const owns = configRequestScope()
  uploadMessage.value = ''
  if (!form.upload_limit_downloaders?.length) {
    uploadMessageStatus.value = 'warning'
    uploadMessage.value = '请先选择限速下载器'
    return
  }
  uploadScanningSites.value = true
  const scanOperation = (async () => {
    await flushUploadSiteRulesSave()
    if (!owns()) return null
    return postJsonApi('upload_limit_site_tags', {
      downloaders: form.upload_limit_downloaders,
      rules: cloneUploadSiteRules(),
    })
  })()
  uploadSiteScanTail = scanOperation
  try {
    const response = await scanOperation
    if (!owns()) return
    uploadSiteItems.value = response?.items || []
    form.upload_limit_site_rules = response?.rules || form.upload_limit_site_rules || {}
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || `扫描到 ${uploadSiteItems.value.length} 个站点标签，策略已立即生效`
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '站点扫描失败'
  } finally {
    if (uploadSiteScanTail === scanOperation) uploadSiteScanTail = Promise.resolve()
    if (owns()) uploadScanningSites.value = false
  }
}

async function reallocateUploadLimits() {
  const owns = configRequestScope()
  uploadActionRunning.value = 'reallocate'
  uploadMessage.value = ''
  try {
    await uploadSiteScanTail
    await flushUploadSiteRulesSave()
    if (!owns()) return
    const response = await postJsonApi('upload_limit_reallocate', {})
    if (!owns()) return
    applyUploadStatus(response)
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || '上传额度已重新分配'
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '重新分配失败'
  } finally {
    if (owns()) uploadActionRunning.value = ''
  }
}

async function disableAndRestoreUploadLimits() {
  const owns = configRequestScope()
  uploadActionRunning.value = 'restore'
  uploadMessage.value = ''
  try {
    const response = await postJsonApi('upload_limit_disable_restore', {})
    if (!owns()) return
    form.upload_limit_enabled = false
    uploadRestoreDialog.value = false
    await refreshUploadLimitStatus()
    if (!owns()) return
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || '上传限速已停用并恢复'
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '停用恢复失败'
  } finally {
    if (owns()) uploadActionRunning.value = ''
  }
}

function dispositionLabel(action) {
  return {
    close: '关闭告警', request_delete: '等待删除确认', cancel_delete: '取消删除',
    confirm_delete: '删除成功', delete_failed: '删除失败', recovered: '速度恢复',
    completed: '任务完成', deleted: '任务删除',
  }[action] || action || '暂无处置'
}

async function resetMonitorBaseline(downloaderId) {
  const owns = configRequestScope()
  monitorResetting.value = downloaderId
  monitorMessage.value = ''
  try {
    const response = await postJsonApi('reset_speed_monitor_baseline', { downloader_id: downloaderId })
    if (!owns()) return
    monitorMessageStatus.value = response?.code === 0 ? 'success' : 'error'
    monitorMessage.value = response?.msg || (response?.code === 0 ? '速度基准已重置' : '重置失败')
    if (response?.code === 0) await refreshOverview()
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    monitorMessageStatus.value = 'error'
    monitorMessage.value = error?.message || '重置失败'
  } finally {
    if (owns()) monitorResetting.value = ''
  }
}

function tagSelectionKey(downloader, tag) {
  return `${downloader}\u0000${tag}`
}

function resetCleanupKeep(groups) {
  Object.keys(cleanupKeep).forEach(key => delete cleanupKeep[key])
  for (const group of groups || []) {
    for (const item of group.tags || []) {
      cleanupKeep[tagSelectionKey(group.name, item.tag)] = item.kind !== 'legacy_candidate'
    }
  }
}

function setAllCleanupTags(keep) {
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) cleanupKeep[tagSelectionKey(group.name, item.tag)] = keep
  }
}

function cleanupKindMeta(kind) {
  return {
    site: { label: '站点', color: 'primary' },
    managed: { label: '业务', color: 'success' },
    temporary: { label: '临时', color: 'warning' },
    legacy_temporary: { label: '旧临时', color: 'warning' },
    legacy_candidate: { label: '疑似旧临时', color: 'warning' },
    active_temporary: { label: '使用中', color: 'info' },
    other: { label: '其他', color: 'default' },
  }[kind] || { label: '其他', color: 'default' }
}

async function scanCleanupTags() {
  const owns = configRequestScope()
  cleanupMessage.value = ''
  if (!cleanupDownloaders.value.length) {
    cleanupStatus.value = 'warning'
    cleanupMessage.value = '请先选择下载器'
    return
  }
  cleanupScanning.value = true
  try {
    const response = await postJsonApi('tag_cleanup_scan', { downloaders: cleanupDownloaders.value })
    if (!owns()) return
    cleanupScan.value = response || null
    resetCleanupKeep(response?.downloaders || [])
    const errorCount = response?.errors?.length || 0
    const skippedCount = response?.skipped?.length || 0
    cleanupStatus.value = response?.code === 0 ? (errorCount ? 'warning' : 'success') : 'error'
    cleanupMessage.value = response?.code === 0
      ? `扫描完成 · 自动清理 ${response?.auto_removed?.length || 0} 个临时标签 · ${skippedCount} 项无需处理`
      : (response?.msg || '扫描失败')
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    cleanupStatus.value = 'error'
    cleanupMessage.value = error?.message || '扫描失败'
  } finally {
    if (owns()) cleanupScanning.value = false
  }
}

function previewCleanupTags() {
  if (!cleanupRemovals.value.length) {
    cleanupStatus.value = 'warning'
    cleanupMessage.value = '没有需要清理的标签'
    return
  }
  cleanupDialog.value = true
}

async function executeCleanupTags() {
  const owns = configRequestScope()
  cleanupExecuting.value = true
  try {
    const response = await postJsonApi('tag_cleanup_execute', { removals: cleanupRemovals.value })
    if (!owns()) return
    cleanupDialog.value = false
    await scanCleanupTags()
    if (!owns()) return
    cleanupStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    cleanupMessage.value = response?.msg || '清理完成'
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    cleanupStatus.value = 'error'
    cleanupMessage.value = error?.message || '清理失败'
  } finally {
    if (owns()) cleanupExecuting.value = false
  }
}

function tagCompletionSelectionKey(downloader, kind, tag) {
  return `${downloader}\u0000${kind}\u0000${tag}`
}

function resetCompletionSelection(groups) {
  Object.keys(completionKeep).forEach(key => delete completionKeep[key])
  for (const group of groups || []) {
    for (const item of group.tags || []) {
      completionKeep[tagCompletionSelectionKey(group.name, item.kind, item.tag)] = true
    }
  }
}

function setAllCompletionTags(selected) {
  for (const group of completionGroups.value) {
    for (const item of group.tags || []) {
      completionKeep[tagCompletionSelectionKey(group.name, item.kind, item.tag)] = selected
    }
  }
}

function completionKindMeta(kind) {
  return {
    official: { label: '官种', color: 'warning' },
    site: { label: '站点', color: 'primary' },
    transfer: { label: '转种', color: 'success' },
    iyuu: { label: 'IYUU铺种', color: 'info' },
  }[kind] || { label: '其他', color: 'default' }
}

function completionRequestId() {
  return globalThis.crypto?.randomUUID?.()
    || `tag-completion-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function completionTaskIsActive(task) {
  return ['queued', 'running', 'cancelling'].includes(task?.status)
}

function completionTaskText(task) {
  const progress = task?.total ? ` ${task.current}/${task.total}` : ''
  return `${task?.phase || '后台任务运行中'}${progress}`
}

function waitForCompletionDelay() {
  return new Promise(resolve => setTimeout(resolve, 800))
}

async function pollTagCompletionTask(task, owns) {
  let current = task
  let statusFailures = 0
  while (completionTaskIsActive(current)) {
    if (!owns()) return null
    completionTask.value = current
    completionMessage.value = completionTaskText(current)
    try {
      current = await getApi('tag_completion_task', {
        params: { task_id: current.task_id },
        feedback: 'silent',
      })
      statusFailures = 0
    } catch (error) {
      if (isApiRequestCancellation(error)) return null
      statusFailures += 1
      if (statusFailures >= 5) {
        const unavailable = new Error('任务仍在后台运行，但状态接口暂时不可用；刷新页面可继续查询，请勿重复提交。')
        unavailable.tagCompletionUnknown = true
        throw unavailable
      }
    }
    if (!owns()) return null
    if (!current?.found) throw new Error('任务状态已失效；请先重新扫描核对，不要直接重复确认。')
    completionTask.value = current
    if (completionTaskIsActive(current)) {
      completionMessage.value = completionTaskText(current)
      await waitForCompletionDelay()
    }
  }
  return current
}

async function submitAndWaitTagCompletionTask(path, payload, requestId, owns, onAccepted = null) {
  let accepted
  try {
    accepted = await postJsonApi(path, payload, { feedback: 'silent' })
  } catch (error) {
    if (isApiRequestCancellation(error)) throw error
    if (Number(error?.response?.status || error?.status) !== 504) throw error
    try {
      accepted = await getApi('tag_completion_task', {
        params: { request_id: requestId },
        feedback: 'silent',
      })
    } catch (statusError) {
      if (isApiRequestCancellation(statusError)) throw statusError
      accepted = null
    }
    if (!accepted?.found) accepted = await postJsonApi(path, payload, { feedback: 'silent' })
  }
  if (!owns()) return null
  if (accepted?.code !== 0 || !accepted?.task_id) {
    throw new Error(accepted?.msg || '后台任务未能提交')
  }
  onAccepted?.()
  return pollTagCompletionTask(accepted, owns)
}

async function readTagCompletionResult(taskId, owns) {
  let offset = 0
  let merged = null
  while (true) {
    const response = await getApi('tag_completion_result', {
      params: { task_id: taskId, offset, limit: 200 },
      feedback: 'silent',
    })
    if (!owns()) return null
    if (response?.code !== 0 || !response?.result) {
      throw new Error(response?.msg || '任务已结束，但结果暂不可读取')
    }
    const page = response.result
    if (!merged) {
      merged = page
    } else if (Array.isArray(page.downloaders)) {
      const downloaders = new Map((merged.downloaders || []).map(item => [item.name, item]))
      for (const downloader of page.downloaders) {
        let target = downloaders.get(downloader.name)
        if (!target) {
          target = { ...downloader, tags: [] }
          downloaders.set(downloader.name, target)
          merged.downloaders.push(target)
        }
        const tags = new Map((target.tags || []).map(item => [`${item.kind}\u0000${item.tag}`, item]))
        for (const tag of downloader.tags || []) {
          const key = `${tag.kind}\u0000${tag.tag}`
          let targetTag = tags.get(key)
          if (!targetTag) {
            targetTag = { ...tag, hashes: [] }
            tags.set(key, targetTag)
            target.tags.push(targetTag)
          }
          targetTag.hashes.push(...(tag.hashes || []))
        }
      }
    } else {
      for (const key of ['added', 'skipped', 'failed']) {
        if (Array.isArray(page[key])) merged[key] = [...(merged[key] || []), ...page[key]]
      }
    }
    if (response.complete !== false) return merged
    const nextOffset = Number(response.next_offset)
    if (!Number.isFinite(nextOffset) || nextOffset <= offset) {
      throw new Error('任务结果分页游标无效，请重新扫描')
    }
    offset = nextOffset
  }
}

async function applyTagCompletionTaskResult(task, owns) {
  if (!task || !owns()) return
  if (task.operation === 'scan' && ['completed', 'partial'].includes(task.status)) {
    const result = await readTagCompletionResult(task.task_id, owns)
    if (!owns()) return
    completionScan.value = { ...result, task_id: task.task_id }
    resetCompletionSelection(result?.downloaders || [])
    completionStatus.value = result?.code === 0 ? (result?.errors?.length ? 'warning' : 'success') : 'error'
    completionMessage.value = result?.msg || '扫描完成'
    return
  }
  if (task.operation === 'execute' && ['completed', 'partial'].includes(task.status)) {
    const result = await readTagCompletionResult(task.task_id, owns)
    if (!owns()) return
    completionDialog.value = false
    completionScan.value = null
    resetCompletionSelection([])
    completionStatus.value = task.status === 'completed' ? 'success' : 'warning'
    completionMessage.value = `${result?.msg || task.message || '补全完成'}。请重新扫描核对剩余标签。`
    return
  }
  if (['cancelled', 'interrupted'].includes(task.status)) {
    completionScan.value = null
    resetCompletionSelection([])
    completionStatus.value = 'warning'
    completionMessage.value = `${task.message || '任务已停止'}；请重新扫描核对，不要直接重放旧任务。`
    return
  }
  if (task.status === 'failed') {
    completionScan.value = null
    completionStatus.value = 'error'
    completionMessage.value = task.message || '标签补全任务失败'
  }
}

async function restoreTagCompletionTask() {
  const owns = configRequestScope()
  try {
    const task = await getApi('tag_completion_task', { feedback: 'silent' })
    if (!owns() || !task?.found) return
    completionTask.value = task
    if (completionTaskIsActive(task)) {
      completionScanning.value = task.operation === 'scan'
      completionExecuting.value = task.operation === 'execute'
      const completed = await pollTagCompletionTask(task, owns)
      if (completed) await applyTagCompletionTaskResult(completed, owns)
    } else {
      await applyTagCompletionTaskResult(task, owns)
    }
  } catch (error) {
    if (isApiRequestCancellation(error) || !owns()) return
    completionStatus.value = 'warning'
    completionMessage.value = error?.message || '无法恢复标签补全任务状态'
  } finally {
    if (owns()) {
      completionScanning.value = false
      completionExecuting.value = false
    }
  }
}

async function scanTagCompletion() {
  const owns = configRequestScope()
  completionMessage.value = ''
  if (!completionDownloaders.value.length) {
    completionStatus.value = 'warning'
    completionMessage.value = '请先选择下载器'
    return
  }
  completionDialog.value = false
  completionScan.value = null
  resetCompletionSelection([])
  completionTask.value = null
  completionScanning.value = true
  const requestId = completionRequestId()
  try {
    const task = await submitAndWaitTagCompletionTask(
      'tag_completion_scan',
      { request_id: requestId, downloaders: completionDownloaders.value },
      requestId,
      owns,
    )
    if (!owns()) return
    await applyTagCompletionTaskResult(task, owns)
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    if (error?.tagCompletionUnknown || Number(error?.response?.status || error?.status) === 504) {
      completionTask.value = { status: 'unknown' }
      completionStatus.value = 'warning'
      completionMessage.value = '扫描任务状态暂不可确定；刷新页面可恢复查询。扫描只读，不会写入标签。'
    } else {
      completionStatus.value = 'error'
      completionMessage.value = error?.message || '扫描失败'
    }
  } finally {
    if (owns()) completionScanning.value = false
  }
}

function previewTagCompletion() {
  if (!completionRepairs.value.length) {
    completionStatus.value = 'warning'
    completionMessage.value = '没有待补全的标签'
    return
  }
  completionDialog.value = true
}

async function executeTagCompletion() {
  const owns = configRequestScope()
  const requestId = completionRequestId()
  completionTask.value = null
  completionExecuting.value = true
  try {
    const task = await submitAndWaitTagCompletionTask(
      'tag_completion_execute',
      {
        request_id: requestId,
        scan_task_id: completionScan.value?.task_id || '',
        repairs: completionSelections.value,
      },
      requestId,
      owns,
      () => { completionDialog.value = false },
    )
    if (!owns()) return
    await applyTagCompletionTaskResult(task, owns)
  } catch (error) {
    if (isApiRequestCancellation(error)) return
    if (!owns()) return
    if (error?.tagCompletionUnknown || Number(error?.response?.status || error?.status) === 504) {
      completionDialog.value = false
      completionTask.value = { status: 'unknown' }
      completionStatus.value = 'warning'
      completionMessage.value = '补全任务状态暂不可读取；刷新页面可继续查询。请勿重复提交，先核对任务结果。'
    } else {
      completionStatus.value = 'error'
      completionMessage.value = error?.message || '补全失败'
    }
  } finally {
    if (owns()) completionExecuting.value = false
  }
}

async function cancelTagCompletionTask() {
  const taskId = completionTask.value?.task_id
  const owns = configRequestScope()
  if (!taskId) return
  try {
    const response = await postJsonApi('tag_completion_cancel', { task_id: taskId }, { feedback: 'silent' })
    if (!owns() || response?.code !== 0) return
    completionTask.value = response
    completionMessage.value = response.msg || '正在停止标签补全任务'
  } catch (error) {
    if (isApiRequestCancellation(error) || !owns()) return
    completionStatus.value = 'warning'
    completionMessage.value = error?.message || '停止任务失败；请刷新状态后再操作'
  }
}

onMounted(() => { void restoreTagCompletionTask() })

let permissionsRevision = 0
let permissionController = null
async function loadPermissions(refresh = false) {
  const revision = ++permissionsRevision
  permissionController?.abort()
  const controller = new AbortController()
  permissionController = controller
  const api = props.api
  const id = props.pluginId
  const current = () => !configDisposed && revision === permissionsRevision && api === props.api && id === props.pluginId
  canManage.value = false
  permissionError.value = ''
  permissionStatus.value = 'loading'
  try {
    const value = await getManagementPermission(api, { signal: controller.signal, refresh: refresh === true })
    if (!current()) return
    if (typeof value?.can_manage !== 'boolean') throw new Error('权限接口未返回明确结果')
    canManage.value = value.can_manage
    permissionStatus.value = value.can_manage ? 'granted' : 'denied'
  } catch (reason) {
    if (!current()) return
    permissionStatus.value = 'error'
    permissionError.value = reason?.name === 'PermissionTimeoutError' ? '权限核验超时，请重新检查。' : isApiRequestCancellation(reason) ? '权限核验被中断，请重新检查。' : '当前登录身份核验失败，请重新检查。'
  } finally {
    if (permissionController === controller) permissionController = null
  }
}
watch(() => [props.api, props.pluginId], loadPermissions, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => permissionController?.abort())
</script>
<template>
  <div class="dm-config">
    <VCard flat class="dm-card">
    <VAlert v-if="permissionStatus !== 'granted'" :type="permissionStatus === 'error' ? 'warning' : 'info'" variant="tonal" density="compact" :data-permission-status="permissionStatus">
      {{ permissionStatus === 'loading' ? '正在核验管理权限…' : permissionStatus === 'denied' ? '当前登录身份没有管理权限，页面为只读模式。' : permissionError }}
      <VBtn v-if="permissionStatus !== 'loading'" size="small" variant="text" class="ml-2" @click="loadPermissions(true)">重新检查</VBtn>
    </VAlert>
      <VCardItem class="dm-header" :inert="saving">
        <template #prepend>
          <VAvatar color="success" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-download" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">下载中心</VCardTitle>
        <VCardSubtitle class="text-caption">{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch v-model="form.enabled" color="success" hide-details inset :label="form.enabled ? '已启用' : '已停用'" />
        </template>
      </VCardItem>
      <VDivider />
      <div class="dm-body" :inert="saving">
        <nav class="dm-nav">
          <VList density="comfortable" nav class="dm-nav-list py-2">
            <VListItem v-for="item in mainTabs" :key="item.key" :active="activeMain === item.key"
              color="primary" rounded="lg" class="dm-nav-item" @click="selectMain(item.key)">
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="dm-content">
          <div class="dm-subtabs">
            <button v-for="sub in currentSubs" :key="sub.key" type="button"
              class="dm-subtab" :class="{ 'dm-subtab--active': activeSub === sub.key }" @click="activeSub = sub.key">
              <VIcon :icon="sub.icon" size="18" class="mr-1" />{{ sub.title }}
            </button>
          </div>
          <VDivider />
          <div class="dm-window" :class="{ 'dm-window--overview': activeMain === 'overview' }">
            <div v-if="activeSub === 'overview'" class="dm-pane dm-pane--overview">
              <div class="dm-overview-section mb-3">
                <div class="dm-section-title">运行链路</div>
                <div class="dm-flow">
                  <div v-for="flow in runtimeFlows" :key="flow.label" class="dm-flow-block">
                    <div class="dm-flow-label">{{ flow.label }}<button v-if="flow.label === '同步删除' && syncDeletePending" type="button" class="dm-flow-review" data-review-module="sync_delete" @click="reviewDialog = true">待处理 {{ syncDeletePending }} 项 · 查看</button></div>
                    <div class="dm-flow-row">
                      <template v-for="(step, index) in flow.steps" :key="`${flow.label}-${step}`">
                        <span class="dm-flow-step">{{ step }}</span>
                        <VIcon v-if="index < flow.steps.length - 1" class="dm-flow-arrow" icon="mdi-arrow-right" size="14" />
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- ═══ 上传限速 · 基础设置 ═══ -->
            <div v-if="activeSub === 'upload_basic'" class="dm-pane">
              <div class="dm-form-section-heading">
                <div class="dm-section-title">上传限速设置</div>
                <VSwitch v-model="form.upload_limit_enabled" color="success" inset hide-details density="compact" label="启用上传限速" />
              </div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSelect v-model="form.upload_limit_downloaders" label="限速下载器" density="compact" variant="outlined"
                    :items="uploadDownloaderItems" multiple chips closable-chips clearable hide-details />
                  <div class="dm-hint">只扫描和修改这里选中的 qBittorrent / Transmission 实例</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model.number="form.upload_limit_grace_minutes" label="新种宽限（分钟）" type="number" min="0" max="1440"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">默认 30；填 0 表示完成后立即纳入分配</div>
                </VCol>
              </VRow>

              <div class="dm-section-title mt-4">下载器总上限</div>
              <div v-if="uploadSelectedDownloaders.length" class="dm-upload-downloader-list">
                <div v-for="item in uploadSelectedDownloaders" :key="item.value" class="dm-upload-config-row">
                  <div class="dm-upload-config-name">
                    <VIcon :icon="item.type === 'transmission' ? 'mdi-transmission-tower' : 'mdi-download-network-outline'" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong>{{ item.title }}</strong>
                      <div class="text-caption text-medium-emphasis">
                        {{ item.type === 'transmission' ? 'Transmission Session 上传上限' : 'qB 普通与备用上传上限' }}
                      </div>
                    </div>
                  </div>
                  <VTextField :model-value="uploadDownloaderLimit(item.value)"
                    @update:model-value="setUploadDownloaderLimit(item.value, $event)"
                    label="总上限（KiB/s）" type="number" min="1" step="1" density="compact" variant="outlined"
                    hint="必须大于 0；以插件配置为准" persistent-hint />
                </div>
              </div>
              <div v-else class="dm-monitor-empty">尚未选择限速下载器</div>

              <VAlert v-if="form.upload_limit_enabled && !uploadSelectedDownloaders.length" type="warning" variant="tonal" density="compact" class="mt-4">
                请至少选择一个 qBittorrent 或 Transmission 下载器，并设置正整数总上限。
              </VAlert>
              <VAlert v-else-if="form.upload_limit_enabled && uploadMissingLimits.length" type="warning" variant="tonal" density="compact" class="mt-4">
                {{ uploadMissingLimits.map(item => item.title).join('、') }} 尚未设置正整数总上限，保存后上传限速不会启动。
              </VAlert>

              <VAlert type="info" variant="tonal" density="compact" class="mt-4">
                单位为 KiB/s（1 Mbps ≈ 122 KiB/s）。宽限期间不做站点和单种分配，但仍受对应下载器总上传上限。
              </VAlert>
            </div>

            <!-- ═══ 上传限速 · 站点策略 ═══ -->
            <div v-if="activeSub === 'upload_filter'" class="dm-pane">
              <div class="dm-upload-toolbar">
                <div>
                  <div class="dm-section-title mb-1">站点限速</div>
                  <div class="text-caption text-medium-emphasis">扫描只添加站点名称，不预填上限；只有填写正数的站点才会限制合计上传速度。</div>
                </div>
                <div class="d-flex align-center ga-2">
                  <VBtn color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="uploadScanningSites"
                    :disabled="!canManage || uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    @click="scanUploadSites">扫描站点</VBtn>
                  <VBtn color="error" variant="text" prepend-icon="mdi-delete-sweep-outline"
                    :disabled="!canManage || !uploadSiteRuleRows.length || uploadScanningSites || uploadActionRunning === 'reallocate'"
                    :loading="uploadActionRunning === 'site-rules'"
                    @click="clearUploadSiteRules">清空策略</VBtn>
                </div>
              </div>

              <VAlert type="info" variant="tonal" density="compact" class="mt-3">
                仅识别唯一有效的「{{ form.tag_siteprefix || '🏠' }}站点名」标签。上限留空或填 0 时不写单种限速，该站点仍受下载器全局上限约束。
              </VAlert>

              <VAlert v-if="uploadMessage" :type="uploadMessageStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="uploadMessage = ''">{{ uploadMessage }}</VAlert>

              <div v-if="uploadSiteRuleRows.length" class="dm-upload-site-list mt-4">
                <div v-for="row in uploadSiteRuleRows" :key="row.name" class="dm-upload-site-row">
                  <div class="dm-upload-site-name">
                    <VIcon icon="mdi-home-outline" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong class="text-body-2">{{ row.name }}</strong>
                      <div class="text-caption text-medium-emphasis">{{ form.tag_siteprefix || '🏠' }}{{ row.name }}</div>
                    </div>
                  </div>
                  <VTextField :model-value="row.limit_kib" @update:model-value="setUploadSiteRule(row.name, $event)"
                    label="合计上限（KiB/s）" type="number" min="0" step="1" clearable density="compact" variant="outlined"
                    :disabled="!canManage || uploadScanningSites || uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    hint="留空或 0 表示该站点不限速；正数为跨下载器共享的站点合计上限" persistent-hint />
                  <VBtn icon="mdi-delete-outline" size="small" color="error" variant="text" title="删除站点"
                    :disabled="!canManage || uploadScanningSites || uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    @click="removeUploadSiteRule(row.name)" />
                </div>
              </div>
              <div v-else class="dm-monitor-empty mt-3">尚未扫描站点；没有站点上限时只应用下载器全局上限</div>

              <VAlert type="info" variant="tonal" density="compact" class="mt-4">
                正数上限限制该站点全部任务的合计上传速度；多个受限站点在下载器全局额度内按实际需求共享可用带宽。
              </VAlert>
            </div>

            <!-- ═══ 上传限速 · 运行状态 ═══ -->
            <div v-if="activeSub === 'upload_status'" class="dm-pane">
              <div class="dm-upload-toolbar">
                <div>
                  <div class="dm-section-title mb-1">运行状态</div>
                  <div class="text-caption text-medium-emphasis">MP 或插件离线时，下载器继续保留最后一次已写入的限速。</div>
                </div>
                <div class="d-flex ga-2 flex-wrap justify-end">
                  <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="uploadActionRunning === 'refresh'"
                    @click="refreshUploadLimitStatus">刷新</VBtn>
                  <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-call-split"
                    :loading="uploadActionRunning === 'reallocate'"
                    :disabled="!canManage || !uploadLimit.enabled || uploadScanningSites || uploadActionRunning === 'site-rules'"
                    @click="reallocateUploadLimits">立即分配</VBtn>
                  <VBtn size="small" color="warning" variant="tonal" prepend-icon="mdi-backup-restore"
                    :disabled="!canManage || !uploadLimit.active && !uploadLimit.enabled" @click="uploadRestoreDialog = true">停用并恢复</VBtn>
                </div>
              </div>

              <VAlert v-if="uploadMessage" :type="uploadMessageStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="uploadMessage = ''">{{ uploadMessage }}</VAlert>
              <VAlert v-for="error in uploadLimit.errors || []" :key="error" type="warning" variant="tonal" density="compact" class="mt-2">
                {{ error }}
              </VAlert>

              <div class="dm-upload-summary mt-4">
                <div class="dm-monitor-metric"><span>服务</span><strong>{{ uploadLimitStatus.label }}</strong></div>
                <div class="dm-monitor-metric"><span>实时速率</span><strong>{{ formatUploadRate(uploadLimit.upload_rate_bps) }}</strong></div>
                <div class="dm-monitor-metric"><span>受限任务</span><strong>{{ uploadLimit.managed_torrents || 0 }}</strong></div>
                <div class="dm-monitor-metric"><span>宽限任务</span><strong>{{ uploadLimit.grace_torrents || 0 }}</strong></div>
              </div>
              <div class="dm-hint mt-2">实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。</div>

              <div class="dm-section-title mt-4">下载器状态</div>
              <div v-if="uploadLimitDownloaderRows.length" class="dm-upload-status-grid">
                <div v-for="item in uploadLimitDownloaderRows" :key="item.id" class="dm-upload-status-card">
                  <div class="dm-upload-status-head">
                    <div class="min-w-0">
                      <strong class="text-body-2">{{ item.id }}</strong>
                      <div class="text-caption text-medium-emphasis">{{ item.type === 'transmission' ? 'Transmission' : 'qBittorrent' }}</div>
                    </div>
                    <VChip size="x-small" :color="item.error ? 'warning' : 'success'" variant="tonal">{{ item.error ? '异常' : '正常' }}</VChip>
                  </div>
                  <div class="dm-upload-values">
                    <span>实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                    <span>{{ item.type === 'transmission' ? 'Session 全局上限' : 'QB 全局上限' }} <strong>{{ item.total_limit_kib }} KiB/s</strong></span>
                    <span>受限任务 <strong>{{ item.managed_torrents || 0 }}</strong></span>
                    <span>宽限任务 <strong>{{ item.grace_torrents || 0 }}</strong></span>
                  </div>
                  <div v-if="item.error" class="text-caption text-warning mt-2 dm-break-text">{{ item.error }}</div>
                </div>
              </div>
              <div v-else class="dm-monitor-empty">当前没有启用的限速下载器</div>

              <div class="dm-section-title mt-4">受限站点</div>
              <div v-if="uploadLimitSiteRows.length" class="dm-upload-site-status">
                <div v-for="item in uploadLimitSiteRows" :key="item.key" class="dm-upload-site-status-row">
                  <div class="min-w-0">
                    <strong class="text-body-2">{{ item.name }}</strong>
                    <div class="text-caption text-medium-emphasis">{{ item.torrent_count }} 个任务 · {{ item.downloaders?.join('、') }}</div>
                  </div>
                  <span class="text-caption">实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                  <span class="text-caption">站点额度 <strong>{{ item.allocated_kib }} KiB/s</strong></span>
                  <span class="text-caption">站点上限 <strong>{{ item.limit_kib }} KiB/s</strong></span>
                </div>
              </div>
              <div v-else class="dm-monitor-empty">当前没有填写正数上限的受限站点</div>
            </div>

            <!-- ═══ 速度监控 · 基础设置 ═══ -->
            <div v-if="activeSub === 'monitor_basic'" class="dm-pane">
              <div class="dm-form-section-heading">
                <div class="dm-section-title">速度监控设置</div>
                <VSwitch v-model="form.speed_monitor_enabled" color="success" inset hide-details density="compact" label="启用监控" />
              </div>
              <div class="dm-monitor-basic-grid" data-monitor-basic-grid>
                <div>
                  <VSelect v-model="form.speed_monitor_downloaders" label="监控下载器" density="compact" variant="outlined"
                    :items="monitorDownloaderItems" multiple chips closable-chips clearable hide-details />
                  <div class="dm-hint">支持 qBittorrent 和 Transmission</div>
                </div>
                <div>
                  <VSelect v-model="form.speed_monitor_mode" label="基准模式" density="compact" variant="outlined" hide-details
                    :items="monitorModeItems" />
                </div>
                <div>
                  <VTextField v-model.number="form.speed_monitor_interval_seconds" label="活跃扫描间隔（秒）" type="number" min="10" max="300"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">范围 10–300 秒，默认 30 秒。</div>
                </div>
                <div>
                  <VSelect v-model="form.speed_monitor_notification_type" label="通知分类" density="compact" variant="outlined" hide-details
                    :items="notificationTypeItems" />
                </div>
              </div>
              <div class="dm-hint mt-3">判定阈值在条件筛选中调整。</div>
              <VAlert type="info" variant="tonal" density="compact" class="mt-4">
                速度监控独立于转移做种和 IYUU；插件总开关、监控开关和至少一个下载器同时启用后才运行。
              </VAlert>
            </div>

            <!-- ═══ 速度监控 · 阈值策略 ═══ -->
            <div v-if="activeSub === 'monitor_filter'" class="dm-pane">
              <div class="dm-section-title">任务范围</div>
              <VRow class="mb-3 dm-form-grid dm-form-grid--one"><VCol cols="12" class="dm-form-field"><VTextField v-model="form.speed_monitor_exclude_categories" label="排除分类关键词" density="compact" variant="outlined" clearable hide-details />
              <div class="dm-hint">逗号分隔；qB 分类或 Transmission group 命中任一关键词的任务不进入速度监控</div></VCol></VRow>
              <div class="dm-section-title">采样与判定</div>
              <VRow class="dm-form-grid dm-form-grid--four">
                <VCol cols="12" sm="6" md="3" class="dm-form-field">
                  <VTextField v-model.number="form.speed_monitor_grace_minutes" label="启动宽限（分钟）" type="number" min="0" max="1440"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">范围 0–1440</div>
                </VCol>
                <VCol cols="12" sm="6" md="3" class="dm-form-field">
                  <VTextField v-model.number="form.speed_monitor_tolerance" label="允许时长倍数" type="number" min="1.01" step="0.1"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">必须大于 1</div>
                </VCol>
                <VCol cols="12" sm="6" md="3" class="dm-form-field">
                  <VTextField v-model.number="form.speed_monitor_consecutive_abnormal_samples" label="连续异常次数" type="number" min="1" max="10"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">范围 1–10</div>
                </VCol>
                <VCol cols="12" sm="6" md="3" class="dm-form-field">
                  <VTextField v-model.number="form.speed_monitor_min_samples" label="可信样本门槛" type="number" min="1" max="100"
                    density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">范围 1–100，默认 5</div>
                </VCol>
              </VRow>

              <VAlert type="info" variant="tonal" density="compact" class="mt-3 dm-threshold-suggestion">
                <div class="dm-threshold-suggestion-head">
                  <div class="dm-threshold-suggestion-title">样本建议</div>
                  <VBtn size="small" variant="tonal" color="primary" prepend-icon="mdi-check-all"
                    :disabled="!speedThresholdSuggestionRows.some(row => row.available)"
                    @click="applyAllSpeedThresholdSuggestions">应用全部可用建议</VBtn>
                </div>
                <div class="dm-threshold-suggestion-list">
                  <div v-for="row in speedThresholdSuggestionRows" :key="row.label" class="dm-threshold-suggestion-row">
                    <span class="dm-threshold-suggestion-label">{{ row.label }}</span>
                    <span class="dm-threshold-suggestion-current">当前值 {{ row.current }}</span>
                    <strong class="dm-threshold-suggestion-suggested">建议值 {{ row.suggested }}</strong>
                    <VBtn size="x-small" variant="text" color="primary" prepend-icon="mdi-check-circle-outline"
                      class="dm-threshold-suggestion-action" :disabled="!row.available"
                      @click="applySpeedThresholdSuggestion(row)">采用建议</VBtn>
                  </div>
                </div>
              </VAlert>

              <div class="dm-section-title mt-4">每下载器速度</div>
              <VAlert v-if="!form.speed_monitor_downloaders?.length" type="warning" variant="tonal" density="compact">
                请先在基础设置中选择监控下载器。
              </VAlert>
              <div v-else class="dm-monitor-speed-list">
                <div v-for="downloaderId in form.speed_monitor_downloaders" :key="downloaderId" class="dm-monitor-speed-row">
                  <div class="dm-monitor-speed-name"><VIcon icon="mdi-download-network-outline" size="18" />{{ downloaderId }}</div>
                  <VTextField v-if="form.speed_monitor_mode === 'manual'"
                    :model-value="speedMiB(form.speed_monitor_manual_speed_bps, downloaderId)"
                    @update:model-value="setSpeedMiB('speed_monitor_manual_speed_bps', downloaderId, $event)"
                    label="最低期望速度（MiB/s）" type="number" min="0.01" max="102400" step="0.1"
                    density="compact" variant="outlined" hint="手动模式必填，范围 0.01–102400 MiB/s" persistent-hint />
                  <VTextField v-else
                    :model-value="speedMiB(form.speed_monitor_floor_speed_bps, downloaderId)"
                    @update:model-value="setSpeedMiB('speed_monitor_floor_speed_bps', downloaderId, $event)"
                    label="保护下限（MiB/s）" type="number" min="0.01" max="102400" step="0.1" clearable
                    density="compact" variant="outlined" hint="可留空；填写后与自动基准取较大值" persistent-hint />
                </div>
              </div>
              <VAlert v-if="form.speed_monitor_mode === 'auto'" type="info" variant="tonal" density="compact" class="mt-3">
                未设置保护下限时，自动模式只能相对历史健康样本判断，无法识别首批样本整体偏慢。
              </VAlert>
            </div>

            <!-- ═══ 速度监控 · 运行状态 ═══ -->
            <div v-if="activeSub === 'monitor_status'" class="dm-pane">
              <div class="dm-section-title">运行状态</div>
              <VAlert v-if="monitorMessage" :type="monitorMessageStatus" variant="tonal" density="compact" closable class="mb-3"
                @click:close="monitorMessage = ''">{{ monitorMessage }}</VAlert>
              <div class="dm-monitor-summary">
                <div class="dm-monitor-metric"><span>服务</span><strong>{{ speedMonitorStatus.label }}</strong></div>
                <div class="dm-monitor-metric"><span>选中下载器</span><strong>{{ speedMonitor.selected_downloaders?.length || 0 }}</strong></div>
                <div class="dm-monitor-metric"><span>活跃会话</span><strong>{{ speedMonitor.active_sessions || 0 }}</strong></div>
                <div class="dm-monitor-metric"><span>待处理告警</span><strong>{{ speedMonitor.pending_alerts || 0 }}</strong></div>
              </div>
              <VAlert v-if="speedMonitor.state_error" type="error" variant="tonal" density="compact" class="mt-3">{{ speedMonitor.state_error }}</VAlert>

              <div class="dm-section-title mt-4">下载器基准</div>
              <div v-if="speedBaselines.length" class="dm-monitor-baselines">
                <div v-for="item in speedBaselines" :key="item.downloader_id" class="dm-monitor-baseline">
                  <div class="dm-monitor-baseline-head">
                    <div class="min-w-0">
                      <strong class="text-body-2">{{ item.downloader_id }}</strong>
                      <div class="text-caption text-medium-emphasis">{{ item.status === 'trusted' ? '可信基准' : '校准中' }} · {{ item.sample_count }}/{{ item.min_samples }} 样本</div>
                    </div>
                    <VBtn :disabled="!canManage" v-if="speedMonitor.mode === 'auto'" size="small" variant="tonal" color="warning" icon="mdi-restart"
                      :loading="monitorResetting === item.downloader_id" title="重置自动基准" @click="resetMonitorBaseline(item.downloader_id)" />
                  </div>
                  <div class="dm-baseline-values">
                    <span>当前参考 <strong>{{ formatSpeed(item.reference_speed_bps) }}</strong></span>
                    <span>可信 <strong>{{ formatSpeed(item.trusted_speed_bps) }}</strong></span>
                    <span>临时 <strong>{{ formatSpeed(item.provisional_speed_bps) }}</strong></span>
                  </div>
                  <div v-if="item.relative_only" class="dm-relative-note">相对基准：未配置绝对保护下限</div>
                </div>
              </div>
              <div v-else class="dm-monitor-empty">尚无下载器基准数据</div>

              <div class="dm-hint mt-4">最近处置及执行记录请在详情页查看。</div>

              <VAlert type="error" variant="tonal" density="compact" class="mt-4">
                Telegram 二次确认后会删除种子及全部数据，且不可恢复；关闭告警不会删除任务。
              </VAlert>
              <VAlert type="info" variant="tonal" density="compact" class="mt-2">
                如有换种需求，可配合订阅助手增强版（SubscribeAssistantEnhanced）使用，由其负责监听 MoviePilot 删除事件。
              </VAlert>
            </div>

            <!-- ═══ 转移做种 · 基础设置 ═══ -->
            <div v-if="activeSub === 'basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSelect v-model="form.fromdownloader" label="源下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" />
                  <div class="dm-hint">选择源下载器</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSelect v-model="form.todownloader" label="目的下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" />
                  <div class="dm-hint">选择目的下载器</div>
                </VCol>
              </VRow>
              <VAlert
                v-if="form.todownloader && selectedToDownloaderType === 'transmission'"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-2"
              >
                Transmission 当前不支持种子重命名，命名补刀与恢复原名不会生效；转移做种、IYUU 辅种和做种校验不受影响。
              </VAlert>
              <VRow class="mt-2 dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.frompath" label="源数据文件根路径" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">源下载器中数据的根路径</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.topath" label="目的数据文件根路径" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">目标下载器中数据的根路径</div>
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--four">
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.transfer_enabled" color="success" inset hide-details label="启用转移做种" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.notify" color="info" inset hide-details label="发送通知" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VTextField v-model.number="form.delay_minutes" label="延迟时间（分钟）" type="number" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">下载完成后延迟 N 分钟再转移</div>
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 筛选条件 ═══ -->
            <div v-if="activeSub === 'filter'" class="dm-pane">
              <div class="dm-section-title">条件筛选</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.includelabels" label="转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">仅转移包含这些标签的种子</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.nolabels" label="不转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">跳过包含这些标签的种子</div>
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.includecategory" label="转移种子分类（逗号分隔）" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">仅转移这些分类的种子</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.transferemptylabel" color="info" inset hide-details label="转移无标签种子" />
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.nopaths" label="不转移数据文件目录（每行一个）" density="compact" variant="outlined" hide-details rows="3" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 高级选项 ═══ -->
            <div v-if="activeSub === 'advanced'" class="dm-pane">
              <div class="dm-section-title">高级选项</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field"><VSwitch v-model="form.transfer_fallback_enabled" color="success" inset hide-details label="转移做种兜底服务" /></VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model.number="form.transfer_fallback_interval_minutes" label="兜底间隔（分钟）" type="number" min="1" density="compact" variant="outlined" hide-details :disabled="!form.transfer_fallback_enabled" /></VCol>
              </VRow>
              <div class="dm-hint mb-3">事件漏触发时按此间隔扫描，默认 60 分钟。</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model="form.fromtorrentpath" label="源种子文件路径" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model="form.add_torrent_tags" label="添加种子标签" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
              <div class="dm-hint mb-3">源种子文件路径如 BT_backup，可留空自动获取；多个标签以逗号分隔。</div>
              <VRow class="dm-form-grid dm-form-grid--four">
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.deletesource" color="error" inset hide-details label="删除源种子" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.deleteduplicate" color="error" inset hide-details label="删除重复种子" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.remainoldcat" color="info" inset hide-details label="保留原分类" />
                </VCol>
                <VCol cols="12" md="3" class="dm-form-field">
                  <VSwitch v-model="form.remainoldtag" color="info" inset hide-details label="保留原标签" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ IYUU辅种 · 基础设置 ═══ -->
            <div v-if="activeSub === 'iyuu_basic'" class="dm-pane">
              <div class="dm-section-title">IYUU铺种设置</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.iyuu_enabled" color="success" inset hide-details label="启用 IYUU 铺种" />
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.iyuu_onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
              </VRow>
              <div class="dm-hint mt-2">按执行周期运行；勾选“立即运行一次”并保存可立即执行。</div>
              <VRow class="mt-2 dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.iyuu_token" label="IYUU Token" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">在 https://iyuu.cn 获取</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VCronField v-model="form.iyuu_cron" label="执行周期" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <div class="dm-section-title mt-4">辅助铺种</div>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VBtn size="small" variant="tonal" :disabled="!canManage" :aria-expanded="editingPiecesCredentials && canManage"
                    @click="editingPiecesCredentials = !editingPiecesCredentials">{{ editingPiecesCredentials && canManage ? '隐藏凭据' : '编辑接口与凭据' }}</VBtn>
                  <VTextarea v-if="editingPiecesCredentials && canManage" v-model="form.pieces_site_keys" label="辅助铺种配置" density="compact" variant="outlined"
                    class="mt-2" rows="4" auto-grow hide-details autocomplete="off" spellcheck="false"
                    placeholder="青蛙:/api/pieces-hash,你的Passkey&#10;憨憨:/nexusapi/pieces-hash,你的Passkey" />
                  <div v-else class="dm-hint">{{ form.pieces_site_keys ? '已填写，凭据已隐藏。' : '未填写，仅使用 IYUU。' }}</div>
                </VCol>
              </VRow>
              <VAlert type="info" variant="tonal" density="compact" class="mt-3">
                <div>1. 先启用 IYUU 铺种、填写 IYUU Token，并在「条件筛选」选择辅种下载器。</div>
                <div>2. 每行一站，格式：站名:/查询路径,Passkey。站点须在 MoviePilot「站点管理」中启用，名称一致且唯一。</div>
                <div>3. 域名取自站点管理，路径由你填写，不内置、不自动探测。只填本站路径，不填完整网址，不把 Passkey 放进路径。</div>
                <div>4. 请求间隔可省略，默认 1 秒；要间隔 3 秒，在凭据后加 ,3。使用 fxo_ 开放令牌时需有 crossseed 查询和下载权限。</div>
                <div>5. 保存后随 IYUU 任务补查未命中的已配置站点；需要立即执行时，勾选「立即运行一次」并保存。此项留空则仅使用 IYUU。</div>
              </VAlert>
            </div>

            <!-- ═══ IYUU辅种 · 筛选条件 ═══ -->
            <div v-if="activeSub === 'iyuu_filter'" class="dm-pane">
              <div class="dm-section-title">条件筛选</div>
              <VRow class="mb-2 dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field"><VSelect v-model="form.iyuu_downloaders" label="辅种下载器" density="compact" variant="outlined" hide-details
                  :items="downloaderItems" multiple chips closable-chips clearable /></VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VSelect v-model="form.iyuu_auto_downloader" label="主辅分离下载器（可选）" density="compact" variant="outlined" hide-details
                  :items="downloaderItems" clearable /></VCol>
              </VRow>
              <VRow class="mb-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field"><VSelect v-model="form.iyuu_sites" label="IYUU 匹配站点" density="compact" variant="outlined" hide-details
                  :items="siteItems" multiple chips closable-chips clearable />
                <div class="dm-hint">留空表示全部站点</div></VCol>
              </VRow>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.iyuu_nolabels" label="不辅种标签（逗号分隔）" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">跳过包含这些标签的种子</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model.number="form.iyuu_size" label="最小辅种体积（GB）" type="number" min="0" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">仅处理体积大于此值的种子</div>
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.iyuu_nopaths" label="不辅种数据文件目录（每行一个）" density="compact" variant="outlined" hide-details rows="3" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ IYUU辅种 · 高级选项 ═══ -->
            <div v-if="activeSub === 'iyuu_advanced'" class="dm-pane">
              <div class="dm-section-title">辅种后处理</div>
              <VTextField v-model.number="form.reseed_max_additions" label="每轮最多新增任务" type="number" min="1" max="1000" density="compact" variant="outlined" hide-details class="mb-3" />
              <VTextarea v-model="form.pieces_torrent_paths" label="Transmission 种子目录（可选）" rows="2" density="compact" variant="outlined" hide-details
                placeholder="下载器名称=/MoviePilot内可读的种子目录" />
              <div class="dm-hint mb-3">Pieces 补查时使用，每行一个下载器的已挂载目录；qBittorrent 无需填写。</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model="form.iyuu_labelsafterseed" label="辅种后增加标签" density="compact" variant="outlined" hide-details />
                <div class="dm-hint">逗号分隔，默认：已整理,辅种</div></VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VTextField v-model="form.iyuu_categoryafterseed" label="辅种后增加分类" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.iyuu_auto_category" color="info" inset hide-details label="分类复用(QB有效)" />
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field"><VSwitch v-model="form.iyuu_clearcache" color="warning" inset hide-details label="清除缓存后运行" /></VCol>
              </VRow>
            </div>

            <!-- ═══ 种子重命名 · 命名格式 ═══ -->
            <div v-if="activeSub === 'rename_basic'" class="dm-pane">
              <div class="dm-section-title">重命名设置</div>
              <VRow class="dm-form-grid dm-form-grid--one">
                <VCol cols="12" md="4" class="dm-form-field">
                  <VSwitch v-model="form.rename_enabled" color="success" inset hide-details label="启用重命名" />
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.rename_movie_format" label="电影命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint" v-pre>可用变量：{{ title }}、{{ year }}、{{ original_name }}</div>
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.rename_tv_format" label="电视剧命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint" v-pre>可用变量：{{ title }}、{{ year }}、{{ season_episode }}、{{ original_name }}</div>
                </VCol>
              </VRow>
            </div>

            <div v-if="activeSub === 'rename_filter'" class="dm-pane">
              <div class="dm-section-title">条件筛选</div>
              <VTextarea v-model="form.rename_exclude_dirs" label="排除目录（每行一个）" density="compact" variant="outlined" hide-details rows="2" />
            </div>

            <!-- ═══ 站点标签 · Tracker 映射 ═══ -->
            <div v-if="activeSub === 'tag_basic'" class="dm-pane">
              <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
                <div class="dm-section-title">站点标签设置</div>
                <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-tag-plus-outline"
                  @click="activeSub = 'tag_repair'">补全标签</VBtn>
              </div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.tag_enabled" color="success" inset hide-details label="启用站点标签" />
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.tag_siteprefix" label="站点标签前缀" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.tag_tracker_mappings_str" label="Tracker 映射（域名 -> 映射域名）" density="compact" variant="outlined" hide-details rows="4" />
                  <div class="dm-hint">可留空。先按 MP 站点目录识别；未知域名才查自定义映射，再查内置映射。每行一条：tracker 域名 -> 站点域名。</div>
                </VCol>
              </VRow>
              <div class="dm-section-title mt-4">官种标签设置</div>
              <VRow class="dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VSwitch v-model="form.tag_official_enabled" color="success" inset hide-details label="启用官种标签" />
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model="form.tag_official_prefix" label="官种标签前缀" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid dm-form-grid--one">
                <VCol cols="12" class="dm-form-field">
                  <VTextarea v-model="form.tag_official_mappings" label="官种映射（站点:制作组|制作组）" density="compact" variant="outlined" hide-details rows="4" />
                  <div class="dm-hint">每站一行，站名与 MoviePilot 一致。转种、铺种及老种补全只认本站的完整制作组后缀；前缀留空时打「官种」。</div>
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 站点标签 · 补全标签 ═══ -->
            <div v-if="activeSub === 'tag_repair'" class="dm-pane">
              <div class="dm-section-title">补全标签</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-3">
                站点标签按 tracker 恢复；普通转种、铺种标签需要对应历史。启用官种后，本站与制作组匹配的老种无需历史，确认补全即可替换转种、铺种或辅种角色标签；其他标签保留。
              </VAlert>
              <div class="dm-cleanup-toolbar">
                <VSelect v-model="completionDownloaders" label="下载器" density="compact" variant="outlined" hide-details
                  :items="tagCompletionDownloaderItems" multiple chips closable-chips class="dm-cleanup-select" />
                <VBtn color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="completionScanning"
                  :disabled="!canManage || !completionDownloaders.length || completionScanning || completionExecuting || completionTask?.status === 'unknown'"
                  @click="scanTagCompletion">扫描待补标签</VBtn>
                <VBtn v-if="completionTask?.can_cancel" color="warning" variant="text" prepend-icon="mdi-stop-circle-outline"
                  :disabled="!canManage" @click="cancelTagCompletionTask">停止任务</VBtn>
              </div>

              <VProgressLinear v-if="completionScanning || completionExecuting" :model-value="completionTask?.progress || 0"
                color="primary" height="4" rounded class="mt-3" />

              <VAlert v-if="completionMessage" :type="completionStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="completionMessage = ''">{{ completionMessage }}</VAlert>

              <div v-if="completionScan" class="dm-cleanup-results mt-4">
                <div class="dm-cleanup-summary">
                  <div>
                    <div class="text-subtitle-2">扫描结果</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ completionGroups.length }} 个下载器 · 待补 {{ completionRepairAssociations }} 条标签关联
                    </div>
                  </div>
                  <div class="d-flex ga-1 flex-wrap justify-end">
                    <VBtn size="small" variant="text" prepend-icon="mdi-check-all" @click="setAllCompletionTags(true)">全选</VBtn>
                    <VBtn size="small" variant="text" color="warning" prepend-icon="mdi-checkbox-blank-outline"
                      @click="setAllCompletionTags(false)">取消全选</VBtn>
                  </div>
                </div>

                <VAlert v-for="item in completionScan.errors || []" :key="`${item.downloader}-${item.message}`"
                  type="warning" variant="tonal" density="compact" class="mb-2">
                  {{ item.downloader }} · {{ item.message }}
                </VAlert>

                <div v-for="group in completionGroups" :key="group.name" class="dm-tag-group">
                  <div class="dm-tag-group-head">
                    <div class="d-flex align-center ga-2 min-w-0">
                      <VIcon icon="mdi-download-network-outline" size="19" color="primary" />
                      <strong class="text-body-2">{{ group.name }}</strong>
                    </div>
                    <span class="text-caption text-medium-emphasis">
                      {{ group.task_count }} 个任务 · {{ group.missing_count }} 条待补
                      <template v-if="group.unmatched_tracker_count"> · {{ group.unmatched_tracker_count }} 个 tracker 未识别</template>
                    </span>
                  </div>

                  <div v-if="!group.tags.length" class="dm-cleanup-empty">
                    <VIcon icon="mdi-tag-check-outline" size="28" color="success" />
                    <span>没有可恢复的缺失标签</span>
                  </div>
                  <div v-else class="dm-tag-list">
                    <label v-for="item in group.tags" :key="`${group.name}-${item.kind}-${item.tag}`" class="dm-tag-row">
                      <VCheckboxBtn v-model="completionKeep[tagCompletionSelectionKey(group.name, item.kind, item.tag)]" color="success" />
                      <div class="dm-tag-content">
                        <div class="dm-tag-line">
                          <span class="dm-tag-name" :title="item.tag">{{ item.tag }}</span>
                          <VChip size="x-small" variant="tonal" :color="completionKindMeta(item.kind).color">
                            {{ completionKindMeta(item.kind).label }}
                          </VChip>
                          <span class="text-caption text-medium-emphasis">{{ item.count }} 个任务</span>
                        </div>
                        <div class="dm-tag-samples" :title="(item.samples || []).join(' · ')">{{ (item.samples || []).join(' · ') }}</div>
                      </div>
                    </label>
                  </div>
                </div>

                <div class="dm-cleanup-actions">
                  <div class="text-caption text-medium-emphasis">
                    已选 {{ completionRepairs.length }} 个标签组 · {{ completionRepairAssociations }} 条任务关联
                  </div>
                  <VBtn color="primary" variant="tonal" prepend-icon="mdi-eye-outline"
                    :disabled="!canManage || !completionRepairs.length" @click="previewTagCompletion">预览补全</VBtn>
                </div>
              </div>
            </div>

            <!-- ═══ 站点标签 · 标签清理 ═══ -->
            <div v-if="activeSub === 'tag_advanced'" class="dm-pane">
              <div class="dm-section-title">高级选项 · 手动清理标签</div>
              <div class="dm-hint mb-3">扫描后核对标签与任务，预览清单确认无误后再清理。</div>
              <div class="dm-cleanup-toolbar">
                <VSelect v-model="cleanupDownloaders" label="下载器" density="compact" variant="outlined" hide-details
                  :items="tagCleanupDownloaderItems" multiple chips closable-chips class="dm-cleanup-select" />
                <VBtn color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="cleanupScanning"
                  :disabled="!canManage || !cleanupDownloaders.length" @click="scanCleanupTags">扫描标签</VBtn>
              </div>

              <VAlert v-if="cleanupMessage" :type="cleanupStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="cleanupMessage = ''">{{ cleanupMessage }}</VAlert>

              <div v-if="cleanupScan" class="dm-cleanup-results mt-4">
                <div class="dm-cleanup-summary">
                  <div>
                    <div class="text-subtitle-2">扫描结果</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ cleanupGroups.length }} 个下载器 · 自动清理 {{ cleanupAutoRemovedCount }} 个临时标签
                    </div>
                  </div>
                  <div class="d-flex ga-1 flex-wrap justify-end">
                    <VBtn size="small" variant="text" prepend-icon="mdi-check-all" @click="setAllCleanupTags(true)">全部保留</VBtn>
                    <VBtn size="small" variant="text" color="warning" prepend-icon="mdi-checkbox-blank-outline"
                      @click="setAllCleanupTags(false)">取消全选</VBtn>
                  </div>
                </div>

                <VAlert v-for="item in cleanupScan.errors || []" :key="`${item.downloader}-${item.message}`"
                  type="warning" variant="tonal" density="compact" class="mb-2">
                  {{ item.downloader }} · {{ item.message }}
                </VAlert>

                <div v-for="group in cleanupGroups" :key="group.name" class="dm-tag-group">
                  <div class="dm-tag-group-head">
                    <div class="d-flex align-center ga-2 min-w-0">
                      <VIcon icon="mdi-download-network-outline" size="19" color="primary" />
                      <strong class="text-body-2">{{ group.name }}</strong>
                    </div>
                    <span class="text-caption text-medium-emphasis">{{ group.task_count }} 个任务 · {{ group.tags.length }} 个标签</span>
                  </div>

                  <div v-if="!group.tags.length" class="dm-cleanup-empty">
                    <VIcon icon="mdi-tag-check-outline" size="28" color="success" />
                    <span>没有待选择标签</span>
                  </div>
                  <div v-else class="dm-tag-list">
                    <label v-for="item in group.tags" :key="`${group.name}-${item.tag}`" class="dm-tag-row">
                      <VCheckboxBtn v-model="cleanupKeep[tagSelectionKey(group.name, item.tag)]" color="success" />
                      <div class="dm-tag-content">
                        <div class="dm-tag-line">
                          <span class="dm-tag-name" :title="item.tag">{{ item.tag }}</span>
                          <VChip size="x-small" variant="tonal" :color="cleanupKindMeta(item.kind).color">
                            {{ cleanupKindMeta(item.kind).label }}
                          </VChip>
                          <span class="text-caption text-medium-emphasis">{{ item.count }} 个任务</span>
                        </div>
                        <div class="dm-tag-samples" :title="(item.samples || []).join(' · ')">{{ (item.samples || []).join(' · ') }}</div>
                      </div>
                    </label>
                  </div>
                </div>

                <div class="dm-cleanup-actions">
                  <div class="text-caption text-medium-emphasis">
                    待清理 {{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联
                  </div>
                  <VBtn color="warning" variant="tonal" prepend-icon="mdi-eye-outline"
                    :disabled="!canManage || !cleanupRemovals.length" @click="previewCleanupTags">预览清理</VBtn>
                </div>
              </div>
            </div>

            <div v-if="syncDeleteVisited" v-show="activeMain === 'sync_delete' && activeSub.startsWith('sync_delete_')" class="dm-pane">
              <SyncDeletePane :can-manage="canManage" :api="props.api" :plugin-id="props.pluginId" :form="form" mode="config"
                :section="activeMain === 'sync_delete' ? activeSub.slice('sync_delete_'.length) : ''" />
            </div>
            <div v-if="autoDeleteVisited" v-show="activeMain === 'auto_delete' && activeSub.startsWith('auto_delete_')" class="dm-pane">
              <AutoDeletePane :downloader-request="downloaderRequest" ref="autoDeletePane" :can-manage="canManage" :api="props.api" :plugin-id="props.pluginId" mode="config"
                :section="activeMain === 'auto_delete' ? activeSub.slice('auto_delete_'.length) : ''" :active="activeMain === 'auto_delete' && activeSub.startsWith('auto_delete_')"
                @show-advanced="activeSub = 'auto_delete_advanced'"
                @saved="values => { Object.assign(form, values); refreshOverview() }" />
            </div>

            <!-- ═══ 做种校验 v3.0.15 · 基础设置 ═══ -->
            <div v-if="activeSub === 'seed_basic'" class="dm-pane">
              <div class="dm-section-title">做种校验设置</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-4">做种校验采用按需触发：仅在转移做种、IYUU铺种或手动补刀添加种子后启动。队列为空后自动停止。</VAlert>
              <VRow class="dm-form-grid dm-form-grid--one">
                <VCol cols="12" md="4" class="dm-form-field">
                  <VSwitch v-model="form.seed_autostart" color="success" inset hide-details label="启用自动开始做种" />
                </VCol>
              </VRow>
            </div>

            <div v-if="activeSub === 'seed_advanced'" class="dm-pane">
              <div class="dm-section-title">高级选项</div>
              <VRow class="dm-form-grid dm-form-grid--one">
                <VCol cols="12" md="4" class="dm-form-field"><VSwitch v-model="form.seed_skipverify" color="warning" inset hide-details label="跳过校验（qBittorrent 有效）" /></VCol>
              </VRow>
              <VRow class="mt-2 dm-form-grid">
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model.number="form.seed_check_interval" label="校验检查间隔（秒）" type="number" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">建议 60 秒</div>
                </VCol>
                <VCol cols="12" md="6" class="dm-form-field">
                  <VTextField v-model.number="form.seed_max_wait_minutes" label="最大等待时间（分钟）" type="number" density="compact" variant="outlined" hide-details />
                  <div class="dm-hint">超时后移出队列</div>
                </VCol>
              </VRow>
              <div class="dm-hint">本模块按需启动，不使用定时扫描周期。执行情况在详情页查看。</div>
            </div>

          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dm-actions">
        <span v-if="saveNotice" role="status" class="text-caption" :class="saveProblem ? 'text-warning' : 'text-success'">{{ saveNotice }}</span>
        <VSpacer />
        <VBtn variant="text" :disabled="saving" @click="emit('close')">关闭</VBtn>
        <VBtn :loading="saving" :disabled="saving || !canManage || Boolean(autoDeletePane?.busy)" color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>

    <VDialog v-model="reviewDialog" max-width="960" :persistent="Boolean(reviewPane?.busy)" @update:model-value="!$event && closeReview()">
      <VCard v-if="reviewDialog" class="dm-review-dialog">
        <VCardTitle class="dm-review-title">同步删除 · 待处理详情<VBtn icon="mdi-close" variant="text" :disabled="Boolean(reviewPane?.busy)" aria-label="关闭待处理详情" @click="closeReview" /></VCardTitle>
        <VDivider />
        <VCardText class="dm-review-content"><SyncDeletePane ref="reviewPane" :api="props.api" :plugin-id="props.pluginId" :can-manage="canManage" :initial-pending-only="true" /></VCardText>
      </VCard>
    </VDialog>
    <VDialog v-model="cleanupDialog" max-width="620">
      <VCard>
        <VCardItem>
          <template #prepend>
            <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-tag-remove-outline" /></VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">确认标签清理</VCardTitle>
          <VCardSubtitle>{{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VList density="compact" class="dm-cleanup-preview-list">
          <VListItem v-for="item in cleanupRemovals" :key="`${item.downloader}-${item.tag}`">
            <template #prepend><VIcon icon="mdi-tag-outline" size="18" /></template>
            <VListItemTitle>{{ item.tag }}</VListItemTitle>
            <VListItemSubtitle>{{ item.downloader }} · {{ item.hashes.length }} 个任务</VListItemSubtitle>
          </VListItem>
        </VList>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="cleanupExecuting" @click="cleanupDialog = false">取消</VBtn>
          <VBtn :disabled="!canManage" color="error" variant="flat" prepend-icon="mdi-tag-remove-outline" :loading="cleanupExecuting"
            @click="executeCleanupTags">确认清理</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="completionDialog" max-width="680">
      <VCard>
        <VCardItem>
          <template #prepend>
            <VAvatar color="primary" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-tag-plus-outline" /></VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">确认补全标签</VCardTitle>
          <VCardSubtitle>{{ completionRepairAssociations }} 条任务标签关联</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="text-body-2">
          执行时会重新核验。选中的官种标签将替换该种子的转种、铺种或辅种角色标签，其余标签保留；不改名、不转移、不删除种子。
        </VCardText>
        <VList density="compact" class="dm-cleanup-preview-list">
          <VListItem v-for="item in completionRepairs" :key="`${item.downloader}-${item.kind}-${item.tag}`">
            <template #prepend><VIcon icon="mdi-tag-outline" size="18" /></template>
            <VListItemTitle>
              {{ item.tag }} <VChip size="x-small" variant="tonal" :color="completionKindMeta(item.kind).color">{{ completionKindMeta(item.kind).label }}</VChip>
            </VListItemTitle>
            <VListItemSubtitle>{{ item.downloader }} · {{ item.hashes.length }} 个任务</VListItemSubtitle>
          </VListItem>
        </VList>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="completionExecuting" @click="completionDialog = false">取消</VBtn>
          <VBtn :disabled="!canManage || completionExecuting || completionTask?.status === 'unknown'" color="primary" variant="flat" prepend-icon="mdi-tag-plus-outline" :loading="completionExecuting"
            @click="executeTagCompletion">确认补全</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="uploadRestoreDialog" max-width="560">
      <VCard>
        <VCardItem>
          <template #prepend>
            <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-backup-restore" /></VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">停用并恢复上传限速</VCardTitle>
          <VCardSubtitle>恢复插件接管前的下载器与单种上传设置</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="text-body-2">
          当前值仍等于插件最后写入值时才会恢复；若你后来手工修改过，则保留手工值，不会覆盖。
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="uploadActionRunning === 'restore'" @click="uploadRestoreDialog = false">取消</VBtn>
          <VBtn :disabled="!canManage" color="warning" variant="flat" prepend-icon="mdi-backup-restore" :loading="uploadActionRunning === 'restore'"
            @click="disableAndRestoreUploadLimits">确认恢复</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>
<style scoped>
.dm-review-dialog { height: min(760px, calc(100dvh - 48px)); display: flex; flex-direction: column; overflow: hidden; }
.dm-review-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex: 0 0 auto; white-space: normal; }
.dm-review-content { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.dm-form-section-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 18px; }
.dm-form-section-heading .dm-section-title { margin: 0; }
.dm-form-section-heading :deep(.v-input) { flex: 0 0 auto; }
.dm-monitor-basic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px 24px; align-items: start; }
.dm-monitor-basic-grid > div { min-width: 0; }
@media (max-width: 760px) { .dm-monitor-basic-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; } }
.dm-config {
  width: min(1120px, calc(100vw - 48px));
  max-width: 100%;
  padding: 8px;
}
.dm-card {
  width: 100%;
  height: min(860px, calc(100dvh - 48px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.dm-header { padding: 14px 18px; }
.dm-header :deep(.v-card-subtitle) {
  max-width: min(560px, 52vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dm-body { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-nav-list { width: 100%; }
.dm-nav-item { margin: 2px 8px; }
.dm-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.dm-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.dm-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), 0.7); background: transparent; border: none; cursor: pointer; transition: background 0.15s, color 0.15s; white-space: nowrap; }
.dm-subtab:hover { background: rgba(var(--v-theme-primary), 0.08); color: rgb(var(--v-theme-primary)); }
.dm-subtab--active { background: rgba(var(--v-theme-primary), 0.14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.dm-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.dm-window--overview { overflow-y: hidden; }
.dm-pane { min-height: 100%; padding: 18px 20px; }
.dm-pane--overview { min-height: auto; padding: 12px 16px; }
.dm-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dm-hint { font-size: 12px; line-height: 1.5; color: rgba(var(--v-theme-on-surface), 0.6); margin-top: 2px; }
.dm-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px 12px; min-width: 0; }
.dm-flow { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; }
.dm-flow-block { min-width: 0; }
.dm-flow-block:first-child { grid-column: 1 / -1; }
.dm-flow-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-primary)); margin-bottom: 5px; }
.dm-flow-row { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.78); }
.dm-flow-step { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), 0.02); white-space: nowrap; }
.dm-flow-arrow { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), 0.44); }
.dm-flow-review { margin-left: 12px; color: rgb(var(--v-theme-warning)); font-size: 11px; font-weight: 400; text-decoration: underline; text-underline-offset: 3px; }
.dm-flow-review:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 3px; }
.dm-config :deep(.v-row) { align-items: start; }
.dm-config :deep(.v-input) { min-width: 0; }
.dm-break-text { overflow-wrap: anywhere; }
.dm-monitor-speed-list, .dm-monitor-baselines { display: grid; gap: 10px; }
.dm-threshold-suggestion { border-radius: 8px; }
.dm-threshold-suggestion-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
.dm-threshold-suggestion-title { font-size: 13px; font-weight: 600; }
.dm-threshold-suggestion-list { display: grid; gap: 4px; }
.dm-threshold-suggestion-row { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(112px, auto) minmax(112px, auto) auto; grid-template-areas: 'label current suggested action'; gap: 10px; align-items: center; min-width: 0; padding: 5px 0; border-top: 1px solid rgba(var(--v-border-color), .35); font-size: 12px; }
.dm-threshold-suggestion-row > span, .dm-threshold-suggestion-row > strong { min-width: 0; overflow-wrap: anywhere; }
.dm-threshold-suggestion-label { font-weight: 600; }
.dm-threshold-suggestion-label { grid-area: label; }
.dm-threshold-suggestion-current { grid-area: current; }
.dm-threshold-suggestion-suggested { grid-area: suggested; }
.dm-threshold-suggestion-action { grid-area: action; justify-self: end; }
.dm-monitor-speed-row { display: grid; grid-template-columns: minmax(150px, 0.45fr) minmax(240px, 1fr); gap: 14px; align-items: start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-speed-name { display: flex; align-items: center; gap: 8px; min-width: 0; padding-top: 8px; font-size: 13px; font-weight: 600; overflow-wrap: anywhere; }
.dm-monitor-summary, .dm-upload-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-monitor-metric { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-metric span { display: block; color: rgba(var(--v-theme-on-surface), 0.62); font-size: 12px; }
.dm-monitor-metric strong { display: block; margin-top: 3px; overflow-wrap: anywhere; font-size: 15px; }
.dm-monitor-baselines { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.dm-monitor-baseline { min-width: 0; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-baseline-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }
.dm-baseline-values { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 9px; font-size: 12px; }
.dm-relative-note { margin-top: 7px; color: rgb(var(--v-theme-warning)); font-size: 12px; }
.dm-disposition { display: grid; gap: 3px; min-width: 0; padding: 10px 12px; border-left: 3px solid rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.06); font-size: 12px; }
.dm-disposition span { min-width: 0; overflow-wrap: anywhere; }
.dm-monitor-empty { display: flex; min-height: 64px; align-items: center; justify-content: center; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 13px; }
.dm-upload-downloader-list, .dm-upload-site-list, .dm-upload-site-status { display: grid; gap: 10px; }
.dm-upload-config-row { display: grid; grid-template-columns: minmax(220px, .72fr) minmax(260px, 1fr); gap: 16px; align-items: start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-config-name, .dm-upload-site-name { display: flex; align-items: flex-start; gap: 9px; min-width: 0; padding-top: 8px; overflow-wrap: anywhere; }
.dm-upload-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.dm-upload-site-row { display: grid; grid-template-columns: minmax(180px, .72fr) minmax(250px, 1fr) auto; gap: 12px; align-items: start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-row :deep(.v-btn) { margin-top: 4px; }
.dm-upload-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.dm-upload-status-card { min-width: 0; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-status-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; min-width: 0; }
.dm-upload-values { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 12px; margin-top: 10px; font-size: 12px; }
.dm-upload-values span { min-width: 0; overflow-wrap: anywhere; }
.dm-upload-site-status-row { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(102px, auto) minmax(112px, auto) minmax(124px, auto); gap: 10px; align-items: center; min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-status-row > span { min-width: 0; overflow-wrap: anywhere; }
.dm-cleanup-toolbar { display: flex; align-items: center; gap: 10px; }
.dm-cleanup-select { flex: 1 1 auto; min-width: 0; }
.dm-cleanup-results { display: grid; gap: 10px; }
.dm-cleanup-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dm-tag-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.dm-tag-group-head { min-height: 42px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-tag-list { max-height: 280px; overflow-y: auto; }
.dm-tag-row { min-height: 54px; display: flex; align-items: center; gap: 4px; padding: 6px 10px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); cursor: pointer; }
.dm-tag-row:last-child { border-bottom: none; }
.dm-tag-row:hover { background: rgba(var(--v-theme-primary), 0.05); }
.dm-tag-content { flex: 1 1 auto; min-width: 0; }
.dm-tag-line { display: flex; align-items: center; gap: 7px; min-width: 0; }
.dm-tag-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.dm-tag-samples { margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(var(--v-theme-on-surface), 0.55); font-size: 11px; }
.dm-cleanup-empty { min-height: 82px; display: flex; align-items: center; justify-content: center; gap: 8px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 13px; }
.dm-cleanup-actions { position: sticky; bottom: -18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0 0; background: rgb(var(--v-theme-surface)); }
.dm-cleanup-preview-list { max-height: 360px; overflow-y: auto; }
.dm-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .dm-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .dm-card { height: min(860px, calc(100dvh - 16px)); }
  .dm-header :deep(.v-card-subtitle) { max-width: 100%; }
  .dm-body { flex-direction: column; }
  .dm-nav { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .dm-nav::-webkit-scrollbar { display: none; }
  .dm-nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .dm-nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }
  .dm-nav-item :deep(.v-list-item-title) { white-space: nowrap; }
  .dm-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; scrollbar-width: none; padding: 6px 12px; }
  .dm-subtabs::-webkit-scrollbar { display: none; }
  .dm-subtab { flex: 0 0 auto; padding: 6px 12px; }
  .dm-monitor-summary, .dm-upload-summary, .dm-monitor-baselines, .dm-monitor-speed-row { grid-template-columns: 1fr; }
  .dm-upload-config-row, .dm-upload-site-row, .dm-upload-status-grid, .dm-upload-site-status-row { grid-template-columns: 1fr; }
  .dm-upload-config-name, .dm-upload-site-name { padding-top: 0; }
  .dm-upload-toolbar { align-items: stretch; flex-direction: column; }
  .dm-upload-toolbar :deep(.v-btn) { width: 100%; }
  .dm-upload-site-row :deep(.v-btn) { justify-self: end; margin-top: 0; }
  .dm-threshold-suggestion-head { align-items: stretch; flex-direction: column; }
  .dm-threshold-suggestion-head :deep(.v-btn) { align-self: flex-start; }
  .dm-threshold-suggestion-row { grid-template-columns: minmax(112px, 1fr) minmax(84px, auto); grid-template-areas: 'label current' 'suggested action'; gap: 6px; }
  .dm-threshold-suggestion-action { justify-self: end; }
  .dm-monitor-speed-name { padding-top: 0; }
  .dm-cleanup-toolbar, .dm-cleanup-summary, .dm-cleanup-actions, .dm-tag-group-head { align-items: stretch; flex-direction: column; }
  .dm-cleanup-toolbar :deep(.v-btn), .dm-cleanup-actions :deep(.v-btn) { width: 100%; }
  .dm-tag-line { flex-wrap: wrap; }
  .dm-tag-name { width: 100%; }
  .dm-window--overview { overflow-y: auto; }
}
@media (min-width: 761px) and (max-width: 960px) {
  .dm-monitor-summary, .dm-upload-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-upload-site-row { grid-template-columns: minmax(180px, .7fr) minmax(220px, 1fr) auto; }
  .dm-upload-status-grid { grid-template-columns: 1fr; }
  .dm-upload-site-status-row { grid-template-columns: minmax(170px, 1fr) repeat(3, minmax(96px, auto)); }
  .dm-window--overview { overflow-y: auto; }
}
@media (max-height: 808px) {
  .dm-window--overview { overflow-y: auto; }
}
</style>
