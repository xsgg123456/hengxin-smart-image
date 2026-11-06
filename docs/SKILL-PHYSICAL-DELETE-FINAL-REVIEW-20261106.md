# Skill 物理删除独立审查（最终候选）

- candidateId：`aa7725195abd5b5bb5e5fd012c75eac8e7259fa191c19bbfeb5a016c6e57522d`。
- 审查范围：当前全部 git diff、未跟踪的 backend Skill 模块/测试、全部 `scripts/release/skill-physical-*.py`、Vue 删除交互及生成类型声明；包括 AGENTS.md 的净释放验收规则。需求依据 `Product-Spec.md:1415`、`DEV-PLAN.md:1642`、`docs/SKILL-PHYSICAL-DELETE-20261106.md:5` 至末尾完整合同。未将其他历史 Phase 当成本轮新增要求。
- 已完整读取 AGENTS.md、code-review SKILL.md、HARNESS-REVIEW.md、实施合同及前两轮失败报告。按固定快照、Stage 1 逐条契约、Stage 2 质量/安全/视觉顺序执行。只写本报告；未修复、提交、部署或调用模型。
- 起始及审查完成时 `review-status.currentId` 均与候选相同，`approved=false`；期间未观察到受审代码变化。报告不代替主 Agent 的 review-approve。

## Stage 1：Spec Compliance

本轮代码实现 **PASS**。未发现 HIGH/MEDIUM/LOW 新缺陷。生产提交、发布与存量回收属于后续执行验收，不能由代码 PASS 推定已完成。

以下路径简写：`M/` 为 `hengxin-smart-image/backend/app/overseas/management/`，`E/` 为同级 `execution/`，`T/` 为 `hengxin-smart-image/backend/tests/`，`F/` 为 `hengxin-smart-image/frontend/`，`R/` 为 `scripts/release/`。行号均为本候选实际文件行号。

