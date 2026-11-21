// Run against the local overseas frontend and its signed-in test member.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = new URL(process.env.OVERSEAS_LOCAL_URL || 'http://127.0.0.2:4191/overseas/')
assert.ok(['localhost', '127.0.0.1', '127.0.0.2'].includes(base.hostname))
const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 911 } })
  await page.goto(new URL('#/overseas/design-center', base).href)
  const sidebar = page.locator('aside')
  await sidebar.getByText('创作工具集', { exact: true }).click()
  await page.getByRole('heading', { name: '创作工具集', exact: true }).waitFor()
  assert.equal(new URL(page.url()).hash, '#/overseas/creative-tools')
  const platforms = page.getByRole('list', { name: '平台生图' })
  const editing = page.getByRole('list', { name: '图片工具' })
  assert.deepEqual(await platforms.getByRole('heading').allTextContents(), [
    '亚马逊生图(OUTON)', '亚马逊生图(OUTONLIFE)', '亚马逊生图(BELEEV)', 'Wayfair生图',
    '沃尔玛生图', 'The Home Depot生图', '美客多生图', '其他平台(自定义尺寸)'
  ])
  assert.deepEqual(await editing.getByRole('heading').allTextContents(), [
    '爆款复刻', 'AI去掉产品', 'AI一键白底图', 'AI无痕改字', 'AI万物抠图', 'AI产品换色'
  ])
  const cards = page.locator('.tool-card')
  const rows = () => cards.evaluateAll(elements => {
    const counts = new Map()
    for (const card of elements) {
      const y = Math.round(card.getBoundingClientRect().top)
      counts.set(y, (counts.get(y) || 0) + 1)
    }
    return [...counts.values()]
  })
  assert.deepEqual(await rows(), [6, 2, 6])
  const covers = [
    ['亚马逊生图(OUTON)', 'outon'],
    ['亚马逊生图(OUTONLIFE)', 'outonlife'],
    ['亚马逊生图(BELEEV)', 'beleev'],
    ['Wayfair生图', 'wayfair'],
    ['沃尔玛生图', 'walmart'],
    ['The Home Depot生图', 'home-depot'],
    ['美客多生图', 'mercado-libre'],
    ['其他平台(自定义尺寸)', 'custom-size'],
    ['AI去掉产品', 'replicate'],
    ['爆款复刻', 'white-background'],
    ['AI一键白底图', 'edit-text'],
    ['AI无痕改字', 'cutout'],
    ['AI万物抠图', 'recolor'],
    ['AI产品换色', 'remove-product'],
  ]
  for (const [title, filename] of covers) {
    const card = cards.filter({
      has: page.getByRole('heading', { name: title, exact: true })
    })
    const src = await card.locator('img').evaluate(async image => {
      await image.decode()
      return image.currentSrc
    })
    const asset = new URL(`../src/views/overseas/creative-tools/tool-covers/${filename}.jpg`, import.meta.url)
    assert.deepEqual(await (await page.request.get(src)).body(), await readFile(asset))
  }
  async function assertMoving(layer) {
    const previous = await layer.evaluate(canvas => canvas.toDataURL())
    await page.waitForFunction(({ canvas, previous }) => canvas.toDataURL() !== previous, {
      canvas: await layer.elementHandle(), previous
    }, { polling: 120, timeout: 4000 })
  }
  function waitForLift(card, y) {
    return page.waitForFunction(({ el, y }) =>
      new DOMMatrixReadOnly(getComputedStyle(el).transform).m42 === y, { el: card, y })
  }
  // Both yellow fan silhouettes, the rider and sled, and the house and street lamp
  // have distinct points on the 500 x 278 covers. Compare their actual pixels.
  async function checkFade(card, scene) {
    const layer = card.locator('canvas.ready')
    await layer.waitFor()
    const fan = scene === 'replicate'
    const snow = scene === 'edit-text'
    const background = fan ? [[130, 130], [375, 169]] : snow ? [[75, 55], [100, 85]] : [[75, 100], [78, 100]]
    const subject = fan ? [[329, 33], [309, 194]]
      : snow ? [[222, 151], [200, 170], [152, 221]]
        : [[226, 87], [195, 150], [167, 170], [190, 225], [300, 213]]
    const sample = () => layer.evaluate((canvas, { background, subject }) => {
      const photo = document.createElement('canvas')
      photo.width = canvas.width
      photo.height = canvas.height
      const source = photo.getContext('2d')
      source.drawImage(canvas.parentElement.querySelector('img'), 0, 0, photo.width, photo.height)
      const frame = canvas.getContext('2d')
      function pixels(ctx, coordinates) {
        return coordinates.map(([x, y]) => Array.from(ctx.getImageData(x, y, 1, 1).data).slice(0, 3))
      }
      return {
        background: pixels(frame, background), original: pixels(source, background),
        subject: pixels(frame, subject), originalSubject: pixels(source, subject),
        checker: pixels(source, [[396, 100], [399, 100]]),
        fanBlades: pixels(frame, Array.from({ length: 115 }, (_, i) => [265 + i, 66]))
      }
    }, { background, subject })
    await page.waitForTimeout(600)
    const middle = await sample()
    await page.waitForTimeout(1400)
    const end = await sample()
    assert.notDeepEqual(middle.background, middle.original, scene + ' begins fading')
    assert.notDeepEqual(middle.background, end.background, scene + ' fades progressively')
    assert.deepEqual(middle.subject, middle.originalSubject, scene + ' subject during fade')
    assert.deepEqual(end.subject, end.originalSubject, scene + ' subject after fade')
    if (fan) {
      for (const rgb of end.background) assert.ok(Math.max(...rgb) - Math.min(...rgb) < 32, 'ceiling replaces yellow fans')
      await page.waitForTimeout(230)
      const later = await sample()
      assert.deepEqual(later.background, end.background)
      assert.notDeepEqual(later.fanBlades, end.fanBlades, 'photographed fan keeps turning')
    } else {
      assert.deepEqual(end.background, snow ? [[255, 255, 255], [255, 255, 255]] : end.checker)
      assert.equal(await card.locator('.cover-scene').evaluate(el => getComputedStyle(el).transform), 'none')
      const finalFrame = await layer.evaluate(canvas => canvas.toDataURL())
      await page.waitForTimeout(1300)
      assert.equal(await layer.evaluate(canvas => canvas.toDataURL()), finalFrame, scene + ' holds final frame')
    }
  }
  for (const card of await platforms.locator('.tool-card').all()) {
    await card.getByRole('heading').hover()
    const layer = card.locator('canvas.ready')
    await layer.waitFor()
    await assertMoving(layer)
    assert.equal(await card.locator('.cover-scene').evaluate(el => getComputedStyle(el).transitionDuration), '3s')
  }
  for (const item of await editing.getByRole('listitem').all()) {
    const scene = await item.getAttribute('data-scene')
    const card = item.locator('.tool-card')
    const element = await card.elementHandle()
    const title = card.getByRole('heading')
    const photo = card.locator('img')
    const canvas = card.locator('canvas')
    await title.hover()
    await waitForLift(element, -3)
    assert.equal(await canvas.count(), 0, scene + ' title hover')
    await photo.hover()
    await waitForLift(element, -3)
    if (['white-background', 'cutout'].includes(scene)) {
      await page.waitForFunction(el => new DOMMatrixReadOnly(getComputedStyle(el).transform).a > 1.001,
        await card.locator('.cover-scene').elementHandle())
      assert.equal(await canvas.count(), 0, scene + ' gently zooms the original photograph')
    } else if (scene === 'remove-product') {
      const layer = card.locator('canvas.ready')
      await layer.waitFor()
      await assertMoving(layer)
    } else {
      await checkFade(card, scene)
    }
    await title.hover()
    await canvas.waitFor({ state: 'detached' })
    await page.waitForFunction(el => new DOMMatrixReadOnly(getComputedStyle(el).transform).isIdentity,
      await card.locator('.cover-scene').elementHandle())
    await waitForLift(element, -3)
    await page.mouse.move(0, 0)
    await waitForLift(element, 0)
  }
  await page.mouse.move(0, 0)
  const activePhoto = editing.locator('[data-scene="replicate"] img')
  await activePhoto.hover()
  await editing.locator('canvas.ready').waitFor()
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.locator('canvas').first().waitFor({ state: 'detached' })
  for (const card of await cards.all()) {
    await card.hover()
    assert.equal(await card.evaluate(el => getComputedStyle(el).transform), 'none')
    assert.equal(await card.locator('.cover-scene').evaluate(el => getComputedStyle(el).transform), 'none')
    assert.equal(await card.locator('canvas').count(), 0)
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await editing.waitFor()
  assert.deepEqual(await rows(), [2, 2, 2, 2, 2, 2, 2])
  console.log('PASS official navigation, refresh, 14 original covers, responsive rows, eight platform animations, six image-only hover effects, whole-card lift, exit reset and reduced motion')
} finally {
  await browser.close()
}
