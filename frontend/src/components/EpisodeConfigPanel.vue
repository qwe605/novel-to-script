<script setup>
/**
 * 分集配置面板 — 右栏（仅漫剧模式显示）。
 * 包含：分集参数设置 + 生成结果卡片列表 + 封面图提示词生成。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generateCover } from '../api/convert.js'

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
    <div class="panel-title">🎬 分集设置</div>
    <div class="panel-scroll">
      <div class="config-section">
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
            <span class="label-hint" style="margin-top:2px">{{ durationLabel }}</span>
          </div>

          <div class="config-group">
            <label>🪝 集末钩子风格</label>
            <el-select v-model="episodeConfig.hook_style" size="small">
              <el-option v-for="opt in hookStyleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </div>

          <div class="config-group">
            <label>✂️ 自动切分场景</label>
            <el-switch v-model="episodeConfig.auto_split" size="small" />
          </div>

          <div class="config-group">
            <label>📝 集标题模板</label>
            <el-input v-model="episodeConfig.title_template" size="small" placeholder="第{n}集 {subtitle}" />
            <span class="label-hint">可用变量: <code>{n}</code> <code>{subtitle}</code> <code>{pause}</code></span>
          </div>

          <div class="config-group">
            <label>🏷️ 场景前缀 <span class="label-hint">（可选）</span></label>
            <el-input v-model="episodeConfig.scene_prefix" size="small" placeholder="例：S01E{n:02d}" />
          </div>
        </template>

        <div v-else class="disabled-hint">
          💡 不启用分集时，所有场景将合并在一个输出中
        </div>
      </div>

      <!-- 生成结果 -->
      <div class="section-divider" v-if="episodes.length"><span>📺 生成结果</span></div>

      <div v-if="!episodes.length && !loading" class="empty-state">
        <div class="empty-icon">🎞️</div>
        <div class="empty-text">设置分集参数后开始转换</div>
        <div class="empty-hint">集数结果将在此处展示</div>
      </div>
      <div v-else-if="loading" class="empty-state">
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

          <!-- 封面生成 -->
          <div class="cover-actions">
            <el-button
              size="small" text
              :loading="coverGenerating[ep.episode_id]"
              @click="onGenerateCover(ep)"
            >
              🎨 {{ coverResults[ep.episode_id] ? '重新生成封面' : '生成封面' }}
            </el-button>
            <el-button
              v-if="coverResults[ep.episode_id]"
              size="small" text
              @click="copyPrompt(ep.episode_id)"
            >
              📋 复制提示词
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
/* ... existing styles unchanged ... */
.panel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
.panel-title { padding: 14px 18px; font-size: 14px; font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.panel-scroll { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; }

.right-panel { width: 320px; flex-shrink: 0; }

.config-section { display: flex; flex-direction: column; gap: 12px; }
.config-group { display: flex; flex-direction: column; gap: 6px; }
.config-group label { font-size: 12px; color: var(--text-muted); font-weight: 500; }

.label-hint { font-size: 10px; color: var(--text-muted); font-weight: 400; }
.label-hint code { font-family: var(--mono); font-size: 10px; background: var(--bg-card); padding: 1px 3px; border-radius: 2px; }

.duration-row { display: flex; align-items: center; gap: 6px; }
.duration-sep { color: var(--text-muted); font-weight: 500; }

.disabled-hint { padding: 12px; background: var(--bg-card); border-radius: 8px; font-size: 12px; color: var(--text-muted); text-align: center; }

.section-divider { padding: 8px 0; font-size: 12px; font-weight: 600; color: var(--text-secondary); border-top: 1px solid var(--border); text-align: center; }
.section-divider span { background: var(--bg-panel); padding: 0 8px; }

.empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); min-height: 120px; }
.empty-icon { font-size: 48px; opacity: 0.4; margin-bottom: 12px; }
.empty-text { font-size: 14px; color: var(--text-secondary); margin-bottom: 4px; }
.empty-hint { font-size: 12px; color: var(--text-muted); }

.episode-list { display: flex; flex-direction: column; gap: 10px; }
.episode-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; transition: border-color 0.2s; }
.episode-card:hover { border-color: var(--border-light); }
.episode-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.ep-num { font-size: 13px; font-weight: 600; color: var(--accent-amber); }
.ep-duration { font-size: 11px; color: var(--text-muted); background: var(--bg-deep); padding: 2px 6px; border-radius: 4px; }
.ep-title { font-size: 12px; color: var(--text-primary); font-weight: 500; margin-bottom: 4px; }
.ep-hook { font-size: 11px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ep-meta { display: flex; gap: 8px; font-size: 10px; color: var(--text-muted); margin-bottom: 4px; }
.ep-meta span { background: var(--bg-deep); padding: 2px 6px; border-radius: 4px; }

/* cover */
.cover-actions { display: flex; gap: 4px; border-top: 1px solid var(--border); padding-top: 6px; margin-top: 4px; }
.cover-result { margin-top: 6px; padding: 8px; background: var(--bg-deep); border-radius: 6px; }
.cover-meta { display: flex; gap: 8px; font-size: 10px; color: var(--text-muted); margin-bottom: 4px; }
.cover-meta span { background: var(--bg-card); padding: 1px 6px; border-radius: 3px; }
.cover-prompt-en { font-size: 10px; color: var(--text-secondary); line-height: 1.5; word-break: break-word; font-family: var(--mono); }

:deep(.el-switch.is-checked .el-switch__core) { background: var(--accent-cyan); border-color: var(--accent-cyan); }
:deep(.el-select) { width: 100%; }
</style>
