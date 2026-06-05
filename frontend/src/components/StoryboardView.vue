<script setup>
import { computed, ref } from 'vue'
import yaml from 'js-yaml'

const props = defineProps({
  yamlText: { type: String, default: '' },
})

const script = computed(() => {
  try { return yaml.load(props.yamlText)?.script || null }
  catch { return null }
})

const scenes = computed(() => script.value?.scenes || [])
const episodes = computed(() => script.value?.episodes || [])

const charMap = computed(() => {
  const map = {}
  for (const c of (script.value?.characters || [])) {
    const name = c.name?.split('：').pop()?.split('（')[0]?.trim() || c.name || c.id
    map[c.id] = name
  }
  return map
})

function charName(id) { return id ? (charMap.value[id] || id) : '' }

const epSceneMap = computed(() => {
  const m = {}
  for (const ep of episodes.value) {
    for (const sid of (ep.scenes || [])) m[sid] = ep.episode_number
  }
  return m
})

const currentEp = ref(1)
const epOptions = computed(() => {
  if (!episodes.value.length) return []
  return episodes.value.map(e => ({ num: e.episode_number, title: e.title, scenes: e.scenes }))
})

const filteredScenes = computed(() => {
  if (!episodes.value.length) return scenes.value
  const ep = episodes.value.find(e => e.episode_number === currentEp.value)
  if (!ep) return scenes.value
  const ids = new Set(ep.scenes || [])
  return scenes.value.filter(s => ids.has(s.scene_id))
})

const currentScene = ref(null)
const currentSceneId = computed(() => currentScene.value?.scene_id)
function selectScene(sc) { currentScene.value = currentScene.value?.scene_id === sc.scene_id ? null : sc }

const shotLabels = {
  'EXTREME_CLOSE-UP': '大特写', 'CLOSE-UP': '特写',
  'MEDIUM': '中景', 'WIDE': '全景', 'LONG': '远景',
  'MEDIUM_CLOSE-UP': '近景', 'TWO_SHOT': '双人',
}

const seqColors = ['#22d3ee', '#f59e0b', '#a855f7', '#34d399', '#f472b6', '#60a5fa', '#fb923c', '#4ade80']
</script>

<template>
  <div class="storyboard" v-if="script">
    <!-- Episode Selector -->
    <div class="sb-toolbar" v-if="episodes.length">
      <span class="sb-ep-label">📺 选集：</span>
      <button v-for="ep in epOptions" :key="ep.num"
        class="sb-ep-btn" :class="{ active: ep.num === currentEp }"
        @click="currentEp = ep.num; currentScene = null">
        第{{ ep.num }}集
      </button>
    </div>

    <!-- Scene Thumbnail Strip -->
    <div class="sb-scene-strip" v-if="filteredScenes.length">
      <div v-for="(sc, i) in filteredScenes" :key="sc.scene_id"
        class="sb-scene-thumb"
        :class="{ active: currentSceneId === sc.scene_id }"
        @click="selectScene(sc)"
      >
        <span class="thumb-idx">S{{ i + 1 }}</span>
        <span class="thumb-loc">{{ sc.heading?.location?.slice(0, 6) || '—' }}</span>
        <span class="thumb-count">{{ sc.beats?.length || 0 }}镜</span>
      </div>
    </div>

    <!-- Panel Grid -->
    <div class="sb-panels" v-if="currentScene">
      <div class="sb-scene-bar">
        <span>{{ currentScene.heading?.int_ext }} {{ currentScene.heading?.location }}</span>
        <span class="sb-time">{{ currentScene.heading?.time }}</span>
        <span>{{ currentScene.beats?.length || 0 }} 镜头</span>
      </div>

      <div class="panel-grid">
        <div v-for="beat in (currentScene.beats || [])" :key="beat.beat_id"
          class="sb-panel"
          :class="'p-' + beat.type"
          :style="{ borderColor: seqColors[(currentScene.sequence_id?.split('_')[1]||1)%seqColors.length] + '40' }"
        >
          <!-- Panel Header -->
          <div class="panel-info">
            <span class="panel-shot">{{ shotLabels[beat.extensions?.manju?.shot] || beat.extensions?.manju?.shot || '—' }}</span>
            <span v-if="beat.extensions?.manju?.visual_effect" class="panel-fx">{{ beat.extensions.manju.visual_effect }}</span>
          </div>

          <!-- Character Badge -->
          <div class="panel-char" v-if="beat.character">
            {{ charName(beat.character) }}
          </div>

          <!-- Content Area -->
          <div class="panel-content" :class="{ dialogue: beat.type === 'dialogue' }">
            <template v-if="beat.type === 'dialogue'">
              <div class="bubble-tail"></div>
              <div class="bubble-text">{{ beat.content }}</div>
              <div class="bubble-sub" v-if="beat.parenthetical">{{ beat.parenthetical }}</div>
            </template>
            <template v-else-if="beat.type === 'narration' || beat.type === 'vos'">
              <div class="narration-box">「{{ beat.content }}」</div>
            </template>
            <template v-else>
              <div class="action-text">{{ beat.content }}</div>
            </template>
          </div>

          <!-- Footer -->
          <div class="panel-footer">
            <span>{{ beat.beat_id?.split('_').pop() }}</span>
            <span v-if="beat.extensions?.manju?.bgm" class="has-bgm" title="BGM">🎵</span>
            <span v-if="beat.extensions?.manju?.sfx" class="has-sfx" title="音效">🔊</span>
            <span class="panel-dur">{{ beat.extensions?.manju?.duration_seconds || '—' }}s</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div class="sb-empty" v-if="!currentScene && filteredScenes.length">
      <div class="empty-icon">👆</div>
      <div>点击上方场景卡片查看分镜</div>
      <div class="empty-hint">每个场景的镜头将以漫画分格形式展示</div>
    </div>
    <div class="sb-empty" v-if="!filteredScenes.length">
      <div class="empty-icon">🎞️</div>
      <div>暂无场景数据</div>
    </div>
  </div>
  <div v-else class="sb-empty">
    <div class="empty-icon">🎬</div>
    <div>加载剧本数据中...</div>
  </div>
