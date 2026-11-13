# 国内每轮显式 Skill 独立审查

- 日期：2026-11-13；角色：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`fd5487184fd946ffaa76a1b6a77587ad042dbd80c7e7543a6387951eb2637b71`。
- 范围：本次 `git diff HEAD` 的 28 个已跟踪文件，以及 `backend/tests/test_domestic_explicit_skill_pg.py`、`frontend/tests/domestic-explicit-skill.test.ts`、`frontend/tests/domestic-explicit-skill.browser.mjs`，代码目录均在 `hengxin-smart-image/` 下。未跟踪 `=12.1,` 排除。
- 源文档：`Product-Spec.md:1`、`DEV-PLAN.md:1`、`Design-Brief.md:1` 的 2026-11-13 增量条款；旧自动调用条款由新条款覆盖。
- 审查顺序：逐条核对需求及执行链 → 核对类型/安全/测试真实性 → 实际截图比较及浏览器独立复跑 → 复核快照。
- 结论：**Stage 1 PASS；Stage 2 PASS**。本次范围无 HIGH / MEDIUM / LOW 待修发现。该结论不等于生产发布或真实模型生图效果验收。

## Stage 1 · Spec Compliance：PASS

以下 `backend/`、`frontend/` 路径均相对于 `hengxin-smart-image/`。

| 需求 | 结论及代码证据 | 验证证据 |
|---|---|---|
| 五入口在上传附件左侧显示真实技能名、默认不选 | 完整实现。`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:25` 渲染绑定目录的 `displayName`；`:73` 将 checkbox 与当前草稿 Skill 双向关联。`frontend/src/views/shared/studio/use-studio.ts:15` 初始为空 | 独立浏览器复跑五入口，每入口验证初始未选、标签位于上传左侧；`frontend/tests/domestic-explicit-skill.browser.mjs:98` |
| 仅本轮明确选中才调用；成功清空、下一轮不自动沿用 | 完整实现。`backend/app/modules/domestic_studio/policy.py:45` 未选直接返回明确 none；`:47` 校验显式选择。`frontend/src/views/shared/studio/use-studio.ts:137` 成功清草稿；`studio-composer-draft.ts:28` 同时清 Skill | 新增前端测试 `frontend/tests/domestic-explicit-skill.test.ts:6` 独立复跑通过；浏览器五入口均验证第二轮 `skillId:null` |
| 明确拒绝保留草稿供修正；未知请求保留原选择、body、幂等键 | 完整实现。`frontend/src/views/shared/studio/use-studio.ts:128` 保存 pending，`:149` 仅确定性 4xx（除408）解除 pending，草稿保留；`:160` 原请求重试。成功才在 `:137` 清草稿 | `frontend/tests/domestic-explicit-skill.test.ts:31` 网络失败；浏览器 `:139` 的503失败、锁定、同key/body重试及清空检查通过。不将明确拒绝误称为永久锁住原请求 |
| 切换会话独立保留未发送草稿与选择 | 完整实现。`frontend/src/views/shared/studio/studio-composer-draft.ts:14` 以用户、工作台、会话隔离 key，`:46` 恢复对应草稿 | `frontend/tests/domestic-explicit-skill.test.ts:52`；浏览器甲乙会话文字及选择来回切换通过 |
| 服务端仅接受当前绑定且可用的 Skill | 完整实现。`backend/app/modules/domestic_studio/turn_service.py:70` 传入实际 choice；`policy.py:47` 精确比对绑定；既有 `bindings.py:75` 加 admission 锁及刷新绑定，`skill_state.py:57` 校验启用状态 | `backend/tests/test_domestic_explicit_skill_pg.py:40` 覆盖绑定变化、停用拒绝及取消选择后正常发送；既有绑定并发测试已相应改为显式选择 |
| 每轮冻结实际选择，原请求重试不被新绑定改写 | 完整实现。`backend/app/modules/domestic_studio/turn_service.py:48` 先处理幂等回执；`:73` 写入冻结 snapshot；`skill_references.py:21` 无技能不建 pin | `backend/tests/test_domestic_explicit_skill_pg.py:23` 验证 none 幂等；`:40` 验证已选请求冻结重试与篡改 body 拒绝 |
| 不选不挂载、不注入 Skill，不加 `$Skill` 前缀 | 完整实现。`backend/app/modules/domestic_studio/execution_workspace.py:65` 设置 `use_skill`，`:66` 不执行 materialization，`:72` 无技能无前缀。复用 `backend/app/execution/workspace.py:103` 隐藏发现目录及 `persistent_mounts.py:41` 空技能挂载 | `backend/tests/test_domestic_explicit_skill_pg.py:123`；真实 Bubblewrap 测试 `backend/tests/test_domestic_real_sandbox_linux.py:42` 在沙箱内断言第二轮没有 Skill 文件、没有发现目录技能、没有前缀 |
| 继续原会话和图片上下文，明确不重启历史技能流程 | 完整实现。`backend/app/modules/domestic_studio/execution_workspace.py:41` 保留原 session，`:60` 准备历史输入，`:73` 增加本轮约束；`runner.py:126` 使用原 session resume | 新增 PG 测试 `:123` 检查同 home/work、原图文件保留、原session及提示；真实沙箱测试 `:81` 第二轮执行并保留首轮 marker。历史上下文没有被声称抹除 |
| 旧冻结技能轮次兼容；缺 pin 的损坏任务不得伪装 none；清理保护保留 | 完整实现。`backend/app/modules/domestic_studio/execution_workspace.py:35` 接受旧 marker 缺省且 pin 匹配；`skill_references.py:37` 验证明确 none、任务/轮次/会话/归属；`:57` 对异常缺 pin 拒绝清理 | 新增 PG 测试 `:75` 六种损坏注入，`:103` 旧 snapshot 可执行、删 pin 后执行与清理都拒绝；测试不以缺 pin 本身当作 none |
| 历史展示实际冻结技能名称 | 完整实现。`backend/app/modules/domestic_studio/queries.py:88` 从 turn snapshot 读 displayName/name；`DomesticWorkspace.vue:15` 允许既有 `StudioTurns.vue:6` 展示标签 | 新增 HTTP/PG 测试 `:154` 比对已选/none 两轮名称；浏览器五入口历史标签均出现 |
| 无绑定、目录不可用仍能正常发送；旧选择失效可取消 | 完整实现。`backend/app/modules/domestic_studio/queries.py:57` 返回空选项；`policy.py:45` 无选择不读取目录；`frontend/src/views/shared/studio/use-studio.ts:33` 不再以 fixedSkillReady 禁止发送；`DomesticWorkspace.vue:25` 提供取消失效选择 | 新增 HTTP/PG 测试 `:154` 注入目录503后普通发送成功；浏览器无绑定、绑定变化后取消并发送均通过 |
| 管理员文案同步 | 完整实现。`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:3`、`:6`、`:7` 说明可选、用户选用及普通对话可用；`admin/skills.vue:3` 按轮选择说明 | 实际源码与 Spec 对照，无残留本次修改区域的自动调用引导 |
| 窄屏、长名及发送中控件可用 | 完整实现。`frontend/src/views/hengxin/domestic-studio/workspace.css:19` 工具栏允许换行、`:21` checkbox 自适应高度、`:22` 标签任意断行、`:24` 发送区靠右 | 独立浏览器1920/1000/390视口及390发送中边界检查通过；已实际查看四张本轮截图和原1920/390工作台基准截图 |
| 不扩展海外行为、依赖、数据库或共享后端 | 完整实现。唯一共享代码改动 `frontend/src/views/shared/studio/use-studio.ts:33` 删除国内 fixedSkillReady 限制；既有草稿清空机制未改。版本 `frontend/package.json:3` 为0.2.71；diff没有依赖版本、锁文件、迁移或海外后端修改 | 全部567项前端测试通过；海外查询 `backend/app/overseas/studio/queries.py:122` 等未提供该国内门槛字段。此结论为回归与代码范围核验，非海外生产实操 |

