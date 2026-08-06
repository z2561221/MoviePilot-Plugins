<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useAgentRankState } from './useAgentRankState'
import AgentAnalysisDialog from './AgentAnalysisDialog.vue'
import CriticChatDialog from './CriticChatDialog.vue'
import FeedbackCommentDialog from './FeedbackCommentDialog.vue'
import PendingConfirmations from './PendingConfirmations.vue'
import RecommendationActions from './RecommendationActions.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  showClose: { type: Boolean, default: true },
})
const emit = defineEmits(['action', 'switch', 'close'])
const state = useAgentRankState(props.api)

const activeTab = ref('board')
const snackbar = ref({ show: false, message: '', color: 'success' })
const historyPage = ref(1)
const boardHistoryPage = ref(1)
const initialized = ref(false)
const expandedHistoryKeys = ref(new Set())
const expandedBoardHistoryKeys = ref(new Set())
const tagDrafts = reactive({ positive: '', negative: '' })
const analysisDialog = ref(false)
const commentDialog = ref(false)
const criticDialog = ref(false)
const pendingDialog = ref(false)
const selectedAnalysisItem = ref(null)
const selectedJudgment = ref(null)
const historyPageSize = 10
const boardHistoryPageSize = 10
const recommendationCards = ref([])
let conversationStatusTimer = null
let runProgressTimer = null
let exposureObserver = null
let pageUnmounted = false

const recommendations = computed(() => state.board.value?.recommendations?.slice(0, 5) || [])
const agentName = computed(() => state.agentDisplayName.value || 'CinePilot Agent')
const criticUnreadCount = computed(() => Number(state.conversationStatus.value?.unread_count || 0))
const archiveEntries = computed(() => state.overview.value?.archive?.entries || [])
const historyPages = computed(() => Math.max(1, Math.ceil((state.historyMeta.value.total || 0) / historyPageSize)))
const boardHistoryPages = computed(() => Math.max(1, Math.ceil((state.boardHistoryMeta.value.total || 0) / boardHistoryPageSize)))
const positiveTags = computed(() => state.profile.value?.tags || [])
const negativeTags = computed(() => state.profile.value?.negative_tags || [])
const archivedProfileTags = computed(() => state.profile.value?.archived_profile_tags || [])
const questioningStateMeta = computed(() => ({
  exploring: { text: '探索中', color: 'info', icon: 'mdi-compass-outline' },
  stabilizing: { text: '趋于稳定', color: 'primary', icon: 'mdi-chart-timeline-variant-shimmer' },
  low_interruption: { text: '低打扰', color: 'success', icon: 'mdi-bell-sleep-outline' },
}[state.profile.value?.questioning_state] || { text: '探索中', color: 'info', icon: 'mdi-compass-outline' }))
const profileStats = computed(() => [
  { label: '播放样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-database-check-outline' },
  { label: '偏好标签', value: positiveTags.value.length, suffix: '个', icon: 'mdi-heart-outline' },
  { label: '避雷标签', value: negativeTags.value.length, suffix: '个', icon: 'mdi-shield-alert-outline' },
])
const boardMatchTags = computed(() => {
  const counts = new Map()
  recommendations.value.forEach(item => {
    const tags = item.match_tags || []
    tags.forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1))
  })
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
    .slice(0, 10)
    .map(([tag, count]) => ({ tag, count }))
})
const profileRunId = computed(() => String(state.profile.value?.run_id || '').slice(0, 8) || '—')
const detailStats = computed(() => [
  { label: '榜单条目', value: recommendations.value.length, suffix: '部', icon: 'mdi-format-list-numbered' },
  { label: '画像样本', value: state.profile.value?.playback_count || 0, suffix: '条', icon: 'mdi-account-heart-outline' },
  { label: '忽略归档', value: archiveEntries.value.length, suffix: '部', icon: 'mdi-archive-outline' },
])
function healthCoverageText(health) {
  return ({ none: '尚无归因样本', partial: '部分阶段已覆盖', complete: '链路已覆盖' }[health?.attribution_coverage] || '归因状态未评估')
}

const statusMetaFor = status => ({
  idle: { text: '待生成', color: 'default' },
  running: { text: '运行中', color: 'primary' },
  success: { text: '已完成', color: 'success' },
  sample_insufficient: { text: '样本不足', color: 'warning' },
  candidate_insufficient: { text: '候选不足', color: 'warning' },
  recommendation_incomplete: { text: '榜单不足', color: 'warning' },
  recommendation_degraded: { text: '降级榜单', color: 'warning' },
  agent_failed: { text: 'Agent失败', color: 'error' },
  validation_failed: { text: '校验失败', color: 'error' },
  subscription_partial_failed: { text: '部分订阅失败', color: 'warning' },
  profile_agent_failed: { text: '画像生成失败', color: 'error' },
  profile_validation_failed: { text: '画像校验失败', color: 'error' },
  policy_failed: { text: '策略生成失败', color: 'error' },
  policy_superseded: { text: '策略已过期', color: 'warning' },
  candidate_failed: { text: '候选采集失败', color: 'error' },
  candidate_filter_failed: { text: '候选过滤失败', color: 'error' },
  candidate_snapshot_failed: { text: '候选快照失败', color: 'error' },
  ranking_agent_failed: { text: '排序生成失败', color: 'error' },
  ranking_validation_failed: { text: '排序校验失败', color: 'error' },
  ranking_save_failed: { text: '榜单保存失败', color: 'error' },
  runtime_exception: { text: '运行异常', color: 'error' },
  }[status] || { text: '运行异常', color: 'error' })

const historyStageLabels = {
  probe: '依赖探测',
  playback_snapshot: '冻结播放',
  policy: '确定策略',
  profile: '生成画像',
  candidate: '冻结候选',
  ranking: 'Agent排序',
  save: '保存榜单',
}
const historyStageStatusLabels = {
  ready: '完成', generated: '已生成', reused: '复用', cached: '使用缓存', saved: '已保存',
  success: '成功', pending: '等待', running: '进行中', stopped: '停止', failed: '失败',
  sample_insufficient: '样本不足', candidate_insufficient: '候选不足',
  recommendation_incomplete: '榜单不足', agent_failed: 'Agent失败',
  recommendation_degraded: '降级榜单',
  validation_failed: '校验失败', subscription_partial_failed: '部分订阅失败',
  profile_agent_failed: '画像生成失败', profile_validation_failed: '画像校验失败',
  policy_failed: '策略生成失败',
  policy_superseded: '偏好已更新，请重新生成',
  candidate_failed: '候选采集失败', candidate_filter_failed: '候选过滤失败',
  candidate_snapshot_failed: '候选快照失败', ranking_agent_failed: '排序生成失败',
  ranking_validation_failed: '排序校验失败', ranking_save_failed: '榜单保存失败', runtime_exception: '运行异常',
}
const historySourceLabels = {
  douban: '豆瓣', tmdb: 'TMDB', tmdb_movies: 'TMDB电影', tmdb_tv: 'TMDB剧集',
  tmdb_recommend: 'TMDB相关', bangumi: 'Bangumi', anilist: 'AniList',
}
const historyExclusionLabels = {
  invalid_or_unrecognized: '未识别', watched: '已观看', watched_completed: '已看完', library: '已入库',
  subscribed: '已订阅', disliked: '已点踩', archived: '已忽略', negative_keyword: '排除词',
  ambiguous_playback_count: '播放次数误写为看完次数',
  unsupported_playback_claim: '观看经历无法回溯',
}
const profileCacheReasonLabels = {
  disabled: '缓存已关闭',
  forced_rebuild: '本轮强制重建',
  missing: '没有可复用画像',
  profile_schema_changed: '画像结构已升级',
  retrieval_resolution_changed: '检索规则已升级',
  playback_changed: '播放记录已变化',
}
const rankingFallbackReasonLabels = {
  ranking_agent_failed: '排序调用失败',
  ranking_validation_failed: '排序格式失败',
  refill_agent_failed: '补选调用失败',
  refill_validation_failed: '补选格式失败',
  refill_insufficient: '补选数量不足',
  ranking_insufficient: '排序数量不足',
}
const historyValidationDropLabels = {
  unknown_candidate: '候选不在冻结池',
  duplicate_candidate: '候选重复',
  disliked_candidate: '已点踩',
  archived_candidate: '已忽略',
  subscribed_candidate: '已订阅',
  legacy_evidence_schema: '仍使用旧支持度字段',
  invalid_confidence: '支持度无效',
  summary_too_long: '简介超过30字',
  reason_too_long: '推荐理由超过30字',
  invalid_summary: '简介语义不完整',
  invalid_reason: '推荐理由不可信',
  ambiguous_playback_count: '播放次数误写为看完次数',
  unsupported_playback_claim: '观看经历无法回溯',
  unsupported_candidate_claim: '作品信息无法回溯',
  insufficient_match_evidence: '具体匹配证据不足',
  insufficient_verified_evidence: '可验证正向证据不足',
  missing_counter_evidence: '遗漏已存在的主要反证',
  process_or_generic_reason: '理由仍是过程描述或宽泛分类',
}
const historyAgentStageLabels = {
  profile: '画像',
  ranking: '排序',
  refill: '补选',
}
const historyAgentStatusLabels = {
  completed: '完成',
  validation_failed: '校验失败',
  failed: '调用失败',
  pending: '未完成',
}
const historyAgentSourceLabels = {
  agent_tokens: 'Agent Tokens',
  moviepilot_system: 'MoviePilot 系统',
  mixed: '混合来源',
  unknown: '来源未返回',
}
const historyTriggerLabels = {
  manual: '手动刷新',
  schedule: '周期运行',
  startup: '启动补偿',
  feedback: '反馈变化',
  exposure: '曝光后轮换',
  unknown: '未记录',
  legacy_snapshot: '历史兼容快照',
}

