<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { convertFile, getTaskStatus, getDownloadUrl, getProviders, testProvider } from '../api/convert.js'
import ScriptPreview from '../components/ScriptPreview.vue'
import StoryboardView from '../components/StoryboardView.vue'

// ========== localStorage 持久化 ==========
const LS_KEY_AI     = 'nts_ai_config_v2'
const LS_KEY_EP     = 'nts_episode_config'
const LS_KEY_BASE   = 'nts_base_config'

function loadFromLS(key, defaults) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    return { ...defaults, ...parsed }
  } catch { return defaults }
}

function saveToLS(key, obj) {
  try { localStorage.setItem(key, JSON.stringify(obj)) } catch { /* ignore */ }
}

// ========== 状态 ==========
const file        = ref(null)
const fileName    = ref('')
const isDragging  = ref(false)
const loading     = ref(false)
const taskId      = ref('')
const status      = ref('')
const showAIKey   = ref(false)
const showAISettings = ref(false)
const previewTab = ref('script') // 'script' | 'storyboard' | 'yaml'
const originalYaml = ref('')       // 转换完成时的原始 YAML（用于对比是否被编辑过）
const isDirty = ref(false)         // 是否已被用户修改过

// 提供商列表（初始默认值，后端加载后覆盖）
const providerList = ref([
  { key: 'deepseek',   name: 'DeepSeek',   default_base_url: 'https://api.deepseek.com',        default_model: 'deepseek-chat',          known_models: ['deepseek-chat','deepseek-reasoner'], api_type: 'openai_compatible' },
  { key: 'anthropic',  name: 'Anthropic',  default_base_url: 'https://api.anthropic.com',        default_model: 'claude-sonnet-4-6',       known_models: ['claude-sonnet-4-6','claude-opus-4-8','claude-haiku-4-5'], api_type: 'anthropic' },
  { key: 'openai',     name: 'OpenAI',     default_base_url: 'https://api.openai.com/v1',        default_model: 'gpt-4o',                  known_models: ['gpt-4o','gpt-4.1','gpt-4o-mini'], api_type: 'openai_compatible' },
  { key: 'openrouter', name: 'OpenRouter', default_base_url: 'https://openrouter.ai/api/v1',     default_model: 'openai/gpt-4o',           known_models: ['openai/gpt-4o','anthropic/claude-sonnet-4-6'], api_type: 'openai_compatible' },
  { key: 'custom',     name: '自定义',     default_base_url: 'http://localhost:11434/v1',        default_model: 'llama3',                  known_models: [], api_type: 'openai_compatible' },
])

// 基础配置
const savedBase = loadFromLS(LS_KEY_BASE, { script_type: 'manju', mode: 'rule', panel_mode: 'simple' })
const config = reactive(savedBase)

// AI 配置（v2 新增 provider + base_url）
const savedAI = loadFromLS(LS_KEY_AI, {
  provider: 'deepseek',
  api_key: '',
  model: 'deepseek-chat',
  base_url: '',
  temperature: 0.7,
  max_tokens: 8192,
  top_p: 1.0,
  system_prompt: '',
})
const aiConfig = reactive(savedAI)

// 分集配置
const savedEP = loadFromLS(LS_KEY_EP, {
  enabled: true,
  target_episodes: null,
  min_duration_seconds: 180,
  max_duration_seconds: 300,
  hook_style: 'cliffhanger',
  auto_split: true,
  title_template: '第{n}集 {subtitle}',
  scene_prefix: '',
})
const episodeConfig = reactive(savedEP)

// 自动保存
watch(aiConfig,      (v) => saveToLS(LS_KEY_AI, v),   { deep: true })
watch(episodeConfig, (v) => saveToLS(LS_KEY_EP, v),   { deep: true })
watch(config,        (v) => saveToLS(LS_KEY_BASE, v), { deep: true })

const result   = ref(null)
const yamlText = ref('')