部分实现：无。未实现：无。Spec 漂移：无新增页面、API、表、迁移或越出本次最小范围的功能。

## Stage 2 · Code Quality：PASS

- 代码结构与类型：修改/新增代码文件均未超过300行；新增明确的 `explicit_no_skill` 判定复用于执行与清理，避免两套条件漂移（`backend/app/modules/domestic_studio/skill_references.py:37`、`execution_workspace.py:33`）。新增前端无 `any`，当前0.2.71类型检查独立通过。`git diff --check` 无输出、退出0。
- 错误处理：目录不可用退化为空选项，明确选择不可用仍拒绝（`queries.py:65`、`policy.py:47`）；执行及回收对坏快照保持拒绝（`skill_references.py:60`、`execution_workspace.py:38`）。未知发送结果不会新建第二请求（`frontend/src/views/shared/studio/use-studio.ts:149`、`:160`）。
- 测试真实性：新增PG用例使用真实事务/表与 HTTP 客户端，参数化覆盖12项，不只检查返回文字；旧用例增加 `skillId` 是使前提符合新的显式选择合同，没有删除执行/身份/完整性断言（例如 `backend/tests/test_domestic_execution_workspace_pg.py:26`、`test_domestic_turns_pg.py:60`）。真实 Bubblewrap 内检查 `/work/skills`、发现目录及resume状态（`test_domestic_real_sandbox_linux.py:42`）；CLI是本地替身，不是模型效果测试。浏览器运行真实组件，API明确拦截为隔离数据（`frontend/tests/domestic-explicit-skill.browser.mjs:67`），覆盖请求内容、key、失败与恢复、交互和几何边界。
- 安全扫描：在本轮全部修改/新增代码检索密钥前缀、前端敏感环境变量、eval、HTML直接注入、字符串拼接SQL、硬编码口令等，无新增命中；`execution_workspace.py:56` 的 Python `any()` 非 TypeScript `any`。选择授权仍由服务端绑定/启用状态及原有归属校验约束（`turn_service.py:45`、`policy.py:47`），无新增外部端点或权限。
- 既有依赖风险：`output/explicit-skill-audit.log:1` 原始输出为79项（39 high、35 moderate、5 low）；主Agent的critical阈值扫描退出0，不代表依赖零漏洞。本轮 `frontend/package.json:3` 仅版本号变化，未引入/升级依赖；不将既有依赖风险误记为本次新增缺陷，也不宣称已修复。
- 视觉对比：实际打开并比较 `output/playwright/domestic-explicit-skill/workspace-1920.png`、`workspace-1000.png`、`workspace-390.png`、`workspace-390-loading.png` 与 `output/playwright/domestic-r11-responsive-1920.png`、`domestic-r11-responsive-390.png`。新控件沿用 Element Plus checkbox/现有12px工具栏文字与蓝色，桌面左侧插入、窄屏换行，上传和发送仍完整可见，发送中保持位置并禁用（`DomesticWorkspace.vue:25`、`workspace.css:19`）。浏览器独立复跑再次真实渲染并产出 `output/playwright/domestic-explicit-skill-review/`，复看390截图与原基准一致保留页头、会话头、输入与操作层级。外部图标请求被隔离脚本阻断导致外壳图标差异，不来自本轮CSS。

