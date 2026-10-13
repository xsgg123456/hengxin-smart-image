# 海外任务删除、归档保护与 Skill 目录最终审查

- candidateId：`643bdd423c44876e69ad4fce7d4bdd005a45965cefc5c9d81eabd0f4e518c781`。
- 结论：**Stage 1 PASS；Stage 2 PASS。未发现本候选新增的 HIGH / MEDIUM 阻塞项。**
- 范围：本轮海外任务永久删除、独立归档与动态权限、完整 Skill 安装/目录/冻结执行、对应正式前端、海外迁移 0013、隔离测试和发布准备脚本。实际应用位于 `hengxin-smart-image/`。评估本地实现与发布准备，不把生产安装、切换和真实收费成图列为已完成。
- 依据：`AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1026` 起本轮需求、`Design-Brief.md:180` 起界面约定，以及本轮计划、Skill 盘点和安装 runbook。
- 开始及结束核对 `review-status.currentId` 均为上述候选。审查期间未发现受控代码变化，未修改源码、未提交、未部署、未写 `.needs-review`，也未执行 `review-approve`。本报告由主 Agent 结合相同快照登记批准。

下表中 `backend/`、`frontend/` 均相对应用根 `hengxin-smart-image/`；`tasks/`、`archives/`、`execution/`、`management/`、`studio/` 省略前缀 `backend/app/overseas/`。前轮报告 `docs/reviews/OVERSEAS-DELETE-SKILLS-20261013.md` 的逐项证据经过本轮代码复核，原 FAIL 结论只对应其旧候选。

## Stage 1：Spec Compliance

### 原 HIGH 关闭证据

`Product-Spec.md:1034` 要求任务存在时，归档设计权限随合法改派原子更新，删除后保留最后归属。

- `tasks/assignment.py:16` 持有 Task 行锁，`:30` 同事务更新所有关联 Archive 的 `designer_id`，`:38` 一次提交。该父锁同时被归档与删除使用。旧幂等请求在 `:18` 提前返回，不会把权限恢复为旧设计师。
- `archives/snapshot.py:12` 仅初始化不存在的元数据；已有权限由合法改派事务维护。`archives/service.py:65` 在 Task / Archive 锁定并刷新后用独立归属鉴权；删除后仍使用相同字段。
- `backend/tests/test_overseas_archive_assignment.py:47` 经真实 FastAPI HTTP 接口连续改派 A → B → C，重放 A → B，验证 A/B 列表无记录、详情/原图/ZIP 403，C 全部允许；真实图片和 ZIP 内容删除前后逐字节一致。`:79` 在 flush 后注入故障，验证 Task 版本及 Archive 权限一起回滚。
- `backend/tests/test_overseas_archive_assignment_postgres.py:18` 在真实 PostgreSQL 运行改派先行及删除先行两个顺序，验证后一操作 409，清理后保留最后有效负责人。`test_overseas_task_deletion_legacy.py:27` 验证 legacy 改派、全部版本/轮次删除及旧设计师 ZIP 403、新负责人 ZIP 内容一致。
- 历史迁移 `backend/migrations/overseas/versions/0013_task_deletion_archives.py:21` 从任务当前负责人回填旧 Archive，并非首次归档负责人；前一错误候选未发布。主线只读实查记录生产当前无 Archive，本轮不要求为不可达的错误快照虚构补数据。后续实际发布仍须核对生产状态。

上述新增 HTTP、回滚、PG 竞争及 legacy 用例包含在 reviewer 独立执行的 44 项通过结果中。原 S1-H1 关闭。

### 全部本轮条目