| 合同逐项要求 | 结论 | 实现与验证证据 |
| --- | --- | --- |
| 目标1：名称+内容独立实体，release 只有小型索引；相同内容复用，更新 A 不复制 B | 完整实现 | `M/skill_objects.py:21` 写 schema 2 manifest，`:87` 验证并复用已存在对象；`T/test_skill_object_storage.py:46` 真实树比较 B 的 inode/mtime、对象数量、相同内容 release 与仅 manifest 的 release 目录。 |
| 目标1：完整字节、空目录、权限检查、下载一致 | 完整实现 | `M/skill_objects.py:45` 全量复制校验，`M/installed_catalog.py:57` 校验清单，`:73` 定位实体，`M/skill_downloads.py:28` 410/逐文件哈希；`T/test_skill_object_storage.py:46` 二进制与空目录，`:204`、`:227` Linux 权限/链接检查。浏览器 result.json 111 项上传清单与保存读回一致。 |
| 目标2：清除中央无用实体、旧安装副本、完成上传暂存，保留历史独立副本 | 完整实现 | `M/skill_cleanup.py:61` 明确三类清理目标，`:114` 全部预验后执行；`T/test_skill_physical_cleanup.py:29` 在真实中央/暂存树中途注入删除失败并重试；`T/test_skill_physical_history.py:87` 删除中央后仍从原 owner 准备原始 Skill。 |
| 目标2：清理实际完成才成功，真实净释放、失败持久重试 | 完整实现 | `M/skill_publication.py:35` cleanup 完成才记审计完成，`:91` 持久 pending 与事务；`M/skill_preparation.py:90` 首次操作前固定中央/历史/元数据基线，`:123` 重试沿用；`M/skill_cleanup.py:132` 减去新增历史占用；13 个 preparation 用例及真实部分删除测试通过。 |
| 目标3：排队、运行、收取、退出未确认阻删，不强停 | 完整实现 | `M/skill_references.py:23` 非终态或未确认退出均 busy，`:27` Task→admission 锁序与删除判断；`T/test_skill_physical_history.py:134` 八种在途状态均 409，指针/字节不变；没有在删除路径终止任务的调用。 |
| 目标3：更新后在途任务仍读旧冻结版本 | 完整实现 | `M/skill_publication.py:133` retained 合并 active_keys，`M/skill_cleanup.py:74` 保留未迁移的活跃旧树；`T/test_skill_physical_history.py:152` 更新后新旧分别读回，终态后删除再从原 owner 读取旧内容。 |
| 目标4：优先本会话副本，核对原冻结清单，不跨会话、不改 payload/聊天 | 完整实现 | `E/skill_content.py:19` owner 历史优先；`E/skill_history.py:12` home/round 同属校验，`:22` 文件全集/哈希/权限检查，`:52` 只搜索本 owner；`T/test_skill_physical_history.py:87`、`:179`、`:217` 覆盖原 payload/消息不变、陌生 owner 与伪造 workspace 拒绝。 |
| 目标4：缺少时从完整源补齐并计入占用；非 Studio 也保留独立资料 | 完整实现 | `M/skill_references.py:52` 校验 DB 所属并选择 Studio conversation 或普通 job 根，`:82` 保全；`E/skill_history.py:115` 缺失复制/验证。历史测试 `:87` 四组合覆盖已有/缺失与 Studio/analysis，核对 session、附件、参考图、工作文件原字节/inode/mtime；准备账本测新增历史抵扣。 |
| 目标4及顺序3：历史副本成为唯一源前完成持久化，磁盘故障不得继续删除 | 完整实现；前轮 HIGH 已修 | `E/skill_history.py:71` 新目录同步自身和父级，`:89` 对最终副本每个文件、内部目录、到 owner 的祖先、lock、owner 父级以及 Studio execution 根建立同步边界；`:119` 已有副本也 durable；`M/skill_references.py:113` 不跳过已有副本。`T/test_skill_history_durability.py:13` 四组合对文件/owner 同步注入失败，503、中央仍在、preparing 留存，重试同步完成后才 rmtree；`:54` 验证 Studio 祖先。独立执行五项全部通过。 |
| 目标5：旧索引保留，引用驱动 GC，不能只按时间或启用状态删 | 完整实现 | `M/installed_catalog.py:35` 支持 schema 1/2，`:180` 原冻结元数据可解析；`M/skill_maintenance.py:27` 对磁盘 input 与 DB owner 引用匹配，`:49` gate/所有 Job 排空；`T/test_skill_physical_maintenance.py:44` 三套旧树回收、索引/当前内容/历史保持，`:91` 未归属 input 在修改前拒绝。 |
| 目标6：API/worker 中央只读，publisher 受控写，历史路径/业务/属主限定 | 完整实现 | `M/skill_publication.py:20` 角色及指定账号双检；`M/skill_publisher.py:167` root、进程排他锁、UDS 0660；`M/skill_references.py:44` 固定海外 execution 根与 `:52` DB owner 绑定；`R/skill-physical-runtime.py:99` 仅 publisher 加明确历史根挂载，`R/skill-physical-deploy.py:189` 核验实际 UID、挂载及 socket；未加模型挂载/前端历史入口。 |
| 顺序1：安装、冻结、下载兼容完整包与旧清单 | 完整实现 | 上述对象/目录/下载模块；`M/skill_install.py:118` 离线安装复用对象且无引用证明时不自行 GC；`T/test_skill_offline_objects.py:36`、`:61`、`:81` 覆盖 portable bundle、旧冻结保留和复制失败指针保持。 |
| 顺序2：真实临时文件保全，跨会话及链接攻击拒绝 | 完整实现 | `T/test_skill_physical_history.py:87` 删除后实际调用 materials.prepare；`:204` 硬链接拒绝；`T/test_skill_physical_cleanup.py:108` 链接/junction 越界拒绝。独立50项真实 DB/目录专项通过。 |
| 顺序3：首次/最后一项、重复删除、权限/版本、磁盘错误和并发事务 | 完整实现 | `M/skill_publication.py:152` 固定 release/checksum/version、审计重放；`T/test_overseas_skill_transfers_failures.py:42`、`:56`、`:95`、`:121`、`:141` 覆盖首次复制、指针、pending、DB rollback 与并发；`T/test_skill_physical_cleanup.py:29` 最后一项删除和重复回收结果一致。 |
| 顺序3：无需旧浏览器状态也能恢复提交后的清理 | 完整实现；首轮问题已修 | `M/skill_publisher.py:25` lifespan 启动/每5秒同锁恢复，`:70` pending health 503；`T/test_skill_publisher_recovery.py:10` 真实 TestClient lifespan 解除磁盘故障后自动完成，普通目录 GET 恢复。此测试纳入独立50项。 |
| 顺序4：沿用确认框，历史保留/运行中阻删、真实释放反馈 | 完整实现 | `F/src/views/overseas/admin/SkillFolderActions.vue:43` 固定版本、二次确认、原请求重试；`:53` 实际 reclaimedBytes 格式化；`F/src/api/overseas/skill-transfers.ts:63` 拒绝负数/缺失/非安全整数；`OverseasLiveSkills.vue:25` 503 保留行，`OverseasSkillCatalog.vue:17` 保留表和重试入口。实际截图确认/失败/成功分别匹配文案，没有死引导。 |
| 顺序4：组件、类型、构建、浏览器 | 已验证 | reviewer 独立全前端529通过、typecheck成功；读取真实生产 build 日志成功。浏览器脚本 `F/tests/skill-folders.browser.mjs:98` 窄屏宽度断言、`:113` 正确等待释放提示；result.json 六项 errors=[]。浏览器503为前端拦截注入，真实后台删除故障另由50项专项验证，二者不混称。 |
| 顺序5：固定快照/中文提交/隐私制品/真实安装身份/基线/排空/备份/保持国内 | 工具完整；提交部署待执行 | `R/skill-physical-package.py:59` 非candidate要求干净受审提交、源码/制品哈希与隐私校验；`R/skill-physical-baseline.py:12` 固定17文件和各服务基线；`R/skill-physical-deploy.py:28` candidate禁切生产，`:49` 无关容器保持，`:144` 双gate排空/不SIGKILL，`:174` 数据库与native备份。中文提交规则 `AGENTS.md:60`。独立发布工具21项通过。 |
| 顺序6：全量迁移、外部可恢复备份、原索引、全历史保留与净量/健康 | 工具完整；外部备份已核验，生产GC待执行 | `R/skill-physical-backup.py:137` 去重备份、`:162` 独立空目标恢复/元数据核验；reviewer 对本地备份执行 verify 通过（17,678项、444对象）。`R/skill-physical-maintenance.py:88` 绑定基线/实际树/净量/历史receipt；`R/skill-physical-recovery.py:29` GC后禁止回退旧reader、`:72` 服务只读目录/健康。最终生产净释放量和当前下载/选择/准备尚待执行，不能引用预计6.57GB作实际结果。 |

