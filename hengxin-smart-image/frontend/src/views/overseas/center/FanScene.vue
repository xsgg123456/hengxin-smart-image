<template>
  <span class="fan-scene" aria-hidden="true">
    <canvas ref="canvas" width="882" height="333"></canvas>
  </span>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const canvas = ref<HTMLCanvasElement>()
const media = window.matchMedia('(hover: hover) and (prefers-reduced-motion: no-preference)')
let card: HTMLButtonElement | null = null
let frame = 0
let disposed = false
let stopAt = 0
let startedAt = 0
let ready: Promise<void> | undefined
let draw: ((angle: number) => void) | undefined

// The patch and rotor use the original 1455 × 759 photo coordinates.
const left = 466, top = 61, patchWidth = 882, patchHeight = 333
type Point = [number, number]
function polygon(ctx: CanvasRenderingContext2D, points: Point[]) {
  ctx.beginPath()
  points.forEach(([x,y],i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y))
  ctx.closePath()
}
function surface() {
  const layer = document.createElement('canvas')
  layer.width = patchWidth; layer.height = patchHeight
  return layer.getContext('2d', {willReadFrequently:true})!
}

async function prepare() {
  const photo = card!.querySelector('img')!
  await photo.decode()
  if (disposed) return
  const base = surface()
  base.drawImage(photo, left, top, patchWidth, patchHeight, 0, 0, patchWidth, patchHeight)
  const source=base.getImageData(0,0,patchWidth,patchHeight)
  const output=base.getImageData(0,0,patchWidth,patchHeight)
  // Reconstruct a continuous ceiling behind the moving blades, feathering into
  // the photo. Both colour samples come from the ceiling in this same picture.
  for(let x=0;x<patchWidth;x++){
    const upper=[0,0,0],lower=[0,0,0]
    for(let dx=-10;dx<=10;dx++){
      const col=Math.max(0,Math.min(patchWidth-1,x+dx))
      for(let c=0;c<3;c++){
        upper[c]+=source.data[(9*patchWidth+col)*4+c]/21
        lower[c]+=source.data[(292*patchWidth+col)*4+c]/21
      }
    }
    for(let y=0;y<patchHeight;y++){
      const mix=Math.max(0,Math.min(1,x/21,(patchWidth-1-x)/22,(y-13)/24,(293-y)/18))
      if(!mix)continue
      const t=Math.max(0,Math.min(1,(y-9)/283)),index=(y*patchWidth+x)*4
      for(let c=0;c<3;c++){
        const ceiling=upper[c]*(1-t)+lower[c]*t
        output.data[index+c]=Math.round(source.data[index+c]*(1-mix)+ceiling*mix)
      }
    }
  }
  base.putImageData(output,0,0)
  const ctx=canvas.value!.getContext('2d')!
  const rotorX=905,rotorY=228
  // Trace the oak blade at the upper right, then project all five blades into the fan's tilted rotation plane.
  const rotorBlade: Point[]=[[40,-9],[93,-16],[327,-29],[364,-28],[382,-17],[390,0],[386,17],[112,24],[57,13]]
  // Sample a strip along the grain of the photographed wooden blade.
  const wood=document.createElement('canvas')
  wood.width=192;wood.height=18
  const woodCtx=wood.getContext('2d')!
  woodCtx.transform(1,.15,0,1,-1042,-202-1042*.15)
  woodCtx.drawImage(photo,0,0)
  function blade(theta:number) {
    const sin=Math.sin(theta),cos=Math.cos(theta)
    ctx.save()
    ctx.translate(rotorX,rotorY)
    ctx.transform(cos,.30*sin,-sin,.30*cos+.32,0,0)
    polygon(ctx,rotorBlade)
    ctx.clip()
    ctx.drawImage(wood,35,-32,365,62)
    ctx.fillStyle='rgba(255,243,202,'+(.09+.23*(1-cos)/2)+')'
    ctx.fillRect(35,-32,365,62)
    ctx.restore()
  }
  function originalRegion(points:Point[]) {
    ctx.save();polygon(ctx,points);ctx.clip()
    ctx.drawImage(photo, left, top, patchWidth, patchHeight, left, top, patchWidth, patchHeight)
    ctx.restore()
  }
  draw=(angle:number)=>{
    ctx.setTransform(1,0,0,1,0,0);ctx.drawImage(base.canvas,0,0);ctx.translate(-left,-top)
    const angles=Array.from({length:5},(_,i)=>angle+i*Math.PI*2/5)
    originalRegion([[859,98],[870,91],[902,85],[932,88],[951,95],[946,116],[933,134],[917,140],[916,167],[896,167],[896,141],[879,134],[865,116]])
    originalRegion([[851,291],[857,291],[857,382],[851,382]])
    originalRegion([[957,286],[966,286],[966,394],[957,394]])
    angles.filter(a=>Math.sin(a)<0).forEach(blade)
    originalRegion([[823,176],[847,166],[899,160],[951,164],[977,173],[984,185],[979,214],[950,233],[935,250],[873,250],[868,230],[831,222],[824,214]])
    // A blade crosses the left half of the photographed motor. Restore its surface
    // from the unobstructed, symmetric right half before the front blades pass.
    ctx.save()
    polygon(ctx,[[825,174],[849,165],[869,164],[907,205],[913,219],[851,219],[825,204]])
    ctx.clip()
    ctx.translate(rotorX*2,0);ctx.scale(-1,1)
    ctx.drawImage(photo,0,0)
    ctx.restore()
    angles.filter(a=>Math.sin(a)>=0).forEach(blade)
    originalRegion([[871,251],[941,252],[967,263],[962,299],[951,321],[927,335],[898,338],[868,329],[850,310],[839,277],[840,262]])
  }
}
function tick(now:number) {
  if(disposed || !media.matches || (stopAt && now>=stopAt)){frame=0;return}
  draw?.((now-startedAt)*Math.PI*2/3000-.48)
  frame=requestAnimationFrame(tick)
}
function sync() {
  const active=media.matches && !!card?.matches(':hover, :focus-visible')
  if(!active){stopAt=performance.now()+350;return}
  stopAt=0
  ready??=prepare()
  void ready.then(()=>{
    if(!disposed && !stopAt && !frame){startedAt=performance.now();tick(startedAt)}
  }).catch(()=>{ready=undefined})
}
onMounted(()=>{
  card=canvas.value!.closest('button')
  for(const event of ['pointerenter','pointerleave','focus','blur'])card?.addEventListener(event,sync)
  media.addEventListener('change',sync);sync()
})
onUnmounted(()=>{
  disposed=true;cancelAnimationFrame(frame)
  for(const event of ['pointerenter','pointerleave','focus','blur'])card?.removeEventListener(event,sync)
  media.removeEventListener('change',sync)
})
</script>
