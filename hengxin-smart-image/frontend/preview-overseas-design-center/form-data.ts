export type MaterialKind = 'requirement' | 'competitor'
export interface FormMaterial {
  name: string
  kind: MaterialKind
  source: 'sample' | 'local'
  file?: File
}

export interface CreateSubmission {
  sku: string
  title: string
  productName: string
  brand: string
  platform: string
  language: string
  designer: string
  materials: FormMaterial[]
}

export const sample = {
  sku: 'GN-0008',
  name: 'OUTON 落地灯产品套图',
  productName: 'OUTON 落地灯',
  brand: 'OUTON',
  language: 'en',
  materials: [
    { name: 'GN-0008 落地灯图片需求.pptx', kind: 'requirement', source: 'sample' },
    { name: 'GN-0008 竞品分析.xlsx', kind: 'competitor', source: 'sample' },
  ] as FormMaterial[],
}
