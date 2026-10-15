# Studio 文件连续性 · 独立审查报告

- 日期：2026-10-15。
- candidateId：`2bf4ec347fb80829df115d2b1f6cac0739d0cf85ad86d61d356553f041dc9df2`。
- 分支：`codex/studio-file-continuity`。
- **Stage 1：FAIL，1 项 MEDIUM。Stage 2：未执行。** 文件名由主 Agent 指定，不代表批准。
- 审查开始及完成独立测试后，`harness.py review-status` 均返回上述 currentId。报告写完后的最后检查发现主 Agent 已开始修复，currentId 变为 `7b8d6f6ac459c8408f92e118e5f92cf0b2ae3083d625755c0c2ed7521a912df2`；至少 `context_workspace.py` 与 `test_studio_context_notice.py` 已变化。本报告的复现、行号、测试和结论仅适用于送审的 `2bf4ec3…`，不覆盖该新快照。报告 Markdown 本身不改变代码快照。
- reviewer 仅执行本地读取、临时目录复现、测试及本报告写入，没有修改代码、连接生产、启动模型、提交、登记批准或写 `.needs-review`。

## 合同与审查范围

逐条读取 `Product-Spec.md` 末尾“2026-10-15 · 海外工作台多轮文件连续性修复”、`DEV-PLAN.md` 对应阶段、`docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md:59`–`:134`，并按 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md` 执行。早期审查报告用于定位待复核点，不作为本候选通过依据。

下文 `B/` 表示 `hengxin-smart-image/backend/`。范围包括：

- `B/app/overseas/studio/context_{fs,assets,migration,workspace}.py`、`restore_context.py`、`work_baseline.py`、`execution.py`、`delivery.py`。
- `B/app/execution/persistent_mounts.py`、`workspace.py`、`B/app/overseas/execution/materials.py`；只读追踪既有 runner、Studio service、归档和任务清理。
- 新增 `test_studio_context_*`、`test_studio_restore_context.py`、`test_studio_persistent_mounts.py`、`test_studio_work_baseline.py`、`studio_context_probe.py`，以及修改的 `test_overseas_studio_execution.py`。
- `scripts/release/overseas-context-{deploy,recovery}.py`、`package-overseas.py` 和对应测试；只读追踪继承的发布步骤。
- `hengxin-smart-image/frontend/package.json:3`，前端版本从 0.2.35 到 0.2.36。没有页面源码变更。

## M1-R · MEDIUM：增量迁移内部失败后的重试仍会丢恢复路径提示

**合同：** `Product-Spec.md:1162` 要求必要时提供恢复索引路径；方案 `docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md:111` 要求有歧义旧路径不静默选版本，并在首次升级续接提供必要路径信息；`:112`、`:115`、`:131`–`:132` 要求迁移失败可重入、回退新增轮次重新盘点以及失败路径回归。

**实际差异：** 本候选修复了“prepare 完成后、dispatch 前取消”的既有 M1，但遗漏了增量迁移自身中断的情况。已有 persistent 布局且旧提示已被真正派发后，回退旧版本产生同路径不同内容的新 round，再升级在线迁移。如果写入 `context-index.json` 或 `manifest.json` 失败，下一次重试能保留并索引两版本，却没有恢复提示，原逻辑路径已经移除。

根因证据：

1. `B/app/overseas/studio/context_migration.py:231` 先保存 pending journal，`:233` 复制版本，`:235` 移除歧义逻辑入口。外层直到 `context_workspace.py:110`、`:112` 才分别保存索引和 manifest。
2. 任一 metadata 保存失败后，旧 manifest 中的 `recovery_notice_turns` 未更新，journal 保留。
3. 重试时 `context_migration.py:195` 将 journal 纳入 `registered`，`:197` 因其已在 known 中得到空 additions，`:237` 返回 `0`。
4. `context_workspace.py:89` 的旧 notice 不包含已派发的新历史；`:102` 得到 `changed=False`，`:103`–`:104` 不保存新的 notice，`:131` 得到 `recovery_notice=False`。
5. `execution.py:87`–`:88` 因而不添加 `/work/.context-files.json` 引导。真实接线中 `B/app/overseas/execution/runner.py:93` 的工作区准备早于 `:125` 的 before_execute，准备抛错不会写 `execution.py:97` 的 dispatched。此复现不依赖伪造或不可达的 dispatched 前提。

这是提示语义不完整，**不是数据丢失**：独立复现确认原字节和新增旧版字节均在恢复索引里；但模型记住的 `/work/notes.txt` 已不存在，下一次实际续接没有必要的路径说明。

独立最小复现，在 `B/` 以 `.venv/Scripts/python.exe` 执行以下脚本，仅使用临时目录和仓库现有 fixture helper：

```python
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'tests')
from test_studio_context_assets import workspace
from test_studio_context_migration import row, write, index
from app.overseas.studio import context_workspace as context, context_fs as fs