## 编译与运行证据

审查者独立运行当前快照的 `pnpm typecheck`，退出0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.71 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

审查者独立运行新增前端测试，退出0，原始结果：

```text
✔ 国内每轮选择独立：成功后清空，下一轮不沿用，未绑定仍能发送 (15.9188ms)
✔ 未知发送保留原选择和请求，核实成功后才清空 (5.0023ms)
✔ 会话切换保留各自选择，失效选择阻止误发且可取消 (4.7868ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 538.0071
```

已读取主Agent完整前端测试日志 `output/explicit-skill-frontend-tests.log`，原始汇总：

```text
ℹ tests 567
ℹ suites 0
ℹ pass 567
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 18253.129
```

已读取国内生产构建日志 `output/explicit-skill-build.log`，原始末行：

```text
../../output/explicit-skill-domestic-build/assets/index.vue_vue_type_style_index_0_lang-C6Frq7pH.js                       814.14 kB │ gzip: 275.64 kB
../../output/explicit-skill-domestic-build/assets/index-CNd2yUwo.js                                                       963.71 kB │ gzip: 307.80 kB
✓ built in 50.36s
```

后端证据为主Agent隔离Linux运行日志，本审查未另连生产或重复部署。原始首轮及补验结果如下；首轮两失败均是子进程 `ModuleNotFoundError: No module named 'app'`，补充PYTHONPATH后原两用例通过，没有为补验修改代码：

```text
# output/domestic-explicit-backend-tests.log
FAILED tests/test_domestic_cross_uid_linux.py::test_api_and_worker_different_uids_fence_late_write_after_pg_disconnect
FAILED tests/test_domestic_upload_remote_late_pg.py::test_deleted_only_after_a_late_remote_write_is_confirmed_and_removed
2 failed, 174 passed, 19 skipped, 1 warning in 143.44s (0:02:23)

# output/domestic-explicit-backend-env-retest.log
..                                                                       [100%]
2 passed in 16.77s
```

因此是首轮174通过加补验2通过，未解决失败0，不是声称单次全量176通过；19项跳过不计通过。主Agent记录的跳过前提为未提供退役数据库、MinIO大文件开关及Redis；新增12项与真实Bubblewrap执行在本次可运行范围。日志本身未展开全部skip原因，本报告不额外推断其已验证。

审查者使用已读取的 `frontend/tests/domestic-explicit-skill.browser.mjs` 在127.0.0.1:3018独立复跑，退出0；原始JSON结果为 `"result":"PASS"`、`"sends":15`、`"errors":[]`、`"unexpected":[]`，十组检查完整保存在 `output/playwright/domestic-explicit-skill-review/report.json:2`。含五入口、独立草稿、503原请求重试、失效取消、未绑定发送和三视口/发送中布局。

## 快照及交接

初次和结束前 `python .codex/hooks/harness.py review-status` 的 `currentId` 均为 `fd5487184fd946ffaa76a1b6a77587ad042dbd80c7e7543a6387951eb2637b71`，代码快照未变化。审查期间主Agent仅明确了 `Product-Spec.md:3` 中“明确拒绝保留草稿、未知结果保留原幂等请求”的措辞，本审查重新读取并按该条核对了 `use-studio.ts:149`；没有让旧代码结论覆盖新代码。

本报告仅审查，不修复、不commit、不写 `.needs-review`、不登记审批。由主Agent以同一 candidateId 和本报告路径运行 `review-approve` 登记 Stage 1 / Stage 2 PASS；若代码再变需重新固定快照和复核。

