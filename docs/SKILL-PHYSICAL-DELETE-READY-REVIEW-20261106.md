# Skill 物理删除候选独立审查（第二轮）

- candidateId：`bf1fca7348ccc784558ef69e2b7b041b33e5992b7771cee46d5d5cfcfdaf61ea`。
- 范围：主 Agent 指定的全部 `git diff`、新增 backend 模块与测试、前端变更、全部 `scripts/release/skill-physical-*.py`。需求源为 `docs/SKILL-PHYSICAL-DELETE-20261106.md:5`、`Product-Spec.md:1415`、`DEV-PLAN.md:1642`；不把产品其他历史阶段重新算作本轮开发范围。
- 方法：读取 code-review skill，逐条核对合同与代码，独立执行恢复/账本测试、发布工具测试及真实隔离数据库/文件的持久性调用探针。未修改产品或发布代码，未提交、部署或调用模型。
- **Stage 1：FAIL，1 个 HIGH。Stage 2：未执行。** 按 skill 的 HIGH 停止规则，不登记两阶段 PASS，不得据本报告批准提交。
- 开始及审查结束前 `harness.py review-status` 的 currentId 均为上述候选，approved=false；未观察到受审源码变动。探针仅写入 Git 忽略的 output 目录。

## Stage 1：HIGH S1-04，历史保全没有完成持久化边界就删除中央源

合同 `docs/SKILL-PHYSICAL-DELETE-20261106.md:8` 要求历史独立副本保留，`:10` 要求缺失副本先补齐并校验，`:18` 要求磁盘错误、崩溃恢复及失败不能误报完成。

`backend/app/overseas/execution/skill_history.py:71` 的 `_directory` 仅 mkdir/chown；`:86` 首次创建 `owner/skill-history`，`:108` 至 `:111` 只同步新树内部及 `skill-history` 本身，从未同步容纳这个新目录项的 `owner`。`backend/app/overseas/management/skill_references.py:100` 同样可能新建 base/owner，但不落盘其父目录项。接着 `skill_publication.py:178` 的保全调用返回，`:187` 发布和 `skill_cleanup.py:127` 真实删除中央源，并可返回成功。

因此，程序只证明历史副本在当前内核缓存中可读，没有证明新路径已稳定落盘。Linux `fsync` 手册明确要求对包含目录项的父目录另行同步；对子目录/文件的同步不能代替这一保证。[Linux man-pages fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)。整机故障后若新历史入口丢失，中央源已回收，原冻结 Skill 将不可再恢复。这是删除前历史保全的正确性缺口。

独立探针 `output/skill-physical-20261106/reviewer_durability_probe.py:8` 使用现有真实 API、publisher、隔离数据库和真实临时文件：创建没有 Skill 副本的已完成 Studio 会话，在 `fs.sync(owner)` 注入磁盘错误并记录所有同步路径，然后删除。实际始终没有执行该同步，删除仍成功且中央实体消失：

```text
DURABILITY {'status': 200, 'historyExists': True, 'centralExists': False, 'ownerSyncCalled': False,
 'syncPaths': ['skill-history\\.stage-…\\folder-test',
               'skill-history\\.stage-…\\folder-test\\assets',
               'skill-history\\.stage-…\\folder-test\\assets',
               'skill-history\\.stage-…\\folder-test\\empty',
               'skill-history\\.stage-…\\folder-test',
               'skill-history\\.stage-…', 'skill-history']}
1 passed, 2 warnings in 4.08s
```

输出中仅随机 staging 名做省略；布尔值和状态码为原始输出。这个 PASS 表示成功证实缺少调用，不表示产品通过。探针运行于 Windows，证明实际生产代码的调用顺序；Linux 持久性风险依据上述官方语义，并未声称模拟了真实断电丢盘。

修复边界还应包括“已有副本直接复用”：`skill_references.py:106` 找到副本便跳过 `preserve`；`skill_history.py:83` 也直接返回。特别是非 Studio 的旧 round 副本由 `execution/skill_copy.py:7` 写出，`:21` 至 `:24` 仅 close/chmod，没有 fsync。历史字节哈希正确不等于持久化完成。本轮物理回收首次使其可能成为唯一副本，所以删除前应对最终选中的历史文件及路径建立可验证的持久化边界，而不只对新拷贝补一个调用；新文件 chmod/chown 后的最终元数据也应纳入该边界。

