<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, type Task } from '../api'
import { usePolling } from '../composables'
import Icon from '../components/Icon.vue'
const route = useRoute()
const task = ref(String(route.query.task || '')),
  tasks = ref<Task[]>([]),
  lines = ref<string[]>([]),
  cursor = ref<string | null>(null),
  search = ref(''),
  paused = ref(false)
const filtered = computed(() =>
  lines.value.filter((line) => line.toLowerCase().includes(search.value.toLowerCase())),
)
let generation = 0
const { error, refresh } = usePolling(async (signal) => {
  if (paused.value) return
  const current = generation
  if (!tasks.value.length) tasks.value = (await api<{ tasks: Task[] }>('/tasks', { signal })).tasks
  const query = new URLSearchParams({ lines: '500' })
  if (task.value) query.set('task', task.value)
  if (cursor.value) query.set('cursor', cursor.value)
  const data = await api<{ lines: string[]; cursor: string | null; reset: boolean }>(
    `/logs?${query}`,
    { signal },
  )
  if (current !== generation) return
  cursor.value = data.cursor
  lines.value = [...(data.reset ? [] : lines.value), ...data.lines].slice(-2000)
}, 3000)
watch(task, () => {
  generation++
  cursor.value = null
  lines.value = []
  void refresh()
})
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">EVERY DETAIL, IN VIEW</div>
        <h1>日志</h1>
        <p>沿着执行的轨迹，找到每一个答案。</p>
      </div>
      <button class="button glass" @click="paused = !paused">
        <span class="status-dot" :class="{ paused }"></span>{{ paused ? '继续更新' : '暂停更新' }}
      </button>
    </div>
    <div class="toolbar glass">
      <select v-model="task" aria-label="日志来源">
        <option value="">全部运行日志</option>
        <option v-for="item in tasks" :key="item.job_id" :value="item.job_id">
          {{ item.description }}
        </option></select
      ><label class="search"
        ><Icon name="search" :size="18" /><input
          v-model="search"
          placeholder="在已加载日志中查找…"
          aria-label="搜索日志"
      /></label>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="log-view surface">
      <div class="log-title">
        <span
          ><span class="status-dot" :class="{ paused }"></span
          >{{ paused ? '已暂停' : '自动更新' }}</span
        ><span>{{ filtered.length }} 行 · 最多保留 2,000 行</span>
      </div>
      <div class="log-lines" role="region" aria-label="日志内容" tabindex="0">
        <div
          v-for="(line, index) in filtered"
          :key="index"
          class="log-line"
          :class="{
            'log-error': /ERROR|错误|失败/.test(line),
            'log-warn': /WARNING|警告/.test(line),
          }"
        >
          <span class="line-number">{{ index + 1 }}</span
          ><code>{{ line.trimEnd() }}</code>
        </div>
        <div v-if="!filtered.length" class="empty">
          <Icon name="logs" :size="32" />
          <h3>这里还很安静</h3>
          <p>任务运行后，日志会自动出现在这里。</p>
        </div>
      </div>
    </div>
  </section>
</template>
