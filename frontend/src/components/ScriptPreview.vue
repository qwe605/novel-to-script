<script setup>
import { computed, ref } from 'vue'
import yaml from 'js-yaml'

const props = defineProps({
  yamlText: { type: String, default: '' },
  config: { type: Object, default: () => ({ script_type: 'manju' }) },
  characters: { type: Array, default: () => [] },
})

const emit = defineEmits(['update-beat'])

const script = computed(() => {
  try { return yaml.load(props.yamlText)?.script || null }
  catch { return null }
})

const title = computed(() => script.value?.title || '未命名剧本')
const metadata = computed(() => script.value?.metadata || {})
const scenes = computed(() => script.value?.scenes || [])
const episodes = computed(() => script.value?.episodes || [])
const sequences = computed(() => script.value?.sequences || [])

// Build episode → scene map
const episodeSceneMap = computed(() => {
  const map = {}
  for (const ep of episodes.value) {
    for (const sid of (ep.scenes || [])) {
      map[sid] = { epNum: ep.episode_number, epTitle: ep.title, hook: ep.hook }
    }
  }
  return map
})

// Build character id → name map
const charMap = computed(() => {
  const map = {}
  for (const c of (script.value?.characters || [])) {
    const name = c.name?.split('：').pop()?.split('（')[0]?.trim() || c.name || c.id
    map[c.id] = name
  }
  return map
})

function charName(id) {
  if (!id) return ''
  return charMap.value[id] || id
}

const expandedScenes = ref({})

function toggleScene(id) {
  expandedScenes.value[id] = !expandedScenes.value[id]
}

const beatTypeIcon = {
  action: '🎬', dialogue: '💬', narration: '📢', vos: '🧠',
  sfx: '🔊', music: '🎵', transition: '✂️',
}

const shotLabels = {
  'EXTREME_CLOSE-UP': '大特写', 'CLOSE-UP': '特写', 'MEDIUM': '中景',
  'WIDE': '全景', 'LONG': '远景', 'MEDIUM_CLOSE-UP': '近景',
}

const sceneTypeLabels = {
  dialogue_heavy: '对白为主', action: '动作', static: '静态',
  montage: '蒙太奇', transition: '转场',
}

