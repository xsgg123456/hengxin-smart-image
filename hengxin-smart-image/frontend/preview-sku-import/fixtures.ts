export interface SourceFile { id: string; filename: string; size: number }
export interface Requirement {
  id: string; platformName: string; brandName: string; title: string; productName: string
  language: string; designerName: string; status: string; createdAt: string; files: SourceFile[]
}
export interface PreviewFile extends SourceFile {
  kind: 'requirement' | 'competitor'; state: 'importing' | 'ready' | 'failed'; progress: number; local?: File
}
export const designers = ['刘滴', '周仁平', '黄湘婷', '姚锐娟', '张帅']
const file = (id: string, filename: string, size = 988361): SourceFile => ({ id, filename, size })
const base: Requirement = {
  id: 'R-ASSK', platformName: '亚马逊/Amazon', brandName: 'OUTON', title: '张帅测试', productName: '灯具',
  language: '英语', designerName: '刘滴', status: '待开始', createdAt: '2026-11-03',
  files: [file('ATT6166ACEB656A', 'F49D1625E_V1副图A+需求优化.pptx')],
}
// 已核验字段的静态快照，仅供独立交互预览；不携带密钥或下载签名。
export const fixtures: Record<string, Requirement[]> = {
  ASSK: [base],
  'SP-XLLHBC01-BT': [{ ...base, id: 'R20F7D8A6D0', platformName: 'BELEEV', brandName: 'BELEEV', title: 'V1老品副图优化 共12张', productName: '', language: '', designerName: '周仁平', files: [file('ATTC9692E42B926', 'V1副图A+需求优化.pptx')] }],
  'H-ZGD000901-US-G': [
    { ...base, id: 'RB74E9542BD', platformName: 'OUTON', brandName: '多平台', title: '直杆布罩灯-摇臂款-12W三段亮度灯泡-美规-电镀金色H-ZGD000901-US-G', productName: '', language: '', designerName: '黄湘婷', createdAt: '2026-10-31', files: [file('ATT9A5D90AA5B48', '直杆布罩灯-摇臂款-12W三段亮度灯泡-美规-电镀金色H-ZGD000901-US-G.pptx', 15047024)] },
    { ...base, id: 'RF16CBC9F73', platformName: 'OUTON', brandName: '多平台', title: '直杆布罩灯-摇臂款-12W三段亮度灯泡-美规-电镀金色', productName: '', language: '', designerName: '姚锐娟', status: '已完成', createdAt: '2026-09-22', files: [file('ATT94F62AE089F6', '直杆布罩灯-摇臂款-12W三段亮度灯泡-美规-电镀金色.pptx', 6482787)] },
    { ...base, id: 'REC06DB290A', platformName: 'OUTON', brandName: 'Outon/OUTONLIFE', title: '直杆布罩灯-摇臂款-12W三段亮度灯泡-美观-电镀金色', productName: '', language: '', designerName: '姚锐娟', status: '已完成', createdAt: '2026-09-11', files: [file('ATT7C72AADE9648', 'FF0973048_F65F071E2_直杆布罩灯-图需-260904修改.pptx', 60894980)] },
  ],
  'DEMO-MULTI': [{ ...base, id: 'DEMO-MULTI', title: '落地灯主图及 A+ 设计需求（多附件演示）', files: [file('demo-ppt1', '落地灯主图需求.pptx'), file('demo-ppt2', 'A+页面补充说明.PPT'), file('demo-xlsx', '竞品分析.xlsx', 245760), file('demo-pdf', '产品规格与参考.pdf', 1258291)] }],
  'DEMO-FAIL': [{ ...base, id: 'DEMO-FAIL', title: '附件失败与重试演示', files: [file('demo-ok', '图片需求.pptx'), file('demo-fail', '竞品分析.xlsx', 245760)] }],
}
export const scenarios = [
  { sku: 'ASSK', label: 'ASSK · 单条正常回填' },
  { sku: 'H-ZGD000901-US-G', label: 'H-ZGD000901-US-G · 多条选择' },
  { sku: 'SP-XLLHBC01-BT', label: 'SP-XLLHBC01-BT · 缺失与异常字段' },
  { sku: 'DEMO-MULTI', label: 'DEMO-MULTI · 多附件分类' },
  { sku: 'DEMO-FAIL', label: 'DEMO-FAIL · 附件失败与重试' },
  { sku: 'DEMO-EMPTY', label: 'DEMO-EMPTY · 没有结果' },
  { sku: 'DEMO-ERROR', label: 'DEMO-ERROR · 查询失败' },
]
export const pause = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))
