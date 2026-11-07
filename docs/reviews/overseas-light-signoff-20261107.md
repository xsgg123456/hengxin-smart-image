# 海外轻量化最终候选独立审查 · 2026-11-07

## 结论与范围

- candidateId：`9034596747651e3aa5651efca2932d5e1ad7ca9267fa28cc5da350f2636707bd`。
- 审查范围：`Product-Spec.md:1–27`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7`，`hengxin-smart-image/frontend/preview-overseas-light/`；本轮海外管理、任务、成品库后端与正式前端、相关测试；`scripts/release/overseas-light-{runtime,package,deploy}.py` 及发布测试。未访问生产、提交、部署、修改业务实现或调用收费模型。
- **Stage 1：FAIL。** 四项 MEDIUM：成品库搜索框宽度、任务页容器及分页间距、普通按钮颜色、成品库空态清除入口与确认预览不符。未发现 HIGH。**Stage 2：未完成，不能登记 PASS。** 必须修复后重新固定候选并从 Stage 1 重审。
- 开始、审查中及本报告写入后 `review-status` 的 `currentId` 均等于该 candidateId，`approved: false`。主 Agent 说明上一候选 `6e209bc4c4032c560fa96623ef152c54d4787f42dac290153269fad16f085791` 至今仅日期 CSS 和浏览器断言变化，但状态文件未保存该候选的文件哈希清单，本审查无法独立证明逐文件差异，未将旧结论直接覆盖新快照。以下源码和验证均指本候选。

## Stage 1 发现

### S1-01 · MEDIUM · 成品库搜索框宽度和筛选位置偏离确认预览

`Design-Brief.md:3` 要求桌面按已确认预览对齐。预览 `frontend/preview-overseas-light/ArchivePreview.vue:4–7` 使用 `.hx-search`，`frontend/src/views/hengxin/prototype.css:26` 将其最大宽度设为 255px；正式 `frontend/src/views/overseas/OverseasArchivePage.vue:77` 覆盖为 320px。独立浏览器以 1280×900、展开侧栏和模拟 API 测得：

```text
正式：搜索 x=283 width=320；归档人 x=682 width=200；重置 x=961 width=88
预览：搜索 x=283 width=255；归档人 x=638.671875 width=200；重置 x=939.328125 width=88
```

搜索框宽 65px，其他筛选项也被挤移。脚本 `output/playwright/review-light-archive-geometry.mjs`；数据不同及预览横幅导致的垂直位移未作为差异。

### S1-02 · MEDIUM · 任务页内容区和分页区尺寸与预览不符

正式 `frontend/src/views/overseas/OverseasPortal.vue:4,6` 与 `OverseasWorkspace.vue:1` 形成两层 `.hx-page`；`frontend/src/views/hengxin/prototype.css:2` 每层左右各有 8px 内距。相同视口下正式任务卡 `x=267, width=977`，预览 `x=259, width=993`，正式内容两侧各多 8px。顶部计数/分页正式使用 `OverseasTasksPage.vue:38` 的 `.hx-filter.hx-gap`，预览 `preview-overseas-light/TasksPreview.vue:7` 和 `style.css:8` 使用 `.task-page-top`：正式表头相对卡顶 192px，预览为 201px。各项测量来自 `output/playwright/review-light-layout-geometry.mjs`；数据行高度不因模拟数据不同而比较。

### S1-03 · MEDIUM · 普通操作按钮颜色与预览不符

同视口、无悬停及焦点时，正式普通按钮文字和边框均为 `rgb(93, 135, 255)`；预览文字为 `rgb(96, 98, 102)`、边框为 `rgb(220, 223, 230)`。实测范围：

- 任务：“刷新任务”（`frontend/src/views/overseas/OverseasWorkspace.vue:31`；预览 `preview-overseas-light/WorkspacePreview.vue:31`）。
- 成品库：“重置筛选”“刷新成品”“下载整套成品”（`OverseasArchivePage.vue:4,21`；预览 `ArchivePreview.vue:7,17`）。
- 调用与执行：“刷新数据”“重置筛选”（`frontend/src/views/overseas/admin/OverseasActivityPage.vue:8,14`；预览 `ActivityPreview.vue:10,16`）。

上述均为普通 `ElButton`；主操作按钮不在此项比较之内。实测脚本 `output/playwright/review-light-buttons.mjs`。`Design-Brief.md:3` 同时要求沿用现有蓝色操作，修复时应限定作用范围，避免无关页面风格变化。

### S1-04 · MEDIUM · 成品库空结果缺少预览的清空筛选入口

确认预览 `frontend/preview-overseas-light/ArchivePreview.vue:11` 在有筛选且无结果时提供“清空筛选”按钮；正式 `frontend/src/views/overseas/OverseasArchivePage.vue:4–7` 只显示空态，顶部另有重置按钮，但空态内缺该交互。`frontend/tests/overseas-lightweight.browser.mjs:131–132` 只测顶部重置，未证明空态入口存在。此问题由主 Agent 同轮只读对照发现，本审查核对了源码。

## Stage 1 逐项对照

除上述明确不一致外，下面“匹配”限定于所列源码和隔离测试，不代表生产验收完成。路径均相对于 `hengxin-smart-image/`。

| 需求 | 对照结果及证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址及权限 | 匹配。`frontend/src/identity-main.ts:22–23` 建新地址并重定向旧地址；`frontend/src/views/overseas/OverseasPortal.vue:49–53` 根据能力生成入口；`backend/app/overseas/management/router.py:13,18–35` 要求 `stats.read`。浏览器脚本 `frontend/tests/overseas-lightweight.browser.mjs:82–85` 测旧地址。 |
| `:8` 实际请求、排队/失败/取消、幂等、北京时间 | 匹配已测范围。`backend/app/overseas/studio/service.py:60–74,90–98` 建立请求及实际发送人，`management/usage.py:30–48` 按 Turn 聚合，`management/facts.py:21–38` 处理时间区间；前端 `OverseasActivityPage.vue:51–57` 生成北京时间自然日开区间。`backend/tests/test_overseas_lightweight.py:16–30,33–56` 测发送、重放、取消、重发、失败及边界；本轮 SQLite 与隔离 PostgreSQL 均通过。 |
| `:9–10` 历史未知、可见范围、图片与停用人员 | 匹配已测范围。`management/facts.py:51–59` 以权限过滤、外连接实际 Turn，候选不排除有记录的停用人；`management/usage.py:34–48` 聚合图片与最近时间；`OverseasActivityPage.vue:3,27` 提示未记录及已删除数据；`test_overseas_lightweight.py:33–69` 验证计数及权限。图片为测试夹具，不代表收费模型生成已测。 |
| `:11` 四项概况、下钻、查询、详情及状态 | 功能匹配已测范围，视觉有 S1-03。`management/usage.py:12–16` 合并执行中状态；`management/facts.py:39–47` 处理状态和任务检索；`OverseasActivityPage.vue:59–83`、`:24,30` 实现下钻、详情及取消耗时；浏览器脚本 `:87–96` 测人员/状态下钻与排队取消。 |
| `:15` 真实归档人及组合筛选、先过滤再分页 | 功能匹配。`backend/app/overseas/archives/service.py:63–87` 使用归档事件 `EXISTS`，在计数和分页前过滤；`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19` 提供筛选与早期参与提示；`backend/tests/test_overseas_archive_audit.py:37–46` 测多人及组合条件。空态和视觉见 S1-01、S1-03、S1-04。 |
| `:16` 候选、历史缺失、删除原任务及保留原操作 | 匹配已测范围。`backend/app/overseas/archives/audit.py:9–21,31–35` 保存姓名并标记不完整；`archives/service.py:90–99` 从可见真实事件取人员；`test_overseas_archive_audit.py:47–69` 测删除原任务；`OverseasArchivePage.vue:46–50,64–67` 删除成品后刷新候选；浏览器脚本 `:127–139` 测实际组件删除和候选清除。 |
| `:20` 当前负责人、改派、停用及权限范围 | 匹配已测范围。`backend/app/overseas/tasks/queries.py:84–91,127–131` 按当前 `designer_id` 和权限过滤；`frontend/src/views/overseas/OverseasWorkspace.vue:16–25,54` 显示范围、筛选与负责人；`OverseasTasksPage.vue:149–155` 返回时刷新候选；浏览器脚本 `:107–117` 测改派及删除唯一任务。 |
| `:21` 两处 20 条分页、条件先于分页、位置、返回 | 功能匹配，尺寸见 S1-02。`tasks/queries.py:84–94,111–124` 先过滤再计数分页；`OverseasTasksPage.vue:38,40,94,153–158` 提供分页及条件变化处理；浏览器脚本 `:97–125` 测首页、末页、空结果、详情返回、筛选及删除后刷新。 |
| `:22` 三组状态、旧流程、返工与删除异常 | 匹配已测范围。`tasks/queries.py:77–80,92–94` 定义分组并排除删除异常；`frontend/src/views/overseas/task-status.ts:7–29` 定义展示及历史 `submitted` 引导；`OverseasWorkspace.vue:51–54` 展示异常；`test_overseas_lightweight.py:78–105` 覆盖返工、删除异常和旧状态。 |
| `:23` 分批归档与显式完成/解冻 | 源码匹配：`backend/app/overseas/studio/service.py:123–158,161–191` 分离归档与显式完成/解冻。本审查未操作生产。 |
| `:25` 预览、窄屏、测试和交付 | **未全部匹配**：S1-01 至 S1-04。日期控件前次阻塞已修：`OverseasActivityPage.vue:103` 使用 scoped deep 选择器；浏览器脚本 `:24–31,84,149` 在两个视口验证外框包含与按钮不重叠。390px 任务状态说明滚到可见区域后 x=127..263，表格容器 x=49..341，脚本 `output/playwright/review-light-mobile-note.mjs`。真实提交后最终包、安装及生产验证仍未执行。 |

**范围漂移：** 本轮新增 `/management/people`、`/task-assignees`、`/archive-operators` 均对应上述已批准需求，见 `backend/app/overseas/management/router.py:23–25`、`tasks/router.py:34–38`、`archives/router.py:28–30`；在派发范围未发现额外产品页面。此结论不是全仓扫描。

**前次审查问题复核：** 日期控件正式 1280px `x=487..787`、宽 300px，重置 `x=801..889`；390px 控件及父容器均 `x=41..349`，按钮位于下行，重叠问题已修。改派候选、历史 `submitted`、排队取消耗时、顶部/底部范围和删除后候选刷新分别见上表。`scripts/release/overseas-light-package.py:30–65,68–104` 静态上由已审提交 Git archive 在 `node_modules` 之外构建；`overseas-light-runtime.py:58–61` 只验证入口直接引用，**不验证 JS 动态引用的完整性**，真实包必须另测。旧报告所载 692 文件隔离构建属于上一 candidate，不是本次正式包。

## 独立验证原始输出

1. 本候选后端 SQLite，命令为 `backend/.venv/Scripts/python.exe -m pytest -q` 加 `test_overseas_lightweight.py`、`test_overseas_archive_audit.py`、`test_overseas_management.py`、`test_overseas_management_operators.py`、`test_overseas_tasks.py`，退出 0：

```text
....................................................                     [100%]
52 passed, 2 warnings in 19.02s
```

2. PostgreSQL 17 本地临时容器、独立 `review_light_test`，`test_overseas_lightweight_postgres.py`，退出 0，容器已删除：

```text
....                                                                     [100%]
4 passed, 2 warnings in 6.26s
isolated-container-cleaned 1f0ce31c673b30a1e43248e5af04aeb9ed37899c7ea0973f58e2ff49bcf0664e
```

3. `scripts/release/test_overseas_light_release.py`，退出 0：

```text
...                                                                      [100%]
3 passed in 0.57s
```

4. 前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`，退出 0，原始汇总：

