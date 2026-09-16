// Usage: node export-assets.cjs /path/to/sharp
const fs = require('node:fs/promises')
const path = require('node:path')
const sharp = require(process.argv[2] || 'sharp')
const root = path.resolve(__dirname, '..')
const frontend = path.resolve(root, '../frontend')

async function png(name, size, destination) {
  return sharp(path.join(root, `${name}.svg`), { density: 288 })
    .resize({ width: size }).png().toFile(destination)
}

async function main() {
  const assetDir = path.join(frontend, 'src/assets/images/brand')
  await fs.mkdir(assetDir, { recursive: true })
  for (const name of ['mark', 'mark-small', 'mark-white', 'logo-horizontal', 'logo-horizontal-white', 'logo-compact', 'logo-compact-white']) {
    await fs.copyFile(path.join(root, `${name}.svg`), path.join(assetDir, `${name}.svg`))
  }
  for (const name of ['mark', 'mark-white', 'logo-horizontal', 'logo-horizontal-white', 'logo-compact', 'app-icon', 'app-icon-dark']) {
    await png(name, name.startsWith('logo') ? 2280 : 1024, path.join(root, `${name}.png`))
  }
  for (const size of [16, 24, 32, 48, 64]) {
    await png(size <= 24 ? 'mark-small' : 'mark', size, path.join(root, `icon-${size}.png`))
  }
  await fs.copyFile(path.join(root, 'favicon.svg'), path.join(frontend, 'public/favicon.svg'))
  await png('app-icon', 180, path.join(frontend, 'public/apple-touch-icon.png'))
  // ICO container with PNG entries; no extra package is needed.
  const images = await Promise.all([16, 32, 48, 256].map(size =>
    sharp(path.join(root, 'favicon.svg'), { density: 384 }).resize(size, size).png().toBuffer()))
  const ico = Buffer.alloc(6 + images.length * 16)
  ico.writeUInt16LE(1, 2)
  ico.writeUInt16LE(images.length, 4)
  let offset = ico.length
  images.forEach((buffer, i) => {
    const size = [16, 32, 48, 256][i]
    const entry = 6 + i * 16
    ico[entry] = ico[entry + 1] = size === 256 ? 0 : size
    ico.writeUInt16LE(1, entry + 4)
    ico.writeUInt16LE(32, entry + 6)
    ico.writeUInt32LE(buffer.length, entry + 8)
    ico.writeUInt32LE(offset, entry + 12)
    offset += buffer.length
  })
  const result = Buffer.concat([ico, ...images])
  for (const target of ['favicon.ico', '../frontend/public/favicon.ico', '../frontend/src/assets/images/favicon.ico']) {
    await fs.writeFile(path.resolve(root, target), result)
  }
  console.log('Exported transparent PNGs, 16–64px icons, ICO, and frontend assets.')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
