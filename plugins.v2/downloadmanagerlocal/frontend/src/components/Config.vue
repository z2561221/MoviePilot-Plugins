<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { getPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const form = reactive({})
const activeMain = ref('overview')
const activeSub = ref('overview')
const downloaderItems = ref([])
const siteItems = ref([])
const overview = ref(null)

onMounted(async () => {
  try {
    const [dlResp, siteResp, overviewResp] = await Promise.all([
      getPluginApi(props.api, 'downloaders'),
      getPluginApi(props.api, 'sites'),
      getPluginApi(props.api, 'overview'),
    ])
    if (dlResp) {
      downloaderItems.value = dlResp
    }
    if (siteResp) {
      siteItems.value = siteResp
    }
    if (overviewResp?.code === 0 || overviewResp?.cards) {
      overview.value = overviewResp
    }
  } catch (e) {
    console.error('获取列表失败:', e)
  }
})

const defaults = {
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
  iyuu_enabled: false, iyuu_cron: '', iyuu_onlyonce: false,
  iyuu_token: '', iyuu_downloaders: [], iyuu_auto_downloader: '',
  iyuu_sites: [], iyuu_nolabels: '', iyuu_nopaths: '',
  iyuu_size: 0, iyuu_auto_category: false,
  iyuu_labelsafterseed: '已整理,辅种', iyuu_categoryafterseed: '',
  iyuu_clearcache: false,
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
}

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '总览下载中心运行链路、模块状态和待关注事项。' },
  { key: 'transfer', title: '转移做种', icon: 'mdi-transfer', desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'iyuu', title: 'IYUU辅种', icon: 'mdi-seed-plus', desc: '基于 IYUU API 自动辅种，铺种后自动打站点标签。' },
  { key: 'rename', title: '命名补刀', icon: 'mdi-rename-box', desc: '转移后自动根据 TMDB 信息命名种子，并支持失败补刀。' },
  { key: 'tag', title: '站点标签', icon: 'mdi-tag-multiple', desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'seed', title: '做种校验', icon: 'mdi-check-circle-outline', desc: '统一控制跳过校验和自动开始做种，按需触发。' },
]

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-variant' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  iyuu: [
    { key: 'iyuu_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'iyuu_filter', title: '筛选条件', icon: 'mdi-filter-variant' },
    { key: 'iyuu_advanced', title: '高级选项', icon: 'mdi-tune' },
  ],
  rename: [{ key: 'format', title: '命名格式', icon: 'mdi-format-text' }],
  tag: [{ key: 'mapping', title: 'Tracker 映射', icon: 'mdi-link-variant' }],
  seed: [{ key: 'seed_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const selectedToDownloaderType = computed(() => {
  const selected = downloaderItems.value.find(item => item.value === form.todownloader)
  return selected?.type || ''
})
const overviewCards = computed(() => {
  const cards = overview.value?.cards || {}
  const archive = overview.value?.archive || {}
  return [
    {
      title: '转移做种',
      icon: 'mdi-transfer',
      color: cards.transfer?.active ? 'success' : 'warning',
      value: cards.transfer?.active ? '运行中' : '未就绪',
      desc: cards.transfer?.fallback_enabled ? '兜底服务已启用' : '兜底服务未启用',
    },
    {
      title: 'IYUU铺种',
      icon: 'mdi-seed-plus',
      color: cards.iyuu?.enabled ? 'success' : 'default',
      value: cards.iyuu?.enabled ? '已启用' : '未启用',
      desc: `成功 ${cards.iyuu?.success || 0} · 失败 ${cards.iyuu?.fail || 0}`,
    },
    {
      title: '命名补刀',
      icon: 'mdi-auto-fix',
      color: archive.archived ? 'warning' : 'primary',
      value: `${archive.active_failed || 0} / ${archive.archived || 0}`,
      desc: `待处理 / 已归档，阈值 ${archive.threshold || 3} 次`,
    },
    {
      title: '做种校验',
      icon: 'mdi-check-circle-outline',
      color: cards.seed?.autostart ? 'success' : 'default',
      value: cards.seed?.autostart ? '自动开始' : '仅校验',
      desc: cards.seed?.skipverify ? '跳过校验' : '按需校验',
    },
  ]
})
const runtimeFlows = [
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
    label: '兜底补刀',
    steps: ['异常命名', '兜底补刀', '失败计数', '归档恢复'],
  },
]

watch(() => props.initialConfig, v => {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, defaults, v || {})
}, { immediate: true, deep: true })