</template>

<style scoped>
.storyboard {
  height: 100%; overflow-y: auto; display: flex; flex-direction: column;
  background: var(--bg-deep);
}

.sb-toolbar {
  display: flex; align-items: center; gap: 6px; padding: 10px 14px;
  background: var(--bg-panel); border-bottom: 1px solid var(--border);
  flex-shrink: 0; flex-wrap: wrap;
}
.sb-ep-label { font-size: 12px; color: var(--text-muted); }
.sb-ep-btn {
  font-size: 11px; padding: 3px 10px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--bg-card); color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s;
}
.sb-ep-btn:hover { border-color: var(--accent-cyan); }
.sb-ep-btn.active {
  background: var(--accent-cyan-dim); border-color: var(--accent-cyan);
  color: var(--accent-cyan); font-weight: 600;
}

.sb-scene-strip {
  display: flex; gap: 4px; padding: 8px 12px; overflow-x: auto;
  background: var(--bg-panel); border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sb-scene-thumb {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  min-width: 56px; padding: 6px 4px; border-radius: 8px;
  background: var(--bg-card); border: 1px solid var(--border);
  cursor: pointer; transition: all 0.15s; flex-shrink: 0;
}
.sb-scene-thumb:hover { border-color: var(--border-light); }
.sb-scene-thumb.active {
  border-color: var(--accent-cyan); background: var(--accent-cyan-dim);
}
.thumb-idx { font-size: 13px; font-weight: 700; color: var(--accent-cyan); }
.sb-scene-thumb.active .thumb-idx { color: var(--accent-cyan); }
.thumb-loc { font-size: 9px; color: var(--text-muted); max-width: 48px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thumb-count { font-size: 9px; color: var(--text-muted); }

.sb-panels { flex: 1; overflow-y: auto; padding: 12px; }
.sb-scene-bar {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
  padding: 8px 14px; background: var(--bg-card); border-radius: 8px;
  font-size: 12px; color: var(--text-primary);
}
.sb-scene-bar .sb-time {
  font-size: 10px; color: var(--text-muted);
  background: var(--bg-deep); padding: 1px 8px; border-radius: 4px;
}

/* Panel grid */
.panel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.sb-panel {
  background: var(--bg-card);
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px 6px;
  display: flex; flex-direction: column;
  min-height: 120px;
  transition: border-color 0.2s;
}
.sb-panel:hover { border-color: var(--border-light); }

.panel-info {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.panel-shot {
  font-size: 10px; color: var(--text-muted);
  background: var(--bg-deep); padding: 1px 6px; border-radius: 3px;
  font-family: var(--mono);
}
.panel-fx {
  font-size: 9px; color: #f472b6;
  background: rgba(244,114,182,0.1); padding: 1px 6px; border-radius: 3px;
}

.panel-char {
  font-size: 11px; color: var(--accent-cyan); font-weight: 600;
  background: rgba(34,211,238,0.08); display: inline-block;
  padding: 1px 8px; border-radius: 4px; margin-bottom: 6px;
  align-self: flex-start;
}

.panel-content { flex: 1; display: flex; align-items: center; justify-content: center; padding: 4px 0; }
.panel-content.dialogue {
  background: rgba(245,158,11,0.04); border-radius: 8px; padding: 8px;
  position: relative; flex-direction: column;
}
.bubble-tail {
  width: 0; height: 0;
  border-left: 6px solid transparent; border-right: 6px solid transparent;
  border-bottom: 8px solid rgba(245,158,11,0.15);
  position: absolute; bottom: 100%; left: 20px;
}
.bubble-text {
  font-size: 13px; color: var(--accent-amber); line-height: 1.5;
  text-align: center; font-weight: 500;
}
.bubble-sub {
  font-size: 10px; color: var(--text-muted); font-style: italic;
  margin-top: 4px; text-align: center;
}
.narration-box {
  font-size: 12px; color: #a855f7; font-style: italic;
  text-align: center; line-height: 1.5;
  background: rgba(168,85,247,0.06); padding: 6px; border-radius: 6px;
  width: 100%;
}
.action-text {
  font-size: 12px; color: var(--text-secondary); text-align: center;
  line-height: 1.6; width: 100%;
}

.panel-footer {
  display: flex; align-items: center; gap: 6px; margin-top: 6px;
  font-size: 9px; color: var(--text-muted); font-family: var(--mono);
  padding-top: 4px; border-top: 1px solid var(--border);
}
.has-bgm, .has-sfx { font-size: 11px; }
.panel-dur { margin-left: auto; }

/* Beat type borders */
.p-dialogue { border-left-color: var(--accent-amber) !important; }
.p-action { border-left-color: var(--accent-cyan) !important; }
.p-narration, .p-vos { border-left-color: #a855f7 !important; }

.sb-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; color: var(--text-muted); gap: 8px;
}
.empty-hint { font-size: 11px; color: var(--text-muted); opacity: 0.6; }
.empty-icon { font-size: 40px; opacity: 0.4; }
</style>