for failure in ('context-index.json', 'manifest.json'):
    with tempfile.TemporaryDirectory(prefix='review-journal-notice-') as folder:
        root = Path(folder)
        old = workspace(root)
        write(old.work, 'notes.txt', b'original')
        first = workspace(root, old.home.parent.name)
        dispatched = row(first)
        context.prepare(first, [row(old)], [], lambda _: None)
        rollback = workspace(root, old.home.parent.name)
        write(rollback.work, 'notes.txt', b'new legacy version')
        history = [row(old), dispatched, row(rollback)]
        failed = workspace(root, old.home.parent.name)
        save = fs.save
        def fail_metadata(path, data):
            if path.name == failure:
                raise OSError('injected metadata failure')
            return save(path, data)
        fs.save = fail_metadata
        try:
            context.prepare(failed, history, [], lambda _: None)
            raise AssertionError('expected metadata failure')
        except OSError:
            pass
        finally:
            fs.save = save
        journal = (first.work.parent / 'migration-pending.json').exists()
        resumed = workspace(root, old.home.parent.name)
        context.prepare(resumed, history, [], lambda _: None)
        values = sorted((resumed.work / item['path'].removeprefix('/work/')).read_text()
                        for item in index(resumed)['files'])
        print(json.dumps(dict(failed_write=failure, pending_journal=journal,
            retry_notice=resumed.recovery_notice,
            logical_exists=(resumed.work/'notes.txt').exists(), indexed_bytes=values)))