// Export HTML storyboard
function exportHTML() {
  const s = script.value
  if (!s) return
  const epTitle = s.title || '剧本'
  const rows = scenes.value.map((sc, i) => {
    const epInfo = episodeSceneMap.value[sc.scene_id]
    const epTag = epInfo ? `<span style="background:#f59e0b20;color:#f59e0b;padding:1px 6px;border-radius:4px;font-size:11px">第${epInfo.epNum}集</span>` : ''
    const beats = (sc.beats||[]).map(b => {
      const ch = charName(b.character)
      const mj = b.extensions?.manju || {}
      return `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #222">
        <span style="color:#666;min-width:24px">${beatTypeIcon[b.type]||'•'}</span>
        ${ch?`<span style="color:#22d3ee;min-width:48px">${ch}</span>`:''}
        <span style="flex:1;color:#ccc">${b.content||''}</span>
        <span style="color:#666;font-size:11px">${mj.duration_seconds||''}s</span>
      </div>`
    }).join('')
    return `<div style="margin:8px 0;background:#1a1d28;border-radius:8px;padding:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <b style="color:#fff">${sc.heading?.int_ext||''} ${sc.heading?.location||''} - ${sc.heading?.time||''}</b>
        ${epTag}
      </div>
      ${beats}
    </div>`
  }).join('')
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${epTitle} - 分镜脚本</title>
<style>body{background:#0b0d12;color:#e8eaf0;font-family:system-ui;max-width:800px;margin:0 auto;padding:20px}
h1{color:#22d3ee}</style></head><body>
<h1>${epTitle}</h1><p>场景:${s.metadata?.total_scenes||0} | 节拍:${s.metadata?.total_beats||0} | 集数:${s.metadata?.total_episodes||0} | 时长:${s.metadata?.estimated_duration_minutes||0}min</p>
${rows}</body></html>`
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${epTitle}_分镜脚本.html`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <div class="script-preview" v-if="script">
    <!-- Header -->
    <div class="sp-header">
      <div class="sp-title-row">
        <h2 class="sp-title">{{ title }}</h2>
        <span class="sp-type-badge">{{ config.script_type === 'manju' ? '网文漫剧' : config.script_type === 'screenplay' ? '影视剧本' : config.script_type === 'audio_drama' ? '广播剧' : '舞台剧' }}</span>
        <button class="export-btn" @click="exportHTML" title="导出HTML分镜脚本">📥 导出分镜</button>
      </div>
      <div class="sp-meta">
        <span>{{ metadata.total_scenes || 0 }} 场景</span>
        <span>{{ metadata.total_beats || 0 }} 节拍</span>
        <span v-if="metadata.total_episodes">{{ metadata.total_episodes }} 集</span>
        <span>{{ metadata.estimated_duration_minutes || 0 }}min</span>
        <span v-if="metadata.adapted_by" class="sp-by">{{ metadata.adapted_by }}</span>
      </div>
    </div>

    <!-- Character Roster -->
    <div class="sp-characters" v-if="script.characters?.length">
      <div class="sp-section-title">👥 角色表</div>
      <div class="char-chips">
        <span v-for="c in script.characters" :key="c.id" class="char-chip" :title="c.description">
          {{ charName(c.id) }}
          <small v-if="c.archetype">{{ c.archetype }}</small>
        </span>
      </div>
    </div>

    <!-- Episode Navigation (manju) -->
    <div class="sp-episodes" v-if="episodes.length && config.script_type === 'manju'">
      <div class="sp-section-title">📺 集数</div>
      <div class="ep-tabs">
        <span v-for="ep in episodes" :key="ep.episode_id" class="ep-tab">
          第{{ ep.episode_number }}集: {{ ep.title }}
          <small>{{ Math.round((ep.target_duration_seconds||240)/60) }}min · {{ ep.scenes?.length||0 }}场景</small>
        </span>
      </div>
    </div>

    <!-- Scene List -->
    <div class="sp-section-title">🎞️ 场景列表（共 {{ scenes.length }} 场）</div>
    <div class="scene-list">
      <div v-for="(sc, idx) in scenes" :key="sc.scene_id" class="scene-card">
        <!-- Scene Header -->
        <div class="scene-header" @click="toggleScene(sc.scene_id)">
          <div class="scene-heading-info">
            <span class="scene-num">#{{ idx + 1 }}</span>
            <span class="scene-location">
              <b>{{ sc.heading?.int_ext || 'INT.' }}</b>
              {{ sc.heading?.location || '—' }}
              <span class="scene-time">{{ sc.heading?.time || 'DAY' }}</span>
            </span>
            <span class="scene-badges">
              <span class="sbadge type">{{ sceneTypeLabels[sc.type] || sc.type }}</span>
              <span v-if="sc.mood" class="sbadge mood">{{ sc.mood }}</span>
              <span v-if="episodeSceneMap[sc.scene_id]" class="sbadge ep">
                第{{ episodeSceneMap[sc.scene_id].epNum }}集
              </span>
            </span>
          </div>
          <div class="scene-meta-right">
            <span class="scene-dur">{{ sc.estimated_duration_seconds || 0 }}s</span>
            <span class="scene-arrow">{{ expandedScenes[sc.scene_id] ? '▾' : '▸' }}</span>
          </div>
        </div>

        <!-- Beat Table (expandable) -->
        <div v-if="expandedScenes[sc.scene_id]" class="beat-table">
          <div class="beat-row header">
            <span class="col-num">#</span>
            <span class="col-type">类型</span>
            <span class="col-char">角色</span>
            <span class="col-content">内容</span>
            <span class="col-dur">⏱</span>
          </div>
          <div v-for="beat in (sc.beats || [])" :key="beat.beat_id" class="beat-row"
            :class="'beat-' + beat.type">
            <span class="col-num">{{ beat.beat_id?.split('_').pop() }}</span>
            <span class="col-type" :title="beat.type">
              {{ beatTypeIcon[beat.type] || '•' }}
            </span>
            <span class="col-char" v-if="beat.character">
              <span class="char-tag">{{ charName(beat.character) }}</span>
            </span>
            <span class="col-char" v-else><span class="char-tag empty">—</span></span>
            <span class="col-content">
              <template v-if="beat.type === 'dialogue'">
                <span class="dialogue-mark">"</span>{{ beat.content }}<span class="dialogue-mark">"</span>
              </template>
              <template v-else-if="beat.type === 'narration' || beat.type === 'vos'">
                <em>"{{ beat.content }}"</em>
              </template>
              <template v-else>
                {{ beat.content }}
              </template>
              <span v-if="beat.parenthetical" class="paren">（{{ beat.parenthetical }}）</span>
            </span>
            <span class="col-dur">{{ beat.extensions?.manju?.duration_seconds || beat.extensions?.screenplay?.duration_seconds || '—' }}s</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="sp-empty">
    <div class="empty-icon">📜</div>
    <div>暂无剧本数据</div>
  </div>
</template>

<style scoped>
.script-preview {
  height: 100%; overflow-y: auto; padding: 16px 20px;
  font-size: 13px; color: var(--text-primary);
}

.sp-header {
  margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid var(--border);
}
.sp-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.sp-title { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0; }
.sp-type-badge {
  font-size: 11px; background: var(--accent-cyan-dim); color: var(--accent-cyan);
  padding: 3px 10px; border-radius: 6px; font-weight: 500;
}
.export-btn {
  margin-left: auto; font-size: 12px; padding: 4px 12px;
  background: var(--bg-card); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
  transition: all 0.2s;
}
.export-btn:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }

.sp-meta { display: flex; gap: 14px; flex-wrap: wrap; }
.sp-meta span {
  font-size: 12px; color: var(--text-muted);
  background: var(--bg-card); padding: 2px 10px; border-radius: 6px;
}
.sp-by { color: var(--text-secondary) !important; }

/* Character chips */
.sp-characters { margin-bottom: 16px; }
.sp-section-title {
  font-size: 12px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
}
.char-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.char-chip {
  font-size: 12px; background: var(--bg-card); border: 1px solid var(--border);
  padding: 4px 10px; border-radius: 20px; color: var(--text-primary);
  display: flex; align-items: baseline; gap: 6px; cursor: default;
}
.char-chip small { font-size: 10px; color: var(--text-muted); }

/* Episodes */
.sp-episodes { margin-bottom: 16px; }
.ep-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.ep-tab {
  font-size: 12px; background: var(--bg-card); border: 1px solid var(--border);
  padding: 6px 12px; border-radius: 8px; color: var(--accent-amber);
  display: flex; gap: 8px; align-items: baseline;
}
.ep-tab small { color: var(--text-muted); font-size: 10px; }

/* Scene cards */
.scene-list { display: flex; flex-direction: column; gap: 8px; }
.scene-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden;
  transition: border-color 0.2s;
}
.scene-card:hover { border-color: var(--border-light); }

.scene-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; cursor: pointer; user-select: none;
  transition: background 0.15s;
}
.scene-header:hover { background: var(--bg-hover); }

