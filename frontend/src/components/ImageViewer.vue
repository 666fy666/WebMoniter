<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  images: { src: string; thumb: string }[]
  initialIndex: number
}>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const image = ref<HTMLImageElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const index = ref(props.initialIndex)
const current = computed(() => props.images[index.value]!)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const state = ref<'loading' | 'ready' | 'error'>('loading')
const dimensions = ref('')
const attempt = ref(0)
const previousFocus = document.activeElement
const previousOverflow = document.body.style.overflow
const pointers = new Map<number, { x: number; y: number }>()
let gesture: { x: number; y: number; panX: number; panY: number; time: number } | null = null
let pinch: { distance: number; zoom: number } | null = null

function reset() {
  zoom.value = 1
  pan.value = { x: 0, y: 0 }
  pointers.clear()
  gesture = pinch = null
}
function setZoom(value: number, point?: { clientX: number; clientY: number }) {
  const previous = zoom.value
  zoom.value = Math.min(5, Math.max(1, value))
  if (zoom.value === 1) pan.value = { x: 0, y: 0 }
  else if (point && image.value) {
    const rect = image.value.getBoundingClientRect()
    const ratio = zoom.value / previous
    pan.value.x += (point.clientX - rect.left - rect.width / 2) * (1 - ratio)
    pan.value.y += (point.clientY - rect.top - rect.height / 2) * (1 - ratio)
  }
}
function show(next: number) {
  index.value = (next + props.images.length) % props.images.length
  reset()
  state.value = 'loading'
  dimensions.value = ''
  attempt.value++
  void nextTick(() => {
    dialog.value
      ?.querySelector('.weibo-lightbox-thumb.active')
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  })
}
function loaded(event: Event) {
  const target = event.target as HTMLImageElement
  state.value = 'ready'
  dimensions.value = `${target.naturalWidth} × ${target.naturalHeight} px`
}
function pointerDown(event: PointerEvent) {
  if (event.button > 0) return
  image.value?.setPointerCapture(event.pointerId)
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 1) {
    gesture = {
      x: event.clientX,
      y: event.clientY,
      panX: pan.value.x,
      panY: pan.value.y,
      time: performance.now(),
    }
  } else if (pointers.size === 2) {
    const [a, b] = [...pointers.values()]
    pinch = { distance: Math.hypot(a!.x - b!.x, a!.y - b!.y), zoom: zoom.value }
    gesture = null
  }
}
function pointerMove(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()]
    if (pinch.distance > 0)
      setZoom((pinch.zoom * Math.hypot(a!.x - b!.x, a!.y - b!.y)) / pinch.distance)
  } else if (gesture && zoom.value > 1) {
    pan.value = {
      x: gesture.panX + event.clientX - gesture.x,
      y: gesture.panY + event.clientY - gesture.y,
    }
  }
}
function pointerEnd(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  const swipe = gesture
  pointers.delete(event.pointerId)
  if (image.value?.hasPointerCapture(event.pointerId))
    image.value.releasePointerCapture(event.pointerId)
  gesture = pinch = null
  if (swipe && event.type === 'pointerup' && zoom.value === 1 && props.images.length > 1) {
    const dx = event.clientX - swipe.x
    const dy = event.clientY - swipe.y
    if (
      Math.abs(dx) >= 48 &&
      Math.abs(dx) > Math.abs(dy) * 1.3 &&
      performance.now() - swipe.time < 700
    )
      show(index.value + (dx < 0 ? 1 : -1))
  }
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft') show(index.value - 1)
  else if (event.key === 'ArrowRight') show(index.value + 1)
  else if (event.key === '+' || event.key === '=') setZoom(zoom.value + 0.25)
  else if (event.key === '-' || event.key === '_') setZoom(zoom.value - 0.25)
  else if (event.key === '0') reset()
  else return
  event.preventDefault()
}
function filename(src: string, i: number) {
  const extension =
    new URL(src, window.location.href).pathname.match(/\.[a-z0-9]{2,5}$/i)?.[0] || '.jpg'
  return `weibo-${String(i + 1).padStart(2, '0')}${extension}`
}
function saveAll() {
  props.images.forEach(({ src }, i) => {
    const link = document.createElement('a')
    link.href = src
    link.download = filename(src, i)
    document.body.appendChild(link)
    link.click()
    link.remove()
  })
}
onMounted(() => {
  window.addEventListener('keydown', keydown)
  document.body.style.overflow = 'hidden'
  dialog.value?.showModal()
  closeButton.value?.focus()
})
onUnmounted(() => {
  window.removeEventListener('keydown', keydown)
  document.body.style.overflow = previousOverflow
  if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus()
})
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="weibo-lightbox show"
      :class="{
        'has-thumbs': images.length > 1,
        'is-loading': state === 'loading',
        'has-error': state === 'error',
      }"
      aria-label="微博原图预览"
      @cancel.prevent="emit('close')"
      @click.self="emit('close')"
    >
      <div class="weibo-lightbox-toolbar" role="toolbar" aria-label="图片浏览工具">
        <button
          class="weibo-lightbox-tool"
          aria-label="缩小图片"
          :disabled="zoom <= 1"
          @click="setZoom(zoom - 0.25)"
        >
          −
        </button>
        <span class="weibo-lightbox-zoom-level" aria-live="polite"
          >{{ Math.round(zoom * 100) }}%</span
        >
        <button
          class="weibo-lightbox-tool"
          aria-label="放大图片"
          :disabled="zoom >= 5"
          @click="setZoom(zoom + 0.25)"
        >
          +
        </button>
        <button
          class="weibo-lightbox-tool weibo-lightbox-zoom-reset"
          aria-label="适应窗口"
          :disabled="zoom === 1"
          @click="reset"
        >
          适应
        </button>
        <a
          class="weibo-lightbox-tool"
          aria-label="下载当前图片"
          :href="current.src"
          :download="filename(current.src, index)"
          >↓</a
        >
        <button
          v-if="images.length > 1"
          class="weibo-lightbox-tool"
          aria-label="保存全部图片"
          @click="saveAll"
        >
          ⇩
        </button>
        <button
          ref="closeButton"
          class="weibo-lightbox-tool weibo-lightbox-close"
          aria-label="关闭大图"
          @click="emit('close')"
        >
          ×
        </button>
      </div>
      <button
        v-if="images.length > 1"
        class="weibo-lightbox-nav weibo-lightbox-prev"
        aria-label="上一张"
        @click="show(index - 1)"
      >
        ‹
      </button>
      <figure class="weibo-lightbox-figure" @click.self="emit('close')">
        <div
          class="weibo-lightbox-stage"
          :aria-busy="state === 'loading'"
          @click.self="emit('close')"
        >
          <div v-if="state === 'loading'" class="weibo-lightbox-loading" role="status">
            <span class="weibo-lightbox-spinner" aria-hidden="true"></span>正在加载原图…
          </div>
          <img
            :key="`${index}:${attempt}`"
            ref="image"
            class="weibo-lightbox-image"
            :class="{ 'is-zoomed': zoom > 1 }"
            :src="current.src"
            :alt="`微博原图，第 ${index + 1} 张，共 ${images.length} 张`"
            :style="{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})` }"
            referrerpolicy="no-referrer"
            draggable="false"
            @load="loaded"
            @error="state = 'error'"
            @wheel.prevent="setZoom(zoom + ($event.deltaY < 0 ? 0.25 : -0.25), $event)"
            @dblclick.prevent="setZoom(zoom > 1 ? 1 : 2, $event)"
            @pointerdown="pointerDown"
            @pointermove.prevent="pointerMove"
            @pointerup="pointerEnd"
            @pointercancel="pointerEnd"
          />
          <div v-if="state === 'error'" class="weibo-lightbox-error" role="alert">
            <span>原图暂时无法显示</span>
            <button class="weibo-lightbox-retry" @click="show(index)">重新加载</button>
          </div>
        </div>
        <figcaption class="weibo-lightbox-caption">
          <span class="weibo-lightbox-counter" aria-live="polite"
            >{{ index + 1 }} / {{ images.length }}</span
          >
          <span v-if="dimensions" class="weibo-lightbox-dimensions">{{ dimensions }}</span>
          <span class="weibo-lightbox-hint">双击或滚轮缩放 · 拖动查看细节</span>
        </figcaption>
      </figure>
      <div
        v-if="images.length > 1"
        class="weibo-lightbox-thumbs"
        role="group"
        aria-label="微博图片缩略图"
      >
        <button
          v-for="(entry, i) in images"
          :key="i"
          class="weibo-lightbox-thumb"
          :class="{ active: i === index }"
          :aria-label="`查看第 ${i + 1} 张图片`"
          :aria-pressed="i === index"
          @click="show(i)"
        >
          <img :src="entry.thumb" alt="" referrerpolicy="no-referrer" />
        </button>
      </div>
      <button
        v-if="images.length > 1"
        class="weibo-lightbox-nav weibo-lightbox-next"
        aria-label="下一张"
        @click="show(index + 1)"
      >
        ›
      </button>
    </dialog>
  </Teleport>