### 上两轮问题关闭情况

- 准备阶段失败后净释放虚高：固定首次 `.preparing.json` 基线，所有新增历史及目录元数据计入；`T/test_skill_preparation_accounting.py:25`、`:45`、`:75`、`:176` 的复制后失败、提升后失败、追加owner、commit回滚独立通过。
- 整页刷新后恢复不可达：publisher自主恢复，`T/test_skill_publisher_recovery.py:10` 独立通过。
- 浏览器断言与真实提示不一致：脚本 `F/tests/skill-folders.browser.mjs:113` 已匹配“Skill 已删除，释放”；已读取六项成功结果并打开成功截图。
- 历史副本 fsync 边界缺失：新建/已有副本和文件/祖先同步均覆盖；本轮五项故障注入独立通过，不将 Windows 的目录fsync no-op说成 Linux 持久化验证。

完整实现、部分实现、未实现分类：审查范围内实现项均完整；没有发现部分或完全缺失的代码功能。提交、上线、生产GC和最终生产测量明确为尚未执行的交付步骤。未发现 Spec 漂移：新增私有维护路由 `M/skill_publisher.py:154` 对应授权迁移，公开 `M/skill_transfer_router.py:20` 至 `:79` 无此路由；生成声明清理与版本0.2.65不新增产品功能。

## Stage 2：Code Quality

