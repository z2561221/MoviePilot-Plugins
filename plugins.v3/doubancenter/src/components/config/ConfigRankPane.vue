<script setup>
defineProps({
  config: { type: Object, required: true },
})
</script>

<template>
  <div v-show="config.activeSub === 'basic'" class="dc-pane">
    <div class="dc-section-title">基础设置</div>
    <VRow>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.onlyonce" color="warning" inset hide-details label="立即运行一次" /></VCol>
      <VCol cols="12" md="4"><VCronField v-model="config.form.cron" label="运行周期" density="compact" variant="outlined" hide-details /></VCol>
    </VRow>
    <VRow class="mt-2">
      <VCol cols="12"><VTextField v-model="config.form.rsshub_domain" label="RSSHub 域名" density="compact" variant="outlined" hide-details hint="默认 https://rsshub.ddsrem.com，所有榜单共用" persistent-hint /></VCol>
    </VRow>
    <VAlert class="mt-3" type="info" variant="tonal" density="compact" text="订阅用户名统一为「豆瓣中心」。即将上映支持评分、地区、想看筛选；空或 0 表示不限。" />
  </div>

  <div v-show="config.activeSub === 'list'" class="dc-pane">
    <div class="dc-rank-list-heading">
      <div>
        <div class="dc-section-title mb-1">榜单列表</div>
        <div class="dc-rank-list-summary text-caption text-medium-emphasis">已启用 {{ config.enabledRankCount }} 个 · 自定义 {{ config.customRankCount }} 个</div>
      </div>
      <VBtn icon size="small" variant="tonal" color="primary" aria-label="新增自定义榜单" @click="config.addCustomRank">
        <VIcon icon="mdi-plus" size="20" /><VTooltip activator="parent" location="top">新增自定义榜单</VTooltip>
      </VBtn>
    </div>
    <VAlert type="info" variant="tonal" density="compact" class="mb-3" text="每个榜单独立控制；即将上映按提前天数筛选，其他榜单按最近天数筛选，自定义榜单可选择日期方向。空或 0 表示不限。" />
    <VAlert v-if="config.customRankError" type="error" variant="tonal" density="compact" class="mb-2" :text="config.customRankError" />
    <div class="dc-rank-list-1col">
      <div v-for="rank in config.rankDefs" :key="rank.key" class="dc-rank-card" :class="{ 'dc-rank-card--on': config.form.rank_configs[rank.key]?.enabled, 'dc-rank-card--expanded': config.isExpanded(rank.key) }">
        <div class="dc-rank-card-summary">
          <VBtn icon :aria-label="`${config.isExpanded(rank.key) ? '收起' : '展开'}${rank.name}`" variant="text" size="small" class="dc-rank-expand" @click="config.toggleRank(rank.key)">
            <VIcon :icon="config.isExpanded(rank.key) ? 'mdi-chevron-down' : 'mdi-chevron-right'" size="20" />
          </VBtn>
          <VCheckbox v-model="config.form.rank_configs[rank.key].enabled" color="primary" hide-details density="compact" class="dc-rank-check" :aria-label="`启用${rank.name}`" />
          <div class="dc-rank-summary-main" @click="config.toggleRank(rank.key)">
            <div class="dc-rank-summary-title"><span>{{ rank.name }}</span><VChip v-if="rank.custom" size="x-small" color="primary" variant="tonal">自定义</VChip></div>
            <div class="dc-rank-summary-meta">
              <span>数量 {{ config.form.rank_configs[rank.key]?.count || '不限' }}</span>
              <span v-if="rank.filters.includes('vote')">评分 {{ config.form.rank_configs[rank.key]?.vote || '不限' }}</span>
              <span>地区 {{ (config.form.rank_configs[rank.key]?.regions || []).join('、') || '不限' }}</span>
              <span v-if="rank.filters.includes('year')">年份 {{ config.form.rank_configs[rank.key]?.year || '不限' }}</span>
              <span v-if="rank.filters.includes('wish_count')">想看 {{ config.form.rank_configs[rank.key]?.wish_count || '不限' }}</span>
              <span v-if="rank.filters.includes('air_days')">{{ config.rankDateSummary(rank) }}</span>
            </div>
          </div>
          <div class="dc-rank-actions">
            <VBtn v-if="rank.custom" icon variant="flat" color="error" class="dc-delete-rank" :aria-label="`删除${rank.name || '自定义榜单'}`" @click.stop="config.requestRemoveCustomRank(rank)">
              <VIcon icon="mdi-delete-outline" size="20" /><VTooltip activator="parent" location="top">删除自定义榜单</VTooltip>
            </VBtn>
          </div>
        </div>
        <Transition name="dc-rank-details">
          <div v-if="config.isExpanded(rank.key)" class="dc-rank-card-details">
            <div class="dc-rank-detail-toolbar">
              <VCheckbox v-model="config.form.rank_configs[rank.key].enabled" label="自动订阅" color="primary" hide-details density="compact" class="dc-rank-detail-enable" />
              <div v-if="!rank.custom" class="dc-rank-route-hint text-caption text-medium-emphasis">路由：{{ rank.route }}</div>
            </div>
            <div v-if="rank.custom" class="dc-custom-rank-route-row">
              <VTextField :ref="element => config.setNameInputRef(rank.key, element)" v-model="rank.model.name" label="榜单名称" density="compact" variant="outlined" hide-details class="dc-custom-rank-name" />
              <VTextField v-model="rank.model.route" label="路由" placeholder="/example/rsshub/route?foo=bar" density="compact" variant="outlined" hide-details class="dc-custom-rank-route" />
              <VSelect v-model="rank.model.date_mode" :items="config.dateModeOptions" label="日期方向" density="compact" variant="outlined" hide-details class="dc-custom-rank-date-mode" />
            </div>
            <div class="dc-rank-card-body">
              <div class="dc-rank-field dc-rank-field--count"><VTextField v-model.number="config.form.rank_configs[rank.key].count" label="数量" placeholder="0 不限" type="number" min="0" density="compact" variant="outlined" hide-details class="dc-rank-input" /></div>
              <div v-if="rank.filters.includes('vote')" class="dc-rank-field dc-rank-field--vote"><VTextField v-model.number="config.form.rank_configs[rank.key].vote" label="评分" placeholder="0 不限" type="number" min="0" max="10" step="0.1" density="compact" variant="outlined" hide-details class="dc-rank-input" /></div>
              <VCombobox v-model="config.form.rank_configs[rank.key].regions" :items="[]" label="地区" placeholder="自定义填写" multiple chips closable-chips clearable hide-details density="compact" variant="outlined" class="dc-rank-regions" />
              <div v-if="rank.filters.includes('year')" class="dc-rank-field dc-rank-field--threshold"><VTextField v-model.number="config.form.rank_configs[rank.key].year" label="年份" placeholder="0 不限" type="number" min="0" density="compact" variant="outlined" hide-details class="dc-rank-input" /></div>
              <div v-if="rank.filters.includes('wish_count')" class="dc-rank-field dc-rank-field--threshold"><VTextField v-model.number="config.form.rank_configs[rank.key].wish_count" label="想看" placeholder="0 不限" type="number" min="0" density="compact" variant="outlined" hide-details class="dc-rank-input" /></div>
              <div v-if="rank.filters.includes('air_days')" class="dc-rank-field dc-rank-field--days"><VTextField v-model.number="config.form.rank_configs[rank.key].air_days" :label="config.rankDateLabel(rank)" placeholder="0 不限" type="number" min="0" density="compact" variant="outlined" hide-details class="dc-rank-input" /></div>
            </div>
          </div>
        </Transition>
      </div>
    </div>
    <div v-if="!config.form.custom_ranks.length" class="dc-custom-ranks-empty text-caption text-medium-emphasis">尚未添加自定义榜单</div>
    <VDialog :model-value="config.deleteDialog" max-width="420" @update:model-value="config.deleteDialog = $event">
      <VCard>
        <VCardTitle class="text-body-1">删除自定义榜单</VCardTitle>
        <VCardText>确定删除「{{ config.deleteTarget?.name || '未命名榜单' }}」吗？相关订阅、历史和运行条目不会被删除。</VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="config.deleteDialog = false">取消</VBtn><VBtn color="error" variant="tonal" @click="config.removeCustomRank(config.deleteTarget?.key)">删除</VBtn></VCardActions>
      </VCard>
    </VDialog>
  </div>

  <div v-show="config.activeSub === 'filter'" class="dc-pane">
    <div class="dc-section-title">观察设置</div>
    <VRow>
      <VCol cols="12" md="8"><VSelect v-model="config.form.observe_rank_keys" :items="config.rankDefs.map(rank => ({ title: rank.name, value: rank.key }))" label="观察榜单" multiple chips clearable density="compact" variant="outlined" hide-details hint="被选中的榜单会先进入观察队列，达到观察期后再订阅" persistent-hint /></VCol>
      <VCol cols="12" md="4"><VTextField v-model.number="config.form.observe_days" label="观察期（天）" type="number" min="0" density="compact" variant="outlined" hide-details hint="新条目在榜 N 天后才订阅，0 为不启用" persistent-hint /></VCol>
    </VRow>
    <VRow class="mt-2"><VCol cols="12"><VTextarea v-model="config.form.blacklist_keywords" label="黑名单关键词（一行一个）" rows="3" auto-grow density="compact" variant="outlined" hide-details hint="标题包含任一关键词则跳过订阅。支持片段匹配，如输入「综艺」会匹配所有含「综艺」的剧名" persistent-hint /></VCol></VRow>
  </div>
