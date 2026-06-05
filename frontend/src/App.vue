<script setup>
import HomeView from './views/HomeView.vue'
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <div class="logo">
        <span class="logo-icon">📖</span>
        <span class="logo-text">Novel-to-Script</span>
        <span class="logo-tag">AI 小说转剧本</span>
      </div>
      <div class="logo-sub">网文漫剧 · 影视剧本 · 广播剧 · 舞台剧</div>
    </header>
    <main class="app-main">
      <HomeView />
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-deep);
}

.app-header {
  height: 56px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  font-size: 22px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.logo-tag {
  font-size: 12px;
  color: var(--accent-cyan);
  background: var(--accent-cyan-dim);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.logo-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.app-main {
  flex: 1;
  overflow: hidden;
  padding: 16px;
}
</style>
