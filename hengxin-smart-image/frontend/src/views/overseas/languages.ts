export const OVERSEAS_LANGUAGES = [
  { value: 'en', label: '英语' },
  { value: 'de', label: '德语' },
  { value: 'fr', label: '法语' },
  { value: 'es', label: '西班牙语' }
] as const

export function languageLabel(value?: string | null) {
  return OVERSEAS_LANGUAGES.find(option => option.value === value)?.label || '未设置'
}

export function validateLanguage(value: unknown) {
  if (!OVERSEAS_LANGUAGES.some(option => option.value === value)) throw Error('请选择语言（英语、德语、法语或西班牙语）')
}
