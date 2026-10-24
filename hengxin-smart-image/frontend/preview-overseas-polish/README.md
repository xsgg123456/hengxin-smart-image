# 海外三项小优化 · 待确认交互预览

本轮仅独立预览，不改正式需求、生产组件或数据。

1. 目标站点标签去掉语言。
2. 六平台依次显示亚马逊/Amazon、美客多/Mercado Libre、沃尔玛/Walmart、家得宝/The Home Depot、虾皮/Shopee、威费尔/Wayfair。
3. 输入区严格保持正式工作台两行高度，不自动增高，不加文字标题行；仅在现有发送工具栏中增加“展开编辑”。弹窗内查看和编辑完整文字、Enter换行，完成/Escape关闭保留内容。

2026-10-24用户纠正：废弃基于旧preview-studio-sessions拼装及6行增高方案。StudioPreview.vue以当前src/views/overseas/studio/OverseasStudio.vue为直接快照；引用全部正式子组件、studio.css、studio-sessions.css及高度计算。仅替换API为本地示例、增加弹窗入口和用于对照的baseline开关。无旧预览样式覆盖。素材和图片是示例，不声称与线上业务内容相同。

验收：同窗口、同内容、同展开状态切换“对照原版”，工作台、会话列、素材列、输入框、输入区的矩形尺寸保持一致；短文及长文输入区高度相同；正常与展开工作台两种状态都验证。弹窗关闭保留草稿，独立构建和类型检查通过。

运行：frontend下 node node_modules/vite/bin/vite.js --config preview-overseas-polish/vite.config.ts --mode demo
地址：http://127.0.0.1:3032/preview-overseas-polish/index.html
