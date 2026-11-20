<template>
  <canvas ref="layer" class="motion-layer" :class="{ ready }" width="500" height="278" aria-hidden="true" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { getScene, type Scene } from './scenes'

const props = defineProps<{ photo: HTMLImageElement; scene: Scene }>()
const layer = ref<HTMLCanvasElement>()
const ready = ref(false)
let disposed = false
let frame = 0
onBeforeUnmount(() => { disposed = true; cancelAnimationFrame(frame) })

onMounted(async () => {
  try {
    await props.photo.decode()
    if (disposed) return
    const ctx = layer.value?.getContext('2d')
    if (!ctx) return
    const draw = getScene(props.photo, props.scene)
    const start = performance.now()
    let last = -Infinity
    function tick(now: number) {
      if (disposed || !ctx) return
      if (now - last >= 1000 / 30 - 1) {
        last = now
        ctx.drawImage(props.photo, 0, 0, 500, 278)
        ctx.save()
        draw(ctx, ((now - start) % 3000) / 3000)
        ctx.restore()
        ready.value = true
      }
      frame = requestAnimationFrame(tick)
    }
    tick(start)
  } catch {
    // The original cover remains visible if decoding or canvas setup fails.
    ready.value = false
  }
})
</script>

<style scoped>
.motion-layer { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; pointer-events: none; transition: opacity .22s ease; }
.motion-layer.ready { opacity: 1; }
.motion-layer.motion-leave-to { opacity: 0; }
</style>
