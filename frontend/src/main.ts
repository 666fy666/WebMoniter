import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { useSession } from './stores'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/Overview.vue'), meta: { title: '概览' } },
    { path: '/tasks', component: () => import('./views/Tasks.vue'), meta: { title: '任务' } },
    { path: '/data', component: () => import('./views/Data.vue'), meta: { title: '监控数据' } },
    { path: '/config', component: () => import('./views/Config.vue'), meta: { title: '配置' } },
    { path: '/logs', component: () => import('./views/Logs.vue'), meta: { title: '日志' } },
    {
      path: '/account',
      component: () => import('./views/Account.vue'),
      meta: { title: '账户与外观' },
    },
    {
      path: '/login',
      component: () => import('./views/Login.vue'),
      meta: { title: '登录', public: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
const app = createApp(App)
app.use(createPinia())
const session = useSession()
router.beforeEach(async (to) => {
  if (!session.authenticated) {
    try {
      await session.refresh()
    } catch {
      if (!to.meta.public) return '/login'
    }
  }
  if (!to.meta.public && !session.authenticated) return '/login'
  if (to.path === '/login' && session.authenticated) return '/'
})
router.afterEach((to) => {
  document.title = `${to.meta.title} · WebMoniter`
})
window.addEventListener('session-expired', () => {
  session.authenticated = false
  void router.replace('/login')
})
app.use(router).mount('#app')