// 连通性测试状态
const testStatus    = ref('')  // '' | 'testing' | 'ok' | 'fail'
const testMessage   = ref('')
const testLatency   = ref(null)
const availableModels = ref([])  // [{id, owned_by}]

// ========== 计算属性 ==========
const isManju = computed(() => config.script_type === 'manju')
const isAI    = computed(() => config.mode === 'ai')

const currentProvider = computed(() =>
  (providerList.value || []).find(p => p.key === aiConfig.provider)
)

const modelOptions = computed(() => {
  // 优先使用动态发现的模型列表
  if (availableModels.value.length > 0) {
    return availableModels.value.map(m => ({
      label: m.owned_by ? `${m.id} (${m.owned_by})` : m.id,
      value: m.id,
    }))
  }
  // 回退到提供商内置已知模型
  const cp = currentProvider.value
  if (cp?.known_models?.length) {
    return cp.known_models.map(m => ({ label: m, value: m }))
  }
  return [{ label: aiConfig.model || '—', value: aiConfig.model || '' }]
})

const stats = computed(() => {
  if (!result.value) return null
  const m = result.value
  return {
    scenes:   m?.total_scenes ?? 0,
    beats:    m?.total_beats ?? 0,
    episodes: m?.total_episodes ?? 0,
    duration: m?.estimated_duration_minutes ?? 0,
  }
})

const episodes = computed(() => {
  if (!result.value?.episodes) return []
  return result.value.episodes
})

const hookStyleOptions = [
  { label: '悬念式（cliffhanger）', value: 'cliffhanger' },
  { label: '反转式（twist）',       value: 'twist' },
  { label: '情感式（emotional）',   value: 'emotional' },
  { label: '悬疑式（suspense）',    value: 'suspense' },
  { label: '行动式（action）',      value: 'action' },
]

// ========== 初始化：加载提供商列表 ==========
onMounted(async () => {
  try {
    const remote = await getProviders()
    if (remote?.length) {
      providerList.value = remote
    }
  } catch {
    // 使用内置默认列表，无需提示
  }
})

// provider 切换时自动更新默认 model 和 base_url
watch(() => aiConfig.provider, (newProvider) => {
  const found = (providerList.value || []).find(p => p.key === newProvider)
  if (found) {
    if (!aiConfig.base_url) aiConfig.base_url = found.default_base_url
    // 如果当前 model 不在新 provider 的 known_models 中，切换为默认
    const known = found.known_models || []
    if (known.length && !known.includes(aiConfig.model)) {
      aiConfig.model = found.default_model
    }
  }
  // 切换 provider 时清空上一轮测试结果
  testStatus.value = ''
  testMessage.value = ''
  testLatency.value = null
  availableModels.value = []
})

// ========== AI 预设 ==========
const aiPresets = {
  creative: { temperature: 0.9, top_p: 0.95, label: '创意模式' },
  balanced: { temperature: 0.7, top_p: 1.0,  label: '均衡模式' },
  precise:  { temperature: 0.3, top_p: 0.85, label: '精确模式' },
}

function applyAIPreset(key) {
  const p = aiPresets[key]
  aiConfig.temperature = p.temperature
  aiConfig.top_p = p.top_p
  ElMessage.success(`已切换至：${p.label}`)
}

// ========== 连通性测试 ==========
async function onTestConnection() {
  if (!aiConfig.api_key) {
    ElMessage.warning('请先填写 API Key')
    return
  }

  testStatus.value = 'testing'
  testMessage.value = '正在测试连接...'
  testLatency.value = null
  availableModels.value = []

  try {
    const res = await testProvider({
      provider: aiConfig.provider,
      api_key: aiConfig.api_key,
      base_url: aiConfig.base_url || undefined,
      model: aiConfig.model || undefined,
    })

    testStatus.value = res.ok ? 'ok' : 'fail'
    testMessage.value = res.message
    testLatency.value = res.latency_ms

    if (res.ok) {
      // 使用 API 返回的可用模型列表
      if (res.available_models?.length) {
        availableModels.value = res.available_models
        ElMessage.success(`连接成功！发现 ${res.available_models.length} 个模型`)
      } else {
        ElMessage.success('连接成功！API Key 有效')
      }
      // 自动展开 AI 设置
      showAISettings.value = true
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    testStatus.value = 'fail'
    testMessage.value = err.response?.data?.detail || err.message || '测试请求失败'
    testLatency.value = null
    ElMessage.error(testMessage.value)
  }
}

// ========== 文件上传 ==========
function onFileChange(e) {
  const f = e.target.files?.[0]
  if (f) setFile(f)
}

function onDrop(e) {
  isDragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f) setFile(f)
}

