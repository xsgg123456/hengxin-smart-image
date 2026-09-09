# 表格空状态修复审查

日期：2026-09-09。审查范围仅为 `TABLE-LAYOUT-FIX.md` 的表格布局修复，不重新授予 Phase 6–8 全量通过。此前 Phase 8 视觉 PASS 漏检真实空状态裁切，不能作为本次验收证据。

## Stage 1：需求符合性（本次修复通过）

依据：`Product-Spec.md:157` 要求任务中心空状态可用，`:308` 要求异常和空状态可用；`Design-Brief.md:13`、`:55` 要求复用原 Art 组件与业务卡片；`hengxin-smart-image/docs/TABLE-LAYOUT-FIX.md:5`、`:7` 为本次完成标准。

| 检查项 | 结论与证据 |
|---|---|
| 根因定位 | 已匹配。主 Agent 修前实际测量 table=100px、body=60px、ElEmpty=290.625px，说明文字超出裁切体。`frontend/src/components/core/tables/art-table/index.vue:146` 默认空态100%；`:148` 默认预留工具栏；`frontend/src/hooks/core/useTableHeight.ts:39`、`:40`、`:72` 缺少实际工具栏仍预留44+12px。业务卡片 `frontend/src/views/hengxin/prototype.css:8` 无确定高度。 |
| 任务中心配置 | 已匹配。`frontend/src/views/hengxin/components/Tasks.vue:13` 显式自然高度、340px空态、关闭工具栏预留。`art-table/index.vue:236` 优先空态高度，`:238` 其次业务高度，`:142` 保留真实列头。关闭的是 ArtTableHeader 预留，不是表格列名。 |
| 同根因用法覆盖 | 代码已完整覆盖8处。任务`:13`；`admin/users.vue:7`；`admin/skills.vue:5`；`admin/settings.vue:12`；`admin/usage.vue:18`、`:24`；`admin/monitor.vue:11`、`:14`，全部使用相同三个现有 props。后7处原先同样缺少定高与实际工具栏，应同步。 |
| 1920×911空态 | 已匹配。主 Agent 修后测量 table=340px、body=300px、ElEmpty=290.625px；审查 Agent 独立打开 `output/playwright/table-layout-current.png`，插图、说明及分页均完整，列头保留。 |
| 1024空态、有数据、加载态 | 已匹配。`output/table-layout-browser.log:1`：两宽空态均body=300、empty=290.625、contained=true、paginationClear=true；两宽loading均visible=true，两宽各2条数据行contained=true。`scripts/phase8/table-layout-regression.js:11`、`:44` 同时断言分页不重叠。审查 Agent 独立查看空态1024、数据1920/1024截图。 |
| 邻居卡片与明细抽屉 | Skill 邻居卡片实际验证body=300、empty=290.625、contained=true，审查 Agent 查看 `output/playwright/table-layout-skills-neighbor.png`。调用明细抽屉仅静态核对 `admin/usage.vue:24`，未单独浏览器实测；不得将本报告扩展为8处所有状态全量实测。 |
| 不伪造任务填表 | 本次布局变更只增加组件 props，数据仍来自 `Tasks.vue:37` 的 useTaskList。测试来源标签是既有 Phase 8 变更，不归入本次修复。 |
| Spec 漂移 | 本次配置未增加页面、数据模型或接口；保留原空态文案、列、分页和组件。证据为上述8处调用及 `Tasks.vue:21`。 |

## Stage 2：代码质量（本次变更通过）

- 配置适配：复用现有3个props，无新类型、全局样式、算法或错误处理分支；变更落在上表8处调用，组件逻辑 `art-table/index.vue:232` 不变。没有本次新增 any 或大文件问题；现有 ArtTable 的泛型 any 与文件长度不归因于此次3个props的小修。
- 安全扫描：对 Tasks.vue 与 admin 目录执行 eval、innerHTML、危险前缀变量及密钥模式扫描，无命中。本次8处仅字面量布局props，不引入网络写入或注入入口。
- 测试真实性：`scripts/phase8/table-layout-regression.js:19` 使用真实空任务列表验证两宽；`:29` 在浏览器拦截GET提供明确fixture行，先阻塞响应验证loading，再释放验证行边界。没有通过创建数据库任务掩盖空态。`:11`、`:44` 检查分页位置；并非仅比较DOM中是否存在文字。51项前端测试是回归证据，不充当布局证据。
- 视觉对比：独立查看任务空态1920/1024、数据1920/1024及Skill邻居截图，空态插图、描述、列头保留，卡片、按钮、颜色沿用原组件。Skill截图下部“没有操作权限”来自仅在浏览器模拟超管身份，而默认绑定API仍真实拒绝权限，不能当作正式超管功能验收。
- 验证边界：加载态证明遮罩出现；有数据证明2行与分页边界。未验证调用明细抽屉、其他5处表格的全部运行状态，也未验证满页12行、所有屏高和全屏模式。1024沿用原宽列横向滚动，未重新设计列宽。
- 本次阻断问题：0。此前Phase8漏检仍应保留在验收记录，不以此次通过改写历史。

## 编译结果

主 Agent 本次执行 vue-tsc，exit=0、无诊断文本；构建exit=0。独立读取 `output/table-layout-build.log:1` 和 `output/table-layout-tests.log`。以下为原始输出节选，完整构建日志保存在原路径，未复用旧 Phase 8 记录。

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3303 modules transformed.
rendering chunks...
✓ built in 37.45s
```

```text
ℹ tests 51
ℹ suites 0
ℹ pass 51
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1634.0633
```

浏览器最终原始结果：

```json
{"result":"TABLE LAYOUT PASS","measurements":[{"label":"empty-1920","bodyHeight":300,"emptyHeight":290.625,"paginationClear":true,"contained":true},{"label":"empty-1024","bodyHeight":300,"emptyHeight":290.625,"paginationClear":true,"contained":true},{"label":"loading-1920","visible":true},{"label":"data-1920","rows":2,"contained":true},{"label":"loading-1024","visible":true},{"label":"data-1024","rows":2,"contained":true},{"label":"skills-neighbor","bodyHeight":300,"emptyHeight":290.625,"paginationClear":true,"contained":true}]}
```