| Spec / 验收条目 | 结论 | 代码与行为证据 |
|---|---|---|
| 仅有效海外 super_admin 删除，四类非管理员拒绝，每人单角色 | 完整 | `backend/app/overseas/permissions.py:23` 唯一角色及专用能力；`tasks/deletion.py:33` 服务端重验，`tasks/router.py:43` DELETE 带浏览器请求守卫；`backend/tests/test_overseas_task_deletion.py:55` 四角色直接 HTTP 拒绝，真实浏览器四角色无按钮。 |
| 列表查看旁红色删除、最新任务名称/版本确认、取消不写 | 完整 | `frontend/src/views/overseas/OverseasWorkspace.vue:54`、`OverseasTaskDelete.vue:3`、`:43`、`:58`；后端 `tasks/deletion.py:43`/`:46`。reviewer 实际打开确认框，空名称按钮禁用并取消；主线真实浏览器已验证取消没有 DELETE 请求。 |
| 明示永久清理范围及归档保留，无死引导 | 完整 | `OverseasTaskDelete.vue:7` 提示对应真实 `cleanup_files.py:27`、`cleanup_records.py:16`；本轮实际弹窗截图可见完整警告与名称。 |
| 持久 deleting/delete_failed、刷新恢复、失败重试、实际完成才移除 | 完整 | `tasks/models.py:88`、`deletion.py:36`、`:51`、`cleanup.py:55`/`:61`；`OverseasTaskDelete.vue:31` 轮询及 `OverseasTasksPage.vue:97` 仅 deleted 移除。`output/playwright/delete-skills/fault-result.json` 覆盖断网、刷新、重新确认和失败恢复。 |
| 删除后禁止编辑、上传、对话、生成、归档、重试原业务 | 完整 | `tasks/queries.py:21` 写锁守卫，`studio/queries.py:14` 复用；`OverseasTasksPage.vue:12` 起停止渲染业务操作。真实 HTTP 日志明确验证 new work fenced。 |
| 排队撤销、停止 CLI、核实进程及子进程，未知状态不删目录 | 完整 | `deletion.py:17`、`cleanup_process.py:31`/`:49`/`:55`；真实 Linux 存活子进程测试 `test_overseas_task_deletion_process.py:17`，故障测试 `test_overseas_task_deletion_faults.py:117`。 |
| 重复请求合并、不再领取、迟到结果不写入/复活 | 完整 | `deletion.py:36`、`execution/claims.py:69`、`execution/queue.py:29`/`:60`；`execution/objects.py:29` 先写归属账本，`:36` 写存储前再验，`runner.py:146` 实际收集使用。`test_overseas_task_deletion_legacy.py:105` 覆盖存储写成功但响应丢失及删除后迟到写拒绝。 |
| 清理任务、SKU、资料原件/解析、方案/审核、对话/附件、全部过程图版本、作业/事件 | 完整 | `cleanup_records.py:16` 显式依赖顺序物理删除；`cleanup_files.py:18`/`:27` 所属对象及确证任务命名空间，`:103` 删除后核实不存在。legacy、studio 无/部分/全部归档及真实 HTTP 验证通过。 |
| 全部 CLI 私有 home、记忆、日志、各轮目录 | 完整 | `cleanup_files.py:60` 使用实际 Job 与 Conversation UUID 枚举目录，`:121` 物理清理；`test_overseas_task_deletion.py:81` 与 `test_overseas_task_deletion_legacy.py:27` 覆盖工作台和旧流程多轮目录。 |
| 隔离其他任务、公共 Skill 和凭据，路径/链接安全 | 完整 | `cleanup_files.py:49` 跨任务归属检查，`:74` 校验根目录、UUID、边界及软硬链接；只删确证所属目录。`test_overseas_task_deletion_faults.py:78`、`:93` 和真实 HTTP 隔离断言通过。 |
| 精确已归档版本、SKU、元数据和独立文件保留 | 完整 | `archives/models.py:12`/`:23` 独立归属及资产表，`snapshot.py:38` 精确版本，`:51`/`:53` 任务与 SKU，`:58` 独立 key，`:60` 至 `:66` 读写校验。主线真实 HTTP 部分归档 PNG/ZIP 哈希一致；reviewer 新改派用例验证字节一致。 |
| 先保护归档再清理，历史归档兼容，保护失败不破坏源 | 完整 | `cleanup.py:38` 至 `:46` 先提交保护与清单；`snapshot.py:43` 旧记录兼容；迁移 `0013_task_deletion_archives.py:21` 回填。`test_overseas_task_deletion_faults.py:19` 腐坏不删、修复继续，`:44` 中途失败后持久清单恢复。 |
| 删除后成品检索/详情/原图/ZIP 独立且保持权限 | 完整 | `archives/service.py:47` 独立 SQL 范围、`:65` 鉴权、`:80`/`:89`/`:102` 详情/原图/ZIP；`cleanup_records.py:14` 解除关联。reviewer 实际页面显示两张有效图片和“原任务已删除”，无失效任务入口。 |
| 改派权限随最后有效负责人迁移且删除不放宽 | 完整 | `tasks/assignment.py:30` 同事务更新；本报告原 HIGH 关闭证据及四接口 HTTP、事务回滚、真实 PG 两顺序。 |
| 并发归档/删除顺序确定、重复清理/重启不复活 | 完整 | `tasks/deletion.py:34` 与 `studio/service.py:17` 共用父锁；`test_overseas_deletion_postgres.py:75` 双顺序，`:104` 双请求/双维护；`cleanup.py:42` 清单持久化。reviewer 实际 PostgreSQL 用例通过。 |
| 7 目录的 14 包全部保留，三组英文重名分别独立 ID | 完整离线包及安装实现 | `management/skill_inventory_20261013.json:1` 映射；`skill_install.py:14` 唯一名/来源校验。reviewer 逐个读取源与目标文件：14 包、181 文件、源 111321820 字节、目标 111321938 字节；全部 SHA256 匹配清单。 |
| 沃尔玛原版与新版 9.27 同时保留、统一可辨识名称 | 完整离线包及实现 | inventory original/revised-0927 唯一标识；`skill_install.py:37` 只适配名称及必要自引用。reviewer 逐个 adaptedFiles 重新计算替换并与原文对照，118 字节差额仅为该适配；各自设计指令未合并。 |
| 完整参考图/脚本资源，大包不经旧 20 MiB ZIP，海外专用 | 完整 | `skill_install.py:37` 全量复制，`installed_tree.py:14` 支持完整大包，`installed_catalog.py:23` 海外上下文与生产根目录白名单；`test_overseas_installed_skills.py:121` 大资源、`:150` 国内拒绝。未执行包内脚本。 |
| Skill 管理仅名称/描述、搜索/刷新，写入口/API 移除 | 完整 | `OverseasSkillCatalog.vue:3` 至 `:21` 两列只读；`management/router.py:26` Skill 仅 GET。reviewer 实际 DOM 两列表头，无添加/上传/版本/启停入口，主线真实 HTTP 验证写 API 关闭。 |
| 长描述/窄屏完整，加载、空目录、失败区分 | 完整 | `OverseasSkillCatalog.vue:5` 至 `:9`、`:24` 换行；`installed_catalog.py:74`/`:88` 区分空与 503；`test_overseas_installed_skills.py:75`。reviewer 390px 截图无水平溢出；主线长描述及故障截图已核对。 |
| 页面和工作台同一可用目录，不返回整包指令/私有路径 | 完整 | `management/skills.py:5` 与 `studio/queries.py:80` 共用 listing；`installed_catalog.py:96` 只返回 id/name/displayName/description；真实 HTTP 和 `test_overseas_installed_skills.py:22` 检查两者一致。 |
| 每轮冻结完整所选包，更新不改旧轮次，只读隔离挂载 | 完整实现；生产挂载待发布验收 | `installed_catalog.py:102` 冻结发布/包校验值，`:112` 执行重新校验；`execution/materials.py:21` 全量复制，`skill_copy.py:8` 限定私有轮次，`backend/app/execution/workspace.py:101` 两处只读挂载且遮蔽旧发现目录。`test_overseas_installed_skills.py:22`、`:156` 验证旧快照及缓存失效。 |
| 海外发布排空/备份/迁移/失败关闭，同一真实目录、真实 worker 探针 | 发布准备完整；生产未执行 | `scripts/release/overseas-update-deploy.py:70` 顺序保护，`overseas-skills-runtime.py:48` 只读 bind、`:54` 空旧卷及全量预检、`:88` API/native inode/14包181文件/非root校验；`management/skill_probe.py:15` 真实 sandbox 逐文件 SHA、只读、仅选中包。reviewer 发布故障 54 项通过，不能替代生产探针输出。 |

