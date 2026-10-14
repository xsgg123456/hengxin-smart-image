import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMaterialsApi, isMaterial, validateFile, readyMaterialIds, type Material } from '../src/api/overseas/materials'
import { createTasksApi, emptyTaskDraft } from '../src/api/overseas/tasks'
const version = { version: 1, status: 'ready' as const, parserVersion: 'v1', text: '<script>data</script>', error: null, createdAt: '2026-10-12' }
const material: Material = { ...version, id: 'm/1', kind: 'competitor', name: 'a.csv', sizeBytes: 100, contentType: 'text/csv', taskId: null, versions: [version] }
test('资料契约拒绝缺版本、空解析、无效状态；只允许未绑定成功资料和唯一类别', () => {
  assert.equal(isMaterial(material), true)
  for (const value of [{ ...material, versions: [] }, { ...material, text: '' }, { ...material, taskId: 1 }, { ...material, status: 'processing' }, { ...material, versions: [{}] }]) assert.equal(isMaterial(value), false)
  assert.deepEqual(readyMaterialIds([material]), ['m/1'])
  for (const files of [[], [material, material], [{ ...material, taskId: 'bound' }]]) assert.throws(() => readyMaterialIds(files))
})
test('任意上传格式、空文件与500 MB边界', () => {
  assert.doesNotThrow(() => validateFile({ name: 'A.PDF', size: 500_000_000 }, 'requirement'))
  for (const name of ['a.xls', 'a.xlsx', 'a.csv']) assert.doesNotThrow(() => validateFile({ name, size: 1 }, 'competitor'))
  for (const name of ['a.doc', 'a.ppt', 'a.pptx', 'a.zip', '无扩展名']) for (const kind of ['requirement', 'competitor'] as const) assert.doesNotThrow(() => validateFile({ name, size: 1 }, kind))
  assert.deepEqual(readyMaterialIds([{ ...material, status: 'failed', text: '', error: '未解析' }]), ['m/1'])
  assert.throws(() => validateFile({ name: 'a.pdf', size: 0 }, 'requirement'), /为空/)
  assert.throws(() => validateFile({ name: 'a.csv', size: 500_000_000 + 1 }, 'competitor'), /500 MB/)
  assert.doesNotThrow(() => validateFile({ name: 'a.pdf', size: 1 }, 'competitor'))
})
test('资料 API 使用海外路径、写保护、会话及受保护原件，无公开地址', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createMaterialsApi(async (url, options) => {
    calls.push({ url: String(url), options })
    if (options?.method === 'DELETE') return new Response(null, { status: 204 })
    if (String(url).includes('/content')) return new Response('raw')
    return new Response(JSON.stringify(String(url).includes('/tasks/') ? [material] : material))
  })
  await api.get('m/1'); await api.list('task/1'); await api.retry('m/1'); await api.remove('m/1')
  assert.equal(await (await api.content('m/1', false, new AbortController().signal)).text(), 'raw')
  assert.equal(calls[0].url, '/api/overseas/v1/materials/m%2F1')
  assert.equal(calls[1].url, '/api/overseas/v1/tasks/task%2F1/materials')
  for (const { options } of calls) assert.equal(options?.credentials, 'include')
  for (const index of [2, 3]) assert.equal((calls[index].options?.headers as Record<string, string>)['X-HX-Request'], '1')
  assert.equal(calls[4].options?.cache, 'no-store')
  assert.equal(calls[4].url, '/api/overseas/v1/materials/m%2F1/content?download=false')
})
test('创建携带资料且补充提交携带版本与稳定幂等key', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createTasksApi(async (url, options) => { calls.push({ url: String(url), options }); return new Response('{}') })
  await assert.rejects(api.create({ ...emptyTaskDraft(), materialIds: ['m1'] }, 'create'))
  await assert.rejects(api.submitMaterials('t/1', ['m1'], 3, 'stable'))
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)).materialIds, ['m1'])
  assert.equal(calls[1].url, '/api/overseas/v1/tasks/t%2F1/materials')
  assert.deepEqual(JSON.parse(String(calls[1].options?.body)), { materialIds: ['m1'], version: 3 })
  assert.equal((calls[1].options?.headers as Record<string, string>)['Idempotency-Key'], 'stable')
})

test('XHR进度来自实际事件，取消和错误不产生可提交记录', async () => {
  const signal = new AbortController(), progress: number[] = [], headers: Record<string, string> = {}
  let xhr: XMLHttpRequest
  const factory = () => {
    xhr = { upload: {}, open() {}, setRequestHeader(key: string, value: string) { headers[key] = value }, send(body: FormData) { assert.equal(body.get('file') instanceof File, true) }, abort() { this.onabort?.(new ProgressEvent('abort')) } } as XMLHttpRequest
    return xhr
  }
  const api = createMaterialsApi(fetch, factory), pending = api.upload(new File(['a,b'], 'a.csv'), 'competitor', n => progress.push(n), signal.signal)
  assert.equal(xhr!.withCredentials, true); assert.equal(headers['X-HX-Request'], '1'); assert.equal(headers['Content-Type'], undefined)
  xhr!.upload.onprogress!.call(xhr!.upload, { lengthComputable: true, loaded: 5, total: 10 } as ProgressEvent)
  assert.deepEqual(progress, [50])
  // Node没有浏览器ProgressEvent；模拟xhr取消回调。
  xhr!.abort = () => xhr!.onabort!.call(xhr!, {} as ProgressEvent)
  signal.abort(); await assert.rejects(pending, /取消/)
  const aborted = new AbortController(); aborted.abort()
  await assert.rejects(api.upload(new File(['a'], 'a.csv'), 'competitor', () => {}, aborted.signal), /取消/)
})

test('身份请求默认10秒保持兼容，资料重试使用120秒解析预算', async () => {
  const { createIdentityRequest } = await import('../src/api/identity/request')
  const original = AbortSignal.timeout, durations: number[] = []
  AbortSignal.timeout = (milliseconds: number) => { durations.push(milliseconds); return new AbortController().signal }
  try {
    await createIdentityRequest(async () => new Response('{}'))('/api/check', (v): v is object => typeof v === 'object')
    await createMaterialsApi(async () => new Response(JSON.stringify(material))).retry('m1')
    assert.deepEqual(durations, [10000, 120000])
  } finally { AbortSignal.timeout = original }
})
