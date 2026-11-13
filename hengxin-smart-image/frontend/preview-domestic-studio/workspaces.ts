export type WorkspaceId = 'camera' | 'case' | 'product' | 'scene' | 'phone'
export type WorkspaceConfig = {
  id: WorkspaceId; group: 'new' | 'replace'; path: string; title: string
  description: string; welcome: string; guidance: string
  primaryRole: string; primaryTitle: string; primaryHint: string
  secondaryRole: string; secondaryTitle: string; secondaryHint: string
  example: string; placeholder: string; reply: string
}
export const workspaces: WorkspaceConfig[] = [
  {
    id: 'camera', group: 'new', path: '/new-product/camera-accessories', title: '相机配件生成',
    description: '上传相机配件图片和资料，说说你想生成什么。',
    welcome: '为你的相机配件，制作产品图片', guidance: '添加产品实拍、卖点或图需资料，告诉我想要的风格和用途。',
    primaryRole: '相机配件资料', primaryTitle: '上传相机配件资料', primaryHint: '产品实拍、适用机型、功能卖点',
    secondaryRole: '效果参考', secondaryTitle: '添加效果参考', secondaryHint: '风格、构图或场景参考 · 可选',
    example: '根据这款相机手柄的实拍，制作一组突出安装方式和握持体验的产品图。',
    placeholder: '描述相机配件的出图要求，或继续提出修改意见…',
    reply: '我会结合相机配件实拍、适用机型和你的要求开展图片设计。',
  },
  {
    id: 'case', group: 'new', path: '/new-product/phone-case', title: '手机壳生成',
    description: '上传手机壳图片和资料，说说你想呈现的效果。',
    welcome: '让手机壳的设计与细节，更好地呈现', guidance: '添加手机壳实拍和适用机型，告诉我需要什么样的产品图片。',
    primaryRole: '手机壳资料', primaryTitle: '上传手机壳资料', primaryHint: '产品实拍、适用机型、材质卖点',
    secondaryRole: '效果参考', secondaryTitle: '添加效果参考', secondaryHint: '风格、构图或场景参考 · 可选',
    example: '根据这款手机壳的实拍，制作一组突出材质、镜头保护和握持效果的产品图。',
    placeholder: '描述手机壳的出图要求，例如材质、配色、场景和展示重点…',
    reply: '我会结合手机壳实拍、适用机型及材质特点，按你的要求开展图片设计。',
  },
  {
    id: 'product', group: 'replace', path: '/product-replace/product-only', title: '只换产品',
    description: '替换图中的产品，保留原来的场景、构图和文字。',
    welcome: '只换产品，其余保持原样', guidance: '添加待替换原图与新产品素材，并说明需要替换的对象。',
    primaryRole: '待替换原图', primaryTitle: '上传待替换原图', primaryHint: '需要替换产品的原始图片',
    secondaryRole: '新产品素材', secondaryTitle: '上传新产品素材', secondaryHint: '用于替换的新产品实拍',
    example: '把原图中的产品换成新款，保留背景、模特、文字和整体构图。',
    placeholder: '说明要替换的产品，例如：把黑色手机壳换成素材中的白色款…',
    reply: '我会以原图为基础替换指定产品，并保留原来的背景、模特、文字和构图。',
  },
  {
    id: 'scene', group: 'replace', path: '/product-replace/scene-model-product-size', title: '换场景 / 模特 / 产品 / 修改尺寸',
    description: '按需更换场景、模特或产品，也可以调整图片尺寸。',
    welcome: '场景、模特、产品和尺寸，按你的要求调整', guidance: '上传原图，说明这次要改哪些部分、保留哪些内容；改尺寸时写明目标宽高。',
    primaryRole: '待修改原图', primaryTitle: '上传待修改原图', primaryHint: '需要调整的产品图或场景图',
    secondaryRole: '替换素材与参考', secondaryTitle: '添加素材与参考', secondaryHint: '场景、模特或产品素材 · 按需',
    example: '把背景换成明亮的客厅，保留产品，图片调整为 1500 × 1500 像素。',
    placeholder: '说明要更换的场景、模特、产品，或目标尺寸；不需要全部修改…',
    reply: '我会只处理你明确提出的场景、模特、产品或尺寸调整，其余内容按要求保留。',
  },
  {
    id: 'phone', group: 'replace', path: '/product-replace/phone-wallpaper-film', title: '换手机 / 壁纸 / 膜',
    description: '替换图中的手机、屏幕壁纸或保护膜，按需选择修改内容。',
    welcome: '手机、壁纸或保护膜，换成你需要的效果', guidance: '添加原图和对应素材，说清楚这次换什么，以及需要保留的部分。',
    primaryRole: '待修改原图', primaryTitle: '上传待修改原图', primaryHint: '含手机、屏幕或保护膜的原图',
    secondaryRole: '手机 / 壁纸 / 膜素材', secondaryTitle: '上传替换素材', secondaryHint: '手机、壁纸或保护膜参考图片',
    example: '只把手机屏幕壁纸换成参考图，保留手机、保护膜、反光和其他内容。',
    placeholder: '说明要换手机、壁纸还是膜，以及对应的素材和保留要求…',
    reply: '我会按你的要求处理手机、屏幕壁纸或保护膜，并保留指定的其他内容。',
  },
]