```

原始输出（退出码 0 表示复现程序成功运行，不是功能验收通过）：

```json
{"failed_write": "context-index.json", "pending_journal": true, "retry_notice": false, "logical_exists": false, "indexed_bytes": ["new legacy version", "original"]}
{"failed_write": "manifest.json", "pending_journal": true, "retry_notice": false, "logical_exists": false, "indexed_bytes": ["new legacy version", "original"]}
```

**现有测试覆盖与盲区：** `B/tests/test_studio_context_notice.py:10`、`:31` 的本候选用例通过，证明成功准备后的取消/未派发不再消耗提示。`test_studio_context_migration.py:180` 与 `test_studio_context_edited_versions.py:75` 检查 metadata 失败后的字节、索引和编辑保持，没有检查“已有提示已派发 + 新增旧轮次 + 迁移自身失败”后的新提示。因此这两组测试同时通过，仍无法覆盖本复现。

**修复验收：** 在增量迁移的 journal 或等价持久恢复状态中保留需要通知的事实，覆盖复制/索引/manifest 中断；重试完成及后续取消均不能丢提示，直到新的实际 dispatched 历史出现才不再重复。至少补上面两个 metadata 故障分支，并检查恢复后的字节集合、歧义入口、提示及真实派发后消失。维护恢复和原件恢复采用的同一状态逻辑也需覆盖，不能只保留成功 prepare 后取消的回归。

## Stage 1 逐项合同核对

以下“完整实现”仅对应该行子行为；整个 Stage 1 因 M1-R 未通过。部署、安装产物验证及指定生产旧会话恢复属于主 Agent 后续交付，本报告不将源码与 fixture 验证写成已上线。

| 合同条目 | 实现结论与证据 |
| --- | --- |
| 同 conversation 使用固定 work，原件与提取/转换/笔记/脚本/中间文件持续可读 | 完整实现。`B/app/overseas/studio/context_workspace.py:83`、`:127`–`:130` 绑定固定 persistent/work；`execution.py:34` 读取 DB 已派发历史。`B/tests/test_studio_context_assets.py:33` 和 `test_overseas_studio_execution.py:66` 的三轮原件/研究文件断言在本次独立测试通过。 |
| 纯文本、重入页面、worker 重启不清空 | 持久机制完整。`context_workspace.py:87` 从磁盘加载，`:128` 每轮重新绑定，独立测试每轮重建 Workspace。所交真实 Linux probe 三次独立沙箱支持跨进程可读；reviewer 没有执行生产 worker 重启或浏览器刷新。 |
| 新会话/新任务隔离，未主动提供的资料不带入 | 完整实现。`execution.py:22`–`:38` 限定 task/conversation；`context_workspace.py:23` 校验 round 归属；`context_assets.py:40` 仅处理冻结 history/current_inputs。`test_studio_context_assets.py:96`、`test_studio_context_safety.py:101` 本次通过。 |
| 所有输入类别、同名文件、资源/内容版本、重复引用 | 完整实现通用冻结输入处理。`context_assets.py:13`、`:30`、`:40` 由资源 ID/对象位置和 checksum 建立路径；既有 `B/app/overseas/studio/service.py:51`–`:65` 统一冻结附件和图片引用。`test_studio_context_assets.py:56` 本次通过；真实 fixture probe 覆盖七种扩展名和新增同名原件。 |
| 原件只读、完整性校验、缺失/损坏按授权信息恢复、存储错误具体可见 | 完整实现。`context_assets.py:67`–`:108` 校验全部注册原件并复用旧源或重新读取冻结对象；`:98`、`:101` 错误包含文件名；`B/app/execution/persistent_mounts.py:38` 只读挂载。`test_studio_context_assets.py:70`、`:86` 和 `test_studio_context_safety.py:86` 本次通过，Linux 只读写拒绝有提交的实际 sandbox 证据。 |
| 普通工作文件可编辑，恢复版本编辑不误报完整性 | 完整实现所审分支。`B/app/execution/workspace.py:91`–`:95` work 可写、受控原件另挂；`context_migration.py:103`、`:123` 重新盘点映射文件并保留编辑。`test_studio_context_edited_versions.py:39`、`:50`、`:59`、`:75`、`:112`、`:131` 本次通过。 |
| 每轮 input/日志独立，私有来源清单/锁不挂载 | 完整实现。`workspace.py:32` 独立 control；`B/app/overseas/execution/materials.py:15`–`:17` 写 control 与 round 快照；`persistent_mounts.py:38`–`:41` 仅挂原件、input、公共索引。`test_studio_persistent_mounts.py:24` 本次通过，probe 检查 control 在 sandbox 不可见。 |
| Skill 本轮选择、有/无/切换、完整资源、未选不挂旧 Skill | 完整实现接线。`materials.py:18`–`:29`、`:31`–`:69` 按冻结版本准备文本与 assets；`workspace.py:100`–`:109` 隐藏旧发现目录并只读挂本轮版本。挂载用例本次通过，真实三轮 probe 首轮选、后轮不选通过；未新增跨页面选择记忆。 |
| 用户普通消息原文、原 session/history/归档记录不改 | 完整实现。`execution.py:84` 保留原文，`:56` resume，`:133` 禁止 session 换号；`restore_context.py:21`–`:68` 仅查询与文件恢复。`test_studio_restore_context.py:41` 对原 session、reply、作业状态和执行次数保持的断言本次通过。 |
| 旧会话 DB 归属、终态和 uncertain 门禁、原 session 文件必须存在 | 完整实现。`restore_context.py:29` 锁任务，`:33` 拒绝活跃或未确认退出进程，`:41` 校验 turn/job payload 归属，`:51` 验证原 session 文件。`test_studio_restore_context.py:72` 和 `test_overseas_studio_execution.py:163` 本次通过。 |
| 旧工作文件/原件、冲突来源索引、无歧义原路径保留 | 完整实现数据路径。`context_migration.py:36` 盘点历史，`:143` 盘点现有入口与目录，`:213` 选择版本路径，`:240` 公开真实路径；`context_assets.py:78` 原件别名冲突不静默覆盖。迁移与冲突测试本次通过。 |
| 首次/增量恢复路径提示，失败/取消/重试不提前消耗 | **部分实现，M1-R。** 成功 prepare 后未派发与维护恢复通过 `test_studio_context_notice.py:10`、`:31`；内部 metadata 失败后的 journal 重试丢提示，独立最小复现见上。 |
| 初次原子启用、迁移可重入、失败保留源 | 数据行为完整。`context_workspace.py:93` 临时目标，`:118` 原子 rename；`context_migration.py:231` journal、`:233` 完成复制后才 `:235` 撤歧义别名。`test_studio_context_migration.py:122`、`:180` 和 edited/work_conflicts 故障用例本次通过。提示状态不完整另列 M1-R。 |
| 回退旧版新增 round 后再次升级增量恢复 | 数据行为完整。`context_workspace.py:92` 重新扫描未 managed 历史，`context_migration.py:195`–`:200` 合并现有/新增/用户编辑。`test_studio_context_migration.py:88`、`test_studio_context_work_conflicts.py:28` 本次通过；本复现同样确认两版本完整。 |
| 磁盘不足、越界、链接、硬链接、特殊文件、并发准备 | 已覆盖平台行为完整。`context_fs.py:15`、`:23`、`:65`、`:160`、`:167` 路径、流式校验、空间及进程锁；`test_studio_context_safety.py:22`、`:47`、`:75`、`:101`、`:116` 本次通过。Windows 的 POSIX/符号链接条件 skip 不算通过；Linux 条件覆盖来自提交的 Linux 日志。 |
| 正式图片必须本轮明确引用且新增/修改，旧图/草稿不自动收取 | 完整实现。`execution.py:75`–`:77` 执行前建立内容基线；`delivery.py:144`–`:169` 保留最终引用/合法性/归属，并用验证图片自身 checksum 对比；`work_baseline.py:142` 拒绝未改变字节。`test_studio_work_baseline.py:55`、`:68`、`:80`、`:147` 和 runner 草稿用例本次通过。 |
| 输入/Skill 资源不得充输出，原生生成图仍按 session 历史门禁 | 完整实现。`delivery.py:158` 保持既有 `_local_file` 边界，`work_baseline.py:83` 跳过受保护目录；`test_studio_work_baseline.py:109`、`:119` 本次通过。 |
| 交付与归档版本独立，修改工作文件不改已归档字节，删除覆盖会话根 | 完整实现接线保持。`execution.py:115`–`:123` 新 UUID/object key；`B/app/overseas/studio/service.py:114`–`:116` 调用归档 protect；`B/app/overseas/tasks/cleanup_files.py:63` 删除整个 conversation 根。`test_studio_work_baseline.py:90` 本次通过；既有删除/归档回归由所交全量 Linux 日志支持。 |
| 取消/失败/uncertain 不重复启动 | 既有执行门禁保持。`runner.py:103`、`:124`、`:158` 区分派发前/退出后/未知进程；`test_overseas_studio_execution.py:151` 本次通过。恢复提示例外单列 M1-R。 |
| 500 MB/100 附件上限，国内及海外非 Studio 旧路径 | 边界及旧接线保持。`context_assets.py:17` 保留 500,000,000 字节；`workspace.py:93` 仅 persistent 分支增加挂载，`materials.py:16` 为旧流程保留 workspace.work；前端仅版本变更。所交 Linux 全量回归 2446 passed 支持共享路径，未将其当成本候选最终 M1 改动的全量验证。 |
| Linux 至少三轮实际读取、派生文件、同名新增、跨会话隔离 | 有实际 fixture 证据。`B/tests/studio_context_probe.py:20` 调用实际 sandbox_command，`:22` 隔离网络，`:38`–`:89` 验证 7→7→8 原件和派生文件/只读/隔离。已读取 `output/context-isolated-sandbox.json` 原始成功结果；reviewer 本次未连接 Linux/生产重跑。 |
| 恢复来源到目标完整性证明不能目标自证 | 完整实现。`studio_context_probe.py:110`–`:137` 用独立 inspect plan 校验旧源当前哈希、来源归属、索引和实际目标 checksum，并逐条比冻结 inputs；`:153` 验证后才 `:164` 三次实际只读 sandbox。`test_studio_context_probe.py:44`、`:52` 包含删源、错源/索引/目标等失败对照，本次通过。 |
| inspect 只读、apply 固定摘要、指定生产旧文件恢复 | 工具完整，生产操作待执行。`context_workspace.py:71` 不创建目录/锁/下载；`restore_context.py:63` 固定 digest，`:55`–`:61` 提供独立冻结 inputs。`test_studio_restore_context.py:41`、`:63` 本次通过。原任务 2 原件/187 研究文件是已提供只读预演证据，reviewer 没有恢复生产。 |
| 0.2.36 包、固定旧基线/目标清单 hash、备份排空、无 DB 迁移 | 实现和发布单测通过，实际发布尚未执行。`scripts/release/overseas-context-deploy.py:18`、`:47`、`:70`、`:107`、`:122` 固定版本、基线和目标、验证备份停止状态并仅检查 schema；`overseas-context-recovery.py:34`–`:43` 重查停止/队列。相关发布测试本次 99 passed/24 subtests。 |
| 恢复逐项源覆盖、三次实际读取完成才切换开放，失败门禁 | 实现符合合同。`overseas-context-recovery.py:64`–`:78` inspect→固定摘要 apply→独立计划覆盖校验→三次读取，`:85` 才写 verified；继承 `overseas-upload-deploy.py:209` 起先关入口、排空和备份，before_switch 成功后才 switch/open。`scripts/release/test_overseas_context.py:52` 实际故障注入断言不切换、不开放，本次通过。 |
| UI/引导真实性与范围漂移 | 前端 diff 仅 `frontend/package.json:3` 版本变更，无新增页面、组件、样式或 Skill 选择记忆；不存在本候选新 UI 与邻居页面对比对象。恢复索引文件真实存在，提示时序有 M1-R。未发现合同范围外页面/API/数据库表；运维恢复与发布脚本属于明确授权范围。 |

## 已有缺陷复核

- **H1：已修复所报数据问题。** `context_migration.py:143` 纳入当前未登记文件、阻塞祖先和目录子树；`B/tests/test_studio_context_work_conflicts.py:28`、`:42`、`:75`、`:102`、`:140` 从预置字节集合证明编辑及新增文件不会被旧轮次覆盖，本次通过。
- **H2：已修复所报可编辑恢复路径问题。** `context_migration.py:103` 盘点实际映射内容，`:117` 只保留有真实来源的旧版本，`:123` 不覆盖编辑后的恢复位置，`:205` 保持普通逻辑编辑入口；`test_studio_context_edited_versions.py` 13 个展开用例本次通过，含再次编辑、copy/index/manifest 中断、故障期间编辑和仍存在的旧字节副本。
- **M1：成功准备后取消分支已修复，增量内部中断分支仍未闭环。** `context_workspace.py:103`–`:104` 现在对在线和维护恢复都写 notice；新增 notice 测试通过。独立复现说明依赖 `len(additions)` 的 changed 判断无法代表 journal 中已发生且尚未通知的迁移。

## 独立验证与原始输出

reviewer 在当前候选执行后端相关回归：

```text
./.venv/Scripts/python.exe -m pytest -q tests/test_studio_context_assets.py tests/test_studio_context_migration.py tests/test_studio_context_work_conflicts.py tests/test_studio_context_edited_versions.py tests/test_studio_context_notice.py tests/test_studio_context_safety.py tests/test_studio_context_probe.py tests/test_studio_persistent_mounts.py tests/test_studio_restore_context.py tests/test_studio_work_baseline.py tests/test_overseas_studio_execution.py
107 passed, 13 skipped, 2 warnings in 26.00s
```

两项警告原文：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
```