function setFile(f) {
  const ok = ['.txt', '.md', '.zip'].some(ext => f.name.toLowerCase().endsWith(ext))
  if (!ok) { ElMessage.warning('请上传 .txt / .md / .zip 文件'); return }
  file.value = f
  fileName.value = f.name
}

function clearFile() { file.value = null; fileName.value = '' }

// ========== 转换 ==========
async function onConvert() {
  if (!file.value) { ElMessage.warning('请先上传小说文件'); return }

  loading.value = true
  result.value = null
  yamlText.value = ''
  status.value = 'processing'

  try {
    const params = {
      ...config,
      ai_config: isAI.value ? { ...aiConfig } : undefined,
      episode_config: isManju.value ? { ...episodeConfig } : undefined,
    }
    // 空 base_url 不发送
    if (params.ai_config && !params.ai_config.base_url) {
      delete params.ai_config.base_url
    }

    const res = await convertFile(file.value, params)
    taskId.value = res.task_id

    if (res.status === 'completed') {
      await loadResult(res.task_id)
      ElMessage.success('转换成功')
    } else {
      status.value = 'failed'
      ElMessage.error(res.message || '转换失败')
    }
  } catch (err) {
    status.value = 'failed'
    ElMessage.error(err.response?.data?.detail || err.message || '请求失败')
  } finally {
    loading.value = false
  }
}

async function loadResult(id) {
  const data = await getTaskStatus(id)
  status.value = data.status
  result.value = data
  try {
    const resp = await fetch(getDownloadUrl(id))
    const text = await resp.text()
    yamlText.value = text
    originalYaml.value = text
    isDirty.value = false
  } catch {
    yamlText.value = '# 预览加载失败'
    originalYaml.value = ''
  }
}

function onYamlEdited(newYaml) {
  yamlText.value = newYaml
  isDirty.value = originalYaml.value !== '' && newYaml !== originalYaml.value
}

function onDownload() {
  if (!yamlText.value) return
  // 下载经过编辑的 YAML（而非服务端原始文件）
  const blob = new Blob([yamlText.value], { type: 'application/x-yaml;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `剧本_已编辑.yaml`
  a.click()
  URL.revokeObjectURL(a.href)
}

// ========== YAML 高亮 ==========
function highlightedYaml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^(\s*)(#.*)$/gm, '$1<span style="color:#5a6078;font-style:italic">$2</span>')
    .replace(/([\w-]+)(:)/g, '<span style="color:#22d3ee">$1</span><span style="color:#8b92a8">$2</span>')
    .replace(/'([^']*)'/g, '<span style="color:#f59e0b">\'$1\'</span>')
    .replace(/"([^"]*)"/g, '<span style="color:#f59e0b">"$1"</span>')
    .replace(/\b(true|false|null)\b/g, '<span style="color:#f472b6">$1</span>')
    .replace(/\b(\d+)\b/g, '<span style="color:#a78bfa">$1</span>')
}
</script>

