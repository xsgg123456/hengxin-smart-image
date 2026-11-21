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
  // Sample real canvas frames: CSS zoom alone must not pass the hover check.
  for (const card of await cards.all()) {
    await card.hover()
    const layer = card.locator('canvas.ready')
    await layer.waitFor()
    const previous = await layer.evaluate(canvas => canvas.toDataURL())
    await page.waitForFunction(({ canvas, previous }) => canvas.toDataURL() !== previous, {
      canvas: await layer.elementHandle(), previous
    }, { polling: 120, timeout: 4000 })
    assert.equal(await card.locator('.cover-scene').evaluate(el => getComputedStyle(el).transitionDuration), '3s')
  }
  await page.mouse.move(0, 0)
  await page.locator('canvas.motion-layer').first().waitFor({state:'detached'})
  await cards.first().hover()
  await cards.first().locator('canvas.ready').waitFor()
  await page.emulateMedia({reducedMotion:'reduce'})
  await page.locator('canvas.motion-layer').first().waitFor({state:'detached'})
  assert.equal(await cards.first().evaluate(el => getComputedStyle(el).transform), 'none')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await editing.waitFor()
  assert.deepEqual(await rows(), [2, 2, 2, 2, 2, 2, 2])
  console.log('PASS official navigation, refresh, 14 cards, responsive rows and all fourteen original covers, animated scenes and reduced motion')
} finally {
  await browser.close()
}
