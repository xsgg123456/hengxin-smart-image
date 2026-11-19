import { isNewProductKey, workspaceKeys, type WorkspaceKey } from '../shared/domestic-workspace-keys'

const definitions: Record<WorkspaceKey, { title: string; path: string; description: string }> = {
  general: { title: '新品通用生成', path: '/new-product/general', description: '上传任意品类的产品图片和资料，说明想生成什么效果。' },
  camera: { title: '相机配件生成', path: '/new-product/camera-accessories', description: '上传相机配件图片和资料，说说你想生成什么。' },
  case: { title: '手机壳生成', path: '/new-product/phone-case', description: '上传手机壳图片和资料，说说你想呈现的效果。' },
  film: { title: '所有膜生成', path: '/new-product/screen-protector', description: '上传膜类产品的图片和资料，说明需要呈现的效果。' },
  cable: { title: '数据线生成', path: '/new-product/data-cable', description: '上传数据线图片和资料，说明需要呈现的效果。' },
  earbud: { title: '耳机保护套生成', path: '/new-product/earbud-case', description: '上传耳机保护套图片和资料，说明需要呈现的效果。' },
  accessory: { title: '创意配件生成 (手机挂绳/防水袋/手机支架/平板支架)', path: '/new-product/creative-accessories', description: '上传创意配件图片和资料，说明需要呈现的效果。' },
  product: { title: '只换产品', path: '/product-replace/product-only', description: '替换图中的产品，保留原来的场景、构图和文字。' },
  scene: { title: '换场景 / 模特 / 产品 / 修改尺寸', path: '/product-replace/scene-model-product-size', description: '按需更换场景、模特或产品，也可以调整图片尺寸。' },
  phone: { title: '换手机 / 壁纸 / 膜', path: '/product-replace/phone-wallpaper-film', description: '替换图中的手机、屏幕壁纸或保护膜，按需选择修改内容。' },
  edit: { title: '通用修改产品图片', path: '/product-replace/general-edit', description: '上传待修改的产品图片，说明需要调整的内容。' },
}

export const domesticWorkspaces = workspaceKeys.map(key => ({
  key, group: isNewProductKey(key) ? '新品生成' : '产品替换', ...definitions[key]
}))
export const archiveWorkspaces = domesticWorkspaces.filter(item => isNewProductKey(item.key))
export const workspaceTitle = (key: WorkspaceKey) => definitions[key].title
