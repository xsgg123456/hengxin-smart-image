<script setup lang="ts">
import { computed, defineAsyncComponent, ref, shallowRef, watch } from 'vue'
import { useDocumentVisibility, useEventListener, useMediaQuery } from '@vueuse/core'
import { useRoute, useRouter } from 'vue-router'
import { FolderOpened } from '@element-plus/icons-vue'
import { CREATIVE_TOOLS, type CreativeTool, type CreativeToolKey } from '@/api/overseas/creative-tools'
import type { TasksApi } from '@/api/overseas/tasks'
import CreateCreativeTask from './CreateCreativeTask.vue'
import MyCreations from './MyCreations.vue'
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

const covers: Record<CreativeToolKey, [string, string]> = {
  'outon': [outonCover, '为 OUTON 制作亚马逊主图和 A+ 图'],
  'outonlife': [outonlifeCover, '为 OUTONLIFE 制作亚马逊主图和 A+ 图'],
  'beleev': [beleevCover, '为 BELEEV 制作亚马逊主图和 A+ 图'],
  'wayfair': [wayfairCover, '为威费尔商品制作主图和详情图'],
  'walmart': [walmartCover, '为沃尔玛商品制作主图和详情图'],
  'home-depot': [homeDepotCover, '为家得宝商品制作上架主图'],
  'mercado-libre': [mercadoLibreCover, '为美客多商品制作上架主图'],
  'custom-size': [customSizeCover, '按目标平台的宽高要求生成商品图'],
}
const platformTools = CREATIVE_TOOLS.map(tool => ({ scene: tool.value, name: tool.label, cover: covers[tool.value][0], description: covers[tool.value][1] }))
const editingTools: ToolCard[] = [
  { name: '爆款复刻', description: '参考爆款构图，制作同款风格商品图', cover: whiteBackgroundCover, scene: 'white-background' },
  { name: 'AI去掉产品', description: '移除画面中的产品，补全背景', cover: replicateCover, scene: 'replicate' },
  { name: 'AI一键白底图', description: '保留商品主体，一键换成纯白背景', cover: editTextCover, scene: 'edit-text' },
  { name: 'AI无痕改字', description: '替换图中文字，贴合原有字形与背景', cover: cutoutCover, scene: 'cutout' },
  { name: 'AI万物抠图', description: '抠出图中主体，保留透明背景', cover: recolorCover, scene: 'recolor' },
  { name: 'AI产品换色', description: '更换产品颜色，保留材质与光影', cover: removeProductCover, scene: 'remove-product' }
]
const groups = [{ label: '平台生图', tools: platformTools }, { label: '图片工具', tools: editingTools }]
const props = defineProps<{ api: TasksApi; actorId: string; refresh: number }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const router = useRouter(), route = useRoute()
const myTasksOpen = computed(() => route.query.view === 'mine')
const selected = ref<CreativeTool>()
function choose(scene: Scene) {
  stop()
  selected.value = CREATIVE_TOOLS.find(tool => tool.value === scene)
}
function closeMine() {
  const query = { ...route.query }
  delete query.view
  void router.replace({ query })
}
function openTask(id: string) {
  selected.value = undefined
  void router.push('/overseas/tasks/' + encodeURIComponent(id))
}
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
    <header class="catalog-heading">
      <h1 id="toolkit-title">创作工具集</h1>
      <ElButton :icon="FolderOpened" @click="router.push({ query: { ...route.query, view: 'mine' } })">我的创作</ElButton>
    </header>
    <ul v-for="group in groups" :key="group.label" :aria-label="group.label" class="tool-grid">
      <li v-for="tool in group.tools" :key="tool.scene" :data-scene="tool.scene" :class="{ 'in-motion': active?.scene === tool.scene }"
          @pointerenter="group.tools === platformTools && enter($event, tool.scene)" @pointerleave="stop" @pointercancel="stop">
        <ElCard shadow="never" class="tool-card" :body-style="{ padding: '0' }">
          <div class="cover-window" @pointerenter="group.tools === editingTools && enter($event, tool.scene)"
               @pointerleave="group.tools === editingTools && stop()">
            <div class="cover-scene">
              <img class="tool-cover" :src="tool.cover" alt="" />
              <Transition name="motion">
                <CoverMotion v-if="active?.scene === tool.scene && tool.scene !== 'white-background' && tool.scene !== 'cutout'" :scene="tool.scene" :photo="active.photo" />
              </Transition>
            </div>
          </div>
          <div class="tool-copy">
            <h2><button v-if="group.tools === platformTools" type="button" class="tool-action" @click="choose(tool.scene)">{{ tool.name }}</button><template v-else>{{ tool.name }}</template></h2>
            <p>{{ tool.description }}</p>
          </div>
        </ElCard>
      </li>
    </ul>
  </section>
  <CreateCreativeTask v-if="selected" :key="selected.value" :tool="selected" :actor-id="props.actorId" :api="api" @close="selected = undefined" @created="openTask" @failure="emit('failure', $event)" />
  <MyCreations v-if="myTasksOpen" :api="api" :refresh="refresh" @close="closeMine" @open="openTask" @failure="emit('failure', $event)" />
</template>

<style scoped>
.tool-catalog { padding: 24px clamp(16px, 1.5vw, 28px) 36px; color: var(--el-text-color-primary); }
.tool-catalog h1 { margin: 0 0 20px; font-size: 28px; line-height: 1.25; font-weight: 650; }
.catalog-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.catalog-heading h1 { margin: 0; }
.tool-card { position: relative; }
.tool-action { font: inherit; color: inherit; text-align: inherit; border: 0; background: transparent; padding: 0; cursor: pointer; }
.tool-action::after { content: ''; position: absolute; inset: 0; border-radius: inherit; }
.tool-card:focus-within { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.tool-action:focus { outline: none; }
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
  .tool-grid > li:hover .tool-card { transform: translateY(-3px); }
  :is([data-scene="edit-text"], [data-scene="recolor"]).in-motion .cover-scene { transform: none; }
  .in-motion .cover-scene { transform: scale(1.05); transition: transform 3s ease-in-out; }
}
@media(max-width:1500px) { .tool-grid { grid-template-columns: repeat(4,minmax(0,1fr)); } }
@media(max-width:1100px) { .tool-grid { grid-template-columns: repeat(3,minmax(0,1fr)); } }
@media(max-width:720px) { .tool-grid { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; } .tool-copy { padding: 12px; } .tool-card h2 { font-size: 15px; } .tool-card { border-radius: 14px; } }
</style>
