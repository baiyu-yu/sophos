<script setup lang="ts">
import { NButton, NInput, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { RotateCcw, Save } from 'lucide-vue-next'
import api from '@/api'

const message = useMessage()

const loading = ref(false)
const saving = ref(false)
const prefix = ref('.')
const savedPrefix = ref('.')
const regexText = ref('')
const savedRegexText = ref('')

const canSave = computed(() => {
  const value = prefix.value.trim()
  return value.length > 0 && value.length <= 3 && !/\s/.test(value) && value !== savedPrefix.value
})

const regexLines = computed(() =>
  regexText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean),
)

const canSaveRegex = computed(() => regexLines.value.join('\n') !== savedRegexText.value)

function normalizeRegexText(value: unknown) {
  return Array.isArray(value) ? value.map(String).join('\n') : ''
}

async function loadSettings() {
  loading.value = true
  try {
    const { data } = await api.get('/settings')
    const value = String(data?.settings?.command_prefix ?? '.')
    prefix.value = value
    savedPrefix.value = value
    const regexTextValue = normalizeRegexText(data?.settings?.trigger_regexes)
    regexText.value = regexTextValue
    savedRegexText.value = regexTextValue
  } catch (error: any) {
    message.error(error?.response?.data?.message ?? '读取设置失败')
  } finally {
    loading.value = false
  }
}

async function savePrefix() {
  if (!canSave.value) return
  saving.value = true
  try {
    const { data } = await api.put('/settings/command_prefix', { value: prefix.value.trim() })
    prefix.value = data.value
    savedPrefix.value = data.value
    message.success(data.message ?? '已保存')
  } catch (error: any) {
    message.error(error?.response?.data?.message ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function resetPrefix() {
  saving.value = true
  try {
    const { data } = await api.delete('/settings/command_prefix')
    prefix.value = String(data.value ?? '.')
    savedPrefix.value = prefix.value
    message.success('已恢复默认前缀 .')
  } catch (error: any) {
    message.error(error?.response?.data?.message ?? '恢复失败')
  } finally {
    saving.value = false
  }
}

async function saveRegexes() {
  if (!canSaveRegex.value) return
  saving.value = true
  try {
    const { data } = await api.put('/settings/trigger_regexes', { value: regexLines.value })
    const saved = normalizeRegexText(data.value)
    regexText.value = saved
    savedRegexText.value = saved
    message.success(data.message ?? '已保存')
  } catch (error: any) {
    message.error(error?.response?.data?.message ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function resetRegexes() {
  saving.value = true
  try {
    const { data } = await api.delete('/settings/trigger_regexes')
    const reset = normalizeRegexText(data.value)
    regexText.value = reset
    savedRegexText.value = reset
    message.success('已恢复默认（不配置正则）')
  } catch (error: any) {
    message.error(error?.response?.data?.message ?? '恢复失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">设置</h1>
        <p class="page-subtitle">运行时可调项，保存后立即生效，无需重启</p>
      </div>
    </header>

    <section class="glass-panel-heavy settings-card">
      <div class="card-heading">
        <div>
          <h2>命令前缀</h2>
          <p class="card-hint">
            聊天里触发命令的前缀，例如改成 <code>!</code> 后发送 <code>!help</code>；<code>.</code> 始终兼容。
          </p>
        </div>
      </div>

      <div class="prefix-row">
        <NInput
          v-model:value="prefix"
          class="prefix-input"
          maxlength="3"
          show-count
          placeholder="."
          :disabled="loading || saving"
        />
        <NButton type="primary" :disabled="!canSave || loading" :loading="saving" @click="savePrefix">
          <template #icon><Save :size="16" /></template>
          保存
        </NButton>
        <NButton :disabled="loading || saving" @click="resetPrefix">
          <template #icon><RotateCcw :size="16" /></template>
          恢复默认
        </NButton>
      </div>

      <p class="preview">
        预览：<code>{{ prefix.trim() || '.' }}help</code> · <code>{{ prefix.trim() || '.' }}bot</code>
      </p>
      <p class="card-hint">支持 1–3 个字符，不能包含空格；中文句号「。」也会被自动识别为命令。</p>
    </section>

    <section class="glass-panel-heavy settings-card">
      <div class="card-heading">
        <div>
          <h2>触发正则</h2>
          <p class="card-hint">
            群聊消息只要匹配任意一条正则就会触发回复，不依赖 @ 或概率；私聊始终回复，不受影响。每行一条，最多 50 条。
          </p>
        </div>
      </div>

      <NInput
        v-model:value="regexText"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 14 }"
        placeholder="例如：&#10;^小助手&#10;帮我看看&#10;有(人|谁)在吗"
        :disabled="loading || saving"
      />

      <div class="prefix-row">
        <NButton type="primary" :disabled="!canSaveRegex || loading" :loading="saving" @click="saveRegexes">
          <template #icon><Save :size="16" /></template>
          保存
        </NButton>
        <NButton :disabled="loading || saving" @click="resetRegexes">
          <template #icon><RotateCcw :size="16" /></template>
          恢复默认
        </NButton>
        <span class="regex-count">{{ regexLines.length }} 条</span>
      </div>

      <p class="card-hint">
        使用 Python 正则语法，<code>search</code> 语义（无需匹配整句）。非法正则会被拒绝；保存后即时生效。
        也可以在聊天里用 <code>{{ prefix.trim() || '.' }}trigger regex add &lt;正则&gt;</code> 管理。
      </p>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 4px 2px 40px;
}

.settings-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-heading h2 {
  margin: 0 0 6px;
  font-size: 18px;
}

.card-hint {
  margin: 0;
  color: var(--text-color-3, #8a86a0);
  font-size: 13px;
  line-height: 1.6;
}

.prefix-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.prefix-input {
  max-width: 140px;
}

.preview {
  margin: 0;
  font-size: 13px;
  color: var(--text-color-2, #5c5870);
}

.regex-count {
  font-size: 12px;
  color: var(--text-color-3, #8a86a0);
}

code {
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(120, 110, 200, 0.12);
  font-size: 0.92em;
}
</style>
