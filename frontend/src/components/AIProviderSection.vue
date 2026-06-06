<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { testProvider } from '../api/convert.js'
import { ICONS } from '../utils/icons.js'

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
      // 不再自动展开高级参数 — 用户手动点击展开
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

const testBtnStyle = computed(() => {
  if (testStatus.value === 'ok') return 'success'
  if (testStatus.value === 'fail') return 'danger'
  return ''
})
</script>

<template>
  <div>
    <div class="config-divider">
      <span class="divider-icon" v-html="ICONS.bot" /> AI 提供商
    </div>

    <!-- 提供商 -->
    <div class="config-group">
      <el-select v-model="aiConfig.provider" size="small">
        <el-option v-for="p in providerList" :key="p.key" :label="p.name" :value="p.key" />
      </el-select>
    </div>

    <!-- API Key -->
    <div class="config-group">
      <el-input v-model="aiConfig.api_key" :type="showAIKey ? 'text' : 'password'"
        :placeholder="currentProvider ? `输入 ${currentProvider.name} API Key...` : 'sk-...'"
        size="small" clearable>
        <template #prefix><span class="input-icon" v-html="ICONS.key" /></template>
        <template #suffix>
          <span class="key-toggle" @click="showAIKey = !showAIKey">
            <span v-if="showAIKey" v-html="ICONS.xmark" class="eye-icon" />
            <span v-else v-html="ICONS.check" class="eye-icon" />
          </span>
        </template>
      </el-input>
    </div>

    <!-- Base URL + 测试 -->
    <div class="config-group">
      <el-input v-model="aiConfig.base_url" :placeholder="currentProvider?.default_base_url || 'https://api...'"
        size="small" clearable>
        <template #prefix><span class="input-icon" v-html="ICONS.link" /></template>
      </el-input>
      <div class="test-row">
        <el-button :type="testBtnStyle" size="small" :loading="testStatus === 'testing'"
          :disabled="!aiConfig.api_key" @click="onTestConnection" class="test-btn">
          <template v-if="testStatus === 'testing'">测试中...</template>
          <template v-else-if="testStatus === 'ok'">
            <span class="test-icon-ok" v-html="ICONS.check" /> 连接成功
          </template>
          <template v-else-if="testStatus === 'fail'">
            <span class="test-icon-fail" v-html="ICONS.xmark" /> 连接失败
          </template>
          <template v-else>
            <span class="test-icon-default" v-html="ICONS.zap" /> 测试连接
          </template>
        </el-button>
      </div>
      <span class="test-info" v-if="testLatency !== null && testStatus === 'ok'">
        延迟 {{ testLatency }}ms
      </span>
      <span class="test-msg" v-if="testMessage" :class="testStatus">{{ testMessage }}</span>
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
        <span class="section-label">
          <span class="section-icon" v-html="ICONS.settings" />
          高级参数
        </span>
        <svg class="section-chevron" :class="{ open: showAISettings }" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      <div class="section-body" v-show="showAISettings">
        <div class="config-group">
          <label>快速预设</label>
          <div class="preset-btns">
            <button v-for="(p, key) in aiPresets" :key="key" class="preset-btn"
              :class="{ active: aiConfig.temperature === p.temperature && aiConfig.top_p === p.top_p }"
              @click="applyAIPreset(key)">{{ p.label }}</button>
          </div>
        </div>
        <div class="config-group">
          <label>Temperature <code>{{ aiConfig.temperature.toFixed(1) }}</code></label>
          <el-slider v-model="aiConfig.temperature" :min="0" :max="2" :step="0.1"
            :marks="{ 0: '0', 0.5: '.5', 1: '1', 1.5: '1.5', 2: '2' }" size="small" />
        </div>
        <div class="config-group">
          <label>Top P <code>{{ aiConfig.top_p.toFixed(2) }}</code></label>
          <el-slider v-model="aiConfig.top_p" :min="0" :max="1" :step="0.05"
            :marks="{ 0: '0', 0.5: '.5', 1: '1' }" size="small" />
        </div>
        <div class="config-group">
          <label>Max Tokens</label>
          <el-input-number v-model="aiConfig.max_tokens" :min="100" :max="200000" :step="1024" size="small" class="full-width" />
        </div>
        <div class="config-group">
          <label>System Prompt（可选）</label>
          <el-input v-model="aiConfig.system_prompt" type="textarea" :rows="3" placeholder="自定义系统提示词..." size="small" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group > label { font-size: 11px; color: var(--text-tertiary); font-weight: 600; letter-spacing: 0.02em; }
.config-group label code { font-family: var(--font-mono); font-size: 10px; font-weight: 600; color: var(--accent); background: var(--accent-dim); padding: 1px 5px; border-radius: 3px; }

.config-divider { display: flex; align-items: center; gap: 6px; padding: 6px 0 4px; font-size: 11px; font-weight: 600; color: var(--text-tertiary); letter-spacing: 0.03em; text-transform: uppercase; border-top: 1px solid var(--border-subtle); }
.divider-icon { color: var(--accent); display: flex; }

.input-icon { display: flex; align-items: center; color: var(--text-tertiary); }

.config-section { border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-card); }
.section-header { padding: 8px 14px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 600; color: var(--text-secondary); user-select: none; transition: background var(--duration-fast) var(--ease-out); }
.section-header:hover { background: var(--bg-hover); }
.section-label { display: flex; align-items: center; gap: 7px; }
.section-icon { display: flex; color: var(--text-tertiary); }
.section-chevron { color: var(--text-tertiary); transition: transform var(--duration-normal) var(--ease-out); flex-shrink: 0; }
.section-chevron.open { transform: rotate(180deg); }
.section-body { padding: 14px; display: flex; flex-direction: column; gap: 12px; border-top: 1px solid var(--border-subtle); background: var(--bg-surface); }

.test-row { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
.test-btn { width: 100%; }
.test-btn .test-icon-ok, .test-btn .test-icon-fail, .test-btn .test-icon-default { display: inline-flex; align-items: center; vertical-align: -2px; margin-right: 4px; }
.test-info { font-size: 10px; color: var(--text-tertiary); margin-top: 2px; display: block; }
.test-msg { font-size: 10px; line-height: 1.4; padding: 6px 10px; border-radius: var(--radius-sm); margin-top: 2px; font-weight: 450; }
.test-msg.ok { background: var(--green-dim); color: var(--green); }
.test-msg.fail { background: var(--red-dim); color: var(--red); }

.preset-btns { display: flex; gap: 4px; background: var(--bg-surface); border-radius: var(--radius-sm); padding: 3px; border: 1px solid var(--border-subtle); }
.preset-btn { flex: 1; padding: 5px 4px; font-size: 11px; border: none; border-radius: 4px; background: transparent; color: var(--text-tertiary); cursor: pointer; transition: all var(--duration-fast) var(--ease-out); font-weight: 500; }
.preset-btn:hover { color: var(--text-secondary); background: var(--bg-hover); }
.preset-btn.active { background: var(--bg-panel); color: var(--accent); font-weight: 600; box-shadow: var(--shadow-sm); }

.key-toggle { cursor: pointer; display: flex; align-items: center; opacity: 0.5; transition: opacity var(--duration-fast) var(--ease-out); }
.key-toggle:hover { opacity: 1; }
.eye-icon { display: flex; }

.full-width { width: 100%; }
:deep(.el-select) { width: 100%; }
</style>
