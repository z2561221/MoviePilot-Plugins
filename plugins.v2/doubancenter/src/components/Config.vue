<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const form = reactive({})
const activeMain = ref('overview')
const activeSub = ref('overview')
const overview = ref(null)
const loadingOverview = ref(false)

const defaults = {
  enabled: false, cron: '0 8 * * *', notify: false, proxy: false, onlyonce: false,
  rsshub_domain: 'https://rsshub.ddsrem.com',
  rank_configs: {
    coming: { enabled: false, count: 10, wish_count: 5000, air_days: 7, vote: 0, year: 0 },
    tv_real_time: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    tv_chinese: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    tv_global: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    movie_weekly: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
    bangumi: { enabled: false, count: 10, wish_count: 0, air_days: 0, vote: 0, year: 0 },
  },
  region_filters: [], genre_filters: [], resolution_filters: [], custom_rss_addrs: '',
  folio_enabled: true, folio_private: true, folio_first: true, folio_notify: false,
  folio_user: '', folio_exclude: '', folio_cookie: '',
  folio_pc_month: 3, folio_pc_num: 50, folio_mobile_month: 2, folio_mobile_num: 15,
  dashboard_rank_keys: [],
  blacklist_keywords: '',
  observe_days: 0,
  observe_rank_keys: ['coming', 'tv_real_time'],
}

const regionOptions = ['中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国', '英国', '泰国', '印度', '法国', '德国', '西班牙', '加拿大', '澳大利亚', '俄罗斯', '瑞典', '丹麦', '爱尔兰', '意大利', '巴西']
const genreOptions = ['爱情', '喜剧', '剧情', '悬疑', '古装', '动作', '犯罪', '科幻', '家庭', '奇幻', '武侠', '历史', '动画', '惊悚', '战争', '冒险', '恐怖', '灾难', '传记', '音乐', '歌舞']
const resolutionOptions = [{ title: '2160p/4K', value: '2160p|4k|uhd' }, { title: '1080p', value: '1080p' }, { title: '720p', value: '720p' }]

