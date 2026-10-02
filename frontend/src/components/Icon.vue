<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const paths: Record<string, string> = {
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  tasks: 'M9 5h12 M9 12h12 M9 19h12 M3 5l1 1 2-3 M3 12l1 1 2-3 M3 19l1 1 2-3',
  data: 'M3 3v18h18 M7 16v-4 M12 16V7 M17 16v-7',
  config:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',
  logs: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h7',
  account: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M4 21v-3a8 6 0 0 1 16 0v3',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  play: 'M8 4l12 8-12 8z',
  search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 14-3l1 2 M4 17l1 2a8 8 0 0 0 14-3',
  moon: 'M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10',
  check: 'M5 12l4 4L19 6',
  close: 'M6 6l12 12 M18 6L6 18',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1',
}
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.overview" />
  </svg>
</template>
