<script setup>
import Page from './Page.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'LocalToolkit' },
})
const emit = defineEmits(['close', 'switch'])
</script>

<template>
  <Page :api="api" :plugin-id="pluginId" @close="emit('close')" @switch="emit('switch', $event)" />
</template>