function saveConfig() { emit('save', { ...form }) }
function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || ''
}
</script>
<template>
  <div class="dm-config">
    <VCard flat class="dm-card">
      <VCardItem class="dm-header">
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
      <div class="dm-body">
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
            <div v-show="activeSub === 'overview'" class="dm-pane dm-pane--overview">
              <div class="dm-overview-section mb-3">
                <div class="dm-section-title">运行链路</div>
                <div class="dm-flow">
                  <div v-for="flow in runtimeFlows" :key="flow.label" class="dm-flow-block">
                    <div class="dm-flow-label">{{ flow.label }}</div>
                    <div class="dm-flow-row">
                      <template v-for="(step, index) in flow.steps" :key="`${flow.label}-${step}`">
                        <span class="dm-flow-step">{{ step }}</span>
                        <VIcon v-if="index < flow.steps.length - 1" class="dm-flow-arrow" icon="mdi-arrow-right" size="14" />
                      </template>
                    </div>
                  </div>
                </div>
              </div>

              <div class="dm-stat-grid mb-3">
                <div v-for="card in overviewCards" :key="card.title" class="dm-stat">
                  <div class="d-flex align-center ga-2 mb-1">
                    <VAvatar :color="card.color" variant="tonal" size="28" rounded="lg"><VIcon :icon="card.icon" size="17" /></VAvatar>
                    <div class="text-caption text-medium-emphasis">{{ card.title }}</div>
                  </div>
                  <div class="text-subtitle-1 font-weight-bold">{{ card.value }}</div>
                  <div class="text-caption text-medium-emphasis">{{ card.desc }}</div>
                </div>
              </div>

              <div class="dm-overview-grid">
                <div class="dm-overview-section">
                  <div class="dm-section-title">命名概况</div>
                  <div class="text-caption text-medium-emphasis">成功 {{ overview?.rename_history?.success || 0 }} · 失败 {{ overview?.rename_history?.failed || 0 }} · 脏名 {{ overview?.rename_history?.dirty || 0 }}</div>
                </div>
                <div class="dm-overview-section">
                  <div class="dm-section-title">待办关注</div>
                  <div class="text-caption text-medium-emphasis">连续失败 {{ overview?.archive?.active_failed || 0 }} · 接近归档 {{ overview?.archive?.near_archive || 0 }} · 已归档 {{ overview?.archive?.archived || 0 }}</div>
                </div>
              </div>
            </div>

            <!-- ═══ 转移做种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.fromdownloader" label="源下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" hint="选择源下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.todownloader" label="目的下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" hint="选择目的下载器" persistent-hint />
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
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.frompath" label="源数据文件根路径" density="compact" variant="outlined" hide-details
                    hint="源下载器中数据的根路径" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.topath" label="目的数据文件根路径" density="compact" variant="outlined" hide-details
                    hint="目标下载器中数据的根路径" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.fromtorrentpath" label="源种子文件路径" density="compact" variant="outlined" hide-details
                    hint="如 BT_backup，留空自动获取" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.add_torrent_tags" label="添加种子标签" density="compact" variant="outlined" hide-details
                    hint="多个以逗号分隔" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.transfer_enabled" color="success" inset hide-details label="启用转移做种" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.notify" color="info" inset hide-details label="发送通知" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.delay_minutes" label="延迟时间（分钟）" type="number" density="compact" variant="outlined" hide-details
                    hint="下载完成后延迟 N 分钟再转移" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.transfer_fallback_enabled" color="success" inset hide-details label="转移做种兜底服务" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.transfer_fallback_interval_minutes" label="兜底间隔（分钟）" type="number" min="1" density="compact" variant="outlined" hide-details
                    :disabled="!form.transfer_fallback_enabled" hint="事件漏触发时按此间隔扫描，默认60分钟" persistent-hint />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 筛选条件 ═══ -->
            <div v-show="activeSub === 'filter'" class="dm-pane">
              <div class="dm-section-title">筛选条件</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.includelabels" label="转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="仅转移包含这些标签的种子" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.nolabels" label="不转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="跳过包含这些标签的种子" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.includecategory" label="转移种子分类（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="仅转移这些分类的种子" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VSwitch v-model="form.transferemptylabel" color="info" inset hide-details label="转移无标签种子" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.nopaths" label="不转移数据文件目录（每行一个）" density="compact" variant="outlined" hide-details rows="3" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 高级选项 ═══ -->
            <div v-show="activeSub === 'advanced'" class="dm-pane">
              <div class="dm-section-title">高级选项</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.deletesource" color="warning" inset hide-details label="删除源种子" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.deleteduplicate" color="warning" inset hide-details label="删除重复种子" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.remainoldcat" color="info" inset hide-details label="保留原分类" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.remainoldtag" color="info" inset hide-details label="保留原标签" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ IYUU辅种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'iyuu_basic'" class="dm-pane">
              <div class="dm-section-title">IYUU 辅种设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.iyuu_enabled" color="success" inset hide-details label="启用辅种" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.iyuu_onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.iyuu_clearcache" color="error" inset hide-details label="清除缓存后运行" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.iyuu_token" label="IYUU Token" density="compact" variant="outlined" hide-details
                    hint="在 https://iyuu.cn 获取" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VCronField v-model="form.iyuu_cron" label="执行周期" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VSelect v-model="form.iyuu_downloaders" label="辅种下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" multiple chips clearable hint="选择辅种目标下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.iyuu_auto_downloader" label="主辅分离" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" clearable hint="辅种专用下载器（可选）" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VSelect v-model="form.iyuu_sites" label="辅种站点" density="compact" variant="outlined" hide-details
                    :items="siteItems" multiple chips clearable hint="选择允许辅种的站点，留空表示全部站点" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model.number="form.iyuu_size" label="辅种体积大于(GB)" type="number" density="compact" variant="outlined" hide-details
                    hint="只有大于该值的才辅种" persistent-hint />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ IYUU辅种 · 筛选条件 ═══ -->
            <div v-show="activeSub === 'iyuu_filter'" class="dm-pane">
              <div class="dm-section-title">辅种筛选</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.iyuu_nolabels" label="不辅种标签（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="跳过包含这些标签的种子" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.iyuu_labelsafterseed" label="辅种后增加标签" density="compact" variant="outlined" hide-details
                    hint="逗号分隔，默认：已整理,辅种" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.iyuu_categoryafterseed" label="辅种后增加分类" density="compact" variant="outlined" hide-details
                    hint="设置辅种种子的分类" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.iyuu_nopaths" label="不辅种数据文件目录（每行一个）" density="compact" variant="outlined" hide-details rows="3" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ IYUU辅种 · 高级选项 ═══ -->
            <div v-show="activeSub === 'iyuu_advanced'" class="dm-pane">
              <div class="dm-section-title">辅种高级选项</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.iyuu_auto_category" color="info" inset hide-details label="分类复用(QB有效)" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 种子重命名 · 命名格式 ═══ -->
            <div v-show="activeSub === 'format'" class="dm-pane">
              <div class="dm-section-title">重命名设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.rename_enabled" color="success" inset hide-details label="启用重命名" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_movie_format" label="电影命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ original_name }}</div>
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_tv_format" label="电视剧命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ season_episode }}, {{ original_name }}</div>
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_exclude_dirs" label="排除目录（每行一个）" density="compact" variant="outlined" hide-details rows="2" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 站点标签 · Tracker 映射 ═══ -->
            <div v-show="activeSub === 'mapping'" class="dm-pane">
              <div class="dm-section-title">站点标签设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enabled" color="success" inset hide-details label="启用站点标签" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.tag_siteprefix" label="站点标签前缀" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.tag_tracker_mappings_str" label="Tracker 映射（每行: 域名 -> 映射域名）" density="compact" variant="outlined" hide-details rows="4" />
                  <div class="dm-hint">例: tracker.example.com -> example</div>
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 做种校验 v3.0.15 · 基础设置 ═══ -->
            <div v-show="activeSub === 'seed_basic'" class="dm-pane">
              <div class="dm-section-title">做种校验设置</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-4">做种校验采用按需触发：仅在转移做种、IYUU铺种或手动补刀添加种子后启动。队列为空后自动停止。</VAlert>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.seed_autostart" color="success" inset hide-details label="启用自动开始做种" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.seed_skipverify" color="info" inset hide-details label="跳过校验(QB有效)" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model.number="form.seed_check_interval" label="校验检查间隔（秒）" type="number" density="compact" variant="outlined" hide-details hint="建议 60 秒" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model.number="form.seed_max_wait_minutes" label="最大等待时间（分钟）" type="number" density="compact" variant="outlined" hide-details hint="超时后移出队列" persistent-hint />
                </VCol>
              </VRow>
            </div>

          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dm-actions">
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>
<style scoped>
.dm-config {
  width: min(1120px, calc(100vw - 48px));
  max-width: 100%;
  padding: 8px;
}
.dm-card {
  width: 100%;
  height: clamp(760px, calc(100dvh - 48px), 860px);
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
.dm-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.dm-stat { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 8px 10px; min-width: 0; }
.dm-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px 12px; min-width: 0; }
.dm-overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.dm-flow { display: grid; gap: 10px; }
.dm-flow-block { min-width: 0; }
.dm-flow-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-primary)); margin-bottom: 5px; }
.dm-flow-row { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.78); }
.dm-flow-step { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), 0.02); white-space: nowrap; }
.dm-flow-arrow { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), 0.44); }
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
  .dm-stat-grid, .dm-overview-grid { grid-template-columns: 1fr; }
  .dm-window--overview { overflow-y: auto; }
}
@media (max-height: 760px) {
  .dm-window--overview { overflow-y: auto; }
}
</style>