部分实现、未实现：在本次“实现及发布准备”范围内未发现。正式生产安装/迁移/切换/探针/页面冒烟属于下一步操作，仍未完成，不能据本报告宣布整个用户目标交付。

## Stage 2：Code Quality

### 质量、类型与测试真实性

- 通过：本轮受控新增/修改 `.py`、`.ts`、`.vue`、`.mjs` 文件逐个统计均不超过 300 行；前端扫描没有新增显式 `any`。前端请求使用 `unknown` 及 DTO guard，例 `frontend/src/api/overseas/archives.ts:12`、`:18` 校验原图 URL、数量和内容类型；reviewer `vue-tsc --noEmit` 退出码 0。
- 通过：删除请求、进程核实、文件归属清理、数据库清理分离，见 `tasks/deletion.py:32`、`cleanup_process.py:31`、`cleanup_files.py:27`、`cleanup_records.py:12`。后台错误转为固定业务文案 `cleanup.py:11`，不向浏览器泄露内部连接串；故障测试 `test_overseas_task_deletion_faults.py:44` 检查这一点。
- 通过：故障测试确实在删除发生中途注入存储失败、先腐坏真实内容、建立真实软硬链接；并非只有纯函数 happy path。`test_overseas_task_deletion_process.py:17` 真的启动会留下子进程的临时进程；`test_overseas_archive_assignment.py:47` 真的切换 HTTP 身份并打开原图/ZIP。PG fixture `test_overseas_members_postgres.py:22` 使用隔离随机 schema，限定 PostgreSQL `_test` 数据库，没有以 SQLite 宣称验证行锁。
- 通过：浏览器故障矩阵明确标 `mocked: true`，真实矩阵使用实际隔离 HTTP/数据库/MinIO，并分别记录；未把模拟断网测试当生产网络故障证据。对应 `frontend/tests/overseas-delete-faults.browser.mjs:1`、`overseas-delete-skills-real.browser.mjs:1`。

