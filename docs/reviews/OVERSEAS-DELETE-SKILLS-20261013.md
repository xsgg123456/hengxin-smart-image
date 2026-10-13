# 海外删除、归档保护与 Skill 目录审查

- candidateId：`4698b8f05d5ac414e2ef0478e221a0b6792d3368218d0a530054fe17c87af8d5`
- 范围：本轮 `git diff` / 未跟踪的海外任务删除、独立归档、完整 Skill 安装与目录、对应前端、海外迁移 0013、发布脚本及测试；应用根为 `hengxin-smart-image/`。未把无关历史产品功能列为本轮缺陷。
- 审查依据：`AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`；Product-Spec 本轮末尾需求、Design-Brief 的删除/只读目录段，以及本轮计划、盘点、安装 runbook 和验收记录。
- 结论：**Stage 1 FAIL：1 项 HIGH。Stage 2 未执行。不得为该候选登记两阶段 PASS 或执行发布切换。**
- 本次检查开始与结束时，`review-status.currentId` 均为上述 candidateId；源码未变化。审查期间主 Agent 在 Product-Spec 中补充了改派权限的明确描述（普通 Markdown 不计入代码快照），本报告的问题在该补充前已由既有改派语义及真实调用复现。
- 本报告只评价本地实现和发布准备。生产 Skill 安装、真实 worker sandbox、线上页面尚未执行，不能将准备脚本及本地测试标成生产交付完成。

## Stage 1：HIGH 问题

### S1-H1：归档权限冻结在首次归档的设计师，合法改派后权限没有迁移

**级别：HIGH；影响：访问权限回归，以及新负责人无法查看/下载成品。**

需求原文要求“成品库继续按原有权限范围检索、查看和下载，不能因任务删除扩大或丢失访问权限”（送审时 `Product-Spec.md:1042`）；已有改派行为要求原设计失去权限、新设计接续，代码证据为 `backend/tests/test_overseas_assignment.py:89`。审查期间新增的明确约定见当前 `Product-Spec.md:1034`。

可达过程：设计师 A 负责的 Studio 任务先归档一张图片，超级管理员经真实 `/tasks/{id}/assignment` 接口改派给 B。改派成功后，B 可以查看任务，却被归档详情和 ZIP 接口拒绝；A 仍可列出及读取该归档。超级管理员再删除原任务，过期的 A 归属被永久保留，B 仍无法访问。

直接证据（以下路径相对 `hengxin-smart-image/`）：

- `backend/app/overseas/archives/snapshot.py:14`：只有 `record.created_by is None` 时设置权限；第 16 行把首次归档时的 `task.designer_id` 写入快照，以后不更新。
- `backend/app/overseas/tasks/assignment.py:26`：合法改派只更新 `Task.designer_id`，没有同步仍与该任务关联的 Archive。第 21 行版本校验及第 29 行审计使该路径是正式可达操作。
- `backend/app/overseas/archives/service.py:49`：列表只使用 Archive 的旧权限字段；第 75 行详情/原图/ZIP 统一使用旧字段鉴权，即使 `task_id` 尚存在也不按当前负责人检查。
- `backend/app/overseas/tasks/cleanup_records.py:14`：删除将 `Archive.task_id` 置空；`cleanup.py:40` 再次调用 protect，但不会纠正已填的旧负责人。

reviewer 在隔离 Linux 容器内挂载当前源码为只读，复用真实 FastAPI/SQL/图片测试夹具并通过正式改派 API 复现。旧设计师用相同归档业务服务验证（这些服务也是 HTTP 路由调用的实现）；新设计师使用真实 HTTP 接口。临时复现脚本仅写入一次性容器 `/tmp`，未修改源码、未访问生产。

原始输出：

```text
REPRO after_assignment new_designer_task= 200 new_designer_archive= 403 new_designer_zip= 403 old_designer_archive_count= 1 old_designer_picture_count= 1
REPRO after_delete new_designer_archive= 403
REPRO after_delete old_designer_access=True sourceDeleted= True
.
1 passed, 2 warnings in 4.64s
```

这里的 `1 passed` 表示“确认缺陷存在”的复现断言通过，不表示产品行为通过。

修复验收：任务仍存在时，合法改派应在同一事务同步归档最终权限；历史归档在读取/保护时也不能继续沿用过期归属。删除完成后保存最后一次有效负责人，保持独立鉴权。补充旧/新设计师的列表、详情、原图、ZIP 矩阵，覆盖 legacy 和 Studio、改派后追加归档、改派与删除并发，验证旧设计师拒绝、新负责人允许、删除前后结果一致。修复后重新 review-prepare，从 Stage 1 复核新候选。

