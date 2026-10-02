<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, send } from '../api'
import { useSession, useUI } from '../stores'
import Icon from '../components/Icon.vue'
const ui = useUI(),
  session = useSession(),
  router = useRouter()
const oldPassword = ref(''),
  newPassword = ref(''),
  confirm = ref(''),
  busy = ref(false),
  error = ref('')
async function changePassword() {
  error.value = ''
  if (newPassword.value !== confirm.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  busy.value = true
  try {
    await send('/password', { old_password: oldPassword.value, new_password: newPassword.value })
    oldPassword.value = newPassword.value = confirm.value = ''
    ui.notify('密码已更新，其他登录会话已退出')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function logout() {
  try {
    await api('/logout', { method: 'POST' })
    session.authenticated = false
    await router.replace('/login')
  } catch (e) {
    ui.notify((e as Error).message)
  }
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">MAKE IT YOURS</div>
        <h1>账户与外观</h1>
        <p>适合你的样子，恰到好处的体验。</p>
      </div>
    </div>
    <div class="settings-grid">
      <article class="surface settings-card">
        <h2><Icon name="sun" />界面外观</h2>
        <label class="field-label"
          >主题<select v-model="ui.theme" aria-label="主题">
            <option value="system">跟随系统</option>
            <option value="light">浅色 · 晨光</option>
            <option value="dark">深色 · 夜幕</option>
          </select></label
        ><label class="field-label"
          >材质与动态效果<select v-model="ui.effects" aria-label="材质与动态效果">
            <option value="auto">自动 · 适配当前设备</option>
            <option value="full">完整 · 液态玻璃与光感</option>
            <option value="simple">简化 · 轻盈清晰</option>
          </select></label
        >
        <p class="muted small">系统开启“减少动态效果”时，会自动简化交互动画。</p>
        <div class="material-preview glass glass-interactive">
          <span class="preview-orb"></span><strong>光影之间，恰如其分。</strong
          ><small>Liquid Glass × Liquid Acrylic</small>
        </div>
      </article>
      <article class="surface settings-card">
        <h2><Icon name="account" />修改密码</h2>
        <form @submit.prevent="changePassword">
          <label class="field-label"
            >当前密码<input
              v-model="oldPassword"
              type="password"
              autocomplete="current-password"
              required
              maxlength="1024" /></label
          ><label class="field-label"
            >新密码<input
              v-model="newPassword"
              type="password"
              autocomplete="new-password"
              minlength="1"
              maxlength="1024"
              placeholder="输入新密码"
              required /></label
          ><label class="field-label"
            >确认新密码<input
              v-model="confirm"
              type="password"
              autocomplete="new-password"
              minlength="1"
              maxlength="1024"
              required
          /></label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary" :disabled="busy">
            {{ busy ? '正在更新…' : '更新密码' }}
          </button>
        </form>
      </article>
    </div>
    <button class="button danger logout" @click="logout">
      退出当前账户 <Icon name="arrow" :size="17" />
    </button>
  </section>
</template>