<template>
  <div class="home-view">
    <!-- ============ 左栏：上传与全部设置 ============ -->
    <aside class="panel left-panel">
      <div class="panel-title">
        <span>📤 上传与设置</span>
        <span class="saved-indicator" title="设置自动保存到浏览器">💾</span>
      </div>
      <div class="panel-scroll">

        <!-- 文件上传 -->
        <div
          class="upload-zone"
          :class="{ dragover: isDragging }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="onDrop"
          @click="$refs.fileInput.click()"
        >
          <input ref="fileInput" type="file" accept=".txt,.md,.zip" hidden @change="onFileChange" />
          <template v-if="!file">
            <div class="upload-icon">📄</div>
            <div class="upload-text">点击或拖拽上传小说</div>
            <div class="upload-hint">支持 .txt / .md / .zip</div>
          </template>
          <template v-else>
            <div class="upload-icon">✅</div>
            <div class="upload-text" style="color: var(--text-primary)">{{ fileName }}</div>
            <div class="upload-hint" style="cursor: pointer; color: var(--danger)" @click.stop="clearFile">点击移除</div>
          </template>
        </div>

        <!-- 剧本类型 -->
        <div class="config-group">
          <label>📋 剧本类型</label>
          <el-radio-group v-model="config.script_type" size="small">
            <el-radio-button label="manju">网文漫剧</el-radio-button>
            <el-radio-button label="screenplay">影视剧本</el-radio-button>
            <el-radio-button label="audio_drama">广播剧</el-radio-button>
            <el-radio-button label="stage_play">舞台剧</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 转换模式 -->
        <div class="config-group">
          <label>⚙️ 转换模式</label>
          <el-radio-group v-model="config.mode" size="small">
            <el-radio-button label="rule">规则模式</el-radio-button>
            <el-radio-button label="ai">AI 深度</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 画面粒度 -->
        <div class="config-group" v-if="isManju">
          <label>🎨 画面粒度</label>
          <el-radio-group v-model="config.panel_mode" size="small">
            <el-radio-button label="simple">简单分镜</el-radio-button>
            <el-radio-button label="detailed">详细分镜</el-radio-button>
          </el-radio-group>
        </div>

        <!-- ========== AI 提供商 ========== -->
        <div class="config-divider">
          <span>🤖 AI 提供商</span>
        </div>

        <!-- 提供商 -->
        <div class="config-group">
          <el-select v-model="aiConfig.provider" size="small">
            <el-option
              v-for="p in providerList"
              :key="p.key"
              :label="`${p.name}`"
              :value="p.key"
            />
          </el-select>
        </div>

        <!-- API Key -->
        <div class="config-group">
          <el-input
            v-model="aiConfig.api_key"
            :type="showAIKey ? 'text' : 'password'"
            :placeholder="currentProvider ? `输入 ${currentProvider.name} API Key...` : 'sk-...'"
            size="small"
            clearable
          >
            <template #prefix>
              <span style="font-size:12px">🔑</span>
            </template>
            <template #suffix>
              <span class="key-toggle" @click="showAIKey = !showAIKey">
                {{ showAIKey ? '🙈' : '👁️' }}
              </span>
            </template>
          </el-input>
        </div>

        <!-- Base URL + 测试连接 -->
        <div class="config-group">
          <el-input
            v-model="aiConfig.base_url"
            :placeholder="currentProvider?.default_base_url || 'https://api...'"
            size="small"
            clearable
          >
            <template #prefix>
              <span style="font-size:12px">🔗</span>
            </template>
          </el-input>
          <div class="test-row" style="margin-top:4px">
            <el-button
              :type="testStatus === 'ok' ? 'success' : testStatus === 'fail' ? 'danger' : 'default'"
              size="small"
              :loading="testStatus === 'testing'"
              :disabled="!aiConfig.api_key"
              @click="onTestConnection"
              style="width:100%"
            >
              {{ testStatus === 'testing' ? '测试中...' :
                 testStatus === 'ok' ? '✅ 连接成功' :
                 testStatus === 'fail' ? '❌ 连接失败' : '🔍 测试连接' }}
            </el-button>
          </div>
          <span class="test-info" v-if="testLatency !== null && testStatus === 'ok'" style="font-size:11px;color:var(--success);margin-top:2px">
            延迟 {{ testLatency }}ms · 发现 {{ availableModels.length }} 个模型
          </span>
          <span class="test-msg" v-if="testMessage" :class="testStatus" style="margin-top:2px">
            {{ testMessage }}
          </span>
        </div>

        <!-- 模型 -->
        <div class="config-group">
          <el-select
            v-model="aiConfig.model"
            size="small"
            filterable
            allow-create
            placeholder="选择或输入模型名"
          >
            <el-option
              v-for="opt in modelOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>

        <!-- 高级设置（可折叠） -->
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
                  v-for="(p, key) in aiPresets"
                  :key="key"
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

        <!-- 转换按钮 -->
        <el-button type="primary" size="large" :loading="loading" :disabled="!file"
          @click="onConvert" class="convert-btn">
          {{ loading ? '⏳ 转换中...' : '🚀 开始转换' }}
        </el-button>

        <!-- 统计信息 -->
        <div v-if="stats" class="stats-box">
          <div class="stat-item">
            <span class="stat-num">{{ stats.scenes }}</span>
            <span class="stat-label">场景</span>
          </div>
          <div class="stat-item">
            <span class="stat-num">{{ stats.beats }}</span>
            <span class="stat-label">节拍</span>
          </div>
          <div v-if="stats.episodes" class="stat-item">
            <span class="stat-num">{{ stats.episodes }}</span>
            <span class="stat-label">集数</span>
          </div>
          <div class="stat-item">
            <span class="stat-num">{{ stats.duration }}min</span>
            <span class="stat-label">预估时长</span>
          </div>
        </div>

        <el-button v-if="status === 'completed'" type="primary" plain size="default"
          @click="onDownload" class="download-btn">
          {{ isDirty ? '⬇️ 下载已编辑的 YAML' : '⬇️ 下载 YAML' }}
        </el-button>
      </div>
    </aside>

    <!-- ============ 中栏：剧本预览 ============ -->
    <section class="panel center-panel">
      <div class="panel-title">
        <div class="tab-row">
          <button class="tab-btn" :class="{ active: previewTab === 'script' }" @click="previewTab = 'script'">📋 剧本预览</button>
          <button v-if="isManju" class="tab-btn" :class="{ active: previewTab === 'storyboard' }" @click="previewTab = 'storyboard'">🎬 分镜预览</button>
          <button class="tab-btn" :class="{ active: previewTab === 'yaml' }" @click="previewTab = 'yaml'">📝 YAML源码</button>
        </div>
        <span v-if="status === 'completed'" class="status-badge success">转换完成</span>
        <span v-else-if="status === 'failed'" class="status-badge error">转换失败</span>
        <span v-else-if="loading" class="status-badge pending">转换中...</span>
      </div>

      <!-- 剧本预览 -->
      <div v-if="yamlText && previewTab === 'script'" style="flex:1;overflow:hidden">
        <ScriptPreview :yamlText="yamlText" :config="config" @update:yamlText="onYamlEdited" />
      </div>

      <!-- 分镜预览（仅漫剧） -->
      <div v-else-if="yamlText && previewTab === 'storyboard' && isManju" style="flex:1;overflow:hidden">
        <StoryboardView :yamlText="yamlText" @update:yamlText="onYamlEdited" />
      </div>

      <!-- YAML 源码 -->
      <div v-else-if="yamlText && previewTab === 'yaml'" class="yaml-preview">
        <pre v-html="highlightedYaml(yamlText)"></pre>
      </div>

      <!-- 空状态 -->
      <div v-else class="yaml-empty">
        <div class="empty-icon">📖</div>
        <div class="empty-text">上传小说并点击"开始转换"</div>
        <div class="empty-hint">转换结果将在此处实时预览</div>
      </div>
    </section>

    <!-- ============ 右栏：分集设置 & 结果 ============ -->
    <aside class="panel right-panel" v-if="isManju">
      <div class="panel-title">🎬 分集设置</div>
      <div class="panel-scroll">
        <div class="episode-config-section">
          <div class="config-group">
            <label>🔘 启用分集</label>
            <el-switch v-model="episodeConfig.enabled" size="small" />
          </div>
          <template v-if="episodeConfig.enabled">
            <div class="config-group">
              <label>🎯 目标集数 <span class="label-hint">（留空=自动）</span></label>
              <el-input-number v-model="episodeConfig.target_episodes" :min="1" :max="500"
                placeholder="自动" size="small" style="width:100%" />
            </div>
            <div class="config-group">
              <label>⏱️ 集时长范围</label>
              <div class="duration-row">
                <el-input-number v-model="episodeConfig.min_duration_seconds" :min="60" :max="600"
                  :step="30" size="small" style="width:45%" />
                <span class="duration-sep">—</span>
                <el-input-number v-model="episodeConfig.max_duration_seconds" :min="60" :max="600"
                  :step="30" size="small" style="width:45%" />
              </div>
              <span class="label-hint" style="margin-top:2px">
                {{ Math.round(episodeConfig.min_duration_seconds / 60) }}–{{ Math.round(episodeConfig.max_duration_seconds / 60) }} 分钟/集
              </span>
            </div>
            <div class="config-group">
              <label>🪝 集末钩子风格</label>
              <el-select v-model="episodeConfig.hook_style" size="small">
                <el-option v-for="opt in hookStyleOptions" :key="opt.value"
                  :label="opt.label" :value="opt.value" />
              </el-select>
            </div>
            <div class="config-group">
              <label>✂️ 自动切分场景</label>
              <el-switch v-model="episodeConfig.auto_split" size="small" />
            </div>
            <div class="config-group">
              <label>📝 集标题模板</label>
              <el-input v-model="episodeConfig.title_template" size="small"
                placeholder="第{n}集 {subtitle}" />
              <span class="label-hint">可用变量: <code>{n}</code> <code>{subtitle}</code> <code>{pause}</code></span>
            </div>
            <div class="config-group">
              <label>🏷️ 场景前缀 <span class="label-hint">（可选）</span></label>
              <el-input v-model="episodeConfig.scene_prefix" size="small"
                placeholder="例：S01E{n:02d}" />
            </div>
          </template>
          <div v-else class="disabled-hint">
            💡 不启用分集时，所有场景将合并在一个输出中
          </div>
        </div>

        <div class="section-divider" v-if="episodes.length"><span>📺 生成结果</span></div>

        <div v-if="!episodes.length && !loading" class="episode-empty">
          <div class="empty-icon">🎞️</div>
          <div class="empty-text">设置分集参数后开始转换</div>
          <div class="empty-hint">集数结果将在此处展示</div>
        </div>
        <div v-else-if="loading" class="episode-empty">
          <div class="empty-icon">⏳</div>
          <div class="empty-text">转换中...</div>
        </div>
        <div v-else class="episode-list">
          <div v-for="ep in episodes" :key="ep.episode_id" class="episode-card">
            <div class="episode-header">
              <span class="ep-num">第{{ ep.episode_number }}集</span>
              <span class="ep-duration">{{ Math.round(ep.target_duration_seconds / 60) }}min</span>
            </div>
            <div class="ep-title">{{ ep.title }}</div>
            <div class="ep-hook" v-if="ep.hook">{{ ep.hook }}</div>
            <div class="ep-meta">
              <span>{{ ep.scene_count ?? (ep.scenes?.length || 0) }} 场景</span>
              <span v-if="ep.source_chapters?.length">来源: 第{{ ep.source_chapters.join(',') }}章</span>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 非漫剧右栏 -->
    <aside class="panel right-panel" v-else>
      <div class="panel-title">ℹ️ 输出信息</div>
      <div class="panel-scroll">
        <div class="info-card" v-if="!stats">
          <div class="empty-icon" style="font-size:36px">📋</div>
          <div class="empty-text" style="font-size:12px">
            {{ config.script_type === 'screenplay' ? '影视剧本模式' :
               config.script_type === 'audio_drama' ? '广播剧模式' : '舞台剧模式' }}
          </div>
          <div class="empty-hint">分集功能仅在网文漫剧模式下可用</div>
        </div>
        <div v-else class="info-card">
          <div class="stat-item"><span class="stat-num">{{ stats.scenes }}</span><span class="stat-label">场景</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.beats }}</span><span class="stat-label">节拍</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.duration }}min</span><span class="stat-label">时长</span></div>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.home-view {
  display: flex; gap: 16px; height: 100%; max-width: 1800px; margin: 0 auto;
}
.panel {
  background: var(--bg-panel); border: 1px solid var(--border);
  border-radius: 12px; display: flex; flex-direction: column; overflow: hidden;
}
.panel-title {
  padding: 14px 18px; font-size: 14px; font-weight: 600; color: var(--text-primary);
  border-bottom: 1px solid var(--border); display: flex; align-items: center;
  justify-content: space-between; flex-shrink: 0;
}
.panel-scroll {
  flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px;
}

