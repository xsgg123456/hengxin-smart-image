# Skill 独立存储与真实删除独立审查

- candidateId：`30c53dc6d784f84ffe746c81ac8666655e7bb32696a531e3c92d44cf6bdd9215`
- 审查范围：本候选全部 `git diff`、新增 backend 模块/测试、前端变更及所有 `scripts/release/skill-physical-*.py`；合同为 `docs/SKILL-PHYSICAL-DELETE-20261106.md`、`Product-Spec.md:1415`、`DEV-PLAN.md:1642`。不审核整个产品所有已交付阶段。
- 方法：读取 code-review skill，逐条静态核对，独立临时文件/真实测试数据库故障注入，读取主 Agent 原始验证日志。未修改产品或发布代码，未调用模型，未写生产服务器。
- 快照：审查末尾 `harness.py review-status` 的 currentId 仍为上述候选，approved=false；本报告不批准后续修复快照。
- **Stage 1：FAIL（1 HIGH、2 MEDIUM）。Stage 2：未执行。** 有 HIGH 按 skill 要求停止，不登记 review-approve。

## Stage 1 问题

### HIGH S1-01：保全历史后、持久事务日志前失败，重试虚报净释放量

合同原文：目标 2 要求“返回实际回收量”，目标 4 要求“补齐并校验，计入新增占用”；AGENTS.md:37 要求按同一统计范围核对净释放量并计入操作自身产生的副本。

实际：`backend/app/overseas/management/skill_publication.py:169` 先测中央目录，再 `references.preserve` 创建历史副本，随后准备发布/清理计划；`.pending.json` 到 `skill_publication.py:96` 才落盘。此间磁盘/校验错误留下历史副本但没有原始计量凭据。重试时 `skill_references.py:106` 发现已有副本，`skill_references.py:109` 计增量为 0，`skill_cleanup.py:122` 据此把此前新增副本占用误报为净释放。安装更新的 `skill_publication.py:125` 和全量维护 `skill_maintenance.py:77` 也使用同样先保全后落日志顺序。

独立复现：`output/skill-physical-20261106/reviewer_probe.py:8`，沿用真实 API、publisher、隔离数据库和真实临时 Skill/会话文件。第一次在 preserve 成功后的 prepare_release 注入 OSError，收到 503，历史副本存在且无 pending；恢复磁盘后二次删除 200。同一中央+会话范围实际占用不变，但返回释放 328 字节：

```text
ACCOUNTING {'response': 328, 'actualNet': 0, 'before': 2249, 'after': 2249}
```

需让原始基线和新增历史/中央副本在首次持久变更前具备可恢复凭据；覆盖“保全后、日志前失败/重启/再次删除”的净占用验收。不能只补成功路径公式测试。

### MEDIUM S1-02：清理失败后整页刷新失去可达重试入口

合同原文：目标 2 要求“部分失败留持久恢复状态，支持重试”。

实际：`backend/app/overseas/management/installed_catalog.py:140` 遇 pending 一直拒绝目录读取；`skill_publisher.py:21` 仅启动时恢复，之后恢复依赖 publisher 请求。前端 `frontend/src/views/overseas/admin/OverseasLiveSkills.vue:16` 初始列表为空，`:18` 初始 canToggle=false，`:31` 对 503 只保留既有内存状态；整页刷新没有旧状态，既无删除行又无上传入口，目录刷新本身不触发恢复。当前组件用例只测保留旧内存行后的刷新按钮，无法证明整页重入恢复。

独立复现：`output/skill-physical-20261106/reviewer_probe.py:28`，仅对真实中央对象 rmtree 注入故障使 pending 持久化，恢复文件系统后管理目录 GET 仍为 503、pending 仍存在；持有旧删除参数的直接请求才恢复。原始输出：

```text
CATALOG_AFTER_FAILURE 503 {"code":"HTTP_ERROR",...}
2 passed, 2 warnings in 5.05s
```

需提供经过身份/锁边界保护、整页重入也可达的恢复方式，或同 publisher 锁内后台安全恢复。验证恢复前不报成功，恢复后目录可重新读取，反复失败保持凭据。