const rankDefs = [
  { key: 'coming', name: '即将上映', route: '/douban/tv/coming', filters: ['wish_count', 'air_days'] },
  { key: 'tv_real_time', name: '实时热门', route: '/douban/list/tv_real_time_hotest', filters: ['vote', 'year'] },
  { key: 'tv_chinese', name: '华语口碑', route: '/douban/list/tv_chinese_best_weekly', filters: ['vote', 'year'] },
  { key: 'tv_global', name: '全球口碑', route: '/douban/list/tv_global_best_weekly', filters: ['vote', 'year'] },
  { key: 'movie_weekly', name: '电影口碑', route: '/douban/list/movie_weekly_best', filters: ['vote', 'year'] },
  { key: 'bangumi', name: 'BangumiTV', route: '/bangumi.tv/anime/followrank', filters: ['vote', 'year'] },
]

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '运行链路、模块状态和待关注事项。' },
  { key: 'rank', title: '榜单订阅', icon: 'mdi-trophy-outline', desc: '6 个内置榜单 + 自定义 RSS，统一订阅到豆瓣中心。' },
  { key: 'folio', title: '豆瓣时间', icon: 'mdi-book-clock-outline', desc: '追剧观影自动同步进度到豆瓣时间线。' },
  { key: 'dashboard', title: '仪表显示', icon: 'mdi-view-dashboard-outline', desc: '时间线 + 榜单排行双面板。' },
]

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  rank: [{ key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' }, { key: 'list', title: '榜单列表', icon: 'mdi-format-list-bulleted' }, { key: 'filter', title: '条件筛选', icon: 'mdi-filter-variant' }],
  folio: [{ key: 'sync', title: '同步设置', icon: 'mdi-sync' }],
  dashboard: [{ key: 'view', title: '仪表盘选择', icon: 'mdi-view-dashboard-outline' }],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const enabledRankCount = computed(() => rankDefs.filter(r => form.rank_configs?.[r.key]?.enabled).length)
const overviewCards = computed(() => {
  const cards = overview.value?.cards || {}
  return [
    {
      title: '榜单订阅',
      icon: 'mdi-rss',
      color: cards.rss?.enabled ? 'success' : 'warning',
      value: `${cards.rss?.enabled || 0}/${cards.rss?.total || rankDefs.length}`,
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

watch(() => props.initialConfig, val => {
  Object.keys(form).forEach(k => delete form[k])
  const m = {}
  Object.assign(m, defaults, JSON.parse(JSON.stringify(val || {})))
  for (const rd of rankDefs) {
    if (!m.rank_configs[rd.key]) m.rank_configs[rd.key] = { ...defaults.rank_configs[rd.key] }
  }
  Object.assign(form, m)
}, { immediate: true, deep: true })

function saveConfig() {
  emit('save', { ...form })
}

function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || ''
}

async function loadOverview() {
  loadingOverview.value = true
  try {
    const resp = await getPluginApi(props.api, 'overview')
    if (resp?.code === 0 || resp?.cards) overview.value = resp
  } catch (error) {
    console.error('加载豆瓣中心总览失败:', error)
  } finally {
    loadingOverview.value = false
  }
}

onMounted(loadOverview)
</script>

<template>
  <div class="dc-config">
    <VCard flat class="dc-card">
      <VCardItem class="dc-header">
        <template #prepend><VAvatar color="primary" variant="tonal" size="44" rounded="lg" class="dc-header-avatar"><VIcon icon="mdi-book-open-page-variant-outline" size="24" /></VAvatar></template>
        <VCardTitle class="text-h6 dc-header-title">豆瓣中心</VCardTitle>
        <VCardSubtitle class="text-caption dc-header-subtitle">{{ currentMain.desc }}</VCardSubtitle>
        <template #append><VSwitch v-model="form.enabled" color="success" hide-details inset class="dc-enable-switch" :label="form.enabled ? '已启用' : '已停用'" /></template>
      </VCardItem>
      <VDivider />
      <div class="dc-body">
        <nav class="dc-nav">
          <VList density="comfortable" nav class="py-2 dc-nav-list">
            <VListItem v-for="item in mainTabs" :key="item.key" :active="activeMain === item.key" color="primary" rounded="lg" class="dc-nav-item" @click="selectMain(item.key)">
              <template #prepend><VIcon :icon="item.icon" class="dc-nav-icon" /></template>
              <VListItemTitle class="dc-nav-title">{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="dc-content">
          <div class="dc-subtabs">
            <button v-for="sub in currentSubs" :key="sub.key" type="button" class="dc-subtab" :class="{ 'dc-subtab--active': activeSub === sub.key }" @click="activeSub = sub.key"><VIcon :icon="sub.icon" size="18" class="mr-1" />{{ sub.title }}</button>
          </div>
          <VDivider />
          <div class="dc-window" :class="{ 'dc-window--overview': activeMain === 'overview' }">
            <div v-show="activeSub === 'overview'" class="dc-pane dc-pane--overview">
              <div class="dc-overview-section mb-3">
                <div class="dc-section-title d-flex align-center">
                  <span>运行链路</span>
                  <VSpacer />
                  <VBtn size="x-small" variant="text" icon="mdi-refresh" :loading="loadingOverview" @click="loadOverview" />
                </div>
                <div class="dc-flow">
                  <div v-for="flow in (overview?.flows || [])" :key="flow.label" class="dc-flow-block">
                    <div class="dc-flow-label">{{ flow.label }}</div>
                    <div class="dc-flow-row">
                      <template v-for="(step, idx) in flow.steps" :key="`${flow.label}-${step}`">
                        <span>{{ step }}</span>
                        <VIcon v-if="idx < flow.steps.length - 1" icon="mdi-arrow-right" size="15" />
                      </template>
                    </div>
                  </div>
                </div>
              </div>

              <div class="dc-stat-grid mb-3">
                <div v-for="card in overviewCards" :key="card.title" class="dc-stat">
                  <div class="d-flex align-center ga-2 mb-1">
                    <VAvatar :color="card.color" variant="tonal" size="28" rounded="lg"><VIcon :icon="card.icon" size="17" /></VAvatar>
                    <div class="text-caption text-medium-emphasis">{{ card.title }}</div>
                  </div>
                  <div class="text-subtitle-1 font-weight-bold">{{ card.value }}</div>
                  <div class="text-caption text-medium-emphasis">{{ card.desc }}</div>
                </div>
              </div>

              <div class="dc-overview-grid">
                <div class="dc-overview-section">
                  <div class="dc-section-title">待关注</div>
                  <div class="dc-kv"><span>观察队列</span><strong>{{ overview?.attention?.pending_observations || 0 }}</strong></div>
                  <div class="dc-kv"><span>防刷日志</span><strong>{{ overview?.attention?.anti_cheat_logs || 0 }}</strong></div>
                  <div class="dc-kv"><span>黑名命中</span><strong>{{ overview?.attention?.blacklist_hits || 0 }}</strong></div>
                </div>
                <div class="dc-overview-section">
                  <div class="dc-section-title">治理概况</div>
                  <div class="dc-kv"><span>忽略条目</span><strong>{{ overview?.governance?.ignored_observations || 0 }}</strong></div>
                  <div class="dc-kv"><span>订阅记录</span><strong>{{ overview?.governance?.subscribe_records || 0 }}</strong></div>
                  <div class="dc-kv"><span>防刷日志</span><strong>{{ overview?.governance?.anti_cheat_logs || 0 }}</strong></div>
                </div>
              </div>
            </div>

            <div v-show="activeSub === 'basic'" class="dc-pane">
              <div class="dc-section-title">基础设置</div>
              <VRow>
                <VCol cols="12" md="4"><VSwitch v-model="form.onlyonce" color="warning" inset hide-details label="立即运行一次" /></VCol>
                <VCol cols="12" md="4"><VCronField v-model="form.cron" label="运行周期" density="compact" variant="outlined" hide-details /></VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12"><VTextField v-model="form.rsshub_domain" label="RSSHub 域名" density="compact" variant="outlined" hide-details hint="默认 https://rsshub.ddsrem.com，所有榜单共用" persistent-hint /></VCol>
              </VRow>
              <VAlert class="mt-3" type="info" variant="tonal" density="compact" text="订阅用户名统一为「豆瓣中心」。即将上映保留播出窗口、想看人数过滤逻辑。" />
            </div>

            <div v-show="activeSub === 'list'" class="dc-pane">
              <div class="dc-section-title">榜单列表 <span class="text-caption font-weight-regular text-medium-emphasis">（已启用 {{ enabledRankCount }}/{{ rankDefs.length }}）</span></div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-3" text="每个榜单独立控制，条件框之间是且的关系。即将上映保留特殊处理。" />
              <div class="dc-rank-list-1col">
                <div v-for="rd in rankDefs" :key="rd.key" class="dc-rank-card" :class="{ 'dc-rank-card--on': form.rank_configs[rd.key]?.enabled }">
                  <div class="dc-rank-card-header">
                    <VCheckbox v-model="form.rank_configs[rd.key].enabled" :label="rd.name" color="primary" hide-details density="compact" class="dc-rank-check" />
                  </div>
                  <div class="dc-rank-card-body">
                    <div class="dc-rank-field">
                      <span class="dc-rank-label">数量</span>
                      <VTextField v-model.number="form.rank_configs[rd.key].count" type="number" min="1" density="compact" variant="outlined" hide-details class="dc-rank-input" />
                    </div>
                    <div v-if="rd.filters.includes('wish_count')" class="dc-rank-field">
                      <span class="dc-rank-label">想看</span>
                      <VTextField v-model.number="form.rank_configs[rd.key].wish_count" type="number" density="compact" variant="outlined" hide-details class="dc-rank-input" />
                    </div>
                    <div v-if="rd.filters.includes('air_days')" class="dc-rank-field">
                      <span class="dc-rank-label">窗口</span>
                      <VTextField v-model.number="form.rank_configs[rd.key].air_days" type="number" density="compact" variant="outlined" hide-details class="dc-rank-input" />
                    </div>
                    <div v-if="rd.filters.includes('vote')" class="dc-rank-field">
                      <span class="dc-rank-label">评分</span>
                      <VTextField v-model.number="form.rank_configs[rd.key].vote" type="number" min="0" max="10" step="0.1" density="compact" variant="outlined" hide-details class="dc-rank-input" />
                    </div>
                    <div v-if="rd.filters.includes('year')" class="dc-rank-field">
                      <span class="dc-rank-label">年份</span>
                      <VTextField v-model.number="form.rank_configs[rd.key].year" type="number" min="0" density="compact" variant="outlined" hide-details class="dc-rank-input" />
                    </div>
                  </div>
                </div>
              </div>
              <div class="dc-section-title mt-4">自定义榜单</div>
              <VTextarea v-model="form.custom_rss_addrs" label="自定义 RSS 地址（一行一个）" rows="3" auto-grow density="compact" variant="outlined" hide-details />
            </div>

            <div v-show="activeSub === 'filter'" class="dc-pane">
              <div class="dc-section-title">条件筛选</div>
              <VRow>
                <VCol cols="12" md="6"><VSelect v-model="form.region_filters" :items="regionOptions" label="地区筛选" multiple chips closable-chips clearable density="compact" variant="outlined" hide-details /><div class="dc-hint">即将上映专用</div></VCol>
                <VCol cols="12" md="6"><VSelect v-model="form.genre_filters" :items="genreOptions" label="类型筛选" multiple chips closable-chips clearable density="compact" variant="outlined" hide-details /><div class="dc-hint">即将上映专用</div></VCol>
              </VRow>
              <VRow class="mt-2"><VCol cols="12" md="6"><VSelect v-model="form.resolution_filters" :items="resolutionOptions" item-title="title" item-value="value" label="订阅分辨率" multiple chips closable-chips clearable density="compact" variant="outlined" hide-details hint="不选则沿用系统默认" persistent-hint /></VCol></VRow>
              <VDivider class="my-3" />
              <div class="dc-section-title">观察设置</div>
              <VRow>
                <VCol cols="12" md="8"><VSelect v-model="form.observe_rank_keys" :items="rankDefs.map(r => ({ title: r.name, value: r.key }))" label="观察榜单" multiple chips clearable density="compact" variant="outlined" hide-details hint="被选中的榜单会先进入观察队列，达到观察期后再订阅" persistent-hint /></VCol>
                <VCol cols="12" md="4"><VTextField v-model.number="form.observe_days" label="观察期（天）" type="number" min="0" density="compact" variant="outlined" hide-details hint="新条目在榜 N 天后才订阅，0 为不启用" persistent-hint /></VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12"><VTextarea v-model="form.blacklist_keywords" label="黑名单关键词（一行一个）" rows="3" auto-grow density="compact" variant="outlined" hide-details hint="标题包含任一关键词则跳过订阅。支持片段匹配，如输入「综艺」会匹配所有含「综艺」的剧名" persistent-hint /></VCol>
              </VRow>
            </div>

            <div v-show="activeSub === 'sync'" class="dc-pane">
              <div class="dc-section-title">同步设置</div>
              <VRow>
                <VCol cols="12" md="4"><VSwitch v-model="form.folio_enabled" color="success" inset hide-details label="启用豆瓣时间" /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.folio_private" color="info" inset hide-details label="仅自己可见" /></VCol>
                <VCol cols="12" md="4"><VSwitch v-model="form.folio_first" color="info" inset hide-details label="不标记第一集" /></VCol>
              </VRow>
              <VRow class="mt-2"><VCol cols="12" md="4"><VSwitch v-model="form.folio_notify" color="info" inset hide-details label="发送通知" /></VCol></VRow>
              <VRow class="mt-2"><VCol cols="12" md="6"><VTextField v-model="form.folio_user" label="媒体库用户名（多个以 , 分隔）" density="compact" variant="outlined" hide-details /></VCol><VCol cols="12" md="6"><VTextField v-model="form.folio_exclude" label="路径排除关键词（多个以 , 分隔）" density="compact" variant="outlined" hide-details /></VCol></VRow>
              <VRow class="mt-2"><VCol cols="12"><VTextField v-model="form.folio_cookie" label="豆瓣 Cookie（留空从 CookieCloud 获取）" density="compact" variant="outlined" hide-details /></VCol></VRow>
            </div>

            <div v-show="activeSub === 'view'" class="dc-pane">
              <div class="dc-section-title">仪表盘选择</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-2" text="先在「榜单列表」中启用榜单，此处即可选择在仪表盘并排显示。最多选 2 个。" />
              <VRow><VCol cols="12" md="6"><VSelect v-model="form.dashboard_rank_keys" label="选择要显示的榜单" :items="rankDefs.filter(r => form.rank_configs?.[r.key]?.enabled).map(r => ({ title: r.name, value: r.key }))" multiple chips clearable density="compact" variant="outlined" hide-details /></VCol></VRow>
              <div class="dc-section-title mt-4">豆瓣时间线显示设置</div>
              <VRow>
                <VCol cols="12" md="6"><VTextField v-model="form.folio_pc_month" label="大屏显示月份数" type="number" density="compact" variant="outlined" hide-details hint="默认 3" persistent-hint /></VCol>
                <VCol cols="12" md="6"><VTextField v-model="form.folio_pc_num" label="大屏每月最多显示数" type="number" density="compact" variant="outlined" hide-details hint="默认 50" persistent-hint /></VCol>
              </VRow>
              <VRow class="mt-2"><VCol cols="12" md="6"><VTextField v-model="form.folio_mobile_month" label="小屏显示月份数" type="number" density="compact" variant="outlined" hide-details hint="默认 2" persistent-hint /></VCol><VCol cols="12" md="6"><VTextField v-model="form.folio_mobile_num" label="小屏每月最多显示数" type="number" density="compact" variant="outlined" hide-details hint="默认 15" persistent-hint /></VCol></VRow>
            </div>
          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dc-actions"><VSpacer /><VBtn variant="text" class="dc-action-btn" @click="emit('close')">取消</VBtn><VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" class="dc-action-btn dc-action-btn--save" @click="saveConfig">保存配置</VBtn></VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.dc-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.dc-card { width: 100%; height: clamp(760px, calc(100dvh - 48px), 860px); display: flex; flex-direction: column; border-radius: 14px; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dc-header { padding: 14px 18px; }
.dc-header-subtitle { max-width: min(560px, 52vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-body { flex: 1 1 auto; min-height: 0; display: flex; }
.dc-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), .02); }
.dc-nav-item { margin: 2px 8px; }
.dc-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.dc-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.dc-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), .7); background: transparent; border: none; cursor: pointer; transition: background .15s, color .15s; white-space: nowrap; }
.dc-subtab:hover { background: rgba(var(--v-theme-primary), .08); color: rgb(var(--v-theme-primary)); }
.dc-subtab--active { background: rgba(var(--v-theme-primary), .14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.dc-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.dc-window--overview { overflow-y: hidden; }
.dc-pane { min-height: 100%; padding: 18px 20px; }
.dc-pane--overview { min-height: auto; padding: 12px 16px; }
.dc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dc-hint { font-size: 12px; line-height: 1.5; color: rgba(var(--v-theme-on-surface), .6); margin-top: 2px; }
.dc-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dc-stat, .dc-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px; min-width: 0; }
.dc-overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.dc-flow { display: grid; gap: 10px; }
.dc-flow-block { min-width: 0; }
.dc-flow-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-primary)); margin-bottom: 5px; }
.dc-flow-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; color: rgba(var(--v-theme-on-surface), .78); }
.dc-flow-row span { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), .02); }
.dc-kv { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dc-kv:last-child { border-bottom: none; }
.dc-rank-row { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); font-size: 13px; }
.dc-rank-row .v-text-field { max-height: 30px; }
.dc-rank-row .v-text-field :deep(.v-field) { min-height: 28px; max-height: 28px; border-radius: 6px; }
.dc-rank-row .v-text-field :deep(.v-field__input) { min-height: 24px; padding-top: 1px; padding-bottom: 1px; font-size: 13px; }
.dc-rank-row .v-text-field :deep(.v-label) { font-size: 13px; }
.dc-rank-row .v-switch :deep(.v-label) { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dc-rank-switch { white-space: nowrap; }
.dc-rank-row .v-row { margin-top: 0; margin-bottom: 0; }
.dc-rank-row .v-col { padding-top: 1px; padding-bottom: 1px; }
.dc-rank-list-1col { display: flex; flex-direction: column; gap: 6px; }
.dc-rank-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; padding: 8px 12px; background: rgba(var(--v-theme-on-surface), .02); transition: border-color .2s, background .2s; }
.dc-rank-card--on { border-color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .04); }
.dc-rank-card-header { margin-bottom: 6px; }
.dc-rank-check :deep(.v-label) { font-size: 13px; font-weight: 600; }
.dc-rank-card-body { display: flex; flex-wrap: wrap; gap: 6px; }
.dc-rank-field { display: grid; grid-template-columns: 28px 110px; align-items: center; gap: 4px; }
.dc-rank-label { font-size: 12px; color: rgba(var(--v-theme-on-surface), .6); white-space: nowrap; min-width: 28px; }
.dc-rank-input { width: 110px; max-width: 118px; }
.dc-rank-input :deep(.v-field) { min-height: 28px; max-height: 28px; border-radius: 6px; }
.dc-rank-input :deep(.v-field__input) { min-height: 24px; padding-top: 1px; padding-bottom: 1px; font-size: 13px; }
.dc-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .dc-config { width: min(100%, calc(100vw - 16px)); padding: 2px; }
  .dc-card { height: min(860px, calc(100dvh - 16px)); }
  .dc-header { padding: 8px 10px; }
  .dc-header-avatar { width: 34px !important; height: 34px !important; }
  .dc-header-title { font-size: 15px; line-height: 1.25; }
  .dc-header-subtitle { max-width: 100%; }
  .dc-enable-switch { flex: 0 0 46px; width: 46px; min-width: 46px; overflow: hidden; }
  .dc-body { flex-direction: column; }
  .dc-nav { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .dc-nav::-webkit-scrollbar { display: none; }
  .dc-nav-list { display: flex; flex-wrap: nowrap; gap: 4px; min-width: max-content; padding: 5px 8px !important; }
  .dc-nav-item { flex: 0 0 auto; min-width: 86px; min-height: 34px !important; margin: 0; padding-inline: 8px; }
  .dc-nav-title { font-size: 12px; white-space: nowrap; }
  .dc-nav-icon { font-size: 17px; }
  .dc-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; scrollbar-width: none; padding: 5px 8px; }
  .dc-subtabs::-webkit-scrollbar { display: none; }
  .dc-subtab { flex: 0 0 auto; padding: 5px 10px; font-size: 12px; }
  .dc-pane { padding: 12px 12px; }
  .dc-pane--overview { padding: 8px 10px; }
  .dc-section-title { margin-bottom: 6px; }
  .dc-stat-grid, .dc-overview-grid { grid-template-columns: 1fr; }
  .dc-stat-grid, .dc-overview-grid, .dc-flow { gap: 6px; }
  .dc-stat, .dc-overview-section { padding: 8px; }
  .dc-flow-label { margin-bottom: 4px; }
  .dc-flow-row { gap: 4px; font-size: 12px; }
  .dc-flow-row span { padding: 4px 7px; }
  .dc-kv { padding: 5px 0; font-size: 12px; }
  .dc-actions { min-height: 44px; padding: 6px 10px; gap: 6px; }
  .dc-action-btn { min-height: 32px; font-size: 13px; }
  .dc-window--overview { overflow-y: auto; }
}
@media (max-width: 480px) {
  .dc-header-subtitle { display: none; }
  .dc-nav-item { min-width: 80px; }
}
@media (max-height: 760px) {
  .dc-window--overview { overflow-y: auto; }
}
</style>
