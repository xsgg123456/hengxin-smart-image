export const clipboardHint = '无法读取剪贴板，请点击上传区后按 Ctrl+V，或点击选择文件。'
export function isTextInput(target: EventTarget | null): boolean {
  return target instanceof Element && !!target.closest('input, textarea, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')
}
export function singleImageError(count: number, occupied: boolean): string {
  if (count > 1) return '此处最多上传 1 张图片，请一次选择 1 张。'
  if (count && occupied) return '此处已有图片，请先移除再添加。'
  return ''
}
export function clipboardFiles(data: DataTransfer | null): File[] {
  return Array.from(data?.files ?? []).filter(file => file.type.startsWith('image/'))
}
export async function readClipboardImages(clipboard: Pick<Clipboard, 'read'>): Promise<File[]> {
  const items = await clipboard.read()
  const files: File[] = []
  for (const item of items) {
    const type = item.types.find(type => type.startsWith('image/'))
    if (!type) continue
    const blob = await item.getType(type)
    const extension = type === 'image/jpeg' ? 'jpg' : type.split('/')[1] || 'png'
    files.push(new File([blob], '粘贴图片-' + Date.now() + '-' + (files.length + 1) + '.' + extension, { type }))
  }
  return files
}
