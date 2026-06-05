<script setup>
import { computed, reactive, ref, watch } from 'vue'
import yaml from 'js-yaml'

const props = defineProps({
  yamlText: { type: String, default: '' },
  config: { type: Object, default: () => ({ script_type: 'manju' }) },
})

const emit = defineEmits(['update:yamlText'])

// 用 reactive 持有 script 数据（确保编辑后即时反映到 UI）
const scriptData = reactive({ value: null })

function parseCurrent() {
  try { scriptData.value = yaml.load(props.yamlText)?.script || null }
  catch { scriptData.value = null }
}
parseCurrent()

watch(() => props.yamlText, () => parseCurrent())

const script = computed(() => scriptData.value)

// --------------- 编辑状态 ---------------
const expandedScenes = reactive({})
const editingBeat = ref(null)    // { sceneId, beatId } or null
const editingScene = ref(null)   // sceneId or null
const editBuffer = reactive({ content: '', type: '', character: '', parenthetical: '' })

function toggleScene(id) {
  expandedScenes[id] = !expandedScenes[id]
}

function startEditBeat(sceneId, beat) {
  editBuffer.content = beat.content || ''
  editBuffer.type = beat.type || 'action'
  editBuffer.character = beat.character || ''
  editBuffer.parenthetical = beat.parenthetical || ''
  editingBeat.value = { sceneId, beatId: beat.beat_id }
}

function cancelEditBeat() {
  editingBeat.value = null
}

function saveEditBeat() {
  if (!editingBeat.value) return
  const { sceneId, beatId } = editingBeat.value
  const sc = (script.value?.scenes || []).find(s => s.scene_id === sceneId)
  if (!sc) return
  const beat = (sc.beats || []).find(b => b.beat_id === beatId)
  if (!beat) return
  beat.content = editBuffer.content
  beat.type = editBuffer.type
  beat.character = editBuffer.character || null
  beat.parenthetical = editBuffer.parenthetical || null
  editingBeat.value = null
  emitUpdated()
}

function startEditScene(id) { editingScene.value = id }
function cancelEditScene() { editingScene.value = null }

function saveEditScene() {
  if (!editingScene.value) return
  const sc = (script.value?.scenes || []).find(s => s.scene_id === editingScene.value)
  if (!sc) return
  // Buffer stored on sc._edit via reactive by the template binding
  editingScene.value = null
  emitUpdated()
}

function emitUpdated() {
  const s = script.value
  if (!s) return
  const doc = { script: s }
  emit('update:yamlText', yaml.dump(doc, { lineWidth: -1, noRefs: true }))
}

// --------------- helpers ---------------
const title = computed(() => script.value?.title || '未命名剧本')
const metadata = computed(() => script.value?.metadata || {})
const scenes = computed(() => script.value?.scenes || [])
const episodes = computed(() => script.value?.episodes || [])

const episodeSceneMap = computed(() => {
  const map = {}
  for (const ep of episodes.value) {
    for (const sid of (ep.scenes || [])) {
      map[sid] = { epNum: ep.episode_number, epTitle: ep.title, hook: ep.hook }
    }
  }
  return map
})

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

const beatTypeIcon = {
  action: '🎬', dialogue: '💬', narration: '📢', vos: '🧠',
  sfx: '🔊', music: '🎵', transition: '✂️',
}
const beatTypes = ['action', 'dialogue', 'narration', 'vos', 'sfx', 'music', 'transition']

const sceneTypeLabels = {
  dialogue_heavy: '对白为主', action: '动作', static: '静态',
  montage: '蒙太奇', transition: '转场',
}
const sceneTypes = ['dialogue_heavy', 'action', 'static', 'montage', 'transition']

const timeOptions = ['DAY', 'NIGHT', 'DAWN', 'DUSK', 'LATER', 'CONTINUOUS']
const intExtOptions = ['INT.', 'EXT.', 'INT./EXT.']

