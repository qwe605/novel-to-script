<script setup>
/**
 * HomeView — 三栏布局编排。
 * 状态由 usePersistedConfig composable 集中管理，UI 拆分为子组件。
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { convertFile, getTaskStatus, getDownloadUrl, getDemoNovel } from '../api/convert.js'
import { ICONS } from '../utils/icons.js'
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
const uploaderRef = ref(null)
const fileList    = ref([])   // [{ name, size }]
const novelTitle  = ref('')   // 小说标题
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

// 从文件名提取标题
function filenameToTitle(name) {
  // 去扩展名和后缀
  let t = name.replace(/\.(txt|md|zip)$/i, '')
  // 去掉常见前缀和清洗
  t = t.replace(/[（(]?规则编号[零一二三四五六七八九十\d]+[）)]?[-_]?/g, '')
  t = t.replace(/[-_]/g, ' ')
  t = t.replace(/\s+/g, ' ').trim()
  return t || '未命名作品'
}

// 监听 fileList 变化自动提取标题
watch(fileList, (list) => {
  if (list.length && !novelTitle.value) {
    novelTitle.value = filenameToTitle(list[0].name)
  }
}, { deep: false })

// ---- computed ----
const stats = computed(() => {
  if (!result.value) return null
  const m = result.value
  return {
    scenes:   m?.total_scenes ?? 0,
    beats:    m?.total_beats ?? 0,
    episodes: m?.total_episodes ?? 0,
    duration: m?.estimated_duration_minutes ?? 0,
    timing:   m?.timing ?? null,
  }
})

const episodes = computed(() => result.value?.episodes || [])

const fileCount = computed(() => fileList.value.length)
const convertBtnLabel = computed(() => {
  if (loading.value) return '转换中...'
  const hasZip = fileList.value.some(f => f.name.endsWith('.zip'))
  if (fileCount.value < 3 && !hasZip) return `开始转换（已选 ${fileCount.value} 章，需 ≥3 章）`
  return '开始转换'
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
      title: novelTitle.value || '未命名作品',
      ai_config: isAI.value ? { ...aiConfig } : undefined,
      episode_config: isManju.value ? { ...episodeConfig } : undefined,
    }
    if (params.ai_config && !params.ai_config.base_url) delete params.ai_config.base_url

    const filesToSend = uploaderRef.value?.getFiles?.() || []
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
    uploaderRef.value?.addFiles([file])
    novelTitle.value = '穿成病娇大佬的亡妻'
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
        <span class="panel-title-label"><span class="pt-icon" v-html="ICONS.upload" /> 上传与设置</span>
        <span class="saved-dot" title="设置自动保存到浏览器" />
      </div>
      <div class="panel-scroll">
        <FileUploader ref="uploaderRef" v-model="fileList" />
        <el-button v-if="!fileList.length" size="small" text @click="loadDemo" class="demo-btn">
          <span class="btn-icon" v-html="ICONS.dice" /> 加载示例小说（3章）
        </el-button>

        <!-- 小说标题 -->
        <div class="config-group">
          <label><span class="label-icon" v-html="ICONS.edit" /> 小说标题</label>
          <el-input v-model="novelTitle" size="small" placeholder="自动从文件名提取，可修改"
            :disabled="!fileList.length && !novelTitle"
            clearable />
        </div>

        <div class="config-group">
          <label><span class="label-icon" v-html="ICONS.film" /> 剧本类型</label>
          <el-radio-group v-model="config.script_type" size="small">
            <el-radio-button label="manju">网文漫剧</el-radio-button>
            <el-radio-button label="screenplay">影视剧本</el-radio-button>
            <el-radio-button label="audio_drama">广播剧</el-radio-button>
            <el-radio-button label="stage_play">舞台剧</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 转换模式 -->
        <div class="config-group">
          <label><span class="label-icon" v-html="ICONS.settings" /> 转换模式</label>
          <el-radio-group v-model="config.mode" size="small">
            <el-radio-button label="rule">规则模式</el-radio-button>
            <el-radio-button label="ai">AI 深度</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 画面粒度 -->
        <div class="config-group" v-if="isManju">
          <label><span class="label-icon" v-html="ICONS.sparkles" /> 画面粒度</label>
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
          <div class="stat-item"><span class="stat-num">{{ stats.beats }}</span><span class="stat-label">镜头</span></div>
          <div v-if="stats.episodes" class="stat-item"><span class="stat-num">{{ stats.episodes }}</span><span class="stat-label">集数</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.duration }}min</span><span class="stat-label">预估时长</span></div>
        </div>

        <!-- 耗时统计 -->
        <div v-if="stats?.timing" class="timing-box">
          <div class="timing-title">⏱ 耗时统计</div>
          <div class="timing-rows">
            <div v-for="(sec, name) in stats.timing" :key="name" class="timing-row">
              <span class="timing-name">{{ name }}</span>
              <span class="timing-bar"><span class="timing-fill" :style="{ width: Math.min(100, (sec / (stats.timing['总耗时'] || 1)) * 100) + '%' }" /></span>
              <span class="timing-sec">{{ sec }}s</span>
            </div>
          </div>
        </div>

        <el-button v-if="status === 'completed'" type="primary" plain size="default" @click="onDownload" class="download-btn">
          <span class="btn-icon" v-html="ICONS.download" /> {{ isDirty ? '下载已编辑的 YAML' : '下载 YAML' }}
        </el-button>
      </div>
    </aside>

    <!-- ===== 中栏：预览 ===== -->
    <section class="panel center-panel">
      <div class="panel-title">
        <div class="tab-row">
          <button class="tab-btn" :class="{ active: previewTab === 'script' }" @click="previewTab = 'script'">
            <span class="tab-icon" v-html="ICONS.script" /> 剧本预览
          </button>
          <button v-if="isManju" class="tab-btn" :class="{ active: previewTab === 'storyboard' }" @click="previewTab = 'storyboard'">
            <span class="tab-icon" v-html="ICONS.layout" /> 分镜预览
          </button>
          <button class="tab-btn" :class="{ active: previewTab === 'yaml' }" @click="previewTab = 'yaml'">
            <span class="tab-icon" v-html="ICONS.code" /> YAML 源码
          </button>
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
        <div class="empty-graphic" v-html="ICONS.file" />
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
      :scriptTitle="result?.title || ''"
      :scriptType="config.script_type"
      :characters="result?.characters || []"
    />

    <!-- 非漫剧右栏 -->
    <aside class="panel right-panel" v-else>
      <div class="panel-title">
        <span class="panel-title-label"><span class="pt-icon" v-html="ICONS.monitor" /> 输出信息</span>
      </div>
      <div class="panel-scroll">
        <div class="info-card" v-if="!stats">
          <div class="empty-graphic" v-html="ICONS.layout" />
          <div class="empty-text" style="font-size:12px">
            {{ config.script_type === 'screenplay' ? '影视剧本模式' : config.script_type === 'audio_drama' ? '广播剧模式' : '舞台剧模式' }}
          </div>
          <div class="empty-hint">分集功能仅在网文漫剧模式下可用</div>
        </div>
        <div v-else class="info-card">
          <div class="stat-item"><span class="stat-num">{{ stats.scenes }}</span><span class="stat-label">场景</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.beats }}</span><span class="stat-label">镜头</span></div>
          <div class="stat-item"><span class="stat-num">{{ stats.duration }}min</span><span class="stat-label">时长</span></div>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
/* =============================================================================
   HomeView — 三栏布局
   ============================================================================= */

