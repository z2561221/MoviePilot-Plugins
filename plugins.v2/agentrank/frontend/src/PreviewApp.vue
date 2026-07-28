<script setup>
import { computed, ref } from 'vue'
import AppPage from './components/AppPage.vue'
import Config from './components/Config.vue'
import Dashboard from './components/Dashboard.vue'
import Page from './components/Page.vue'

const query = new URLSearchParams(window.location.search)
const view = ref(query.get('view') || 'app')
const status = ref(query.get('status') || 'success')

const views = [
  { title: '推荐中心', value: 'app' },
  { title: '详情页面', value: 'page' },
  { title: '配置页面', value: 'config' },
  { title: '仪表板', value: 'dashboard' },
]
const statuses = [
  { title: '待加载', value: 'idle' },
  { title: '运行中', value: 'running' },
  { title: '已完成', value: 'success' },
  { title: '播放样本不足', value: 'sample_insufficient' },
  { title: '候选数量不足', value: 'candidate_insufficient' },
  { title: '推荐榜单不足', value: 'recommendation_incomplete' },
  { title: '画像输出校验失败', value: 'profile_validation_failed' },
  { title: 'Agent 调用失败', value: 'agent_failed' },
  { title: '输出校验失败', value: 'validation_failed' },
  { title: '部分订阅失败', value: 'subscription_partial_failed' },
]

