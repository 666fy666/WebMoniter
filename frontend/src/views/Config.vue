<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import {
  api,
  ApiError,
  send,
  type ConfigResponse,
  type Metadata,
  type Config,
  type Value,
} from '../api'
import { useUI } from '../stores'
import Icon from '../components/Icon.vue'
import FieldEditor from '../components/FieldEditor.vue'
const route = useRoute(),
  ui = useUI()
const document = ref<Config>({}),
  meta = ref<Metadata | null>(null),
  version = ref(''),
  baseline = ref(''),
  selected = ref(String(route.query.section || 'weibo'))
const search = ref(''),
  error = ref(''),
  busy = ref(false),
  yamlMode = ref(false),
  yamlText = ref(''),
  yamlBaseline = ref(''),
  pushType = ref('')
const dirty = computed(() =>
  yamlMode.value
    ? yamlText.value !== yamlBaseline.value
    : JSON.stringify(document.value) !== baseline.value,
)
const titles: Record<string, string> = {
  push_channel: '推送渠道',
  mysql: '数据库',
  app: '访问设置',
  quiet_hours: '免打扰',
  plugins: '扩展任务',
  log_cleanup: '日志清理',
}
function title(key: string) {
  return (
    titles[key] ||
    meta.value?.tasks.find((t) => t.config_section === key)?.description.replace(/签到$/, '') ||
    key
  )
}
const sections = computed(() =>
  Object.keys(document.value).filter((key) =>
    `${key} ${title(key)}`.toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const fields = computed(() => {
  const value = document.value[selected.value]
  return value && !Array.isArray(value) && typeof value === 'object' ? value : {}
})
const channels = computed(() =>
  Array.isArray(document.value.push_channel)
    ? (document.value.push_channel as Record<string, Value>[])
    : [],
)
const channelNames = computed(() => channels.value.map((c) => String(c.name || '')).filter(Boolean))
function updateField(key: string, value: Value) {
  document.value[selected.value] = { ...fields.value, [key]: value }
}
function template(key: string): Value {
  return key === 'accounts'
    ? Object.fromEntries((meta.value?.accounts[selected.value] || []).map((k) => [k, '']))
    : ''
}
function hydrate(data: ConfigResponse) {
  const defaults = meta.value?.defaults || {}
  document.value = Object.fromEntries(
    [...new Set([...Object.keys(defaults), ...Object.keys(data.config)])].map((key) => {
      const value = data.config[key],
        base = defaults[key]
      if (base && typeof base === 'object' && !Array.isArray(base))
        return [
          key,
          {
            ...base,
            ...(value && typeof value === 'object' && !Array.isArray(value) ? value : {}),
          },
        ]
      return [key, value ?? base]
    }),
  )
  version.value = data.version
  baseline.value = JSON.stringify(document.value)
  if (!(selected.value in document.value)) selected.value = Object.keys(document.value)[0] || ''
}
async function load() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const [metadata, config] = await Promise.all([
      api<Metadata>('/config/metadata'),
      api<ConfigResponse>('/config'),
    ])
    meta.value = metadata
    hydrate(config)
    pushType.value = meta.value.push_channels[0]?.type || ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function save() {
  if (busy.value) return
  const section = selected.value,
    savingYaml = yamlMode.value,
    submitted = JSON.parse(JSON.stringify(document.value)) as Config,
    content = yamlText.value
  busy.value = true
  error.value = ''
  try {
    const result = await send<ConfigResponse>(
      '/config',
      savingYaml
        ? { version: version.value, content }
        : { version: version.value, config: { [section]: submitted[section] } },
      'PUT',
    )
    // Preserve edits made before or during this request, even after switching sections.
    const pending = document.value,
      old = JSON.parse(baseline.value) as Config
    hydrate(result)
    if (!savingYaml) {
      for (const key of Object.keys(pending))
        if (
          JSON.stringify(pending[key]) !==
          JSON.stringify(key === section ? submitted[key] : old[key])
        )
          document.value[key] = pending[key]
    } else {
      yamlBaseline.value = content
    }
    ui.notify('配置已保存，调度设置将在数秒内更新')
  } catch (e) {
    error.value = (e as Error).message
    if (e instanceof ApiError && e.fields.length) {
      error.value += '\n' + e.fields.map((f) => `${f.path}: ${f.message}`).join('\n')
      const [section, key] = e.fields[0].path.split('.')
      if (section in document.value) selected.value = section
      await nextTick()
      window.document
        .querySelector<HTMLInputElement>(`[data-field="${CSS.escape(key || '')}"] input`)
        ?.focus()
    }
  } finally {
    busy.value = false
  }
}
async function toggleYaml() {
  if (busy.value) return
  if (dirty.value && !window.confirm('切换编辑方式会放弃尚未保存的内容，是否继续？')) return
  if (yamlMode.value) {
    yamlMode.value = false
    yamlText.value = yamlBaseline.value = ''
    await load()
    return
  }
  if (!window.confirm('YAML 中包含完整凭据。仅在可信设备上查看，是否继续？')) return
  busy.value = true
  try {
    const result = await send<{ version: string; content: string }>('/config/reveal', {})
    version.value = result.version
    yamlText.value = yamlBaseline.value = result.content
    yamlMode.value = true
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function testDatabase() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await send<{ message: string }>('/database/test', { mysql: fields.value })
    ui.notify(result.message)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
function addChannel() {
  const spec = meta.value?.push_channels.find((p) => p.type === pushType.value)
  if (!spec) return
  document.value.push_channel = [
    ...channels.value,
    {
      ...Object.fromEntries(spec.fields.map((f) => [f, ''])),
      name: `${spec.name} ${channels.value.length + 1}`,
      type: spec.type,
    },
  ]
}
function guard(e: BeforeUnloadEvent) {
  if (dirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onBeforeRouteLeave(() => !dirty.value || window.confirm('还有未保存的配置，确定离开？'))
onMounted(() => {
  void load()
  window.addEventListener('beforeunload', guard)
})
onUnmounted(() => {
  yamlText.value = ''
  window.removeEventListener('beforeunload', guard)
})
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">A PLACE FOR EVERYTHING</div>
        <h1>配置</h1>
        <p>你的平台、账号和消息，在这里连接起来。</p>
      </div>
      <button class="button glass" :disabled="busy" @click="toggleYaml">
        {{ yamlMode ? '返回表单' : 'YAML 高级编辑' }}
      </button>
    </div>
    <p v-if="error" class="error" role="alert" tabindex="-1">
      {{ error }} <button class="button subtle" :disabled="busy" @click="load">重新加载</button>
    </p>
    <div v-if="yamlMode" class="surface settings-card">
      <label class="field-label"
        >完整 YAML（包含敏感凭据）<textarea
          v-model="yamlText"
          class="yaml-editor"
          spellcheck="false"
          autocomplete="off"
        ></textarea>
      </label>
      <div class="save-bar">
        <span class="muted small">{{ dirty ? '有未保存的修改' : '所有修改已保存' }}</span
        ><button class="button primary" :disabled="busy || !dirty" @click="save">
          保存完整配置
        </button>
      </div>
    </div>
    <div v-else class="config-layout">
      <aside class="config-nav glass">
        <label class="search"
          ><Icon name="search" :size="16" /><input
            v-model="search"
            placeholder="查找配置…"
            aria-label="查找配置模块"
        /></label>
        <nav aria-label="配置模块">
          <button
            v-for="key in sections"
            :key="key"
            :class="{ selected: selected === key }"
            :aria-pressed="selected === key"
            @click="selected = key"
          >
            {{ title(key)
            }}<span
              v-if="
                document[key] &&
                typeof document[key] === 'object' &&
                !Array.isArray(document[key]) &&
                (document[key] as Record<string, Value>).enable
              "
              class="status-dot"
            ></span>
          </button>
        </nav>
      </aside>
      <article class="surface config-content">
        <div class="config-title">
          <div>
            <h2>{{ title(selected) }}</h2>
            <p class="muted small">按模块保存 · 敏感信息安全保留</p>
          </div>
          <span v-if="dirty" class="badge" data-status="queued">有未保存修改</span>
        </div>
        <div v-if="selected === 'push_channel'">
          <div class="channel-add">
            <select v-model="pushType" aria-label="新增渠道类型">
              <option v-for="type in meta?.push_channels" :key="type.type" :value="type.type">
                {{ type.name }}
              </option></select
            ><button class="button" @click="addChannel">＋ 添加渠道</button>
          </div>
          <div v-for="(channel, index) in channels" :key="index" class="channel-card">
            <div class="array-heading">
              <h3>{{ channel.name || '新渠道' }}</h3>
              <button
                class="button subtle danger"
                @click="document.push_channel = channels.filter((_, i) => i !== index)"
              >
                移除
              </button>
            </div>
            <FieldEditor
              v-for="(value, key) in channel"
              :key="key"
              :name="String(key)"
              :model-value="value"
              @update:model-value="channel[key] = $event"
            />
          </div>
          <div v-if="!channels.length" class="empty">
            <Icon name="config" :size="30" />
            <h3>连接你的第一个推送渠道</h3>
            <p>选择渠道类型，填写凭据后保存。</p>
          </div>
        </div>
        <div v-else class="config-fields">
          <FieldEditor
            v-for="(value, key) in fields"
            :key="`${selected}.${key}`"
            :name="String(key)"
            :model-value="value"
            :secret="meta?.fields[selected]?.[key]?.secret"
            :hint="
              meta?.fields[selected]?.[key]?.label === key
                ? undefined
                : meta?.fields[selected]?.[key]?.label
            "
            :item-template="template(String(key))"
            :choices="channelNames"
            @update:model-value="updateField(String(key), $event)"
          />
          <p v-if="!Object.keys(fields).length" class="muted">此模块可通过 YAML 高级编辑设置。</p>
        </div>
        <div class="save-bar">
          <button v-if="selected === 'mysql'" class="button" :disabled="busy" @click="testDatabase">
            测试连接
          </button>
          <span class="small muted">{{ busy ? '正在处理…' : '保存后自动应用，无需重启' }}</span
          ><button
            class="button primary glass-interactive"
            :disabled="busy || !dirty"
            @click="save"
          >
            <Icon name="check" :size="17" />保存当前模块
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