reviewer 在仓库根目录执行发布回归：

```text
./hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_context.py scripts/release/test_overseas_context_recovery.py scripts/release/test_package_overseas.py
99 passed, 24 subtests passed in 3.63s
```

reviewer 在 `B/` 执行语法编译，原始 stdout/stderr 为空、退出码 0；读取实际退出码后输出：

```text
./.venv/Scripts/python.exe -m compileall -q app tests ../../scripts
compileall exit=0
```

本次还读取以下主 Agent 提交的证据，但未冒充 reviewer 重跑或最终安装产物已验证：

```text
output/context-release-candidate-linux-tests.log:
2446 passed, 189 skipped, 15 warnings in 266.54s (0:04:26)
```

该 Linux 全量记录属于最后 M1 改动前的候选，最终安装镜像全量测试待审查通过后由主 Agent 执行。Windows 的 13 个平台条件 skip 和 Linux 的 189 个条件 skip 均不计入通过数。

`output/context-isolated-sandbox.json`：code=0、stderr 为空，stdout 原文：

```json
{"threeRounds": [{"round": 1, "originals": 7, "derived": true, "readonly": true, "isolated": true}, {"round": 2, "originals": 7, "derived": true, "readonly": true, "isolated": true}, {"round": 3, "originals": 8, "derived": true, "readonly": true, "isolated": true}], "legacyRecovery": {"conversationId": "12c2b593-ec55-4518-a8d4-8e45537cc25a", "independentSandboxReads": [{"readableFiles": 4, "allHashesMatch": true}, {"readableFiles": 4, "allHashesMatch": true}, {"readableFiles": 4, "allHashesMatch": true}], "sourceDigest": "12e4ed34b2b7a9e0aa02299bc9a7e02e6b6d81c9506c1402262224170f7a7ff9", "sourceFilesVerified": 4, "sourceInputsVerified": 2}}
```

这证明测试文件在实际 Linux sandbox 连续读取、只读与隔离，以及独立旧源计划覆盖目标；不证明已恢复生产目标、不证明模型完成出图，也不证明字体或商品素材充足。

## Stage 2 与交接

**Stage 2 未执行。** 按 Skill 的“Stage 1 通过才进 Stage 2”，本次不出具代码质量、安全扫描、完整测试真实性或视觉审查 PASS。上述路径/隔离/发布门禁检查为 Stage 1 合同核对，不能代替 Stage 2 安全结论；也未据既有依赖审计声称无安全风险。

本报告不能用于 `review-approve`。主 Agent 修复 M1-R 后应重新冻结 candidate，由独立 reviewer 从 Stage 1 复核并继续 Stage 2；不能用当前报告覆盖新快照或写 `.needs-review=clean` 放行。生产发布和旧会话恢复仍未由本报告批准。