</template>

<style scoped>
.weibo-lightbox {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100dvh;
  max-width: none;
  max-height: none;
  margin: 0;
  border: 0;
  padding: calc(76px + env(safe-area-inset-top)) 80px calc(34px + env(safe-area-inset-bottom));
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
  background: rgba(5, 7, 12, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-sizing: border-box;
  transition:
    opacity 180ms ease,
    visibility 180ms ease;
}

.weibo-lightbox.show {
  visibility: visible;
  opacity: 1;
  pointer-events: auto;
}

.weibo-lightbox.has-thumbs {
  padding-bottom: calc(106px + env(safe-area-inset-bottom));
}

.weibo-lightbox-figure {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  margin: 0;
  overflow: hidden;
}

.weibo-lightbox-stage {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.weibo-lightbox-image {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  object-position: center;
  border-radius: 8px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.38);
  cursor: zoom-in;
  touch-action: none;
  user-select: none;
  transform-origin: center center;
  will-change: transform;
}

.weibo-lightbox.is-loading .weibo-lightbox-image,
.weibo-lightbox.has-error .weibo-lightbox-image {
  visibility: hidden;
}

.weibo-lightbox-image.is-zoomed {
  cursor: grab;
}

.weibo-lightbox-image.is-dragging {
  cursor: grabbing;
  transition: none;
}

.weibo-lightbox-loading,
.weibo-lightbox-error {
  position: absolute;
  inset: 0;
  display: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.86);
  font-size: 14px;
  text-align: center;
}

