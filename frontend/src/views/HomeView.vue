<script setup>
/**
 * HomeView — 三栏布局编排。
 * 状态由 usePersistedConfig composable 集中管理，UI 拆分为子组件。
 */
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { convertFile, getTaskStatus, getDownloadUrl, getDemoNovel } from '../api/convert.js'
import { usePersistedConfig } from '../composables/usePersistedConfig.js'
import ScriptPreview from '../components/ScriptPreview.vue'
import StoryboardView from '../components/StoryboardView.vue'
import FileUploader from '../components/FileUploader.vue'
import AIProviderSection from '../components/AIProviderSection.vue'
import EpisodeConfigPanel from '../components/EpisodeConfigPanel.vue'

// ---- shared state (composable) ----
const {
  providerList, config, aiConfig, episodeConfig,
  testStatus, testMessage, testLatency, availableModels,
  isManju, isAI, currentProvider, modelOptions,
  AI_PRESETS, HOOK_STYLE_OPTIONS,
} = usePersistedConfig()

// ---- local state ----
const fileList    = ref([])   // [{ file, name, size }]
const loading     = ref(false)
const taskId      = ref('')
const status      = ref('')
const progress    = ref(0)        // 0-100
const progressMsg = ref('')
const previewTab  = ref('script')
const originalYaml = ref('')
const isDirty     = ref(false)
const result      = ref(null)
const yamlText    = ref('')
let pollTimer     = null

// ---- computed ----
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

const episodes = computed(() => result.value?.episodes || [])

const fileCount = computed(() => fileList.value.length)
const convertBtnLabel = computed(() => {
  if (loading.value) return '⏳ 转换中...'
  const hasZip = fileList.value.some(f => f.name.endsWith('.zip'))
  if (fileCount.value < 3 && !hasZip) return `🚀 开始转换（已选 ${fileCount.value} 章，需 ≥3 章）`
  return '🚀 开始转换'
})

// ---- connection test callback ----
function onConnectionTested({ models }) {
  if (models?.length) availableModels.value = models
}

// ---- conversion (async + polling) ----
async function onConvert() {
  if (!fileList.value.length) { ElMessage.warning('请先上传小说文件（至少 1 个）'); return }

  loading.value = true
  result.value = null
  yamlText.value = ''
  progress.value = 0
  progressMsg.value = '提交任务...'

  // 1) 提交任务 → 后端立即返回 task_id
  try {
    const params = {
      ...config,
      ai_config: isAI.value ? { ...aiConfig } : undefined,
      episode_config: isManju.value ? { ...episodeConfig } : undefined,
    }
    if (params.ai_config && !params.ai_config.base_url) delete params.ai_config.base_url

    const filesToSend = fileList.value.map(f => f.file)
    const res = await convertFile(filesToSend, params)
    taskId.value = res.task_id

    // 2) 开始轮询
    startPolling(res.task_id)
  } catch (err) {
    loading.value = false
    ElMessage.error(err.response?.data?.detail || err.message || '请求失败')
  }
}

