import { onMounted, onUnmounted, ref } from 'vue'

/** No overlapping requests; hidden pages pause and failures back off. */
export function usePolling(load: (signal: AbortSignal) => Promise<void>, interval = 5000) {
  const error = ref('')
  const loading = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined
  let failures = 0
  let disposed = false
  async function refresh() {
    if (disposed || loading.value || document.hidden) return
    clearTimeout(timer)
    controller = new AbortController()
    loading.value = true
    try {
      await load(controller.signal)
      error.value = ''
      failures = 0
    } catch (e) {
      if (!controller.signal.aborted) {
        error.value = e instanceof Error ? e.message : '加载失败'
        failures++
      }
    } finally {
      loading.value = false
      if (!disposed && !document.hidden)
        timer = setTimeout(refresh, Math.min(interval * 2 ** failures, 60000))
    }
  }
  function visibility() {
    if (document.hidden) {
      clearTimeout(timer)
      controller?.abort()
    } else void refresh()
  }
  onMounted(() => {
    void refresh()
    document.addEventListener('visibilitychange', visibility)
  })
  onUnmounted(() => {
    disposed = true
    clearTimeout(timer)
    controller?.abort()
    document.removeEventListener('visibilitychange', visibility)
  })
  return { error, loading, refresh }
}
