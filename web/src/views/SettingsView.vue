<script setup lang="ts">
import {
  NButton,
  NEmpty,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { RotateCcw, Save } from 'lucide-vue-next'
import api from '@/api'

interface ConfigSpec {
  key: string
  type: 'str' | 'int' | 'float' | 'float?' | 'bool' | 'json'
  label: string
  group: string
  description: string
  default: unknown
  minimum: number | null
  maximum: number | null
  options: string[]
  requires_restart: boolean
  secret: boolean
}

const message = useMessage()

const SECRET_MASK = '********'
const TEXTAREA_KEYS = new Set(['llm_user_schema', 'llm_bot_schema', 'trigger_regexes', 'agent_workflow'])

const loading = ref(false)
const specs = ref<ConfigSpec[]>([])
const groups = ref<string[]>([])
const values = ref<Record<string, unknown>>({})
const drafts = ref<Record<string, unknown>>({})
const savingKey = ref('')

const groupedSpecs = computed(() => {
  const byGroup = new Map<string, ConfigSpec[]>()
  for (const spec of specs.value) {
    const list = byGroup.get(spec.group) ?? []
    list.push(spec)
    byGroup.set(spec.group, list)
  }
  const order = [...groups.value, ...byGroup.keys()]
  const result: Array<{ name: string; items: ConfigSpec[] }> = []
  const seen = new Set<string>()
  for (const name of order) {
    if (seen.has(name)) continue
    seen.add(name)
    const items = byGroup.get(name)
    if (items && items.length) result.push({ name, items })
  }
  return result
})

function errorText(error: any, fallback: string) {
  return error?.response?.data?.error ?? error?.response?.data?.message ?? fallback
}

function maskSecret(value: unknown) {
  return value === SECRET_MASK ? '' : String(value ?? '')
}

function normalizeDraft(spec: ConfigSpec, value: unknown) {
  if (spec.type === 'json') return JSON.stringify(value ?? spec.default ?? null, null, 2)
  if (spec.type === 'bool') return Boolean(value)
  if (spec.type === 'int' || spec.type === 'float' || spec.type === 'float?') {
    return value === null || value === undefined ? null : Number(value)
  }
  if (spec.secret) return maskSecret(value)
  return String(value ?? '')
}

function syncDraft(spec: ConfigSpec) {
  drafts.value[spec.key] = normalizeDraft(spec, values.value[spec.key])
}

function isDirty(spec: ConfigSpec) {
  return JSON.stringify(drafts.value[spec.key]) !== JSON.stringify(normalizeDraft(spec, values.value[spec.key]))
}

async function loadSettings() {
  loading.value = true
  try {
    const { data } = await api.get('/settings')
    specs.value = (data?.specs ?? []) as ConfigSpec[]
    groups.value = (data?.groups ?? []) as string[]
    values.value = { ...(data?.settings ?? {}) }
    const next: Record<string, unknown> = {}
    for (const spec of specs.value) next[spec.key] = normalizeDraft(spec, values.value[spec.key])
    drafts.value = next
  } catch (error: any) {
    message.error(errorText(error, '读取设置失败'))
  } finally {
    loading.value = false
  }
}

function coerceValue(spec: ConfigSpec, raw: unknown) {
  if (spec.type === 'bool') return Boolean(raw)
  if (spec.type === 'json') {
    try {
      return JSON.parse(String(raw ?? 'null'))
    } catch {
      throw new Error('JSON 格式不合法')
    }
  }
  if (spec.type === 'int' || spec.type === 'float') {
    const num = Number(raw)
    if (raw === null || raw === '' || !Number.isFinite(num)) throw new Error('请输入数字')
    return num
  }
  if (spec.type === 'float?') {
    if (raw === null || raw === '') return null
    const num = Number(raw)
    if (!Number.isFinite(num)) throw new Error('请输入数字或留空')
    return num
  }
  return String(raw ?? '').trim()
}

async function saveField(spec: ConfigSpec) {
  if (savingKey.value) return
  savingKey.value = spec.key
  try {
    const value = coerceValue(spec, drafts.value[spec.key])
    const { data } = await api.put(`/settings/${spec.key}`, { value })
    values.value[spec.key] = data?.value
    syncDraft(spec)
    message.success(data?.message ?? '已保存')
  } catch (error: any) {
    message.error(errorText(error, error?.message ?? '保存失败'))
  } finally {
    savingKey.value = ''
  }
}

async function resetField(spec: ConfigSpec) {
  if (savingKey.value) return
  savingKey.value = spec.key
  try {
    const { data } = await api.delete(`/settings/${spec.key}`)
    values.value[spec.key] = data?.value
    syncDraft(spec)
    message.success('已恢复默认')
  } catch (error: any) {
    message.error(errorText(error, '恢复失败'))
  } finally {
    savingKey.value = ''
  }
}

function stringOptions(spec: ConfigSpec) {
  return spec.options.map((option) => ({ label: option, value: option }))
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">设置</h1>
        <p class="page-subtitle">所有运行时配置都可在这里修改；保存后立即生效，标注「重启生效」的项在重启后生效</p>
      </div>
      <div class="page-actions">
        <NButton :loading="loading" @click="loadSettings">
          <template #icon><RotateCcw :size="16" /></template>
          重新读取
        </NButton>
      </div>
    </header>

    <NEmpty v-if="!loading && !specs.length" description="没有可配置项" />

    <section v-for="group in groupedSpecs" :key="group.name" class="glass-panel-heavy settings-card">
      <div class="card-heading">
        <h2>{{ group.name }}</h2>
      </div>

      <div class="field-list">
        <div v-for="spec in group.items" :key="spec.key" class="field-row">
          <div class="field-meta">
            <div class="field-label">
              {{ spec.label }}
              <NTag v-if="spec.requires_restart" size="tiny" :bordered="false" type="warning">重启生效</NTag>
            </div>
            <div class="field-key">{{ spec.key }}</div>
            <div v-if="spec.description" class="field-desc">{{ spec.description }}</div>
          </div>

          <div class="field-control">
            <NSwitch
              v-if="spec.type === 'bool'"
              :value="Boolean(drafts[spec.key])"
              :disabled="loading || !!savingKey"
              @update:value="(value) => (drafts[spec.key] = value)"
            />
            <NInputNumber
              v-else-if="spec.type === 'int' || spec.type === 'float' || spec.type === 'float?'"
              :value="drafts[spec.key] as number | null"
              class="number-input"
              :min="spec.minimum ?? undefined"
              :max="spec.maximum ?? undefined"
              :step="spec.type === 'int' ? 1 : 0.1"
              :precision="spec.type === 'int' ? 0 : undefined"
              :clearable="spec.type === 'float?'"
              :placeholder="spec.type === 'float?' ? '留空表示不传' : ''"
              :disabled="loading || !!savingKey"
              @update:value="(value) => (drafts[spec.key] = value)"
            />
            <NSelect
              v-else-if="spec.options.length"
              :value="String(drafts[spec.key] ?? '')"
              :options="stringOptions(spec)"
              :disabled="loading || !!savingKey"
              @update:value="(value) => (drafts[spec.key] = value)"
            />
            <NInput
              v-else-if="TEXTAREA_KEYS.has(spec.key) || spec.type === 'json'"
              :value="String(drafts[spec.key] ?? '')"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 12 }"
              :placeholder="spec.default === null || spec.default === undefined ? '' : String(spec.default)"
              :disabled="loading || !!savingKey"
              @update:value="(value) => (drafts[spec.key] = value)"
            />
            <NInput
              v-else
              :value="String(drafts[spec.key] ?? '')"
              :type="spec.secret ? 'password' : 'text'"
              :show-password-on="spec.secret ? 'click' : undefined"
              :placeholder="spec.secret ? '已设置则留空，输入新值可覆盖' : String(spec.default ?? '')"
              :disabled="loading || !!savingKey"
              @update:value="(value) => (drafts[spec.key] = value)"
            />
          </div>

          <div class="field-actions">
            <NButton
              size="small"
              type="primary"
              :disabled="!isDirty(spec) || !!savingKey"
              :loading="savingKey === spec.key"
              @click="saveField(spec)"
            >
              <template #icon><Save :size="14" /></template>
              保存
            </NButton>
            <NButton size="small" :disabled="!!savingKey" @click="resetField(spec)">
              默认
            </NButton>
          </div>
        </div>
      </div>
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
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card-heading h2 {
  margin: 0;
  font-size: 17px;
}

.field-list {
  display: flex;
  flex-direction: column;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(240px, 1.6fr) auto;
  gap: 14px;
  align-items: start;
  padding: 12px 0;
  border-top: 1px solid rgba(140, 130, 200, 0.12);
}

.field-row:first-child {
  border-top: none;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.field-key {
  margin-top: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--text-color-3, #8a86a0);
}

.field-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-color-3, #8a86a0);
}

.field-control {
  display: flex;
  align-items: center;
  min-width: 0;
}

.field-control > * {
  width: 100%;
}

.number-input {
  max-width: 220px;
}

.field-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 900px) {
  .field-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>
