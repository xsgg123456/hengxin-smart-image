<template>
  <main><p>归档图片真实组件隔离验收</p><button @click="logout">退出账号</button><p role="status">{{ status }}</p>
    <OverseasArchivePage v-if="loggedIn" :key="generation" :refresh="generation" :capabilities="['task.delete']" @failure="failure" />
  </main>
</template>
<script setup>
import { ref } from 'vue'
import OverseasArchivePage from '@/views/overseas/OverseasArchivePage.vue'
import { overseasImageCache as cache } from '@/api/overseas/image-cache'
import { createArchivesApi } from '@/api/overseas/archives'
const loggedIn = ref(true), status = ref('就绪'), generation = ref(0)
cache.setIdentity('fixture-account-a')
function logout() { cache.setIdentity(''); loggedIn.value = false; status.value = '已退出' }
function failure(reason) { status.value = reason.message }
window.archiveTest = { cache, api: createArchivesApi(), reset() { cache.clear(); cache.setIdentity('fixture-account-a'); generation.value++; loggedIn.value = true }, switchAccount() { cache.setIdentity('fixture-account-b'); generation.value++ } }
</script>
<style>
body { margin:0; background:#f4f6f9; color:#263448; font:14px Arial,sans-serif; }
main { max-width:1120px; padding:24px; margin:auto; }
.hx-row,.hx-filter { display:flex; gap:12px; flex-wrap:wrap; }.hx-gap { margin-top:16px; }
.hx-library-grid { display:grid; gap:16px; }.hx-footnote { color:#606266; font-size:12px; }
</style>