修复验收：新历史和已有历史两路径，覆盖已有 owner、新建 owner/base、中途 fsync 失败及重试。任何必要的历史持久化失败必须在发布/物理回收之前拒绝，中央源和恢复凭据保留。对最终文件及逐层目录的同步次序提供 Linux 证据；无须调用模型。

## 上轮问题复核

| 原问题 | 结论 | 本候选证据 |
| --- | --- | --- |
| S1-01 准备阶段新增副本漏计 | 修复已验证 | `management/skill_preparation.py:90` 首次复制前记录中央、owner 历史和目录元数据基线；`:123` 重试仍从原基线计算；`skill_publication.py:41` 仅 cleanupComplete 后清除；`tests/test_skill_preparation_accounting.py:25` 等 13 用例独立通过。覆盖历史已复制、中央已提升、提交回滚、增加新 owner、跨名拒绝、维护接续和篡改拒绝。 |
| S1-02 整页刷新后恢复不可达 | 修复已验证 | `management/skill_publisher.py:25` lifespan 启动恢复并每 5 秒在同一锁内重试，`:70` pending 返回 health 503；`tests/test_skill_publisher_recovery.py:10` 独立 TestClient lifespan 用例证明解除磁盘故障后无需旧删除参数即可恢复目录。 |
| S1-03 浏览器成功文案断言错误 | 已修复，主 Agent 浏览器日志支持 | `frontend/tests/skill-folders.browser.mjs:113` 等待真实“Skill 已删除，释放”；`SkillFolderActions.vue:53` 发出相同文字。读取 `output/skill-physical-20261106/browser.log`：6 项通过、errors=[]。不是本 reviewer 独立浏览器重跑，也不是 Stage 2 视觉结论。 |

以上 backend/frontend 路径均位于 `hengxin-smart-image/` 下；表内 management/execution 路径位于 `backend/app/overseas/` 下。

## 合同完整覆盖

“代码覆盖”表示已定位到实现与对应测试，不覆盖 S1-04，不等于整体验收 PASS。下列逐条覆盖目标及顺序全部条目。