</template>

<style scoped>
.dc-pane { min-height: 100%; padding: 18px 20px; }
.dc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dc-rank-list-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.dc-rank-list-summary { line-height: 1.35; }
.dc-rank-list-1col { display: flex; flex-direction: column; gap: 4px; }
.dc-rank-card { display: block; min-width: 0; padding: 0; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .02); transition: border-color .2s, background .2s; }
.dc-rank-card--on { border-color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .04); }
.dc-rank-card-summary { display: grid; grid-template-columns: 36px 34px minmax(0, 1fr) 42px; align-items: center; gap: 4px; min-height: 50px; padding: 6px 8px; }
.dc-rank-expand { width: 36px; height: 36px; }
.dc-rank-check :deep(.v-label) { font-size: 13px; font-weight: 600; }
.dc-rank-summary-main { min-width: 0; cursor: pointer; }
.dc-rank-summary-title { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; min-width: 0; font-size: 13px; font-weight: 600; line-height: 1.25; }
.dc-rank-summary-title > span { min-width: 0; overflow-wrap: anywhere; }
.dc-rank-summary-meta { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 3px; color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; line-height: 1.25; }
.dc-rank-actions { display: flex; align-items: center; justify-content: flex-end; min-width: 36px; }
.dc-delete-rank { width: 36px !important; height: 36px !important; min-width: 36px !important; flex: 0 0 36px; border: 1px solid rgb(var(--v-theme-error)); background: rgb(var(--v-theme-error)) !important; color: rgb(var(--v-theme-on-error)) !important; box-shadow: 0 0 0 1px rgba(0, 0, 0, .18); }
.dc-delete-rank :deep(.v-icon) { color: currentColor !important; opacity: 1 !important; }
.dc-rank-card-details { display: grid; gap: 10px; padding: 9px 12px 12px; border-top: 1px solid rgba(var(--v-border-color), .45); min-width: 0; }
.dc-rank-detail-toolbar { min-height: 30px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dc-rank-detail-enable { flex: 0 0 auto; min-width: 0; min-height: 30px; margin-left: -8px; }
.dc-rank-card-body { display: grid; grid-template-columns: 80px 80px minmax(150px, 1fr) 92px 108px; align-items: start; gap: 8px; min-width: 0; }
.dc-rank-field { min-width: 0; width: 100%; }
.dc-rank-field--count { grid-column: 1; }
.dc-rank-field--vote { grid-column: 2; }
.dc-rank-regions { grid-column: 3; min-width: 0; width: 100%; }
.dc-rank-field--threshold { grid-column: 4; }
.dc-rank-field--days { grid-column: 5; }
.dc-rank-input { width: 100%; max-width: none; }
.dc-rank-input :deep(.v-field), .dc-rank-regions :deep(.v-field) { min-height: 40px; border-radius: 6px; }
.dc-rank-input :deep(.v-field__input), .dc-rank-regions :deep(.v-field__input) { min-height: 38px; padding-top: 3px; padding-bottom: 3px; font-size: 13px; }
.dc-rank-input :deep(.v-label), .dc-rank-regions :deep(.v-label) { font-size: 12px; }
.dc-custom-rank-route-row { display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.5fr) minmax(120px, .55fr); gap: 8px; align-items: end; min-width: 0; }
.dc-custom-rank-name, .dc-custom-rank-route, .dc-custom-rank-date-mode { min-width: 0; }
.dc-rank-route-hint { overflow-wrap: anywhere; }
.dc-custom-ranks-empty { border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 12px; text-align: center; }
.dc-rank-details-enter-active, .dc-rank-details-leave-active { transition: opacity .15s ease, transform .15s ease; will-change: opacity, transform; }
.dc-rank-details-enter-from, .dc-rank-details-leave-to { opacity: 0; transform: translateY(-4px); }
@media (max-width: 760px) {
  .dc-pane { padding: 12px; }
  .dc-section-title { margin-bottom: 6px; }
  .dc-rank-card-summary { grid-template-columns: 34px 34px minmax(0, 1fr) 40px; padding: 6px 4px; }
  .dc-rank-summary-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 3px 8px; }
  .dc-rank-card-details { padding: 9px 10px 12px; }
  .dc-rank-detail-toolbar { align-items: flex-start; flex-direction: column; gap: 2px; }
  .dc-rank-card-body { grid-template-columns: 1fr; gap: 8px; }
  .dc-rank-detail-enable, .dc-rank-regions { min-width: 0; width: 100%; }
  .dc-rank-field, .dc-rank-field--count, .dc-rank-field--vote, .dc-rank-regions, .dc-rank-field--threshold, .dc-rank-field--days { grid-column: 1; }
  .dc-custom-rank-route-row { grid-template-columns: 1fr; }
  .dc-delete-rank { width: 36px !important; height: 36px !important; }
}
</style>
