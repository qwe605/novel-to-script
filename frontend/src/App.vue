<script setup>
import HomeView from './views/HomeView.vue'
import { useTheme } from './composables/useTheme.js'

const { theme, toggle } = useTheme()
</script>

<template>
  <div class="app-root">
    <!-- 背景动画层 -->
    <div class="bg-aurora" />
    <div class="bg-grid" />
    <div class="bg-scan" />

    <header class="app-bar">
      <div class="bar-left">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">小说转剧本</span>
        </div>
      </div>
      <nav class="bar-nav">
        <button class="nav-pill active">转换</button>
      </nav>
      <div class="bar-right">
        <button class="theme-btn" @click="toggle" :title="theme === 'dark' ? '浅色' : '深色'">
          <svg v-if="theme === 'light'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </button>
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
  background: var(--bg-app); position: relative;
  transition: background var(--duration-normal) var(--ease-out);
}

/* ---- 顶栏 — 玻璃态 ---- */
.app-bar {
  position: relative; z-index: 20;
  height: 48px;
  background: rgba(255,255,255,0.60); backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-subtle);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; flex-shrink: 0;
  user-select: none;
  transition: background var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}
html.dark .app-bar {
  background: rgba(14,17,25,0.72);
}

.bar-left {
  display: flex; align-items: center; gap: 10px;
}
.brand-icon {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 8px;
  background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(167,139,250,0.18));
  color: var(--accent);
}
.brand-name {
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  letter-spacing: -0.3px;
}

/* 导航 pill */
.bar-nav { display: flex; gap: 6px; }
.nav-pill {
  padding: 5px 16px; border-radius: 20px; border: 1px solid var(--border);
  background: rgba(255,255,255,0.08); color: var(--text-secondary);
  font-size: 12px; font-weight: 600; cursor: default;
  transition: all var(--duration-fast) var(--ease-out);
}
.nav-pill.active { border-color: var(--accent); background: rgba(56,189,248,0.10); color: var(--accent); }
html.dark .nav-pill.active { background: rgba(56,189,248,0.14); }

.bar-right { display: flex; align-items: center; gap: 8px; }
.theme-btn {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  border: 1px solid var(--border-subtle);
  border-radius: 20px;
  background: rgba(255,255,255,0.04);
  color: var(--text-tertiary); cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.theme-btn:hover {
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 20px rgba(56,189,248,0.15);
}

.app-main { flex: 1; overflow: hidden; padding: 12px 16px 16px; position: relative; z-index: 1; }

@media (max-width: 900px) { .app-main { padding: 8px; } }
</style>
