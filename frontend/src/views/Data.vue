<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { api } from '../api'
import { usePolling } from '../composables'
import Icon from '../components/Icon.vue'
import Avatar from '../components/Avatar.vue'
import PostBody from '../components/PostBody.vue'
import ImageViewer from '../components/ImageViewer.vue'
interface Item {
  [key: string]: unknown
}
const platforms: Record<string, string> = {
  weibo: '微博',
  huya: '虎牙',
  bilibili_live: '哔哩哔哩直播',
  bilibili_dynamic: '哔哩哔哩动态',
  douyin: '抖音',
  kuaishou: '快手',
  douyu: '斗鱼',
  xhs: '小红书',
}
const platform = ref('weibo'),
  page = ref(1),
  total = ref(0),
  pages = ref(0),
  items = ref<Item[]>([])
let generation = 0
let pendingRefresh = false
const preview = ref<{ images: { src: string; thumb: string }[]; index: number } | null>(null)
const { error, loading, refresh } = usePolling(async (signal) => {
  const current = generation
  const result = await api<{ data: Item[]; total: number; total_pages: number }>(
    `/data/${platform.value}?page=${page.value}&page_size=50`,
    { signal },
  )
  if (generation !== current) return
  items.value = result.data
  total.value = result.total
  pages.value = result.total_pages
}, 30000)
watch(platform, () => (page.value = 1), { flush: 'sync' })
watch([platform, page], () => {
  preview.value = null
  generation++
  items.value = []
  total.value = pages.value = 0
  error.value = ''
  pendingRefresh = loading.value
  if (!pendingRefresh) void refresh()
})
watch(loading, (busy) => {
  if (!busy && pendingRefresh) {
    pendingRefresh = false
    error.value = ''
    void nextTick(refresh)
  }
})
function name(item: Item) {
  return String(item['用户名'] || item.name || item.uname || item.user_name || '未命名用户')
}
function id(item: Item) {
  return String(
    item.UID ||
      item.uid ||
      item.room ||
      item.douyin_id ||
      item.principal_id ||
      item.profile_id ||
      '',
  )
}
function url(value: unknown) {
  return typeof value === 'string' &&
    (/^https?:\/\//.test(value) || value.startsWith('/weibo_img/'))
    ? value
    : ''
}
function images(item: Item) {
  const originals = Array.isArray(item.images) ? item.images : []
  const thumbs = Array.isArray(item.image_thumbs) ? item.image_thumbs : []
  return Array.from({ length: Math.max(originals.length, thumbs.length) }, (_, i) => ({
    src: url(originals[i]) || url(thumbs[i]),
    thumb: url(thumbs[i]) || url(originals[i]),
  })).filter((image) => image.src)
}
function live(item: Item) {
  return ['1', 'true', '直播中', '是', 'True'].includes(String(item.is_live))
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">STAY CLOSE TO WHAT MATTERS</div>
        <h1>监控数据</h1>
        <p>你关心的动态，在这里汇聚。</p>
      </div>
      <button class="button glass" :disabled="loading" @click="refresh">
        <Icon name="refresh" :size="17" />刷新数据
      </button>
    </div>
    <div class="platform-tabs glass" aria-label="数据平台">
      <button
        v-for="(label, key) in platforms"
        :key="key"
        :class="{ selected: platform === key }"
        :aria-pressed="platform === key"
        @click="platform = key"
      >
        {{ label }}
      </button>
    </div>
    <p v-if="error && items.length" class="error" role="alert">
      更新失败：{{ error }}。当前显示上次成功读取的数据。
    </p>
    <div class="section-heading">
      <span class="muted">{{ total }} 个监控对象</span
      ><span class="muted small">展示各对象的最近状态</span>
    </div>
    <div class="data-grid" :aria-busy="loading">
      <article v-for="item in items" :key="`${platform}:${id(item)}`" class="surface data-card">
        <div class="data-card-title">
          <Avatar :name="name(item)" :src="item.avatar_url" />
          <div class="grow">
            <h3>{{ name(item) }}</h3>
            <small class="muted">{{ id(item) }}</small>
          </div>
          <span
            v-if="item.is_live !== undefined"
            class="badge"
            :data-status="live(item) ? 'success' : 'idle'"
            >{{ live(item) ? '直播中' : '未开播' }}</span
          >
        </div>
        <p v-if="item['认证信息']" class="small muted">{{ item['认证信息'] }}</p>
        <PostBody
          :text="
            String(
              item['文本'] ||
                item.dynamic_text ||
                item.latest_note_title ||
                item['简介'] ||
                '暂无新的动态内容',
            )
          "
        />
        <div v-if="images(item).length" class="post-images">
          <button
            v-for="(image, i) in images(item)"
            :key="i"
            type="button"
            :aria-label="`查看第 ${i + 1} 张图片`"
            @click="preview = { images: images(item), index: i }"
          >
            <img :src="image.thumb" alt="动态图片" loading="lazy" decoding="async" />
          </button>
        </div>
        <img
          v-else-if="url(item.room_pic || item.video_cover_thumb)"
          :src="url(item.room_pic || item.video_cover_thumb)"
          class="post-cover"
          alt="封面"
          loading="lazy"
          decoding="async"
        />
        <details
          v-if="item.retweeted_status && Object.keys(item.retweeted_status as object).length"
          class="repost"
        >
          <summary>查看转发内容</summary>
          <PostBody
            :text="
              String(
                (item.retweeted_status as Item).text ||
                  (item.retweeted_status as Item).文本 ||
                  JSON.stringify(item.retweeted_status),
              )
            "
          />
        </details>
        <div class="data-card-footer">
          <span class="small muted">{{ platforms[platform] }}</span
          ><a
            v-if="url(item.url)"
            :href="url(item.url)"
            target="_blank"
            rel="noopener noreferrer"
            class="text-link"
            >查看原页面 <Icon name="arrow" :size="15"
          /></a>
        </div>
      </article>
    </div>
    <div v-if="!items.length && loading" class="empty surface" role="status">
      <Icon name="refresh" :size="34" />
      <h3>正在读取动态…</h3>
    </div>
    <div v-else-if="!items.length && error" class="empty surface" role="alert">
      <h3>读取失败</h3>
      <p>{{ error }}</p>
      <button class="button" @click="refresh">重新加载</button>
    </div>
    <div v-else-if="!items.length" class="empty surface">
      <Icon name="data" :size="34" />
      <h3>等待第一条动态</h3>
      <p>配置监控对象并启用任务后，最新状态会显示在这里。</p>
      <RouterLink to="/config" class="button">前往配置</RouterLink>
    </div>
    <div v-if="pages > 1" class="pagination">
      <button class="button" :disabled="page <= 1" @click="page--">上一页</button
      ><span>{{ page }} / {{ pages }}</span
      ><button class="button" :disabled="page >= pages" @click="page++">下一页</button>
    </div>
  </section>
  <ImageViewer
    v-if="preview"
    :images="preview.images"
    :initial-index="preview.index"
    @close="preview = null"
  />
</template>
