/** Prevent two tabs from overwriting the same local demo snapshot. */
export async function lockDemo(key: string): Promise<() => Promise<void>> {
  if (!navigator.locks) throw new Error('当前浏览器不支持 Demo 存储锁，请使用本机 Chrome 或 Edge 打开')
  return new Promise((resolve, reject) => {
    const finished = navigator.locks.request(`hengxin-framework-demo:${key}`, { ifAvailable: true }, async lock => {
      if (!lock) { reject(new Error('此 Demo 场景已在另一标签页打开。请关闭那个页面，再刷新本页继续。')); return }
      await new Promise<void>(release => resolve(async () => { release(); await finished }))
    })
    void finished.catch(reject)
  })
}
