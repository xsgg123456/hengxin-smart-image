import { prepareFan } from './fans'

function surface() {
  const c = document.createElement('canvas')
  c.width = 500
  c.height = 278
  return c.getContext('2d', { willReadFrequently: true })!
}

// Follow the left-hand photographic panel. Everything outside its edge already
// has the finished white background, including the fine hair on the right.
function snowOverlay() {
  const overlay = surface()
  overlay.scale(.5, .5)
  overlay.fillStyle = 'white'
  overlay.fill(new Path2D('M80 38H544L520 518H80Q40 518 40 478V78Q40 38 80 38Z'))
  overlay.globalCompositeOperation = 'destination-out'
  const rider = new Path2D(
    'M559 66 Q533 66 521 93 L519 105 523 113 518 121 513 126 509 140 ' +
    'Q492 142 483 149 L469 148 458 153 452 161 454 168 463 160 471 158 ' +
    'L461 166 452 172 450 181 458 174 462 175 454 186 449 191 434 198 ' +
    'Q413 201 405 222 Q401 231 408 244 L417 253 434 258 440 263 428 278 ' +
    'Q411 266 396 262 Q380 258 368 270 L346 288 324 309 304 327 294 339 ' +
    'Q283 339 283 353 L274 348 261 344 250 345 244 350 239 351 237 357 ' +
    'L232 361 234 369 231 376 235 384 236 390 242 395 247 403 255 407 ' +
    'L263 408 270 415 275 425 278 430 277 434 287 444 299 450 307 444 ' +
    'L307 451 279 446 Q264 441 255 447 Q249 452 268 458 L349 484 372 489 ' +
    'L389 485 397 487 416 478 425 478 436 472 445 471 455 455 ' +
    'L475 447 504 434 650 384 690 310 690 70Z')
  overlay.fill(rider)
  // Snow peeks through the opening between the mittens and the steering bar.
  overlay.globalCompositeOperation = 'source-over'
  overlay.fill(new Path2D('M463 250 Q473 245 479 237 L480 248 474 253 463 253Z'))
  return overlay.canvas
}

// Reconstruct the ceiling along the direction of each side of the cornice.
// Feather the outer margin into the untouched photograph.
function ceilingOverlay(photo: HTMLImageElement) {
  const src = surface()
  src.drawImage(photo, 0, 0, 500, 278)
  const original = src.getImageData(0, 0, 500, 278).data
  const overlay = surface()
  const clean = overlay.createImageData(500, 278)
  for (const [left, right, top, bottom, slope] of [[30, 227, 88, 173, .175], [302, 453, 144, 200, -.13]]) {
    for (let x = left; x < right; x++) {
      for (let y = top; y < bottom; y++) {
        // Keep the pendant wire and its mounting point below the right-hand ghost.
        if (x >= 306 && x <= 313 && y >= 182) continue
        const t = (x - left) / (right - left)
        const offset = 4 * (500 * y + x)
        for (let channel = 0; channel < 3; channel++) {
          let value = 0
          for (const [boundary, weight] of [[left, 1-t],[right,t]]) {
            const v = y + slope * (boundary-x)
            const i = (Math.floor(v)*500 + boundary)*4 + channel
            const f = v - Math.floor(v)
            value += weight*((1-f)*original[i]+f*original[i+2000])
          }
          clean.data[offset+channel] = value
        }
        const edge = Math.min(x-left,right-x,y-top,bottom-y)
        clean.data[offset+3] = 255*Math.min(1,edge/6)
      }
    }
  }
  overlay.putImageData(clean,0,0)
  return overlay.canvas
}

// Continue the existing checkerboard with a strip from its unobstructed right
// side. 107 source pixels span nine full repeats, keeping the squares aligned.
function houseOverlay(photo: HTMLImageElement) {
  const overlay = surface()
  overlay.save()
  overlay.beginPath()
  overlay.roundRect(20, 19, 460, 240, 16)
  overlay.clip()
  overlay.beginPath()
  overlay.rect(20, 19, 221, 240)
  overlay.clip()
  for (const x of [-78, 29, 136]) {
    overlay.drawImage(photo, 350, 19, 107, 240, x, 19, 107, 240)
  }
  overlay.restore()

  // Trace the model in 2x reference coordinates. The street lamp belongs to
  // the base; the narrow spaces on either side of its pole are background.
  overlay.scale(.5, .5)
  overlay.globalCompositeOperation = 'destination-out'
  overlay.fill(new Path2D(
    'M702 40 L480 65 L469 63 Q468 56 459 54 Q447 51 443 63 L440 73 ' +
    'L398 182 Q394 192 385 194 Q379 196 382 203 L385 205 374 205 ' +
    'L373 212 378 215 378 233 374 239 374 244 370 245 370 380 ' +
    'L367 385 367 402 363 417 361 423 350 425 349 432 344 429 ' +
    'L343 408 344 405 344 400 341 397 338 306 339 301 341 297 ' +
    'L341 289 344 280 345 275 342 271 338 268 338 265 335 264 ' +
    'L335 258 332 256 330 258 330 263 326 266 326 269 321 272 ' +
    'L320 277 322 281 325 295 326 300 330 303 331 309 334 399 ' +
    'L331 402 332 407 335 409 333 428 329 432 329 435 311 436 ' +
    'L308 439 309 450 307 452 309 455 573 499 693 440Z'))
  return overlay.canvas
}

export const FADE_DURATION_MS = 1750

type RemovalScene = 'replicate' | 'edit-text' | 'recolor'
export function removalFrame(photo: HTMLImageElement, scene: RemovalScene) {
  const overlay = scene === 'recolor' ? houseOverlay(photo)
    : scene === 'edit-text' ? snowOverlay() : ceilingOverlay(photo)
  const fan = scene === 'replicate' ? prepareFan(photo, 'replicate') : undefined
  return (ctx: CanvasRenderingContext2D, elapsed: number) => {
    if (fan) {
      ctx.save()
      fan(ctx, elapsed % 3000 / 3000)
      ctx.restore()
    }
    const t = Math.min(1, elapsed / FADE_DURATION_MS)
    ctx.globalAlpha = t*t*(3-2*t)
    ctx.drawImage(overlay, 0, 0)
    ctx.globalAlpha = 1
  }
}