/* ===== 左栏 ===== */
.left-panel { width: 360px; flex-shrink: 0; }
.upload-zone {
  border: 2px dashed var(--border); border-radius: 10px; padding: 24px 16px;
  text-align: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0;
}
.upload-zone:hover, .upload-zone.dragover { border-color: var(--accent-cyan); background: var(--accent-cyan-dim); }
.upload-icon { font-size: 28px; margin-bottom: 6px; }
.upload-text { font-size: 14px; color: var(--text-secondary); font-weight: 500; }
.upload-hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group label { font-size: 12px; color: var(--text-muted); font-weight: 500; }
.config-group label code {
  font-family: var(--mono); font-size: 11px; color: var(--accent-cyan);
  background: var(--accent-cyan-dim); padding: 1px 4px; border-radius: 3px;
}
.label-hint { font-size: 10px; color: var(--text-muted); font-weight: 400; }
.label-hint code {
  font-family: var(--mono); font-size: 10px; background: var(--bg-card);
  padding: 1px 3px; border-radius: 2px;
}

/* AI 设置面板 */
.config-section { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.section-header {
  padding: 10px 14px; background: var(--bg-card); cursor: pointer; display: flex;
  justify-content: space-between; align-items: center; font-size: 13px;
  font-weight: 500; color: var(--text-primary); user-select: none; transition: background 0.2s;
}
.section-header:hover { background: var(--bg-hover); }
.section-toggle { font-size: 12px; color: var(--text-muted); }
.section-body {
  padding: 14px; display: flex; flex-direction: column; gap: 12px; border-top: 1px solid var(--border);
}

/* 配置区隔线 */
.config-divider {
  padding: 4px 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  border-top: 1px solid var(--border);
  text-align: left;
}

/* 测试连接 */
.test-row { display: flex; align-items: center; gap: 8px; }
.test-info {
  font-size: 11px; color: var(--success); font-family: var(--mono); white-space: nowrap;
}
.test-msg {
  font-size: 11px; line-height: 1.4; padding: 6px 8px; border-radius: 6px; margin-top: 2px;
}
.test-msg.ok {
  background: rgba(52, 211, 153, 0.1); color: var(--success);
}
.test-msg.fail {
  background: rgba(248, 113, 113, 0.1); color: var(--danger);
}

/* 预设按钮 */
.preset-btns { display: flex; gap: 6px; }
.preset-btn {
  flex: 1; padding: 5px 0; font-size: 11px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--bg-card); color: var(--text-secondary);
  cursor: pointer; transition: all 0.2s;
}
.preset-btn:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }
.preset-btn.active {
  border-color: var(--accent-cyan); background: var(--accent-cyan-dim);
  color: var(--accent-cyan); font-weight: 600;
}

