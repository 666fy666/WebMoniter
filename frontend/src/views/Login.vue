<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, send, type Session } from '../api'
import { useSession } from '../stores'
import Icon from '../components/Icon.vue'
const username = ref('admin'),
  password = ref(''),
  error = ref(''),
  busy = ref(false)
const router = useRouter(),
  session = useSession()
async function login() {
  error.value = ''
  busy.value = true
  try {
    await api('/session')
    const result = await send<Session>('/login', {
      username: username.value,
      password: password.value,
    })
    session.authenticated = result.authenticated
    password.value = ''
    await router.replace('/')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="login-card glass">
    <div class="brand-mark large">w<span></span></div>
    <div class="eyebrow">WELCOME TO YOUR WORKSPACE</div>
    <h1>欢迎回来。</h1>
    <p class="muted">每一次变化，都值得被看见。</p>
    <form @submit.prevent="login">
      <label class="field-label"
        >用户名<input v-model="username" autocomplete="username" required maxlength="128" /></label
      ><label class="field-label"
        >密码<input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          maxlength="1024"
      /></label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="button primary full-width glass-interactive" :disabled="busy">
        {{ busy ? '正在登录…' : '进入工作空间' }}<Icon name="arrow" :size="18" />
      </button>
    </form>
    <span class="login-footer">WebMoniter · 从容掌控你的日常</span>
  </div>
</template>