在 Stage 1 无阻断问题后执行，结论 **PASS**。没有新增需修复的质量或安全问题。

| 检查 | 结论与证据 |
| --- | --- |
| 命名、职责和文件大小 | 对象、历史、账本、清理、事务、维护分别独立；例如 `M/skill_objects.py:1`、`E/skill_history.py:1`、`M/skill_preparation.py:1`。按全部受审 py/ts/vue/mjs实际统计，最大 `R/skill-physical-deploy.py:300`，没有超过300行文件。 |
| 类型与异常 | 删除DTO明确 `F/src/api/overseas/skill-transfers.ts:6`，失败unknown按IdentityError细分；新增前端实现无any绕过。`M/skill_publisher.py:54` 存储/完整性异常503，`:25` 保留持久状态并后台恢复；`:70` 不伪报健康。独立typecheck exit 0。 |
| 安全扫描 | 检查受审源码及危险模式：未发现硬编码真实密钥、eval、innerHTML或新增动态SQL输入。`M/skill_cleanup.py:35` 受控相对路径及UUID/hash白名单，`:114` 全部目标预验；`E/skill_history.py:22` 与 `studio/context_fs.py:25` 拒绝链接/硬链接；`R/skill-physical-backup.py:86` 校验恢复路径/类型/元数据。绝对路径为固定生产白名单，非用户私有路径泄露。维护SQL `R/skill-physical-maintenance.py:80` 与`:145`只含固定语句和内部布尔值。 |
| 权限隔离 | `M/skill_transfer_router.py:15` 与 `M/skill_publication.py:20` 双侧授权；公开写路由保留browser_request；UDS无公网端口，publisher精确挂载；`R/skill-physical-deploy.py:189`、`R/skill-physical-recovery.py:93` 实际检查权限/只读。 |
| 测试真实性 | 历史/清理使用实际SQLite、临时目录、原字节/inode/mtime和真实API，注入发生在实际fsync/rmtree/commit边界；不是用mock返回成功取代行为。`T/test_skill_history_durability.py:13` 的移除回调断言同步先于删除；`T/test_skill_preparation_accounting.py:21` 同统计范围总量；`T/test_skill_physical_history.py:87` 真正删除中央后重新prepare。Linux权限专用用例需Linux证据，不以Windows跳过算通过。 |
| UI 与邻居实际渲染对比 | 已独立打开 `output/playwright/skill-folders/03-delete-confirm.png`、`06-delete-failed.png`、`06-empty.png`、`02-saved-and-verified.png`、`output/skill-physical-20261106/narrow-settled.png`，并打开既有 `output/playwright/delete-skills-final-review/monitor-desktop.png` 与 `output/playwright/local-skills-neighbor-settings.png` 对照。新交互保留蓝色主按钮、白卡/浅边框、Element确认框、12px状态文字/1.6行高与8px动作间距（`SkillFolderActions.vue:62`），桌面失败可重试、成功释放量可读；390px卡片和提示无页面水平溢出，表格沿用内部横向滚动。没有新设计稿，以既有管理页为基准。未使用动画中的05-narrow作缺陷证据；此项是独立目视保存的实际渲染，未声称本reviewer另启浏览器重跑。 |

## 原始验证输出与证据边界

reviewer 独立执行六个历史/清理/准备/恢复文件：

```text
50 passed, 2 warnings in 95.88s (0:01:35)
```

两个warning来自既有Starlette/httpx、anyio弃用提示；没有失败或skip。

reviewer 独立发布工具测试及全部受审Python编译：

```text
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.424s

OK
COMPILE_OK 40
MAX_LINES (300, 'scripts/release/skill-physical-deploy.py')
OVER_300 []
```

reviewer 独立前端回归/类型检查，进程exit 0：

