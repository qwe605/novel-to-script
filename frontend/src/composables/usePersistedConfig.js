/**
 * 持久化配置 composable — 所有 localStorage + reactive state 集中管理。
 * HomeView 及其子组件通过此 composable 共享配置状态。
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { getProviders } from '../api/convert.js'

// ========== localStorage helpers ==========

export function loadFromLS(key, defaults) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return defaults
    return { ...defaults, ...JSON.parse(raw) }
  } catch { return defaults }
}

export function saveToLS(key, obj) {
  try { localStorage.setItem(key, JSON.stringify(obj)) } catch { /* ignore */ }
}

// ========== keys ==========

export const LS_KEY_AI   = 'nts_ai_config_v2'
export const LS_KEY_EP   = 'nts_episode_config'
export const LS_KEY_BASE = 'nts_base_config'

// ========== composable ==========

export function usePersistedConfig() {
  // ---- 提供商列表 ----
  const providerList = ref([
    { key: 'deepseek',   name: 'DeepSeek',   default_base_url: 'https://api.deepseek.com',        default_model: 'deepseek-chat',          known_models: ['deepseek-chat','deepseek-reasoner'], api_type: 'openai_compatible' },
    { key: 'anthropic',  name: 'Anthropic',  default_base_url: 'https://api.anthropic.com',        default_model: 'claude-sonnet-4-6',       known_models: ['claude-sonnet-4-6','claude-opus-4-8','claude-opus-4-7','claude-haiku-4-5','claude-sonnet-4-5'], api_type: 'anthropic' },
    { key: 'openai',     name: 'OpenAI',     default_base_url: 'https://api.openai.com/v1',        default_model: 'gpt-4o',                  known_models: ['gpt-4o','gpt-4.1','gpt-4o-mini','gpt-4-turbo','o4-mini'], api_type: 'openai_compatible' },
    { key: 'openrouter', name: 'OpenRouter', default_base_url: 'https://openrouter.ai/api/v1',     default_model: 'openai/gpt-4o',           known_models: ['openai/gpt-4o','anthropic/claude-sonnet-4-6','anthropic/claude-opus-4-8','google/gemini-2.5-pro','meta-llama/llama-4-maverick'], api_type: 'openai_compatible' },
    { key: 'custom',     name: '自定义',     default_base_url: 'http://localhost:11434/v1',        default_model: 'llama3',                  known_models: [], api_type: 'openai_compatible' },
  ])

  // ---- 基础配置 ----
  const config = reactive(loadFromLS(LS_KEY_BASE, { script_type: 'manju', mode: 'rule', panel_mode: 'simple' }))

  // ---- AI 配置 ----
  const aiConfig = reactive(loadFromLS(LS_KEY_AI, {
    provider: 'deepseek',
    api_key: '',
    model: 'deepseek-chat',
    base_url: '',
    temperature: 0.7,
    max_tokens: 8192,
    top_p: 1.0,
    system_prompt: '',
  }))

  // ---- 分集配置 ----
  const episodeConfig = reactive(loadFromLS(LS_KEY_EP, {
    enabled: true,
    target_episodes: null,
    min_duration_seconds: 180,
    max_duration_seconds: 300,
    hook_style: 'cliffhanger',
    auto_split: true,
    title_template: '第{n}集 {subtitle}',
    scene_prefix: '',
  }))

  // ---- 连通性测试状态 ----
  const testStatus    = ref('')
  const testMessage   = ref('')
  const testLatency   = ref(null)
  const availableModels = ref([])

  // ---- 计算属性 ----
  const isManju = computed(() => config.script_type === 'manju')
  const isAI    = computed(() => config.mode === 'ai')

  const currentProvider = computed(() =>
    (providerList.value || []).find(p => p.key === aiConfig.provider)
  )

  const modelOptions = computed(() => {
    if (availableModels.value.length > 0) {
      return availableModels.value.map(m => ({
        label: m.owned_by ? `${m.id} (${m.owned_by})` : m.id,
        value: m.id,
      }))
    }
    const cp = currentProvider.value
    if (cp?.known_models?.length) {
      return cp.known_models.map(m => ({ label: m, value: m }))
    }
    return [{ label: aiConfig.model || '—', value: aiConfig.model || '' }]
  })

  // ---- 自动保存 ----
  watch(aiConfig,      (v) => saveToLS(LS_KEY_AI, v),   { deep: true })
  watch(episodeConfig, (v) => saveToLS(LS_KEY_EP, v),   { deep: true })
  watch(config,        (v) => saveToLS(LS_KEY_BASE, v), { deep: true })

  // provider 切换时自动更新 model 和 base_url
  watch(() => aiConfig.provider, (newProvider) => {
    const found = (providerList.value || []).find(p => p.key === newProvider)
    if (found) {
      if (!aiConfig.base_url) aiConfig.base_url = found.default_base_url
      const known = found.known_models || []
      if (known.length && !known.includes(aiConfig.model)) {
        aiConfig.model = found.default_model
      }
    }
    testStatus.value = ''
    testMessage.value = ''
    testLatency.value = null
    availableModels.value = []
  })

  // ---- 初始化 ----
  onMounted(async () => {
    try {
      const remote = await getProviders()
      if (remote?.length) providerList.value = remote
    } catch { /* fallback to built-in list */ }
  })

  // ---- AI 预设 ----
  const AI_PRESETS = {
    creative: { temperature: 0.9, top_p: 0.95, label: '创意模式' },
    balanced: { temperature: 0.7, top_p: 1.0,  label: '均衡模式' },
    precise:  { temperature: 0.3, top_p: 0.85, label: '精确模式' },
  }

  const HOOK_STYLE_OPTIONS = [
    { label: '悬念式（cliffhanger）', value: 'cliffhanger' },
    { label: '反转式（twist）',       value: 'twist' },
    { label: '情感式（emotional）',   value: 'emotional' },
    { label: '悬疑式（suspense）',    value: 'suspense' },
    { label: '行动式（action）',      value: 'action' },
  ]

  return {
    // state
    providerList, config, aiConfig, episodeConfig,
    testStatus, testMessage, testLatency, availableModels,
    // computed
    isManju, isAI, currentProvider, modelOptions,
    // constants
    AI_PRESETS, HOOK_STYLE_OPTIONS,
  }
}
