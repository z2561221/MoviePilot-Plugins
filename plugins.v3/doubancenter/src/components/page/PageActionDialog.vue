<script setup>
defineProps({
  page: { type: Object, required: true },
})
</script>

<template>
  <VDialog :model-value="page.showDialog" max-width="420" @update:model-value="page.showDialog = $event">
    <VCard rounded="lg" class="dc-action-dialog">
      <VCardItem class="pa-3">
        <template #prepend>
          <VAvatar size="36" rounded="md" class="mr-2">
            <VImg v-if="page.dialogPoster()" :src="page.dialogPoster()" />
            <VIcon v-else icon="mdi-filmstrip" />
          </VAvatar>
        </template>
        <VCardTitle class="text-body-1 font-weight-bold pa-0">{{ page.dialogItem?.item?.title || '' }}</VCardTitle>
        <VCardSubtitle class="text-caption pa-0">{{ page.dialogItem?.rk ? page.rankNameOf(page.dialogItem.rk, page.dialogItem.item) : '' }}</VCardSubtitle>
      </VCardItem>
      <VDivider />
      <VAlert v-if="page.dialogResolveError" type="warning" variant="tonal" density="compact" class="mx-3 mt-3" :text="page.dialogResolveError" />
      <VCardActions class="pa-3 pt-2 dc-dialog-actions">
        <VBtn variant="tonal" color="primary" prepend-icon="mdi-plus-circle-outline" class="dc-dialog-action text-none" :disabled="page.dialogResolving" @click="page.doSubscribe">订阅</VBtn>
        <VBtn variant="tonal" prepend-icon="mdi-movie-open-outline" class="dc-dialog-action dc-dialog-action--tmdb text-none" :loading="page.dialogResolving" :disabled="page.dialogResolving || !page.tmdbIdOf(page.dialogItem?.item)" @click="page.doOpenTmdb">TMDB</VBtn>
        <VBtn :href="page.sourceButtonHref() || undefined" target="_blank" rel="noopener noreferrer" variant="tonal" :color="page.sourceButtonColor()" :prepend-icon="page.sourceButtonIcon()" :disabled="!page.sourceButtonUrl()" class="dc-dialog-action text-none" @click="page.openSource">{{ page.sourceButtonLabel() }}</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.dc-dialog-action { flex: 1 1 0; min-width: 0; height: 36px; }
.dc-dialog-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.dc-dialog-action--tmdb { color: #0288d1 !important; color: color-mix(in srgb, #0288d1 78%, rgb(var(--v-theme-on-surface)) 22%) !important; }
@media (max-width: 760px) {
  .dc-action-dialog { width: min(420px, calc(100vw - 24px)); max-width: calc(100vw - 24px); }
}
</style>