### MEDIUM S1-03：正式浏览器验收断言与产品成功文案不一致

`frontend/tests/skill-folders.browser.mjs:113` 等待 `/已释放/`，而 `frontend/src/views/overseas/admin/SkillFolderActions.vue:53` 发出的文字是“Skill 已删除，释放 …”，父组件原样显示。因此到最后删除步骤会超时，不能作为正式浏览器 PASS 证据。修复断言并实际跑完；这是验证用例缺陷，不是声称真实删除本身失败。

## 合同逐条覆盖

下表“代码覆盖”仅指已找到实现及证据，不等于绕过上述 FAIL 的验收通过。backend/frontend 路径均位于 `hengxin-smart-image/` 下。

| 合同条目 | 结论 | 代码和验证证据 |
| --- | --- | --- |
| 目标 1：名称+内容独立实体、索引、小变更不复制其他对象 | 代码覆盖 | `backend/app/overseas/management/skill_objects.py:87` 复用既有 checksum；`:21` schema 2 小索引；`tests/test_skill_object_storage.py:46` 对比对象 inode/mtime。 |
| 目标 1：完整字节、空目录、权限和下载一致性 | 代码覆盖，Linux真实身份待补 | `skill_objects.py:59` 保留空目录/字节；`:69` 权限；`skill_downloads.py:28` 定位实体；`test_overseas_skill_transfers.py:73` 真实上传下载校验。 |
| 目标 2：清理中央旧副本和完成暂存 | 代码覆盖 | `skill_cleanup.py:57` 枚举旧发布、对象、已安装暂存；`:110` 全量先校验再真实 rmtree；`test_skill_physical_cleanup.py:29` 验证部分删除、日志、重试和幂等。 |
| 目标 2：完成才成功、持久恢复、真实净量 | **部分实现，S1-01/S1-02** | `skill_publication.py:34` cleanup 完成才登记成功；但 pre-journal 新增占用漏计且重入恢复入口缺失，独立复现如上。 |
| 目标 3：全部在途/退出未确认阻删，不强停 | 代码覆盖 | `skill_references.py:23` 检查非终态及未确认退出，`:27` 锁任务和 gate；`test_skill_physical_history.py:134` 八种状态均拒绝且指针不变。 |
| 目标 3：更新保留旧任务版本 | 代码覆盖 | `skill_publication.py:131` retained 合并 active_keys；`skill_cleanup.py:71` 未迁移的在途旧树保留；`test_skill_physical_history.py:152` 更新后旧任务仍读原内容。 |
| 目标 4：同会话副本优先、核对冻结清单、不跨会话 | 代码覆盖 | `execution/skill_content.py:19` 先按 frozen_item 与 owner 查找；`skill_history.py:12` workspace 所属路径校验、`:22` 逐字节/权限验证；`test_skill_physical_history.py:87` 删除后真实 prepare、异 owner 拒绝。 |
| 目标 4：缺失补齐、已结束非Studio、原payload/上下文/附件保留 | 代码覆盖；新增占用错误见 S1-01 | `skill_references.py:52` 以 Conversation/Turn/Job 确认 owner，`:82` 保全；`test_skill_physical_history.py:87` Studio/analysis、有无副本四组合，验证原文件 inode/mtime/字节及数据库字段。 |
| 目标 5：旧索引保留、引用驱动回收、schema 1/2兼容 | 代码覆盖 | `installed_catalog.py:35` 校验两种清单，`:73` schema 1 旧树或中央对象解析，schema 2 禁旧树回退；`skill_maintenance.py:26` 核对真实磁盘冻结 input；`:48` 要求暂停且排空；`test_skill_physical_maintenance.py:44` 真实旧库迁移与未知输入拒绝。 |
| 目标 6：正式库只读、publisher受控写、历史挂载不暴露API/模型 | 代码覆盖，生产实际身份待补 | `skill_publisher.py:140` root、独占锁、UDS 0660；`:126` 私有 maintenance route，公共 router 没有对应 route；`skill-physical-runtime.py:99` 只加 publisher 原生执行根挂载；`skill-physical-deploy.py:189` 核对身份、mount 和 API UID socket 可读。 |
| 顺序 1/2：存储及历史专项验证 | 已有测试证据；本次独立故障探针另揭 S1-01 | 上述模块/测试，既有 frontend/backend 完整日志由主Agent提供；本次没有宣称执行全部历史用例。 |
| 顺序 3：发布事务、权限冲突、首次/最后删除、并发、崩溃 | 代码覆盖但故障边界未满足 | `skill_publication.py:88` DB/指针事务、`:147` 冲突/幂等；`test_overseas_skill_transfers_failures.py:121` commit失败、`:141` 并发；S1-01发生于现有日志事务之外。 |
| 顺序 4：沿用确认框、在途提示、实际释放及真实浏览器 | **部分实现** | `SkillFolderActions.vue:43` 固定确认参数/失败重试、不从404推断成功；前端 API 校验非负安全整数；S1-02恢复入口、S1-03浏览器断言待修，视觉实际渲染未验收。 |
| 顺序 5：固定快照、中文提交、隐私与实际身份、基线、双gate、排空、备份、国内保护 | 审查失败；发布尚未执行 | `skill-physical-package.py:60` 受审状态/固定提交/隐私与制品摘要；`skill-physical-deploy.py:83` 双镜像原生基线、`:144` gate排空、`:174` backup；`:49` 无关container校验，沿用 reuse 国内保护。本次独立脚本21项PASS，但不是生产切换证据。 |
| 顺序 6：外部可恢复备份、历史全量保留、实际净回收及当前目录验收 | 工具代码覆盖，未执行生产GC，S1-01阻断 | `skill-physical-backup.py:137` 内容寻址备份、`:162` 隔离恢复对比；`skill-physical-maintenance.py:88` receipt/原索引/历史验证；`skill-physical-recovery.py:31` maintenance开始后禁止旧读者回滚。外部备份、净回收量、生产当前下载/选择/准备证据均待实施。 |

