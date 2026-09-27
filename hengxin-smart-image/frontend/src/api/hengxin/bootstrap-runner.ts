import { identity } from './identity'

/** 同代次共享启动；新代次无需等待旧启动，旧 finally 不能解锁新启动。 */
export function createBootstrapRunner<T>(options: {
  load: () => Promise<T>; start: () => void; accept: (value: T) => void | Promise<void>
  fail: (error: unknown) => void; finish: () => void
}) {
  let running: { epoch: number; promise: Promise<void> } | undefined
  return () => {
    const epoch = identity.epoch
    if (running?.epoch === epoch) return running.promise
    options.start()
    const promise = Promise.resolve().then(options.load).then(value => {
      if (identity.current(epoch)) return options.accept(value)
    }).catch(error => { if (identity.current(epoch)) options.fail(error) }).finally(() => {
      if (identity.current(epoch)) options.finish()
      if (running?.promise === promise) running = undefined
    })
    running = { epoch, promise }
    return promise
  }
}
