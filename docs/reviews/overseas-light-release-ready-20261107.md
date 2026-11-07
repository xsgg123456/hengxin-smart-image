# 海外轻量化发布候选独立审查 · 2026-11-07

## 快照、范围与结论

- candidateId：`42d0d349ca7b51bd6b0108e9abb387d66d674f4125c00ea421bf54cb5e0179e8`。
- 审查范围：`Product-Spec.md:1–25`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7`、`hengxin-smart-image/frontend/preview-overseas-light/`；海外 management、tasks、archives 本轮查询和路由、正式前端及 API、状态映射和相关测试；`scripts/release/overseas-light-{runtime,package,deploy}.py` 及发布单测。参考四份前次报告 `docs/reviews/overseas-light-{review,recheck,final,signoff}-20261107.md`，但重新核查当前源码与下列测试，未把旧快照结论直接作为当前快照通过凭据。
- **Stage 1：FAIL**，一项 MEDIUM：执行概况未选中状态按钮的文字颜色与确认预览不一致。未发现 HIGH。**Stage 2：未执行，不能登记 PASS**。修复后重新固定快照并从 Stage 1 开始复审。
- 开始及报告写入前运行 `python .codex/hooks/harness.py review-status`，`currentId` 均等于上述 candidateId，`approved: false`，审查期间受控代码快照未变。报告 Markdown 不属于代码快照。未修改业务实现、提交、部署、访问生产或调用付费模型。

## Stage 1 发现

### S1-01 · MEDIUM · 执行概况未选中状态按钮颜色不符合确认预览

**要求：** `Design-Brief.md:3` 要求桌面按确认预览对齐；`Product-Spec.md:11,25` 要求四种状态概况及同视口对照。

**实际：** 正式 `hengxin-smart-image/frontend/src/views/overseas/admin/OverseasActivityPage.vue:5,95–101` 四个文本按钮没有针对未选中态的中性色覆盖；预览 `frontend/preview-overseas-light/ActivityPreview.vue:7`、`frontend/preview-overseas-light/style.css:5` 使用预览全局默认色。本审查通过真实浏览器、1280×900、模拟 API、无鼠标悬停或键盘焦点读取计算样式：

```text
                 排队中 / 执行中 / 失败 / 待核实
