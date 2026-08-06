<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue', 'pending-change'])
const { smAndDown } = useDisplay()
const draft = ref('')
const localError = ref('')
const messageList = ref(null)
const pollTimer = ref(null)

const messages = computed(() => props.state.conversation.value?.messages || [])
const commands = computed(() => props.state.conversation.value?.commands || [])
const pendingCommands = computed(() => commands.value.filter(item => item.status === 'pending_confirmation'))
const conversationOperation = computed(() => props.state.operationState('conversation'))
const sendOperation = computed(() => props.state.operationState('conversation:send'))
const agentName = computed(() => props.state.agentDisplayName?.value || 'CinePilot Agent')
const canSend = computed(() => draft.value.trim().length > 0 && !sendOperation.value.loading)
const hasPendingMessages = computed(() => messages.value.some(item => ['queued', 'processing'].includes(item.status)))

function stopPolling() {
  if (pollTimer.value) clearTimeout(pollTimer.value)
  pollTimer.value = null
}

async function pollConversation() {
  if (!props.modelValue || !hasPendingMessages.value) {
    stopPolling()
    return
  }
  try { await props.state.loadConversation({ markRead: true }) } catch (_) { /* 保留共享可重试错误。 */ }
  if (!hasPendingMessages.value) {
    stopPolling()
    await scrollToEnd()
    return
  }
  pollTimer.value = setTimeout(pollConversation, 1500)
}

function startPolling() {
  stopPolling()
  if (!hasPendingMessages.value || !props.modelValue) return
  pollTimer.value = setTimeout(pollConversation, 500)
}

function close() {
  emit('update:modelValue', false)
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}

async function scrollToEnd() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

async function load() {
  try {
    await Promise.all([props.state.loadConversation({ markRead: true }), props.state.loadPendingCenter()])
    await scrollToEnd()
    startPolling()
  } catch (_) {
    // 共享状态保存可见错误和重试动作。
  }
}

async function send() {
  const value = draft.value.trim()
  if (!value) return
  localError.value = ''
  try {
    await props.state.sendConversationMessage(value)
    draft.value = ''
    emit('pending-change')
    await scrollToEnd()
    startPolling()
  } catch (error) {
    localError.value = error?.message || '消息发送失败，草稿已保留'
    try { await props.state.loadConversation({ markRead: true }) } catch (_) { /* 对话读取错误由共享状态展示。 */ }
    await scrollToEnd()
  }
}

async function retryMessage(messageId) {
  localError.value = ''
  try {
    await props.state.retryConversationMessage(messageId)
    emit('pending-change')
    await scrollToEnd()
    startPolling()
  } catch (error) {
    localError.value = error?.message || '重试失败'
    try { await props.state.loadConversation({ markRead: true }) } catch (_) { /* 对话读取错误由共享状态展示。 */ }
  }
}

async function respondCommand(command, action) {
  localError.value = ''
  try {
    await props.state.respondConversationCommand(command.command_id, action)
    emit('pending-change')
  } catch (error) {
    localError.value = error?.message || '待执行操作失败'
  }
}

watch(() => props.modelValue, open => { if (open) load(); else stopPolling() }, { immediate: true })
watch(() => messages.value.length, () => { if (props.modelValue) scrollToEnd() })
onUnmounted(stopPolling)
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :fullscreen="smAndDown"
    max-width="820"
    content-class="ar-chat-dialog"
    scrollable
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="ar-chat">
      <VToolbar density="compact" class="ar-chat__toolbar">
        <VAvatar color="primary" variant="tonal" size="34" class="ms-3 me-3"><VIcon icon="mdi-forum-outline" /></VAvatar>
        <div>
          <div class="ar-chat__title">{{ agentName }}</div>
          <div class="ar-chat__subtitle">{{ props.state.selectedUsername.value || '当前画像' }}</div>
        </div>
        <VSpacer />
        <VBadge v-if="pendingCommands.length" :content="pendingCommands.length" color="warning" inline>
          <VIcon icon="mdi-inbox-outline" size="20" />
        </VBadge>
        <VBtn icon="mdi-refresh" variant="text" :aria-label="`刷新 ${agentName} 对话`" :loading="conversationOperation.loading" @click="load" />
        <VBtn icon="mdi-close" variant="text" :aria-label="`关闭 ${agentName} 对话`" @click="close" />
      </VToolbar>
      <VDivider />

      <div ref="messageList" class="ar-chat__messages">
        <VAlert v-if="conversationOperation.error" type="error" variant="tonal" density="compact" class="mb-3">
          {{ conversationOperation.error.message }}
          <template #append><VBtn variant="text" size="small" @click="props.state.retryOperation('conversation')">重试</VBtn></template>
        </VAlert>
        <div v-if="!messages.length && !conversationOperation.loading" class="ar-chat__empty">
          <VIcon icon="mdi-forum-outline" size="34" color="primary" />
          <span>还没有对话记录</span>
        </div>
        <div
          v-for="message in messages"
          :key="message.message_id"
          class="ar-chat__message"
          :class="`ar-chat__message--${message.role}`"
        >
          <div class="ar-chat__bubble" :class="{ 'ar-chat__bubble--failed': ['failed', 'retryable_failed'].includes(message.status) }">
            <div class="ar-chat__content">{{ message.content }}</div>
            <div class="ar-chat__meta">
              <span>{{ formatTime(message.created_at) }}</span>
              <span v-if="message.role === 'assistant' && (message.provider || message.model)">{{ [message.provider, message.model].filter(Boolean).join(' · ') }}</span>
              <span v-if="message.role === 'user' && message.status === 'queued'">已受理</span>
              <span v-else-if="message.role === 'user' && message.status === 'processing'">处理中</span>
            </div>
            <div v-if="['failed', 'retryable_failed'].includes(message.status)" class="ar-chat__failure">
              <span>{{ message.error_message || '消息处理失败' }}</span>
              <VBtn size="x-small" variant="text" prepend-icon="mdi-refresh" @click="retryMessage(message.message_id)">重试</VBtn>
            </div>
          </div>
        </div>

        <div v-if="pendingCommands.length" class="ar-chat__commands">
          <div class="ar-chat__commands-title">待执行操作</div>
          <div v-for="command in pendingCommands" :key="command.command_id" class="ar-chat__command">
            <div class="ar-chat__command-main">
              <strong>{{ command.title }}</strong>
              <span>{{ command.preview }}</span>
            </div>
            <div class="ar-chat__command-actions">
              <VBtn size="small" variant="text" @click="respondCommand(command, 'reject')">拒绝执行</VBtn>
              <VBtn size="small" color="primary" variant="tonal" :disabled="command.requires_superuser" @click="respondCommand(command, 'confirm')">确认执行</VBtn>
            </div>
          </div>
        </div>
      </div>

      <VDivider />
      <div class="ar-chat__composer">
        <VTextarea
          v-model="draft"
          :label="`给 ${agentName} 发消息`"
          density="compact"
          variant="outlined"
          rows="2"
          auto-grow
          max-rows="5"
          maxlength="1000"
          hide-details
          @keydown.enter.exact.prevent="send"
        />
        <VBtn icon="mdi-send" color="primary" variant="flat" aria-label="发送消息" :loading="sendOperation.loading" :disabled="!canSend" @click="send" />
      </div>
      <VAlert v-if="localError || sendOperation.error" type="error" variant="tonal" density="compact" class="ar-chat__composer-error">
        {{ localError || sendOperation.error?.message }}
      </VAlert>
    </VCard>
  </VDialog>
