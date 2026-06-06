<script setup>
/**
 * 分集配置面板 — 右栏（仅漫剧模式显示）。
 * 包含：分集参数设置 + 生成结果卡片列表 + 封面图提示词生成。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generateCover } from '../api/convert.js'
import { ICONS } from '../utils/icons.js'

const props = defineProps({
  episodeConfig:  { type: Object, required: true },
  hookStyleOptions:{ type: Array,  default: () => [] },
  episodes:       { type: Array,  default: () => [] },
  loading:        { type: Boolean, default: false },
  scriptTitle:    { type: String, default: '' },
  scriptType:     { type: String, default: 'manju' },
  characters:     { type: Array,  default: () => [] },
})

const durationLabel = computed(() =>
  `${Math.round(props.episodeConfig.min_duration_seconds / 60)}–${Math.round(props.episodeConfig.max_duration_seconds / 60)} 分钟/集`
)

// ---- cover generation ----
const coverGenerating = ref({})   // { episode_id: true }
const coverResults   = ref({})   // { episode_id: { prompt_cn, prompt_en, style, aspect_ratio } }

async function onGenerateCover(ep) {
  if (coverGenerating.value[ep.episode_id]) return
  coverGenerating.value[ep.episode_id] = true
  try {
    const res = await generateCover({
      title: props.scriptTitle || '未命名剧本',
      script_type: props.scriptType,
      hook: ep.hook,
      characters: props.characters,
      episode_title: ep.title,
    })
    coverResults.value[ep.episode_id] = res
    ElMessage.success('封面提示词已生成')
  } catch {
    ElMessage.error('生成失败')
  } finally {
    coverGenerating.value[ep.episode_id] = false
  }
}

function copyPrompt(epId) {
  const r = coverResults.value[epId]
  if (!r) return
  navigator.clipboard.writeText(r.prompt_en).then(
    () => ElMessage.success('英文提示词已复制到剪贴板'),
  )
}
</script>

<template>
  <aside class="panel right-panel">
    <div class="panel-title">
      <span class="panel-title-label"><span class="pt-icon" v-html="ICONS.video" /> 分集设置</span>
    </div>
    <div class="panel-scroll">
      <div class="config-section">
        <div class="config-group">
          <label><span class="label-icon" v-html="ICONS.zap" /> 启用分集</label>
          <el-switch v-model="episodeConfig.enabled" size="small" />
        </div>

        <template v-if="episodeConfig.enabled">
          <div class="config-group">
            <label><span class="label-icon" v-html="ICONS.list" /> 目标集数 <span class="label-hint">（留空=自动）</span></label>
            <el-input-number v-model="episodeConfig.target_episodes" :min="1" :max="500"
              placeholder="自动" size="small" style="width:100%" />
          </div>

          <div class="config-group">
            <label><span class="label-icon" v-html="ICONS.clock" /> 集时长范围</label>
            <div class="duration-row">
              <el-input-number v-model="episodeConfig.min_duration_seconds" :min="60" :max="600"
                :step="30" size="small" style="width:45%" />
              <span class="duration-sep">—</span>
              <el-input-number v-model="episodeConfig.max_duration_seconds" :min="60" :max="600"
                :step="30" size="small" style="width:45%" />
            </div>
            <span class="label-hint" style="margin-top:2px">{{ durationLabel }}</span>
          </div>

          <div class="config-group">
            <label><span class="label-icon" v-html="ICONS.hook" /> 集末钩子风格</label>
            <el-select v-model="episodeConfig.hook_style" size="small">
              <el-option v-for="opt in hookStyleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </div>

          <div class="config-group">
            <label><span class="label-icon" v-html="ICONS.scissors" /> 自动切分场景</label>
            <el-switch v-model="episodeConfig.auto_split" size="small" />
          </div>

          <div class="config-group">
            <label><span class="label-icon" v-html="ICONS.edit" /> 集标题模板</label>
            <el-input v-model="episodeConfig.title_template" size="small" placeholder="第{n}集 {subtitle}" />
            <span class="label-hint">可用变量: <code>{n}</code> <code>{subtitle}</code> <code>{pause}</code></span>
          </div>

        </template>

        <div v-else class="disabled-hint">
          不启用分集时，所有场景将合并在一个输出中
        </div>
      </div>

      <!-- 生成结果 -->
      <div class="section-divider" v-if="episodes.length">
        <span><span class="si-icon" v-html="ICONS.monitor" /> 生成结果</span>
      </div>

      <div v-if="!episodes.length && !loading" class="empty-state">
        <div class="empty-graphic" v-html="ICONS.video" />
        <div class="empty-text">设置分集参数后开始转换</div>
        <div class="empty-hint">集数结果将在此处展示</div>
      </div>
      <div v-else-if="loading" class="empty-state">
        <div class="empty-graphic loading-pulse" v-html="ICONS.refresh" />
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

          <!-- 封面生成 -->
          <div class="cover-actions">
            <el-button
              size="small" text
              :loading="coverGenerating[ep.episode_id]"
              @click="onGenerateCover(ep)"
            >
              <span class="cover-btn-icon" v-html="ICONS.sparkles" /> {{ coverResults[ep.episode_id] ? '重新生成' : '生成封面' }}
            </el-button>
            <el-button
              v-if="coverResults[ep.episode_id]"
              size="small" text
              @click="copyPrompt(ep.episode_id)"
            >
              <span class="cover-btn-icon" v-html="ICONS.copy" /> 复制提示词
            </el-button>
          </div>

          <!-- 封面提示词展示 -->
          <div v-if="coverResults[ep.episode_id]" class="cover-result">
            <div class="cover-meta">
              <span>{{ coverResults[ep.episode_id].style }}</span>
              <span>{{ coverResults[ep.episode_id].aspect_ratio }}</span>
            </div>
            <div class="cover-prompt-en">{{ coverResults[ep.episode_id].prompt_en }}</div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* ---- 图标 ---- */
