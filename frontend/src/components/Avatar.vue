<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{ name: string; src?: unknown }>()
const failed = ref(false)
const source = computed(() => {
  if (typeof props.src !== 'string') return ''
  const value = props.src.trim()
  if (!value || /[\s\\]/.test(value)) return ''
  try {
    const parsed = new URL(value, window.location.origin)
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password)
      return ''
    if (value.startsWith('//')) return `https:${value}`
    return /^https?:\/\//i.test(value) || value.startsWith('/weibo_img/') ? value : ''
  } catch {
    return ''
  }
})
watch(source, () => (failed.value = false))
</script>
<template>
  <span class="avatar soft">
    <img
      v-if="source && !failed"
      :key="source"
      :src="source"
      :alt="`${name}的头像`"
      width="48"
      height="48"
      loading="lazy"
      decoding="async"
      referrerpolicy="no-referrer"
      @error="failed = true"
    />
    <span v-else :aria-label="`${name}的默认头像`">{{ Array.from(name)[0] }}</span>
  </span>
</template>