</template>

<style scoped>
:global(.ar-chat-dialog) { width: min(820px, calc(100vw - 32px)); height: min(760px, calc(100dvh - 32px)); max-height: calc(100dvh - 32px); margin: 16px; overflow: hidden; }
.ar-chat { width: 100%; height: 100%; min-height: 0; max-height: 100%; display: flex; flex-direction: column; overflow: hidden; border-radius: 10px; }
.ar-chat__toolbar { flex: 0 0 auto; background: rgb(var(--v-theme-surface)); }
.ar-chat__title { font-size: 15px; font-weight: 700; }
.ar-chat__subtitle { color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-chat__messages { flex: 1 1 0; min-height: 0; overflow-y: auto; padding: 16px; }
.ar-chat__empty { min-height: 260px; display: grid; place-items: center; align-content: center; gap: 10px; color: rgba(var(--v-theme-on-surface), .55); font-size: 13px; }
.ar-chat__message { display: flex; margin-bottom: 10px; }
.ar-chat__message--user { justify-content: flex-end; }
.ar-chat__bubble { width: fit-content; max-width: min(82%, 620px); padding: 9px 11px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .025); }
.ar-chat__message--user .ar-chat__bubble { border-color: rgba(var(--v-theme-primary), .28); background: rgba(var(--v-theme-primary), .08); }
.ar-chat__bubble--failed { border-color: rgba(var(--v-theme-error), .38); }
.ar-chat__content { overflow-wrap: anywhere; white-space: pre-wrap; font-size: 13px; line-height: 1.55; }
.ar-chat__meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 10px; margin-top: 5px; color: rgba(var(--v-theme-on-surface), .5); font-size: 10px; }
.ar-chat__failure { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 6px; color: rgb(var(--v-theme-error)); font-size: 11px; }
.ar-chat__commands { display: grid; gap: 7px; margin-top: 18px; padding-top: 12px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.ar-chat__commands-title { color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.ar-chat__command { display: flex; align-items: center; gap: 12px; padding: 9px 10px; border: 1px solid rgba(var(--v-theme-warning), .32); border-radius: 8px; background: rgba(var(--v-theme-warning), .045); }
.ar-chat__command-main { min-width: 0; flex: 1 1 auto; }
.ar-chat__command-main strong, .ar-chat__command-main span { display: block; overflow-wrap: anywhere; }
.ar-chat__command-main strong { font-size: 12px; }
.ar-chat__command-main span { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .64); font-size: 11px; }
.ar-chat__command-actions { flex: 0 0 auto; display: flex; gap: 4px; }
.ar-chat__composer { flex: 0 0 auto; display: grid; grid-template-columns: minmax(0, 1fr) 44px; align-items: end; gap: 8px; padding: 12px 14px; }
.ar-chat__composer-error { flex: 0 0 auto; margin: 0 14px 12px; }
@media (max-width: 760px) {
  :global(.ar-chat-dialog) { width: 100%; height: 100dvh; max-height: 100dvh; margin: 0; }
  .ar-chat { width: 100%; height: 100dvh; max-height: none; border-radius: 0; }
  .ar-chat__messages { padding: 12px; }
  .ar-chat__bubble { max-width: 90%; }
  .ar-chat__command { align-items: flex-start; flex-direction: column; }
  .ar-chat__command-actions { align-self: flex-end; }
}
</style>
