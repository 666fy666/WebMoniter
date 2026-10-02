<script setup lang="ts">
import { onMounted, onUnmounted, ref, useId, watch } from 'vue'

const props = defineProps<{ text: string }>()
const body = ref<HTMLElement | null>(null)
const expanded = ref(false)
const overflowing = ref(false)
const id = useId()
let observer: ResizeObserver | undefined
function measure() {
  if (body.value && !expanded.value)
    overflowing.value = body.value.scrollHeight > body.value.clientHeight + 1
}
watch(
  () => props.text,
  () => (expanded.value = false),
)
watch([() => props.text, expanded], measure, { flush: 'post' })
onMounted(() => {
  observer = new ResizeObserver(measure)
  if (body.value) observer.observe(body.value)
  measure()
})
onUnmounted(() => observer?.disconnect())
</script>
<template>
  <div class="post-content">
    <p :id="id" ref="body" class="post-body" :class="{ collapsed: !expanded }">{{ text }}</p>
    <button
      v-if="overflowing || expanded"
      class="button subtle post-toggle"
      :aria-expanded="expanded"
      :aria-controls="id"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起正文' : '展开全文' }}
    </button>
  </div>
</template>