正式文字颜色      rgb(93, 135, 255)  四项相同
预览文字颜色      rgb(96, 98, 102)   四项相同
正式与预览背景    rgba(0, 0, 0, 0)   四项相同
正式与预览边框    rgba(0, 0, 0, 0)   四项相同
```

四种状态圆点颜色各自一致；实测脚本 `output/playwright/review-release-ready-colors.mjs`，截图 `output/playwright/review-release-ready-activity.png`、`output/playwright/review-release-ready-preview.png`。应限定未选中态修正，并保留选中态和交互反馈；修复后再同视口验四项状态。

**其他文案观察：** 预览标题下为功能说明（`frontend/preview-overseas-light/ActivityPreview.vue:3`），正式为真实姓名和角色（`frontend/src/views/overseas/OverseasPortal.vue:5`）。规范没有规定这段文案逐字一致，真实身份也不属于示例数据，因此本项列为对齐差异，未单独判为功能缺失。

## Stage 1 逐条对照

以下路径除根目录文档和 `scripts/` 外均相对于 `hengxin-smart-image/`；“匹配”仅指列出的范围和隔离验证。

| 需求 | 结论与证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址与权限 | 匹配。`frontend/src/identity-main.ts:22–23` 定义新路由与旧地址重定向；`frontend/src/views/overseas/OverseasPortal.vue:49–53` 根据能力提供一个入口；`backend/app/overseas/management/router.py:13,18–35` 要求 `stats.read`。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:82–85` 测旧地址。 |
| `:8` 用户实际发起次数、幂等、排队/失败/取消及北京时间 | 匹配已测范围。`backend/app/overseas/studio/service.py:60–74,90–98` 将实际操作人及新请求关联，幂等重放返回原请求；`management/usage.py:30–48` 按带 Turn 的 Job 聚合；`management/facts.py:21–38` 实施时间边界；`frontend/src/views/overseas/admin/OverseasActivityPage.vue:51–57` 使用北京时间自然日开区间。`backend/tests/test_overseas_lightweight.py:16–30,33–56` 实测发送、重放、排队取消、新请求、失败与边界，SQLite 和隔离 PostgreSQL 均通过。 |
| `:9–10` 历史未知、权限范围、图片、最近时间和停用成员 | 匹配已测范围。`management/facts.py:51–68` 对作业外连接 Turn 并先施加 `stats.read` 的任务范围，候选取有记录的成员；`management/usage.py:34–48` 聚合图片和最近发起；`OverseasActivityPage.vue:3,27` 提示未知操作者及删除后的统计边界；`test_overseas_lightweight.py:33–69` 测未知作业、停用人员及权限。图片使用测试夹具，不代表真实模型生成已测。 |
| `:11` 四项概况、下钻、筛选、分页、详情及脱敏错误 | 功能匹配已测范围；颜色见 S1-01。`management/usage.py:12–16` 将 collecting/cancelling 汇入执行中；`management/facts.py:39–47` 处理状态和任务检索；`management/monitor.py:11–25` 分页并返回脱敏错误；`OverseasActivityPage.vue:59–87` 管理汇总、人员/状态下钻和耗时；浏览器脚本 `:87–96` 覆盖下钻、详情与排队取消。 |
| `:15` 实际归档人、关键词组合和分页前筛选 | 匹配。`backend/app/overseas/archives/service.py:63–87` 按实际归档事件 `EXISTS` 和关键词过滤后计数分页；`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19` 提供筛选及历史参与提示；`backend/tests/test_overseas_archive_audit.py:37–46` 覆盖多人及组合条件。 |
| `:16` 候选、姓名快照、历史缺失、原任务删除与原有操作 | 匹配已测范围。`backend/app/overseas/archives/service.py:90–99,102–116` 按可见归档事件取候选、按既有范围鉴权；`archives/audit.py:9–35` 保留快照并标不完整；`test_overseas_archive_audit.py:47–69` 测删除源任务后的记录和权限；`OverseasArchivePage.vue:21–26,46–50,64–67` 保留下载、删除、查看及删除后候选刷新；浏览器脚本 `:127–139` 测删除及清除失效候选。 |
| `:20` 当前负责人、停用成员、改派与范围 | 匹配已测范围。`backend/app/overseas/tasks/queries.py:84–91,127–131` 按当前 `designer_id` 和权限过滤候选；`frontend/src/views/overseas/OverseasWorkspace.vue:16–25,54` 展示范围及可搜索负责人；`OverseasTasksPage.vue:98–102,146–155` 在删除或返回列表时更新候选；浏览器脚本 `:107–117` 测改派及删除唯一任务。 |
| `:21` 每页20条、顶部及底部分页、先过滤、位置及返回 | 匹配已测范围。`tasks/queries.py:84–94,111–124` 在计数和分页前应用条件；`OverseasTasksPage.vue:37–40,94,153–158` 提供两处分页面板、记录位置及筛选重置；浏览器脚本 `:97–125` 覆盖首页、末页、空结果、详情返回和筛选。 |
| `:22` 三类状态、旧流程、返工、删除异常 | 匹配已测范围。`tasks/queries.py:77–80,92–94` 在后端归组并从常规组排除删除异常；`frontend/src/views/overseas/task-status.ts:7–29` 显示分组及 `submitted` 的待开始分析提示；`OverseasWorkspace.vue:51–54` 显示删除异常；`test_overseas_lightweight.py:78–105` 测 `reworking`、删除异常和历史 `submitted`。 |
| `:23` 分批归档不自动完成、显式完成与解冻 | 源码匹配：`backend/app/overseas/studio/service.py:123–158,162–191` 将归档与完成/解冻分开；本次未操作生产。 |
| `:25` 同视口、窄屏、空错态与交付 | **未完全匹配**：状态按钮颜色见 S1-01。三页模拟 API 浏览器脚本覆盖错误重试、390px 控件可达及资源请求；其不能证明最终发布包或生产运行。正式提交后构建、包实测、隔离安装、生产只读验收均尚未完成。 |

**范围漂移：** `/management/people`、`/task-assignees`、`/archive-operators` 分别对应已确认的人员统计、负责人和归档人需求（`management/router.py:23–25`、`tasks/router.py:34–38`、`archives/router.py:28–30`）；在本次派发范围未发现额外产品页面。不是全仓范围扫描。

