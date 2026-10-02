<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Value } from '../api'
const props = withDefaults(
  defineProps<{
    modelValue: Value
    name: string
    label?: string
    secret?: boolean
    itemTemplate?: Value
    choices?: string[]
    hint?: string
  }>(),
  { secret: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: Value] }>()
const labels: Record<string, string> = {
  enable: '启用任务',
  enabled: '启用',
  cookie: 'Cookie',
  cookies: '多个 Cookie',
  accounts: '多账号',
  username: '用户名',
  password: '密码',
  email: '邮箱',
  api_key: 'API 密钥',
  time: '执行时间',
  push_channels: '推送渠道',
  name: '渠道名称',
  type: '渠道类型',
  token: 'Token',
  url: '服务地址',
  key: '密钥',
  host: '主机',
  port: '端口',
  user: '用户名',
  database: '数据库',
  concurrency: '请求并发数',
  monitor_interval_seconds: '监控间隔（秒）',
  uids: '用户 UID',
  rooms: '直播间 ID',
  douyin_ids: '抖音号',
  targets: '监控目标',
  profile_ids: '用户主页 ID',
  start: '开始时间',
  end: '结束时间',
  base_url: '公开访问地址',
  retention_days: '日志保留天数',
  auto_renew: '自动续费',
  renew_product_ids: '续费产品 ID',
  renew_threshold_days: '续费阈值（天）',
  cookie_refresh_enable: '自动刷新 Cookie',
  cookie_refresh_time: 'Cookie 刷新时间',
  skip_forward: '跳过转发',
  connect_timeout: '连接超时（秒）',
  pool_min_size: '最小连接数',
  pool_max_size: '最大连接数',
  refresh_token: '刷新令牌',
  refresh_tokens: '多个刷新令牌',
  access_token: '访问令牌',
  access_tokens: '多个访问令牌',
  account: '账号',
  tokens: '多个令牌',
  device_params: '设备参数',
  request_body: '请求内容',
  request_bodies: '多个请求内容',
  openid: 'OpenID',
  openids: '多个 OpenID',
  city_code: '城市代码',
  payload: '浏览器指纹',
}
const title = computed(() => props.label || labels[props.name] || props.name)
const isSecret = computed(
  () =>
    !/_(enable|enabled|time|timeout|interval_seconds)$/.test(props.name) &&
    (props.secret ||
      /password|passwd|cookie|token|secret|api_key|authorization|request_bod|device_params/i.test(
        props.name,
      ) ||
      ['key', 'sckey', 'sendkey', 'openid', 'url', 'payload', 'headers'].includes(props.name)),
)
const masked = computed(
  () => typeof props.modelValue === 'string' && props.modelValue.startsWith('__KEEP_SECRET__:'),
)
const revealed = ref(false)
const array = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
function updateIndex(index: number, value: Value) {
  const next = [...array.value]
  next[index] = value
  emit('update:modelValue', next)
}
function remove(index: number) {
  emit(
    'update:modelValue',
    array.value.filter((_, i) => i !== index),
  )
}
function add() {
  emit('update:modelValue', [
    ...array.value,
    JSON.parse(JSON.stringify(props.itemTemplate ?? '')) as Value,
  ])
}
function updateKey(key: string, value: Value) {
  emit('update:modelValue', { ...(props.modelValue as Record<string, Value>), [key]: value })
}
function choose(value: string, selected: boolean) {
  emit(
    'update:modelValue',
    selected ? [...array.value, value] : array.value.filter((v) => v !== value),
  )
}
</script>
<template>
  <fieldset v-if="Array.isArray(modelValue)" class="nested-field">
    <legend>{{ title }}</legend>
    <template v-if="name === 'push_channels' && choices"
      ><div class="choice-list">
        <label v-for="choice in choices" :key="choice"
          ><input
            type="checkbox"
            :checked="array.includes(choice)"
            @change="choose(choice, ($event.target as HTMLInputElement).checked)"
          />{{ choice }}</label
        ><span v-if="!choices.length" class="muted small">先在推送渠道中添加渠道。</span>
      </div>
      <p class="muted small">不选择时使用全部已配置的渠道。</p></template
    ><template v-else
      ><div v-for="(item, i) in array" :key="i" class="array-item">
        <div class="array-heading">
          <span>第 {{ i + 1 }} 项</span
          ><button type="button" class="button subtle danger" @click="remove(i)">移除</button>
        </div>
        <FieldEditor
          :model-value="item"
          :name="name"
          :label="typeof item === 'object' ? undefined : title"
          :secret="isSecret"
          @update:model-value="updateIndex(i, $event)"
        />
      </div>
      <button type="button" class="button subtle" @click="add">＋ 添加{{ title }}</button></template
    >
  </fieldset>
  <fieldset
    v-else-if="modelValue !== null && typeof modelValue === 'object'"
    class="nested-field object-field"
  >
    <legend>{{ title }}</legend>
    <FieldEditor
      v-for="(value, key) in modelValue"
      :key="key"
      :model-value="value"
      :name="String(key)"
      :secret="isSecret"
      @update:model-value="updateKey(String(key), $event)"
    />
  </fieldset>
  <label v-else-if="typeof modelValue === 'boolean'" class="switch-field"
    ><span
      >{{ title }}<small v-if="hint">{{ hint }}</small></span
    ><input
      type="checkbox"
      role="switch"
      :checked="modelValue"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)" /><span
      class="switch-track"
      aria-hidden="true"
    ></span
  ></label>
  <div v-else class="field" :data-field="name">
    <label class="field-label"
      >{{ title
      }}<span class="input-wrap"
        ><input
          :value="masked ? '' : (modelValue ?? '')"
          :type="
            typeof modelValue === 'number'
              ? 'number'
              : isSecret && !revealed
                ? 'password'
                : /^(time|start|end|cookie_refresh_time)$/.test(name)
                  ? 'time'
                  : 'text'
          "
          :placeholder="masked ? '已设置 · 留空保持不变' : ''"
          :autocomplete="isSecret ? 'new-password' : 'off'"
          @input="
            emit(
              'update:modelValue',
              typeof modelValue === 'number'
                ? Number(($event.target as HTMLInputElement).value)
                : ($event.target as HTMLInputElement).value,
            )
          "
        /><button
          v-if="isSecret && !masked"
          type="button"
          class="input-action"
          :aria-label="revealed ? '隐藏内容' : '显示内容'"
          @click="revealed = !revealed"
        >
          {{ revealed ? '隐藏' : '显示' }}
        </button></span
      ></label
    >
    <div v-if="masked" class="secret-note">
      <span>已安全保存</span
      ><button type="button" @click="emit('update:modelValue', '')">清除</button>
    </div>
    <small v-if="hint" class="muted">{{ hint }}</small>
  </div>
</template>
