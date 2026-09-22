import type { HengxinService } from '../../types/hengxin'
import { createMockService } from './mock'
import { demoKey, readDemo, writeDemo } from './demo-storage'
import { lockDemo } from './demo-lock'

// 仅由显式 demo 模式动态加载；角色共用场景，真实 API 不参与。
export async function createDemoService(options: Parameters<typeof createMockService>[0] = {}): Promise<HengxinService> {
  const key = demoKey()
  const release = await lockDemo(key)
  let snapshot
  try { snapshot = await readDemo(key) } catch (reason) { await release(); throw reason }
  let queue = Promise.resolve(), stopped = false, failure: Error | undefined
  let engine: ReturnType<typeof createMockService>
  try {
    engine = createMockService({ ...options, demo: true, snapshot, changed: () => {
      queue = queue.then(save).catch(fail)
    } })
  } catch (reason) { await release(); throw reason }
  function fail(reason: unknown) {
    failure = new Error(`Demo 数据未保存，演示已暂停，请刷新后重试。${reason instanceof Error ? reason.message : ''}`)
    engine.dispose()
    window.dispatchEvent(new CustomEvent('hengxin:demo-storage-error', { detail: failure.message }))
  }
  async function save() {
    if (stopped || failure) return
    await writeDemo(key, engine.snapshot())
  }
  const dispose = async () => { stopped = true; engine.dispose(); window.removeEventListener('pagehide', dispose); await release() }
  window.addEventListener('pagehide', dispose)
  try { await save() } catch (reason) { await dispose(); throw reason }
  return new Proxy(engine, {
    get(target, property) {
      if (property === 'dispose') return dispose
      const method: unknown = Reflect.get(target, property)
      if (typeof method !== 'function') return method
      return (...args: unknown[]) => {
        const result = queue.then(async () => {
          if (failure) throw failure
          if (stopped) throw new Error('Demo 已关闭，请刷新页面')
          let value: unknown, rejected: unknown
          try { value = await Reflect.apply(method, target, args) } catch (reason) { rejected = reason }
          try { await save() } catch (reason) { fail(reason); throw failure }
          if (rejected) throw rejected
          return value
        })
        queue = result.then(() => undefined, () => undefined)
        return result
      }
    }
  })
}
