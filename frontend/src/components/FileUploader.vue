<script setup>
/**
 * 文件上传组件 — 多选/拖拽 + 列表展示 + 排序。
 * 内部用 Map 安全存 File 对象，对外通过 expose 暴露 getFiles()。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ICONS } from '../utils/icons.js'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const ALLOWED_EXTS = ['.txt', '.md', '.zip']
const isDragging = ref(false)
const dragOverIdx = ref(-1)

// ---- 数据 ----
// _items: UI 列表 [{id, name, size}]
// _store: id → File (非响应式)
const _items = ref([...props.modelValue])
let _nextId = 1
let _store = {}

function syncUp() {
  emit('update:modelValue', [..._items.value])
}

/** 获取真实 File 对象列表供上传 */
function getFiles() {
  return _items.value.map((it) => _store[it.id]).filter(Boolean)
}

// ---- add ----
function addFiles(rawFiles) {
  let addedCount = 0
  for (const f of rawFiles) {
    const ext = '.' + f.name.toLowerCase().split('.').pop()
    if (!ALLOWED_EXTS.includes(ext)) {
      ElMessage.warning(`不支持的文件类型: ${f.name}`)
      continue
    }
    const dup = _items.value.find((it) => it.name === f.name && it.size === f.size)
    if (dup) continue

    const id = _nextId++
    _store[id] = f
    _items.value.push({ id, name: f.name, size: f.size })
    addedCount++
  }
  if (addedCount > 0) syncUp()
  else if (rawFiles.length > 0) ElMessage.warning('文件已存在或不支持该类型')
}

function onInputChange(e) {
  if (e.target?.files?.length) {
    addFiles(Array.from(e.target.files))
    e.target.value = ''
  }
}

function onDrop(e) {
  isDragging.value = false
  dragOverIdx.value = -1
  if (e.dataTransfer?.files?.length) addFiles(Array.from(e.dataTransfer.files))
}

// ---- remove / clear ----
function removeFile(idx) {
  const it = _items.value[idx]
  if (it) delete _store[it.id]
  _items.value.splice(idx, 1)
  syncUp()
}

function clearAll() {
  _store = {}
  _items.value = []
  syncUp()
}

// ---- drag sort ----
function onDragStart(idx, e) { e.dataTransfer.setData('text/plain', String(idx)) }
function onDragOver(idx, e) { e.preventDefault(); dragOverIdx.value = idx }
function onDragLeave(idx, e) { if (dragOverIdx.value === idx) dragOverIdx.value = -1 }
function onDropSort(idx, e) {
  e.preventDefault(); dragOverIdx.value = -1
  const from = parseInt(e.dataTransfer.getData('text/plain'))
  if (isNaN(from) || from === idx) return
  const arr = [..._items.value]
  const [moved] = arr.splice(from, 1)
  arr.splice(idx, 0, moved)
  _items.value = arr
  syncUp()
}

function fmtsize(b) {
  if (b < 1024) return b + 'B'
  return (b / 1024).toFixed(1) + 'KB'
}

defineExpose({ getFiles, addFiles })
</script>

<template>
  <div>
    <div class="upload-zone" :class="{ dragover: isDragging }"
      @dragover.prevent="isDragging = true" @dragleave="isDragging = false"
      @drop.prevent="onDrop">
      <label class="upload-label">
        <input type="file" accept=".txt,.md,.zip" multiple @change="onInputChange" />
        <template v-if="!_items.length">
          <div class="upload-graphic"><span class="upload-svg" v-html="ICONS.upload" /></div>
          <div class="upload-text">拖拽文件到此处，或点击上传</div>
          <div class="upload-hint">.txt / .md / .zip · 多选 · ≥3 章</div>
        </template>
        <template v-else>
          <div class="upload-graphic done">
            <span class="upload-svg-check" v-html="ICONS.check" />
          </div>
          <div class="upload-text done">已选择 {{ _items.length }} 个文件</div>
          <div class="upload-hint">点击继续添加，下方可拖拽排序</div>
        </template>
      </label>
    </div>

    <div v-if="_items.length" class="file-list">
      <div class="file-list-header">
        <span class="file-list-title"><span class="fl-icon" v-html="ICONS.list" /> 章节列表</span>
        <span class="file-list-count">{{ _items.length }} 章</span>
        <button class="clear-all-btn" @click="clearAll">清空</button>
      </div>
      <div v-for="(item, idx) in _items" :key="item.id" class="file-item"
        :class="{ 'drag-over': dragOverIdx === idx }" draggable="true"
        @dragstart="onDragStart(idx, $event)" @dragover="onDragOver(idx, $event)"
        @dragleave="onDragLeave(idx, $event)" @drop="onDropSort(idx, $event)">
        <span class="file-grip">
          <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor"><circle cx="3" cy="3" r="1.2"/><circle cx="7" cy="3" r="1.2"/><circle cx="3" cy="7" r="1.2"/><circle cx="7" cy="7" r="1.2"/><circle cx="3" cy="11" r="1.2"/><circle cx="7" cy="11" r="1.2"/></svg>
        </span>
        <span class="file-num">{{ idx + 1 }}</span>
        <span class="file-name">{{ item.name }}</span>
        <span class="file-size">{{ fmtsize(item.size) }}</span>
        <button class="file-remove" @click.stop="removeFile(idx)" title="移除">
          <span v-html="ICONS.xmark" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-zone { border: 2px dashed var(--border); border-radius: var(--radius-lg); padding: 24px 16px 20px; text-align: center; cursor: pointer; transition: all var(--duration-normal) var(--ease-out); background: rgba(255,255,255,0.20); backdrop-filter: blur(4px); position: relative; overflow: hidden; }