未发现已读变更中新增与合同无关的产品页面/API。新增私有 maintenance 功能在合同顺序 6 的范围内；AGENTS.md:37 的净量规则与本轮需求一致。未发现合同条目完全没有任何实现；缺口及待实施事项已逐项列出，不把尚未部署当作产品缺陷。

## 验证与原始编译输出

独立执行 `python scripts/release/skill-physical-tests.py`：

```text
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.439s

OK
```

独立故障探针使用 backend `.venv/Scripts/python.exe -m pytest output/skill-physical-20261106/reviewer_probe.py -q -s -p no:cacheprovider`，成功证明两个缺陷前提，不是产品通过测试。原始关键输出已列于 S1-01/S1-02。探针在忽略的 output 路径，不改变候选源码。

读取主 Agent 构建日志 `output/skill-physical-20261106/frontend-build.log`，原始摘录（非本审查重新构建）：

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

读取 `output/skill-physical-20261106/backend-full.log`：

```text
9 failed, 2817 passed, 442 skipped, 6 warnings in 648.73s (0:10:48)
```

主 Agent 独立导出修改前 HEAD 后的 `baseline-failures.log` 原始输出：

```text
9 failed, 43 passed, 2 warnings in 11.85s
```

两日志列出的九个失败名称一致，涉及 configuration、management_freeze、pictures、pictures_protocol 四文件；不因此将本次新增故障排除。前端529项/其他专项通过为主 Agent 提供的运行信息，未在本报告写成独立重跑结论。

## 未验证边界与交接

- Linux API UID10001、publisher root、native UID999/root 的同候选安装测试尚在主 Agent 进行；本报告没有其最终输出。
- 真实前端浏览器/邻居页面视觉比较未完成。Stage 2 的完整质量、安全扫描、测试真实性和视觉对照因 HIGH 未执行。
- 未提交、未部署、未进行生产清理，不宣称正式会话续聊或模型调用通过。
- 主 Agent 已收到 S1-01/S1-02/S1-03。修复后须重新 review-prepare 并重新派发独立审查；本报告不能为新快照登记两阶段 PASS。
