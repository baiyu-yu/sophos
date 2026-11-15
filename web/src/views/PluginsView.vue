<script setup lang="ts">
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NRadioButton,
  NRadioGroup,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useDialog,
  useMessage,
  type UploadFileInfo,
} from 'naive-ui'
import {
  ExternalLink,
  PackageOpen,
  RefreshCw,
  RotateCw,
  Settings2,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'

interface PluginInfo {
  name: string
  version: string
  description: string
  author: string
  homepage: string
  enabled: boolean
  status: 'loaded' | 'disabled' | 'failed'
  error: string | null
  tools: string[]
  config: Record<string, any>
  default_config: Record<string, any>
  path: string | null
  source: 'directory' | 'file' | 'entry_point'
}

interface ConfigField {
  key: string
  kind: 'bool' | 'number' | 'string' | 'json'
}

const message = useMessage()
const dialog = useDialog()
const route = useRoute()

const plugins = ref<PluginInfo[]>([])
const pluginsDir = ref('')
const loading = ref(false)
const busyNames = reactive<Record<string, boolean>>({})
const reloadingAll = ref(false)

// ── 上传 ──
const uploadVisible = ref(false)
const uploadFile = ref<File | null>(null)
const overwrite = ref(false)
const uploading = ref(false)

// ── 配置 ──
const configVisible = ref(false)
const configPlugin = ref<PluginInfo | null>(null)
const configFields = ref<ConfigField[]>([])
const formDraft = reactive<Record<string, any>>({})
const jsonText = ref('')
const configMode = ref<'form' | 'json'>('form')
const savingConfig = ref(false)

const loadedCount = computed(() => plugins.value.filter((p) => p.status === 'loaded').length)

const statusMeta: Record<string, { label: string; type: 'success' | 'warning' | 'error' | 'default' }> = {
  loaded: { label: '运行中', type: 'success' },
  disabled: { label: '已停用', type: 'default' },
  failed: { label: '加载失败', type: 'error' },
}

function errorText(error: any, fallback: string): string {
  return error?.response?.data?.reason ?? error?.response?.data?.message ?? fallback
}

function replacePlugin(updated: PluginInfo) {
  const index = plugins.value.findIndex((item) => item.name === updated.name)
  if (index === -1) {
    plugins.value.push(updated)
  } else {
    plugins.value[index] = updated
  }
}

async function loadPlugins() {
  loading.value = true
  try {
    const { data } = await api.get('/plugins')
    plugins.value = data.plugins as PluginInfo[]
    pluginsDir.value = data.plugins_dir as string
  } catch (error: any) {
    message.error(errorText(error, '加载插件列表失败'))
  } finally {
    loading.value = false
  }
}

async function togglePlugin(plugin: PluginInfo, enabled: boolean) {
  busyNames[plugin.name] = true
  try {
    const { data } = await api.put(`/plugins/${encodeURIComponent(plugin.name)}/enabled`, { enabled })
    replacePlugin(data.plugin as PluginInfo)
    message.success(data.message ?? '已更新插件状态')
  } catch (error: any) {
    message.error(errorText(error, '更新插件状态失败'))
  } finally {
    busyNames[plugin.name] = false
  }
}

async function reloadPlugin(plugin: PluginInfo) {
  busyNames[plugin.name] = true
  try {
    const { data } = await api.post(`/plugins/${encodeURIComponent(plugin.name)}/reload`)
    replacePlugin(data.plugin as PluginInfo)
    message.success(data.message ?? '插件已重载')
  } catch (error: any) {
    message.error(errorText(error, '重载插件失败'))
  } finally {
    busyNames[plugin.name] = false
  }
}

async function reloadAll() {
  reloadingAll.value = true
  try {
    const { data } = await api.post('/plugins/reload')
    plugins.value = data.plugins as PluginInfo[]
    message.success(data.message ?? '插件已重新加载')
  } catch (error: any) {
    message.error(errorText(error, '重新加载插件失败'))
  } finally {
    reloadingAll.value = false
  }
}

function confirmUninstall(plugin: PluginInfo) {
  dialog.warning({
    title: '删除插件',
    content: `确定删除插件「${plugin.name}」吗？插件文件、启用状态与配置都会被移除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      busyNames[plugin.name] = true
      try {
        const { data } = await api.delete(`/plugins/${encodeURIComponent(plugin.name)}`)
        plugins.value = data.plugins as PluginInfo[]
        message.success(data.message ?? '插件已删除')
      } catch (error: any) {
        message.error(errorText(error, '删除插件失败'))
      } finally {
        busyNames[plugin.name] = false
      }
    },
  })
}

// ── 上传 ──
function openUpload() {
  uploadFile.value = null
  overwrite.value = false
  uploadVisible.value = true
}

function onFileChange({ fileList }: { fileList: UploadFileInfo[] }) {
  uploadFile.value = fileList[0]?.file ?? null
}

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function submitUpload() {
  if (!uploadFile.value) {
    message.warning('请先选择插件文件')
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', uploadFile.value, uploadFile.value.name)
    const { data } = await api.post(`/plugins/upload?overwrite=${overwrite.value ? 'true' : 'false'}`, form, {
      timeout: 120_000,
    })
    replacePlugin(data.plugin as PluginInfo)
    uploadVisible.value = false
    message.success(data.message ?? '插件已安装')
  } catch (error: any) {
    message.error(errorText(error, '上传插件失败'))
  } finally {
    uploading.value = false
  }
}

// ── 配置 ──
function fieldKind(value: unknown): ConfigField['kind'] {
  if (typeof value === 'boolean') return 'bool'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'string') return 'string'
  return 'json'
}

function mergedConfig(plugin: PluginInfo): Record<string, any> {
  return { ...plugin.default_config, ...plugin.config }
}

function openConfig(plugin: PluginInfo) {
  configPlugin.value = plugin
  const merged = mergedConfig(plugin)
  configFields.value = Object.keys(merged)
    .sort()
    .map((key) => ({ key, kind: fieldKind(merged[key]) }))
  for (const key of Object.keys(formDraft)) delete formDraft[key]
  for (const field of configFields.value) {
    const value = merged[field.key]
    formDraft[field.key] = field.kind === 'json' ? JSON.stringify(value ?? null, null, 2) : value
  }
  jsonText.value = JSON.stringify(merged, null, 2)
  configMode.value = 'form'
  configVisible.value = true
}

function resetConfig() {
  if (!configPlugin.value) return
  const defaults = configPlugin.value.default_config
  for (const field of configFields.value) {
    const value = defaults[field.key]
    formDraft[field.key] = field.kind === 'json' ? JSON.stringify(value ?? null, null, 2) : value
  }
  jsonText.value = JSON.stringify(defaults, null, 2)
  message.info('已恢复为默认值，保存后生效')
}

function buildConfig(): Record<string, any> | null {
  if (configMode.value === 'json') {
    try {
      const parsed = JSON.parse(jsonText.value)
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        message.error('配置必须是 JSON 对象')
        return null
      }
      return parsed as Record<string, any>
    } catch {
      message.error('配置 JSON 格式不正确')
      return null
    }
  }
  const result: Record<string, any> = {}
  for (const field of configFields.value) {
    const value = formDraft[field.key]
    if (field.kind === 'json') {
      try {
        result[field.key] = JSON.parse(value)
      } catch {
        message.error(`字段「${field.key}」不是合法的 JSON`)
        return null
      }
    } else {
      result[field.key] = value
    }
  }
  return result
}

async function saveConfig() {
  if (!configPlugin.value) return
  const config = buildConfig()
  if (config === null) return
  savingConfig.value = true
  try {
    const { data } = await api.put(`/plugins/${encodeURIComponent(configPlugin.value.name)}/config`, { config })
    replacePlugin(data.plugin as PluginInfo)
    configVisible.value = false
    message.success(data.message ?? '配置已保存')
  } catch (error: any) {
    message.error(errorText(error, '保存插件配置失败'))
  } finally {
    savingConfig.value = false
  }
}

onMounted(async () => {
  await loadPlugins()
  if (route.query.upload) openUpload()
})
</script>

<template>
  <div class="plugins-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">插件</h1>
        <p class="page-subtitle">上传插件即可扩展工具能力；插件的启停与配置都在这里管理</p>
      </div>
      <div class="page-actions glass-panel">
        <NSpace align="center" :size="12">
          <NText depth="3">{{ loadedCount }} / {{ plugins.length }} 已加载</NText>
          <NButton quaternary :loading="reloadingAll" @click="reloadAll">
            <template #icon><RefreshCw :size="16" /></template>
            重新扫描
          </NButton>
          <NButton type="primary" @click="openUpload">
            <template #icon><Upload :size="16" /></template>
            上传插件
          </NButton>
        </NSpace>
      </div>
    </div>

    <NAlert v-if="pluginsDir" type="default" :bordered="false" class="plugins-dir">
      插件目录：<code>{{ pluginsDir }}</code>
    </NAlert>

    <div v-if="plugins.length" class="plugins-grid">
      <NCard
        v-for="plugin in plugins"
        :key="plugin.name"
        class="plugin-card glass-panel-heavy"
        :bordered="false"
      >
        <div class="plugin-card__top">
          <div class="plugin-title">
            <div class="plugin-icon">
              <PackageOpen :size="20" />
            </div>
            <div class="plugin-title__text">
              <div class="plugin-name-row">
                <h2 class="plugin-name">{{ plugin.name }}</h2>
                <NTag size="small" :bordered="false" round>v{{ plugin.version }}</NTag>
                <NTag size="small" :bordered="false" round type="info">{{ plugin.source }}</NTag>
                <NTag
                  size="small"
                  :bordered="false"
                  round
                  :type="statusMeta[plugin.status]?.type ?? 'default'"
                >
                  {{ statusMeta[plugin.status]?.label ?? plugin.status }}
                </NTag>
              </div>
              <p class="plugin-description">{{ plugin.description || '未提供描述' }}</p>
            </div>
          </div>

          <div class="plugin-actions">
            <NSwitch
              :value="plugin.enabled"
              :loading="busyNames[plugin.name]"
              @update:value="(value: boolean) => togglePlugin(plugin, value)"
            />
            <NButton quaternary circle title="配置" @click="openConfig(plugin)">
              <template #icon><Settings2 :size="18" /></template>
            </NButton>
            <NButton
              quaternary
              circle
              title="重载"
              :loading="busyNames[plugin.name]"
              @click="reloadPlugin(plugin)"
            >
              <template #icon><RotateCw :size="18" /></template>
            </NButton>
            <NButton quaternary circle title="删除" @click="confirmUninstall(plugin)">
              <template #icon><Trash2 :size="18" /></template>
            </NButton>
          </div>
        </div>

        <div v-if="plugin.error" class="plugin-error">
          <NAlert type="error" :bordered="false" :show-icon="false">{{ plugin.error }}</NAlert>
        </div>

        <div class="plugin-meta">
          <div class="plugin-meta-item">
            <span class="plugin-meta-label">工具</span>
            <div v-if="plugin.tools.length" class="plugin-tools">
              <NTag v-for="tool in plugin.tools" :key="tool" size="small" :bordered="false">
                {{ tool }}
              </NTag>
            </div>
            <NText v-else depth="3">未注册工具</NText>
          </div>
          <div class="plugin-meta-item plugin-meta-item--right">
            <span v-if="plugin.author" class="plugin-meta-label">{{ plugin.author }}</span>
            <a
              v-if="plugin.homepage"
              class="plugin-link"
              :href="plugin.homepage"
              target="_blank"
              rel="noreferrer"
            >
              主页
              <ExternalLink :size="14" />
            </a>
          </div>
        </div>
      </NCard>
    </div>

    <NEmpty
      v-else-if="!loading"
      class="plugins-empty glass-panel-heavy"
      description="还没有安装插件"
    >
      <template #extra>
        <NButton type="primary" @click="openUpload">
          <template #icon><Upload :size="16" /></template>
          上传第一个插件
        </NButton>
      </template>
    </NEmpty>

    <!-- 上传弹窗 -->
    <NModal
      v-model:show="uploadVisible"
      preset="card"
      title="上传插件"
      class="plugin-modal"
      :style="{ width: '520px', maxWidth: '92vw' }"
    >
      <NSpace vertical :size="14">
        <NAlert type="info" :bordered="false">
          支持 <code>.zip</code> 目录插件包（压缩包内需包含 <code>plugin.py</code>）或单个
          <code>.py</code> 文件。上传后立即加载，插件默认启用。
        </NAlert>
        <NUpload :default-upload="false" :max="1" accept=".zip,.py" @change="onFileChange">
          <NButton dashed>
            <template #icon><Upload :size="16" /></template>
            选择文件
          </NButton>
        </NUpload>
        <NText v-if="uploadFile" depth="2">
          {{ uploadFile.name }}（{{ formatSize(uploadFile.size) }}）
        </NText>
        <NCheckbox v-model:checked="overwrite">覆盖同名插件</NCheckbox>
      </NSpace>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="uploadVisible = false">取消</NButton>
          <NButton type="primary" :loading="uploading" @click="submitUpload">上传并启用</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 配置弹窗 -->
    <NModal
      v-model:show="configVisible"
      preset="card"
      :title="configPlugin ? `配置：${configPlugin.name}` : '配置'"
      class="plugin-modal"
      :style="{ width: '620px', maxWidth: '94vw' }"
    >
      <NSpace vertical :size="14">
        <NRadioGroup v-model:value="configMode" size="small">
          <NRadioButton value="form">表单</NRadioButton>
          <NRadioButton value="json">JSON</NRadioButton>
        </NRadioGroup>

        <NForm v-if="configMode === 'form'" label-placement="left" label-width="150" :show-feedback="false">
          <NFormItem v-for="field in configFields" :key="field.key" :label="field.key">
            <NSwitch v-if="field.kind === 'bool'" v-model:value="formDraft[field.key]" />
            <NInputNumber
              v-else-if="field.kind === 'number'"
              v-model:value="formDraft[field.key]"
              style="width: 100%"
            />
            <NInput v-else-if="field.kind === 'string'" v-model:value="formDraft[field.key]" />
            <NInput
              v-else
              v-model:value="formDraft[field.key]"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 10 }"
            />
          </NFormItem>
          <NEmpty v-if="!configFields.length" description="该插件没有可配置项" />
        </NForm>

        <NInput
          v-else
          v-model:value="jsonText"
          type="textarea"
          :autosize="{ minRows: 12, maxRows: 24 }"
          placeholder="{}"
        />
      </NSpace>
      <template #footer>
        <NSpace justify="space-between" align="center">
          <NButton quaternary @click="resetConfig">恢复默认</NButton>
          <NSpace>
            <NButton @click="configVisible = false">取消</NButton>
            <NButton type="primary" :loading="savingConfig" @click="saveConfig">保存</NButton>
          </NSpace>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.plugins-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-actions {
  padding: 10px 14px;
  flex-shrink: 0;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 600;
}

.page-subtitle {
  margin-top: 6px;
  opacity: 0.68;
}

.plugins-dir {
  font-size: 0.85rem;
}

.plugins-dir code {
  font-family: 'Maple Mono CN', monospace;
  opacity: 0.85;
}

.plugins-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.plugin-card {
  padding: 18px;
}

.plugin-card :deep(.n-card__content) {
  padding: 0;
}

.plugin-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.plugin-title {
  display: flex;
  gap: 12px;
  min-width: 0;
}

.plugin-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, rgba(120, 160, 255, 0.25), rgba(120, 160, 255, 0.08));
  color: #6f8dff;
}

.plugin-title__text {
  min-width: 0;
}

.plugin-name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.plugin-name {
  font-size: 1.05rem;
  font-weight: 600;
}

.plugin-description {
  margin-top: 6px;
  opacity: 0.72;
  font-size: 0.9rem;
}

.plugin-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.plugin-error {
  margin-top: 12px;
}

.plugin-meta {
  margin-top: 14px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.plugin-meta-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.plugin-meta-item--right {
  margin-left: auto;
}

.plugin-meta-label {
  font-size: 0.82rem;
  opacity: 0.6;
}

.plugin-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.plugin-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: inherit;
  opacity: 0.7;
  text-decoration: none;
}

.plugin-link:hover {
  opacity: 1;
  text-decoration: underline;
}

.plugins-empty {
  padding: 48px 16px;
}

.plugin-modal :deep(.n-card__content) {
  padding-top: 8px;
}

@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-actions {
    width: 100%;
  }

  .plugin-card__top {
    flex-direction: column;
  }

  .plugin-actions {
    align-self: flex-end;
  }
}
</style>