.key-toggle { cursor: pointer; font-size: 14px; user-select: none; padding: 0 4px; }
.key-toggle:hover { opacity: 0.7; }

.convert-btn { width: 100%; margin-top: 4px; font-weight: 600; flex-shrink: 0; }
.download-btn { width: 100%; flex-shrink: 0; }
.saved-indicator { font-size: 13px; opacity: 0.6; cursor: help; transition: opacity 0.2s; }
.saved-indicator:hover { opacity: 1; }

.stats-box { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; flex-shrink: 0; }
.stat-item {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px; text-align: center;
}
.stat-num { display: block; font-size: 18px; font-weight: 700; color: var(--accent-cyan); }
.stat-label { font-size: 11px; color: var(--text-muted); }

/* ===== 中栏 ===== */
.center-panel { flex: 1; min-width: 0; }

/* Tab row */
.tab-row { display: flex; gap: 2px; }
.tab-btn {
  font-size: 12px; padding: 5px 14px; border: none; border-radius: 6px;
  background: transparent; color: var(--text-muted); cursor: pointer;
  transition: all 0.15s; font-family: var(--sans);
}
.tab-btn:hover { background: var(--bg-hover); color: var(--text-secondary); }
.tab-btn.active {
  background: var(--accent-cyan-dim); color: var(--accent-cyan); font-weight: 600;
}

