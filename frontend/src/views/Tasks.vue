<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, send, dateTime, statusLabels, type Task } from '../api'
import { usePolling } from '../composables'
import { useUI } from '../stores'
import Icon from '../components/Icon.vue'
const ui = useUI()
const tasks = ref<Task[]>([])
const search = ref('')
const tab = ref('all')
const submitting = ref('')
const tabs = [
  { id: 'all', name: '全部任务' },
  { id: 'monitor', name: '平台监控' },
  { id: 'task', name: '定时任务' },
]
const { error, loading, refresh } = usePolling(async (signal) => {
  tasks.value = (await api<{ tasks: Task[] }>('/tasks', { signal })).tasks
})
const filtered = computed(() =>
  tasks.value.filter(
    (t) =>
      (tab.value === 'all' || t.kind === tab.value) &&
      `${t.description} ${t.job_id}`.toLowerCase().includes(search.value.toLowerCase()),
  ),
)
async function run(task: Task) {
  submitting.value = task.job_id
  try {
    const result = await send<{ duplicate: boolean }>(`/tasks/${task.job_id}/runs`, {})
    ui.notify(result.duplicate ? '任务已在执行队列中' : '任务已加入执行队列')
    await refresh()
  } catch (e) {
    ui.notify((e as Error).message)
  } finally {
    submitting.value = ''
  }
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">AUTOMATION, IN HARMONY</div>
        <h1>任务</h1>
        <p>有序调度，每一件小事都被妥善照顾。</p>
      </div>
      <button class="button glass glass-interactive" :disabled="loading" @click="refresh">
        <Icon name="refresh" :size="17" />刷新状态
      </button>
    </div>
    <div class="toolbar glass">
      <div class="segmented" aria-label="任务类别">
        <span
          class="segment-highlight"
          :style="{ transform: `translateX(${tabs.findIndex((t) => t.id === tab) * 100}%)` }"
        ></span
        ><button
          v-for="item in tabs"
          :key="item.id"
          :aria-pressed="tab === item.id"
          @click="tab = item.id"
        >
          {{ item.name }}
        </button>
      </div>
      <label class="search"
        ><Icon name="search" :size="18" /><input
          v-model="search"
          placeholder="搜索任务…"
          aria-label="搜索任务"
        /><kbd>/</kbd></label
      >
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="section-heading">
      <span class="muted">{{ filtered.length }} 个任务</span
      ><span class="small muted">状态自动更新</span>
    </div>
    <div class="surface task-list">
      <div class="task-table-heading">
        <span>任务</span><span>最近状态</span><span>下次执行</span><span>操作</span>
      </div>
      <article v-for="task in filtered" :key="task.job_id" class="task-row">
        <div class="task-name">
          <span class="task-icon" :class="task.kind === 'monitor' ? 'lavender' : 'peach'"
            ><Icon :name="task.kind === 'monitor' ? 'data' : 'tasks'"
          /></span>
          <div>
            <h3>{{ task.description }}</h3>
            <span class="small muted"
              >{{ task.kind === 'monitor' ? '平台监控' : '定时任务' }}
              <span class="separator">·</span> {{ task.enabled ? '已启用' : '已停用' }}</span
            >
          </div>
        </div>
        <div>
          <span class="badge" :data-status="task.last_run?.status || 'idle'">{{
            statusLabels[task.last_run?.status || 'idle']
          }}</span
          ><small v-if="!task.available" class="muted">当前镜像未提供此任务</small>
        </div>
        <span class="small muted next-run">{{ dateTime(task.next_run) }}</span>
        <div class="row-actions">
          <button
            class="button run-button glass-interactive"
            :disabled="
              !task.available ||
              submitting === task.job_id ||
              ['queued', 'running'].includes(task.last_run?.status || '')
            "
            @click="run(task)"
          >
            <Icon name="play" :size="14" />运行</button
          ><RouterLink
            :to="`/logs?task=${task.job_id}`"
            class="icon-button"
            :aria-label="`查看${task.description}日志`"
            ><Icon name="logs" :size="18" /></RouterLink
          ><RouterLink
            :to="`/config?section=${task.section}`"
            class="icon-button"
            :aria-label="`配置${task.description}`"
            ><Icon name="config" :size="18"
          /></RouterLink>
        </div>
      </article>
      <div v-if="!filtered.length" class="empty">
        <Icon name="search" :size="30" />
        <h3>{{ loading ? '正在读取任务…' : '没有匹配的任务' }}</h3>
        <p>试试其他关键词或任务类别。</p>
      </div>
    </div>
  </section>
</template>