function startPolling(id) {
  stopPolling()
  const POLL_MS = 600

  pollTimer = setInterval(async () => {
    try {
      const data = await getTaskStatus(id)

      // 更新进度
      if (data.progress != null) {
        progress.value = Math.round(data.progress * 100)
      }
      progressMsg.value = data.progress_message || ''

      if (data.status === 'completed') {
        stopPolling()
        await loadResultData(data)
        loading.value = false
        ElMessage.success('转换成功')
      } else if (data.status === 'failed') {
        stopPolling()
        loading.value = false
        ElMessage.error(data.error || '转换失败')
      }
    } catch {
      // 网络抖动，继续轮询
    }
  }, POLL_MS)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onUnmounted(() => stopPolling())

// ---- Load Demo ----
async function loadDemo() {
  try {
    const text = await getDemoNovel()
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const file = new File([blob], 'demo_novel.md', { type: 'text/plain' })
    fileList.value = [{ file, name: 'demo_novel.md (示例)', size: blob.size }]
    ElMessage.success('已加载示例小说（3章），可直接点击转换')
  } catch {
    ElMessage.warning('加载示例失败，请检查后端是否运行')
  }
}

async function loadResultData(data) {
  status.value = data.status
  result.value = data
  progress.value = 100
  progressMsg.value = '完成'
  try {
    const resp = await fetch(getDownloadUrl(data.task_id))
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
  const blob = new Blob([yamlText.value], { type: 'application/x-yaml;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '剧本_已编辑.yaml'
  a.click()
  URL.revokeObjectURL(a.href)
}

// ---- YAML syntax highlight ----
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
    <!-- ===== 左栏：上传与设置 ===== -->
    <aside class="panel left-panel">
      <div class="panel-title">
        <span>📤 上传与设置</span>
        <span class="saved-indicator" title="设置自动保存到浏览器">💾</span>
      </div>
      <div class="panel-scroll">
        <!-- 文件上传 -->
        <FileUploader v-model="fileList" />
        <el-button v-if="!fileList.length" size="small" text @click="loadDemo" style="margin-top:-8px">
          🎲 加载示例小说（3章）
        </el-button>

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

        <!-- AI 提供商 -->
        <AIProviderSection
          :aiConfig="aiConfig"
          :providerList="providerList"
          :currentProvider="currentProvider"
          :modelOptions="modelOptions"
          :aiPresets="AI_PRESETS"
          @connection-tested="onConnectionTested"
        />

        <!-- 转换按钮 -->
        <el-button type="primary" size="large" :loading="loading" :disabled="!fileList.length"
          @click="onConvert" class="convert-btn">
          {{ convertBtnLabel }}
        </el-button>

        <!-- 进度条（后台转换中） -->
        <div v-if="loading && progress > 0" class="progress-section">
          <el-progress :percentage="progress" :stroke-width="8"
            :status="progress === 100 ? 'success' : ''"
            :color="progress === 100 ? 'var(--success)' : 'var(--accent-cyan)'" />
          <span class="progress-label">{{ progressMsg }}</span>
        </div>

        <!-- 统计信息 -->
        <div v-if="stats" class="stats-box">
          <div class="stat-item"><span class="stat-num">{{ stats.scenes }}</span><span class="stat-label">场景</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.beats }}</span><span class="stat-label">节拍</span></div>
          <div v-if="stats.episodes" class="stat-item"><span class="stat-num">{{ stats.episodes }}</span><span class="stat-label">集数</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.duration }}min</span><span class="stat-label">预估时长</span></div>
        </div>

        <el-button v-if="status === 'completed'" type="primary" plain size="default" @click="onDownload" class="download-btn">
          {{ isDirty ? '⬇️ 下载已编辑的 YAML' : '⬇️ 下载 YAML' }}
        </el-button>
      </div>
    </aside>

    <!-- ===== 中栏：预览 ===== -->
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

      <div v-if="yamlText && previewTab === 'script'" style="flex:1;overflow:hidden">
        <ScriptPreview :yamlText="yamlText" :config="config" @update:yamlText="onYamlEdited" />
      </div>
      <div v-else-if="yamlText && previewTab === 'storyboard' && isManju" style="flex:1;overflow:hidden">
        <StoryboardView :yamlText="yamlText" @update:yamlText="onYamlEdited" />
      </div>
      <div v-else-if="yamlText && previewTab === 'yaml'" class="yaml-preview">
        <pre v-html="highlightedYaml(yamlText)"></pre>
      </div>
      <div v-else class="yaml-empty">
        <div class="empty-icon">📖</div>
        <div class="empty-text">上传小说并点击"开始转换"</div>
        <div class="empty-hint">转换结果将在此处实时预览</div>
      </div>
    </section>

    <!-- ===== 右栏：分集设置 / 输出信息 ===== -->
    <EpisodeConfigPanel
      v-if="isManju"
      :episodeConfig="episodeConfig"
      :hookStyleOptions="HOOK_STYLE_OPTIONS"
      :episodes="episodes"
      :loading="loading"
    />

    <!-- 非漫剧右栏 -->
    <aside class="panel right-panel" v-else>
      <div class="panel-title">ℹ️ 输出信息</div>
      <div class="panel-scroll">
        <div class="info-card" v-if="!stats">
          <div class="empty-icon" style="font-size:36px">📋</div>
          <div class="empty-text" style="font-size:12px">
            {{ config.script_type === 'screenplay' ? '影视剧本模式' : config.script_type === 'audio_drama' ? '广播剧模式' : '舞台剧模式' }}
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

.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group label { font-size: 12px; color: var(--text-muted); font-weight: 500; }

.saved-indicator { font-size: 13px; opacity: 0.6; cursor: help; transition: opacity 0.2s; }
.saved-indicator:hover { opacity: 1; }
.convert-btn { width: 100%; margin-top: 4px; font-weight: 600; flex-shrink: 0; }
.progress-section { margin-top: 8px; }
.progress-label { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; text-align: center; }
.download-btn { width: 100%; flex-shrink: 0; }

.stats-box { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; flex-shrink: 0; }
.stat-item {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px; text-align: center;
}
.stat-num { display: block; font-size: 18px; font-weight: 700; color: var(--accent-cyan); }
.stat-label { font-size: 11px; color: var(--text-muted); }

/* ===== 中栏 ===== */
.center-panel { flex: 1; min-width: 0; }

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
.info-card { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 20px; }

/* Element Plus overrides */
:deep(.el-slider__marks-text) { font-size: 10px; color: var(--text-muted); }
:deep(.el-slider__bar) { background: var(--accent-cyan); }
:deep(.el-slider__button) { border-color: var(--accent-cyan); }
:deep(.el-select) { width: 100%; }

@media (max-width: 1200px) {
  .home-view { flex-direction: column; }
  .left-panel, .right-panel { width: 100%; max-height: 45vh; }
  .center-panel { min-height: 40vh; }
}
</style>
