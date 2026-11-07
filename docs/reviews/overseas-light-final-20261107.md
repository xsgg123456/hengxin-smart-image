# 海外轻量化独立复审 · 2026-11-07

## 结论、范围与快照

- **candidateId：** `6e209bc4c4032c560fa96623ef152c54d4787f42dac290153269fad16f085791`。
- **范围：** `Product-Spec.md:1–27`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7`、`hengxin-smart-image/frontend/preview-overseas-light/`；海外管理、任务、成品库的本轮后端与正式前端、相关测试；`scripts/release/overseas-light-{runtime,package,deploy}.py` 和发布测试。未访问生产，最终包和生产切换未在本次独立审查中运行。
- **Stage 1：FAIL。** 一项 MEDIUM 的视觉和窄屏不一致，见 S1-01；未发现 HIGH。**Stage 2：未完成，不得登记 PASS。** 修复后重固定快照，从 Stage 1 重审。
- 审查开始及报告写入前 `review-status` 的 `currentId` 均等于上述 candidateId，`approved: false`；业务代码快照未变。本报告只针对该快照，普通 Markdown 报告不属于快照。审查未修改实现、提交、部署、访问生产或进行收费调用。

## Stage 1 发现

### S1-01 · MEDIUM · 日期筛选控件超宽并遮挡相邻按钮

**要求：** `Design-Brief.md:3` 要求桌面按确认预览对齐、1280px 筛选换行、390px 控件可到达且不裁切；`Product-Spec.md:11,25` 要求日期筛选及窄屏验收。

**实际：** `hengxin-smart-image/frontend/src/views/overseas/admin/OverseasActivityPage.vue:101–103` 为日期父容器设 300px，试图设置日期控件为 100%，但浏览器计算的实际宽度为 350px；确认预览 `frontend/preview-overseas-light/style.css:7` 日期控件实际宽 300px。正式控件侵入旁边重置按钮或状态筛选所在区域；390px 时超出父容器和视口。`frontend/tests/overseas-lightweight.browser.mjs:14` 的 `unclipped` 只检查内部输入与祖先裁切，未检测日期控件外框与相邻控件相交，因此该脚本 PASS 不能证明两者不重叠。

**独立复现：** 本地模拟 API，1280×900 展开侧栏，浏览器计算矩形的水平坐标：

```text
formal 1280: 日期容器 x=487..787 width=300; 日期控件 x=487..837 width=350; 重置按钮 x=801..889 width=88
formal 390:  日期容器 x=41..349 width=308; 日期控件 x=41..391 width=350
preview 1280: 日期容器 x=487..787 width=300; 日期控件 x=487..787 width=300; 重置按钮 x=801..889 width=88
```

正式控件与按钮重叠 **36px**；390px 超出父容器 **42px**、右边缘超过视口 **1px**。脚本 `output/playwright/review-light-date.mjs`；截图 `output/playwright/review-light-date-formal.png`、`output/playwright/review-light-date-preview.png`。应修正控件实际尺寸，并测试两个视口下的边界和控件间不重叠。

## Stage 1 逐条对照

以下“匹配”限定于所列证据，不代表阶段通过。以下前后端简写均相对于 `hengxin-smart-image/`。

| 需求 | 结果及证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址、权限 | 匹配。`frontend/src/identity-main.ts:22–23` 定义新路由和两个旧地址跳转；`frontend/src/views/overseas/OverseasPortal.vue:49–53` 按能力生成一个入口；`backend/app/overseas/management/router.py:13,18–35` 使用 `stats.read`。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:72` 测旧 usage 跳转。 |
| `:8` 发起次数、幂等、北京时间 | 匹配已测范围。`backend/app/overseas/studio/service.py:60–74,90–98` 将发起人与请求关联、幂等重放不建新请求；`management/usage.py:30–48` 汇总；`management/facts.py:21–38` 处理时区和开区间；`frontend/src/views/overseas/admin/OverseasActivityPage.vue:51–57` 使用北京时间自然日。`backend/tests/test_overseas_lightweight.py:16–30,53–56` 测实际发送、重放、排队取消、再发送与边界。 |
| `:9` 未知历史与数据保留边界 | 匹配。`backend/app/overseas/management/facts.py:51–53` 在权限范围外连接 Turn；`management/monitor.py:21–25` 可返回缺失操作者；`OverseasActivityPage.vue:3,27` 如实提示未知和已删除数据；`test_overseas_lightweight.py:33–69` 覆盖未知作业及权限。 |
| `:10` 人员、图片、最近时间、停用人员 | 匹配已测范围。`management/usage.py:34–48` 关联请求汇总图片和最近时间，`management/facts.py:56–59` 不排除有记录的停用成员；`test_overseas_lightweight.py:38–52` 检查计数和停用成员。图片使用隔离 fixture，不能推断真实模型生成已测试。 |
| `:11` 概况、下钻、过滤、详情与错误 | 功能路径匹配，视觉不通过 S1-01。`management/usage.py:12–16` 将收集和取消中汇总至执行中；`management/facts.py:39–47` 处理状态及任务搜索；`OverseasActivityPage.vue:59–83` 完成下钻与排队取消耗时，`:24,30` 显示记录及详情。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:74` 起覆盖下钻及详情。 |
| `:15` 归档人和关键词先于计数分页 | 匹配。`backend/app/overseas/archives/service.py:63–87` 按事件和关键词先过滤后计数分页；`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19` 显示筛选和早期参与提示；`backend/tests/test_overseas_archive_audit.py:37–46` 覆盖多人及组合条件。 |
| `:16` 停用人员、历史快照、原任务删除、删除后刷新 | 匹配已测范围。`backend/app/overseas/archives/audit.py:9–21,31–35` 保存姓名快照并标不完整；`archives/service.py:90–99` 从权限内实际事件取候选；`test_overseas_archive_audit.py:47–69` 覆盖删除源任务。`OverseasArchivePage.vue:46–50,64–67` 删除后重查候选并清除失效选择；浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:126` 起实测唯一归档删除。 |
| `:20` 实际负责人、改派与范围 | 匹配。`backend/app/overseas/tasks/queries.py:84–91,127–131` 用当前 `designer_id` 和权限过滤并保留停用负责人；`frontend/src/views/overseas/OverseasWorkspace.vue:16–25,54` 提供范围及筛选；`OverseasTasksPage.vue:149–155` 返回列表重查候选。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:92` 起实测新增负责人改派及删除后候选清除。 |
| `:21` 20 条、两处分页、分页前过滤、位置及返回 | 匹配。`tasks/queries.py:84–94,111–124` 在计数和 offset 前过滤；`OverseasTasksPage.vue:37–40,94,153–158` 保留 20 条、两处翻页、底部范围与条件重置页码；浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:86` 起测试首页、末页、空结果、返回和删除后补满。 |
| `:22` 三组状态、历史 submitted、返工和删除异常 | 匹配已测范围。`tasks/queries.py:77–80,92–94` 定义服务端三组并排除删除异常；`frontend/src/views/overseas/task-status.ts:7–29` 显示状态及下一步；`test_overseas_lightweight.py:78–105` 覆盖 `reworking`、删除异常及旧 `submitted`；浏览器脚本实测旧状态文案。 |
| `:23` 归档不自动完成，显式完成和解冻 | 匹配源码。`backend/app/overseas/studio/service.py:123–158,161–191` 分离批量归档与显式完成/解冻；未操作生产。 |
| `:25` 视觉和验收 | 未完成。S1-01 不符合确认预览；正式页面、预览和 390px 的检查使用模拟数据。最终包浏览器、安装和生产切换待主 Agent 后续验证。 |

