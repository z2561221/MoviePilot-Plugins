<script setup>
defineProps({
  config: { type: Object, required: true },
})
</script>

<template>
  <div v-show="config.activeSub === 'view'" class="dc-pane">
    <div class="dc-section-title">仪表盘选择</div>
    <VAlert type="info" variant="tonal" density="compact" class="mb-2" text="仪表盘最多显示 6 个已启用榜单；开启发现页后，保存并刷新 MP 页面即可从左侧「发现」分组进入豆瓣中心。" />
    <VRow>
      <VCol cols="12" md="6"><VSelect v-model="config.form.dashboard_rank_keys" label="选择要显示的榜单（最多 6 个）" :items="config.rankDefs.filter(rank => config.form.rank_configs?.[rank.key]?.enabled).map(rank => ({ title: rank.name, value: rank.key }))" multiple chips clearable density="compact" variant="outlined" hide-details @update:model-value="config.limitDashboardRanks" /></VCol>
      <VCol cols="12" md="6"><VSwitch v-model="config.form.discovery_page_enabled" color="success" inset hide-details label="开启发现页" /></VCol>
    </VRow>
  </div>
</template>

<style scoped>
.dc-pane { min-height: 100%; padding: 18px 20px; }
.dc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
@media (max-width: 760px) {
  .dc-pane { padding: 12px; }
  .dc-section-title { margin-bottom: 6px; }
}
</style>
