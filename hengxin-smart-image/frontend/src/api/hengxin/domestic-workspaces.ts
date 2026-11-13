import type { WorkspaceKey } from './domestic-studio-skills'

export const domesticWorkspaces: { key: WorkspaceKey; group: string; title: string; path: string; description: string }[] = [
  { key: 'camera', group: '新品生成', title: '相机配件生成', path: '/new-product/camera-accessories', description: '上传相机配件图片和资料，说说你想生成什么。' },
  { key: 'case', group: '新品生成', title: '手机壳生成', path: '/new-product/phone-case', description: '上传手机壳图片和资料，说说你想呈现的效果。' },
  { key: 'product', group: '产品替换', title: '只换产品', path: '/product-replace/product-only', description: '替换图中的产品，保留原来的场景、构图和文字。' },
  { key: 'scene', group: '产品替换', title: '换场景 / 模特 / 产品 / 修改尺寸', path: '/product-replace/scene-model-product-size', description: '按需更换场景、模特或产品，也可以调整图片尺寸。' },
  { key: 'phone', group: '产品替换', title: '换手机 / 壁纸 / 膜', path: '/product-replace/phone-wallpaper-film', description: '替换图中的手机、屏幕壁纸或保护膜，按需选择修改内容。' },
]