| 条目 | 结论 | 代码与验证证据 |
| --- | --- | --- |
| 目标 1，名称+内容独立对象、小索引、相同内容复用、更新 A 不复制 B | 代码覆盖 | `management/skill_objects.py:21` schema 2 索引、`:87` 验证复用；`tests/test_skill_object_storage.py:46` 对比 B 的 inode/mtime、重复发布及对象数量。 |
| 目标 1，完整字节、空目录、权限及下载一致性 | 代码覆盖；最终 Linux 身份证据待主 Agent补齐 | `skill_objects.py:45` 逐项复制与验包；`installed_catalog.py:73` 定位对象；`skill_downloads.py:28` 固定版本下载及 410；对象测试 `:46`、`:204`、`:227` 覆盖字节/空目录/权限。 |
| 目标 2，删除中央对象、旧安装副本和已完成上传暂存 | 代码覆盖 | `skill_cleanup.py:61` 枚举白名单路径，`:114` 全量验证后 rmtree；`tests/test_skill_physical_cleanup.py:29` 真实半途删除失败及重复重试。 |
| 目标 2，成功必须实际完成、真实净回收及持久恢复 | 部分实现，S1-04 阻断 | `skill_publication.py:35` 清理完成后记审计；`skill_preparation.py:90`、`skill_cleanup.py:132` 统一原始中央基线减新增历史；上轮漏计已修，新的历史持久化边界仍不满足。 |
| 目标 3，所有在途及退出未确认任务阻删、不强停 | 代码覆盖 | `skill_references.py:23` busy 覆盖非终态和未确认退出；`:27` Task 锁、删除标记和 admission gate 顺序；`tests/test_skill_physical_history.py:134` 八种状态拒删且指针不动。 |
| 目标 3，更新保留在途旧版本 | 代码覆盖 | `skill_publication.py:133` retained 加 active_keys；`skill_cleanup.py:74` 未迁移在途旧树保留；`test_skill_physical_history.py:152` 真实新旧包读回及终态后删除。 |
| 目标 4，优先本会话副本、冻结清单精确验证、禁止跨会话 | 代码覆盖 | `execution/skill_content.py:19` 本 owner 优先；`skill_history.py:12` home/round 身份一致，`:22` 文件全集/哈希/权限；历史测试 `:87`、`:179`、`:217` 验证异 owner、payload 伪造、链接及 workspace 混配拒绝。 |
| 目标 4，缺失补齐、非 Studio、保留 session/上下文/附件/工作文件 | 部分实现，S1-04 阻断崩溃保证 | `skill_references.py:52` DB 所属校验及业务路径、`:82` 保全；`test_skill_physical_history.py:87` 四组合核对原文件字节/inode/mtime 和数据库 payload/turn/transcript，删除后真实 materials.prepare 可读；尚缺持久化边界。 |
| 目标 5，索引保留、引用驱动 GC、schema 1/2 兼容 | 代码覆盖 | `installed_catalog.py:35` 两种索引验证；`:73` schema 1 旧树或中央对象、schema 2 不回退；`skill_maintenance.py:27` 未归属冻结磁盘 input 拒绝；`:49` 全任务排空+gate；`tests/test_skill_physical_maintenance.py:44` 旧树迁移及目录/记录保留。 |
| 目标 6，中央只读、publisher 受控写、历史路径/业务/属主边界 | 代码覆盖；未声称生产已切换 | `skill_publication.py:20` 角色+指定账号；`skill_publisher.py:167` root/独占锁/UDS 0660；`skill_references.py:44` 固定海外执行根、`:52` DB owner；`scripts/release/skill-physical-runtime.py:99` 只给 publisher 新历史挂载，`skill-physical-deploy.py:189` 验证实际 RW/UID/UDS。 |
| 顺序 1，独立存储与完整安装/冻结/下载验证 | 代码覆盖 | 上述对象与目录模块；`tests/test_skill_offline_objects.py:39` 离线 bundle 仍完整，发布索引小型化；`:65` 离线安装不自行 GC 未知历史引用。 |
| 顺序 2，历史和安全隔离专项 | 部分实现 | 上述历史测试与调用探针；正常态保全有证据，崩溃持久性缺口见 S1-04。 |
| 顺序 3，事务/在途/物理清理/幂等/权限版本/磁盘错误并发 | 部分实现 | `skill_publication.py:91` DB/指针日志；`:152` 固定删除版本及审计重放；`tests/test_overseas_skill_transfers_failures.py:121` commit 回滚、`:141` 并发；准备阶段恢复新增 13 用例独立通过，S1-04 仍阻断生命周期验收。 |
| 顺序 4，确认框/历史保留与运行中提示/释放量/浏览器 | 代码和主 Agent 浏览器证据覆盖 | `SkillFolderActions.vue:43` 二次确认、冻结 pendingRemoval、错误重试与成功量；`OverseasLiveSkills.vue:25` 503 保留旧列表；`frontend/src/api/overseas/skill-transfers.ts:63` 严格校验非负安全整数；browser.log 的真实上传/保存/更新/删除失败重试六项，窄屏断言见 browser.mjs:98。本轮无新增设计稿，沿用现有组件。 |
| 顺序 5，固定候选/中文提交、隐私制品、基线、排空、备份恢复、国内保持 | 工具代码覆盖；未实施交付 | `skill-physical-package.py:59` 候选/受审提交、隐私/hash；`skill-physical-baseline.py:14` 17 文件含 native 缺失依赖；`skill-physical-deploy.py:83` 双镜像与 native 基线、`:144` 双 gate/稳定排空/不 SIGKILL、`:174` 备份；`:49` 无关容器固定。独立发布 21 测试通过。此候选 Stage 1 FAIL，不能提交部署。 |
| 顺序 6，外部备份、全历史保全、存量 GC、索引、净量及健康 | 工具代码覆盖；生产未执行，S1-04 阻断 | `skill-physical-backup.py:137` 内容去重、`:162` 隔离空目标恢复与内容/元数据比对；`skill-physical-maintenance.py:88` receipt/旧索引/全历史核对；`skill-physical-recovery.py:29` maintenance 后禁旧读者回退；`:72` 服务/目录验证。外部备份下载、实际净释放、生产当前下载/选择/准备应在修复复审后逐项实证。 |

