<script setup lang="ts">
import { defineAsyncComponent, shallowRef, watch } from 'vue'
import { useDocumentVisibility, useEventListener, useMediaQuery } from '@vueuse/core'
import type { Scene } from './motion/scenes'

import outonCover from './tool-covers/outon.jpg'
import outonlifeCover from './tool-covers/outonlife.jpg'
import beleevCover from './tool-covers/beleev.jpg'

import wayfairCover from './tool-covers/wayfair.jpg'
import walmartCover from './tool-covers/walmart.jpg'
import homeDepotCover from './tool-covers/home-depot.jpg'
import mercadoLibreCover from './tool-covers/mercado-libre.jpg'
import customSizeCover from './tool-covers/custom-size.jpg'

import replicateCover from './tool-covers/replicate.jpg'
import whiteBackgroundCover from './tool-covers/white-background.jpg'
import editTextCover from './tool-covers/edit-text.jpg'
import cutoutCover from './tool-covers/cutout.jpg'
import recolorCover from './tool-covers/recolor.jpg'
import removeProductCover from './tool-covers/remove-product.jpg'

type ToolCard = { name: string; description: string; cover: string; scene: Scene }

const platformTools: ToolCard[] = [
  { name: '亚马逊生图(OUTON)', description: '为 OUTON 制作亚马逊主图和 A+ 图', cover: outonCover, scene: 'outon' },
  { name: '亚马逊生图(OUTONLIFE)', description: '为 OUTONLIFE 制作亚马逊主图和 A+ 图', cover: outonlifeCover, scene: 'outonlife' },
  { name: '亚马逊生图(BELEEV)', description: '为 BELEEV 制作亚马逊主图和 A+ 图', cover: beleevCover, scene: 'beleev' },
  { name: 'Waifair生图', description: '为威费尔商品制作主图和详情图', cover: wayfairCover, scene: 'wayfair' },
  { name: '沃尔玛生图', description: '为沃尔玛商品制作主图和详情图', cover: walmartCover, scene: 'walmart' },
  { name: 'The Home Depot生图', description: '为家得宝商品制作上架主图', cover: homeDepotCover, scene: 'home-depot' },
  { name: '美客多生图', description: '为美客多商品制作上架主图', cover: mercadoLibreCover, scene: 'mercado-libre' },
  { name: '其他平台(自定义尺寸)', description: '按目标平台的宽高要求生成商品图', cover: customSizeCover, scene: 'custom-size' },
]
const editingTools: ToolCard[] = [
  { name: 'AI去掉产品', description: '移除画面中的产品，补全背景', cover: replicateCover, scene: 'replicate' },
  { name: '爆款复刻', description: '参考爆款构图，制作同款风格商品图', cover: whiteBackgroundCover, scene: 'white-background' },
  { name: 'AI一键白底图', description: '保留商品主体，一键换成纯白背景', cover: editTextCover, scene: 'edit-text' },
  { name: 'AI无痕改字', description: '替换图中文字，贴合原有字形与背景', cover: cutoutCover, scene: 'cutout' },
  { name: 'AI万物抠图', description: '抠出图中主体，保留透明背景', cover: recolorCover, scene: 'recolor' },
  { name: 'AI产品换色', description: '更换产品颜色，保留材质与光影', cover: removeProductCover, scene: 'remove-product' }
]
const groups = [{ label: '平台生图', tools: platformTools }, { label: '图片工具', tools: editingTools }]
const CoverMotion = defineAsyncComponent(() => import('./motion/CoverMotion.vue'))
const active = shallowRef<{ scene: Scene; photo: HTMLImageElement }>()
const allowed = useMediaQuery('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)')
const visibility = useDocumentVisibility()
function stop() { active.value = undefined }
function enter(event: PointerEvent, scene: Scene) {
  if (!allowed.value || event.pointerType === 'touch' || visibility.value !== 'visible') return
  const photo = (event.currentTarget as HTMLElement).querySelector('img')
  if (photo) active.value = { scene, photo }
}
watch([allowed, visibility], () => {
  if (!allowed.value || visibility.value !== 'visible') stop()
})
useEventListener(window, 'blur', stop)
</script>

<template>
  <section class="tool-catalog" aria-labelledby="toolkit-title">
    <h1 id="toolkit-title">创作工具集</h1>
    <ul v-for="group in groups" :key="group.label" :aria-label="group.label" class="tool-grid">
      <li v-for="tool in group.tools" :key="tool.scene" :data-scene="tool.scene" :class="{ 'in-motion': active?.scene === tool.scene }"
          @pointerenter="enter($event, tool.scene)" @pointerleave="stop" @pointercancel="stop">
        <ElCard shadow="never" class="tool-card" :body-style="{ padding: '0' }">
          <div class="cover-window">
            <div class="cover-scene">
              <img class="tool-cover" :src="tool.cover" alt="" />
              <Transition name="motion">
                <CoverMotion v-if="active && active.scene === tool.scene" :scene="tool.scene" :photo="active.photo" />
              </Transition>
            </div>
          </div>
          <div class="tool-copy">
            <h2>{{ tool.name }}</h2>
            <p>{{ tool.description }}</p>
          </div>
        </ElCard>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.tool-catalog { padding: 24px clamp(16px, 1.5vw, 28px) 36px; color: var(--el-text-color-primary); }
.tool-catalog h1 { margin: 0 0 20px; font-size: 28px; line-height: 1.25; font-weight: 650; }
.tool-grid { padding: 0; margin: 0; display: grid; grid-template-columns: repeat(6,minmax(0,1fr)); gap: 16px; list-style: none; }
.tool-grid + .tool-grid { margin-top: 16px; }
.tool-card { height: 100%; overflow: hidden; border-radius: 20px; border: 1px solid var(--el-border-color-lighter); transition: border-color .18s ease; }
.tool-card:hover { border-color: var(--el-color-primary-light-3); }
.cover-window { overflow: hidden; }
.cover-scene { position: relative; }
.tool-cover { display: block; width: 100%; aspect-ratio: 1.8; object-fit: cover; }
.tool-copy { padding: 13px 16px 16px; }
.tool-copy p { margin: 3px 0 0; font-size: 13px; line-height: 1.5; color: var(--el-text-color-secondary); }
.tool-card h2 { margin: 0; font-size: 17px; line-height: 1.45; font-weight: 550; }
@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {
  .tool-card { transition: transform .16s ease-out, border-color .18s ease; }
  .cover-scene { transform-origin: 78% 50%; transition: transform .38s ease-out; }
  [data-scene="replicate"] .cover-scene, [data-scene="recolor"] .cover-scene,
  [data-scene="home-depot"] .cover-scene, [data-scene="edit-text"] .cover-scene { transform-origin: center; }
  .in-motion .tool-card { transform: translateY(-3px); }
  .in-motion .cover-scene { transform: scale(1.05); transition: transform 3s ease-in-out; }
}
@media(max-width:1500px) { .tool-grid { grid-template-columns: repeat(4,minmax(0,1fr)); } }
@media(max-width:1100px) { .tool-grid { grid-template-columns: repeat(3,minmax(0,1fr)); } }
@media(max-width:720px) { .tool-grid { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; } .tool-copy { padding: 12px; } .tool-card h2 { font-size: 15px; } .tool-card { border-radius: 14px; } }
</style>
