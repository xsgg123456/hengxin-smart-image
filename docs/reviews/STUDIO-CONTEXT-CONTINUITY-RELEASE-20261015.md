# 海外 Studio 文件连续性发布候选独立审查

- 日期：2026-10-15。
- candidateId：`0dc3921eccfc4628d259d4b3d4895fbb8c1ee405aabc90972f42cfe349fe4d67`。
- 仓库/分支：`D:/Work_Project/hengxin-smart-image`，`codex/studio-file-continuity`。
- Stage 1：**FAIL，1 项 MEDIUM（M1）**，在线自动恢复提示在未派发的失败/取消轮次被消耗。
- Stage 2：**未执行**。code-review Skill 要求 Stage 1 通过后进入 Stage 2；本次没有把未完成的合同项降格为 PASS。
- 开始审查、独立复现及写报告前的 `review-status.currentId` 均为上述编号，`approved=false`。本报告仅覆盖此快照。
- reviewer 只读源码与证据、运行本地测试和临时目录复现、写本报告；未连接生产、未恢复业务目录、未调用模型、未修改业务代码、未提交或登记批准。

## 审查范围与源合同

已读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1157`、`DEV-PLAN.md:1417`、`docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md`，以及前两份失败报告；旧报告没有被用作当前实现的证明。

下文 `B/` 代表 `hengxin-smart-image/backend/`。范围为：

- `B/app/overseas/studio/context_fs.py`、`context_assets.py`、`context_migration.py`、`context_workspace.py`、`restore_context.py`、`work_baseline.py`、`execution.py`、`delivery.py`。
- `B/app/execution/persistent_mounts.py`、`workspace.py`、`B/app/overseas/execution/materials.py`；只读追踪 runner、Studio service、归档和清理的既有调用边界。
- 所有新增 `test_studio_context_*`、`test_studio_restore_context.py`、`test_studio_persistent_mounts.py`、`test_studio_work_baseline.py`、`studio_context_probe.py`、修改的 `test_overseas_studio_execution.py`。
- `scripts/release/overseas-context-deploy.py`、`overseas-context-recovery.py`、`package-overseas.py` 和对应测试；只读追踪继承的附件/上传发布门禁。
- `hengxin-smart-image/frontend/package.json:3` 的版本变更；没有页面源码变化。

## M1 · MEDIUM：在线自动迁移的提示未保留到下一次实际派发

**合同原文：** `Product-Spec.md:1162` 要求“必要时提供恢复索引路径”；方案 `docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md:111` 要求“有歧义的旧路径不静默选一个版本，使用明确的新路径映射。在首次升级续接中仅提供必要的恢复路径信息”。Spec `:1164` 和方案 `:131` 同时要求覆盖取消/失败路径。

**实际差异：** `B/app/overseas/studio/context_workspace.py:90` 仅当 `maintenance_recovery=True` 时持久保存已派发历史快照；在线自动迁移只在 `:130` 依据本次 `migrated` 设置对象内的 `recovery_notice`。prepare 成功后，若该轮在派发前失败或取消，后续轮次读取已完成的 manifest，`migrated=0`，又没有 `recovery_notice_turns`，故不再向 CLI 提供索引路径。

这是生产可达的顺序：`B/app/overseas/execution/runner.py:93` 先完成工作区迁移；`:96` 材料准备、`:102` 沙箱构造和 `:105` 取消/所有权检查均早于 `:125` 的 `before_execute`；`B/app/overseas/studio/execution.py:97` 才把轮次标为 dispatched。前述任一步失败不会把它加入后续 dispatched history。下一轮 `execution.py:87` 不再追加提示。

有同名冲突时，该缺陷尤其明确：旧逻辑路径已撤除，只有 `/work/.context-recovered/...` 中的多个版本。数据仍保留并被索引，故本项不宣称数据丢失，也不定为 HIGH；但首次真正续接缺少合同规定的恢复引导，因此不满足 Stage 1。

**独立最小复现：** 在 `B/` 用 `.venv/Scripts/python.exe` 执行；只操作临时目录，不需要数据库、网络或模型。

```python
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'tests')
from test_studio_context_assets import workspace
from test_studio_context_migration import row, write, index
from app.overseas.studio import context_workspace as context

