<script setup>
/**
 * AI 提供商配置组件 — 提供商选择、API Key、测试连接、模型、高级参数。
 * 接收 aiConfig 等 reactive 对象作为 props，通过 testProvider 函数回调测试。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { testProvider } from '../api/convert.js'

const props = defineProps({
  aiConfig:       { type: Object, required: true },
  providerList:   { type: Array,  required: true },
  currentProvider:{ type: Object, default: null },
  modelOptions:   { type: Array,  default: () => [] },
  aiPresets:      { type: Object, default: () => ({}) },
})

const emit = defineEmits(['connection-tested'])

const showAIKey = ref(false)
const showAISettings = ref(false)
const testStatus  = ref('')
const testMessage = ref('')
const testLatency = ref(null)

function applyAIPreset(key) {
  const p = props.aiPresets[key]
  if (!p) return
  props.aiConfig.temperature = p.temperature
  props.aiConfig.top_p = p.top_p
  ElMessage.success(`已切换至：${p.label}`)
}

async function onTestConnection() {
  if (!props.aiConfig.api_key) {
    ElMessage.warning('请先填写 API Key')
    return
  }

  testStatus.value = 'testing'
  testMessage.value = '正在测试连接...'
  testLatency.value = null

  try {
    const res = await testProvider({
      provider: props.aiConfig.provider,
      api_key: props.aiConfig.api_key,
      base_url: props.aiConfig.base_url || undefined,
      model: props.aiConfig.model || undefined,
    })

    testStatus.value = res.ok ? 'ok' : 'fail'
    testMessage.value = res.message
    testLatency.value = res.latency_ms

    if (res.ok) {
      const count = res.available_models?.length || 0
      ElMessage.success(count ? `连接成功！发现 ${count} 个模型` : '连接成功！API Key 有效')
      showAISettings.value = true
      emit('connection-tested', { models: res.available_models || [] })
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    testStatus.value = 'fail'
    testMessage.value = err.response?.data?.detail || err.message || '测试请求失败'
    testLatency.value = null
    ElMessage.error(testMessage.value)
    emit('connection-tested', { models: [] })
  }
}
</script>

<template>
  <div>
    <!-- 区隔线 -->
    <div class="config-divider"><span>🤖 AI 提供商</span></div>

    <!-- 提供商 -->
    <div class="config-group">
      <el-select v-model="aiConfig.provider" size="small">
        <el-option v-for="p in providerList" :key="p.key" :label="p.name" :value="p.key" />
      </el-select>
    </div>

    <!-- API Key -->
    <div class="config-group">
      <el-input
        v-model="aiConfig.api_key"
        :type="showAIKey ? 'text' : 'password'"
        :placeholder="currentProvider ? `输入 ${currentProvider.name} API Key...` : 'sk-...'"
        size="small" clearable
      >
        <template #prefix><span style="font-size:12px">🔑</span></template>
        <template #suffix>
          <span class="key-toggle" @click="showAIKey = !showAIKey">{{ showAIKey ? '🙈' : '👁️' }}</span>
        </template>
      </el-input>
    </div>

    <!-- Base URL + 测试连接 -->
    <div class="config-group">
      <el-input v-model="aiConfig.base_url" :placeholder="currentProvider?.default_base_url || 'https://api...'" size="small" clearable>
        <template #prefix><span style="font-size:12px">🔗</span></template>
      </el-input>
      <div class="test-row" style="margin-top:4px">
        <el-button
          :type="testStatus === 'ok' ? 'success' : testStatus === 'fail' ? 'danger' : 'default'"
          size="small" :loading="testStatus === 'testing'" :disabled="!aiConfig.api_key"
          @click="onTestConnection" style="width:100%"
        >
          {{ testStatus === 'testing' ? '测试中...' : testStatus === 'ok' ? '✅ 连接成功' : testStatus === 'fail' ? '❌ 连接失败' : '🔍 测试连接' }}
        </el-button>
      </div>
      <span class="test-info" v-if="testLatency !== null && testStatus === 'ok'" style="font-size:11px;color:var(--success);margin-top:2px">
        延迟 {{ testLatency }}ms
      </span>
      <span class="test-msg" v-if="testMessage" :class="testStatus" style="margin-top:2px">{{ testMessage }}</span>
    </div>

    <!-- 模型 -->
    <div class="config-group">
      <el-select v-model="aiConfig.model" size="small" filterable allow-create placeholder="选择或输入模型名">
        <el-option v-for="opt in modelOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <!-- 高级设置 -->
    <div class="config-section">
      <div class="section-header" @click="showAISettings = !showAISettings">
        <span>⚙️ 高级参数</span>
        <span class="section-toggle">{{ showAISettings ? '▾' : '▸' }}</span>
      </div>
      <div class="section-body" v-show="showAISettings">
        <!-- 快速预设 -->
        <div class="config-group">
          <label>🎯 快速预设</label>
          <div class="preset-btns">
            <button
              v-for="(p, key) in aiPresets" :key="key"
              class="preset-btn"
              :class="{ active: aiConfig.temperature === p.temperature && aiConfig.top_p === p.top_p }"
              @click="applyAIPreset(key)"
            >{{ p.label }}</button>
          </div>
        </div>

        <!-- Temperature -->
        <div class="config-group">
          <label>🌡️ Temperature <code>{{ aiConfig.temperature.toFixed(1) }}</code></label>
          <el-slider v-model="aiConfig.temperature" :min="0" :max="2" :step="0.1"
            :marks="{ 0: '0', 0.5: '0.5', 1: '1', 1.5: '1.5', 2: '2' }" size="small" />
        </div>

        <!-- Top P -->
        <div class="config-group">
          <label>🎲 Top P <code>{{ aiConfig.top_p.toFixed(2) }}</code></label>
          <el-slider v-model="aiConfig.top_p" :min="0" :max="1" :step="0.05"
            :marks="{ 0: '0', 0.5: '0.5', 1: '1' }" size="small" />
        </div>

        <!-- Max Tokens -->
        <div class="config-group">
          <label>📏 Max Tokens</label>
          <el-input-number v-model="aiConfig.max_tokens" :min="100" :max="200000" :step="1024"
            size="small" style="width: 100%" />
        </div>

        <!-- System Prompt -->
        <div class="config-group">
          <label>💬 System Prompt（可选）</label>
          <el-input v-model="aiConfig.system_prompt" type="textarea" :rows="3"
            placeholder="自定义系统提示词..." size="small" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group label { font-size: 12px; color: var(--text-muted); font-weight: 500; }
.config-group label code { font-family: var(--mono); font-size: 11px; color: var(--accent-cyan); background: var(--accent-cyan-dim); padding: 1px 4px; border-radius: 3px; }

.config-divider { padding: 4px 0; font-size: 12px; font-weight: 600; color: var(--text-secondary); border-top: 1px solid var(--border); text-align: left; }

.config-section { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.section-header { padding: 10px 14px; background: var(--bg-card); cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: 500; color: var(--text-primary); user-select: none; transition: background 0.2s; }
.section-header:hover { background: var(--bg-hover); }
.section-toggle { font-size: 12px; color: var(--text-muted); }
.section-body { padding: 14px; display: flex; flex-direction: column; gap: 12px; border-top: 1px solid var(--border); }

.test-row { display: flex; align-items: center; gap: 8px; }
.test-info { font-size: 11px; color: var(--success); font-family: var(--mono); white-space: nowrap; }
.test-msg { font-size: 11px; line-height: 1.4; padding: 6px 8px; border-radius: 6px; margin-top: 2px; }
.test-msg.ok { background: rgba(52, 211, 153, 0.1); color: var(--success); }
.test-msg.fail { background: rgba(248, 113, 113, 0.1); color: var(--danger); }

.preset-btns { display: flex; gap: 6px; }
.preset-btn { flex: 1; padding: 5px 0; font-size: 11px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text-secondary); cursor: pointer; transition: all 0.2s; }
.preset-btn:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }
.preset-btn.active { border-color: var(--accent-cyan); background: var(--accent-cyan-dim); color: var(--accent-cyan); font-weight: 600; }

.key-toggle { cursor: pointer; font-size: 14px; user-select: none; padding: 0 4px; }
.key-toggle:hover { opacity: 0.7; }

:deep(.el-slider__marks-text) { font-size: 10px; color: var(--text-muted); }
:deep(.el-slider__bar) { background: var(--accent-cyan); }
:deep(.el-slider__button) { border-color: var(--accent-cyan); }
:deep(.el-select) { width: 100%; }
:deep(.el-switch.is-checked .el-switch__core) { background: var(--accent-cyan); border-color: var(--accent-cyan); }
</style>
