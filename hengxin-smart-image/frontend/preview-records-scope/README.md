# 国内换图记录 · 独立交互预览

用户仅授权预览，待确认方案不写入正式 Spec、设计规范或开发计划。

1. 复用正式 Art 侧栏、页头、工作标签、内容容器、ArtTable、PicturePreview、prototype.css 和 Element Plus 主题；完成标准为与正式记录模板同视口对照。
2. 默认我的任务；全部任务内按创建人搜索选择；状态、时间、任务名称/编号联合筛选，筛选后回第1页。统计覆盖所有匹配记录，分页不改变统计。完成标准为浏览器实际操作验证。
3. 详情关闭及列表刷新保留筛选/页码；重新进入菜单默认我的任务；重置清空筛选但保留当前我的/全部范围。提供有数据、空结果、加载及模拟错误场景。
4. 独立入口、内存示例任务、无业务 API 代理；删除仅作用于示例且需确认；新建等非本轮入口明确提示。类型检查、独立构建、浏览器验证及独立审查后提供本地链接。

演示身份为“张三”，示例日期固定为2026-10-22；“今天/近7天/近30天”围绕该日演示，不冒充生产记录。详情只预览示例图片，不模拟真实生图。

运行：在 frontend 执行 `pnpm exec vite --config preview-records-scope/vite.config.ts --mode demo`，打开 http://127.0.0.1:3026/preview-records-scope/index.html#/api-image-edits/records 。

基准入口：同页面 URL 添加 `?baseline=1`（位于 # 前），用于复用正式 RealRecords.vue 模板的对照。构建：`pnpm exec vite build --config preview-records-scope/vite.config.ts --mode demo`。类型检查：`pnpm exec vue-tsc --noEmit -p preview-records-scope/tsconfig.json`。