.home-view {
  display: flex; gap: 12px; height: 100%; max-width: 1800px; margin: 0 auto;
}

/* ---- 面板基类 ---- */
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.panel-title {
  padding: 12px 18px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.01em;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  user-select: none;
  background: var(--bg-surface);
}

.panel-scroll {
  flex: 1; overflow-y: auto; padding: 14px;
  display: flex; flex-direction: column; gap: 12px;
}

/* =============================================================================
   左栏 — 上传与设置
   ============================================================================= */

.left-panel { width: 352px; flex-shrink: 0; }

/* 通用图标 */
.panel-title-label { display: flex; align-items: center; gap: 7px; }
.pt-icon { display: flex; color: var(--text-tertiary); }
.label-icon { display: inline-flex; vertical-align: -2px; margin-right: 4px; color: var(--text-tertiary); }
.tab-icon { display: inline-flex; vertical-align: -2px; margin-right: 4px; }
.btn-icon { display: inline-flex; vertical-align: -2px; margin-right: 3px; }
.demo-btn { margin-top: -8px; }
.saved-dot { display: block; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); opacity: 0.5; cursor: help; transition: opacity var(--duration-fast); }
.saved-dot:hover { opacity: 1; }
.empty-graphic { color: var(--text-tertiary); opacity: 0.25; margin-bottom: 12px; }