.weibo-lightbox.is-loading .weibo-lightbox-loading,
.weibo-lightbox.has-error .weibo-lightbox-error {
  display: flex;
}

.weibo-lightbox-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: rgba(255, 255, 255, 0.92);
  border-radius: 50%;
  animation: weibo-lightbox-spin 0.8s linear infinite;
}

@keyframes weibo-lightbox-spin {
  to {
    transform: rotate(360deg);
  }
}

.weibo-lightbox-retry {
  min-width: 96px;
  min-height: 44px;
  padding: 0 18px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: 999px;
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
  cursor: pointer;
  font: inherit;
  transition:
    background 150ms ease,
    border-color 150ms ease;
}

.weibo-lightbox-retry:hover {
  border-color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.22);
}

.weibo-lightbox-caption {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 28px;
  margin-top: 8px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 13px;
  line-height: 1.4;
}

.weibo-lightbox-counter {
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}

.weibo-lightbox-dimensions::before,
.weibo-lightbox-hint::before {
  content: '·';
  margin-right: 9px;
  color: rgba(255, 255, 255, 0.36);
}

.weibo-lightbox-dimensions {
  font-variant-numeric: tabular-nums;
}

.weibo-lightbox-hint {
  color: rgba(255, 255, 255, 0.58);
}

.weibo-lightbox-toolbar {
  position: fixed;
  top: calc(16px + env(safe-area-inset-top));
  right: 24px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: calc(100vw - 48px);
  padding: 6px;
  overflow-x: auto;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.52);
  scrollbar-width: none;
}

.weibo-lightbox-toolbar::-webkit-scrollbar {
  display: none;
}

.weibo-lightbox-tool,
.weibo-lightbox-nav {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  cursor: pointer;
  text-decoration: none;
  transition:
    background 150ms ease,
    transform 150ms ease;
}

.weibo-lightbox-tool:hover,
.weibo-lightbox-nav:hover {
  background: rgba(255, 255, 255, 0.28);
}

.weibo-lightbox-tool:focus-visible,
.weibo-lightbox-nav:focus-visible,
.weibo-lightbox-thumb:focus-visible,
.weibo-lightbox-retry:focus-visible {
  outline: 3px solid #f9a8d4;
  outline-offset: 2px;
}

.weibo-lightbox-tool {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  font-size: 22px;
  line-height: 1;
}

.weibo-lightbox-tool:disabled {
  cursor: default;
  opacity: 0.42;
}

.weibo-lightbox-zoom-level {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 44px;
  padding: 0 10px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 999px;
}

