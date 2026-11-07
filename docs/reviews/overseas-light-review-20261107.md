# 海外管理及任务轻量化独立审查 · 2026-11-07

## 审查结论与快照

- **candidateId**：`88615899a70a2a903991f61f74a358984b04e80f728e7cf651336cbeba737dd0`。
- **审查范围**：`Product-Spec.md:1–27`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7` 和 `hengxin-smart-image/frontend/preview-overseas-light/`；海外管理统计、执行监控、任务、归档 API 和正式前端及其测试；`scripts/release/overseas-light-{runtime,package,deploy}.py`、相应发布测试。
- **Stage 1：FAIL**。S1-01 为 HIGH 发布凭据完整性缺口，另有三项 MEDIUM 功能/引导偏差。**Stage 2：未执行**，不能登记两阶段 PASS。审查未修改产品实现，未部署或操作生产。
- 开始和报告写入后 `python .codex/hooks/harness.py review-status` 均返回 `currentId` 等于上述 candidateId，审查期间代码快照未变，`approved: false`；此前 `reviewedId` 为 `f92fa1784dfed80b62088c378f24978856f88a5c32d028daa98cee766b8ff957`。本报告只针对该快照，不可覆盖任何后续修订。

## Stage 1 发现

### S1-01 · HIGH · 待发布前端未与已审快照建立可验证的构建关系

**要求**：`Product-Spec.md:25–27`、`DEV-PLAN.md:7` 要求正式构建、独立审查后安全发布；`AGENTS.md` 的快照协议要求最终交付匹配批准快照。

**实际**：`scripts/release/overseas-light-package.py:24–35` 对源文件核对已审提交，`:51` 却直接收集工作区的 `frontend/dist`，`:54–56` 把其自算哈希写进带 candidateId 的 manifest。`dist` 被 `.gitignore:15` 忽略，也被 `.codex/hooks/review_files.py:8–10` 排除在审查快照之外；脚本没有从已审提交独立重建或验证构建产物来源。`scripts/release/overseas-light-runtime.py:28–61` 校验路径和 manifest 自报哈希，却不核对入口引用或产物与已审源码的关系。可重复证据：`scripts/release/test_overseas_light_release.py:17–33` 用仅含字节 `html`、没有 JavaScript 入口的 `index.html` 构造包，并断言 `verify_package` 成功；本审查实际运行该测试，3 项全部通过。`scripts/release/overseas-light-deploy.py:214–217` 先安装前端、重新开放入口，才通过 `:179–189` 检查公网入口 JS；无入口的坏包因此直到切换后才失败并进入回滚。

**影响**：旧、错误或非已审生成物仍可带合法的源码 candidateId 进入包；本次交付不能只凭 manifest 断言前端属于批准快照。当前实际数据并不显示已污染：审查者用相同源码独立构建 `output/review-overseas-light-dist`，与当前 `frontend/dist` 的 **692/692 文件逐项 SHA-256 相同**。这证明本次现有目录相同，不能证明之后打包仍强制绑定该结果。应在打包环节建立从固定已审提交到构建产物的可复核绑定，并在切换前拒绝缺失入口及引用的坏包。

### S1-02 · MEDIUM · 改派后负责人筛选候选不刷新

**要求**：`Product-Spec.md:20` 要求改派后展示与筛选都按当前 `designer_id`，候选来自当前可见任务的实际负责人。

**实际**：`hengxin-smart-image/frontend/src/views/overseas/OverseasTasksPage.vue:134–138` 改派成功只更新详情；`:146–157` 返回列表时路径变化只调用 `load`，`loadAssignees` 只在角色/身份、显式刷新等路径运行。新负责人此前没有任务时，列表行显示新负责人，下拉却保留旧负责人，找不到新负责人，直到点“刷新任务”。

**复现**：独立浏览器载入正式组件、用本地模拟 API 完成改派并返回列表，原始输出：

```text
{"afterAssignment":"b","assigneeRequests":2,"staleOldOption":1,"newOption":0}
```

复现脚本 `output/playwright/review-light-reassign.mjs`；后端 `hengxin-smart-image/backend/app/overseas/tasks/assignment.py:27–31` 已在事务中改为新负责人，因此该观察是前端候选缓存问题。需要让成功改派后的候选与当前列表同步，并覆盖新负责人原先无可见任务的场景。

### S1-03 · MEDIUM · 历史已获准 submitted 被错误引导去审核

**要求**：`Product-Spec.md:22` 要求待处理提示真实对应下一步，保留旧流程和动作语义；`Product-Spec.md:1100–1103` 要求已在途历史任务继续原流程。

**实际**：`hengxin-smart-image/frontend/src/views/overseas/task-status.ts:9,20–23` 对全部 `submitted` 输出“待设计审核图需”。但 `hengxin-smart-image/backend/migrations/overseas/versions/0010_requirements_review.py:18–20` 为历史 submitted 设置 `requirements_approved=true`；`hengxin-smart-image/backend/app/overseas/tasks/requirements.py:50–56` 仅允许 `pending_review` 审核；`hengxin-smart-image/frontend/src/views/overseas/OverseasPlans.vue:55` 对 submitted 提供“开始分析”。已审查的 `hengxin-smart-image/backend/tests/test_overseas_plans.py:152–162` 也构造已获准的旧 submitted。独立浏览器以该历史状态加载正式列表，原始输出 `LEGACY_LIST 1`，表示出现一处“待设计审核图需”；该模拟仅验证显示，历史有效性由迁移及旧计划测试前提证明。需要对历史实际动作给出准确提示，并让服务端分组与展示维持一致。

### S1-04 · MEDIUM · 排队取消的执行记录把耗时标成进行中

**要求**：`Product-Spec.md:11` 要求记录/详情如实显示状态、开始结束时间和耗时；`:8` 特别包含发起后取消。

**实际**：`hengxin-smart-image/backend/app/overseas/execution/cancel.py:23–27` 可在 queued 时直接结束；`hengxin-smart-image/backend/app/overseas/execution/claims.py:40–43,95–97` 说明该路径写 `completed_at` 但未进入设置 `started_at` 的领取分支。`hengxin-smart-image/frontend/src/views/overseas/admin/OverseasActivityPage.vue:24,30,80` 的 `duration` 在结束时间存在但开始时间为空、状态 `cancelled` 时落入“进行中”，列表和详情均误报。现有浏览器测试 `frontend/tests/overseas-lightweight.browser.mjs:15,59–65` 仅含 running 与 failed 且均有 startedAt，不能发现该终态。应对未开始即取消如实显示无执行耗时或未开始。

## Stage 1 逐条对照

下表的“匹配”仅指所列证据覆盖的行为，不等于整阶段通过。

| 需求 | 结果和证据 |
|---|---|
| `Product-Spec.md:7` 合并入口、旧地址、权限 | 匹配。`frontend/src/identity-main.ts:22–23` 注册合并入口和两个旧 URL 重定向；`frontend/src/views/overseas/OverseasPortal.vue:40–42,49–52` 按能力生成入口；`backend/app/overseas/management/router.py:11–35` 要求 `stats.read`。独立浏览器旧入口重定向通过。 |
| `:8` 按实际持久请求计数、幂等、日期 | 源码匹配，端到端仍需补覆盖。`backend/app/overseas/studio/service.py:60–74,90–101` 幂等重放不新建、成功发送将 Job 与含 actor 的 Turn 同事务保存；`management/usage.py:30–48` 按关联 Turn 汇总、无状态过滤；`management/facts.py:21–38` 做起止边界；`frontend/src/views/overseas/admin/OverseasActivityPage.vue:50–57` 构造北京时间自然日。`backend/tests/test_overseas_lightweight.py:13–36` 覆盖伪造持久记录、排队/失败及日期，不足以独立证明真正发送、幂等、取消后统计的整链；现有发送测试前提见 `tests/test_overseas_studio.py:47–66,78–89`。 |
| `:9` 未知历史、人员范围和保留 | 匹配源码。`management/facts.py:51–53` 先按 `stats.read` 范围并外连接 Turn；`management/usage.py:34–36` 仅归属可追溯 Turn；`management/monitor.py:21–25` 可返回空操作者，前端 `OverseasActivityPage.vue:3,24,27` 标未记录及删除边界。`studio/conversation_cleanup.py:91–109` 确实按既有规则删除轮次及作业。`test_overseas_lightweight.py:21,37,43–49` 覆盖未知作业及角色范围。 |
| `:10` 人员、图片数、停用成员 | 匹配已检查范围。`management/usage.py:37–48` 按 actor 聚合请求、图片/版本及最近时间；`management/facts.py:56–59` 候选来自有记录的成员且不排除停用；`test_overseas_lightweight.py:18–32` 覆盖停用、排队/失败及图片计数。该测试直接插入图片，不等同于完整生成/返工链测试。 |
| `:11` 概况、下钻、过滤、详情和错误 | **部分实现**：S1-04。其余范围：`management/usage.py:12–16` 汇总 collecting/cancelling 到 running；`facts.py:39–47` 实现状态组和任务名/ID；`OverseasActivityPage.vue:59–80` 概况用无条件权限范围，人员下钻保留日期，状态下钻清空人员和日期。`:61–62` 对 collecting/cancelling 使用 `status`，不会错误传入 `statusGroup`。 |
| `:15` 归档人及关键词先于计数分页 | 匹配。`backend/app/overseas/archives/service.py:63–87` 以关联 `ArchiveEvent.actor_id` 的 EXISTS、关键词先于 count/offset；`OverseasArchivePage.vue:4–5,17–19` 显示筛选和早期参与提示；`tests/test_overseas_archive_audit.py:37–46` 检查两名真实参与人及关键词。 |
| `:16` 停用/历史快照、旧记录、源任务删除 | 匹配已检查范围。`archives/audit.py:9–21,31–35` 保存实际确认人姓名与不完整标记；`archives/service.py:90–99` 从权限内事件取最近姓名；`tests/test_overseas_archive_audit.py:49–69` 覆盖删源后、原有历史缺失及再次归档。权限过滤使用 `service.py:64–65,90–96`，非猜测创建人归档。 |
| `:20` 当前负责人、改派与可搜索候选 | **部分实现**：后端 `tasks/queries.py:84–94,127–131` 用当前 designer_id 和权限过滤，前端 `OverseasWorkspace.vue:25,54` 有可搜索筛选及列；改派后候选存在 S1-02。 |
| `:21` 20 条、两处翻页、服务端先筛选、返回状态 | 匹配所测路径。`tasks/queries.py:84–94,111–124` 先过滤再 count/offset；`frontend/src/views/overseas/OverseasTasksPage.vue:37–40,89–95,146–159` 两处 20 条分页、条件重置页码且详情返回保留组件状态；`tests/test_overseas_lightweight.py:52–78` 25 条跨页；独立浏览器实测详情返回第 2 页及组合条件。 |
| `:22` 三组状态、旧流程、删除异常 | **部分实现**：S1-03 的旧 submitted 提示错误；`backend/app/overseas/tasks/queries.py:77–80,92–94` 分组及排除删除中的数据，`frontend/src/views/overseas/task-status.ts:7–29` 包含 reworking 及删除异常样式；`tests/test_overseas_lightweight.py:59–79` 覆盖 reworking 与 delete_failed。 |
| `:23` 归档不自动完成、显式完成/解冻 | 匹配源码。`backend/app/overseas/studio/service.py:123–158` 归档后只 finish，不设 completed；`:161–191` 显式 complete 与 reopen 检查状态及活动任务。未在本审查实际发起收费或生产操作。 |
| `:25–27` 验收、视觉、部署保护 | **未通过**：S1-01 至 S1-04；正式前端构建和隔离后端/浏览器验证见下。未对正式任务页和活动页独立完成 390px 全路径裁切检验，也未执行生产部署或在线身份实测。 |

### 设计对照与范围漂移

- 独立浏览器以 `1280×900` 打开当前预览及正式源码壳，预览截图 `output/playwright/review-light-preview-{activity,tasks,archive}.png`，正式截图 `output/playwright/overseas-light-live/{activity,tasks,archive}.png`。正式页是本地模拟 API，不是生产数据；两个截图状态和记录数不同，故不能用像素差得出整体完全一致。目视核对了白底卡片、蓝色操作、状态条、筛选区和归档卡片的对应布局。
- 数值证据：预览 `frontend/preview-overseas-light/style.css:4–9` 的状态条间距 18px、状态数字 18px、人员/日期筛选宽 190px/300px、归档卡片最小宽 420px/内边距 18px；正式对应 `frontend/src/views/overseas/admin/OverseasActivityPage.vue:89–99` 与 `frontend/src/views/overseas/OverseasArchivePage.vue:78–87` 相同。`390×844` 正式浏览器仅实测成品筛选及刷新可达，不能扩写成三页全通过。
- 本轮范围内新增 `/management/people`、`/task-assignees`、`/archive-operators` 分别服务已批准统计/任务/归档需求（`backend/app/overseas/management/router.py:23–25`、`tasks/router.py:35–38`、`archives/router.py:28–30`）；未发现该范围内额外产品页面。此项不是全仓未授权功能扫描。

## 已执行的验证与原始输出

1. 正式源码壳浏览器：设置现有 `PLAYWRIGHT_MODULE`，运行 `node tests/overseas-lightweight.browser.mjs`，exit 0。此脚本拦截本地 API，实际渲染组件但不证明生产 HTTP：

```text
PASS: 旧入口、人员调用统计/下钻、执行状态/详情、负责人+状态+分页返回、归档人+关键词/错误重试、390px控件裁切
```

2. 后端 `pytest -q tests/test_overseas_lightweight.py tests/test_overseas_archive_audit.py tests/test_overseas_management_operators.py`，exit 0；原始结果行：

```text
............                                                             [100%]
12 passed, 2 warnings in 7.08s
```

3. 未提供 PostgreSQL URL 时，`test_overseas_lightweight_postgres.py` 原始结果 `3 skipped, 2 warnings in 2.63s`。之后仅为审查新建独立 PostgreSQL 17 测试容器及 `review_light_test`，重跑同命令，exit 0，原始结果：

```text
...                                                                      [100%]
3 passed, 2 warnings in 5.57s
```

测试容器 `cc01d8d528762bcf9e8bdc44bdffc79067e47da2e6d09adcaa4ccddff47bc7ca` 退出并自动删除；没有访问其他数据库。

4. 发布脚本单测 `pytest -q scripts/release/test_overseas_light_release.py`，exit 0；其中 S1-01 的坏包接受是该测试成功断言所证明的缺口，非安装/生产发布通过：

```text
...                                                                      [100%]
3 passed in 0.35s
```

5. 正式 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：exit 0，原始标准输出为空。正式 Vite 构建输出到独立 `output/review-overseas-light-dist`，exit 0，完整原始输出为 `output/review-overseas-light-build.log`；终端记录的关键原始行：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4826 modules transformed.
✓ built in 37.66s
```

首次独立构建结束后按文件相对路径及 SHA-256 比较正式 `dist` 与独立构建，原始输出：

```text
packaged_dist 692 independent_build 692
only_packaged []
only_independent []
changed []
```

发布脚本的代理关闭/排空、回滚路径可在 `scripts/release/overseas-light-deploy.py:195–239`、`scripts/release/skill-reuse-gate.py:68–98` 静态看到，模拟回滚断言见 `scripts/release/test_overseas_light_release.py:44–86`；未运行真实安装、流量切换或恢复，不能据此称生产回退已验证。

## Stage 2

由于 Stage 1 含 HIGH，**未执行 Stage 2**：未完成全量代码质量、安全扫描、测试真实性系统审计及实际邻居页面对照，不作通过结论。修复后须重新 `review-prepare`，复核所有变化并从 Stage 1 重审；不得把本报告登记为两阶段 PASS，也不得直接向 `.needs-review` 写 clean。