/* 配置项 */
.config-group {
  display: flex; flex-direction: column; gap: 6px;
}
.config-group > label {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 600;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  gap: 4px;
}

.convert-btn {
  width: 100%;
  margin-top: 2px;
  font-weight: 600;
  flex-shrink: 0;
  font-size: 14px;
  letter-spacing: -0.01em;
}

/* 进度条 */
.progress-section {
  margin-top: 4px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.progress-label {
  font-size: 11px;
  color: var(--text-tertiary);
  display: block;
  margin-top: 6px;
  text-align: center;
}

/* 下载按钮 */
.download-btn { width: 100%; flex-shrink: 0; }

/* 统计方格 */
.stats-box {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px; flex-shrink: 0;
}
.stat-item {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 10px;
  text-align: center;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.stat-item:hover { border-color: var(--border); }
.stat-num {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: 10px;
  color: var(--text-tertiary);
  font-weight: 500;
  letter-spacing: 0.03em;
}

/* 耗时统计 */
.timing-box {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  flex-shrink: 0;
}
.timing-title {
  font-size: 10px; color: var(--text-tertiary); font-weight: 600;
  margin-bottom: 6px; letter-spacing: 0.02em;
}
.timing-rows { display: flex; flex-direction: column; gap: 3px; }
.timing-row { display: flex; align-items: center; gap: 6px; }
.timing-name {
  font-size: 10px; color: var(--text-secondary); min-width: 48px;
  flex-shrink: 0; font-weight: 450;
}
.timing-bar {
  flex: 1; height: 4px; background: var(--bg-hover);
  border-radius: 2px; overflow: hidden;
}
.timing-fill {
  display: block; height: 100%; background: var(--accent);
  border-radius: 2px; opacity: 0.5;
  transition: width 0.5s var(--ease-out);
}
.timing-sec {
  font-size: 10px; color: var(--text-tertiary); font-family: var(--font-mono);
  min-width: 32px; text-align: right; flex-shrink: 0;
}

/* =============================================================================
   中栏 — 预览
   ============================================================================= */

.center-panel { flex: 1; min-width: 0; }

/* Tab 切换 */
.tab-row {
  display: flex;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 2px;
  gap: 1px;
}
.tab-btn {
  font-size: 12px;
  padding: 5px 14px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-family: var(--font-sans);
  font-weight: 500;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text-secondary); }
.tab-btn.active {
  background: var(--bg-panel);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

/* 状态标记 */
.status-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.status-badge.success { background: var(--green-dim); color: var(--green); }
.status-badge.error   { background: var(--red-dim);   color: var(--red); }
.status-badge.pending { background: var(--amber-dim);  color: var(--amber); }

/* YAML 源码预览 */
.yaml-preview {
  flex: 1; overflow: auto; padding: 18px 20px;
  background: var(--bg-surface);
}
.yaml-preview pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.75;
  color: var(--text-secondary);
  white-space: pre;
  word-wrap: normal;
  font-weight: 450;
}

/* 空状态 */
.yaml-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  gap: 6px;
  padding: 40px 20px;
}
.yaml-empty .empty-icon {
  font-size: 52px;
  opacity: 0.3;
  margin-bottom: 8px;
  filter: grayscale(0.3);
}
.yaml-empty .empty-text {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}
.yaml-empty .empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* =============================================================================
   右栏
   ============================================================================= */

.right-panel { width: 304px; flex-shrink: 0; }
.info-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
}

/* =============================================================================
   Element Plus 深度覆盖
   ============================================================================= */

:deep(.el-select) { width: 100%; }
:deep(.el-slider__marks-text) { font-size: 10px; color: var(--text-tertiary); }

@media (max-width: 1200px) {
  .home-view { flex-direction: column; }
  .left-panel, .right-panel { width: 100%; max-height: 45vh; }
  .center-panel { min-height: 40vh; }
}
</style>