### 安全扫描

- 本轮新增/改动实现未发现硬编码真实密钥、`eval`/动态 `exec`、`dangerouslySetInnerHTML`/`innerHTML`、含密钥的 `VITE_*`、`shell=True` 或用户输入字符串拼 SQL。查询使用绑定表达式，例 `archives/service.py:47`；迁移 SQL 为固定语句 `0013_task_deletion_archives.py:21`。扫描命中的 Python `any(...)` 是内建聚合，与 TypeScript `any` 无关。
- 文件风险有具体防护：`cleanup_files.py:44`/`:74` 对象命名空间和清理边界，`installed_tree.py:25`/`:46` 禁止链接、特殊文件及超量资源、读取时核实 inode，`:39` 生产 root 所有且 worker 不可写。`skill_install.py:113` 只允许运维原子发布，未开放到网页。
- 下载和权限防护：`archives/service.py:75` 独立权限，`:95` private/no-store/nosniff，`:109` ZIP 文件名净化；`frontend/src/api/overseas/archives.ts:18` 禁止任意返回 URL，`OverseasArchivePicture.vue:20`/`:35` 释放对象 URL、卸载中止请求。改派与删除前后权限矩阵已真实执行。
- 发布子进程使用参数数组及受控路径，`scripts/release/overseas-skills-runtime.py:14` 限定环境继承，`:28` 以真实海外用户降权探测，失败不输出配置/凭据。`:88` 禁止 root 探针代替 worker 探针；当前仅验证代码及故障注入，尚无生产探针成功事实。
- **历史依赖风险保留**：`output/delete-skills-dependency-audit.log:2` 为 71 项（36 high、34 moderate、1 low，0 critical）；本轮 `frontend/package.json:3` 只升应用版本，未升级依赖/锁文件。此处不是“所有依赖无漏洞”的结论，也不把历史审计项冒充本候选新引入漏洞。

### 实际视觉对比

reviewer 使用 Playwright 打开 `http://localhost:3022` 隔离真实环境，登录测试管理员，实际查看 Skill 页、邻居执行监控、任务列表、成品库、已删除来源归档详情、删除确认。浏览器只做读取、登录和取消确认，没有发送删除或模型请求。

