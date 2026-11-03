import type { DraftFields, Requirement } from '@/api/overseas/requirement-drafts'
import { OVERSEAS_PLATFORMS } from './platforms'
import { OVERSEAS_LANGUAGES } from './languages'
export function mapRequirement(current: DraftFields, source: Requirement) {
  const fields: DraftFields = { ...current, skus: current.skus.map(s => ({ ...s })) }, warnings: string[] = []
  const mappings = [
    ['platform', '目标平台', source.platformName, OVERSEAS_PLATFORMS.find(p => p.label === source.platformName || p.value === source.platformName)?.value],
    ['brand', '品牌', source.brandName, ['OUTON', 'OUTONLIFE', 'BELEEV'].find(b => b === source.brandName)],
    ['language', '语言', source.language, OVERSEAS_LANGUAGES.find(l => l.label === source.language || l.value === source.language)?.value]
  ] as const
  for (const [key, label, value, mapped] of mappings) {
    if (mapped) fields[key] = mapped
    else warnings.push(`${label}：${value ? `「${value}」无法匹配` : '上游未填写'}，请手动核对。`)
  }
  for (const [key, label, value] of [['name', '任务名称', source.title], ['productName', '品名', source.productName]] as const) {
    if (value?.trim() && value.length <= 80) fields[key] = value
    else warnings.push(`${label}：${value ? '内容超过 80 字' : '上游未填写'}，请手动补充。`)
  }
  if (source.matchedDesigner) fields.designerId = source.matchedDesigner.id
  else warnings.push(`负责设计：「${source.designerName || '未填写'}」无法唯一匹配，请手动选择。`)
  return { fields, warnings }
}
