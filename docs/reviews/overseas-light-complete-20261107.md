# 海外管理及任务轻量化完整独立审查 · 2026-11-07

## 快照、范围与结论

- candidateId：`e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9`。
- 审查范围：`Product-Spec.md:1–27`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7`、已确认的 `hengxin-smart-image/frontend/preview-overseas-light/`；海外 management、tasks、archives 相关后端、正式前端和测试；`scripts/release/overseas-light-{runtime,package,deploy}.py` 与发布测试。
- **Stage 1：PASS（送审源码与下述隔离验证范围）。Stage 2：PASS（下述质量、安全、测试和视觉检查范围）。** 未发现 HIGH 或需要阻断本候选的 MEDIUM；已知发布前未完成事项见文末，不能据此宣称整体验收或部署完成。
- 审查开始与报告写入前 `review-status` 的 `currentId` 都等于本 candidateId，`approved: false`；报告 Markdown 不纳入代码快照。审查期间未修改业务代码、未提交、未访问生产或部署、未调用收费模型。报告写入后再次核对 `currentId` 仍为该 candidateId、`approved: false`；主 Agent 必须使用该编号登记两阶段 PASS，不得写 `.needs-review` 为 clean 代替凭据。
- 参考 `docs/reviews/overseas-light-{review,recheck,final,signoff,release-ready}-20261107.md` 的问题定位和旧证据，但旧候选文件哈希清单不可供本审查逐项验证，未把旧报告的测试或 PASS 覆盖本快照。下列验证均在本次 candidate 上独立执行。

## Stage 1：Spec 逐条对照

路径除根目录文档及 `scripts/` 外均相对于 `hengxin-smart-image/`。匹配仅覆盖指明的行为及测试范围。

| 需求 | 结论与证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址、权限 | 匹配。`frontend/src/identity-main.ts:21–23` 提供单入口及旧地址重定向；`frontend/src/views/overseas/OverseasPortal.vue:41–53,145–149` 按能力显示并调用接口；`backend/app/overseas/management/router.py:13,18–35` 要求 `stats.read`，`management/facts.py:51–53` 先按任务权限过滤。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:87–93` 验证旧地址跳转。 |
| `:8` 实际发起请求、幂等、排队/失败/取消、北京时间 | 匹配。`backend/app/overseas/studio/service.py:60–101` 建立请求与实际发送人并沿用重放，`management/usage.py:30–48` 统计持久化请求，`management/facts.py:14–38`、`frontend/src/views/overseas/admin/OverseasActivityPage.vue:51–57` 使用北京时间自然日半开区间。`backend/tests/test_overseas_lightweight.py:16–30,33–56` 检查重放 1 次、排队取消仍 1 次、重发 2 次、失败与时间边界；本候选 SQLite 和隔离 PostgreSQL 均通过。 |
| `:9–10` 未知历史、留存边界、图片和停用人员 | 匹配已测范围。`management/facts.py:51–59` 外连接历史、按权限取实际操作者，`management/usage.py:34–48` 聚合图片及最近时间；`OverseasActivityPage.vue:3,27` 明示历史缺失与删除边界；`test_overseas_lightweight.py:33–69` 检查未知作业、停用人员、图片、时间和非授权任务。图片为持久化测试夹具，不代表真实模型执行。 |
| `:11` 概况、下钻、筛选、分页和详情 | 匹配已测范围。`management/usage.py:8–16` 汇总四种概况并将 collecting/cancelling 归执行中，`management/facts.py:39–47` 支持状态和任务搜索，`management/monitor.py:11–25` 分页并输出脱敏错误；`OverseasActivityPage.vue:23–30,59–87` 实现详情、范围与下钻。浏览器脚本 `:94–106` 验证人员、状态下钻和排队取消耗时。 |
| `:15` 实际归档人、组合搜索及分页前过滤 | 匹配。`backend/app/overseas/archives/service.py:63–87` 依据实际事件 `EXISTS` 和关键词过滤，之后计数、分页；`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19` 提供可搜索归档人及历史参与提示。`backend/tests/test_overseas_archive_audit.py:19–46` 验证不同归档人、幂等及组合筛选。 |
| `:16` 真实候选、姓名快照、历史缺失、源任务删除及保留操作 | 匹配已测范围。`archives/service.py:90–99,102–116` 以可见归档事件生成候选并沿用权限；`archives/audit.py:9–35` 保存姓名快照和不完整历史；`test_overseas_archive_audit.py:47–70` 验证删源任务后的归档、权限和未知历史；`OverseasArchivePage.vue:21–26,46–50,64–67` 保留操作并在删除后刷新候选，浏览器脚本 `:141–159` 验证筛选、空态清除与删除。 |
| `:20` 实际负责人、停用、改派与范围 | 匹配已测范围。`backend/app/overseas/tasks/queries.py:84–91,127–131` 以当前 `designer_id` 和任务权限筛选候选；`frontend/src/views/overseas/OverseasWorkspace.vue:16–25,84` 显示范围与负责人；`OverseasTasksPage.vue:98–102,146–156` 在删除或返回列表后刷新候选。浏览器脚本 `:121–137` 实际通过模拟 API 改派给此前无任务成员、返回筛选并删除其唯一任务。 |
| `:21` 两处20条分页、先过滤、位置和返回 | 匹配已测范围。`tasks/queries.py:84–94,111–124` 先过滤再计数、分页；`OverseasTasksPage.vue:37–40,153–158` 维护顶部/底部分页及条件变化；浏览器脚本 `:113–126,138–139` 验证首页、末页、空结果与详情返回。 |
| `:22` 三类状态、历史状态及删除异常 | 匹配已测范围。`tasks/queries.py:77–80,92–94` 分组并排除删除异常进入常规组；`frontend/src/views/overseas/task-status.ts:7–30` 定义展示、`submitted` 下一步及异常颜色；`OverseasWorkspace.vue:51–54` 保留异常提示。`test_overseas_lightweight.py:78–105` 覆盖返工、删除失败和旧 submitted。 |
| `:23` 分批归档、显式完成与解冻 | 源码匹配：`backend/app/overseas/studio/service.py:123–191` 分别处理归档和显式完成/解冻；未操作生产。 |
| `:27` 预览、窄屏、错误和交付 | 代码与隔离浏览器部分匹配：`frontend/tests/overseas-lightweight.browser.mjs:24–36,87–172` 验证尺寸、下钻、改派、删除、错误重试和 390px 控件。最终提交包构建、隔离安装及生产只读验收尚待主 Agent 执行；它们不属于本报告已通过的证据。 |

