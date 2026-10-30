<template>
  <main>
    <h1>海外图片缓存 · 隔离回归</h1>
    <p>真实 StudioAssetImage / ElImageViewer；1600 × 1000 原件与 240 × 150 缩略图</p>
    <button @click="prefetch">预取当前会话</button>
    <button @click="logout">退出账号</button>
    <p role="status">{{ status }}</p>
    <section v-if="loggedIn" class="gallery">
      <StudioAssetImage v-for="asset in pictures" :key="asset.id" :asset="asset" :group="pictures" title="原件验收" @failure="failure" />
    </section>
    <h2 v-if="loggedIn">图片附件 / 任务素材</h2>
    <section v-if="loggedIn" class="attachments">
      <StudioAssetImage v-for="asset in attachments" :key="asset.id" :asset="asset" :group="attachments" title="附件验收" @failure="failure" />
    </section>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import StudioAssetImage from '@/views/overseas/studio/StudioAssetImage.vue'
import { overseasImageCache as cache, createImageCache } from '@/api/overseas/image-cache'
const loggedIn = ref(true), status = ref('就绪')
const url = id => `/api/overseas/v1/tasks/fixture/studio/pictures/${id}/content`
const pictures = ['a', 'b', 'c'].map(id => ({ id, name: `${id}.png`, url: url(id), width: 1600, height: 1000, turnId: 'turn-1', sku: null, archived: false }))
const attachments = [
  { id: 'upload:attachment', name: 'attachment.png', url: '/api/overseas/v1/tasks/fixture/studio/files/attachment/content', source: 'upload' },
  { id: 'task:material', name: 'material.png', url: '/api/overseas/v1/materials/material/content', source: 'task' }
].map(asset => ({ ...asset, contentType: 'image/png', sizeBytes: 800000 }))
cache.setIdentity('fixture-account-a')
function prefetch() { cache.setPrefetch('session-a', pictures.map(p => ({ url: p.url }))); status.value = '后台预取已启动' }
function logout() { cache.setIdentity(''); loggedIn.value = false; status.value = '已退出' }
function failure(reason) { status.value = reason instanceof Error ? reason.message : String(reason) }
// This bridge invokes the production cache; no alternate cache implementation is tested.
window.imageTest = {
  cache, createImageCache, url,
  reset(actor = 'fixture-account-a') { cache.clear(); cache.setIdentity(actor); loggedIn.value = true; status.value = '就绪' },
  async acquire(id) {
    const lease = await cache.acquire(url(id))
    const result = { size: lease.blob.size, type: lease.blob.type, url: lease.url }
    lease.release(); return result
  }
}
</script>
<style>
body { margin:0; background:#f4f6f9; color:#263448; font:16px Arial,sans-serif; }
main { max-width:1120px; margin:48px auto; }
button { cursor:pointer; padding:8px 16px; margin-right:8px; }
.gallery,.attachments { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }
.gallery > .el-image,.attachments > .el-image { width:100%; height:220px; background:white; border:1px solid #dce3ed; border-radius:12px; }
.image-caption { color:white; text-align:center; line-height:1.7; }
.image-caption small,.image-state small { display:block; }
.image-state { display:grid; place-content:center; height:100%; }
</style>
