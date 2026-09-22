<template>
  <div ref="surface" class="generation-canvas" :class="{ running, paused, still: motion === false, compact }" :style="{ '--phase': `${-index * 0.43}s` }"
    role="status" :aria-label="`第 ${index + 1} 张 · ${label || (running ? '生成中' : '排队中')}`">
    <div class="generation-art" aria-hidden="true">
      <div class="generation-light light-one"></div>
      <div class="generation-light light-two"></div>
      <div class="generation-frame">
        <svg viewBox="0 0 48 48" fill="none"><path d="M16 9H11a2 2 0 0 0-2 2v5M32 9h5a2 2 0 0 1 2 2v5M9 32v5a2 2 0 0 0 2 2h5M39 32v5a2 2 0 0 1-2 2h-5" stroke="currentColor" stroke-width="1.5"/><path d="m24 15 2.4 6.6L33 24l-6.6 2.4L24 33l-2.4-6.6L15 24l6.6-2.4Z" fill="currentColor"/></svg>
      </div>
    </div>
    <div class="generation-copy"><strong>{{ label || (running ? '正在生成画面' : '等待开始生成') }}</strong><span>{{ description || (running ? '结果就绪后将在这里呈现' : '任务已受理，请稍候') }}</span></div>
    <div class="generation-footer" aria-hidden="true"><span>第 {{ index + 1 }} 张</span><span class="generation-state"><i></i>{{ statusText || (running ? '生成中' : '排队中') }}</span></div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
withDefaults(defineProps<{ running: boolean; index: number; label?: string; description?: string; statusText?: string; motion?: boolean; compact?: boolean }>(), { motion: true })
const surface = ref<HTMLElement>()
const inView = ref(false), pageVisible = ref(true)
const paused = computed(() => !inView.value || !pageVisible.value)
let observer: IntersectionObserver | undefined
function visibility() { pageVisible.value = document.visibilityState === 'visible' }
onMounted(() => {
  visibility()
  document.addEventListener('visibilitychange', visibility)
  if (typeof IntersectionObserver !== 'undefined') {
    observer = new IntersectionObserver(entries => { inView.value = entries.some(entry => entry.isIntersecting) })
    if (surface.value) observer.observe(surface.value)
  } else inView.value = true
})
onBeforeUnmount(() => { observer?.disconnect(); document.removeEventListener('visibilitychange', visibility) })
</script>
<style scoped>
.generation-canvas { position:relative; isolation:isolate; aspect-ratio:1; overflow:hidden; border-radius:8px; background:var(--el-fill-color-light); color:var(--el-text-color-primary); display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:0; }
.generation-art { position:absolute; inset:0; overflow:hidden; z-index:-1; }
.generation-light { position:absolute; width:85%; height:85%; border-radius:50%; opacity:.32; background:radial-gradient(ellipse,var(--el-color-primary-light-5),transparent 68%); animation:canvas-breathe 5s ease-in-out infinite; animation-delay:var(--phase); }
.light-one { left:-24%; top:-22%; }
.light-two { right:-25%; bottom:-32%; opacity:.22; }
.generation-frame { position:absolute; top:17%; left:calc(50% - 27px); width:54px; height:54px; color:var(--el-color-primary); display:grid; place-items:center; animation:canvas-breathe 4s ease-in-out infinite; animation-delay:var(--phase); }
.generation-frame svg { width:44px; height:44px; }
.generation-copy { display:flex; flex-direction:column; align-items:center; gap:8px; margin-top:44px; padding:0 10px; text-align:center; }
.generation-copy strong { font-size:14px; font-weight:600; }
.generation-copy>span { font-size:12px; color:var(--el-text-color-regular); line-height:1.5; }
.generation-footer { position:absolute; bottom:12px; left:12px; right:12px; display:flex; justify-content:space-between; gap:8px; font-size:11px; color:var(--el-text-color-regular); }
.generation-state { display:flex; align-items:center; gap:5px; }
.generation-state i { width:5px; height:5px; border-radius:50%; background:var(--el-color-primary); }
.running .generation-light { animation:canvas-flow 7s ease-in-out infinite alternate; animation-delay:var(--phase); opacity:.6; }
.running .light-two { animation-direction:alternate-reverse; }
.paused *, .paused .generation-light { animation-play-state:paused; }
.still *, .still .generation-light { animation:none; }
.compact { aspect-ratio:auto; padding:8px; opacity:.96; }
.compact .generation-frame, .compact .generation-footer { display:none; }
.compact .generation-copy { margin-top:0; gap:3px; }
@keyframes canvas-breathe { 0%,100% { opacity:.4; } 50% { opacity:.85; } }
@keyframes canvas-flow { from { transform:translate(-6%,-4%) scale(.9); } to { transform:translate(35%,28%) scale(1.15); } }
@media(prefers-reduced-motion:reduce) { .generation-canvas *, .running .generation-light { animation:none; } }
</style>