## 前次四项修复的同视口复核

1. 成品搜索宽度：正式与预览均 `x=283, width=255`；归档人均 `x=638.671875, width=200`，重置均 `x=939.328125, width=88`。代码 `frontend/src/views/overseas/OverseasArchivePage.vue:4`、`frontend/src/views/hengxin/prototype.css:26`；实测脚本 `output/playwright/review-light-archive-geometry.mjs`。
2. 任务页内距与顶部分页：正式与预览卡片均 `x=259, width=993`，表头相对卡顶均 `201px`；正式 `frontend/src/views/overseas/OverseasTasksPage.vue:37–40,168` 与预览 `frontend/preview-overseas-light/TasksPreview.vue:7`、`style.css:8`；脚本 `output/playwright/review-light-layout-geometry.mjs`。数据行高度随示例内容变化，未据此判差异。
3. 六个普通按钮：刷新任务、重置筛选、刷新成品、下载整套成品、刷新数据、调用页重置筛选，正式与预览均为文字 `rgb(96, 98, 102)`、边框 `rgb(220, 223, 230)`；`OverseasWorkspace.vue:31,91`、`OverseasArchivePage.vue:4,21`、`OverseasActivityPage.vue:8,14,93`；实测脚本 `output/playwright/review-light-buttons.mjs`。
4. 成品空态清空：`OverseasArchivePage.vue:7` 在筛选无结果时显示“清空筛选”；`frontend/tests/overseas-lightweight.browser.mjs:132–135` 在真实组件和模拟 API 中点击并验证成品重新出现，本审查重跑通过。

## 独立验证及编译原始输出

1. 后端 SQLite：在 `backend` 运行 `.venv/Scripts/python.exe -m pytest -q tests/test_overseas_lightweight.py tests/test_overseas_archive_audit.py tests/test_overseas_management.py tests/test_overseas_management_operators.py tests/test_overseas_tasks.py`，exit 0；原始摘要：

```text
....................................................                     [100%]
52 passed, 2 warnings in 26.75s
```

两条警告为 Starlette TestClient 对 httpx 的弃用警告及 AnyIO BlockingPortal 类型别名弃用警告。

2. 隔离 PostgreSQL 17 临时容器、独立 `review_light_test`，运行 `tests/test_overseas_lightweight_postgres.py`，exit 0；容器已移除：

```text
....                                                                     [100%]
4 passed, 2 warnings in 6.25s
isolated-container-cleaned c1f925b82dc0b6edfbcf5f00ecb0520cb577a75e08e151e75f73bbb2e7805924
```

3. 发布单测 `backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_light_release.py`，exit 0：

```text
...                                                                      [100%]
3 passed in 2.27s
```

4. 前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`，exit 0，原始汇总：

```text
ℹ tests 529
ℹ suites 0
ℹ pass 529
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 22321.0469
```

5. 正式 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 和预览 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-overseas-light/tsconfig.json` 均 exit 0，**两次原始 stdout/stderr 均为空**。遵照派发限制，本审查未在工作树运行 Vite dev/build；前次报告的隔离构建属于前次候选，本次未把其作为当前候选或最终提交包的构建证明。

6. 当前正式源码、`127.0.0.1:3038` 隔离模拟 API，运行 `frontend/tests/overseas-lightweight.browser.mjs`，exit 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

该脚本无四个状态按钮非选中色断言；本审查额外测试发现 S1-01。

## Stage 2 与发布边界

**Stage 2 未执行，无代码质量、安全扫描、测试真实性及邻居页面对比的 PASS 结论。** 本次失败候选不得用 `review-approve` 登记两阶段 PASS，亦不得向 `.needs-review` 写 clean；修复后必须重新固定快照并从 Stage 1 重审。

前次报告已指出 `scripts/release/overseas-light-runtime.py:58–61` 验证 HTML 直接引用但不验证 JS 动态引用的完整性；`scripts/release/test_overseas_light_release.py:17–94` 的回退测试为模拟，不等同真实安装、在途任务或生产回滚。`scripts/release/overseas-light-package.py:30–65,68–104` 从固定 Git 提交构建，提交后的最终包须另行实测动态资源、隔离安装及授权范围内生产只读验收；本次不声称这些后续步骤已完成。
