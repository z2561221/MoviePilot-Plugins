<script setup>
defineProps({
  config: { type: Object, required: true },
})
</script>

<template>
  <div v-show="config.activeSub === 'wish'" class="dc-pane">
    <div class="dc-section-title">同步想看</div>
    <VRow>
      <VCol cols="12" md="3"><VSwitch v-model="config.form.wish_enabled" color="success" inset hide-details label="启用想看同步" /></VCol>
      <VCol cols="12" md="3"><VSwitch v-model="config.form.wish_onlyonce" color="warning" inset hide-details label="立即运行一次" /></VCol>
      <VCol cols="12" md="3"><VCronField v-model="config.form.wish_cron" label="独立同步周期" density="compact" variant="outlined" hide-details /></VCol>
      <VCol cols="12" md="3"><VTextField v-model.number="config.form.wish_days" label="最近天数" type="number" min="0" density="compact" variant="outlined" hide-details hint="默认 7 天" persistent-hint /></VCol>
    </VRow>
    <VRow class="mt-2">
      <VCol cols="12" md="8"><VTextField v-model="config.form.wish_user" label="豆瓣用户 ID" density="compact" variant="outlined" hide-details hint="读取该用户的动态 feed，仅处理「想看」条目" persistent-hint /></VCol>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.wish_notify" color="info" inset hide-details label="发送通知" /></VCol>
    </VRow>
    <VAlert class="mt-3" type="info" variant="tonal" density="compact" text="通过豆瓣动态 feed 同步，首次只建立最近天数内的基线；后续周期只处理最近天数内新增的想看。" />
    <div class="dc-wish-status mt-3">
      <div class="dc-kv"><span>队列待处理</span><strong>{{ config.overview?.cards?.folio?.wish?.queue || 0 }}</strong></div>
      <div class="dc-kv"><span>失败记录</span><strong>{{ config.overview?.cards?.folio?.wish?.failed || 0 }}</strong></div>
      <div class="dc-kv"><span>最近运行</span><strong>{{ config.overview?.cards?.folio?.wish?.last_run || '尚未运行' }}</strong></div>
      <div class="dc-kv"><span>状态错误</span><strong>{{ config.overview?.cards?.folio?.wish?.last_error || '无' }}</strong></div>
    </div>
  </div>

  <div v-show="config.activeSub === 'sync'" class="dc-pane">
    <div class="dc-section-title">同步观影</div>
    <VRow>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.folio_enabled" color="success" inset hide-details label="启用豆瓣时间" /></VCol>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.folio_private" color="info" inset hide-details label="仅自己可见" /></VCol>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.folio_first" color="info" inset hide-details label="不标记第一集" /></VCol>
    </VRow>
    <VRow class="mt-2">
      <VCol cols="12" md="4"><VSwitch v-model="config.form.folio_notify" color="info" inset hide-details label="发送通知" /></VCol>
      <VCol cols="12" md="4"><VSwitch v-model="config.form.folio_exclude_live_tv" color="info" inset hide-details label="排除电视直播源" /></VCol>
    </VRow>
    <VRow class="mt-2"><VCol cols="12" md="6"><VTextField v-model="config.form.folio_user" label="媒体库用户名（多个以 , 分隔）" density="compact" variant="outlined" hide-details /></VCol><VCol cols="12" md="6"><VTextField v-model="config.form.folio_exclude" label="路径排除关键词（多个以 , 分隔）" density="compact" variant="outlined" hide-details /></VCol></VRow>
    <VRow class="mt-2"><VCol cols="12"><VTextField v-model="config.form.folio_cookie" label="豆瓣 Cookie（留空从 CookieCloud 获取）" density="compact" variant="outlined" hide-details /></VCol></VRow>
  </div>
</template>

<style scoped>
.dc-pane { min-height: 100%; padding: 18px 20px; }
.dc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dc-wish-status { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 6px 10px; background: rgba(var(--v-theme-on-surface), .02); }
.dc-wish-status strong { max-width: 70%; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: right; }
.dc-kv { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dc-kv:last-child { border-bottom: none; }
@media (max-width: 760px) {
  .dc-pane { padding: 12px; }
  .dc-section-title { margin-bottom: 6px; }
  .dc-kv { padding: 5px 0; font-size: 12px; }
}
</style>
