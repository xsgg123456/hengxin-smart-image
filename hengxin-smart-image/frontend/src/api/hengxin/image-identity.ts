import { identity } from './identity'

/** 原生图片和传送到 body 的预览器同样不能绕过身份错误核验。 */
export function installImageIdentity(doc: Document) {
  const epochs = new WeakMap<HTMLImageElement, number>()
  const record = (node: Node) => {
    if (!(node instanceof Element)) return
    if (node instanceof HTMLImageElement) epochs.set(node, identity.epoch)
    node.querySelectorAll('img').forEach(image => epochs.set(image, identity.epoch))
  }
  record(doc.documentElement)
  const observer = new MutationObserver(records => {
    for (const recordItem of records) {
      if (recordItem.type === 'attributes') record(recordItem.target)
      else recordItem.addedNodes.forEach(record)
    }
  })
  observer.observe(doc.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] })
  const onError = (event: Event) => {
    const image = event.target
    if (!(image instanceof HTMLImageElement) || !image.isConnected) return
    if (!image.closest('.hx-protected-content, .el-image-viewer__wrapper, .el-overlay')) return
    const epoch = epochs.get(image)
    if (epoch !== undefined) void identity.verify(epoch, true)
  }
  doc.addEventListener('error', onError, true)
  return () => { observer.disconnect(); doc.removeEventListener('error', onError, true) }
}