.weibo-lightbox-zoom-reset {
  width: 58px;
  font-size: 13px;
  font-weight: 700;
}

.weibo-lightbox-close {
  font-size: 30px;
}

.weibo-lightbox-nav {
  position: fixed;
  top: 50%;
  width: 52px;
  height: 52px;
  font-size: 42px;
  line-height: 1;
  transform: translateY(-50%);
}

.weibo-lightbox-nav:hover {
  transform: translateY(-50%) scale(1.04);
}

.weibo-lightbox-prev {
  left: 24px;
}

.weibo-lightbox-next {
  right: 24px;
}

.weibo-lightbox-nav[hidden] {
  display: none;
}

.weibo-lightbox-tool[hidden] {
  display: none;
}

.weibo-lightbox-thumbs {
  position: fixed;
  left: 50%;
  bottom: calc(18px + env(safe-area-inset-bottom));
  z-index: 2;
  display: flex;
  gap: 8px;
  max-width: min(760px, calc(100vw - 48px));
  padding: 8px;
  overflow-x: auto;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  transform: translateX(-50%);
  scrollbar-width: thin;
}

.weibo-lightbox-thumbs[hidden] {
  display: none;
}

.weibo-lightbox-thumb {
  flex: 0 0 auto;
  width: 54px;
  height: 54px;
  padding: 0;
  overflow: hidden;
  border: 2px solid transparent;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  opacity: 0.74;
  transition:
    border-color 150ms ease,
    opacity 150ms ease,
    transform 150ms ease;
}

.weibo-lightbox-thumb.active {
  border-color: rgba(255, 255, 255, 0.92);
  opacity: 1;
}

.weibo-lightbox-thumb:hover {
  opacity: 1;
  transform: translateY(-1px);
}

.weibo-lightbox-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  padding: 2px;
  object-fit: contain;
  object-position: center;
  border-radius: 5px;
}

@media (max-width: 480px) {
  .weibo-lightbox {
    padding: calc(66px + env(safe-area-inset-top)) 8px calc(42px + env(safe-area-inset-bottom));
  }

  .weibo-lightbox.has-thumbs {
    padding-bottom: calc(86px + env(safe-area-inset-bottom));
  }

  .weibo-lightbox-toolbar {
    top: calc(8px + env(safe-area-inset-top));
    left: 8px;
    right: 8px;
    gap: 5px;
    max-width: calc(100vw - 16px);
    padding: 4px;
    justify-content: flex-start;
  }

  .weibo-lightbox-tool {
    width: 44px;
    height: 44px;
    font-size: 18px;
  }

  .weibo-lightbox-zoom-level {
    min-width: 48px;
    height: 44px;
    padding: 0 6px;
    font-size: 12px;
  }

  .weibo-lightbox-zoom-reset {
    width: 52px;
    font-size: 12px;
  }

  .weibo-lightbox-nav {
    width: 44px;
    height: 44px;
    font-size: 34px;
    background: rgba(0, 0, 0, 0.28);
  }

  .weibo-lightbox-prev {
    left: 10px;
  }

  .weibo-lightbox-next {
    right: 10px;
  }

  .weibo-lightbox-thumbs {
    bottom: calc(8px + env(safe-area-inset-bottom));
    max-width: calc(100vw - 16px);
    padding: 5px;
  }

  .weibo-lightbox-thumb {
    width: 52px;
    height: 52px;
  }

  .weibo-lightbox-caption {
    gap: 7px;
    min-height: 24px;
    margin-top: 4px;
    font-size: 12px;
  }

  .weibo-lightbox-hint {
    display: none;
  }
}

@media (max-height: 540px) and (orientation: landscape) {
  .weibo-lightbox {
    padding-top: calc(60px + env(safe-area-inset-top));
  }

  .weibo-lightbox.has-thumbs {
    padding-bottom: calc(70px + env(safe-area-inset-bottom));
  }

  .weibo-lightbox-thumbs {
    bottom: calc(6px + env(safe-area-inset-bottom));
  }

  .weibo-lightbox-thumb {
    width: 44px;
    height: 44px;
  }

  .weibo-lightbox-hint {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .weibo-lightbox-spinner {
    animation: none;
  }

  .weibo-lightbox,
  .weibo-lightbox-image {
    transition: none;
  }
}

.weibo-lightbox::backdrop {
  background: transparent;
}
</style>
