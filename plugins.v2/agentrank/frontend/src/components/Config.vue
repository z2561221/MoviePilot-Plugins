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
  schedule_enabled: false,
  cron: '0 8 * * *',
  users: [],
  default_user: '',
  discovery_sources: {
    douban: true,
    tmdb_movies: true,
    tmdb_tv: true,
    bangumi: true,
  },
  weights: { ...weightDefaults },
  media_types: ['movie', 'tv', 'anime'],
  profile_scope: 'all',
  recent_days: 365,
  subscription_sample_limit: 200,
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
  agent_prompt: '请综合用户订阅画像、榜单权重与候选特征排序，优先推荐真正贴合用户口味、同时兼顾质量、新鲜感与题材多样性的作品。推荐理由和作品简介要轻松诙谐、机灵自然，避免套话、低俗表达与剧透。',
}

const form = reactive(structuredClone(defaults))
const activeMain = ref('overview')
const activeAdvanced = ref('runtime')
const loading = ref(false)
const status = ref({ state: 'stopped', validation_errors: [] })
const availableUsers = ref([])
const loadError = ref('')
const runtimeDefaults = ref(structuredClone(defaults))
const clearProfileSwitch = ref(false)
const clearProfileDialog = ref(false)
const clearProfileLoading = ref(false)
const actionFeedback = reactive({ show: false, message: '', color: 'success' })

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看推荐链路、运行状态和失败兜底。' },
  { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant', desc: '配置参与用户、默认用户和运行周期。' },
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

const sourceDefs = [
  { key: 'douban', title: '豆瓣发现', subtitle: '热门电影、剧集与动画', icon: 'mdi-alpha-d-circle-outline' },
  { key: 'tmdb_movies', title: 'TMDB电影', subtitle: '高热度电影候选', icon: 'mdi-movie-open-star-outline' },
  { key: 'tmdb_tv', title: 'TMDB剧集', subtitle: '高热度剧集候选', icon: 'mdi-television-classic' },
  { key: 'bangumi', title: 'Bangumi', subtitle: '动画与番剧候选', icon: 'mdi-animation-outline' },
]

const mediaTypeOptions = [
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
  { title: '动漫', value: 'anime' },
]
const actionOptions = [
  { title: '仅更新榜单', value: 'update' },
  { title: '通知确认', value: 'notify' },
  { title: '自动订阅前 N', value: 'auto_subscribe' },
]
const advancedTabs = [
  { key: 'runtime', title: '运行设置', icon: 'mdi-cog-outline' },
  { key: 'prompt', title: '提示设置', icon: 'mdi-text-box-edit-outline' },
]

const currentMain = computed(() => mainTabs.find(item => item.key === activeMain.value) || mainTabs[0])
const clearProfileUser = computed(() => form.default_user || form.users[0] || '')
const userOptions = computed(() => {
  const values = availableUsers.value.length ? availableUsers.value : form.users
  return values.map(name => ({ title: name, value: name }))
})

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

function applyConfig(value) {
  const next = cloneConfig(value)
  Object.assign(form, cloneConfig(defaults), next)
  form.weights = { ...weightDefaults, ...(next.weights || {}) }
  form.discovery_sources = Object.fromEntries(
    Object.keys(defaults.discovery_sources).map(key => [key, Boolean(next.discovery_sources?.[key] ?? defaults.discovery_sources[key])]),
  )
  form.users = Array.isArray(next.users) ? [...new Set(next.users.filter(Boolean))] : []
  form.media_types = Array.isArray(next.media_types) ? [...next.media_types] : [...defaults.media_types]
  form.exclude_keywords = Array.isArray(next.exclude_keywords) ? [...next.exclude_keywords] : []
}

watch(() => props.initialConfig, applyConfig, { immediate: true, deep: true })
watch(
  () => [...form.users],
  users => {
    if (!users.includes(form.default_user)) form.default_user = users[0] || ''
  },
)

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
    availableUsers.value = optionsData?.available_users || optionsData?.users || []
    runtimeDefaults.value = { ...structuredClone(defaults), ...(optionsData?.defaults || {}) }
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

function restoreAgentPrompt() {
  form.agent_prompt = runtimeDefaults.value.agent_prompt || defaults.agent_prompt
}

function requestClearProfile(value) {
  if (!value) return
  if (!clearProfileUser.value) {
    clearProfileSwitch.value = false
    actionFeedback.show = true
    actionFeedback.color = 'warning'
    actionFeedback.message = '请先选择默认用户'
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
    await postPluginApi(props.api, 'profile/clear', { username: clearProfileUser.value, confirm: true })
    actionFeedback.color = 'success'
    actionFeedback.message = `${clearProfileUser.value} 的画像与榜单已清除`
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
          <VSwitch v-model="form.enabled" color="success" hide-details inset label="启用插件" />
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
                <div v-for="(step, index) in ['读取用户订阅', '冻结发现候选', '受限Agent排序', '确定性安全校验', '更新榜单与动作']" :key="step" class="ar-config__step">
                  <VAvatar size="28" color="primary" variant="tonal">{{ index + 1 }}</VAvatar>
                  <span>{{ step }}</span>
                  <VIcon v-if="index < 4" icon="mdi-chevron-right" size="18" class="ar-config__step-arrow" />
                </div>
              </div>
              <div class="ar-config__overview-grid">
                <VCard variant="outlined" class="ar-config__overview-card">
                  <VCardText>
                    <div class="d-flex align-center justify-space-between mb-2">
                      <span class="text-subtitle-2">当前状态</span>
                      <VChip :color="status.state === 'ready' ? 'success' : 'warning'" variant="tonal" size="small">
                        {{ status.state === 'ready' ? '已就绪' : '未运行' }}
                      </VChip>
                    </div>
                    <div class="ar-config__hint">{{ form.enabled ? '插件已启用，等待手动或周期刷新。' : '启用并保存后才会生成榜单。' }}</div>
                  </VCardText>
                </VCard>
                <VCard variant="outlined" class="ar-config__overview-card">
                  <VCardText>
                    <div class="text-subtitle-2 mb-2">失败兜底</div>
                    <div class="ar-config__hint">Agent、候选或保存失败时保留旧画像与旧榜单，不执行订阅。</div>
                  </VCardText>
                </VCard>
              </div>
              <VAlert v-if="loadError" type="error" variant="tonal" class="mt-3">{{ loadError }}</VAlert>
              <VAlert v-if="status.validation_errors?.length" type="warning" variant="tonal" class="mt-3">
                <div v-for="item in status.validation_errors" :key="item">{{ item }}</div>
              </VAlert>
            </div>

            <div v-show="activeMain === 'basic'" class="ar-config__pane">
              <div class="ar-config__section-title">基础设置</div>
              <VRow>
                <VCol cols="12" md="7">
                  <VAutocomplete v-model="form.users" :items="userOptions" item-title="title" item-value="value" label="参与用户" multiple chips closable-chips density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="5">
                  <VSelect v-model="form.default_user" :items="form.users" label="默认用户" density="compact" variant="outlined" hide-details :disabled="!form.users.length" />
                </VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.schedule_enabled" color="success" label="周期运行" hide-details inset /></VCol>
                <VCol cols="12" md="8"><VCronField v-model="form.cron" label="运行周期" density="compact" variant="outlined" hide-details :disabled="!form.schedule_enabled" /></VCol>
              </VRow>
              <VAlert type="info" variant="tonal" class="mt-4">周期任务按参与用户顺序执行，单用户失败不会阻断后续用户。</VAlert>
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
                <VCol cols="12" md="6"><VSelect v-model="form.profile_scope" :items="[{ title: '全部订阅', value: 'all' }, { title: '近期订阅', value: 'recent' }]" label="画像范围" density="compact" variant="outlined" hide-details /></VCol>
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
                <VCol cols="12" md="3"><VTextField v-model.number="form.auto_subscribe_top_n" type="number" min="0" :max="form.auto_subscribe_limit" label="自动订阅前 N" density="compact" variant="outlined" hide-details :disabled="form.action_mode !== 'auto_subscribe'" /></VCol>
                <VCol cols="12" md="3"><VTextField v-model.number="form.auto_subscribe_limit" type="number" min="0" max="10" label="安全上限" density="compact" variant="outlined" hide-details /></VCol>
                <VCol cols="12"><VSwitch v-model="form.notify" color="info" label="发送通知" hide-details inset :disabled="form.action_mode === 'update'" /></VCol>
              </VRow>
              <VAlert :type="form.action_mode === 'auto_subscribe' ? 'warning' : 'info'" variant="tonal" class="mt-4">
                {{ form.action_mode === 'auto_subscribe' ? '自动订阅仍会逐项检查候选快照、归档、置信度、识别 ID 和重复订阅。' : '通知确认只发送摘要，用户仍需从榜单界面手动订阅。' }}
              </VAlert>
            </div>

            <div v-show="activeMain === 'advanced'" class="ar-config__pane">
              <template v-if="activeAdvanced === 'runtime'">
                <div class="ar-config__section-title">运行设置</div>
                <VRow>
                  <VCol cols="12" md="4"><VSwitch v-model="form.discovery_page_enabled" color="success" label="开启发现页" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.profile_cache_enabled" color="success" label="画像缓存" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VSwitch v-model="form.rebuild_profile_each_run" color="warning" label="每次重建" hide-details inset /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.subscription_sample_limit" type="number" min="1" max="1000" label="订阅样本上限" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.minimum_samples" type="number" min="1" max="100" label="最少样本" density="compact" variant="outlined" hide-details /></VCol>
                  <VCol cols="12" md="4"><VTextField v-model.number="form.history_limit" type="number" min="1" max="200" label="历史上限" density="compact" variant="outlined" hide-details /></VCol>
                </VRow>
                <VAlert type="info" variant="tonal" class="mt-4">画像缓存开启且关闭每次重建时，Agent 会参考上一版画像持续演进；每次重建开启或画像缓存关闭时，仅按当前订阅重新建立。</VAlert>
                <div class="ar-config__danger-row mt-4">
                  <div>
                    <div class="ar-config__danger-title">清除画像</div>
                    <div class="ar-config__hint">清除默认用户“{{ clearProfileUser || '未选择' }}”的画像与榜单，不影响 MoviePilot 订阅和归档。</div>
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
                <VAlert type="info" variant="tonal" class="mt-4">该提示词用于调整候选排序、画像措辞和文案风格；只读工具边界、JSON 输出协议及十字校验由插件固定保留。</VAlert>
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
          将清除“{{ clearProfileUser }}”的画像与当前榜单。MoviePilot 订阅、订阅任务、忽略归档和插件配置不会被删除。
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
.ar-config__pipeline { display: flex; align-items: center; gap: 8px; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; background: rgba(var(--v-theme-on-surface), .02); }
.ar-config__step { display: flex; align-items: center; gap: 8px; min-width: 0; font-size: 12px; font-weight: 500; }
.ar-config__step-arrow { color: rgba(var(--v-theme-on-surface), .35); }
.ar-config__overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.ar-config__overview-card, .ar-config__source-card { border-radius: 10px; }
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
  .ar-config__body { flex-direction: column; }
  .ar-config__nav { width: 100%; flex: 0 0 auto; border-right: 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .ar-config__nav::-webkit-scrollbar { display: none; }
  .ar-config__nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .ar-config__nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }
  .ar-config__subtabs { overflow-x: auto; }
  .ar-config__window--overview { overflow-y: auto; }
  .ar-config__pipeline { align-items: flex-start; flex-direction: column; }
  .ar-config__step-arrow { display: none; }
  .ar-config__overview-grid, .ar-config__source-grid, .ar-config__weight-grid { grid-template-columns: 1fr; }
  .ar-config__danger-row { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 390px) {
  .ar-config { width: 100%; padding: 2px; }
  .ar-config__header { padding-inline: 12px; }
  .ar-config__nav-item { min-width: 88px; }
  .ar-config__pane { padding: 12px; }
  .ar-config__actions { flex-wrap: wrap; padding-inline: 12px; }
}
@media (max-height: 760px) { .ar-config__window--overview { overflow-y: auto; } }
</style>
