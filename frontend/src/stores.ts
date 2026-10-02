import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api, type Session } from './api'

function stored(key: string, fallback: string) {
  try {
    return localStorage.getItem(key) || fallback
  } catch {
    return fallback
  }
}
export const useSession = defineStore('session', () => {
  const authenticated = ref(false)
  async function refresh() {
    authenticated.value = (await api<Session>('/session')).authenticated
  }
  return { authenticated, refresh }
})
export const useUI = defineStore('ui', () => {
  const theme = ref(stored('wm-theme', 'system'))
  const effects = ref(stored('wm-effects', 'auto'))
  const toast = ref('')
  let timer: ReturnType<typeof setTimeout>
  function notify(message: string) {
    toast.value = message
    clearTimeout(timer)
    timer = setTimeout(() => {
      toast.value = ''
    }, 5000)
  }
  const dark = window.matchMedia('(prefers-color-scheme: dark)')
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
  const coarse = window.matchMedia('(pointer: coarse)')
  const systemDark = ref(dark.matches)
  const simple = ref(reduced.matches || coarse.matches)
  dark.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })
  reduced.addEventListener('change', () => {
    simple.value = reduced.matches || coarse.matches
  })
  coarse.addEventListener('change', () => {
    simple.value = reduced.matches || coarse.matches
  })
  const effectiveTheme = computed(() =>
    theme.value === 'system' ? (systemDark.value ? 'dark' : 'light') : theme.value,
  )
  const effectiveEffects = computed(() =>
    reduced.matches || effects.value === 'simple' || (effects.value === 'auto' && simple.value)
      ? 'simple'
      : 'full',
  )
  watch(
    [effectiveTheme, effectiveEffects, theme, effects],
    () => {
      document.documentElement.dataset.theme = effectiveTheme.value
      document.documentElement.dataset.effects = effectiveEffects.value
      try {
        localStorage.setItem('wm-theme', theme.value)
        localStorage.setItem('wm-effects', effects.value)
      } catch {
        /* Storage can be unavailable in private contexts. */
      }
    },
    { immediate: true },
  )
  return { theme, effects, toast, notify }
})
