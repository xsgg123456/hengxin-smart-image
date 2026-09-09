import { computed, onBeforeUnmount, ref, toRaw, watch, type Ref } from 'vue'
import { getExamplePictures, uploadFile } from '@/api/files'
import { IMAGE_MIME_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from '@/api/hengxin/limits'
import type { Mode, Picture } from '@/types/hengxin'

interface UploadEntry {
  id: number
  name: string
  url: string
  localUrl?: string
  file?: File
  picture?: Picture
  state: 'checking' | 'uploading' | 'failed' | 'ready'
  error: string
}
interface UploadOptions {
  mode: Mode
  disabled?: boolean
  exampleCount?: number
}

export function useImageUpload(model: Ref<Picture[]>, props: UploadOptions) {
  let sequence = 0
  let generation = 0
  let alive = true
  let published: Picture[] | undefined
  const entries = ref<UploadEntry[]>([])
  const error = ref('')
  const examplesLoading = ref(false)
  const blocked = computed(() => examplesLoading.value || entries.value.some(e => e.state !== 'ready'))
  const pictures = () => entries.value.flatMap(e => e.picture ? [e.picture] : [])
  const release = (entry: UploadEntry) => {
    if (entry.localUrl) URL.revokeObjectURL(entry.localUrl)
    entry.localUrl = undefined
  }
  function reset(value: Picture[]) {
    generation++
    entries.value.forEach(release)
    entries.value = value.map(picture => ({
      id: ++sequence, name: picture.name, url: picture.url, picture, state: 'ready', error: ''
    }))
    examplesLoading.value = false
    error.value = ''
  }
  function publish() {
    published = pictures()
    model.value = published
  }
  watch(model, value => {
    if (toRaw(value) !== published) reset(value)
  }, { flush: 'sync' })
  reset(model.value)
  watch(() => props.mode, () => reset(model.value), { flush: 'sync' })
  onBeforeUnmount(() => {
    alive = false
    generation++
    entries.value.forEach(release)
  })
  const current = (id: number) => alive ? entries.value.find(e => e.id === id) : undefined

  async function receive(id: number) {
    const entry = current(id)
    if (!entry?.file) return
    entry.state = 'checking'
    entry.error = ''
    try {
      const image = new Image()
      image.src = entry.url
      await image.decode()
      if (!image.naturalWidth || !image.naturalHeight) throw new Error('无法解码图片')
      if (!current(id)) return
      entry.state = 'uploading'
      const picture = await uploadFile(entry.file)
      if (!current(id)) return
      entry.picture = picture
      entry.url = picture.url
      entry.state = 'ready'
      release(entry)
      publish()
    } catch (cause) {
      if (!current(id)) return
      entry.error = entry.state === 'checking'
        ? '无法解码图片，请选择完整的 JPG、PNG 或 WebP 文件'
        : cause instanceof Error ? cause.message : '接收失败，请重试'
      entry.state = 'failed'
    }
  }
  async function add(file: File) {
    if (props.disabled || examplesLoading.value) return
    const reason = entries.value.length >= MAX_IMAGES ? '每组最多 20 张，请移除图片后再添加'
      : !file.size ? '文件为空，请选择有内容的图片'
        : file.size > MAX_IMAGE_BYTES ? '单张图片不能超过 10 MiB'
          : !IMAGE_MIME_TYPES.includes(file.type)
            ? '仅支持 JPG、PNG、WebP 图片' : ''
    if (reason) { error.value = `${file.name}：${reason}`; return }
    const id = ++sequence
    const url = URL.createObjectURL(file)
    entries.value.push({ id, name: file.name, url, localUrl: url, file, state: 'checking', error: '' })
    await receive(id)
  }
  function remove(id: number) {
    if (props.disabled) return
    const entry = current(id)
    if (!entry) return
    generation++
    examplesLoading.value = false
    release(entry)
    entries.value = entries.value.filter(e => e.id !== id)
    publish()
  }
  function move(index: number, direction: number) {
    if (props.disabled || examplesLoading.value) return
    const target = index + direction
    if (target < 0 || target >= entries.value.length) return
    ;[entries.value[index], entries.value[target]] = [entries.value[target], entries.value[index]]
    publish()
  }
  async function retry(id: number) {
    if (props.disabled || examplesLoading.value || current(id)?.state !== 'failed') return
    await receive(id)
  }
  async function useExamples() {
    if (props.disabled || examplesLoading.value) return false
    const count = props.exampleCount ?? (props.mode === 'text' ? 2 : 1)
    if (!Number.isInteger(count) || count < 1 || count > MAX_IMAGES) {
      error.value = '示例图片数量必须为 1 至 20 张'
      return false
    }
    const token = ++generation
    examplesLoading.value = true
    error.value = ''
    try {
      const result = await getExamplePictures(props.mode, count)
      if (!alive || token !== generation) return false
      if (!result.length || result.length > MAX_IMAGES) throw new Error('示例图片数量不符合 1 至 20 张限制')
      reset(result)
      publish()
      return true
    } catch (cause) {
      if (alive && token === generation) error.value = cause instanceof Error ? cause.message : '示例加载失败，请重试'
      return false
    } finally {
      if (alive && token === generation) examplesLoading.value = false
    }
  }
  return { entries, error, blocked, examplesLoading, add, remove, move, retry, useExamples }
}
