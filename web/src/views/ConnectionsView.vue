<script setup lang="ts">
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useDialog,
  useMessage,
} from 'naive-ui'
import {
  Plug,
  Plus,
  RefreshCw,
  RotateCw,
  Settings2,
  Square,
  Trash2,
  Play,
} from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import api from '@/api'

type ConnectionState = 'connected' | 'connecting' | 'stopped' | 'error'

interface ConnectionInfo {
  id: number
  name: string
  ws_url: string
  enabled: boolean
  auto_reconnect: boolean
  reconnect_interval: number
  has_token: boolean
  state: ConnectionState
  error: string
  attempts: number
  connected_at: string
  self_id: string
  nickname: string
}

interface ConnectionForm {
  name: string
  ws_url: string
  token: string
  enabled: boolean
  auto_reconnect: boolean
  reconnect_interval: number
}

const message = useMessage()
const dialog = useDialog()

const connections = ref<ConnectionInfo[]>([])
const loading = ref(false)
const busyIds = reactive<Record<number, boolean>>({})

const modalVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<ConnectionForm>({
  name: '',
  ws_url: 'ws://',
  token: '',
  enabled: true,
  auto_reconnect: true,
  reconnect_interval: 5,
})

const stateMeta: Record<ConnectionState, { label: string; type: 'success' | 'warning' | 'error' | 'default' }> = {
  connected: { label: '已连接', type: 'success' },
  connecting: { label: '连接中', type: 'warning' },
  stopped: { label: '已停止', type: 'default' },
  error: { label: '连接失败', type: 'error' },
}

const connectedCount = computed(
  () => connections.value.filter((item) => item.state === 'connected').length,
)

let timer: ReturnType<typeof setInterval> | null = null

async function loadConnections() {
  loading.value = true
  try {
    const { data } = await api.get('/connections')
    connections.value = (data.connections ?? []) as ConnectionInfo[]
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '加载连接列表失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.ws_url = 'ws://'
  form.token = ''
  form.enabled = true
  form.auto_reconnect = true
  form.reconnect_interval = 5
  modalVisible.value = true
}

function openEdit(connection: ConnectionInfo) {
  editingId.value = connection.id
  form.name = connection.name
  form.ws_url = connection.ws_url
  form.token = ''
  form.enabled = connection.enabled
  form.auto_reconnect = connection.auto_reconnect
  form.reconnect_interval = connection.reconnect_interval
  modalVisible.value = true
}

async function saveConnection() {
  if (!form.name.trim()) {
    message.warning('请填写连接名称')
    return
  }
  if (!/^wss?:\/\//.test(form.ws_url.trim())) {
    message.warning('WebSocket 地址需要以 ws:// 或 wss:// 开头')
    return
  }
  saving.value = true
  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    ws_url: form.ws_url.trim(),
    enabled: form.enabled,
    auto_reconnect: form.auto_reconnect,
    reconnect_interval: form.reconnect_interval,
  }
  if (form.token) payload.token = form.token
  try {
    if (editingId.value === null) {
      await api.post('/connections', payload)
      message.success('连接已创建')
    } else {
      await api.put(`/connections/${editingId.value}`, payload)
      message.success('连接已更新')
    }
    modalVisible.value = false
    await loadConnections()
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '保存连接失败')
  } finally {
    saving.value = false
  }
}

async function startConnection(connection: ConnectionInfo) {
  busyIds[connection.id] = true
  try {
    const { data } = await api.post(`/connections/${connection.id}/start`)
    message.success(data.message ?? '正在连接')
    await loadConnections()
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '启动连接失败')
  } finally {
    busyIds[connection.id] = false
  }
}

async function stopConnection(connection: ConnectionInfo) {
  busyIds[connection.id] = true
  try {
    const { data } = await api.post(`/connections/${connection.id}/stop`)
    message.success(data.message ?? '已停止')
    await loadConnections()
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '停止连接失败')
  } finally {
    busyIds[connection.id] = false
  }
}

async function restartConnection(connection: ConnectionInfo) {
  busyIds[connection.id] = true
  try {
    const { data } = await api.post(`/connections/${connection.id}/restart`)
    message.success(data.message ?? '正在重连')
    await loadConnections()
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '重连失败')
  } finally {
    busyIds[connection.id] = false
  }
}

async function toggleAutoReconnect(connection: ConnectionInfo, value: boolean) {
  try {
    await api.put(`/connections/${connection.id}`, { auto_reconnect: value })
    connection.auto_reconnect = value
  } catch (error: any) {
    message.error(error?.response?.data?.reason ?? '更新自动重连失败')
    await loadConnections()
  }
}