// --------------- 新增 beat ---------------
function addBeat(sceneId) {
  const sc = (script.value?.scenes || []).find(s => s.scene_id === sceneId)
  if (!sc) return
  const maxNum = (sc.beats || []).reduce((m, b) => Math.max(m, parseInt(b.beat_id?.split('_').pop()) || 0), 0)
  const newBeat = {
    beat_id: `b_${String(maxNum + 1).padStart(3, '0')}`,
    type: 'action',
    character: null,
    content: '【新节拍】',
    parenthetical: null,
    extensions: { screenplay: null, audio_drama: null, stage_play: null, manju: null },
  }
  sc.beats.push(newBeat)
  emitUpdated()
  // 自动打开编辑
  expandedScenes[sceneId] = true
  startEditBeat(sceneId, newBeat)
}

function deleteBeat(sceneId, beatId) {
  const sc = (script.value?.scenes || []).find(s => s.scene_id === sceneId)
  if (!sc || !sc.beats) return
  const idx = sc.beats.findIndex(b => b.beat_id === beatId)
  if (idx < 0) return
  sc.beats.splice(idx, 1)
  if (editingBeat.value?.beatId === beatId) editingBeat.value = null
  emitUpdated()
}

// --------------- 导出 ---------------
function exportHTML() {
  const s = script.value
  if (!s) return
  const epTitle = s.title || '剧本'
  const rows = scenes.value.map((sc) => {
    const epInfo = episodeSceneMap.value[sc.scene_id]
    const epTag = epInfo ? `<span style="background:#f59e0b20;color:#f59e0b;padding:1px 6px;border-radius:4px;font-size:11px">第${epInfo.epNum}集</span>` : ''
    const beats = (sc.beats||[]).map(b => {
      const ch = charName(b.character)
      return `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #222">
        <span style="color:#666;min-width:24px">${beatTypeIcon[b.type]||'•'}</span>
        ${ch?`<span style="color:#22d3ee;min-width:48px">${ch}</span>`:''}
        <span style="flex:1;color:#ccc">${b.content||''}</span>
        <span style="color:#666;font-size:11px">${b.extensions?.manju?.duration_seconds||''}s</span>
      </div>`
    }).join('')
    return `<div style="margin:8px 0;background:#1a1d28;border-radius:8px;padding:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <b style="color:#fff">${sc.heading?.int_ext||''} ${sc.heading?.location||''} - ${sc.heading?.time||''}</b>
        ${epTag}
      </div>${beats}</div>`
  }).join('')
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${epTitle} - 分镜脚本</title>
<style>body{background:#0b0d12;color:#e8eaf0;font-family:system-ui;max-width:800px;margin:0 auto;padding:20px}
h1{color:#22d3ee}</style></head><body>
<h1>${epTitle}</h1><p>场景:${s.metadata?.total_scenes||0} | 节拍:${s.metadata?.total_beats||0} | 时长:${s.metadata?.estimated_duration_minutes||0}min</p>
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
        <button class="export-btn" @click="exportHTML" title="导出HTML分镜脚本">📥 导出 HTML</button>
      </div>
      <div class="sp-meta">
        <span>{{ metadata.total_scenes || 0 }} 场景</span>
        <span>{{ metadata.total_beats || 0 }} 节拍</span>
        <span v-if="metadata.total_episodes">{{ metadata.total_episodes }} 集</span>
        <span>{{ metadata.estimated_duration_minutes || 0 }}min</span>
        <span class="sp-hint">💡 点击节拍或场景可直接编辑，编辑后自动更新</span>
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

    <!-- Episode Navigation -->
    <div class="sp-episodes" v-if="episodes.length && config.script_type === 'manju'">
      <div class="sp-section-title">📺 集数</div>
      <div class="ep-tabs">
        <span v-for="ep in episodes" :key="ep.episode_id" class="ep-tab">
          第{{ ep.episode_number }}集: {{ ep.title }}
          <small>{{ Math.round((ep.target_duration_seconds||240)/60) }}min · {{ ep.scenes?.length||0 }}场</small>
        </span>
      </div>
    </div>

    <!-- Scene List -->
    <div class="sp-section-title">🎞️ 场景列表（共 {{ scenes.length }} 场）</div>
    <div class="scene-list">
      <div v-for="(sc, idx) in scenes" :key="sc.scene_id" class="scene-card">
        <!-- Scene Header -->
        <div class="scene-header">
          <div class="scene-heading-info" @click="toggleScene(sc.scene_id)" style="cursor:pointer;flex:1">
            <span class="scene-num">#{{ idx + 1 }}</span>
            <span class="scene-location">
              <b>{{ sc.heading?.int_ext || 'INT.' }}</b>
              {{ sc.heading?.location || '—' }}
              <span class="scene-time">{{ sc.heading?.time || 'DAY' }}</span>
            </span>
            <span class="scene-badges">
              <span class="sbadge type" @click.stop>{{ sceneTypeLabels[sc.type] || sc.type }}</span>
              <span v-if="sc.mood" class="sbadge mood">{{ sc.mood }}</span>
              <span v-if="episodeSceneMap[sc.scene_id]" class="sbadge ep">第{{ episodeSceneMap[sc.scene_id].epNum }}集</span>
            </span>
          </div>
          <button class="edit-icon-btn" @click="startEditScene(sc.scene_id)" title="编辑场景信息">✏️</button>
          <span class="scene-dur">{{ sc.estimated_duration_seconds || 0 }}s</span>
          <span class="scene-arrow" @click="toggleScene(sc.scene_id)" style="cursor:pointer">{{ expandedScenes[sc.scene_id] ? '▾' : '▸' }}</span>
        </div>

        <!-- Scene inline edit bar -->
        <div v-if="editingScene === sc.scene_id" class="scene-edit-bar">
          <select v-model="sc.heading.int_ext" @change="emitUpdated()" class="edit-select">
            <option v-for="o in intExtOptions" :key="o" :value="o">{{ o }}</option>
          </select>
          <input v-model="sc.heading.location" @input="emitUpdated()" class="edit-input" placeholder="地点" style="flex:2" />
          <select v-model="sc.heading.time" @change="emitUpdated()" class="edit-select">
            <option v-for="o in timeOptions" :key="o" :value="o">{{ o }}</option>
          </select>
          <select v-model="sc.type" @change="emitUpdated()" class="edit-select" style="flex:1">
            <option v-for="o in sceneTypes" :key="o" :value="o">{{ sceneTypeLabels[o] || o }}</option>
          </select>
          <input v-model="sc.mood" @input="emitUpdated()" class="edit-input" placeholder="情绪（可选）" style="flex:1" />
          <button class="done-btn" @click="saveEditScene()">✓</button>
        </div>

        <!-- Beat Table (expandable) -->
        <div v-if="expandedScenes[sc.scene_id]" class="beat-table">
          <div class="beat-row header">
            <span class="col-num">#</span>
            <span class="col-type">类型</span>
            <span class="col-char">角色</span>
            <span class="col-content">内容</span>
            <span class="col-dur">⏱</span>
            <span class="col-act"></span>
          </div>

          <div v-for="beat in (sc.beats || [])" :key="beat.beat_id" class="beat-row"
            :class="['beat-' + beat.type, { editing: editingBeat?.beatId === beat.beat_id }]">

            <!-- 编辑模式 -->
            <template v-if="editingBeat?.sceneId === sc.scene_id && editingBeat?.beatId === beat.beat_id">
              <span class="col-num">{{ beat.beat_id?.split('_').pop() }}</span>
              <span class="col-type">
                <select v-model="editBuffer.type" class="edit-select">
                  <option v-for="bt in beatTypes" :key="bt" :value="bt">{{ beatTypeIcon[bt] || bt }} {{ bt }}</option>
                </select>
              </span>
              <span class="col-char">
                <input v-model="editBuffer.character" class="edit-input" placeholder="角色ID" style="width:72px" list="char-list" />
              </span>
              <span class="col-content">
                <input v-model="editBuffer.content" class="edit-input" placeholder="内容" style="width:100%" @keyup.enter="saveEditBeat()" />
              </span>
              <span class="col-dur">—s</span>
              <span class="col-act">
                <button class="done-btn" @click="saveEditBeat()">✓</button>
                <button class="cancel-btn" @click="cancelEditBeat()">✕</button>
              </span>
            </template>

            <!-- 显示模式 -->
            <template v-else>
              <span class="col-num">{{ beat.beat_id?.split('_').pop() }}</span>
              <span class="col-type" :title="beat.type">
                {{ beatTypeIcon[beat.type] || '•' }}
              </span>
              <span class="col-char" v-if="beat.character">
                <span class="char-tag">{{ charName(beat.character) }}</span>
              </span>
              <span class="col-char" v-else><span class="char-tag empty">—</span></span>
              <span class="col-content" @click="startEditBeat(sc.scene_id, beat)" title="点击编辑">
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
              <span class="col-act">
                <button class="mini-btn" @click="startEditBeat(sc.scene_id, beat)" title="编辑">✏️</button>
                <button class="mini-btn del" @click="deleteBeat(sc.scene_id, beat.beat_id)" title="删除">🗑</button>
              </span>
            </template>
          </div>

          <!-- 新增节拍按钮 -->
          <div class="beat-row add-row">
            <button class="add-beat-btn" @click="addBeat(sc.scene_id)">+ 添加节拍</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Datalist for character autocomplete -->
    <datalist id="char-list">
      <option v-for="c in (script.characters || [])" :key="c.id" :value="c.id">{{ charName(c.id) }}</option>
    </datalist>
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

.sp-header { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid var(--border); }
.sp-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.sp-title { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0; }
.sp-type-badge { font-size: 11px; background: var(--accent-cyan-dim); color: var(--accent-cyan); padding: 3px 10px; border-radius: 6px; font-weight: 500; }
.sp-hint { font-size: 11px !important; color: var(--accent-amber) !important; background: var(--accent-amber-dim) !important; }
.export-btn { margin-left: auto; font-size: 12px; padding: 4px 12px; background: var(--bg-card); color: var(--text-secondary); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; transition: all 0.2s; }
.export-btn:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }
.sp-meta { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.sp-meta > span { font-size: 12px; color: var(--text-muted); background: var(--bg-card); padding: 2px 10px; border-radius: 6px; }

.sp-characters { margin-bottom: 16px; }
.sp-section-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.char-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.char-chip { font-size: 12px; background: var(--bg-card); border: 1px solid var(--border); padding: 4px 10px; border-radius: 20px; color: var(--text-primary); display: flex; align-items: baseline; gap: 6px; cursor: default; }
.char-chip small { font-size: 10px; color: var(--text-muted); }

.sp-episodes { margin-bottom: 16px; }
.ep-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.ep-tab { font-size: 12px; background: var(--bg-card); border: 1px solid var(--border); padding: 6px 12px; border-radius: 8px; color: var(--accent-amber); display: flex; gap: 8px; align-items: baseline; }
.ep-tab small { color: var(--text-muted); font-size: 10px; }

/* Scene cards */
.scene-list { display: flex; flex-direction: column; gap: 8px; }
.scene-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; transition: border-color 0.2s; }
.scene-card:hover { border-color: var(--border-light); }
.scene-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; user-select: none; }
.scene-heading-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.scene-num { font-size: 11px; color: var(--text-muted); font-family: var(--mono); min-width: 24px; }
.scene-location { font-size: 13px; color: var(--text-primary); }
.scene-location b { color: var(--accent-cyan); font-weight: 600; margin-right: 4px; }
.scene-time { font-size: 10px; color: var(--text-muted); background: var(--bg-deep); padding: 1px 6px; border-radius: 4px; margin-left: 6px; }
.scene-badges { display: flex; gap: 4px; }
.sbadge { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 500; }
.sbadge.type { background: rgba(34,211,238,0.1); color: var(--accent-cyan); }
.sbadge.mood { background: rgba(168,85,247,0.1); color: #a855f7; }
.sbadge.ep { background: rgba(245,158,11,0.1); color: var(--accent-amber); }
.scene-dur { font-size: 11px; color: var(--text-muted); font-family: var(--mono); margin-right: 8px; }
.scene-arrow { font-size: 14px; color: var(--text-muted); }

/* Scene edit bar */
.scene-edit-bar { display: flex; gap: 6px; padding: 8px 14px; background: var(--bg-hover); border-top: 1px solid var(--border); align-items: center; flex-wrap: wrap; }

/* Beat table */
.beat-table { border-top: 1px solid var(--border); }
.beat-row { display: flex; align-items: flex-start; gap: 6px; padding: 6px 14px; border-bottom: 1px solid rgba(42,46,61,0.5); font-size: 12px; min-height: 32px; transition: background 0.1s; }
.beat-row.editing { background: var(--bg-hover) !important; }
.beat-row.header { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.3px; border-bottom: 1px solid var(--border); background: var(--bg-deep); }

.col-num { min-width: 28px; color: var(--text-muted); font-family: var(--mono); font-size: 11px; }
.col-type { min-width: 32px; text-align: center; font-size: 14px; }
.col-char { min-width: 60px; }
.col-content { flex: 1; line-height: 1.5; color: var(--text-secondary); min-width: 120px; cursor: pointer; border-radius: 4px; padding: 1px 4px; margin: -1px -4px; transition: background 0.1s; }
.col-content:hover { background: rgba(34,211,238,0.08); }
.col-dur { min-width: 34px; text-align: right; font-size: 10px; color: var(--text-muted); font-family: var(--mono); }
.col-act { min-width: 44px; display: flex; gap: 2px; justify-content: flex-end; opacity: 0; transition: opacity 0.1s; }
.beat-row:hover .col-act { opacity: 1; }

.char-tag { display: inline-block; font-size: 11px; background: rgba(34,211,238,0.1); color: var(--accent-cyan); padding: 0 6px; border-radius: 4px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.char-tag.empty { background: transparent; color: var(--text-muted); }
.dialogue-mark { color: var(--accent-amber); }
.paren { color: var(--text-muted); font-size: 10px; margin-left: 4px; font-style: italic; }

/* Beat type colors */
.beat-dialogue { background: rgba(245,158,11,0.03); }
.beat-dialogue .col-content { color: var(--accent-amber); }
.beat-action { background: rgba(34,211,238,0.02); }
.beat-narration, .beat-vos { background: rgba(168,85,247,0.03); }
.beat-sfx, .beat-music { background: rgba(52,211,153,0.03); }

/* Edit inputs */
.edit-input {
  background: var(--bg-deep); border: 1px solid var(--border);
  color: var(--text-primary); font-size: 12px; padding: 3px 6px;
  border-radius: 4px; font-family: var(--sans);
}
.edit-input:focus { border-color: var(--accent-cyan); outline: none; }
.edit-select {
  background: var(--bg-deep); border: 1px solid var(--border);
  color: var(--text-primary); font-size: 11px; padding: 2px 4px;
  border-radius: 4px; cursor: pointer;
}

.done-btn {
  background: var(--success); color: #0b0d12; border: none;
  padding: 3px 8px; border-radius: 4px; cursor: pointer; font-weight: 700; font-size: 12px;
}
.cancel-btn {
  background: none; color: var(--text-muted); border: 1px solid var(--border);
  padding: 2px 6px; border-radius: 4px; cursor: pointer; font-size: 11px;
}
.cancel-btn:hover { color: var(--danger); border-color: var(--danger); }

.edit-icon-btn {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 13px; padding: 2px 4px; opacity: 0;
  transition: opacity 0.1s;
}
.scene-header:hover .edit-icon-btn { opacity: 1; }
.edit-icon-btn:hover { color: var(--accent-cyan); }

.mini-btn {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 12px; padding: 1px 4px;
}
.mini-btn:hover { color: var(--accent-cyan); }
.mini-btn.del:hover { color: var(--danger); }

/* Add beat row */
.add-row { justify-content: center; padding: 8px; }
.add-beat-btn {
  font-size: 11px; padding: 4px 16px; background: var(--bg-deep);
  color: var(--text-muted); border: 1px dashed var(--border);
  border-radius: 6px; cursor: pointer; transition: all 0.2s;
}
.add-beat-btn:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }

.sp-empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); gap: 12px; }
.empty-icon { font-size: 48px; opacity: 0.4; }
</style>
