<script setup>
import { ref } from 'vue'
import Config from './Config.vue'
import Page from './Page.vue'
import { getPluginConfig, savePluginConfig } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'DoubanCenter' },
})

const settingsDialog = ref(false)
const loadingSettings = ref(false)
const savingSettings = ref(false)
const settingsConfig = ref({})
const pageKey = ref(0)
const snackbar = ref({ show: false, message: '', color: 'success' })

async function openSettings() {
  loadingSettings.value = true
  try {
    settingsConfig.value = await getPluginConfig(props.api)
    settingsDialog.value = true
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置加载失败', color: 'error' }
  } finally {
    loadingSettings.value = false
  }
}

async function saveSettings(config) {
  savingSettings.value = true
  try {
    await savePluginConfig(props.api, config)
    settingsConfig.value = { ...(config || {}) }
    settingsDialog.value = false
    pageKey.value += 1
    snackbar.value = { show: true, message: '设置已保存', color: 'success' }
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置保存失败', color: 'error' }
  } finally {
    savingSettings.value = false
  }
}
</script>

<template>
  <main class="dc-app-page">
    <Page
      :key="`${props.pluginId}-${props.navKey}-${pageKey}`"
      :api="props.api"
      :native-subscribe="props.nativeSubscribe"
      app-page
      show-settings
      @switch="openSettings"
    />

    <VDialog v-model="settingsDialog" max-width="1160" :persistent="savingSettings || loadingSettings">
      <VProgressLinear v-if="loadingSettings" indeterminate color="primary" />
      <Config
        v-if="!loadingSettings"
        :api="props.api"
        :initial-config="settingsConfig"
        @save="saveSettings"
        @close="settingsDialog = false"
      />
    </VDialog>

    <VSnackbar v-model="snackbar.show" :color="snackbar.color" timeout="5000">
      {{ snackbar.message }}
    </VSnackbar>
  </main>
</template>

<style scoped>
.dc-app-page { width: 100%; min-width: 0; max-width: 1800px; margin: 0 auto; padding: 16px; background: transparent; }
@media (max-width: 600px) { .dc-app-page { padding: 8px; } }
</style>
