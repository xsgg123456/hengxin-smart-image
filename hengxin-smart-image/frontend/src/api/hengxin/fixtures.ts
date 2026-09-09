import type { Mode, Picture, Workspace } from '../../types/hengxin'
export const MOCK_USER_ID = 'mock-operator'
export const skillNames: Record<Mode, string> = { wallpaper: '壁纸替换 Skill', product: '商品替换 Skill', text: '文字替换 Skill' }
export const sampleImages = (mode: Mode, count = 8): Picture[] => Array.from({ length: count }, (_, i) => ({
  name: `主图 ${String(i + 1).padStart(2, '0')}`, url: `/samples/${mode}-${i % 4}.svg`, version: 1
}))
export function createFixtures(): Workspace {
  const templates = [
    { id: 't1', name: '极简光影 · 手机屏幕套图', mode: 'wallpaper' as const, count: 8 },
    { id: 't2', name: '暮色山川 · 质感展示', mode: 'wallpaper' as const, count: 6 },
    { id: 't3', name: '原色轻透 · 钢化膜系列', mode: 'product' as const, count: 8 },
    { id: 't4', name: '桌面好物 · 产品展示', mode: 'product' as const, count: 4 }
  ].map(t => ({ id: t.id, name: t.name, mode: t.mode, images: sampleImages(t.mode, t.count),
    skill: skillNames[t.mode], active: true, version: 1, ownerId: MOCK_USER_ID }))
  return {
    templates,
    tasks: (['wallpaper', 'product', 'text'] as const).map((mode, i) => ({
      id: `HX0908-00${i + 1}`, name: ['秋日山川 · 手机屏幕系列', '高清钢化膜 · 商品主图', '新品上市 · 文案更新'][i],
      mode, template: templates[i === 1 ? 2 : 0].name, skillVersionId: `mock-${mode}-1`,
      ownerId: MOCK_USER_ID, sessionId: null, currentRoundId: `mock-round-${i}`,
      state: i === 2 ? '失败' : '待查看', progress: i === 2 ? 0 : 100,
      images: sampleImages(mode, i === 2 ? 4 : 8), sources: [], feedback: [],
      time: '2026-09-09T02:32:00.000Z', archived: false
    })),
    archives: [{ id: 'a0', name: '初秋上新 · 屏幕展示套图', mode: 'wallpaper',
      images: sampleImages('wallpaper'), time: '2026-09-07T08:24:00.000Z', ownerId: MOCK_USER_ID, imageVersionIds: [] }]
  }
}