```text
ℹ tests 529
ℹ suites 0
ℹ pass 529
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 44450.136

> hengxin-smart-image-frontend@0.2.65 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

读取主Agent构建证据 `output/skill-physical-20261106/frontend-build.log`，不是本reviewer重构建：

```text
> hengxin-smart-image-frontend@0.2.65 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4822 modules transformed.
✓ built in 37.98s
```

pnpm额外输出已有配置位置warning（pnpm.overrides/onlyBuiltDependencies不再从package.json读取）；未新增依赖或变更包管理配置，本轮没有将其写成新增缺陷或隐藏警告。

独立备份读取验证原始输出：

```json
{"status": "BACKUP_VERIFIED", "indexSha256": "7efc8b0f3358a5c846fa955c9862abdb2d571e1cbf14562015605c750736b11a", "entries": 17678, "uniqueFiles": 444, "logicalBytes": 6807730066, "payloadBytes": 219106064}
```

主Agent的 `output/skill-physical-20261106/library-restore.log:2` 为远端隔离恢复证据，状态 `ISOLATED_RESTORE_VERIFIED`、同indexSha256/条目/字节；恢复函数 `R/skill-physical-backup.py:180` 按hash、uid/gid、mode与纳秒mtime全量比较。reviewer没有另连生产重做恢复；已独立校验下载的实际444个payload。备份219,106,064B是备份新增占用，不是生产净释放量。

主Agent全后端和修改前基线的原始结尾：

```text
backend-full.log: 9 failed, 2817 passed, 442 skipped, 6 warnings in 648.73s (0:10:48)
baseline-failures.log: 9 failed, 43 passed, 2 warnings in 11.85s
```

已核对两份日志全部9个FAILED名称相同，涉及 configuration、management_freeze、pictures、pictures_protocol，受审diff没有修改这四个文件。不声称全后端通过；本次代码PASS基于改动范围审查、新增故障专项、前端及安装验证，不能覆盖上述历史失败。

### 当前候选 Linux 实际身份安装验证

主Agent执行，reviewer读取 `output/skill-physical-20261106/candidate-final-linux.log:2` 至`:3` 的实际结束标记：

```text
PREPARED_IMAGES_BUILT_NO_PRODUCTION_SWITCH
API_PUBLISHER_NATIVE_ISOLATED_TESTS_PASSED
```

目标为 `/opt/hengxin-skill-physical-candidate-aa7725195abd/work`，不引用先前候选结果。主Agent报告该目录的实际角色日志与 `INSTALL_TESTS_PASSED` 已生成：API UID10001为172 passed/1 deselected，publisher root为173 passed，native UID999为58 passed，native-root为14 passed；各角色均无skip。API唯一deselected为需要root的保护目录写入用例，该用例在publisher/native-root无过滤运行。`R/skill-physical-test.py:14` 检查真实UID并编译全部17个实际文件，`:47` 使用隔离PG及network-none容器，`:58` 明确该root-only过滤，`:70` publisher跑未过滤集合。新增历史持久化五项位于API及publisher集合（`R/skill-physical-package.py:23`），因此包含真实POSIX fsync路径验证，而不止Windows调用探针；没有模拟整机断电，也未调用真实模型。

reviewer随后读取已下载的 `output/skill-physical-20261106/final-linux/` 四份本候选原始日志，确认上述数字；各日志末尾原文：

```text
api-installed-tests.txt:
172 passed, 1 deselected, 2 warnings in 69.09s (0:01:09)
publisher-installed-tests.txt:
173 passed, 2 warnings in 71.14s (0:01:11)
candidate-tests.txt:
58 passed in 6.59s
candidate-root-tests.txt:
14 passed in 2.33s
```

依赖风险边界：已读取 `output/skill-physical-20261106/dependency-audit.json` 的原始汇总：0 critical、39 high、35 moderate、5 low。本轮 package.json 仅改版本、锁文件无diff，没有新增依赖；因此此处报告既有依赖风险，不将代码范围的安全扫描PASS表述为项目依赖无漏洞。

## 交接

仅同一candidateId可用于本报告审查凭据。主Agent登记两阶段PASS后，继续中文提交与受审release制品构建、生产关闭接纳/排空/备份、所有reader切换、存量迁移回收及同统计范围净释放验收。生产当前下载/选择/准备、历史记录/上下文/附件/工作文件保全、国内健康需附最终实测证据；本报告不声称已经部署、实际释放6.57GB或验证了真实模型续聊。
