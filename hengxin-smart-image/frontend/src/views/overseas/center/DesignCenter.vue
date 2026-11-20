<template>
      <section class="dc-page hx-page">
        <header class="dc-title"><h1>设计任务中心</h1><p>选择平台创建图需、开始自定义生图，或继续已有任务。</p></header>
        <nav class="dc-tabs" aria-label="任务视图">
          <button v-if="canCreate" type="button" :aria-current="!listing ? 'page' : undefined" @click="emit('view', 'create')">新建设计</button>
          <button v-if="canRead" type="button" :aria-current="listing ? 'page' : undefined" @click="emit('view', 'tasks')">继续任务</button>
        </nav>
        <div v-if="canCreate && !listing" class="dc-grid">
          <button v-for="p in platforms" :key="p.value" class="dc-card" :data-platform="p.value"
            :aria-label="'新建'+p.label.split('/')[0]+'图需'" @click="emit('choose',p.value)">
            <img class="dc-art" :src="platformImages[p.value]" alt="" width="485" height="253" />
            <FanScene v-if="p.value === 'The Home Depot'" />
            <span class="dc-card-copy"><b>{{ p.value }}</b><span>{{ p.label.split('/')[0] }}</span></span>
            <span class="dc-card-action">新建图需 <span aria-hidden="true">↗</span></span>
          </button>
          <button type="button" class="dc-card dc-custom" aria-label="自定义生图，开始创作" @click="emit('custom')">
            <img class="dc-art" :src="scooterPhoto" alt="" width="485" height="253" />
            <span class="dc-card-copy"><b>自定义生图</b><span>Custom</span></span>
            <span class="dc-card-action">开始创作 <span aria-hidden="true">↗</span></span>
          </button>
        </div>
        <slot v-else-if="canRead" />
      </section>
</template>
<script setup lang="ts">
import { OVERSEAS_PLATFORMS as platforms } from '../platforms'
import amazonPhoto from './photos/amazon-hd.webp'
import wayfairPhoto from './photos/wayfair-hd.webp'
import mercadoPhoto from './photos/mercado-libre-hd.webp'
import walmartPhoto from './photos/walmart-hd.webp'
import depotPhoto from './photos/home-depot-hd.webp'
import scooterPhoto from './photos/shopee-hd.webp'
import FanScene from './FanScene.vue'
const platformImages: Record<string,string> = {
  Amazon: amazonPhoto, Wayfair: wayfairPhoto, 'Mercado Libre': mercadoPhoto,
  Walmart: walmartPhoto, 'The Home Depot': depotPhoto,
}
defineProps<{canCreate:boolean; canRead:boolean; listing:boolean}>()
const emit=defineEmits<{view:[tab:'create'|'tasks'];choose:[platform:string];custom:[]}>()
</script>
<style src="./design-center.css"></style>