html.dark .upload-zone { background: rgba(14,17,25,0.25); }
.upload-zone::before { content: ''; position: absolute; inset: 0; opacity: 0; background: radial-gradient(ellipse at center, var(--accent-dim) 0%, transparent 70%); transition: opacity var(--duration-slow) var(--ease-out); }
.upload-zone:hover::before, .upload-zone.dragover::before { opacity: 1; }
.upload-zone:hover, .upload-zone.dragover { border-color: var(--accent); border-style: solid; }

.upload-label { display: block; cursor: pointer; }
.upload-label input { display: none; }

.upload-graphic { position: relative; z-index: 1; margin-bottom: 8px; transition: transform var(--duration-normal) var(--ease-out); }
.upload-zone.dragover .upload-graphic { transform: scale(1.1); }
.upload-svg { display: inline-flex; color: var(--text-tertiary); }
.upload-svg-check { display: inline-flex; color: var(--accent); }
.upload-graphic.done .upload-svg-check { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; background: var(--accent-dim); border-radius: 50%; padding: 6px; }
.upload-text { font-size: 13px; color: var(--text-secondary); font-weight: 500; position: relative; z-index: 1; }
.upload-text.done { color: var(--accent); }
.upload-hint { font-size: 11px; color: var(--text-tertiary); margin-top: 4px; position: relative; z-index: 1; }

.file-list { display: flex; flex-direction: column; gap: 2px; margin-top: 12px; }
.file-list-header { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--text-tertiary); font-weight: 600; letter-spacing: 0.03em; margin-bottom: 4px; text-transform: uppercase; }
.file-list-title { display: flex; align-items: center; gap: 4px; }
.fl-icon { display: flex; }
.file-list-count { margin-left: auto; font-weight: 500; color: var(--text-tertiary); }
.clear-all-btn { font-size: 10px; background: none; border: 1px solid var(--border-subtle); color: var(--text-tertiary); padding: 1px 8px; border-radius: var(--radius-sm); cursor: pointer; font-weight: 500; margin-left: 4px; transition: all var(--duration-fast) var(--ease-out); }
.clear-all-btn:hover { color: var(--red); border-color: var(--red); background: var(--red-dim); }

.file-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px 6px 5px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); font-size: 11px; transition: all var(--duration-fast) var(--ease-out); cursor: grab; user-select: none; }
.file-item:active { cursor: grabbing; }
.file-item:hover { border-color: var(--border); background: var(--bg-hover); }
.file-item.drag-over { border-color: var(--accent); background: var(--accent-dim); box-shadow: inset 0 0 0 1px var(--accent); }
.file-grip { color: var(--text-tertiary); display: flex; flex-shrink: 0; cursor: grab; }
.file-num { font-size: 10px; font-weight: 700; color: var(--accent); background: var(--accent-dim); padding: 1px 5px; border-radius: 3px; min-width: 18px; text-align: center; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.file-name { flex: 1; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 450; }
.file-size { font-size: 10px; color: var(--text-tertiary); font-family: var(--font-mono); flex-shrink: 0; }
.file-remove { background: none; border: none; color: var(--text-tertiary); cursor: pointer; display: flex; align-items: center; padding: 2px; border-radius: 3px; flex-shrink: 0; transition: all var(--duration-fast) var(--ease-out); }
.file-remove:hover { color: var(--red); background: var(--red-dim); }
</style>
