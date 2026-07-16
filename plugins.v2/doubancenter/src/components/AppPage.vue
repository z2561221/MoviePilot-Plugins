<script setup>
import Page from './Page.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'DoubanCenter' },
})
</script>

<template>
  <main class="dc-app-page">
    <Page :key="`${props.pluginId}-${props.navKey}`" :api="props.api" app-page />
  </main>
</template>

<style scoped>
.dc-app-page { width: 100%; min-width: 0; max-width: 1800px; margin: 0 auto; padding: 16px; background: transparent; }
@media (max-width: 600px) { .dc-app-page { padding: 8px; } }
</style>
