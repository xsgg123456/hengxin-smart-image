# 海外 Studio 文件连续性独立审查（第二候选）

- 日期：2026-10-15。
- candidateId：`6266e72745997d193b6b58c3ca840d437d81d99b1981658c501f0e9413f58781`。
- 仓库/分支：`D:/Work_Project/hengxin-smart-image`，`codex/studio-file-continuity`。
- Stage 1：**FAIL，1 项 HIGH（H2）**。
- Stage 2：**未执行**。依 code-review skill，Stage 1 存在 HIGH 时停止。
- 审查开始与完成复现后的 `review-status.currentId` 均等于上述候选；`approved=false`。报告落盘后再次检查已漂移为 `65540dac7ccfec3431a098df2d536a39d1aed6fae7f9818b041bf1d7aca76b3f`（主 Agent 已启动后续修复）。本报告只覆盖指定候选，未审新的快照，不能把旧结论用于批准新版本。
- 本 reviewer 只读取源码/证据，运行本地测试与临时文件复现，写此报告；未连接生产、未运行发布/恢复、未发起模型调用、未修改业务代码、未提交。

## 范围与依据

独立读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1157`、`DEV-PLAN.md:1417`、`docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md`。旧审查结果没有被当成当前代码的证明。

代码范围（下文 `B/` 代表 `hengxin-smart-image/backend/`）：

- `B/app/overseas/studio/context_fs.py`、`context_assets.py`、`context_migration.py`、`context_workspace.py`、`restore_context.py`、`work_baseline.py`、`execution.py`、`delivery.py`。
- `B/app/execution/persistent_mounts.py`、`workspace.py`、`B/app/overseas/execution/materials.py`。
- 对应 `test_studio_context_*`、`test_studio_restore_context.py`、`test_studio_persistent_mounts.py`、`test_studio_work_baseline.py`、`test_overseas_studio_execution.py` 和 `studio_context_probe.py`。
- `scripts/release/overseas-context-deploy.py`、`overseas-context-recovery.py`、相关 release/package 测试、`package-overseas.py`；`hengxin-smart-image/frontend/package.json` 的版本变化。

## HIGH：H2，编辑冲突恢复路径后，后续增量迁移永久拒绝导入

**合同：** `Product-Spec.md:1161` 明确“工作文件可编辑”；`:1162` 要求旧会话普通文件恢复、冲突可追溯、迁移可重入。方案 `docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md:115` 明确回退旧版新增轮次后必须重新盘点增量。

**具体位置：** `B/app/overseas/studio/context_migration.py:100` 的 `working_files()` 只盘点 `logical` 入口，未盘点已经公开的冲突 `path`；`:166` 对 `.context-recovered/...` 下的目标按旧校验值验证，`:169` 直接抛错。这些目标属于模型可写的 `/work`，没有只读挂载；`B/app/execution/workspace.py:91`、`B/app/execution/persistent_mounts.py:38` 证明只读覆盖只保护 inputs、input.json、索引和 Skill。

**可达步骤：**

1. 同会话两个旧轮次都有 `notes.txt`，内容分别为 `old-one`、`old-two`。
2. 首次迁移成功，索引给出两个 `.context-recovered/<turn>/<hash>/notes.txt` 路径。
3. 模型按索引编辑第一个普通文件。此路径确实可写；相同历史再次 prepare 也成功（没有 additions 时 `:154` 提前返回）。
4. 回退旧版，新增一个只含 `unrelated.txt` 的轮次。
5. 再升级，prepare 需要合并新增轮次，却因已编辑的恢复路径抛 `ValueError: 已恢复的历史版本发生改变：notes.txt`。即使新轮次与该笔记无同名冲突，也不能恢复。

**影响：** 用户合法编辑普通恢复文件后，新增历史恢复被阻断；重试相同输入仍在同一校验处失败。旧源及编辑字节尚存，本次没有证明字节丢失，但“可编辑 + 回退新增轮次再升级恢复”核心合同不成立。

**独立最小复现：** 在 backend 目录用 `.venv/Scripts/python.exe` 执行以下代码；只操作 `TemporaryDirectory`，不依赖数据库、网络或模型。

```python
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, 'tests')
from test_studio_context_assets import workspace
from test_studio_context_migration import write, row, index
from app.overseas.studio import context_workspace as context

