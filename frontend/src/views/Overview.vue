<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, dateTime, statusLabels, type Task, type Run } from '../api'
import { usePolling } from '../composables'
import Icon from '../components/Icon.vue'
const tasks = ref<Task[]>([])
const runs = ref<Run[]>([])
const { error } = usePolling(async (signal) => {
  const [a, b] = await Promise.all([
    api<{ tasks: Task[] }>('/tasks', { signal }),
    api<{ runs: Run[] }>('/runs?limit=8', { signal }),
  ])
  tasks.value = a.tasks
  runs.value = b.runs
})
const active = computed(() => tasks.value.filter((t) => t.enabled).length)
const working = computed(
  () => tasks.value.filter((t) => ['queued', 'running'].includes(t.last_run?.status || '')).length,
)
const failed = computed(
  () =>
    tasks.value.filter((t) =>
      ['failed', 'timeout', 'interrupted'].includes(t.last_run?.status || ''),
    ).length,
)
function name(id: string) {
  return tasks.value.find((t) => t.job_id === id)?.description || id
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">YOUR QUIET COMMAND CENTER</div>
        <h1>一切，尽在掌握。</h1>
        <p>把重复的事交给任务，把时间留给自己。</p>
      </div>
      <RouterLink class="button primary glass-interactive" to="/tasks"
        >管理任务 <Icon name="arrow" :size="17"
      /></RouterLink>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="hero glass">
      <div>
        <span class="pill"><span class="status-dot"></span>专注此刻 · 自动发生</span>
        <h2>让每一次变化<br /><span>都有回应。</span></h2>
        <p>监控、签到与消息推送，在一个轻盈的工作空间有序运行。</p>
        <RouterLink to="/config" class="text-link"
          >配置你的工作空间 <Icon name="arrow" :size="17"
        /></RouterLink>
      </div>
      <div class="hero-orbit" aria-hidden="true">
        <div class="orbit-ring"></div>
        <div class="orbit-core">w<span></span></div>
        <div class="orbit-chip chip-one"><Icon name="check" />有序执行</div>
        <div class="orbit-chip chip-two"><Icon name="data" />即时掌握</div>
      </div>
    </div>
    <div class="stats-grid">
      <article class="stat-card surface">
        <span class="stat-icon lavender"><Icon name="tasks" /></span><span>全部任务</span
        ><strong>{{ tasks.length }}<small>项</small></strong>
        <p>监控与日常自动化</p>
      </article>
      <article class="stat-card surface">
        <span class="stat-icon mint"><Icon name="check" /></span><span>已启用</span
        ><strong>{{ active }}<small>项</small></strong>
        <p>按你的节奏自动执行</p>
      </article>
      <article class="stat-card surface">
        <span class="stat-icon peach"><Icon name="refresh" /></span><span>进行中</span
        ><strong>{{ working }}<small>项</small></strong>
        <p>包含正在等待的任务</p>
      </article>
      <article class="stat-card surface">
        <span class="stat-icon rose"><Icon name="logs" /></span><span>需要关注</span
        ><strong>{{ failed }}<small>项</small></strong>
        <p>查看日志了解执行详情</p>
      </article>
    </div>
    <div class="section-heading">
      <h2>最近发生</h2>
      <RouterLink to="/tasks" class="text-link"
        >全部任务 <Icon name="arrow" :size="16"
      /></RouterLink>
    </div>
    <div class="surface activity">
      <div v-for="run in runs" :key="run.run_id" class="activity-row">
        <span class="activity-icon"
          ><Icon :name="run.status === 'success' ? 'check' : 'tasks'"
        /></span>
        <div class="grow">
          <strong>{{ name(run.job_id) }}</strong
          ><small>{{ dateTime(run.created_at) }}</small>
        </div>
        <span class="badge" :data-status="run.status">{{ statusLabels[run.status] }}</span>
      </div>
      <div v-if="!runs.length" class="empty">
        <Icon name="tasks" :size="32" />
        <h3>你的工作空间，准备就绪</h3>
        <p>启用或运行一个任务，执行动态会出现在这里。</p>
      </div>
    </div>
  </section>
</template>
