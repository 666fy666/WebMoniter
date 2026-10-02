<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUI } from './stores'
import Icon from './components/Icon.vue'
const route = useRoute()
const ui = useUI()
const nav = [
  { path: '/', name: '概览', icon: 'overview' },
  { path: '/tasks', name: '任务', icon: 'tasks' },
  { path: '/data', name: '监控数据', icon: 'data' },
  { path: '/config', name: '配置', icon: 'config' },
  { path: '/logs', name: '日志', icon: 'logs' },
  { path: '/account', name: '账户', icon: 'account' },
]
let frame = 0
let active: HTMLElement | null = null
function clearLight() {
  cancelAnimationFrame(frame)
  if (active) {
    active.style.removeProperty('--light-x')
    active.style.removeProperty('--light-y')
  }
  active = null
}
function light(e: PointerEvent) {
  if (document.documentElement.dataset.effects !== 'full' || e.pointerType !== 'mouse') return
  const target = (e.target as HTMLElement).closest<HTMLElement>('.glass-interactive')
  if (!target) {
    clearLight()
    return
  }
  cancelAnimationFrame(frame)
  if (active !== target) clearLight()
  active = target
  frame = requestAnimationFrame(() => {
    const rect = target.getBoundingClientRect()
    target.style.setProperty('--light-x', `${e.clientX - rect.left}px`)
    target.style.setProperty('--light-y', `${e.clientY - rect.top}px`)
  })
}
onMounted(() => {
  document.addEventListener('pointermove', light, { passive: true })
  document.addEventListener('visibilitychange', clearLight)
})
onUnmounted(() => {
  clearLight()
  document.removeEventListener('pointermove', light)
  document.removeEventListener('visibilitychange', clearLight)
})
</script>
<template>
  <a class="skip" href="#main">跳到主要内容</a>
  <div class="ambient" aria-hidden="true"></div>
  <div v-if="route.path !== '/login'" class="app-shell">
    <aside class="sidebar glass">
      <RouterLink to="/" class="brand"
        ><span class="brand-mark">w<span></span></span>
        <div>WebMoniter<small>每一次变化，清晰可见</small></div></RouterLink
      >
      <span class="nav-label">工作空间</span>
      <nav aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="nav-link glass-interactive"
          :class="{ selected: route.path === item.path }"
          ><Icon :name="item.icon" /><span>{{ item.name }}</span
          ><span v-if="route.path === item.path" class="nav-dot"></span
        ></RouterLink>
      </nav>
      <div class="sidebar-bottom">
        <div class="workspace-label"><span class="status-dot"></span>个人工作空间</div>
        <span class="muted small">轻盈运行 · 从容掌控</span
        ><button
          class="theme-button glass-interactive"
          @click="ui.theme = ui.theme === 'dark' ? 'light' : 'dark'"
        >
          <Icon name="moon" />切换外观
        </button>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <span class="breadcrumb"
          >工作空间 <span>/</span> <strong>{{ route.meta.title }}</strong></span
        ><RouterLink class="avatar" to="/account" aria-label="账户设置">W</RouterLink>
      </header>
      <main id="main" tabindex="-1">
        <RouterView v-slot="{ Component, route: viewRoute }">
          <Transition name="page" mode="out-in">
            <!-- Keep a DOM transition target even when a view has multiple roots. -->
            <div v-if="Component" :key="viewRoute.path">
              <component :is="Component" />
            </div>
          </Transition>
        </RouterView>
      </main>
      <footer>WebMoniter <span>你的任务，有序发生。</span></footer>
    </div>
    <nav class="mobile-nav glass" aria-label="移动导航">
      <RouterLink
        v-for="item in nav"
        :key="item.path"
        :to="item.path"
        :class="{ selected: route.path === item.path }"
        ><Icon :name="item.icon" :size="19" /><span>{{ item.name }}</span></RouterLink
      >
    </nav>
  </div>
  <main v-else id="main" class="login-shell"><RouterView /></main>
  <Transition name="toast"
    ><div v-if="ui.toast" class="toast glass" role="status" aria-live="polite">
      <Icon name="check" />{{ ui.toast
      }}<button class="icon-button" aria-label="关闭提示" @click="ui.toast = ''">
        <Icon name="close" :size="16" />
      </button></div
  ></Transition>
</template>