**范围漂移：** 本范围新增 `/management/people`、`/task-assignees`、`/archive-operators` 分别对应获批需求，见 `backend/app/overseas/management/router.py:23–25`、`tasks/router.py:34–38`、`archives/router.py:28–30`；未发现额外产品页面。本结论不是全仓扫描。

**前次问题复核：** `scripts/release/overseas-light-package.py:30–65,68–104` 从固定已审 Git 提交的前端树在 `frontend/output/release-build` 临时目录编译并审计；`overseas-light-runtime.py:58–61` 切换前拒绝缺失入口及其直接引用资源。JS 动态引用完整性仍须在最终包中实测。改派、旧 submitted、排队取消、底部分页范围及删除后候选刷新见上表。

**部署与回滚静态范围：** `scripts/release/overseas-light-deploy.py:94–131,195–239` 固定 API 镜像和基线、检查 schema，关闭海外入口并排空后切换；失败时恢复前端与旧 API，就绪后开放，未确认旧 API 停止时保持关闭。`skill-reuse-gate.py:68–98` 等旧代理 worker 退出，`skill-platform-runtime.py:61–67` 比对其他容器及原生服务。发布单测为模拟，不能代替真实安装、数据与在途任务保全及回滚验证。

## 独立验证原始输出

1. 后端相关 SQLite 测试，exit 0：