const tabs = [
  { key: 'board', title: '推荐榜单', icon: 'mdi-format-list-numbered' },
  { key: 'profile', title: '用户画像', icon: 'mdi-account-heart-outline' },
  { key: 'archive', title: '忽略归档', icon: 'mdi-archive-outline' },
  { key: 'history', title: '运行历史', icon: 'mdi-history' },
  { key: 'board-history', title: '历史榜单', icon: 'mdi-view-list-outline' },
]

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString()
}

function mediaTypeLabel(value) {
  return ({ movie: '电影', tv: '剧集', anime: '动漫' })[value] || '其他类型'
}

function fitScoreValue(item) {
  const rawScore = item?.fit_score
  if (rawScore === null || rawScore === undefined || rawScore === '') return null
  const score = Number(rawScore)
  return Number.isFinite(score) && score >= 0 && score <= 100 ? Math.round(score) : null
}

function fitScoreText(item) {
  const score = fitScoreValue(item)
  return score === null ? '—' : `${score}分`
}

function fitScoreColor(item) {
  const score = fitScoreValue(item)
  if (score === null) return 'default'
  if (score >= 85) return 'success'
  if (score >= 70) return 'primary'
  return 'warning'
}

function historyKey(run) { return `${run?.run_id || ''}:${run?.finished_at || run?.started_at || ''}` }
function isHistoryExpanded(run) { return expandedHistoryKeys.value.has(historyKey(run)) }
function toggleHistory(run) {
  const key = historyKey(run)
  const next = new Set(expandedHistoryKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedHistoryKeys.value = next
}
function boardHistoryKey(item) {
  const board = item?.board || {}
  return `${board.run_id || ''}:${board.generated_at || ''}`
}
function boardHistoryBoard(item) { return item?.board || {} }
function boardHistoryRun(item) { return item?.run || {} }
function isBoardHistoryExpanded(item) { return expandedBoardHistoryKeys.value.has(boardHistoryKey(item)) }
function toggleBoardHistory(item) {
  const key = boardHistoryKey(item)
  const next = new Set(expandedBoardHistoryKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedBoardHistoryKeys.value = next
}
function formatDuration(value) {
  const ms = Number(value)
  if (!Number.isFinite(ms) || ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)}毫秒`
  const totalSeconds = Math.round(ms / 1000)
  if (totalSeconds < 60) return `${totalSeconds}秒`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds ? `${minutes}分${seconds}秒` : `${minutes}分钟`
}
function historyStages(run) {
  const metrics = run?.metrics || {}
  return (Array.isArray(metrics.stage_order) ? metrics.stage_order : []).map(key => ({
    key,
    title: historyStageLabels[key] || '其他阶段',
    status: historyStageStatusLabels[metrics.stage_status?.[key]] || '未记录',
    duration: formatDuration(metrics.stage_ms?.[key]),
    failed: /failed|error|insufficient|validation/i.test(String(metrics.stage_status?.[key] || '')),
  }))
}
function translateHistoryError(value) {
  let text = String(value || '')
  text = text
    .replace(/^playback probe:/i, '播放探测：')
    .replace(/^playback:/i, '播放快照：')
    .replace(/^profile:/i, '画像阶段：')
    .replace(/^candidate:/i, '候选阶段：')
    .replace(/^ranking:/i, '排序阶段：')
    .replace(/^refill:/i, '补选阶段：')
    .replace(/Agent output must be one JSON object:\s*Expecting value/gi, 'Agent 输出不是有效的 JSON 对象：内容为空或格式错误')
    .replace(/Agent output must be one JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent output must be text/gi, 'Agent 输出不是文本')
    .replace(/Expecting value/gi, '内容为空或格式错误')
    .replace(/Extra data/gi, '存在多余内容')
    .replace(/Invalid control character/gi, '包含无效控制字符')
    .replace(/Unterminated string/gi, '字符串未闭合')
    .replace(/profile_validation_failed/gi, '画像校验失败')
    .replace(/policy_superseded/gi, '偏好已更新，请重新生成')
    .replace(/ranking_validation_failed/gi, '排序校验失败')
    .replace(/candidate_insufficient/gi, '候选不足')
    .replace(/recommendation_incomplete/gi, '榜单不足')
    .replace(/ambiguous_playback_count/gi, '播放次数误写为看完次数')
    .replace(/unsupported_playback_claim/gi, '观看经历无法回溯')
    .replace(/Agent did not produce a JSON object/gi, 'Agent 输出不是有效的 JSON 对象')
    .replace(/Agent did not produce text output/gi, 'Agent 输出不是文本')
  return text
}
function historyErrorText(run) {
  const errors = Array.isArray(run?.errors) ? run.errors : []
  if (errors.length) {
    return errors.map(error => translateHistoryError(String(error)
      .replace(/^profile attempt\s+(\d+):/i, '画像第 $1 次：')
      .replace(/^refill attempt\s+(\d+):/i, '补选第 $1 次：')
      .replace(/^attempt\s+(\d+):/i, '排序第 $1 次：')
      .replace(/^profile:/i, '画像阶段：')
      .replace(/^candidate:/i, '候选阶段：')
      .replace(/^ranking:/i, '排序阶段：')
      .replace(/^refill:/i, '补选阶段：'))).join('；')
  }
  return translateHistoryError(run?.message || '本轮没有错误')
}
function historySourceText(run) {
  const sources = run?.metrics?.candidate_source_counts || run?.metrics?.fetched_source_counts || {}
  return Object.entries(sources).map(([key, value]) => `${historySourceLabels[key] || '其他来源'} ${value}`).join('、') || '无来源统计'
}
function historyExclusionText(run) {
  const exclusions = run?.metrics?.candidate_exclusion_counts || {}
  return Object.entries(exclusions).map(([key, value]) => `${historyExclusionLabels[key] || '其他排除原因'} ${value}`).join('、') || '无'
}
function historyPlaybackStatus(value) {
  return ({ ready: '已就绪', cached: '使用缓存', disabled: '已停用', error: '失败', transient_error: '临时错误' })[value] || '状态未知'
}
function historyCandidateTimingText(run) {
  const metrics = run?.metrics || {}
  const parts = [
    ['召回', metrics.candidate_recall_ms],
    ['标准化', metrics.candidate_normalize_ms],
    ['识别', metrics.candidate_recognition_ms],
    ['筛选', metrics.candidate_filter_ms],
    ['快照', metrics.candidate_snapshot_ms],
  ].filter(([, value]) => Number.isFinite(Number(value)))
  return parts.length ? parts.map(([label, value]) => `${label} ${formatDuration(value)}`).join('；') : '未记录'
}
function historyCandidateProcessingText(run) {
  const counts = run?.metrics?.candidate_processing_counts || {}
  const parts = [
    ['召回', counts.raw],
    ['识别输入', counts.recognition_input],
    ['识别成功', counts.recognized],
    ['最终入选', counts.accepted],
  ].filter(([, value]) => Number.isFinite(Number(value)))
  return parts.length ? parts.map(([label, value]) => `${label} ${value} 条`).join('；') : '未记录'
}
function historyProfileCacheText(run) {
  const metrics = run?.metrics || {}
  if (metrics.profile_cache_status === 'hit') return '命中，复用现有画像'
  const reason = profileCacheReasonLabels[metrics.profile_cache_miss_reason]
  if (reason) return `未命中，${reason}`
  return metrics.profile_cache_status ? '未命中，原因未记录' : '未记录'
}
function historyPolicyText(run) {
  const metrics = run?.metrics || {}
  const version = String(metrics.policy_version || '').trim()
  if (!version) return '未记录'
  return `${version}；记忆版本 ${Number(metrics.policy_memory_revision || 0)}；证据 ${Number(metrics.policy_evidence_count || 0)} 项`
}
function historyAgentCalls(run) {
  const calls = Array.isArray(run?.metrics?.agent_provenance) ? run.metrics.agent_provenance : []
  return calls.map((item, index) => {
    const provider = String(item?.selected_provider_name || item?.provider || '').trim()
    const model = String(item?.model || '').trim()
    const source = String(item?.source || 'unknown').trim()
    const status = String(item?.status || 'pending').trim()
    const attempt = Number(item?.attempt || 1)
    const modelCalls = Number(item?.model_call_count || 0)
    return {
      key: `${item?.stage || item?.role || 'agent'}:${item?.attempt || index + 1}:${index}`,
      stage: historyAgentStageLabels[item?.stage] || historyAgentStageLabels[item?.role] || 'Agent',
      attempt: Number.isFinite(attempt) ? Math.max(1, attempt) : 1,
      provider: provider || (source === 'moviepilot_system' ? 'MoviePilot 系统' : source === 'agent_tokens' ? 'Agent Tokens' : '供应商未返回'),
      model: model && model !== 'unknown' ? model : '模型来源未返回',
      source: historyAgentSourceLabels[source] || '来源未返回',
      duration: formatDuration(item?.duration_ms),
      modelCalls: Number.isFinite(modelCalls) ? Math.max(0, modelCalls) : 0,
      status: historyAgentStatusLabels[status] || '状态未返回',
      failed: status === 'failed' || status === 'validation_failed',
      failure: item?.failure_reason ? translateHistoryError(item.failure_reason) : '',
    }
  })
}
function historyModelText(run) {
  const callLabels = historyAgentCalls(run)
    .filter(item => item.model !== '模型来源未返回')
    .map(item => `${item.provider} · ${item.model}`)
  const uniqueCallLabels = [...new Set(callLabels)]
  if (uniqueCallLabels.length) return uniqueCallLabels.join(' / ')
  const provider = String(run?.metrics?.agent_provider || '').trim()
  const model = String(run?.metrics?.agent_model || '').trim()
  if (model && model !== 'unknown') return provider ? `${provider} · ${model}` : model
  return '模型来源未返回'
}
function historyRankingText(run) {
  const metrics = run?.metrics || {}
  const valid = Number(metrics.ranking_valid_count)
  const reserve = Number(metrics.ranking_reserve_count)
  const refill = Number(metrics.refill_agent_calls || 0)
  const fallback = Number(metrics.ranking_fallback_count || 0)
  const fallbackReason = rankingFallbackReasonLabels[metrics.ranking_fallback_reason] || '安全候选补位'
  if (!Number.isFinite(valid)) return '未记录'
  return `校验通过 ${valid} 条；备用 ${Number.isFinite(reserve) ? reserve : 0} 条；补选 ${refill} 次${fallback ? `；保底 ${fallback} 条（${fallbackReason}）` : ''}`
}
function historyValidationDropText(run) {
  const summarize = values => {
    if (!Array.isArray(values) || !values.length) return ''
    const counts = new Map()
    values.forEach(value => {
      const code = String(value || '').trim()
      if (code) counts.set(code, (counts.get(code) || 0) + 1)
    })
    return [...counts.entries()]
      .map(([code, count]) => `${historyValidationDropLabels[code] || '其他校验原因'} ${count}`)
      .join('、')
  }
  const initial = summarize(run?.metrics?.validation_drops)
  const refill = summarize(run?.metrics?.refill_drops)
  const parts = []
  if (initial) parts.push(`首轮：${initial}`)
  if (refill) parts.push(`补选：${refill}`)
  return parts.join('；') || '无'
}
function historySelectionSourceText(run) {
  const metrics = run?.metrics || {}
  const counts = metrics.selection_source_counts || {}
  const agent = Number(metrics.agent_selected_count ?? counts.agent ?? 0)
  const fallback = Number(metrics.safe_fallback_selected_count ?? counts.safe_fallback ?? 0)
  return `Agent 选择 ${agent} 条；安全补位 ${fallback} 条`
}
function historyTriggerText(entry) {
  const value = String(entry?.trigger_reason || '').trim()
  return historyTriggerLabels[value] || value || '未记录'
}
function historyTournamentText(run) {
  const metrics = run?.metrics || {}
  const batches = Number(metrics.preliminary_batch_count || 0)
  const cacheHits = Number(metrics.judgment_card_cache_hit_count ?? metrics.preliminary_cache_hit_count ?? 0)
  const failed = Number(metrics.preliminary_failed_count || 0)
  return `初赛 ${batches} 批；缓存命中 ${cacheHits} 批；失败 ${failed} 批`
}
function historyTournamentTimingText(run) {
  const metrics = run?.metrics || {}
  return `初赛 ${formatDuration(metrics.preliminary_ms)}；决赛 ${formatDuration(metrics.final_ms)}`
}
function historyRepairText(run) {
  const metrics = run?.metrics || {}
  const repairs = Number(metrics.agent_repair_count || 0)
  const finalRetries = Number(metrics.final_retry_count || 0)
  return `结构修正 ${repairs} 次；决赛重试 ${finalRetries} 次`
}
function historyDegradeSourceText(run) {
  const metrics = run?.metrics || {}
  const fallbackCount = Number(metrics.ranking_fallback_count || 0)
  const failedBatches = Number(metrics.preliminary_failed_count || 0)
  const safeFillCount = Number(metrics.preliminary_safe_fill_count || 0)
  if (fallbackCount > 0 || run?.status === 'recommendation_degraded') {
    const reason = rankingFallbackReasonLabels[metrics.ranking_fallback_reason] || '安全候选补位'
    return `安全降级：${reason}`
  }
  if (failedBatches > 0 || safeFillCount > 0) {
    return `部分成功：失败批次补位 ${safeFillCount} 条`
  }
  const inputSource = metrics.final_input_source === 'cached_judgments' ? '复用判断卡' : '本轮判断卡'
  return `完整成功：${inputSource}`
}

async function initialize() {
  try {
    await state.loadOptions()
    if (state.selectedProfileId.value) {
      await Promise.all([
        state.loadProfileData(),
        state.loadRunProgress(),
        state.loadPendingCenter(),
        state.loadConversationStatus(),
      ])
      const progress = state.runProgress.value
      if (!progress?.active && progress?.run_id && state.board.value?.run_id !== progress.run_id) {
        await state.loadProfileData(state.selectedProfileId.value, { force: true })
      }
    }
  } catch (_) {
    // 共享状态承载错误。
  } finally {
    initialized.value = true
    scheduleConversationStatusPoll()
    scheduleRunProgressPoll(1000, true)
  }
}

function stopConversationStatusPoll() {
  if (conversationStatusTimer) window.clearTimeout(conversationStatusTimer)
  conversationStatusTimer = null
}

function scheduleConversationStatusPoll() {
  stopConversationStatusPoll()
  if (pageUnmounted || !initialized.value || !state.selectedProfileId.value) return
  const delay = state.conversationStatus.value?.has_pending ? 2000 : 15000
  conversationStatusTimer = window.setTimeout(pollConversationStatus, delay)
}

async function pollConversationStatus() {
  stopConversationStatusPoll()
  try { await state.loadConversationStatus() } catch (_) { /* 轻量状态错误不打断主页面。 */ }
  scheduleConversationStatusPoll()
}

function stopRunProgressPoll() {
  if (runProgressTimer) window.clearTimeout(runProgressTimer)
  runProgressTimer = null
}

function scheduleRunProgressPoll(delay = 1000, force = false) {
  stopRunProgressPoll()
  if (
    pageUnmounted
    || !initialized.value
    || !state.selectedProfileId.value
    || (!force && !state.runProgress.value?.active)
  ) return
  runProgressTimer = window.setTimeout(pollRunProgress, delay)
}

async function pollRunProgress() {
  stopRunProgressPoll()
  const profileId = state.selectedProfileId.value
  const wasActive = Boolean(state.runProgress.value?.active)
  try {
    const progress = await state.loadRunProgress(profileId)
    if (wasActive && !progress?.active && state.selectedProfileId.value === profileId) {
      await state.loadProfileData(profileId, { force: true })
      if (activeTab.value === 'history') await state.loadHistory(historyPage.value, historyPageSize)
      if (activeTab.value === 'board-history') await state.loadBoardHistory(boardHistoryPage.value, boardHistoryPageSize)
      const completed = ['success', 'recommendation_incomplete', 'recommendation_degraded'].includes(progress?.status)
      snackbar.value = {
        show: true,
        message: progress?.message || (completed ? '榜单生成已完成' : '榜单生成未完成'),
        color: completed ? 'success' : 'error',
      }
    }
  } catch (_) {
    scheduleRunProgressPoll(2000, true)
    return
  }
  scheduleRunProgressPoll()
}

async function handleRefresh() {
  try {
    const result = await state.refresh()
    snackbar.value = {
      show: true,
      message: result?.message || '榜单生成已开始',
      color: 'success',
    }
    scheduleRunProgressPoll(250)
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '榜单生成启动失败', color: 'error' }
  }
}

async function runAction(action, successMessage) {
  try {
    const result = await action()
    snackbar.value = { show: true, message: result?.message || successMessage, color: 'success' }
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '操作失败', color: 'error' }
  }
}

async function changeHistoryPage(page) {
  historyPage.value = page
  try { await state.loadHistory(page, historyPageSize) } catch (_) { /* 错误已保存 */ }
}

async function changeBoardHistoryPage(page) {
  boardHistoryPage.value = page
  try { await state.loadBoardHistory(page, boardHistoryPageSize) } catch (_) { /* 错误已保存 */ }
}

async function addProfileTag(kind) {
  const tag = String(tagDrafts[kind] || '').trim()
  if (!tag) return
  await runAction(
    () => state.updateProfileTag(kind, 'add', tag),
    kind === 'positive' ? '偏好标签已添加' : '避雷标签已添加',
  )
  tagDrafts[kind] = ''
}

async function removeProfileTag(kind, tag) {
  await runAction(
    () => state.updateProfileTag(kind, 'remove', tag),
    kind === 'positive' ? '偏好标签已归档' : '避雷标签已归档',
  )
}

async function restoreProfileTag(item) {
  await runAction(
    () => state.updateProfileTag(item.kind, 'restore', item.tag),
    item.kind === 'positive' ? '偏好标签已恢复' : '避雷标签已恢复',
  )
}

function openAnalysis(item) {
  void state.recordRecommendationDetailOpened(item?.candidate_id)
  selectedAnalysisItem.value = item
  selectedJudgment.value = null
  analysisDialog.value = true
}

function stopExposureObserver() {
  if (exposureObserver) exposureObserver.disconnect()
  exposureObserver = null
}

async function observeRecommendationExposure() {
  await nextTick()
  stopExposureObserver()
  if (pageUnmounted || activeTab.value !== 'board' || !recommendations.value.length) return
  const candidateIds = recommendations.value.map(item => item.candidate_id).filter(Boolean)
  if (!candidateIds.length) return
  if (typeof window === 'undefined' || typeof window.IntersectionObserver !== 'function') {
    void state.recordBoardExposure(candidateIds)
    return
  }
  exposureObserver = new window.IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.25)) return
    stopExposureObserver()
    void state.recordBoardExposure(candidateIds)
  }, { threshold: [0.25] })
  recommendationCards.value.filter(Boolean).forEach(element => exposureObserver.observe(element))
}

function openAnalysisComment(judgment) {
  selectedJudgment.value = judgment
  commentDialog.value = true
}

function showFeedbackResult(message) {
  snackbar.value = { show: true, message, color: 'success' }
}

watch(state.selectedProfileId, async (value, oldValue) => {
  if (!initialized.value || !value || value === oldValue) return
  historyPage.value = 1
  stopConversationStatusPoll()
  stopRunProgressPoll()
  try {
    await Promise.all([
      state.loadProfileData(value),
      state.loadRunProgress(value),
      state.loadPendingCenter(),
      state.loadConversationStatus(),
    ])
  } catch (_) { /* 错误已保存 */ }
  boardHistoryPage.value = 1
  expandedBoardHistoryKeys.value = new Set()
  scheduleConversationStatusPoll()
  scheduleRunProgressPoll(1000, true)
})

watch(activeTab, async value => {
  if (value === 'history') await changeHistoryPage(1)
  if (value === 'board-history') await changeBoardHistoryPage(1)
})

watch(
  () => `${activeTab.value}:${state.board.value?.run_id || ''}:${state.board.value?.revision || 0}:${recommendations.value.length}`,
  () => { void observeRecommendationExposure() },
  { immediate: true },
)

onMounted(() => {
  pageUnmounted = false
  initialize()
})
onBeforeUnmount(() => {
  pageUnmounted = true
  stopConversationStatusPoll()
  stopRunProgressPoll()
  stopExposureObserver()
})
</script>

<template>
  <div class="ar-page" :class="{ 'ar-page--app': !showClose }">
    <VToolbar density="comfortable" class="ar-page__toolbar">
      <VAvatar color="primary" variant="tonal" size="42" rounded="lg" class="ar-page__brand ms-4 me-3">
        <VIcon icon="mdi-brain" size="24" />
      </VAvatar>
      <div class="ar-page__heading">
        <div class="ar-page__title">Agent榜单中心</div>
        <div class="ar-page__subtitle">推荐结果、用户画像与运行记录</div>
      </div>
      <VSpacer />
      <VSelect
        v-if="state.identities.value.length > 1"
        v-model="state.selectedProfileId.value"
        :items="state.identityOptions.value"
        item-title="title"
        item-value="value"
        density="compact"
        variant="outlined"
        hide-details
        label="Emby 用户"
        class="ar-page__identity"
        aria-label="切换 Emby 画像身份"
      />
      <VBtn
        icon="mdi-refresh"
        variant="text"
        :loading="state.loading.action === 'refresh' || state.loading.data"
        :disabled="state.isRunning.value"
        aria-label="刷新详情"
        @click="handleRefresh"
      />
      <VBadge
        :content="criticUnreadCount"
        :model-value="!criticDialog && criticUnreadCount > 0"
        color="error"
        class="ar-page__critic-badge"
      >
        <VBtn
          icon="mdi-forum-outline"
          variant="text"
          :aria-label="criticUnreadCount > 0 ? `打开 ${agentName}，${criticUnreadCount} 条未读回复` : `打开 ${agentName}`"
          @click="criticDialog = true"
        />
      </VBadge>
      <VBadge :content="state.pendingCenter.value?.total || 0" :model-value="Boolean(state.pendingCenter.value?.total)" color="warning" class="ar-page__pending-badge">
        <VBtn icon="mdi-inbox-outline" variant="text" aria-label="打开待处理中心" @click="pendingDialog = true" />
      </VBadge>
      <VBtn icon="mdi-cog-outline" variant="text" aria-label="打开设置" @click="emit('switch', state.options.value?.config || {})" />
      <VBtn v-if="showClose" icon="mdi-close" variant="text" aria-label="关闭详情" class="me-2" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="ar-page__summary-bar">
      <div v-for="stat in detailStats" :key="stat.label" class="ar-page__stat">
        <VIcon :icon="stat.icon" color="primary" size="20" />
        <div>
          <div class="ar-page__stat-value">{{ stat.value }}<span>{{ stat.suffix }}</span></div>
          <div class="ar-page__stat-label">{{ stat.label }}</div>
        </div>
      </div>
      <div
        v-if="state.runProgress.value?.active"
        class="ar-page__progress"
        :class="{ 'ar-page__progress--agent': state.runProgress.value?.agent_active }"
        aria-live="polite"
      >
        <VProgressCircular indeterminate color="primary" size="22" width="2" />
        <div class="ar-page__progress-copy">
          <div class="ar-page__progress-title">{{ agentName }}</div>
          <div class="ar-page__progress-message">{{ state.runProgress.value?.message || '正在生成榜单' }}</div>
        </div>
      </div>
      <VChip
        v-if="state.isRunning.value"
        color="primary"
        variant="tonal"
        size="small"
        prepend-icon="mdi-loading"
        class="ar-page__runtime-chip"
      >
        {{ state.runProgress.value?.stage_index ? `${state.runProgress.value.stage_index}/${state.runProgress.value.stage_total}` : '准备中' }}
      </VChip>
    </div>

    <nav class="ar-page__tabs" aria-label="详情视图">
      <VList density="compact" nav class="ar-page__tab-list">
      <VListItem
        v-for="tab in tabs"
        :key="tab.key"
        :active="activeTab === tab.key"
        color="primary"
        rounded="lg"
        class="ar-page__tab"
        :aria-current="activeTab === tab.key ? 'page' : undefined"
        @click="activeTab = tab.key"
      >
        <template #prepend><VIcon :icon="tab.icon" size="18" /></template>
        <VListItemTitle>{{ tab.title }}</VListItemTitle>
      </VListItem>
      </VList>
    </nav>
    <VDivider />

    <div class="ar-page__content">
      <VAlert v-if="state.error.value" type="error" variant="tonal" class="mb-3">{{ state.error.value.message }}</VAlert>
      <VSkeletonLoader v-if="state.loading.data" type="list-item-avatar-three-line@5" />

      <template v-else>
        <section v-show="activeTab === 'board'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">个性推荐榜单</div>
              <div class="ar-page__section-desc">Agent 根据订阅画像，从发现候选中挑出的前5名。</div>
            </div>
            <VChip size="small" color="primary" variant="tonal">{{ recommendations.length }} 部</VChip>
          </div>

          <VEmptyState
            v-if="!recommendations.length"
            icon="mdi-format-list-numbered"
            title="推荐榜单尚未生成"
            text="点击右上角刷新，根据播放画像生成前5名。"
          />
          <div v-else class="ar-page__ranking">
            <article v-for="item in recommendations" ref="recommendationCards" :key="item.candidate_id" class="ar-page__rank-item">
              <div class="ar-page__rank" :class="{ 'ar-page__rank--top': item.rank <= 3 }">{{ item.rank }}</div>
              <div class="ar-page__poster">
                <VImg v-if="item.poster_path" :src="item.poster_path" :alt="`${item.title} 海报`" cover>
                  <template #error><div class="ar-page__poster-error"><VIcon icon="mdi-image-off-outline" size="26" /></div></template>
                </VImg>
                <VIcon v-else icon="mdi-image-off-outline" size="26" />
              </div>
              <div class="ar-page__rank-main">
                <div class="ar-page__title-row">
                  <div class="ar-page__media-title">{{ item.title }}</div>
                  <VChip size="x-small" variant="tonal">{{ mediaTypeLabel(item.media_type) }}</VChip>
                </div>
                <div class="ar-page__meta-row">
                  <span>{{ item.year || '年份未知' }}</span>
                </div>
                <div class="ar-page__rank-copy">
                  <span class="ar-page__copy-label">推荐：</span>
                  <span class="ar-page__copy-text ar-page__copy-text--reason">{{ item.reason || item.summary || '等待 Agent 补充推荐理由' }}</span>
                </div>
                <div class="ar-page__rank-copy ar-page__rank-copy--muted">
                  <span class="ar-page__copy-label">简介：</span>
                  <span class="ar-page__copy-text ar-page__copy-text--intro">{{ item.summary || '暂无简介' }}</span>
                </div>
                <div v-if="item.match_tags?.length" class="ar-page__match-tags">
                  <VChip v-for="tag in item.match_tags" :key="tag" size="x-small" variant="outlined">{{ tag }}</VChip>
                </div>
              </div>
              <div class="ar-page__rank-actions">
                <VTooltip text="查看 Agent 分析">
                  <template #activator="{ props: tooltipProps }">
                    <VBtn
                      v-bind="tooltipProps"
                      icon="mdi-text-box-search-outline"
                      variant="text"
                      size="small"
                      :aria-label="`查看 ${item.title} 的 Agent 分析`"
                      :disabled="!item.analysis_id"
                      @click="openAnalysis(item)"
                    />
                  </template>
                </VTooltip>
                <VChip size="x-small" :color="fitScoreColor(item)" variant="tonal" class="ar-page__fit-score">契合度 {{ fitScoreText(item) }}</VChip>
                <RecommendationActions
                  :item="item"
                  :loading-action="state.loading.action"
                  :native-subscribe="nativeSubscribe"
                  size="small"
                  @like="candidateId => runAction(() => state.reactToRecommendation('like', candidateId), '已记录点赞')"
                  @dislike="candidateId => runAction(() => state.reactToRecommendation('dislike', candidateId), '已记录点踩')"
                  @subscribe="candidateId => runAction(() => state.subscribe(candidateId), '订阅操作已完成')"
                  @native-subscribe-opened="candidateId => runAction(() => state.recordNativeDrawerOpened(candidateId), '已打开订阅设置')"
                  @archive="candidateId => runAction(() => state.archive(candidateId), '已忽略推荐')"
                />
              </div>
            </article>
          </div>
        </section>

        <section v-show="activeTab === 'profile'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">用户画像</div>
              <div class="ar-page__section-desc">用播放样本描述偏好、避雷方向与本轮榜单命中。</div>
            </div>
            <div class="d-flex align-center ga-2 flex-wrap justify-end">
              <VChip :color="questioningStateMeta.color" size="small" variant="tonal" :prepend-icon="questioningStateMeta.icon">{{ questioningStateMeta.text }}</VChip>
              <VChip size="small" variant="tonal" prepend-icon="mdi-clock-outline">{{ formatTime(state.profile.value?.generated_at) }}</VChip>
            </div>
          </div>

          <VCard variant="outlined" class="ar-page__section-card">
            <VCardItem class="ar-page__profile-head">
              <template #prepend>
                <VAvatar color="primary" variant="tonal" size="44"><VIcon icon="mdi-account-heart-outline" /></VAvatar>
              </template>
              <VCardTitle class="text-subtitle-1 font-weight-bold">画像摘要</VCardTitle>
              <VCardSubtitle>Emby 用户 {{ state.selectedUsername.value || '—' }} · 运行 {{ profileRunId }}</VCardSubtitle>
            </VCardItem>
            <VDivider />
            <VCardText class="ar-page__profile-body">
              <div class="ar-page__profile-summary-panel">
                <div class="ar-page__profile-label"><VIcon icon="mdi-text-box-search-outline" size="18" />口味摘要</div>
                <div class="ar-page__profile-summary">{{ state.profile.value?.summary || '尚未生成用户画像' }}</div>
              </div>

              <div class="ar-page__profile-metrics">
                <div v-for="stat in profileStats" :key="stat.label" class="ar-page__profile-metric">
                  <VIcon :icon="stat.icon" color="primary" size="19" />
                  <div><strong>{{ stat.value }}<span>{{ stat.suffix }}</span></strong><small>{{ stat.label }}</small></div>
                </div>
              </div>

              <div class="ar-page__learning-health">
                <div class="ar-page__profile-label"><VIcon icon="mdi-chart-timeline-variant" size="18" />学习健康度</div>
                <div class="ar-page__health-grid">
                  <div><strong>{{ state.learningHealth.value?.short_term_signal_count || 0 }}</strong><small>短期信号</small></div>
                  <div><strong>{{ state.learningHealth.value?.confirmed_memory_count || 0 }}</strong><small>确认记忆</small></div>
                  <div><strong>{{ state.learningHealth.value?.pending_count || 0 }}</strong><small>待确认</small></div>
                  <div><strong>{{ state.learningHealth.value?.processed_count || 0 }}</strong><small>已处理</small></div>
                  <div><strong>{{ state.learningHealth.value?.exposure_count || 0 }}</strong><small>有效曝光</small></div>
                </div>
                <div class="ar-page__health-footer">
                  <span>{{ healthCoverageText(state.learningHealth.value) }}</span>
                  <span v-if="state.learningHealth.value?.last_effective_feedback_at">最近有效反馈 {{ formatTime(state.learningHealth.value.last_effective_feedback_at) }}</span>
                  <VChip v-if="state.learningHealth.value?.attention_required" size="x-small" color="warning" variant="tonal">{{ state.learningHealth.value.attention_reason || '建议检查反馈归因' }}</VChip>
                </div>
              </div>

              <div class="ar-page__profile-groups">
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label"><VIcon icon="mdi-heart-outline" size="18" />偏好标签</div>
                  <div class="ar-page__chips">
                    <VChip v-for="tag in positiveTags" :key="tag" color="primary" variant="tonal" size="small" closable @click:close="removeProfileTag('positive', tag)">{{ tag }}</VChip>
                    <span v-if="!positiveTags.length" class="text-caption text-medium-emphasis">暂无偏好标签</span>
                  </div>
                  <div class="ar-page__tag-editor">
                    <VTextField v-model="tagDrafts.positive" label="添加偏好标签" density="compact" variant="outlined" hide-details maxlength="20" @keyup.enter="addProfileTag('positive')" />
                    <VBtn color="primary" variant="tonal" size="small" :loading="state.loading.action === 'profile/tags'" @click="addProfileTag('positive')">添加</VBtn>
                  </div>
                </div>
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label ar-page__profile-label--negative"><VIcon icon="mdi-shield-alert-outline" size="18" />避雷标签</div>
                  <div class="ar-page__chips">
                    <VChip v-for="tag in negativeTags" :key="tag" color="error" variant="tonal" size="small" closable @click:close="removeProfileTag('negative', tag)">{{ tag }}</VChip>
                    <span v-if="!negativeTags.length" class="text-caption text-medium-emphasis">暂无避雷标签</span>
                  </div>
                  <div class="ar-page__tag-editor">
                    <VTextField v-model="tagDrafts.negative" label="添加避雷标签" density="compact" variant="outlined" hide-details maxlength="20" @keyup.enter="addProfileTag('negative')" />
                    <VBtn color="error" variant="tonal" size="small" :loading="state.loading.action === 'profile/tags'" @click="addProfileTag('negative')">添加</VBtn>
                  </div>
                </div>
                <div class="ar-page__profile-group">
                  <div class="ar-page__profile-label"><VIcon icon="mdi-target-account" size="18" />本轮命中</div>
                  <div class="ar-page__chips">
                    <VChip v-for="item in boardMatchTags" :key="item.tag" color="info" variant="tonal" size="small">
                      {{ item.tag }}<span v-if="item.count > 1" class="ar-page__tag-count">×{{ item.count }}</span>
                    </VChip>
                    <span v-if="!boardMatchTags.length" class="text-caption text-medium-emphasis">暂无命中标签</span>
                  </div>
                </div>
                <div class="ar-page__profile-group ar-page__profile-group--archived">
                  <div class="ar-page__profile-label ar-page__profile-label--archived"><VIcon icon="mdi-archive-outline" size="18" />归档标签</div>
                  <div class="ar-page__chips">
                    <div v-for="item in archivedProfileTags" :key="`${item.kind}:${item.tag}`" class="ar-page__archived-tag">
                      <VChip :color="item.kind === 'negative' ? 'error' : 'primary'" variant="outlined" size="small">
                        {{ item.tag }} · {{ item.kind === 'negative' ? '避雷' : '偏好' }}
                      </VChip>
                      <VTooltip text="恢复标签">
                        <template #activator="{ props: tooltipProps }">
                          <VBtn v-bind="tooltipProps" icon="mdi-restore" variant="text" size="x-small" aria-label="恢复标签" :loading="state.loading.action === 'profile/tags'" @click="restoreProfileTag(item)" />
                        </template>
                      </VTooltip>
                    </div>
                    <span v-if="!archivedProfileTags.length" class="text-caption text-medium-emphasis">暂无归档标签</span>
                  </div>
                </div>
              </div>
            </VCardText>
          </VCard>
        </section>

        <section v-show="activeTab === 'archive'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">忽略归档</div>
              <div class="ar-page__section-desc">保留被忽略条目的原排名，可随时恢复推荐。</div>
            </div>
            <VChip size="small" variant="tonal">{{ archiveEntries.length }} 部</VChip>
          </div>

          <VEmptyState v-if="!archiveEntries.length" icon="mdi-archive-outline" title="暂无忽略记录" text="榜单中点击忽略后，条目会出现在这里。" />
          <div v-else class="ar-page__archive-list">
            <VCard v-for="entry in archiveEntries" :key="entry.candidate_id" variant="outlined" class="ar-page__archive-card">
              <VCardItem>
                <template #prepend>
                  <div class="ar-page__archive-rank">#{{ entry.original_rank }}</div>
                </template>
                <VCardTitle class="text-subtitle-2 font-weight-bold">{{ entry.recommendation?.title || entry.candidate_id }}</VCardTitle>
                <VCardSubtitle>忽略于 {{ formatTime(entry.archived_at) }}</VCardSubtitle>
                <template #append>
                  <VBtn size="small" variant="tonal" color="primary" class="mr-1" prepend-icon="mdi-backup-restore" @click="runAction(() => state.restore(entry.candidate_id), '推荐已恢复')">恢复</VBtn>
                  <VBtn icon="mdi-delete-outline" size="small" variant="text" color="error" :aria-label="`删除归档 ${entry.candidate_id}`" @click="runAction(() => state.deleteArchive(entry.candidate_id), '归档记录已删除')" />
                </template>
              </VCardItem>
              <VCardText v-if="entry.recommendation?.summary" class="ar-page__archive-summary">{{ entry.recommendation.summary }}</VCardText>
            </VCard>
          </div>
        </section>

        <section v-show="activeTab === 'history'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">运行历史</div>
              <div class="ar-page__section-desc">按结果、耗时、阶段和候选统计查看每次运行。</div>
            </div>
            <VChip size="small" variant="tonal">{{ state.historyMeta.value.total || 0 }} 次</VChip>
          </div>

          <VEmptyState v-if="!state.history.value.length" icon="mdi-history" title="暂无运行记录" text="榜单生成后，这里会记录每次执行结果。" />
          <template v-else>
            <div class="ar-page__history-list">
              <article v-for="run in state.history.value" :key="historyKey(run)" class="ar-page__history-item">
                <div class="ar-page__history-head">
                  <div class="ar-page__history-time">
                    <VIcon icon="mdi-clock-outline" size="17" color="primary" />
                    <strong>{{ formatTime(run.finished_at || run.started_at) }}</strong>
                    <span v-if="run.metrics?.elapsed_ms">耗时 {{ formatDuration(run.metrics.elapsed_ms) }}</span>
                  </div>
                  <VChip size="small" :color="statusMetaFor(run.status).color" variant="tonal">
                    {{ statusMetaFor(run.status).text }}
                  </VChip>
                </div>
                <div class="ar-page__history-message"><span class="ar-page__history-message-label">结果：</span>{{ translateHistoryError(run.message || '本轮运行已记录') }}</div>
                <div class="ar-page__history-metrics">
                  <div><strong>{{ run.metrics?.candidate_count ?? 0 }}</strong><span>候选条目</span></div>
                  <div><strong>{{ run.metrics?.final_count ?? 0 }}</strong><span>安全推荐</span></div>
                  <div><strong class="ar-page__history-model">{{ historyModelText(run) }}</strong><span>供应商 / 模型</span></div>
                  <div><strong>{{ run.metrics?.subscription_success_count ?? 0 }}</strong><span>自动订阅</span></div>
                </div>
                <div v-if="historyStages(run).length" class="ar-page__history-pipeline">
                  <div v-for="stage in historyStages(run)" :key="stage.key" class="ar-page__history-stage" :class="{ 'ar-page__history-stage--failed': stage.failed }">
                    <VIcon :icon="stage.failed ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline'" :color="stage.failed ? 'error' : 'success'" size="17" />
                    <div><strong>{{ stage.title }}</strong><small>{{ stage.status }} · {{ stage.duration }}</small></div>
                  </div>
                </div>
                <div class="ar-page__history-error" :class="{ 'ar-page__history-error--ok': !run.errors?.length && run.status === 'success' }">
                  <VIcon :icon="run.errors?.length ? 'mdi-alert-outline' : 'mdi-information-outline'" size="16" />
                  <span>{{ historyErrorText(run) }}</span>
                </div>
                <div class="ar-page__history-footer">
                  <span>来源：{{ historySourceText(run) }}</span>
                  <VBtn size="x-small" variant="text" :append-icon="isHistoryExpanded(run) ? 'mdi-chevron-up' : 'mdi-chevron-down'" @click="toggleHistory(run)">
                    {{ isHistoryExpanded(run) ? '收起细节' : '查看细节' }}
                  </VBtn>
                </div>
                <div v-if="isHistoryExpanded(run)" class="ar-page__history-details">
                  <div><span>运行编号</span><code>{{ run.run_id || '—' }}</code></div>
                  <div><span>模型调用</span><span>{{ run.metrics?.model_call_count ?? run.metrics?.agent_calls ?? 0 }} 次；画像任务 {{ run.metrics?.profile_agent_calls ?? 0 }} 次；排序任务 {{ run.metrics?.ranking_agent_calls ?? 0 }} 次</span></div>
                  <div v-if="historyAgentCalls(run).length" class="ar-page__history-call-row">
                    <span>调用明细</span>
                    <div class="ar-page__history-agent-calls">
                      <div v-for="call in historyAgentCalls(run)" :key="call.key" class="ar-page__history-agent-call" :class="{ 'ar-page__history-agent-call--failed': call.failed }">
                        <div class="ar-page__history-agent-head">
                          <strong>{{ call.stage }} · 第 {{ call.attempt }} 次</strong>
                          <span>{{ call.status }}</span>
                        </div>
                        <div>{{ call.provider }} · {{ call.model }}</div>
                        <small>{{ call.source }} · {{ call.duration }} · 模型调用 {{ call.modelCalls }} 次</small>
                        <small v-if="call.failure" class="ar-page__history-agent-error">{{ call.failure }}</small>
                      </div>
                    </div>
                  </div>
                  <div><span>画像缓存</span><span>{{ historyProfileCacheText(run) }}</span></div>
                  <div><span>排序策略</span><code>{{ historyPolicyText(run) }}</code></div>
                  <div><span>播放快照</span><span>{{ run.metrics?.playback_count ?? 0 }} 条，{{ historyPlaybackStatus(run.metrics?.playback_status) }}</span></div>
                  <div><span>候选耗时</span><span>{{ historyCandidateTimingText(run) }}</span></div>
                  <div><span>候选处理</span><span>{{ historyCandidateProcessingText(run) }}</span></div>
                  <div><span>初赛批次</span><span>{{ historyTournamentText(run) }}</span></div>
                  <div><span>阶段耗时</span><span>{{ historyTournamentTimingText(run) }}</span></div>
                  <div><span>修正次数</span><span>{{ historyRepairText(run) }}</span></div>
                  <div><span>降级来源</span><span>{{ historyDegradeSourceText(run) }}</span></div>
                  <div><span>排序校验</span><span>{{ historyRankingText(run) }}</span></div>
                  <div><span>校验丢弃</span><span>{{ historyValidationDropText(run) }}</span></div>
                  <div><span>选择来源</span><span>{{ historySelectionSourceText(run) }}</span></div>
                  <div><span>候选排除</span><span>{{ historyExclusionText(run) }}</span></div>
                </div>
              </article>
            </div>
            <VPagination v-model="historyPage" :length="historyPages" density="compact" total-visible="7" class="mt-3" @update:model-value="changeHistoryPage" />
          </template>
          <span class="d-none">page_size={{ historyPageSize }}</span>
        </section>

        <section v-show="activeTab === 'board-history'" class="ar-page__pane">
          <div class="ar-page__section-head">
            <div>
              <div class="ar-page__section-title">历史榜单</div>
              <div class="ar-page__section-desc">只读查看每一轮生成时的完整前5名，保留当时的理由与 Agent 契合度。</div>
            </div>
            <VChip size="small" variant="tonal">{{ state.boardHistoryMeta.value.total || 0 }} 轮</VChip>
          </div>

          <VAlert v-if="state.boardHistoryMeta.value.notice" type="info" variant="tonal" class="mb-3">
            {{ state.boardHistoryMeta.value.notice }}
          </VAlert>
          <VEmptyState
            v-if="!state.boardHistory.value.length"
            icon="mdi-view-list-outline"
            title="暂无历史榜单"
            text="榜单生成后，这里会保存每一轮的完整内容。"
          />
          <template v-else>
            <div class="ar-page__board-history-list">
              <article
                v-for="entry in state.boardHistory.value"
                :key="boardHistoryKey(entry)"
                class="ar-page__board-history-item"
              >
                <div class="ar-page__board-history-head">
                  <div class="ar-page__history-time">
                    <VIcon icon="mdi-clock-outline" size="17" color="primary" />
                    <strong>{{ formatTime(boardHistoryRun(entry).finished_at || boardHistoryBoard(entry).generated_at) }}</strong>
                    <span>新推荐 {{ entry.new_count ?? 0 }} 条</span>
                    <span>上轮重合 {{ entry.overlap_count ?? 0 }} 条</span>
                    <span>回归 {{ entry.return_count ?? entry.returning_count ?? 0 }} 条</span>
                  </div>
                  <VChip size="small" :color="statusMetaFor(boardHistoryBoard(entry).status || boardHistoryRun(entry).status).color" variant="tonal">
                    {{ statusMetaFor(boardHistoryBoard(entry).status || boardHistoryRun(entry).status).text }}
                  </VChip>
                </div>
                <div class="ar-page__board-history-summary">
                  <span>{{ boardHistoryBoard(entry).recommendations?.length || 0 }} 条推荐</span>
                  <span v-if="boardHistoryBoard(entry).message">{{ boardHistoryBoard(entry).message }}</span>
                  <VBtn size="x-small" variant="text" :append-icon="isBoardHistoryExpanded(entry) ? 'mdi-chevron-up' : 'mdi-chevron-down'" @click="toggleBoardHistory(entry)">
                    {{ isBoardHistoryExpanded(entry) ? '收起榜单' : '展开榜单' }}
                  </VBtn>
                </div>
                <div class="ar-page__board-history-metrics">
                  <span>触发：{{ historyTriggerText(entry) }}</span>
                  <span>重合率 {{ Math.round(Number(entry.previous_overlap_rate || 0) * 100) }}%</span>
                  <span>近五轮均值 {{ Math.round(Number(entry.recent_average_overlap_rate || 0) * 100) }}%</span>
                  <span v-if="entry.exposed">已曝光 {{ entry.exposure_count || 0 }} 次{{ entry.interacted ? ' · 有操作' : ' · 无操作' }}</span>
                  <span v-else>未确认曝光</span>
                </div>
                <div v-if="isBoardHistoryExpanded(entry)" class="ar-page__board-history-detail">
                  <div
                    v-for="item in (boardHistoryBoard(entry).recommendations || []).slice(0, 5)"
                    :key="`${boardHistoryKey(entry)}:${item.candidate_id}`"
                    class="ar-page__board-history-rank"
                  >
                    <div class="ar-page__rank" :class="{ 'ar-page__rank--top': item.rank <= 3 }">{{ item.rank }}</div>
                    <div class="ar-page__poster ar-page__poster--history">
                      <VImg v-if="item.poster_path" :src="item.poster_path" :alt="`${item.title} 海报`" cover>
                        <template #error><div class="ar-page__poster-error"><VIcon icon="mdi-image-off-outline" size="22" /></div></template>
                      </VImg>
                      <VIcon v-else icon="mdi-image-off-outline" size="22" />
                    </div>
                    <div class="ar-page__board-history-copy">
                      <div class="ar-page__title-row">
                        <div class="ar-page__media-title">{{ item.title || '未命名作品' }}</div>
                        <VChip size="x-small" variant="tonal">{{ mediaTypeLabel(item.media_type) }}</VChip>
                        <VChip v-if="item.history_state === 'new'" size="x-small" color="success" variant="tonal">本轮新入榜</VChip>
                        <VChip v-else size="x-small" variant="outlined">历史再推荐</VChip>
                        <VChip v-if="item.selection_source === 'returning'" size="x-small" color="info" variant="tonal">回归推荐</VChip>
                      </div>
                      <div class="ar-page__meta-row"><span>{{ item.year || '年份未知' }}</span></div>
                      <div class="ar-page__rank-copy">
                        <span class="ar-page__copy-label">推荐：</span>
                        <span class="ar-page__copy-text">{{ item.reason || item.summary || '暂无推荐理由' }}</span>
                      </div>
                      <div class="ar-page__rank-copy ar-page__rank-copy--muted">
                        <span class="ar-page__copy-label">契合度：</span>
                        <span class="ar-page__copy-text">{{ fitScoreText(item) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
            <VPagination v-model="boardHistoryPage" :length="boardHistoryPages" density="compact" total-visible="7" class="mt-3" @update:model-value="changeBoardHistoryPage" />
          </template>
          <span class="d-none">page_size={{ boardHistoryPageSize }}</span>
        </section>
      </template>
    </div>

    <AgentAnalysisDialog v-model="analysisDialog" :state="state" :item="selectedAnalysisItem" @comment="openAnalysisComment" />
    <FeedbackCommentDialog
      v-model="commentDialog"
      :state="state"
      :item="selectedAnalysisItem"
      :judgment="selectedJudgment"
      @submitted="showFeedbackResult('评论已记录，Agent 将异步重新理解')"
    />
    <CriticChatDialog v-model="criticDialog" :state="state" @pending-change="state.loadPendingCenter" />
    <PendingConfirmations v-model="pendingDialog" :state="state" @changed="showFeedbackResult('待处理项目已更新')" />

    <VSnackbar v-model="snackbar.show" :color="snackbar.color">{{ snackbar.message }}</VSnackbar>
  </div>
</template>

<style scoped>
.ar-page { width: 100%; max-width: none; box-sizing: border-box; height: min(900px, calc(100dvh - 16px)); display: flex; flex-direction: column; overflow: hidden; overflow-x: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 14px; background: transparent; }
.ar-page__toolbar { flex: 0 0 auto; background: transparent; }
.ar-page :deep(.v-btn--icon) { min-width: 40px; min-height: 40px; }
.ar-page :deep(.v-tabs), .ar-page :deep(.v-table), .ar-page :deep(.v-skeleton-loader), .ar-page :deep(.v-empty-state) { background: transparent; }
.ar-page__table-wrap :deep(.v-table__wrapper > table > thead > tr > th) { background: rgba(var(--v-theme-on-surface), .018) !important; }
.ar-page__brand { flex: 0 0 auto; }
.ar-page__heading { min-width: 0; }
.ar-page__title { font-size: 1.08rem; font-weight: 700; line-height: 1.35; }
.ar-page__subtitle { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; }
.ar-page__identity { width: 210px; margin-right: 4px; }
.ar-page__summary-bar { flex: 0 0 auto; min-height: 56px; display: grid; grid-template-columns: repeat(3, minmax(120px, .7fr)) minmax(220px, 1.3fr) auto; align-items: center; gap: 8px; padding: 6px 14px; background: transparent; }
.ar-page__stat { min-width: 0; display: flex; align-items: center; gap: 10px; padding: 4px 10px; border-right: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .7)); }
.ar-page__stat-value { font-size: 17px; font-weight: 700; line-height: 1.2; }
.ar-page__stat-value span { margin-left: 2px; color: rgba(var(--v-theme-on-surface), .48); font-size: 11px; font-weight: 500; }
.ar-page__stat-label { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .55); font-size: 11px; }
.ar-page__progress { min-width: 0; display: flex; align-items: center; gap: 9px; padding: 6px 10px; border-left: 2px solid rgba(var(--v-theme-primary), .42); background: rgba(var(--v-theme-primary), .035); }
.ar-page__progress--agent { background: rgba(var(--v-theme-primary), .075); }
.ar-page__progress-copy { min-width: 0; }
.ar-page__progress-title { color: rgb(var(--v-theme-primary)); font-size: 11px; font-weight: 700; }
.ar-page__progress-message { margin-top: 1px; overflow: hidden; color: rgba(var(--v-theme-on-surface), .72); font-size: 12px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.ar-page__runtime-chip { margin-inline: 8px; }
.ar-page__tabs { flex: 0 0 auto; min-height: 40px; overflow-x: auto; overflow-y: hidden; background: transparent; scrollbar-width: none; overscroll-behavior-inline: contain; touch-action: pan-x; -webkit-overflow-scrolling: touch; }
.ar-page__tabs::-webkit-scrollbar { display: none; }
.ar-page__tab-list { display: flex; flex-wrap: nowrap; gap: 4px; min-width: max-content; padding: 4px 10px !important; background: transparent; }
.ar-page__tab { flex: 0 0 auto; min-width: 112px; margin: 0; padding-inline: 12px; font-size: 13px; font-weight: 600; letter-spacing: 0; }
.ar-page__tab :deep(.v-list-item-title) { white-space: nowrap; }
.ar-page__content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 10px 14px 12px; background: transparent; scrollbar-width: none; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.ar-page__content::-webkit-scrollbar { display: none; }
.ar-page__pane { min-height: 100%; }
.ar-page__section-head { min-height: 38px; display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
.ar-page__section-title { font-size: 15px; font-weight: 700; }
.ar-page__section-desc { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; line-height: 1.5; }
.ar-page__ranking, .ar-page__archive-list { display: flex; flex-direction: column; gap: 6px; }
.ar-page__rank-item { display: grid; grid-template-columns: 34px 50px minmax(0, 1fr) auto; gap: 9px; align-items: center; min-height: 88px; padding: 6px 9px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: transparent; transition: background .12s, border-color .12s; }
.ar-page__rank-item:hover { border-color: rgba(var(--v-theme-primary), .28); background: rgba(var(--v-theme-primary), .045); }
.ar-page__poster { width: 50px; height: 75px; display: grid; place-items: center; overflow: hidden; border-radius: 6px; color: rgba(var(--v-theme-on-surface), .4); background: rgba(var(--v-theme-on-surface), .05); }
.ar-page__poster :deep(.v-img) { width: 100%; height: 100%; }
.ar-page__poster-error { width: 100%; height: 100%; display: grid; place-items: center; }
.ar-page__rank { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; color: rgba(var(--v-theme-on-surface), .62); background: rgba(var(--v-theme-on-surface), .06); font-size: 12px; font-weight: 700; }
.ar-page__rank--top { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .14); }
.ar-page__rank-main { min-width: 0; }
.ar-page__title-row { display: flex; align-items: flex-start; gap: 8px; }
.ar-page__media-title { min-width: 0; display: -webkit-box; overflow: hidden; overflow-wrap: anywhere; -webkit-box-orient: vertical; -webkit-line-clamp: 2; font-size: 15px; font-weight: 700; line-height: 1.4; }
.ar-page__meta-row { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 1px; color: rgba(var(--v-theme-on-surface), .52); font-size: 11px; }
.ar-page__rank-copy { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 5px; margin-top: 3px; font-size: 12px; line-height: 1.4; }
.ar-page__rank-copy--muted { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .62); }
.ar-page__copy-label { color: rgb(var(--v-theme-primary)); font-size: 11px; font-weight: 600; }
.ar-page__copy-text { min-width: 0; display: block; overflow: visible; overflow-wrap: anywhere; }
.ar-page__match-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.ar-page__rank-actions { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 7px; padding-bottom: 2px; }
.ar-page__fit-score { flex: 0 0 auto; margin-left: auto; }
.ar-page__section-card, .ar-page__archive-card, .ar-page__table-card { border-radius: 10px; background: transparent; }
.ar-page__profile-head { padding: 14px 16px; }
.ar-page__profile-body { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(270px, .65fr); gap: 12px; padding: 14px; }
.ar-page__profile-summary-panel, .ar-page__profile-metrics, .ar-page__profile-group { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .72)); border-radius: 9px; background: transparent; }
.ar-page__profile-summary-panel { min-height: 118px; padding: 12px 14px; }
.ar-page__profile-summary { margin-top: 8px; font-size: 14px; line-height: 1.7; }
.ar-page__profile-label { display: flex; align-items: center; gap: 6px; color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.ar-page__profile-label--negative { color: rgb(var(--v-theme-error)); }
.ar-page__profile-label--archived { color: rgba(var(--v-theme-on-surface), .62); }
.ar-page__profile-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; overflow: hidden; }
.ar-page__profile-metric { min-width: 0; display: flex; align-items: center; gap: 8px; padding: 10px; border-right: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .62)); }
.ar-page__profile-metric:last-child { border-right: 0; }
.ar-page__profile-metric strong { display: block; font-size: 17px; line-height: 1.2; }
.ar-page__profile-metric strong span { margin-left: 2px; color: rgba(var(--v-theme-on-surface), .48); font-size: 10px; font-weight: 500; }
.ar-page__profile-metric small { display: block; margin-top: 2px; color: rgba(var(--v-theme-on-surface), .55); font-size: 10px; white-space: nowrap; }
.ar-page__learning-health { grid-column: 1 / -1; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .7)); border-radius: 9px; background: rgba(var(--v-theme-primary), .025); }
.ar-page__health-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin-top: 8px; }
.ar-page__health-grid > div { min-width: 0; display: grid; gap: 2px; }
.ar-page__health-grid strong { font-size: 16px; }
.ar-page__health-grid small, .ar-page__health-footer { color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-page__health-footer { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; margin-top: 8px; }
.ar-page__profile-groups { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.ar-page__profile-group { min-height: 108px; padding: 11px 12px; }
.ar-page__profile-group--archived { grid-column: 1 / -1; min-height: 74px; }
.ar-page__chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.ar-page__archived-tag { display: inline-flex; align-items: center; gap: 2px; }
.ar-page__tag-editor { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; margin-top: 10px; }
.ar-page__tag-count { margin-left: 3px; opacity: .66; font-size: 10px; }
.ar-page__archive-card :deep(.v-card-item) { padding: 12px 14px; }
.ar-page__archive-rank { min-width: 38px; height: 32px; display: grid; place-items: center; border-radius: 8px; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .1); font-size: 12px; font-weight: 700; }
.ar-page__archive-summary { padding-top: 0; color: rgba(var(--v-theme-on-surface), .62); font-size: 12px; }
.ar-page__table-card { overflow: hidden; }
.ar-page__table-wrap { max-width: 100%; overflow-x: auto; }
.ar-page__table-wrap :deep(th) { font-size: 12px; font-weight: 700; }
.ar-page__table-wrap :deep(td) { font-size: 12px; }
.ar-page__time-cell { min-width: 150px; white-space: nowrap; }
.ar-page__error-cell { min-width: 240px; max-width: 360px; white-space: normal; overflow-wrap: anywhere; line-height: 1.45; }
.ar-page__history-list { display: flex; flex-direction: column; gap: 10px; }
.ar-page__history-item { padding: 12px 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; background: transparent; }
.ar-page__history-head, .ar-page__history-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ar-page__history-time { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; }
.ar-page__history-time strong { font-size: 13px; }
.ar-page__history-time span, .ar-page__history-footer { color: rgba(var(--v-theme-on-surface), .55); font-size: 11px; }
.ar-page__history-message { margin-top: 5px; color: rgba(var(--v-theme-on-surface), .78); font-size: 12px; line-height: 1.55; }
.ar-page__history-message-label { color: rgb(var(--v-theme-primary)); font-weight: 600; }
.ar-page__history-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 10px; overflow: hidden; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .68)); border-radius: 8px; }
.ar-page__history-metrics > div { min-width: 0; display: flex; flex-wrap: wrap; align-items: baseline; justify-content: center; gap: 4px; padding: 8px; border-right: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .58)); }
.ar-page__history-metrics > div:last-child { border-right: 0; }
.ar-page__history-metrics strong { font-size: 15px; }
.ar-page__history-metrics .ar-page__history-model { max-width: 100%; overflow-wrap: anywhere; text-align: center; font-size: 12px; }
.ar-page__history-metrics span { color: rgba(var(--v-theme-on-surface), .6); font-size: 11px; }
.ar-page__history-pipeline { display: grid; grid-template-columns: repeat(7, minmax(90px, 1fr)); gap: 6px; margin-top: 10px; overflow-x: auto; }
.ar-page__history-stage { min-width: 90px; display: flex; align-items: center; gap: 6px; padding: 7px 8px; border-radius: 8px; background: rgba(var(--v-theme-success), .055); }
.ar-page__history-stage--failed { background: rgba(var(--v-theme-error), .07); }
.ar-page__history-stage strong, .ar-page__history-stage small { display: block; white-space: nowrap; }
.ar-page__history-stage strong { font-size: 11px; }
.ar-page__history-stage small { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .58); font-size: 10px; }
.ar-page__history-error { display: flex; align-items: flex-start; gap: 6px; margin-top: 9px; padding: 7px 9px; border-radius: 8px; color: rgb(var(--v-theme-error)); background: rgba(var(--v-theme-error), .065); font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; }
.ar-page__history-error--ok { color: rgba(var(--v-theme-on-surface), .62); background: rgba(var(--v-theme-on-surface), .035); }
.ar-page__history-footer { margin-top: 6px; }
.ar-page__history-footer > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ar-page__history-details { display: grid; gap: 6px; margin-top: 7px; padding-top: 8px; border-top: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .62)); font-size: 11px; }
.ar-page__history-details > div { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px; }
.ar-page__history-details > div > span:first-child { color: rgba(var(--v-theme-on-surface), .55); }
.ar-page__history-details code { overflow-wrap: anywhere; white-space: normal; }
.ar-page__history-call-row { align-items: start; }
.ar-page__history-agent-calls { display: grid; gap: 6px; }
.ar-page__history-agent-call { min-width: 0; padding: 7px 8px; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .58)); border-radius: 8px; background: rgba(var(--v-theme-success), .035); line-height: 1.45; overflow-wrap: anywhere; }
.ar-page__history-agent-call--failed { background: rgba(var(--v-theme-error), .045); }
.ar-page__history-agent-head { display: flex; justify-content: space-between; gap: 8px; }
.ar-page__history-agent-head span, .ar-page__history-agent-call small { color: rgba(var(--v-theme-on-surface), .58); }
.ar-page__history-agent-call small { display: block; margin-top: 2px; }
.ar-page__history-agent-error { color: rgb(var(--v-theme-error)) !important; }
.ar-page__board-history-list { display: flex; flex-direction: column; gap: 10px; }
.ar-page__board-history-item { padding: 12px 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; background: transparent; }
.ar-page__board-history-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ar-page__board-history-summary { display: flex; align-items: center; gap: 10px; margin-top: 7px; color: rgba(var(--v-theme-on-surface), .6); font-size: 11px; }
.ar-page__board-history-summary > span:nth-child(2) { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ar-page__board-history-summary .v-btn { margin-left: auto; }
.ar-page__board-history-metrics { display: flex; flex-wrap: wrap; gap: 5px 12px; margin-top: 7px; color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; line-height: 1.45; }
.ar-page__board-history-metrics span { overflow-wrap: anywhere; }
.ar-page__board-history-detail { display: grid; gap: 7px; margin-top: 8px; padding-top: 9px; border-top: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .62)); }
.ar-page__board-history-rank { display: grid; grid-template-columns: 30px 44px minmax(0, 1fr); gap: 9px; align-items: center; min-width: 0; padding: 7px 8px; border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .68)); border-radius: 8px; background: transparent; }
.ar-page__poster--history { width: 44px; height: 66px; }
.ar-page__board-history-copy { min-width: 0; }
.ar-page__board-history-copy .ar-page__title-row { flex-wrap: wrap; }
.ar-page__board-history-copy .ar-page__media-title { font-size: 13px; }
.ar-page__board-history-copy .ar-page__rank-copy { margin-top: 4px; }
@media (max-width: 900px) {
  .ar-page__summary-bar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ar-page__progress { grid-column: 1 / 3; }
  .ar-page__runtime-chip { grid-column: 3; justify-self: end; margin-top: -2px; }
  .ar-page__rank-item { grid-template-columns: 34px 60px minmax(0, 1fr); }
  .ar-page__poster { width: 60px; height: 90px; }
  .ar-page__rank-actions { grid-column: 2 / -1; justify-content: flex-end; }
  .ar-page__profile-body { grid-template-columns: 1fr; }
  .ar-page__profile-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ar-page__profile-group--archived { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .ar-page { width: min(100%, calc(100vw - 12px)); height: min(880px, calc(100dvh - 12px)); }
  .ar-page.ar-page--app { height: calc(100dvh - var(--layout-navbar-block-size, 4rem) - 5rem); }
  .ar-page__toolbar :deep(.v-toolbar__content) { height: auto !important; min-height: 66px; flex-wrap: wrap; overflow: visible; padding-block: 6px; }
  .ar-page__toolbar :deep(.v-spacer) { display: none; }
  .ar-page__brand { order: 1; }
  .ar-page__heading { order: 1; flex: 1 1 180px; }
  .ar-page__toolbar :deep(.v-btn--icon) { order: 2; }
  .ar-page__critic-badge { order: 2; }
  .ar-page__pending-badge { order: 2; }
  .ar-page__identity { order: 3; width: calc(100% - 24px); margin: 6px 12px; }
  .ar-page__summary-bar { min-height: 60px; gap: 4px; padding: 8px 10px; }
  .ar-page__stat { gap: 6px; padding-inline: 6px; }
  .ar-page__stat :deep(.v-icon) { display: none; }
  .ar-page__progress { grid-column: 1 / -1; margin-top: 2px; }
  .ar-page__runtime-chip { display: none; }
  .ar-page__tabs { min-height: 40px; overflow-x: auto; }
  .ar-page__tab-list { width: max-content; min-width: max-content; flex-wrap: nowrap; gap: 4px; padding: 6px 10px !important; }
  .ar-page__tab { flex: 0 0 auto; min-width: 112px; min-height: 40px; padding-inline: 10px; }
  .ar-page__content { padding: 12px 10px; }
  .ar-page__section-head { min-height: 42px; }
  .ar-page__rank-item { grid-template-columns: 30px 54px minmax(0, 1fr); gap: 8px; padding: 9px; }
  .ar-page__poster { width: 54px; height: 81px; }
  .ar-page__rank { width: 28px; height: 28px; }
  .ar-page__rank-actions { grid-column: 1 / -1; justify-content: flex-end; padding-top: 2px; border-top: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .55)); }
  .ar-page__rank-copy { grid-template-columns: 34px minmax(0, 1fr); }
  .ar-page__copy-text,
  .ar-page__copy-text--reason,
  .ar-page__copy-text--intro { display: block; overflow: visible; -webkit-line-clamp: initial; }
  .ar-page__profile-head :deep(.v-card-item__append) { align-self: flex-start; }
  .ar-page__profile-body { padding: 12px; }
  .ar-page__profile-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ar-page__profile-metric { justify-content: center; padding: 9px 6px; }
  .ar-page__profile-metric :deep(.v-icon) { display: none; }
  .ar-page__profile-groups { grid-template-columns: 1fr; }
  .ar-page__profile-group--archived { grid-column: auto; }
  .ar-page__history-item { padding: 10px; }
  .ar-page__history-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ar-page__history-metrics > div:nth-child(2) { border-right: 0; }
  .ar-page__history-metrics > div:nth-child(-n + 2) { border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .58)); }
  .ar-page__history-pipeline { grid-template-columns: repeat(7, minmax(105px, 1fr)); }
  .ar-page__history-footer { align-items: flex-start; }
  .ar-page__board-history-item { padding: 10px; }
  .ar-page__board-history-head { align-items: flex-start; }
  .ar-page__board-history-summary { align-items: flex-start; }
  .ar-page__health-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 390px) {
  .ar-page { width: 100%; height: calc(100dvh - 4px); border-radius: 10px; }
  .ar-page__brand { display: none; }
  .ar-page__heading { flex: 1 1 100%; margin-left: 10px; }
  .ar-page__title { font-size: 1rem; }
  .ar-page__subtitle { display: none; }
  .ar-page__summary-bar { grid-template-columns: repeat(3, 1fr); }
  .ar-page__stat { justify-content: center; text-align: center; }
  .ar-page__stat:last-of-type { border-right: none; }
  .ar-page__content { padding: 10px 8px; }
  .ar-page__rank-item { grid-template-columns: 26px 48px minmax(0, 1fr); gap: 7px; padding-inline: 7px; }
  .ar-page__poster { width: 48px; height: 72px; }
  .ar-page__rank-copy { grid-template-columns: 32px minmax(0, 1fr); }
  .ar-page__profile-head :deep(.v-card-item__prepend) { display: none; }
}
</style>