.status-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.status-badge.success { background: rgba(52,211,153,0.15); color: var(--success); }
.status-badge.error   { background: rgba(248,113,113,0.15); color: var(--danger); }
.status-badge.pending { background: rgba(251,191,36,0.15); color: var(--warning); }
.yaml-preview { flex: 1; overflow: auto; padding: 16px; }
.yaml-preview pre {
  margin: 0; font-family: var(--mono); font-size: 12px; line-height: 1.7;
  color: var(--text-secondary); white-space: pre; word-wrap: normal;
}
.yaml-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); }
.empty-icon { font-size: 48px; opacity: 0.4; margin-bottom: 12px; }
.empty-text { font-size: 14px; color: var(--text-secondary); margin-bottom: 4px; }
.empty-hint { font-size: 12px; color: var(--text-muted); }

/* ===== 右栏 ===== */
.right-panel { width: 320px; flex-shrink: 0; }
.episode-config-section { display: flex; flex-direction: column; gap: 12px; }
.duration-row { display: flex; align-items: center; gap: 6px; }
.duration-sep { color: var(--text-muted); font-weight: 500; }
.disabled-hint {
  padding: 12px; background: var(--bg-card); border-radius: 8px;
  font-size: 12px; color: var(--text-muted); text-align: center;
}
.section-divider {
  padding: 8px 0; font-size: 12px; font-weight: 600; color: var(--text-secondary);
  border-top: 1px solid var(--border); text-align: center;
}
.section-divider span { background: var(--bg-panel); padding: 0 8px; }
.episode-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); min-height: 120px; }
.episode-list { display: flex; flex-direction: column; gap: 10px; }
.episode-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px; transition: border-color 0.2s;
}
.episode-card:hover { border-color: var(--border-light); }
.episode-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.ep-num { font-size: 13px; font-weight: 600; color: var(--accent-amber); }
.ep-duration { font-size: 11px; color: var(--text-muted); background: var(--bg-deep); padding: 2px 6px; border-radius: 4px; }
.ep-title { font-size: 12px; color: var(--text-primary); font-weight: 500; margin-bottom: 4px; }
.ep-hook {
  font-size: 11px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 6px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.ep-meta { display: flex; gap: 8px; font-size: 10px; color: var(--text-muted); }
.ep-meta span { background: var(--bg-deep); padding: 2px 6px; border-radius: 4px; }

.info-card { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 20px; }

/* Element Plus 深色覆盖 */
:deep(.el-slider__marks-text) { font-size: 10px; color: var(--text-muted); }
:deep(.el-slider__bar) { background: var(--accent-cyan); }
:deep(.el-slider__button) { border-color: var(--accent-cyan); }
:deep(.el-select) { width: 100%; }
:deep(.el-switch.is-checked .el-switch__core) { background: var(--accent-cyan); border-color: var(--accent-cyan); }

@media (max-width: 1200px) {
  .home-view { flex-direction: column; }
  .left-panel, .right-panel { width: 100%; max-height: 45vh; }
  .center-panel { min-height: 40vh; }
}
</style>
