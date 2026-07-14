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
  'idle',
  'running',
  'success',
  'sample_insufficient',
  'candidate_insufficient',
  'recommendation_incomplete',
  'agent_failed',
  'validation_failed',
  'subscription_partial_failed',
]

const weights = {
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

const config = {
  enabled: true,
  schedule_enabled: true,
  cron: '0 8 * * *',
  users: ['alice', 'bob'],
  default_user: 'alice',
  discovery_sources: { douban: true, tmdb_movies: true, tmdb_tv: true, bangumi: true, extensions: true },
  weights,
  media_types: ['movie', 'tv', 'anime'],
  profile_scope: 'all',
  recent_days: 365,
  subscription_sample_limit: 200,
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
  agent_prompt: '请综合用户订阅画像、榜单权重与候选特征排序，优先推荐真正贴合用户口味、同时兼顾质量、新鲜感与题材多样性的作品。推荐理由和作品简介要轻松诙谐、机灵自然，避免套话、低俗表达与剧透。',
}

const recommendations = Array.from({ length: 10 }, (_, index) => ({
  candidate_id: `candidate-${index + 1}`,
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
  reason: '脑洞与口碑齐飞起啦',
  summary: '精准贴合画像偏好',
  match_tags: index % 3 ? ['科幻', '悬疑', '成长'] : [],
  confidence: 96 - index * 3,
}))

const profile = {
  run_id: 'preview-run',
  generated_at: '2026-07-12T10:20:30+08:00',
  summary: '偏爱科幻、悬疑与人物成长，也会关注高口碑的新作。',
  tags: ['科幻', '悬疑', '成长', '高口碑'],
  subscription_count: 36,
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
  run_id: `run-${index}`,
  status: index ? 'success' : status.value,
  finished_at: `2026-07-${String(12 - Math.min(index, 9)).padStart(2, '0')}T08:00:00+08:00`,
  metrics: { candidate_count: 100, final_count: 10, agent_calls: 1, subscription_success_count: 0 },
  errors: [],
}))

function dataFor(path) {
  if (path.endsWith('config/options')) return { users: ['alice', 'bob'], available_users: ['alice', 'bob'], default_user: 'alice', config }
  if (path.endsWith('status')) return { state: 'ready', validation_errors: [] }
  if (path.endsWith('overview')) return { archive, latest_run: history[0] }
  if (path.endsWith('board')) {
    const visible = status.value === 'idle'
      ? []
      : status.value === 'recommendation_incomplete'
        ? recommendations.slice(0, 7)
        : recommendations
    return { status: status.value, generated_at: '2026-07-12T10:20:30+08:00', recommendations: visible }
  }
  if (path.endsWith('profile')) return profile
  if (path.endsWith('run-history')) return { items: history.slice(0, 10), total: history.length, page: 1, page_size: 10 }
  return {}
}

const api = {
  async get(path) { return { data: { success: true, data: dataFor(path) } } },
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
