<script setup>
/**
 * 文件上传组件 — 拖拽/点击上传 + 文件列表 + 拖拽排序。
 * 通过 v-model 双向绑定文件列表给父组件。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const ALLOWED_EXTS = ['.txt', '.md', '.zip']
const isDragging = ref(false)
const dragOverIdx = ref(-1)
const fileInput = ref(null)

// ---- internal file list (synced with v-model) ----
const fileList = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const fileCount = computed(() => fileList.value.length)

function addFiles(rawFiles) {
  const added = []
  for (const f of rawFiles) {
    const ext = '.' + f.name.toLowerCase().split('.').pop()
    if (!ALLOWED_EXTS.includes(ext)) {
      ElMessage.warning(`不支持的文件类型: ${f.name}，仅支持 .txt / .md / .zip`)
      continue
    }
    if (fileList.value.some(item => item.name === f.name && item.size === f.size)) continue
    fileList.value = [...fileList.value, { file: f, name: f.name, size: f.size }]
    added.push(f)
  }
  if (!added.length && rawFiles.length > 0) {
    ElMessage.warning('文件已存在或不支持该类型')
  }
}

function onFileChange(e) {
  addFiles(Array.from(e.target.files || []))
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  dragOverIdx.value = -1
  addFiles(Array.from(e.dataTransfer.files || []))
}

function removeFile(idx) {
  const items = [...fileList.value]
  items.splice(idx, 1)
  fileList.value = items
}

function clearAll() { fileList.value = [] }

// ---- drag sort ----
function onDragStart(idx, e) { e.dataTransfer.setData('text/plain', String(idx)) }
function onDragOver(idx, e) { e.preventDefault(); dragOverIdx.value = idx }
function onDragLeave(idx, e) { if (dragOverIdx.value === idx) dragOverIdx.value = -1 }
function onDropSort(idx, e) {
  e.preventDefault()
  dragOverIdx.value = -1
  const from = parseInt(e.dataTransfer.getData('text/plain'))
  if (isNaN(from) || from === idx) return
  const items = [...fileList.value]
  const [moved] = items.splice(from, 1)
  items.splice(idx, 0, moved)
  fileList.value = items
}
</script>

<template>
  <div>
    <!-- Upload zone -->
    <div
      class="upload-zone"
      :class="{ dragover: isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <input ref="fileInput" type="file" accept=".txt,.md,.zip" multiple hidden @change="onFileChange" />
      <template v-if="!fileList.length">
        <div class="upload-icon">📂</div>
        <div class="upload-text">点击或拖拽上传小说章节</div>
        <div class="upload-hint">支持多选 .txt / .md / .zip（≥3 章）</div>
      </template>
      <template v-else>
        <div class="upload-icon">✅</div>
        <div class="upload-text" style="color: var(--text-primary)">已选择 {{ fileCount }} 个文件</div>
        <div class="upload-hint">点击继续添加，下方可拖拽排序</div>
      </template>
    </div>

    <!-- File list with drag sort -->
    <div v-if="fileList.length" class="file-list">
      <div class="file-list-header">
        <span>📋 章节列表（{{ fileCount }} 章）</span>
        <button class="clear-all-btn" @click="clearAll">清空全部</button>
      </div>
      <div
        v-for="(item, idx) in fileList"
        :key="idx"
        class="file-item"
        :class="{ 'drag-over': dragOverIdx === idx }"
        draggable="true"
        @dragstart="onDragStart(idx, $event)"
        @dragover="onDragOver(idx, $event)"
        @dragleave="onDragLeave(idx, $event)"
        @drop="onDropSort(idx, $event)"
      >
        <span class="file-drag-handle">⋮⋮</span>
        <span class="file-chapter-num">第{{ idx + 1 }}章</span>
        <span class="file-name">{{ item.name }}</span>
        <span class="file-size">{{ (item.size / 1024).toFixed(1) }}KB</span>
        <button class="file-remove" @click.stop="removeFile(idx)" title="移除">✕</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-zone {
  border: 2px dashed var(--border); border-radius: 10px; padding: 24px 16px;
  text-align: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0;
}
.upload-zone:hover, .upload-zone.dragover { border-color: var(--accent-cyan); background: var(--accent-cyan-dim); }
.upload-icon { font-size: 28px; margin-bottom: 6px; }
.upload-text { font-size: 14px; color: var(--text-secondary); font-weight: 500; }
.upload-hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.file-list { display: flex; flex-direction: column; gap: 4px; margin-top: 12px; }
.file-list-header { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-muted); margin-bottom: 2px; }
.clear-all-btn { font-size: 10px; background: none; border: 1px solid var(--border); color: var(--text-muted); padding: 1px 8px; border-radius: 4px; cursor: pointer; }
.clear-all-btn:hover { color: var(--danger); border-color: var(--danger); }
.file-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; font-size: 11px; transition: all 0.15s; cursor: grab; }
.file-item:active { cursor: grabbing; }
.file-item:hover { border-color: var(--border-light); }
.file-item.drag-over { border-color: var(--accent-cyan); background: var(--accent-cyan-dim); }
.file-drag-handle { color: var(--text-muted); font-size: 13px; letter-spacing: -2px; cursor: grab; user-select: none; line-height: 1; }
.file-chapter-num { font-size: 10px; font-weight: 600; color: var(--accent-cyan); background: var(--accent-cyan-dim); padding: 1px 6px; border-radius: 3px; min-width: 40px; text-align: center; flex-shrink: 0; }
.file-name { flex: 1; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { font-size: 10px; color: var(--text-muted); font-family: var(--mono); flex-shrink: 0; }
.file-remove { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 12px; padding: 2px; flex-shrink: 0; line-height: 1; }
.file-remove:hover { color: var(--danger); }
</style>