with tempfile.TemporaryDirectory(prefix='review-notice-') as d:
    root = Path(d)
    first = workspace(root)
    second = workspace(root, first.home.parent.name)
    write(first.work, 'notes.txt', b'first')
    write(second.work, 'notes.txt', b'second')
    history = [row(first), row(second)]
    cancelled = workspace(root, first.home.parent.name)
    context.prepare(cancelled, history, [], lambda _: None)
    # 取消/准备失败：没有实际派发，DB history 保持不变。
    resumed = workspace(root, first.home.parent.name)
    context.prepare(resumed, history, [], lambda _: None)
    print(json.dumps({
        'cancelled_prepare_notice': cancelled.recovery_notice,
        'next_real_prepare_notice': resumed.recovery_notice,
        'old_logical_path_exists': (resumed.work / 'notes.txt').exists(),
        'indexed_paths': [item['path'] for item in index(resumed)['files']],
    }))
```

原始输出（exit 0，只表示复现脚本运行成功）：

```json
{"cancelled_prepare_notice": true, "next_real_prepare_notice": false, "old_logical_path_exists": false, "indexed_paths": ["/work/.context-recovered/2e42910b-4bcb-4f87-b2ed-36cd4f8c8161/a7937b64b8caa58f03721bb6bacf5c78cb235febe0e70b1b84cd99541461a08e/notes.txt", "/work/.context-recovered/4a90be84-5838-47ea-a6c2-d3bd6cfe30b3/16367aacb67a4a017c8da8ab95682ccb390863780f7114dda0a0e0c55644c7c4/notes.txt"]}
```

**现有测试盲区：** `B/tests/test_studio_context_notice.py:9` 覆盖了维护恢复且通过；`B/tests/test_studio_context_migration.py:53` 在未模拟 dispatch 的第二次 prepare 后直接断言提示消失，覆盖不到真实取消/失败语义。

**修复验收：** 在线首次/增量恢复和维护恢复均把必要提示保存到下一次真实 dispatched；prepare 失败、取消或重复调用不消耗提示；真实派发后再后续普通轮不重复。保留用户原文、session 和业务记录。补充在线有冲突旧会话 + 准备后未派发 + 新轮次的回归，不只重复维护恢复用例。

## Stage 1 逐条对照

以下“完整实现”只对本表的具体子行为成立；总 Stage 1 因 M1 不通过。生产安装、真实任务恢复和开放入口属于主 Agent 后续交付，不由源码审查冒充完成。

| 合同条目 | 结论、代码位置和证据 |
| --- | --- |
| 同 conversation 持续 work，原件/派生文件跨轮可读 | 完整实现。`B/app/overseas/studio/context_workspace.py:83`、`:127` 使用固定 persistent/work；`execution.py:34` 从 DB 获取已派发历史。`B/tests/test_studio_context_assets.py:33` 实际三轮读取原件和笔记并断言只下载一次；`test_overseas_studio_execution.py:66` 通过 API→runner 三轮验证相同 work、不同 round、原字节持续可读。本次独立测试通过。 |
| 纯文本、重新进入页面、worker 重启不清空 | 完整实现持久存储机制。`context_workspace.py:87` 每次从磁盘加载，`:126` 每轮新 Workspace 绑定同一路径；不依赖前端内存。上述三轮测试每轮重建 Workspace。所交 Linux probe 另启动三次独立沙箱。没有声称 reviewer 做过真实 worker 服务重启或浏览器刷新。 |
| 新会话与任务隔离、未提供材料不自动加入 | 完整实现。`context_workspace.py:23` 限定 root/round 归属；`execution.py:22` 验证 turn/job/task/conversation；`context_assets.py:40` 只注册冻结历史及本轮 inputs。`test_studio_context_assets.py:96` 新会话空环境、`test_studio_context_safety.py:101` 跨会话 round 拒绝均通过。既有 `service.py:51` 只冻结所选附件和图片。 |
| 版本化原件、同名追加、重复复用、缺失/损坏恢复 | 完整实现。`context_assets.py:30` 以资源位置和 checksum 建立版本键，`:67` 校验/修复原件，`:95` 存储异常带文件名失败。`test_studio_context_assets.py:56`、`:69`、`:86`，`test_studio_context_safety.py:86` 独立测试通过。 |
| 原件只读；普通 work 可编辑 | 完整实现本次所审分支。`B/app/execution/persistent_mounts.py:38` 只读覆盖 inputs；`workspace.py:91` work 可写。H1/H2 修复后的编辑/增量/重试字节集合测试通过，见后节。Linux 原件写入拒绝由所交真实沙箱结果支持。 |
| input/日志每轮独立，私有清单不挂载 | 完整实现。`workspace.py:32` 每轮 control；`B/app/overseas/execution/materials.py:15` control 快照、`:16` round_work；`persistent_mounts.py:39` 只读 input/index，未挂载 manifest/锁/control。`test_studio_persistent_mounts.py:24` 校验挂载参数与顺序，本次通过；probe 断言 control 不可见。 |
| Skill 完整版本按本轮选择，有/无/切换不继承旧挂载 | 完整实现接线。`materials.py:18` 选择冻结版本并将文本和 assets 写入本轮目录；`workspace.py:100` 隐藏旧发现目录，`:104` 挂载当前版本，`:109` skills 只读。`test_studio_persistent_mounts.py:24` 有/无选择通过，所交真实三轮 probe 首轮有 Skill、后轮无 Skill 通过。前端选择记忆未新增。 |
| 用户原文、原 session 与历史业务记录不改 | 完整实现。`execution.py:84` 原样拼接 text，`:56` resume 原 session，`:133` 禁止换 session；`restore_context.py:21` 只查询归属与文件恢复。`test_studio_restore_context.py:41` 明确断言 session、旧 reply、job status/execution_count 不变并重复 apply，本次通过。 |
| DB 归属恢复、原 session 文件缺失拒绝、运行/uncertain 时拒绝 | 完整实现。`restore_context.py:29` 锁任务，`:33` 拒绝非终态或未退出进程，`:41` 验证历史 job payload 归属，`:51` 要求旧 session 文件。`test_studio_restore_context.py:72` 和 `test_overseas_studio_execution.py:163` 独立通过。 |
| 旧路径映射、冲突不覆盖、索引包含真实可读版本 | 完整实现所审数据行为。`context_migration.py:36` 盘点 DB 历史，`:103` 对已映射路径重新校验，`:143` 盘点工作入口/祖先/目录，`:213` 分配冲突版本路径，`:240` 输出公开索引；前次 H1/H2 最小形态均已由新测试验证。本次未复现字节丢失或伪造仍存在的 workspace 旧 hash。 |
| 首次恢复的必要路径引导，失败/取消后不消耗 | **部分实现，M1。** `context_workspace.py:90` 的维护恢复分支通过 `test_studio_context_notice.py:9`；在线自动恢复没有持久 notice。独立复现显示下一真实轮次没有提示，旧歧义入口已撤除。 |
| 迁移原子启用、源保留、增量/回退新轮可重入 | 完整实现所审数据路径。`context_workspace.py:95` 临时目录、`:117` 原子 rename；`context_migration.py:231` 先写 journal，`:233` 完成复制，`:235` 才移除歧义入口。`test_studio_context_migration.py:88`、`:122`、`:180`、`test_studio_context_edited_versions.py:73` 等故障/重试用例本次通过。M1 不影响字节保留，但影响恢复提示。 |
| 盘空间不足、链接/硬链接/FIFO/路径越界不得读取外部或破坏源 | 完整实现代码与各平台已测部分。`context_fs.py:15`、`:23`、`:65`、`:160`；`test_studio_context_safety.py:22`、`:47`、`:75`、`:134`。本次 Windows 相关集有13条件 skip；所交最终 Linux增量集仅1 Windows junction skip。跳过不计通过。 |
| 新增/修改图且最终明确引用才收取，旧图/草稿/输入/Skill拒收 | 完整实现。`work_baseline.py:120` 在执行前按内容建立基线，`:142` 比较真正校验过的图片字节；`delivery.py:144` 保留最终引用与归属检查，`:166` 使用 work 基线。`test_studio_work_baseline.py:55`、`:68`、`:80`、`:109`、`:147` 和 runner 草稿用例本次通过。 |
| 归档/已交付版本独立，修改工作图不改归档；删任务覆盖会话根 | 完整实现既有接线保持。`execution.py:115` 为每次收取创建独立 UUID/object_key；`test_studio_work_baseline.py:90` 旧交付字节不随工作图修改。既有 `service.py:117` 调用归档 protect；`B/app/overseas/tasks/cleanup_files.py:63` 按 conversation 清理整根目录，包含 persistent；既有 `test_overseas_studio_conversations.py:55` 断言多会话删除、归档仍可读。全量 Linux 日志支持既有回归，reviewer 未独立删除生产任务。 |
| 取消/失败/uncertain 不重复启动 | 既有执行栅栏保持；提示部分另见 M1。`runner.py:103`、`:124`、`:158` 和 `execution.py:91`；`test_overseas_studio_execution.py:151` 实际重入 runner 仍只有一次命令且状态 uncertain，本次通过。 |
| 全输入类别与500 MB/100附件边界、共享旧路径回归 | 完整实现通用冻结输入处理，既有限制未改。`context_assets.py:13` 上限500,000,000字节；`B/app/overseas/studio/service.py:59` 合并附件与引用图的冻结数据；`schemas.py:12` 每类100；`tests/test_overseas_upload_limits.py:12`、`:28` 有真实大小和边界断言。`workspace.py:93` 仅 persistent 分支新挂载，`materials.py:16` 为普通旧流程保留 workspace.work。所交全量2432通过与最终增量373通过分别按实际快照范围计入，未称旧全量覆盖后续新增代码。 |
| Linux 实际三轮与历史迁移源→目标校验 | 有真实 fixture 证据。`tests/studio_context_probe.py:20` 使用实际 sandbox_command，额外 unshare-net；`:38` 正常7→7→8原件及派生文件；`:169` 另构造旧原件/研究同名冲突；`:110` 将独立源计划和实际索引/目标hash对照，`:164` 三次只读实际沙箱。已读原始 JSON 见下节；不是付费模型生成或生产业务目录恢复。 |
| inspect只读、apply固定digest，旧2原件/187研究文件待部署恢复 | 工具完整实现，实际生产恢复尚未执行。`context_workspace.py:71` 只读盘点；`restore_context.py:63` 核对源digest；`:55` 独立列冻结inputs供probe对照。`test_studio_restore_context.py:41`、`:63` 本次通过；生产2原件/187研究文件是主Agent已交只读预演边界，不在reviewer中重新连接生产。 |
| 0.2.36包、固定基线、无DB迁移、备份排空恢复验证后切换 | 实现与独立发布测试通过，未执行发布。`overseas-context-deploy.py:18`、`:47` 固定版本与原生运行基线；`:70` 固定显式目标hash；`:107` 要求完整备份/执行器停止并验证恢复标记；`:122` 只检查现有schema。`overseas-context-recovery.py:34` 再查停止/无pending，`:64` inspect→apply→三次读，失败不生成verified。独立99测试/24子测试通过。继承 `overseas-upload-deploy.py:209`–`:226` 的关闭入口、排空、备份顺序；失败不切换/不开放由 `test_overseas_context.py:52` 实际故障注入验证。 |
| UI一致性、引导真实性与范围漂移 | 前端 diff 仅 `package.json:3` 从0.2.35到0.2.36，无页面/组件/样式改变，因此本候选不存在需要与邻居页面作视觉对比的新UI。恢复提示引用的索引文件确实存在，但提示时序不完整（M1）。未新增页面、API、数据库表或Skill选择记忆；维护/发布脚本在授权范围内。 |

## 前两次 HIGH 和维护提醒复核

- **H1 已闭环。** `context_migration.py:143` 真实盘点逻辑路径、阻塞祖先及目录子树。`test_studio_context_work_conflicts.py:28`、`:42`、`:75`、`:102`、`:140` 从事先固定字节集合验证现有未登记文件、用户编辑、目录冲突和故障恢复；本次通过。不是仅以生成索引与自身对比。
- **H2 已闭环。** `context_migration.py:103` 检查实际映射 path，`:117` 只保留确有可校验来源的旧版本，`:123` 为仍有旧源的历史版本选不覆盖编辑的恢复位置；`:205` 保持正常编辑入口，真正新冲突才撤歧义别名。`test_studio_context_edited_versions.py:39`、`:50`、`:59`、`:73`、`:112`、`:131` 全部在本次105项通过集中，覆盖再次编辑、metadata/copy中断及中断期间再编辑。
- **维护恢复提醒已闭环，在线路径未闭环。** `restore_context.py:65` 设置 maintenance_recovery，`context_workspace.py:88` 比较已派发历史，`test_studio_context_notice.py:9` 断言准备失败/取消未派发不消耗、真正加入history后不再重复。本候选没有把该持久语义应用于在线自动迁移，见M1。

## 验证原始输出与边界

reviewer 在当前候选独立运行：

```text
./.venv/Scripts/python.exe -m pytest -q tests/test_studio_context_assets.py tests/test_studio_context_migration.py tests/test_studio_context_work_conflicts.py tests/test_studio_context_edited_versions.py tests/test_studio_context_notice.py tests/test_studio_context_safety.py tests/test_studio_context_probe.py tests/test_studio_persistent_mounts.py tests/test_studio_restore_context.py tests/test_studio_work_baseline.py tests/test_overseas_studio_execution.py
105 passed, 13 skipped, 2 warnings in 24.92s
```

两项警告为 Starlette/httpx、anyio BlockingPortal 弃用提示。平台条件跳过保留，不用Windows结果冒充POSIX安全分支通过。M1是这套测试之外的独立真实复现。

reviewer 在仓库根目录独立运行：

```text
./hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_context.py scripts/release/test_overseas_context_recovery.py scripts/release/test_package_overseas.py
99 passed, 24 subtests passed in 4.18s
```

reviewer 编译命令及原始输出（退出码0）：

```text
./.venv/Scripts/python.exe -m compileall -q app tests ../../scripts
compileall exit=0
```

compileall自身 stdout/stderr 为空，末行是本次命令在读取实际退出码后输出；只证明语法编译，不证明功能无缺陷。

已独立读取主Agent提供的日志末尾，未由reviewer重跑这些环境：

```text
output/context-backend-final-linux-tests.log:
2432 passed, 189 skipped, 15 warnings in 271.18s (0:04:31)

