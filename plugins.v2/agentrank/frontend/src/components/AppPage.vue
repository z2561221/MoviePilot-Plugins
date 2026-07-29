<script setup>
import { ref } from 'vue'
import Config from './Config.vue'
import Page from './Page.vue'
import { savePluginConfig } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'AgentRank' },
})

const settingsDialog = ref(false)
const savingSettings = ref(false)
const settingsConfig = ref({})
const pageKey = ref(0)
const snackbar = ref({ show: false, message: '', color: 'success' })

function openSettings(config = {}) {
  settingsConfig.value = { ...(config || {}) }
  settingsDialog.value = true
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
    snackbar.value = {
      show: true,
      message: error?.message || '设置保存失败',
      color: 'error',
    }
  } finally {
    savingSettings.value = false
  }
}
</script>

<template>
  <div class="ar-app-page" :data-nav-key="navKey" :data-plugin-id="pluginId">
    <Page
      :key="pageKey"
      :api="api"
      :native-subscribe="nativeSubscribe"
      :show-close="false"
      @switch="openSettings"
    />

    <VDialog v-model="settingsDialog" max-width="1160" :persistent="savingSettings">
      <Config
        :api="api"
        :initial-config="settingsConfig"
        @save="saveSettings"
        @close="settingsDialog = false"
      />
    </VDialog>

    <VSnackbar v-model="snackbar.show" :color="snackbar.color" timeout="5000">
      {{ snackbar.message }}
    </VSnackbar>
  </div>
</template>

<style scoped>
.ar-app-page {
  width: 100%;
  min-width: 0;
}
</style>