.scene-heading-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.scene-num { font-size: 11px; color: var(--text-muted); font-family: var(--mono); min-width: 24px; }
.scene-location { font-size: 13px; color: var(--text-primary); }
.scene-location b { color: var(--accent-cyan); font-weight: 600; margin-right: 4px; }
.scene-time {
  font-size: 10px; color: var(--text-muted); background: var(--bg-deep);
  padding: 1px 6px; border-radius: 4px; margin-left: 6px;
}
.scene-badges { display: flex; gap: 4px; }
.sbadge {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 500;
}
.sbadge.type { background: rgba(34,211,238,0.1); color: var(--accent-cyan); }
.sbadge.mood { background: rgba(168,85,247,0.1); color: #a855f7; }
.sbadge.ep { background: rgba(245,158,11,0.1); color: var(--accent-amber); }

.scene-meta-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.scene-dur { font-size: 11px; color: var(--text-muted); font-family: var(--mono); }
.scene-arrow { font-size: 14px; color: var(--text-muted); transition: transform 0.2s; }

/* Beat table */
.beat-table { border-top: 1px solid var(--border); overflow-x: auto; }
.beat-row {
  display: flex; align-items: flex-start; gap: 6px; padding: 6px 14px;
  border-bottom: 1px solid rgba(42,46,61,0.5); font-size: 12px;
  min-height: 32px;
}
.beat-row.header {
  font-size: 10px; color: var(--text-muted); text-transform: uppercase;
  letter-spacing: 0.3px; border-bottom: 1px solid var(--border); background: var(--bg-deep);
}
.beat-row:last-child { border-bottom: none; }

.col-num { min-width: 28px; color: var(--text-muted); font-family: var(--mono); font-size: 11px; }
.col-type { min-width: 28px; text-align: center; font-size: 14px; }
.col-char { min-width: 56px; }
.char-tag {
  display: inline-block; font-size: 11px; background: rgba(34,211,238,0.1); color: var(--accent-cyan);
  padding: 0 6px; border-radius: 4px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.char-tag.empty { background: transparent; color: var(--text-muted); }

.col-content { flex: 1; line-height: 1.5; color: var(--text-secondary); min-width: 120px; }
.dialogue-mark { color: var(--accent-amber); }
.paren { color: var(--text-muted); font-size: 10px; margin-left: 4px; font-style: italic; }
.col-dur { min-width: 36px; text-align: right; font-size: 10px; color: var(--text-muted); font-family: var(--mono); }

/* Beat type highlights */
.beat-dialogue { background: rgba(245,158,11,0.03); }
.beat-dialogue .col-content { color: var(--accent-amber); }
.beat-action { background: rgba(34,211,238,0.02); }
.beat-narration, .beat-vos { background: rgba(168,85,247,0.03); }
.beat-sfx, .beat-music { background: rgba(52,211,153,0.03); }

.sp-empty {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; color: var(--text-muted); gap: 12px;
}
</style>
