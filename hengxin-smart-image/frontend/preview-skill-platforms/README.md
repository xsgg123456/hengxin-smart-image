# Skill平台分组独立预览

仅供方案确认，不作为正式需求；不接API、不发布、不改Skill文件。复用实际OverseasShell、ArtTable、OverseasSkillCatalog基准页、StudioSessionList、StudioTurns、StudioMaterials、StudioSkillSelect、StudioTextEditor及原样式。

范围：六个既有平台；一Skill多平台；搜索/状态筛选/批量覆盖归属/添加和移出平台；全局开关；工作台按任务平台与开关过滤；无匹配项；失效选择清空且保留输入。平台归属和开关为示例，内存保存，刷新重置。未实现平台字典增删改。

运行（frontend目录）：`pnpm exec vite --config preview-skill-platforms/vite.config.ts --mode demo`

入口：http://127.0.0.1:3036/preview-skill-platforms/index.html#/overseas/admin/skills

检查：`pnpm exec vue-tsc --noEmit -p preview-skill-platforms/tsconfig.json`

验收：同视口对照现有页面；单项及批量编辑、多平台添加/移除、空分组与筛选、工作台Amazon/Wayfair/Shopee、窄屏滚动可达。不进行真实生图。

补充预览：工作台 Skill 下拉仅显示名称，选中后仍可主动查看说明；取回文件弹窗按文件名或路径即时模糊搜索（忽略英文大小写），清空恢复列表，筛选保留已选项，显示无匹配提示。使用本地示例文件，不读取或取回生产文件。