output/context-final-targeted-linux-tests.log:
373 passed, 1 skipped, 2 warnings in 37.74s

output/context-release-final-tests.log:
157 passed, 72 subtests passed in 5.16s

output/context-frontend-tests.log:
ℹ tests 364
ℹ pass 364
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8869.3714

output/context-frontend-build.log:
✓ built in 32.11s
```

全量Linux运行是前一候选，最终代码变更另有373项增量回归；不将两者混写成“最终候选全量运行完成”。正式安装镜像测试按主Agent交接尚待后续运行。

`output/context-isolated-sandbox.json` 的code=0，stderr为空；stdout原始内容：

```json
{"threeRounds": [{"round": 1, "originals": 7, "derived": true, "readonly": true, "isolated": true}, {"round": 2, "originals": 7, "derived": true, "readonly": true, "isolated": true}, {"round": 3, "originals": 8, "derived": true, "readonly": true, "isolated": true}], "legacyRecovery": {"conversationId": "12c2b593-ec55-4518-a8d4-8e45537cc25a", "independentSandboxReads": [{"readableFiles": 4, "allHashesMatch": true}, {"readableFiles": 4, "allHashesMatch": true}, {"readableFiles": 4, "allHashesMatch": true}], "sourceDigest": "12e4ed34b2b7a9e0aa02299bc9a7e02e6b6d81c9506c1402262224170f7a7ff9", "sourceFilesVerified": 4, "sourceInputsVerified": 2}}
```

这些probe证据证明测试文件通过实际Linux挂载持续可读、只读与隔离，以及旧布局来源到目标完整性；不证明已恢复生产目标、不证明字体/素材足够、不证明模型生成成功。

## Stage 2 与交接

Stage 2 未执行：本报告不提供完整代码质量、安全扫描、测试真实性审计或视觉审查PASS；Stage 1对文件隔离、发布门禁的合同检查不替代Stage 2。

M1修复后重新 `review-prepare`，由独立reviewer从Stage 1复核并继续Stage 2。该报告不能用于 `review-approve`，不得用写 `.needs-review=clean` 放行。生产部署/恢复仍未由本报告批准。
