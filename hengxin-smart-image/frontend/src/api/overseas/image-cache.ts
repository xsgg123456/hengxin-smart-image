import { IdentityError } from '../identity/request'
import { cancelledImage, imageResponseError, PREFETCH_IMAGE_BYTES, readImageBlob } from './image-cache-http'

interface Entry { blob: Blob; etag: string; url?: string; pins: number }
interface Job {
  url: string; controller: AbortController; epoch: number; priority: number; running: boolean; background: boolean; users: number
  promise: Promise<Entry>; resolve: (entry: Entry) => void; reject: (reason: unknown) => void
}
export interface ImageLease { blob: Blob; url: string; release: () => void }
export interface ImageSource { url: string; size?: number }

/** Originals only. HTTP cache remains private and is revalidated by the server on every read. */
export function createImageCache(options: { fetcher?: typeof fetch; maxBytes?: number; maxEntries?: number; createUrl?: typeof URL.createObjectURL; revokeUrl?: typeof URL.revokeObjectURL } = {}) {
  const fetcher: typeof fetch = options.fetcher || ((...args) => fetch(...args))
  const maxBytes = options.maxBytes ?? 128 * 1024 * 1024, maxEntries = options.maxEntries ?? 40
  const createUrl = options.createUrl || (blob => URL.createObjectURL(blob)), revokeUrl = options.revokeUrl || (url => URL.revokeObjectURL(url))
  const entries = new Map<string, Entry>(), jobs = new Map<string, Job>(), listeners = new Set<() => void>()
  let account = '', epoch = 0, active = 0, bytes = 0, scope = '', attempted = new Set<string>()
  function drop(url: string) {
    const entry = entries.get(url); if (!entry) return
    entries.delete(url); bytes -= entry.blob.size
    if (entry.url) { revokeUrl(entry.url); entry.url = undefined }
  }
  function trim() {
    for (const [url, entry] of entries) {
      if (bytes <= maxBytes && entries.size <= maxEntries) break
      if (!entry.pins && !jobs.has(url)) drop(url)
    }
  }
  function touch(url: string, entry: Entry) { entries.delete(url); entries.set(url, entry) }
  function cancel(job: Job) {
    job.controller.abort(); job.reject(cancelledImage())
    if (jobs.get(job.url) === job) jobs.delete(job.url)
  }
  function clear() {
    ++epoch; scope = ''; attempted.clear()
    for (const job of jobs.values()) cancel(job)
    for (const url of entries.keys()) drop(url)
    listeners.forEach(listener => listener())
  }
  function setIdentity(value: string) { if (account !== value) { clear(); account = value } }
  function invalidate(url: string) { drop(url); const job = jobs.get(url); if (job) cancel(job) }
  function assertCurrent(job: Job) { if (job.epoch !== epoch || job.controller.signal.aborted) throw cancelledImage() }
  async function request(job: Job, method: 'HEAD' | 'GET', etag?: string) {
    const response = await fetcher(job.url, { method, credentials: 'include', cache: 'no-cache', redirect: 'error',
      signal: AbortSignal.any([job.controller.signal, AbortSignal.timeout(120000)]), headers: etag ? { 'If-None-Match': etag } : undefined })
    assertCurrent(job)
    if (!response.ok && response.status !== 304) {
      if ([401, 403, 404].includes(response.status)) drop(job.url)
      throw imageResponseError(response.status)
    }
    return response
  }
  async function run(job: Job): Promise<Entry> {
    const cached = entries.get(job.url)
    if (cached || job.background) {
      const head = await request(job, 'HEAD', cached?.etag)
      if (cached && cached.etag && (head.status === 304 || head.headers.get('ETag') === cached.etag)) {
        touch(job.url, cached); return cached
      }
      if (cached) drop(job.url)
      if (job.background && Number(head.headers.get('Content-Length')) > PREFETCH_IMAGE_BYTES) throw cancelledImage()
    }
    const response = await request(job, 'GET')
    if (response.status === 304) throw imageResponseError(502) // Browser-managed GET revalidation normally returns the cached 200 body.
    const blob = await readImageBlob(response, job.background ? PREFETCH_IMAGE_BYTES : undefined)
    assertCurrent(job)
    const entry: Entry = { blob, etag: response.headers.get('ETag') || '', pins: 0 }
    entries.set(job.url, entry); bytes += blob.size
    return entry
  }
  function pump() {
    while (active < 2) {
      const job = [...jobs.values()].filter(item => !item.running).sort((a, b) => b.priority - a.priority)[0]
      if (!job) return
      job.running = true; active++
      void run(job).then(job.resolve, job.reject).finally(() => {
        active--; if (jobs.get(job.url) === job) jobs.delete(job.url)
        // Foreground consumers pin in their promise continuation before eviction.
        queueMicrotask(() => { trim(); pump() })
      })
    }
  }
  function ensure(url: string, background: boolean) {
    if (!account) throw new IdentityError(401, '身份已失效，请重新登录')
    const existing = jobs.get(url)
    if (existing) { if (!background) { existing.priority = 1; existing.background = false }; return existing }
    let resolve!: Job['resolve'], reject!: Job['reject']
    const promise = new Promise<Entry>((yes, no) => { resolve = yes; reject = no })
    const job: Job = { url, controller: new AbortController(), epoch, priority: background ? 0 : 1, running: false, background, users: 0, promise, resolve, reject }
    jobs.set(url, job); queueMicrotask(pump)
    return job
  }
  async function acquire(url: string, { signal }: { signal?: AbortSignal } = {}): Promise<ImageLease> {
    if (signal?.aborted) throw cancelledImage()
    const job = ensure(url, false); job.users++
    let abort!: () => void
    const aborted = new Promise<never>((_resolve, reject) => { abort = () => reject(cancelledImage()); signal?.addEventListener('abort', abort, { once: true }) })
    try {
      const entry = await Promise.race([job.promise, aborted]); assertCurrent(job)
      if (signal?.aborted) throw cancelledImage()
      entry.pins++; entry.url ||= createUrl(entry.blob); touch(url, entry)
      let released = false
      return { blob: entry.blob, url: entry.url, release() {
        if (released) return; released = true; entry.pins--
        if (!entry.pins && entry.url) { revokeUrl(entry.url); entry.url = undefined }
        trim()
      } }
    } finally {
      signal?.removeEventListener('abort', abort); job.users--
      if (!job.users && !job.background && signal?.aborted) { cancel(job); pump() }
    }
  }
  function setPrefetch(nextScope: string, sources: ImageSource[]) {
    if (scope !== nextScope) { scope = nextScope; attempted = new Set() }
    const wanted = new Set(sources.filter(item => !item.size || item.size <= PREFETCH_IMAGE_BYTES).map(item => item.url))
    for (const job of jobs.values()) if (job.background && !wanted.has(job.url) && !job.users) cancel(job)
    if (!account) return
    for (const url of wanted) {
      if (attempted.has(url) || entries.has(url) || jobs.has(url)) continue
      attempted.add(url)
      const job = ensure(url, true)
      void job.promise.catch(() => { /* Prefetch never blocks the page; a click retries explicitly. */ })
    }
    pump()
  }
  return { acquire, setPrefetch, setIdentity, clear, invalidate, subscribe(listener: () => void) { listeners.add(listener); return () => listeners.delete(listener) },
    stats: () => ({ entries: entries.size, bytes, active, queued: [...jobs.values()].filter(job => !job.running).length }) }
}
export const overseasImageCache = createImageCache()