## 完整实现、未实现与漂移

- 完整实现并独立验证的本轮修复：原始准备账本及后台恢复；证据见上轮问题复核与 14 项原始测试结果。
- 部分实现：合同的历史保全及崩溃恢复，存在 S1-04。其余代码覆盖及生产待执行边界已逐项列明；不把尚未部署算作代码缺失。
- 未发现本审查范围中完全没有实现的合同条目；未发现合同外新增产品页面或公开 API。私有维护接口 `skill_publisher.py:154` 对应授权全量 GC；`AGENTS.md:37` 的净量规则与此轮合同一致。
- 安全相关功能边界已在 Stage 1 按合同核对，但尚未做 Stage 2 完整安全扫描、质量/300 行检查或邻居页面实际视觉对比，不能登记其 PASS。

## 验证与原始构建输出

reviewer 独立执行：

```text
python scripts/release/skill-physical-tests.py
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.458s

OK

pytest test_skill_preparation_accounting.py test_skill_publisher_recovery.py -q -p no:cacheprovider
14 passed, 2 warnings in 26.78s
```

持久性独立探针原始结果见 S1-04。曾因首次命令没有 backend/tests 的 PYTHONPATH 而收集失败，补齐导入路径后得到上述结果；不是产品失败。

读取主 Agent 的 `output/skill-physical-20261106/frontend-build.log`，并非 reviewer 重新构建：

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

全后端及独立修改前基线日志尾部原文：

```text
backend-full.log:
9 failed, 2817 passed, 442 skipped, 6 warnings in 648.73s (0:10:48)
baseline-failures.log:
9 failed, 43 passed, 2 warnings in 11.85s
```

已逐项核对两日志的 9 个失败名称完全相同，涉及 configuration、management_freeze、pictures、pictures_protocol 四文件。因此不冒充全后端通过，也不把它们当成本轮新回归。该对照不能抵消新探针揭示的 S1-04。

读取主 Agent 浏览器日志：

```text
"passed": 6
"errors": []
```

覆盖真实文件夹超过 100 同级条目拖入、空目录/二进制、实际目录句柄保存和读回 hash、既有目录拒绝覆盖、同内容幂等/删除取消、更新确认/旧中央版本 410、失败重试/成功释放提示/最终空目录。未由本 reviewer 打开新页面及邻居基准页面，不能将其归作视觉审查。

## 交接与未验证边界

本报告冻结上述候选，Stage 1 HIGH 已通知主 Agent。主 Agent 应修复历史持久化边界、补充 Linux 证据并重新 review-prepare，再从 Stage 1 派发独立复核。不得把本报告的上轮修复通过结论用于批准修改后候选。

本次候选最终 API UID10001、publisher root、native UID999/root 安装回归仍由主 Agent 进行；审查读取到的 candidate-linux-tests.log 属于旧 30c53… 候选且 native-root 失败，不将旧日志当当前候选通过。主 Agent 在报告结束时补充：生产库已做只读外部去重备份（219 MB，覆盖约 6.8 GB 逻辑文件），尚未删除或部署；本 reviewer 未读取该备份最终清单及恢复证据，不独立确认备份验收。生产提交、发布和实际存量回收未执行；真实模型续聊未调用、未验证。

主 Agent 另提供浏览器截图位置 `output/playwright/skill-folders/03-delete-confirm.png`、`06-delete-failed.png`、`06-empty.png`，以及动画稳定后的独立 390 像素页面 `output/skill-physical-20261106/narrow-settled.png`；本轮因 Stage 1 HIGH 停止，没有将其转写为 reviewer 的 Stage 2 视觉 PASS。