## Stage 1：逐条核对

下表路径 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`；省略前缀的 `tasks/`、`archives/`、`studio/`、`execution/`、`management/`、`materials/`、`pictures/`、`plans/` 指 `backend/app/overseas/` 下对应模块，省略前缀的 Vue 文件指 `frontend/src/views/overseas/` 下文件。单项“完整”不覆盖 S1-H1，也不代表整体通过。

| Spec 条目 | 结论 | 代码与验证证据 |
|---|---|---|
| 仅有效海外 super_admin 删除；其他四角色即使本人任务也拒绝；单人单角色 | 完整 | `backend/app/overseas/permissions.py:23` 校验唯一角色，super_admin 才有 task.delete；`tasks/deletion.py:33` 重验权限；`tests/test_overseas_task_deletion.py:55` 四角色 HTTP 拒绝。reviewer 专项测试通过。 |
| 列表查看旁红色删除入口 | 完整 | `frontend/src/views/overseas/OverseasWorkspace.vue:54` 与 `OverseasTasksPage.vue:42`；`OverseasTaskDelete.vue:3` 能力守卫。已查看 `output/playwright/delete-skills/delete-failure-desktop.png`，符合既有 ArtTable/Element 风格。 |
| 名称确认、版本校验、取消不清理 | 完整 | `tasks/deletion.py:43`、`:46`；`OverseasTaskDelete.vue:5`、`:24`、`:46`、`:58`。`tests/test_overseas_task_deletion.py:125` 和真实浏览器脚本 `frontend/tests/overseas-delete-skills-real.browser.mjs:84` 以后覆盖错误名称、取消、正式确认。 |
| 明示永久清理范围及已归档保留 | 完整 | `OverseasTaskDelete.vue:7` 对应实际清理对象；不是指向未实现功能的引导。确认手机截图 `output/playwright/delete-skills/delete-confirm-mobile.png`，实际交互结果在 `real-result.json`。 |
| 持久 deleting/delete_failed、刷新可恢复、失败可重试、仅完成后移除 | 完整 | `tasks/models.py:88`、`tasks/deletion.py:36`、`:51`、`tasks/cleanup.py:55`、`:61`；`OverseasTaskDelete.vue:31` 轮询，`OverseasTasksPage.vue:97` 仅 deleted 移除。`fault-result.json` 两项故障交互通过，截图清晰显示失败与重试。 |
| 删除锁定后禁业务编辑、上传、对话、生成、归档和旧业务重试 | 完整 | `tasks/queries.py:21` 的写入任务锁守卫；`studio/queries.py:14`、`materials/service.py:88`、`pictures/review.py:17`、`plans/service.py:74` 复用。前端 `OverseasTasksPage.vue:12` 至 `:38` 切断操作。HTTP 最终日志有 new work fenced 证据。 |
| 撤销排队、运行先停止并核实进程与子进程；不明时保留 | 完整 | `tasks/deletion.py:17`、`cleanup_process.py:31`、`:49`、`:55`；运行进程身份验证、信号升级在 `cleanup_process.py:39`，进程组扫描在 `:14`。真实 surviving child 测试 `tests/test_overseas_task_deletion_process.py:17`；状态不明及迟到完成测试 `test_overseas_task_deletion.py:139`。 |
| 防新领取、重复请求归并、迟到结果不得重建对象 | 完整 | `execution/claims.py:69`、`queue.py:29`/`:60`；`execution/objects.py:29` 先持久记录所有权，`:36` 写存储前重验；`runner.py:146` 包裹实际收集。`tests/test_overseas_task_deletion_legacy.py:95` 覆盖写成功但响应丢失与迟到写拒绝。 |
| 真清理 Task/SKU/资料原件/解析/方案/审核/对话/附件/图片所有版本/jobs/events | 完整 | `tasks/cleanup_records.py:16` 显式依赖顺序删除全部业务表；`cleanup_files.py:18`/`:27` 收集业务对象和专属 orphan prefix；`:103` 删除后 stat 验证不存在。真实 HTTP `infra/identity-test/delete_skills_checks.py:78`、`:83`/`:90` 与 legacy 测试均验证实际清理。 |
| 旧工作流及 Studio 的全部私有 CLI home、轮次、日志、上下文 | 完整 | `cleanup_files.py:60` 从 Job UUID 与 Conversation UUID 构造确证归属目录，`:74` 检查路径/链接/硬链接，`:121` 清理。`test_overseas_task_deletion.py:81` 检查 home/.codex/sessions；`test_overseas_task_deletion_legacy.py:53` 检查两轮目录。 |
| 不清其他任务、共享 Skill、公共登录配置 | 完整 | `cleanup_files.py:49` 跨任务对象归属检测、`:74` 边界；只枚举有数据库归属或任务专属 prefix。`test_overseas_task_deletion.py:77`、`test_overseas_task_deletion_legacy.py:77`，真实 HTTP 最终日志检查其他任务/Skill/国内数据未变。 |
| 成功归档保留精确图片版本、SKU、元数据、文件独立 | 完整（权限另列失败） | `archives/models.py:12`、`:23` 独立字段与资产表；`snapshot.py:38` 按原版本身份取源并校验 SKU，`:58` 独立 key，`:60` 至 `:66` 校验源、复制后读取、数量。`test_overseas_task_deletion.py:67` 分别 0/1/2 张归档；真实 2/3 部分归档在 HTTP 脚本。 |
| 先保护归档再破坏性清理，失败保留原任务，历史归档兼容 | 完整（权限另列失败） | `cleanup.py:38` 至 `:46` 保护事务先提交；`snapshot.py:43` 兼容无独立资产的历史记录；迁移 `0013_task_deletion_archives.py:21` 回填元数据。`test_overseas_task_deletion_faults.py:19` 腐坏不清理、修复后重试；`:44` 中途故障后用持久清单继续。 |
| 删除后列表/详情/原图/ZIP 不依赖 Task、文件哈希与数量一致 | 完整（权限另列失败） | `archives/service.py:40`、`:47`、`:80`、`:89`、`:102` 独立查询；`cleanup_records.py:14` 解除 Task 关联；HTTP 最终实测 PNG/ZIP SHA256 相同。前端 `OverseasArchiveDetail.vue:9` 显示“原任务已删除”，不跳失效任务。 |
| 归档保持原权限，删除不得扩大/丢失访问 | **部分实现，HIGH** | 无改派场景拒绝陌生人已测；合法改派后仍使用首次负责人，S1-H1 实证失败。不能把静态角色矩阵通过当作动态授权通过。 |
| 并发归档/删除顺序确定，成功归档必保留；重启/重复请求不复活 | 完整（权限并发修复仍需补测） | 共同 Task 行锁：`tasks/deletion.py:34`、`studio/service.py:17`；`tests/test_overseas_deletion_postgres.py:85` 两种顺序、`:111` 双请求双维护，真实 PostgreSQL。持久 manifest 位于 `cleanup.py:42`，不是进程内进度。 |
| 14 包全部保留、3 对英文同名不去重、7 目录数量正确 | 完整的离线包 | `management/skill_inventory_20261013.json:1` 映射；`skill_install.py:14` 唯一命名、源边界；`:58` 生成完整 manifest。reviewer 逐文件核对 sourceEntries/entries 的字节与 SHA256：14 包、181 文件、111321938 字节，源 111321820 字节，差 118；未执行 Skill 正文或包内脚本。 |
| 沃尔玛原版与新版 9.27 区分、各自指令保留 | 完整的离线包 | inventory 中 original / revised-0927 两个唯一 id；`skill_install.py:46` 只替换对应原 name 的必要自引用，manifest 列出 adaptedFiles。reviewer 校验两个源目录及目标文件哈希，14 个 id 全部唯一。 |
| 全量参考图/脚本资源，不靠旧网页 20 MiB ZIP，不安装国内或个人目录 | 完整的安装实现 | `skill_install.py:37` 遍历 entries 全复制，`installed_tree.py:14` 支持 64 MiB 单文件/256 MiB 单包；`installed_catalog.py:23` 强制 overseas、生产白名单。`test_overseas_installed_skills.py:121` 大资源、`:150` 国内拒绝。正式实际安装未执行。 |
| 管理只读名称/描述，搜索刷新；移除写入口及 write API | 完整 | `OverseasSkillCatalog.vue:3` 至 `:21` 仅两列；`management/router.py:26` Skill 仅 GET。`test_overseas_installed_skills.py:22`/`:57` 和 `infra/identity-test/installed_skill_checks.py` 检查实际目录与写接口关闭。已目视 skills-desktop.png，列名为名称/描述。 |
| 完整长描述、窄屏、加载/空/失败真实区分 | 完整 | `OverseasSkillCatalog.vue:5` 至 `:9`、`:24` 换行；`installed_catalog.py:77` 空目录，`:92` 错误 503。`test_overseas_installed_skills.py:75`，浏览器结果及 skills-long-description-mobile.png / management-faults 证据。 |
| 页面与工作台用同一真实目录，不下发整套指令历史/私有路径 | 完整 | `management/skills.py:5` 与 `studio/queries.py:80` 复用 listing；`installed_catalog.py:96` 仅 id/name/displayName/description。HTTP 最终结果验证两者一致。 |
| 每轮冻结、旧轮次不受安装更新影响、完整所选 Skill 只读挂载 | 完整的实现及本地资源验证；生产 sandbox 待验 | `management/installed_catalog.py:102` 冻结 release/checksum，`:112` 执行再次验证；`execution/materials.py:21` 完整复制；`backend/app/execution/workspace.py:101` 仅选中目录双 ro-bind。`backend/tests/test_overseas_installed_skills.py:22` 更新后旧快照仍读取旧资源；`:156` 缓存失效。生产 Skill probe 尚未运行，不宣称生产挂载已成功。 |
| 发布只改海外服务/必要前端、同目录、排空/备份/失败关闭，不做生产删除/模型调用 | 发布准备具备，生产尚未执行 | `scripts/release/overseas-update-deploy.py:73` 至 `:114` 的顺序；`overseas-skills-runtime.py:54` 核查旧空卷与包哈希，`:88` API/native inode、14/181、非 root sandbox；`skill_probe.py:15` 真实 sandbox 哈希与只读探针。准备脚本不等于生产证据。 |

## Spec 漂移与 UI

- 新增独立归档详情/内容 API、TaskDeletion/ExecutionObject/ArchiveAsset 与运维安装入口均对应本轮删除保护和完整安装要求；未发现与本轮无关的新业务功能。证据：`backend/app/overseas/archives/router.py:31`、`tasks/models.py:88`、`archives/models.py:23`、`management/skill_install.py:179`。
- Stage 1 已核对设计约定与代码，并目视提供的 Skill 桌面、删除失败桌面、删除后归档手机截图。使用既有白色圆角卡、ArtTable、Element 蓝色操作、红色危险入口；手机归档显示原图、SKU、下载及“原任务已删除”。对应前端位置见上表。截图是隔离环境，不是生产效果。
- 因 Stage 1 存在 HIGH，没有开展 Stage 2 的邻居页面实际浏览器对比、全面代码质量和安全扫描；这些不能在本报告登记 PASS。

## 测试及编译证据

reviewer 独立执行：只读源码 bind、`--init --network none`、镜像 `hx-overseas-delete-skills-test:local`，测试包括 task_deletion、faults、legacy、process、installed_skills、deletion_migration。原始结束输出：

```text
................................s                                   [100%]
37 passed, 1 skipped, 2 warnings in 16.08s
```

迁移依赖实际 PostgreSQL 的项在该独立无网络命令跳过，不计为 reviewer 运行通过；主 Agent 提供的专用 PG 日志已读取：`output/pg-regression-full-20261013.log`。

读取的最终日志原始输出：

```text
# output/delete-skills-backend-final.log
1951 passed, 166 skipped, 15 warnings in 239.39s (0:03:59)

# output/pg-regression-full-20261013.log
70 passed, 2044 deselected, 2 warnings in 92.35s (0:01:32)

# output/delete-skills-frontend-tests.log
ℹ tests 319
ℹ suites 0
ℹ pass 319
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
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

现有回归全部通过仍未覆盖“归档后改派”的动态权限路径，因此不能消除 S1-H1。后端全量 166 项跳过也不能计为已验证；生产安装、实际 CLI sandbox 与真实成图效果没有本轮通过结论。

编译日志另有原始工具警告：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

主 Agent 另报告生产依赖 audit 为 0 critical、36 high、34 moderate、1 low，且本轮未改依赖；本报告未进入 Stage 2，不把该历史依赖结果转写为新漏洞结论或安全 PASS。

## 交接

Stage 1 功能/权限修复交主 Agent；reviewer 未改源码、未提交、未部署、未写 `.needs-review`。修复后必须生成新 candidateId，并以新快照从 Stage 1 复核；当前候选没有批准资格。生产步骤保持未完成。
