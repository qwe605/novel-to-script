import { ref, watch } from 'vue'

const KEY = 'nts_theme'
const theme = ref(localStorage.getItem(KEY) || 'light')

function apply(t) {
  document.documentElement.classList.toggle('dark', t === 'dark')
}

// 初始化
apply(theme.value)

// 监听变化
watch(theme, (t) => {
  apply(t)
  localStorage.setItem(KEY, t)
})

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, toggle }
}