**未实现 / 部分实现：** 本次代码审查范围未发现其他未实现或部分实现的 Spec 功能；最终发布及生产验收仍未执行，不能把本项视为产品交付完成。**Spec 漂移：** `management/router.py:23–25`、`tasks/router.py:34–38`、`archives/router.py:28–30` 的新增读接口分别对应人员统计、负责人和归档人；未在派发范围发现多余产品页面，未做全仓 scope creep 审计。

### 确认预览复核

- 状态按钮：`OverseasActivityPage.vue:5,95–102` 与 `frontend/preview-overseas-light/ActivityPreview.vue:7`、`style.css:5–6`；1280×900 实测四个未选中按钮文字均 `rgb(96, 98, 102)`、透明背景和边框，四种圆点颜色逐项相同。点击失败并等待动画结束后，两者选中态均文字 `rgb(93, 135, 255)`、背景 `rgb(238, 243, 255)`。脚本 `output/playwright/review-complete-colors.mjs`，截图 `output/playwright/review-release-ready-{activity,preview}.png`。
- 标题说明 `OverseasPortal.vue:5` 与 `preview-overseas-light/ActivityPreview.vue:3` 一致；正式组件浏览器脚本 `:89` 验证。
- 搜索宽度 255px、卡片与任务表头间距 201px、六个普通按钮色、日期控件不重叠、成品空态清除：脚本 `frontend/tests/overseas-lightweight.browser.mjs:24–36,109–153` 对当前源码逐项断言并通过。390px 任务表可横滚：实测 `width=308, full=1070, left=762`，见 `output/playwright/review-light-final-neighbor.mjs`。

## Stage 2：代码质量、安全、测试真实性和邻页