function confirmDelete(connection: ConnectionInfo) {
  dialog.warning({
    title: '删除连接',
    content: `确定删除「${connection.name}」吗？当前连接会被立即断开，自动重连也会停止。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const { data } = await api.delete(`/connections/${connection.id}`)
        connections.value = (data.connections ?? []) as ConnectionInfo[]
        message.success(data.message ?? '连接已删除')
      } catch (error: any) {
        message.error(error?.response?.data?.reason ?? '删除连接失败')
      }
    },
  })
}

onMounted(async () => {
  await loadConnections()
  timer = setInterval(() => {
    void loadConnections()
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="connections-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">协议端连接</h1>
        <p class="page-subtitle">
          管理 OneBot WebSocket 连接，可随时新增、修改、停止重连或删除
        </p>
      </div>
      <div class="page-actions glass-panel">
        <NSpace align="center" :size="12">
          <NText depth="3">{{ connectedCount }} / {{ connections.length }} 已连接</NText>
          <NButton size="small" :loading="loading" @click="loadConnections">
            <template #icon>
              <component :is="RefreshCw" :size="16" />
            </template>
            刷新
          </NButton>
          <NButton size="small" type="primary" @click="openCreate">
            <template #icon>
              <component :is="Plus" :size="16" />
            </template>
            新增连接
          </NButton>
        </NSpace>
      </div>
    </div>

    <NAlert v-if="!connections.length" type="info" :bordered="false" class="seed-hint">
      还没有连接。首次启动会从 <code>ONEBOT_WS_URL</code> 生成一条默认连接，也可以点右上角
      「新增连接」手动添加。
    </NAlert>

    <div class="connection-grid">
      <NCard
        v-for="connection in connections"
        :key="connection.id"
        class="connection-card glass-panel-heavy"
        :bordered="false"
      >
        <template #header>
          <div class="card-head">
            <component :is="Plug" :size="20" class="card-icon" />
            <span class="card-name">{{ connection.name }}</span>
            <NTag size="small" :bordered="false" :type="stateMeta[connection.state].type">
              {{ stateMeta[connection.state].label }}
            </NTag>
          </div>
        </template>

        <div class="card-body">
          <code class="ws-url">{{ connection.ws_url }}</code>
          <div class="meta-row">
            <span class="meta-label">机器人</span>
            <span v-if="connection.self_id">
              {{ connection.nickname || '未命名' }}（{{ connection.self_id }}）
            </span>
            <span v-else class="muted">连接后自动获取</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Token</span>
            <NTag v-if="connection.has_token" size="tiny" :bordered="false" type="success">已配置</NTag>
            <span v-else class="muted">未配置</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">自动重连</span>
            <NSwitch
              :value="connection.auto_reconnect"
              @update:value="(value: boolean) => toggleAutoReconnect(connection, value)"
            />
            <span class="muted">间隔 {{ connection.reconnect_interval }}s</span>
          </div>

          <NAlert
            v-if="connection.state === 'error' && connection.error"
            type="error"
            :bordered="false"
            class="error-box"
          >
            {{ connection.error }}
          </NAlert>
          <NAlert
            v-else-if="connection.state === 'stopped' && !connection.auto_reconnect"
            type="warning"
            :bordered="false"
            class="error-box"
          >
            已手动停止，不会自动重连；点「启动」恢复。
          </NAlert>
        </div>

        <template #footer>
          <NSpace :size="8" justify="end">
            <NButton
              v-if="connection.state === 'connected' || connection.state === 'connecting'"
              size="small"
              :loading="busyIds[connection.id]"
              @click="stopConnection(connection)"
            >
              <template #icon>
                <component :is="Square" :size="14" />
              </template>
              停止
            </NButton>
            <NButton
              v-else
              size="small"
              type="primary"
              :loading="busyIds[connection.id]"
              @click="startConnection(connection)"
            >
              <template #icon>
                <component :is="Play" :size="14" />
              </template>
              启动
            </NButton>
            <NButton size="small" :loading="busyIds[connection.id]" @click="restartConnection(connection)">
              <template #icon>
                <component :is="RotateCw" :size="14" />
              </template>
              重连
            </NButton>
            <NButton size="small" @click="openEdit(connection)">
              <template #icon>
                <component :is="Settings2" :size="14" />
              </template>
              编辑
            </NButton>
            <NButton size="small" quaternary type="error" @click="confirmDelete(connection)">
              <template #icon>
                <component :is="Trash2" :size="14" />
              </template>
            </NButton>
          </NSpace>
        </template>
      </NCard>
    </div>

    <NEmpty
      v-if="!connections.length && !loading"
      class="empty-state"
      description="暂无连接，点击「新增连接」开始"
    />

    <NModal v-model:show="modalVisible" preset="card" class="connection-modal" :title="editingId === null ? '新增连接' : '编辑连接'">
      <NForm label-placement="left" label-width="110">
        <NFormItem label="名称">
          <NInput v-model:value="form.name" placeholder="例如：主机器人" />
        </NFormItem>
        <NFormItem label="WebSocket 地址">
          <NInput v-model:value="form.ws_url" placeholder="ws://127.0.0.1:3001" />
        </NFormItem>
        <NFormItem label="Token">
          <NInput
            v-model:value="form.token"
            type="password"
            show-password-on="click"
            :placeholder="editingId === null ? '可选，与 NapCat 配置一致' : '留空表示不修改'"
          />
        </NFormItem>
        <NFormItem label="启用">
          <NSwitch v-model:value="form.enabled" />
        </NFormItem>
        <NFormItem label="自动重连">
          <NSwitch v-model:value="form.auto_reconnect" />
        </NFormItem>
        <NFormItem label="重连间隔（秒）">
          <NInputNumber v-model:value="form.reconnect_interval" :min="1" :max="600" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="modalVisible = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="saveConnection">保存</NButton>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.connections-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-bottom: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 650;
}

.page-subtitle {
  margin: 6px 0 0;
  color: var(--n-text-color-3, #888);
  font-size: 13px;
}

.page-actions {
  padding: 8px 12px;
  border-radius: 12px;
}

.seed-hint {
  border-radius: 12px;
}

.connection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.connection-card {
  border-radius: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-icon {
  opacity: 0.75;
}

.card-name {
  font-weight: 600;
  font-size: 15px;
}

.ws-url {
  display: block;
  font-size: 12px;
  word-break: break-all;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.12);
  margin-bottom: 10px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.meta-label {
  width: 64px;
  color: var(--n-text-color-3, #888);
}

.muted {
  color: var(--n-text-color-3, #888);
  font-size: 12px;
}

.error-box {
  border-radius: 10px;
  margin-top: 4px;
}

.empty-state {
  padding: 48px 0;
}

.connection-modal {
  width: 460px;
  max-width: 92vw;
}

@media (max-width: 767px) {
  .connection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