```text
....................................................                     [100%]
52 passed, 2 warnings in 17.36s
```

2. `backend/tests/test_overseas_lightweight_postgres.py`，独立 PostgreSQL 17 临时容器，exit 0，容器已停止并删除：

```text
....                                                                     [100%]
4 passed, 2 warnings in 5.72s
isolated-container-cleaned 37e305eb90bc5f385445ff8458fc0daba2c90f9b9f5ca17295547200f8b7c03e
```

3. `backend/tests/test_overseas_studio_postgres.py`，另一独立 PostgreSQL 17 容器，检验现有锁和多会话并发，exit 0，容器已停止并删除：

```text
....                                                                     [100%]
4 passed, 2 warnings in 4.80s
isolated-container-cleaned 5cca7a6c3d77fae781e503afc7f3d6f8c0da51ae9d5fb57fc38919c1eef9bfe2
```

4. `scripts/release/test_overseas_light_release.py`，exit 0：

```text
...                                                                      [100%]
3 passed in 0.38s
```

5. 前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`，exit 0，原始汇总：

```text
ℹ tests 529
ℹ suites 0
ℹ pass 529
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 17293.3856
```

6. 正式及预览 `vue-tsc --noEmit` 两次 exit 0，原始 stdout/stderr 均为空。将当前候选前端复制到隔离目录后独立编译，两个子命令均退出 0、产出 692 文件；编译日志 `output/playwright/review-light-final-candidate-build.log` 首尾原文：

```text
isolated_candidate_build files= 692 vue_tsc_exit= 0 vite_exit= 0
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4826 modules transformed.
✓ built in 39.23s
```

包装脚本在打印带 emoji 的日志时遇到 Windows GBK 编码异常而 exit 1；上述编译子命令均已 exit 0，随后独立 `review-status` 仍匹配 candidateId。此隔离构建不是提交后的最终发布包。

7. 正式源码、模拟 API 浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs`，exit 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

该脚本不覆盖 S1-01 的外框重叠。另打开邻居“系统配置”与新调用页对照，截图 `output/playwright/review-light-final-neighbor.png`、`review-light-final-activity.png`；390px 任务表横滚和状态提示的原始输出：

```text
390px task table horizontal scroll {"width":292,"full":1070,"left":778}
neighbor settings rendered
PASS: 邻居页面及任务状态横滚
```

## Stage 2

**未完成、无 PASS 结论。** 已取得的安全关键字扫描、局部行数和邻居页面证据仅供复审参考；Stage 1 未通过，不能据此批准质量、安全或测试真实性。修复后须重新运行 `review-prepare` 并对新快照重审。