```text
ℹ tests 529
ℹ suites 0
ℹ pass 529
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 17025.8228
```

5. 正式及预览分别运行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 和 `--noEmit -p preview-overseas-light/tsconfig.json`，两次退出 0，原始 stdout/stderr 均为空。当前工作树未运行 Vite dev/build。本次未独立构建提交后正式包。

6. 正式源码在 `127.0.0.1:3038`、隔离模拟 API 下运行 `frontend/tests/overseas-lightweight.browser.mjs`，退出 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

默认执行曾因项目无 `playwright` 本地模块而报 `ERR_MODULE_NOT_FOUND`；使用主 Agent 提供的本机缓存 Playwright 与 Chrome 路径后上述重跑通过。模拟交互不证明真实身份或生产数据。

## Stage 2 与发布边界

**未完成，不作 PASS。** 已对派发范围做初步关键字扫描，未匹配硬编码已知密钥、`eval`、`innerHTML` 或 `shell=True`；抽查查询使用 SQLAlchemy 参数化表达式，固定 SQL 位于 `scripts/release/overseas-light-deploy.py:41,85,102`。关键主文件均少于 300 行，如 `overseas-light-deploy.py:1–264`。这些观察不是完整安全或质量认证。

初步静态审查：`overseas-light-runtime.py:15–26,29–65` 限定 API 文件、版本、基线和清单并校验直接入口；`overseas-light-deploy.py:94–131,195–239` 固定 API 镜像和配置，关闭海外入口、等待排空后切换，失败路径恢复前端及旧 API；`skill-reuse-gate.py:68–98` 等旧代理 worker 退出，`skill-platform-runtime.py:61–67` 检查原生服务和其他容器身份。`scripts/release/test_overseas_light_release.py:17–94` 仅模拟验包篡改、前端切换失败和未确认停止，不等同生产中真实回滚、在途任务或数据保全验证。包装依赖现有 `frontend/node_modules` 工具链（`overseas-light-package.py:37–53`），该目录不在审查快照（`.codex/hooks/review_files.py:8–10`）；实际打包环境依赖可信且须按锁文件维护，产物与动态资源仍须按最终包实测。

本轮打开了模拟数据的正式“系统配置”邻居页和“调用与执行”，对比见 `output/playwright/review-light-final-neighbor.png`、`review-light-final-activity.png`；发现与预览的视觉差异如 S1-01 至 S1-03，无法因此给 Stage 2 视觉 PASS。修复后应重新运行 `review-prepare`，重新派发完整两阶段审查；只有新候选两个阶段均 PASS，主 Agent 才能用 `review-approve` 登记同一候选，不能写 `.needs-review` 为 clean 代替。