const weights = {
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

const identities = [
  { server_name: 'home', user_id: 'user-alice', username: 'Alice', profile_id: 'emby:home:user-alice', schema_version: 1 },
  { server_name: 'remote', user_id: 'user-bob', username: 'Bob', profile_id: 'emby:remote:user-bob', schema_version: 1 },
]
const moviePilotUsers = [
  { id: 1, name: 'admin', is_active: true, is_superuser: true },
  { id: 7, name: 'preview_user', is_active: true, is_superuser: false },
]

const config = {
  enabled: true,
  discovery_page_enabled: true,
  schedule_enabled: true,
  cron: '5 18 * * *',
  emby_identities: identities,
  default_profile_id: identities[0].profile_id,
  profile_access_map: { 7: [identities[0].profile_id] },
  discovery_sources: { douban: true, tmdb_movies: true, tmdb_tv: true, bangumi: true, anilist: true },
  weights,
  media_types: ['movie', 'tv', 'anime'],
  minimum_samples: 5,
  candidate_pool_size: 100,
  confidence_threshold: 0.6,
  exclude_keywords: [],
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
  profile_prompt: '基于用户真实播放记录和明确偏好，归纳稳定的内容偏好与观看动机；单一样本不得形成稳定结论。',
  ranking_prompt: '优先选择有多项具体匹配证据且能补充片单的新作品，兼顾相关性、新鲜感与题材多样性。',
  copy_prompt: '推荐理由和作品简介使用自然、具体、克制且语义完整的短句。',
  critic_prompt: '先复述可核对的内容偏好，再区分已确认事实、当前推测和仍待确认的信息。',
}

const candidatePool = Array.from({ length: 8 }, (_, index) => ({
  candidate_id: `tmdb:${index % 3 === 0 ? 'movie' : 'tv'}:${1000 + index}`,
  rank: index + 1,
  title: index === 0
    ? '这是一部用于验证超长标题在三种视口下都不会挤出主要操作按钮的电影名称'
    : `未来道具研究所推荐样本 ${index + 1}`,
  year: 2026 - (index % 6),
  media_type: ['movie', 'tv', 'anime'][index % 3],
  sources: index % 2 ? [] : ['douban', 'tmdb'],
  source_ids: {
    tmdb: String(1000 + index),
    ...(index % 3 === 2 ? { bangumi: String(2000 + index) } : { douban: String(3000 + index) }),
  },
  poster_path: '',
  reason: index === 0
    ? '你最近看完了多部悬疑科幻短剧，这部同样采用封闭空间调查、多线追凶和高密度反转，但人物成长更扎实，适合作为下一部。'
    : '结合近期播放和高频偏好标签，题材、叙事节奏与口碑均接近你持续关注的作品。',
  summary: index === 0
    ? '一群研究员在封闭实验设施中调查异常信号，却发现每一次修正都会创造新的记忆分歧。他们必须在真相、同伴和原本的世界之间作出选择。'
    : '围绕一场意外展开的群像故事，在紧凑悬念中兼顾人物成长与情感关系。',
  match_tags: index % 3 ? ['科幻', '悬疑', '成长'] : [],
  confidence: 96 - index * 3,
  support: { percentage: 94 - index * 4 },
  analysis_id: `analysis-preview-${index + 1}`,
  feedback_kind: index === 0 ? 'like' : index === 1 ? 'dislike' : '',
}))
const boardRecommendations = ref(candidatePool.slice(0, 5).map(item => ({ ...item })))
const boardRevision = ref(1)
const blockedCandidateIds = new Set()

const conversationMessages = ref([
  {
    message_id: 'preview-message-user', role: 'user', status: 'completed',
    content: '为什么把这部作品排在第一名？', created_at: '2026-07-12T10:25:00+08:00',
  },
  {
    message_id: 'preview-message-assistant', role: 'assistant', status: 'completed',
    content: '它同时匹配了你近期稳定出现的悬疑、科幻与紧凑叙事证据，同时保留了题材新鲜度。',
    created_at: '2026-07-12T10:25:03+08:00', provider: 'Agent Tokens', model: 'critic-preview',
  },
])
const conversationCommands = ref([{
  command_id: 'preview-command-1', status: 'pending_confirmation', title: '归档偏好标签',
  preview: '将“高口碑”从稳定偏好移入归档，后续不再用于排序。', requires_superuser: false,
}])
const pendingItems = ref([
  {
    item_type: 'proposal', item_id: 'preview-proposal-1', title: '确认专属影评师的新理解',
    summary: '你更重视悬疑作品的推理闭环，而不是单纯追求反转数量。',
    detail_lines: ['加强“推理闭环”偏好', '轻微削弱“高密度反转”偏好'],
    created_at: '2026-07-12T10:30:00+08:00', status: 'pending_confirmation', reminder_policy: 'unselected',
  },
  {
    item_type: 'question', item_id: 'preview-question-1', title: '专属影评师需要你确认',
    summary: '你不喜欢这部作品，主要是因为节奏还是人物塑造？',
    detail_lines: ['当前反馈不足以形成稳定负向偏好'],
    options: [{ option_id: 'pace', label: '节奏拖沓' }, { option_id: 'character', label: '人物单薄' }],
    allow_custom_answer: true, created_at: '2026-07-12T10:31:00+08:00', status: 'pending', reminder_policy: 'unselected',
  },
  {
    item_type: 'command', item_id: 'preview-command-1', title: '归档偏好标签',
    summary: '将“高口碑”从稳定偏好移入归档，后续不再用于排序。',
    created_at: '2026-07-12T10:32:00+08:00', status: 'pending_confirmation', reminder_policy: 'unselected',
  },
])

function previewAnalysis(params = {}) {
  const item = candidatePool.find(value => value.candidate_id === params.candidate_id) || candidatePool[0]
  return {
    analysis_id: item.analysis_id,
    candidate_id: item.candidate_id,
    summary: item.summary,
    reason: item.reason,
    positive_evidence: [
      { direction: 'positive', dimension: 'theme', user_value: '近期多次看完悬疑科幻', candidate_value: '封闭空间调查与科幻设定', user_refs: ['playback:1', 'playback:2'], contribution_units: 34 },
      { direction: 'positive', dimension: 'freshness', user_value: '片单需要补充新作品', candidate_value: '未观看且与旧片单不重复', user_refs: ['library:1'], contribution_units: 18 },
    ],
    counter_evidence: [
      { direction: 'negative', dimension: 'year', user_value: '近期偏好成熟完结作', candidate_value: '新作信息仍有限', user_refs: ['playback:3'], contribution_units: -8 },
    ],
    uncertainties: ['尚无该导演作品的直接播放证据'],
    support_percentage: item.support.percentage,
    selection_source: 'agent', policy_version: 'policy-preview-1', memory_revision: 7,
  }
}

function previewConversation(identity) {
  return {
    thread: { thread_id: 'preview-thread', profile_id: identity.profile_id, revision: 3, status: 'active' },
    messages: conversationMessages.value,
    commands: conversationCommands.value,
  }
}

function previewPending(identity) {
  const counts = { proposal: 0, question: 0, command: 0 }
  pendingItems.value.forEach(item => { counts[item.item_type] += 1 })
  return { profile_id: identity.profile_id, items: pendingItems.value, counts, total: pendingItems.value.length }
}

const profile = {
  profile_id: identities[0].profile_id,
  username: identities[0].username,
  run_id: 'preview-run',
  generated_at: '2026-07-12T10:20:30+08:00',
  summary: '偏爱科幻、悬疑与人物成长，也会关注高口碑的新作。',
  tags: ['科幻', '悬疑', '成长', '高口碑'],
  negative_tags: ['套路化续作'],
  archived_profile_tags: [],
  playback_count: 36,
  filters: { genres: ['科幻', '悬疑'], languages: ['zh', 'en'], release_year_min: 2018 },
  ranking_tags: ['封闭空间', '群像成长'],
  retrieval_resolution_version: 1,
  schema_version: 4,
}
const archive = {
  entries: [{
    candidate_id: 'archived-1',
    original_rank: 4,
    archived_at: '2026-07-11T09:00:00+08:00',
    recommendation: { title: '已忽略的归档样本' },
  }],
}
const history = Array.from({ length: 12 }, (_, index) => ({
  profile_id: identities[0].profile_id,
  username: identities[0].username,
  run_id: `run-${index}`,
  status: index ? 'success' : status.value,
  finished_at: `2026-07-${String(12 - Math.min(index, 9)).padStart(2, '0')}T08:00:00+08:00`,
  metrics: {
    candidate_count: 50,
    final_count: 5,
    agent_calls: 2,
    agent_model: 'anthropic/claude-sonnet-4-5-20250929-thinking',
    model_call_count: 4,
    subscription_success_count: 0,
    stage_status: { probe: 'ready', playback_snapshot: 'ready', profile: 'generated', candidate: 'ready', ranking: 'success', save: 'saved' },
    stage_ms: { probe: 24, playback_snapshot: 318, profile: 1260, candidate: 842, ranking: 965, save: 18 },
    candidate_source_counts: { douban: 18, tmdb_movies: 14, tmdb_tv: 12, bangumi: 6 },
    candidate_exclusion_counts: { watched: 7, library: 3, subscribed: 2, disliked: 1, archived: 1 },
    source_errors: {},
  },
  errors: [],
}))

function dataFor(path, params = {}) {
  const identity = identities.find(item => item.profile_id === params.profile_id) || identities[0]
  const playback = { profile_id: identity.profile_id, username: identity.username, source: 'playback_reporting', confidence: 'high', status: 'ready', sample_count: 36, mapped_count: 36, unmapped_count: 4, synced_at: '2026-07-12T10:18:00+08:00', message: 'Playback Reporting 已同步' }
  const enablement = { requested: true, allowed: true, status: 'ready', message: 'Playback Reporting 已就绪', capabilities: {} }
  if (path === 'user/' || path.endsWith('/user/')) return moviePilotUsers
  if (path.endsWith('config/options')) return { emby_identities: identities, default_profile_id: identities[0].profile_id, config, defaults: config, enablement, playback_status: { [identities[0].profile_id]: playback } }
  if (path.endsWith('status')) return { state: 'ready', validation_errors: [], default_profile_id: identities[0].profile_id, playback, enablement }
  if (path.endsWith('overview')) {
    const visible = status.value === 'idle'
      ? []
      : status.value === 'recommendation_incomplete'
        ? boardRecommendations.value.slice(0, 4)
        : boardRecommendations.value
    return {
      profile_id: identity.profile_id,
      username: identity.username,
      archive,
      latest_run: history[0],
      history: history.slice(0, 10).map(item => ({ ...item, profile_id: identity.profile_id, username: identity.username })),
      history_total: history.length,
      profile: { ...profile, profile_id: identity.profile_id, username: identity.username },
      playback,
      enablement,
      board: { profile_id: identity.profile_id, username: identity.username, run_id: 'preview-run', revision: boardRevision.value, status: status.value, generated_at: '2026-07-12T10:20:30+08:00', recommendations: visible },
    }
  }
  if (path.endsWith('board')) {
    const visible = status.value === 'idle'
      ? []
      : status.value === 'recommendation_incomplete'
        ? boardRecommendations.value.slice(0, 4)
        : boardRecommendations.value
    return { run_id: 'preview-run', revision: boardRevision.value, status: status.value, generated_at: '2026-07-12T10:20:30+08:00', recommendations: visible }
  }
  if (path.endsWith('profile')) return profile
  if (path.endsWith('run-history')) return { items: history.slice(0, 10).map(item => ({ ...item, profile_id: identity.profile_id, username: identity.username })), total: history.length, page: 1, page_size: 10 }
  if (path.endsWith('analysis')) return previewAnalysis(params)
  if (path.endsWith('conversation')) return previewConversation(identity)
  if (path.endsWith('pending')) return previewPending(identity)
  if (path.endsWith('data/export')) return {
    schema_version: 1,
    exported_at: new Date().toISOString(),
    profile_id: identity.profile_id,
    retention_policy: {
      candidate_snapshot_limit: 20,
      feedback_event_limit: 1000,
      feedback_queue_limit: 200,
      conversation_message_limit: 200,
      attribution_record_limit: 500,
      analysis_record_limit: 500,
    },
    profile,
  }
  return {}
}

function previewFeedback(kind, candidateId) {
  if (kind === 'like') {
    const target = boardRecommendations.value.find(item => item.candidate_id === candidateId)
    if (target) target.feedback_kind = 'like'
    return { changed: false, board_changed: false, event: { kind }, board_revision: boardRevision.value, message: '已记录喜欢' }
  }
  blockedCandidateIds.add(candidateId)
  const remaining = boardRecommendations.value.filter(item => item.candidate_id !== candidateId)
  const remainingIds = new Set(remaining.map(item => item.candidate_id))
  const replacement = candidatePool.find(item => !blockedCandidateIds.has(item.candidate_id) && !remainingIds.has(item.candidate_id))
  if (replacement) remaining.push({ ...replacement, feedback_kind: '' })
  remaining.forEach((item, index) => { item.rank = index + 1 })
  boardRecommendations.value = remaining.slice(0, 5)
  boardRevision.value += 1
  const complete = boardRecommendations.value.length === 5
  return {
    changed: true,
    board_changed: true,
    event: { kind },
    board_revision: boardRevision.value,
    current_count: boardRecommendations.value.length,
    refill_count: replacement ? 1 : 0,
    refill_status: complete ? 'filled' : 'safe_candidate_insufficient',
    message: complete ? `${kind === 'ignore' ? '忽略' : '不喜欢'}已生效，并从本轮冻结安全候选池补位` : '安全候选不足',
  }
}

const api = {
  async get(path, request = {}) { return { data: { success: true, data: dataFor(path, request.params || {}) } } },
  async post(path, payload = {}) {
    if (path.endsWith('refresh')) status.value = 'success'
    if (path.endsWith('feedback')) return { data: { success: true, data: previewFeedback(payload.kind, payload.candidate_id) } }
    if (path.endsWith('archive')) return { data: { success: true, data: previewFeedback('ignore', payload.candidate_id) } }
    if (path.endsWith('analysis/comment')) return { data: { success: true, data: { changed: true, message: '评论已进入异步理解队列' } } }
    if (path.endsWith('conversation/messages')) {
      const now = new Date().toISOString()
      conversationMessages.value.push({ message_id: `preview-user-${Date.now()}`, role: 'user', status: 'completed', content: payload.content, created_at: now })
      conversationMessages.value.push({ message_id: `preview-agent-${Date.now()}`, role: 'assistant', status: 'completed', content: '我会把这条纠正作为新证据理解；涉及长期画像的变化会先交给你确认。', created_at: now, provider: 'Agent Tokens', model: 'critic-preview' })
      return { data: { success: true, data: previewConversation(identities[0]) } }
    }
    if (path.endsWith('conversation/messages/retry')) return { data: { success: true, data: previewConversation(identities[0]) } }
    if (path.endsWith('conversation/commands/respond')) {
      conversationCommands.value = conversationCommands.value.map(item => item.command_id === payload.command_id ? { ...item, status: payload.action === 'confirm' ? 'completed' : 'rejected' } : item)
      pendingItems.value = pendingItems.value.filter(item => item.item_id !== payload.command_id)
      return { data: { success: true, data: { changed: true } } }
    }
    if (path.endsWith('pending/respond')) {
      if (!(payload.action === 'remind' && payload.reminder_policy !== 'never')) {
        pendingItems.value = pendingItems.value.filter(item => item.item_id !== payload.item_id)
      }
      return { data: { success: true, data: { changed: true } } }
    }
    if (path.endsWith('profile/tags')) {
      const tag = String(payload.tag || '').trim()
      const field = payload.kind === 'negative' ? 'negative_tags' : 'tags'
      const archivedKind = payload.kind === 'negative' ? 'negative' : 'positive'
      profile.archived_profile_tags ||= []
      if (payload.action === 'remove') {
        profile[field] = profile[field].filter(item => item !== tag)
        if (tag && !profile.archived_profile_tags.some(item => item.kind === archivedKind && item.tag === tag)) {
          profile.archived_profile_tags.push({ kind: archivedKind, tag, archived_at: new Date().toISOString() })
        }
      } else {
        if (tag && !profile[field].includes(tag)) profile[field].push(tag)
        profile.archived_profile_tags = profile.archived_profile_tags.filter(item => !(item.kind === archivedKind && item.tag === tag))
      }
      return { data: { success: true, data: { changed: true } } }
    }
    if (path.endsWith('data/reset/full/prepare')) {
      return { data: { success: true, data: { confirmation_token: `preview-${Date.now()}`, expires_at: new Date(Date.now() + 300000).toISOString() } } }
    }
    if (path.endsWith('data/reset/learning')) return { data: { success: true, data: { reset: 'learning' } } }
    if (path.endsWith('data/reset/full')) return { data: { success: true, data: { reset: 'full' } } }
    return { data: { success: true, data: { changed: true, message: '预览操作已完成' } } }
  },
  async put() { return { data: { success: true } } },
}

const activeComponent = computed(() => ({ app: AppPage, page: Page, config: Config, dashboard: Dashboard }[view.value]))
const componentProps = computed(() => view.value === 'config'
  ? { api, initialConfig: config }
  : view.value === 'dashboard'
    ? { api, config }
    : { api })
</script>

<template>
  <VApp>
    <VMain class="preview-main">
      <div class="preview-controls" aria-label="验收夹具控制器">
        <VSelect v-model="view" :items="views" label="页面" density="compact" variant="outlined" hide-details />
        <VSelect v-model="status" :items="statuses" label="状态" density="compact" variant="outlined" hide-details />
      </div>
      <div class="preview-stage">
        <component :is="activeComponent" :key="`${view}-${status}`" v-bind="componentProps" />
      </div>
    </VMain>
  </VApp>
</template>

<style>
html, body, #preview { min-height: 100%; margin: 0; overflow-x: hidden; }
.preview-main { min-height: 100dvh; background: rgb(var(--v-theme-background)); }
.preview-controls { position: sticky; top: 0; z-index: 100; display: grid; grid-template-columns: repeat(2, minmax(0, 180px)); justify-content: center; gap: 8px; padding: 8px; background: rgba(var(--v-theme-surface), .96); border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.preview-stage { display: flex; justify-content: center; min-width: 0; padding: 8px; }
@media (max-width: 390px) {
  .preview-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 6px; }
  .preview-stage { padding: 2px; }
}
</style>
