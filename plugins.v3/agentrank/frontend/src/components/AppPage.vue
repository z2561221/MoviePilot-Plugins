<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Config from './Config.vue'
import Page from './Page.vue'
import { savePluginConfig } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  nativeSubscribe: { type: Function, default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: '' },
  sourcePluginId: { type: String, default: '' },
})

const settingsDialog = ref(false)
const savingSettings = ref(false)
const settingsConfig = ref({})
const pageKey = ref(0)
const snackbar = ref({ show: false, message: '', color: 'success' })
const hostScrollLockClass = 'ar-app-page-host-lock'
let hostScrollLocked = false

function lockHostScroll() {
  if (typeof document === 'undefined' || hostScrollLocked) return
  const root = document.documentElement
  const currentLocks = Number.parseInt(root.dataset.agentRankScrollLocks || '0', 10) || 0
  root.dataset.agentRankScrollLocks = String(currentLocks + 1)
  root.classList.add(hostScrollLockClass)
  document.body?.classList.add(hostScrollLockClass)
  hostScrollLocked = true
}

function unlockHostScroll() {
  if (typeof document === 'undefined' || !hostScrollLocked) return
  const root = document.documentElement
  const currentLocks = Number.parseInt(root.dataset.agentRankScrollLocks || '0', 10) || 0
  const nextLocks = Math.max(0, currentLocks - 1)
  if (nextLocks > 0) {
    root.dataset.agentRankScrollLocks = String(nextLocks)
  } else {
    delete root.dataset.agentRankScrollLocks
    root.classList.remove(hostScrollLockClass)
    document.body?.classList.remove(hostScrollLockClass)
  }
  hostScrollLocked = false
}

onMounted(lockHostScroll)
onBeforeUnmount(unlockHostScroll)

function openSettings(config = {}) {
  settingsConfig.value = { ...(config || {}) }
  settingsDialog.value = true
}

async function saveSettings(config) {
  savingSettings.value = true
  try {
    await savePluginConfig(props.api, props.pluginId, config)
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
      :plugin-id="pluginId"
      :source-plugin-id="sourcePluginId"
      :show-close="false"
      @switch="openSettings"
    />

    <VDialog v-model="settingsDialog" max-width="1160" :persistent="savingSettings">
      <Config
        :api="api"
        :plugin-id="pluginId"
        :source-plugin-id="sourcePluginId"
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
  overflow: hidden;
}

@media (max-width: 760px) {
  :global(.ar-app-page-host-lock) {
    overflow-y: hidden !important;
    overscroll-behavior-y: none;
  }

  :global(.ar-app-page-host-lock .layout-footer) {
    display: none !important;
  }
}
</style>
