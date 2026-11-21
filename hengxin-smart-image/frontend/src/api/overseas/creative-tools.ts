export const CREATIVE_TOOLS = [
  { value: 'outon', label: '亚马逊生图(OUTON)', platform: 'Amazon', brand: 'OUTON' },
  { value: 'outonlife', label: '亚马逊生图(OUTONLIFE)', platform: 'Amazon', brand: 'OUTONLIFE' },
  { value: 'beleev', label: '亚马逊生图(BELEEV)', platform: 'Amazon', brand: 'BELEEV' },
  { value: 'wayfair', label: 'Wayfair生图', platform: 'Wayfair', brand: '' },
  { value: 'walmart', label: '沃尔玛生图', platform: 'Walmart', brand: '' },
  { value: 'home-depot', label: 'The Home Depot生图', platform: 'The Home Depot', brand: '' },
  { value: 'mercado-libre', label: '美客多生图', platform: 'Mercado Libre', brand: '' },
  { value: 'custom-size', label: '其他平台(自定义尺寸)', platform: '', brand: '' },
] as const
export type CreativeTool = typeof CREATIVE_TOOLS[number]
export type CreativeToolKey = CreativeTool['value']
export type CreativeTaskDraft =
  | { toolKey: Exclude<CreativeToolKey, 'custom-size'>; productName: string; sku: string; language: string }
  | { toolKey: 'custom-size'; productNameSku: string }
