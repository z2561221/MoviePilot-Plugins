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

const config = {
  enabled: true,
  discovery_page_enabled: true,
  schedule_enabled: true,
  cron: '5 18 * * *',
  emby_identities: identities,
  default_profile_id: identities[0].profile_id,
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
  profile_cache_enabled: true,
  rebuild_profile_each_run: false,
  playback_enabled: true,
  playback_recent_days: 90,
  playback_completion_threshold: 0.85,
  playback_abandon_minutes: 20,
  playback_cache_days: 7,
  agent_prompt: '以用户真实播放记录和明确偏好为首要依据，可从情绪体验、认知满足、叙事投入、熟悉与新奇的平衡、节奏与完成感五类观看动机辅助排序。稳定动机必须有至少两条独立播放证据或一项人工明确偏好，且只能作为软排序信号。',
}

const recommendations = Array.from({ length: 10 }, (_, index) => ({
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
}))

const profile = {
  profile_id: identities[0].profile_id,
  username: identities[0].username,
  run_id: 'preview-run',
  generated_at: '2026-07-12T10:20:30+08:00',
  summary: '偏爱科幻、悬疑与人物成长，也会关注高口碑的新作。',
  tags: ['科幻', '悬疑', '成长', '高口碑'],
  negative_tags: ['套路化续作'],
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
    final_count: 10,
    agent_calls: 2,
    subscription_success_count: 0,
    stage_status: { probe: 'ready', playback_snapshot: 'ready', profile: 'generated', candidate: 'ready', ranking: 'success', save: 'saved' },
    stage_ms: { probe: 24, playback_snapshot: 318, profile: 1260, candidate: 842, ranking: 965, save: 18 },
    candidate_source_counts: { douban: 18, tmdb_movies: 14, tmdb_tv: 12, bangumi: 6 },
    candidate_exclusion_counts: { watched: 7, library: 3, subscribed: 2, archived: 1 },
    source_errors: {},
  },
  errors: [],
}))

function dataFor(path, params = {}) {
  const identity = identities.find(item => item.profile_id === params.profile_id) || identities[0]
  const playback = { profile_id: identity.profile_id, username: identity.username, source: 'playback_reporting', confidence: 'high', status: 'ready', sample_count: 36, mapped_count: 36, unmapped_count: 4, synced_at: '2026-07-12T10:18:00+08:00', message: 'Playback Reporting 已同步' }
  const enablement = { requested: true, allowed: true, status: 'ready', message: 'Playback Reporting 已就绪', capabilities: {} }
  if (path.endsWith('config/options')) return { emby_identities: identities, default_profile_id: identities[0].profile_id, config, defaults: config, enablement, playback_status: { [identities[0].profile_id]: playback } }
  if (path.endsWith('status')) return { state: 'ready', validation_errors: [], default_profile_id: identities[0].profile_id, playback, enablement }
  if (path.endsWith('overview')) {
    const visible = status.value === 'idle'
      ? []
      : status.value === 'recommendation_incomplete'
        ? recommendations.slice(0, 7)
        : recommendations
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
      board: { profile_id: identity.profile_id, username: identity.username, status: status.value, generated_at: '2026-07-12T10:20:30+08:00', recommendations: visible },
    }
  }
  if (path.endsWith('board')) {
    const visible = status.value === 'idle'
      ? []
      : status.value === 'recommendation_incomplete'
        ? recommendations.slice(0, 7)
        : recommendations
    return { status: status.value, generated_at: '2026-07-12T10:20:30+08:00', recommendations: visible }
  }
  if (path.endsWith('profile')) return profile
  if (path.endsWith('run-history')) return { items: history.slice(0, 10).map(item => ({ ...item, profile_id: identity.profile_id, username: identity.username })), total: history.length, page: 1, page_size: 10 }
  return {}
}

const api = {
  async get(path, request = {}) { return { data: { success: true, data: dataFor(path, request.params || {}) } } },
  async post(path) {
    if (path.endsWith('refresh')) status.value = 'success'
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