with tempfile.TemporaryDirectory(prefix='review-context-') as d:
    root = Path(d)
    old = workspace(root)
    second = workspace(root, old.home.parent.name)
    write(old.work, 'notes.txt', b'old-one')
    write(second.work, 'notes.txt', b'old-two')
    current = workspace(root, old.home.parent.name)
    history = [row(old), row(second)]
    context.prepare(current, history, [], lambda _: None)
    edited = current.work / index(current)['files'][0]['path'].removeprefix('/work/')
    edited.write_bytes(b'edited recovered ordinary file')
    context.prepare(current, history, [], lambda _: None)
    rollback = workspace(root, old.home.parent.name)
    write(rollback.work, 'unrelated.txt', b'new legacy round')
    try:
        context.prepare(current, [*history, row(rollback)], [], lambda _: None)
        print('unexpected success')
    except Exception as exc:
        print(json.dumps({
            'exception': type(exc).__name__, 'message': str(exc),
            'edited_work_preserved': edited.read_bytes() == b'edited recovered ordinary file',
            'new_legacy_file_imported': (current.work / 'unrelated.txt').exists(),
            'old_source_preserved': (old.work / 'notes.txt').read_bytes() == b'old-one',
        }, ensure_ascii=True))
```

原始输出（捕获异常后脚本 exit 0，不代表行为通过）：

```text
{"exception": "ValueError", "message": "\u5df2\u6062\u590d\u7684\u5386\u53f2\u7248\u672c\u53d1\u751f\u6539\u53d8\uff1anotes.txt", "edited_work_preserved": true, "new_legacy_file_imported": false, "old_source_preserved": true}
```

**修复完成标准：** 盘点实际公开的恢复路径及其新编辑版本；原历史版本、编辑版本、回退新增轮次都必须有可读取且校验正确的来源映射。不能删除校验或覆盖编辑来绕过错误。补充“已恢复冲突文件编辑后再次迁移”“workspace 来源版本再次编辑”“中断后重试”的固定原始字节集合断言，并重新执行上述复现。

## Stage 1 逐条对照

以下结论只对说明的子行为成立；整项“旧会话无损增量恢复”因 H2 不通过。

| 合同条目 | 结论与证据 |
| --- | --- |
| 同 conversation 的原件和研究文件跨至少三轮保留，纯文本不清空 | 已实现基本路径。`B/app/overseas/studio/context_workspace.py:74` 固定 persistent/work；`execution.py:34` 从 DB 读已派发历史。`B/tests/test_studio_context_assets.py:35` 实际跨轮读首轮原件和笔记且只下载一次；本次运行通过。 |
| 新会话/任务隔离，未提供资料不自动带入 | 已实现。`context_workspace.py:23` 验证会话/轮次根；`execution.py:22` 校验 turn/task/conversation；`context_assets.py:40` 仅注册冻结历史及本轮 inputs。`B/tests/test_studio_context_assets.py:96`、`test_studio_context_safety.py:101` 覆盖新会话为空和跨会话轮次拒绝。 |
| 原件按资源/内容版本保存、同名追加、缺失/损坏恢复 | 已实现。`context_assets.py:30` 版本身份、`:67` 冻结元数据/字节校验及恢复。`B/tests/test_studio_context_assets.py:59`、`:75`、`:88` 分别覆盖同名多版本、缺失/篡改修复、错误字节不提交初始布局；本次运行通过。 |
| 原件只读，普通工作文件可编辑 | 原件只读挂载已实现，`B/app/execution/persistent_mounts.py:38`；`B/tests/test_studio_persistent_mounts.py:24` 校验挂载。普通直接路径可以编辑；**冲突恢复路径编辑后的后续迁移不通过，H2**。 |
| 输入/日志/Skill 每轮独立；未选择不暴露旧 Skill；用户消息不变 | 已实现代码路径。`B/app/overseas/execution/materials.py:14` 使用 control 和 round_work；`B/app/execution/workspace.py:100` 隐藏旧发现目录，`:108` 只读 Skill；`execution.py:84` 使用原消息文本，`:87` 只追加恢复提示。`B/tests/test_studio_persistent_mounts.py:24` 覆盖有/无选择。未新增 Skill 选择记忆。 |
| DB 归属、session 延续、无业务记录重写 | 已实现恢复入口约束。`B/app/overseas/studio/restore_context.py:21` 查会话/任务，`:35` 阻断运行/不确定进程，`:43` 校验 turn/job 归属，`:53` 要求旧 session 文件。`B/tests/test_studio_restore_context.py:41` 检查 session、job 状态/执行次数和原 reply 不变；`:72` 检查不确定进程门禁。 |
| 旧路径无损迁移、冲突索引、失败原子/重入、回退新增轮次 | **部分实现，H2 阻断。** 初次临时目录原子 rename：`context_workspace.py:87`、`:109`；增量 journal：`context_migration.py:145`、`:184`；已复制后再删歧义入口：`:188`。前次 H1 已闭环，见下一节；H2 显示这些通过项不能扩展为所有增量情况通过。 |
| 链接/硬链接/越界/空间故障应阻断并保留源 | 已实现所审路径。`context_fs.py:15`、`:23`、`:65`、`:160`；`B/tests/test_studio_context_safety.py:22`、`:47`、`:75`、`:86` 覆盖硬链接、控制入口、空间、存储失败。本次运行通过的用例计入，平台跳过项不计已实测；Linux安全分支不能用 Windows 结果替代。 |
| 仅最终明确交付的新增/修改图片；不收旧图/输入/Skill/草稿 | 已实现代码及本地用例。`work_baseline.py:120` 执行前摘要；`:142` 对实际校验字节判旧图；`delivery.py:144` 保留显式引用及归属门禁，`:166` 检查 work 基线。`B/tests/test_studio_work_baseline.py:55`、`:68`、`:80`、`:109`、`:147` 覆盖新改旧图、相同 mtime 下修改、保护资源及混合无效引用。 |
| 修改工作图不改变已交付/归档版本 | 输出继续用独立 UUID/object_key，`execution.py:115`；`B/tests/test_studio_work_baseline.py:90` 验证原交付字节不随工作图修改。归档/删除模块本次未修改；全量归档回归在审查停止时尚不能据正在运行的日志宣布通过。 |
| 取消/失败/uncertain 不重复启动；刷新/重启保持文件 | 当前工作区按磁盘状态重新加载，不依赖前端内存，`context_workspace.py:40`、`:82`。`B/tests/test_overseas_studio_execution.py:151`、`:163` 覆盖 uncertain 不重复及 session 缺失拒绝；本次相关测试集通过。取消/真实 worker 重启/全量回归仍按最终完整证据核验，不由这些单例替代。 |
| Linux 真实三轮读取、所有输入类别、边界限制、共享旧路径回归 | 已读取所交隔离沙箱结果：7→7→8 原件、研究文件/只读/隔离均 true。实现 `B/tests/studio_context_probe.py:46`；结果只证明 fixture 沙箱，未证明生产旧会话已恢复。500 MB 验证在 `context_assets.py:17`；本次未改每轮100附件服务规则。共享工作区仅 `persistent` 分支增加挂载（`B/app/execution/workspace.py:93`），完整共享路径回归仍需最终全量证据。 |
| 恢复按 inspect 清单固定、实际 source→target 对照后再开放 | 代码存在：`restore_context.py:55`、`:65`；`B/tests/studio_context_probe.py:117` 对独立旧源 hash、索引目标、冻结 inputs 逐项检查；`scripts/release/overseas-context-recovery.py:64`、`:71` 固定摘要及核对覆盖数量。`B/tests/test_studio_context_probe.py:52` 六种故障注入本次通过。发布逻辑 `overseas-context-deploy.py:107` 要求完整备份/排空/恢复标记；H2 未解决前不能批准执行。 |
| 0.2.36 包完整、无 DB 迁移、基线固定、失败不开入口 | 发布代码契约已对照：`scripts/release/overseas-context-deploy.py:18`、`:26`、`:47`、`:70`、`:107`；`package-overseas.py:21`、`:63` 要求版本与新增运行/恢复/probe 文件。所交 release 回归日志157通过、72子测试通过；当前未构成真实安装/切换结果的独立批准。 |
| UI 一致性/引导真实性/范围漂移 | 本候选前端仅 `hengxin-smart-image/frontend/package.json:3` 版本变化，未改页面、控件、文案或增加 API/表；恢复提示 `execution.py:87` 指向实际只读索引。没有采纳源方案中可选 Skill 选择记忆。UI 视觉对比因无 UI 变更不适用；Stage 2 视觉与完整安全/质量审查未执行。 |

## 前次 H1 的复核

前次问题为 persistent/work 中未登记同名文件未纳入冲突盘点。候选现在在 `context_migration.py:100` 实际检查原路径、阻塞祖先和目录子树，`:158` 并入冲突计算，`:177` 校验无歧义目标。

`B/tests/test_studio_context_work_conflicts.py:28`、`:42`、`:75`、`:102`、`:140` 使用事先固定的字节集合校验未登记工作文件、已编辑普通入口、深层文件/目录冲突、metadata 故障和复制中断，不只是把生成的索引与自身比较。本次这些测试通过（链接权限不足的用例跳过）。**H1 原复现形态已修复；它没有覆盖 H2 的已映射冲突路径编辑。**

## 验证原始输出及边界

本 reviewer 在当前候选运行：

```text
./.venv/Scripts/python.exe -m pytest -q tests/test_studio_context_assets.py tests/test_studio_context_migration.py tests/test_studio_context_work_conflicts.py tests/test_studio_context_safety.py tests/test_studio_context_probe.py tests/test_studio_persistent_mounts.py tests/test_studio_restore_context.py tests/test_studio_work_baseline.py tests/test_overseas_studio_execution.py
91 passed, 13 skipped, 2 warnings in 17.90s
```

13 项跳过未算通过。两项警告为已安装 Starlette/TestClient 的 httpx 与 anyio BlockingPortal 弃用提示；该测试运行 exit 0。该套现有测试未覆盖 H2，不能以91通过覆盖独立失败复现。

编译命令及原始输出（exit 0）：

```text
./.venv/Scripts/python.exe -m compileall -q app tests ../../scripts
compileall app tests ../../scripts: exit 0
```

所交证据文件只读检查：

```text
output/context-release-final-tests.log:
157 passed, 72 subtests passed in 5.16s

output/context-isolated-sandbox.json:
{"code": 0, "stdout": "{\"threeRounds\": [{\"round\": 1, \"originals\": 7, \"derived\": true, \"readonly\": true, \"isolated\": true}, {\"round\": 2, \"originals\": 7, \"derived\": true, \"readonly\": true, \"isolated\": true}, {\"round\": 3, \"originals\": 8, \"derived\": true, \"readonly\": true, \"isolated\": true}]}\n", "stderr": "", "source": "/var/tmp/hx-context-probe-b956987676b44116886d79e331af505b"}
```

全量 Linux 日志在本 reviewer 读取时仍进行中（71%），本报告不把“没有已见失败”写为全量通过。未运行浏览器、生产恢复、真实安装或付费模型测试。

## Stage 2 与交接

Stage 2 未执行；完整代码质量、安全扫描、依赖审计和相应结论均未给 PASS。Stage 1 的合同隔离校验不代替 Stage 2 安全审查。

修复路由：H2 属于当前 Spec 规定的可编辑工作文件/增量迁移行为缺陷，由主 Agent 完成修复后重新固定快照，并从 Stage 1 开始审查。禁止用本报告登记 `review-approve`，禁止写 `.needs-review=clean`。