- **代码质量：PASS（派发范围）。** 主要生产文件 48–264 行，低于 300 行；如 `management/usage.py:1–48`、`OverseasActivityPage.vue:1–110`、`scripts/release/overseas-light-deploy.py:1–264`。扫描本次正式前端相关文件未发现显式 `any`、`@ts-ignore` 或禁用 lint；请求响应有 `unknown` 校验（`frontend/src/api/overseas/management.ts:18–32`、`tasks.ts:36–65`），异步组件用 generation 和卸载清理防止迟到响应（`OverseasActivityPage.vue:49–50,59–73,89`）。通过不是全仓质量认证。
- **安全：PASS（派发范围静态扫描）。** 对相关前后端和发布脚本扫描 `eval(`、`dangerouslySetInnerHTML`、`innerHTML`、`shell=True`、前端密钥变量、常见明文密钥和绝对用户路径，无匹配；搜索和过滤使用 SQLAlchemy 表达式及 `autoescape=True`（`management/facts.py:28–47`、`archives/service.py:63–79`、`tasks/queries.py:84–119`）。身份和范围证据见 Stage 1；这不是全面渗透测试或密钥历史扫描。
- **测试真实性：PASS（已测合同）。** `test_overseas_lightweight.py:16–30` 通过真实 HTTP 测试客户端发送、重放、取消及重发，非单纯 mock 计数；`:33–69` 用不同角色和历史缺失验证范围和时间；`test_overseas_archive_audit.py:19–57` 用真实归档事务与权限检查多人和源任务删除；浏览器脚本 `:40–85,121–159` 是真实正式组件配模拟 API，不代表生产身份、真实外部存储或收费生成。`scripts/release/test_overseas_light_release.py:17–94` 只模拟包篡改、前端切换失败和未确认停止，不能视作实际生产回滚或在途任务保护证明。
- **邻页视觉：PASS（实际打开比较）。** 本次以模拟 API、1280×900 打开“系统配置”和“调用与执行”，截图 `output/playwright/review-light-final-neighbor.png` 与 `output/playwright/review-light-final-activity.png`；两页沿用同一海外 Shell、白底卡片、字体和 Element 控件，页内按钮差异遵循确认预览。另实测 390px 任务表横滚及三页控件；不代表真实数据、所有设备或发布包已验证。
- **发布脚本静态检查：PASS（受限于后续实测）。** `scripts/release/overseas-light-package.py:30–65,68–104` 从固定提交 Git archive 在 `node_modules` 之外构建并校验审查身份；`overseas-light-runtime.py:29–65` 校验包内哈希、路径与入口直接引用；`overseas-light-deploy.py:94–131,135–167,195–239` 检查基线、进行隔离安装测试、切换和失败回退。验包**不验证 JS 动态引用完整性**，故最终真实包运行和资源检查不得省略。构建工具使用工作机 `frontend/node_modules`（`overseas-light-package.py:37–53`），其不在审查快照中；构建环境须按锁文件维护并可信。

## 本候选独立验证原始输出

1. 后端 SQLite：在 backend 运行 `.venv/Scripts/python.exe -m pytest -q tests/test_overseas_lightweight.py tests/test_overseas_archive_audit.py tests/test_overseas_management.py tests/test_overseas_management_operators.py tests/test_overseas_tasks.py`，exit 0：

```text
....................................................                     [100%]
52 passed, 2 warnings in 17.11s
```

2. PostgreSQL 17 本地独立临时容器、`review_light_test`，运行 `tests/test_overseas_lightweight_postgres.py`，exit 0，容器已删除：

```text
....                                                                     [100%]
4 passed, 2 warnings in 6.38s
isolated-container-cleaned 331f77e46a2110f0985a1b27515afa25c9a9b7eb343369e71c3c96a4a84c0fad
```

两组的警告为 Starlette TestClient 和 AnyIO 别名弃用警告。

3. 发布脚本模拟测试 `backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_light_release.py`，exit 0：

```text
...                                                                      [100%]
3 passed in 0.37s
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
ℹ duration_ms 14224.879
```

5. 正式 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 与预览 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-overseas-light/tsconfig.json` 均 exit 0；**两次原始 stdout/stderr 均为空**。遵照派发限制，本审查未在工作树运行 Vite build/dev，未独立生成本候选正式发布包。

6. 正式源码、localhost:3038 和隔离模拟 API，运行 `frontend/tests/overseas-lightweight.browser.mjs`，exit 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

## 遗留限制与后续门禁

本报告仅审查代码与隔离环境，不证明真实最终构建、发布包动态资源、实际安装/回退、生产权限数据或在途任务保全。主 Agent 必须先核对本报告后 `review-status` 仍为同一 candidate，按协议 `review-approve` 登记，再按已授权流程提交；从已审提交构建最终包，检查包本体三页与所有加载资源、执行生产隔离安装测试，核对实际生产基线后再部署并只读验收。任一代码变化须重新固定候选并复审，不能沿用本结论。
