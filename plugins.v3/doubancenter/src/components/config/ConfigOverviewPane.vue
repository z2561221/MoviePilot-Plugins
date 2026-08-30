<script setup>
defineProps({
  config: { type: Object, required: true },
})
</script>

<template>
  <div class="dc-pane dc-pane--overview">
    <div class="dc-overview-section mb-3">
      <div class="dc-section-title d-flex align-center"><span>运行链路</span></div>
      <div class="dc-flow">
        <div v-for="flow in (config.overview?.flows || [])" :key="flow.label" class="dc-flow-block">
          <div class="dc-flow-label">{{ flow.label }}</div>
          <div v-if="flow.steps?.length" class="dc-flow-row">
            <template v-for="(step, index) in flow.steps" :key="`${flow.label}-${step}`">
              <span>{{ step }}</span><VIcon v-if="index < flow.steps.length - 1" icon="mdi-arrow-right" size="15" />
            </template>
          </div>
          <div v-else-if="flow.flows?.length" class="dc-flow-sub">
            <div v-for="subFlow in flow.flows" :key="`${flow.label}-${subFlow.label}`" class="dc-flow-sub-block">
              <div class="dc-flow-sub-label">{{ subFlow.label }}</div>
              <div class="dc-flow-row dc-flow-row--sub">
                <template v-for="(step, index) in subFlow.steps" :key="`${subFlow.label}-${step}`">
                  <span>{{ step }}</span><VIcon v-if="index < subFlow.steps.length - 1" icon="mdi-arrow-right" size="15" />
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="dc-stat-grid mb-3">
      <div v-for="card in config.overviewCards" :key="card.title" class="dc-stat">
        <div class="d-flex align-center ga-2 mb-1"><VAvatar :color="card.color" variant="tonal" size="28" rounded="lg"><VIcon :icon="card.icon" size="17" /></VAvatar><div class="text-caption text-medium-emphasis">{{ card.title }}</div></div>
        <div class="text-subtitle-1 font-weight-bold">{{ card.value }}</div>
        <div class="text-caption text-medium-emphasis">{{ card.desc }}</div>
      </div>
    </div>

    <div class="dc-overview-grid">
      <div class="dc-overview-section">
        <div class="dc-section-title">待关注</div>
        <div class="dc-kv"><span>观察队列</span><strong>{{ config.overview?.attention?.pending_observations || 0 }}</strong></div>
        <div class="dc-kv"><span>防刷日志</span><strong>{{ config.overview?.attention?.anti_cheat_logs || 0 }}</strong></div>
        <div class="dc-kv"><span>黑名命中</span><strong>{{ config.overview?.attention?.blacklist_hits || 0 }}</strong></div>
      </div>
      <div class="dc-overview-section">
        <div class="dc-section-title">治理概况</div>
        <div class="dc-kv"><span>忽略条目</span><strong>{{ config.overview?.governance?.ignored_observations || 0 }}</strong></div>
        <div class="dc-kv"><span>订阅记录</span><strong>{{ config.overview?.governance?.subscribe_records || 0 }}</strong></div>
        <div class="dc-kv"><span>防刷日志</span><strong>{{ config.overview?.governance?.anti_cheat_logs || 0 }}</strong></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dc-pane { min-height: 100%; padding: 18px 20px; }
.dc-pane--overview { min-height: auto; padding: 12px 16px; }
.dc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dc-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dc-stat, .dc-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px; min-width: 0; }
.dc-overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.dc-flow { display: grid; gap: 10px; }
.dc-flow-block { min-width: 0; }
.dc-flow-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-primary)); margin-bottom: 5px; }
.dc-flow-sub { display: grid; gap: 6px; }
.dc-flow-sub-block { min-width: 0; padding-left: 8px; border-left: 2px solid rgba(var(--v-theme-primary), .25); }
.dc-flow-sub-label { font-size: 12px; font-weight: 600; color: rgba(var(--v-theme-on-surface), .7); margin-bottom: 4px; }
.dc-flow-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; color: rgba(var(--v-theme-on-surface), .78); }
.dc-flow-row--sub { color: rgba(var(--v-theme-on-surface), .72); }
.dc-flow-row span { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), .02); }
.dc-kv { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dc-kv:last-child { border-bottom: none; }
@media (max-width: 760px) {
  .dc-pane--overview { padding: 8px 10px; }
  .dc-section-title { margin-bottom: 6px; }
  .dc-stat-grid, .dc-overview-grid { grid-template-columns: 1fr; }
  .dc-stat-grid, .dc-overview-grid, .dc-flow { gap: 6px; }
  .dc-stat, .dc-overview-section { padding: 8px; }
  .dc-flow-label { margin-bottom: 4px; }
  .dc-flow-sub { gap: 5px; }
  .dc-flow-sub-block { padding-left: 6px; }
  .dc-flow-row { gap: 4px; font-size: 12px; }
  .dc-flow-row span { padding: 4px 7px; }
  .dc-kv { padding: 5px 0; font-size: 12px; }
}
</style>