.panel-title-label { display: flex; align-items: center; gap: 7px; }
.pt-icon { display: flex; color: var(--text-tertiary); }
.label-icon { display: inline-flex; vertical-align: -2px; margin-right: 4px; color: var(--text-tertiary); }
.si-icon { display: inline-flex; vertical-align: -2px; margin-right: 4px; }
.empty-graphic { color: var(--text-tertiary); opacity: 0.25; margin-bottom: 10px; }
.loading-pulse { animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.25; } 50% { opacity: 0.5; } }
.cover-btn-icon { display: inline-flex; vertical-align: -2px; margin-right: 2px; }

/* ---- 面板基类 ---- */
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.right-panel { width: 304px; flex-shrink: 0; }

/* ---- 设置区 ---- */
.config-section { display: flex; flex-direction: column; gap: 10px; }
.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group > label {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.label-hint { font-size: 10px; color: var(--text-tertiary); font-weight: 400; }
.label-hint code {
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--bg-card);
  color: var(--text-tertiary);
  padding: 1px 4px;
  border-radius: 3px;
}

.duration-row { display: flex; align-items: center; gap: 6px; }
.duration-sep {
  color: var(--text-tertiary);
  font-weight: 500;
  font-size: 13px;
}

.disabled-hint {
  padding: 14px;
  background: var(--bg-card);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
  line-height: 1.5;
}

/* ---- 区隔线 ---- */
.section-divider {
  padding: 6px 0 4px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-top: 1px solid var(--border-subtle);
  text-align: center;
}
.section-divider span {
  background: var(--bg-panel);
  padding: 0 10px;
}

/* ---- 空状态 ---- */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  min-height: 120px;
  gap: 4px;
}
.empty-icon { font-size: 40px; opacity: 0.25; margin-bottom: 8px; }
.empty-text { font-size: 13px; color: var(--text-secondary); font-weight: 500; }
.empty-hint { font-size: 11px; color: var(--text-tertiary); }

/* ---- 集列表 ---- */
.episode-list { display: flex; flex-direction: column; gap: 8px; }
.episode-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 12px;
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
}
.episode-card:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-sm);
}

/* 集编号 */
.episode-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.ep-num {
  font-size: 12px;
  font-weight: 700;
  color: var(--amber);
  letter-spacing: -0.01em;
}
.ep-duration {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-surface);
  padding: 2px 7px;
  border-radius: 10px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* 集标题 */
.ep-title {
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 600;
  margin-bottom: 4px;
  letter-spacing: -0.01em;
}

/* 钩子 */
.ep-hook {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-weight: 400;
}

/* 元数据 */
.ep-meta {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}
.ep-meta span {
  background: var(--bg-surface);
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 450;
}

/* ---- 封面生成 ---- */
.cover-actions {
  display: flex;
  gap: 4px;
  border-top: 1px solid var(--border-subtle);
  padding-top: 6px;
  margin-top: 4px;
}
.cover-result {
  margin-top: 6px;
  padding: 10px;
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
}
.cover-meta {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: var(--text-tertiary);
  margin-bottom: 5px;
  font-weight: 500;
}
.cover-meta span {
  background: var(--bg-card);
  padding: 1px 7px;
  border-radius: 4px;
  letter-spacing: 0.01em;
}
.cover-prompt-en {
  font-size: 10px;
  color: var(--text-secondary);
  line-height: 1.55;
  word-break: break-word;
  font-family: var(--font-mono);
  font-weight: 450;
}

:deep(.el-select) { width: 100%; }
</style>
