# 业务表格空状态裁切修复

2026-09-09，用户截图指出任务中心表格空状态被裁切。此前Phase8视觉验收漏检，该结论不能覆盖此缺陷。

计划：先复现并测量空状态与滚动容器高度；修复业务卡片中的表格高度配置，保留既有设计和真实数据；验证1920及1024宽度下空状态插图、说明、分页完整可见，并检查有数据和加载状态；运行前端回归、类型检查和构建，再独立审查。

完成标准：不靠伪造任务填满表格；空状态图文完整位于表格可见区域，有数据正常展示、分页不重叠。真实开发库仅只读检查。

已证实根因：1920×911下表体/滚动容器仅60px，而ElEmpty实际290.625px，说明文字位于裁切区域之外。使用ArtTable现有height/emptyHeight/showTableHeader配置，业务卡片和抽屉采用自然行高、340px空表格高度，不套用全高页面工具栏偏移。任务中心、成员、Skill、调用统计及明细、执行监控两表、配置审计共8处用法同步；不改全局Art组件默认行为。

验证：`table-layout-regression.js` 浏览器输出 `TABLE LAYOUT PASS`，1920/1024下空态表体300px、插图区域290.625px完全包含，分页不重叠；两宽度下加载可见、有数据两行均完整；Skill管理邻居空态同样通过。有数据/管理身份仅在独立浏览器GET响应中模拟，不写开发库；统计明细抽屉本次仅静态核对相同配置，不宣称逐页实测。

前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`：51通过、0失败；`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`退出0；`node node_modules/vite/bin/vite.js build`退出0、37.45秒。日志：`output/table-layout-{browser,tests,build}.log`；真实空态截图：`output/playwright/table-layout-empty-{1920,1024}.png`。审查见TABLE-LAYOUT-REVIEW.md。本次修正此前Phase8视觉验收漏检，不影响其后端队列测试结果。