- 新 Skill 与邻居 `frontend/src/views/overseas/admin/OverseasLiveActivity.vue:4` 共享白卡、16px 圆角、相同标题/搜索/表格密度；按钮实测高度 32px、字号 14px、蓝色 `rgb(93,135,255)` 一致。删除入口为 `rgb(255,77,79)`，与危险按钮约定一致。代码 `OverseasSkillCatalog.vue:2`、`OverseasTaskDelete.vue:3`。
- 实际删除确认宽 560px、名称/范围/输入/取消/红色确认均可见；空名称禁用。归档详情显示独立元数据、“原任务已删除”、两张已成功加载原图和下载按钮；没有失效的原任务入口。代码 `OverseasTaskDelete.vue:5`、`OverseasArchiveDetail.vue:2`、`:9`、`OverseasArchivePicture.vue:3`。
- 390×844 的 Skill 页长行换行、刷新可访问、无页面水平溢出。主线额外长描述、手机删除/归档及故障截图位于 `output/playwright/delete-skills/`，reviewer 自己的邻居/数值/最终截图位于 `output/playwright/delete-skills-final-review/`，`result.json` 的 `errors` 为 `[]`。
- reviewer 首次浏览器脚本把成品库标题误写为“归档成品”导致等待超时；更正测试定位后通过。截图随后等待加载/禁用过渡动画重拍并目视复核，没有把中间加载帧当最终视觉证据。

### Spec 漂移

未发现本轮额外产品范围。新增 TaskDeletion、ExecutionObject、ArchiveAsset、独立归档详情及运维安装/探针分别对应持久清理、迟到对象收敛、独立成品、完整 Skill 安装要求。代码位置：`tasks/models.py:88`、`archives/models.py:23`、`archives/router.py:31`、`management/skill_install.py:179`。未新增网页维护 Skill 或国内业务删除能力。

## 测试与编译原始输出

reviewer 在 Linux 临时容器内以只读源码 bind 执行，网络仅接隔离测试 PostgreSQL。用例：archive_assignment、archive_assignment_postgres、task_deletion、legacy、faults、process、deletion_postgres、deletion_migration、installed_skills。

```text
..................................s..........                            [100%]
44 passed, 1 skipped, 2 warnings in 20.49s
```

1 项 skipped 是历史迁移夹具要求 `TEST_OVERSEAS_DATABASE_URL`，本命令只配置 `TEST_OVERSEAS_MEMBERS_DATABASE_URL`；不计为 reviewer 迁移通过。真实改派/删除 PG 用例实际执行。两条 warning 为现有 Starlette/httpx 和 anyio deprecation。迁移及全量 PG 补充证据来自主线已读取日志。

reviewer 独立发布脚本故障验证，无网络，无生产调用：

```text
......................................................                   [100%]
54 passed in 1.70s
```

reviewer 独立语法编译与前端类型检查：

```text
PYTHON_COMPILE_PASS 113 files (no bytecode written)

[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.28 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

类型检查退出码 0。另已读取主线正式构建及回归原始输出；全后端日志早于本次权限修复，不能代替新增修复专项：

```text
# output/archive-assignment-regression-20261013.log
51 passed, 2 warnings in 21.47s

# output/delete-skills-backend-final.log
1951 passed, 166 skipped, 15 warnings in 239.39s (0:03:59)

# output/pg-regression-full-20261013.log
70 passed, 2044 deselected, 2 warnings in 92.35s (0:01:32)

# output/delete-skills-frontend-tests.log
ℹ tests 319
ℹ pass 319
ℹ fail 0
ℹ skipped 0
ℹ duration_ms 9015.9064

# output/delete-skills-frontend-build.log
> hengxin-smart-image-frontend@0.2.28 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4705 modules transformed.
✓ built in 36.42s

# output/delete-skills-http-final.log
PASS installed catalog matches studio, web writes removed, complete frozen resources survive installation update; zero model calls
PASS super-admin-only DELETE, stale/name checks, new work fenced, independent archive view/PNG/ZIP bytes and permissions after deletion, owned objects/memory gone, other task/Skills/domestic retained
PASS ALL delete/archive/installed Skills real HTTP integration
```

reviewer 独立对真实离线 14 包逐文件核对结果：

```text
packages=14 files=181 bytes=111321938 sourceBytes=111321820
adaptationDelta=118 allSourceAndDestinationHashesMatch=true
release=7f409fdc92401c25f559899e3529720480b482cee0bfbbbca8daaecb0c0c2bbc
```

## 交接边界

允许主 Agent 为本候选登记两阶段 PASS，然后继续已经授权的海外发布步骤。生产安装、生产 schema 0013、API/native 同 inode、真实 worker sandbox 的 14/181 逐文件只读输出及生产页面冒烟必须由主线执行并留证；本报告没有代做或提前认证这些结果。不得使用生产真实任务删除做验收，不触发收费生图；字体/文档工具与真实成图质量也不因完整包校验通过而被宣称已验证。
