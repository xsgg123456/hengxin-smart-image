// These helpers target an isolated Playwright context and an authenticated test API.
// Native CDP drag delivers real FileSystemEntry objects (including empty folders).
export async function dropNativeFolder(page, directoryPath) {
  const target = page.locator('.folder-drop'), box = await target.boundingBox()
  if (!box) throw new Error('上传目录区域不可见')
  const client = await page.context().newCDPSession(page)
  const point = { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  const data = { items: [], files: [directoryPath], dragOperationsMask: 1 }
  try {
    await client.send('Input.dispatchDragEvent', { type: 'dragEnter', ...point, data })
    await client.send('Input.dispatchDragEvent', { type: 'dragOver', ...point, data })
    await client.send('Input.dispatchDragEvent', { type: 'drop', ...point, data })
  } finally { await client.detach() }
}

// Use Chromium's real sandboxed directory/file handles; only replace the OS picker.
// The context owns this storage. Closing the isolated context discards it.
export async function installBrowserFolderPicker(page) {
  await page.addInitScript(() => {
    window.__skillPickerCalls = []
    window.showDirectoryPicker = async () => {
      window.__skillPickerCalls.push({ active: navigator.userActivation.isActive })
      if (!navigator.userActivation.isActive) throw new Error('目录选择不在用户手势内')
      if (window.__skillCancelPicker) throw new DOMException('取消', 'AbortError')
      return navigator.storage.getDirectory()
    }
  })
}

export async function inspectSavedFolder(page, rootName) {
  return page.evaluate(async rootName => {
    const parent = await navigator.storage.getDirectory(), root = await parent.getDirectoryHandle(rootName), entries = {}
    async function walk(dir, prefix) {
      for await (const child of dir.values()) {
        const path = prefix + child.name
        if (child.kind === 'directory') { entries[path + '/'] = { directory: true }; await walk(child, path + '/') }
        else {
          const file = await child.getFile(), bytes = await file.arrayBuffer()
          const sha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join('')
          entries[path] = { size: file.size, sha256 }
        }
      }
    }
    await walk(root, '')
    return { rootName, entries, pickerCalls: window.__skillPickerCalls }
  }, rootName)
}
