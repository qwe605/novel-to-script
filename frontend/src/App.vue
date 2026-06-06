<script setup>
import HomeView from './views/HomeView.vue'
import { useTheme } from './composables/useTheme.js'

const { theme, toggle } = useTheme()
</script>

<template>
  <div class="app-root">
    <header class="app-bar">
      <div class="bar-left">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">Novel-to-Script</span>
          <span class="brand-sep">/</span>
          <span class="brand-desc">AI 小说转剧本</span>
        </div>
      </div>
      <div class="bar-right">
        <!-- 主题切换 -->
        <button class="theme-btn" @click="toggle" :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'">
          <!-- 当前浅色 → 显示月亮（切换到深色） -->
          <svg v-if="theme === 'light'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
          <!-- 当前深色 → 显示太阳（切换到浅色） -->
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </button>
        <span class="bar-badge">v1.0</span>
      </div>
    </header>

    <main class="app-main">
      <HomeView />
    </main>
  </div>
</template>

<style scoped>
.app-root {
  display: flex; flex-direction: column; height: 100vh;
  background: var(--bg-app);
  transition: background var(--duration-normal) var(--ease-out);
}

.app-bar {
  height: 48px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; flex-shrink: 0;
  -webkit-app-region: drag; user-select: none; z-index: 10;
  transition: background var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}

.bar-left {
  display: flex; align-items: center; gap: 10px;
  -webkit-app-region: no-drag;
}
.brand-icon {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--accent-dim), var(--purple-dim));
  color: var(--accent);
}
.brand-text { display: flex; align-items: baseline; gap: 6px; }
.brand-name {
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  letter-spacing: -0.3px;
}
.brand-sep { font-size: 13px; color: var(--text-tertiary); font-weight: 300; }
.brand-desc { font-size: 12px; color: var(--text-tertiary); font-weight: 500; }

.bar-right {
  display: flex; align-items: center; gap: 8px;
  -webkit-app-region: no-drag;
}
.theme-btn {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.theme-btn:hover {
  background: var(--bg-hover); color: var(--text-primary);
  border-color: var(--border);
}

.bar-badge {
  font-size: 10px; font-weight: 600; color: var(--text-tertiary);
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  padding: 2px 8px; border-radius: 10px; letter-spacing: 0.02em;
}

.app-main { flex: 1; overflow: hidden; padding: 12px 16px 16px; }

@media (max-width: 900px) {
  .brand-desc, .brand-sep { display: none; }
  .app-main { padding: 8px; }
}
</style>
