# 工作台多轮文件连续性审查（2026-10-15）

## 快照与结论

- candidateId：`c184666c74e1988a5639b54b1da203157bb9a247b58df30f9692f5ddd071b01e`。
- 分支：`codex/studio-file-continuity`；仓库：`D:/Work_Project/hengxin-smart-image`。
- **Stage 1：FAIL，1 项 HIGH。Stage 2：未执行。不得登记两阶段 PASS。**
- 审查依据：`Product-Spec.md:1157` 至本节末、`DEV-PLAN.md` 2026-10-15 文件连续性部分、`docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md`，按 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md` 执行。
- 开始审查及复现、测试结束后的 `review-status` 返回上述 currentId，`approved: false`。报告写完再次检查时，修复工作已使 currentId 变为 `d7cb74fd7fb832546c83f50b2a7617657cf3d5e4c5ee3c9e8408f55f2014f915`，并新增 `tests/test_studio_context_work_conflicts.py`。本报告仅适用于原候选；新内容未由本轮复审，必须重新 prepare、重新审查，不能沿用本报告批准。
- 审查不连接生产、不运行模型、不修改业务代码、不提交；仅使用本地临时目录复现与测试，读取已有验证日志。

代码路径以下统一以 `hengxin-smart-image/backend/` 为前缀，发布脚本、源文档、output 路径相对仓库根目录。

## 审查范围

- `app/overseas/studio/context_fs.py`、`context_assets.py`、`context_migration.py`、`context_workspace.py`、`restore_context.py`、`work_baseline.py`、`execution.py`、`delivery.py`。
- `app/execution/persistent_mounts.py`、`workspace.py`；`app/overseas/execution/materials.py`。
- `tests/test_studio_context_assets.py`、`test_studio_context_migration.py`、`test_studio_context_safety.py`、`test_studio_persistent_mounts.py`、`test_studio_restore_context.py`、`test_studio_work_baseline.py`、`test_overseas_studio_execution.py`、`studio_context_probe.py`。
- `scripts/release/overseas-context-deploy.py`、`overseas-context-recovery.py`、`test_overseas_context.py`、`test_overseas_context_recovery.py`、`package-overseas.py`、`test_package_overseas.py`。
- `hengxin-smart-image/frontend/package.json` 版本变更；需求、方案、计划变更。为判断接入可达性，另读取既有 service、runner、claims、清理和发布主流程。

## Stage 1：阻断问题

### HIGH / H1：回退增量遇到未登记的工作文件时，恢复索引指向错误字节

**要求：** `Product-Spec.md:1162` 要求“保存来源/校验值/冲突索引，历史同路径不同内容不静默覆盖”；方案第 5 节要求回退后新增轮次重新盘点增量，不能继续信任旧标记。

**实际代码：** `app/overseas/studio/context_migration.py:106` 只合并 manifest/journal 与新扫描的历史文件；`:112` 从这组历史记录推导冲突。只有已经属于冲突集合的路径才在 `:115` 检查现存工作副本。对于未登记过的新路径，`:138` 至 `:144` 发现目标存在后只验证它是普通文件，直接把新历史记录指向该目标，并设置 `conflict=False`，不比较字节或保存新历史版本。

**真实可达顺序：**

1. 旧轮次仅有 `old.txt`，升级执行 `prepare`，生成 persistent 布局。
2. 新版 CLI 在持续工作目录创建 `new.txt`，内容为 `created in persistent work`；普通工作文件不会自动登记到迁移 manifest。
3. 回退旧版后，新轮次在自己的 rounds 目录创建同名 `new.txt`，内容为 `created after rollback`。
4. 再升级并对所有数据库归属轮次执行 `prepare`。
5. 返回成功，索引声称历史来源为回退轮次、校验值属于 `created after rollback`，实际 `/work/new.txt` 仍是 `created in persistent work`；新历史版本没有复制到任何沙箱可见恢复路径。

本地直接调用真实 `context.prepare`，非模拟算法。原始输出：

```text
{"conflict": false, "actual": "created in persistent work", "source": "created after rollback", "index": {"conflict": false, "logicalPath": "/work/new.txt", "name": "new.txt", "path": "/work/new.txt", "sourceChecksum": "ceb4b45ae47fe807e2fd4334ea4a5791538e8b65d4beed6a873f254431eed093", "sources": ["00ecd503-dcb4-4a2a-8b51-4b05be4f1e43"]}}
Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: Restored index points to different content; rollback version unavailable under persistent work
```

复现命令在 backend 目录以 `.venv/Scripts/python.exe -` 执行，退出码 1。最小复现主体如下（辅助函数来自现有测试，只负责建立真实目录与字节）：

```python
import json, tempfile, sys
from pathlib import Path
sys.path.insert(0, 'tests')
from test_studio_context_assets import workspace
from test_studio_context_migration import write, row
from app.overseas.studio import context_workspace as context
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    old = workspace(base)
    write(old.work, 'old.txt', b'old')
    current = workspace(base, old.home.parent.name)
    history = [row(old)]
    context.prepare(current, history, [], lambda _: None)
    write(current.work, 'new.txt', b'created in persistent work')
    rollback = workspace(base, old.home.parent.name)
    write(rollback.work, 'new.txt', b'created after rollback')
    context.prepare(current, [*history, row(rollback)], [], lambda _: None)
    entry = next(x for x in json.loads(current.context_index.read_text())['files']
                 if x['name'] == 'new.txt')
    target = current.work / entry['path'].removeprefix('/work/')
    assert target.read_bytes() == (rollback.work / 'new.txt').read_bytes()
```

**影响：** 源文件没有被删除，但新历史版本不能从持续工作目录读取，模型会依错误来源索引读到另一份内容。已有 `tests/test_studio_context_migration.py:107` 仅覆盖目标原先已经在 manifest 的情况，不能覆盖上述输入。`tests/studio_context_probe.py:120` 从恢复后的目录重新计算 expected，三次读取一致只能证明该目录可读，不能发现源版本被遗漏。

**修复验收：** 把现存工作文件也纳入冲突判断，包括未登记路径、文件/目录及父子路径碰撞；保留各来源和工作副本，索引路径对应真实字节，重试不能丢失版本。补上述回退增量用例，校验两份内容均在 `/work` 可见；源到目标的完整性验证不能只对目标自己计算基准。修复后从 Stage 1 重新审查。

## Stage 1：Spec 逐条核对

下表“已验证部分”只描述列出的行为，不代表整个候选或整个 Spec 通过。

| Spec 条目 | 结论 | 实现与验证证据 |
| --- | --- | --- |
| 1160：同 conversation 持续目录、纯文字续聊、worker 重建工作区不清空 | 已验证部分 | `app/overseas/studio/context_workspace.py:74` 从磁盘 manifest 重载，`:119` 固定 persistent/work；`execution.py:34` 读取已派发历史。`tests/test_studio_context_assets.py:33` 连续三轮保持原件与笔记且仅下载一次；`tests/test_overseas_studio_execution.py:66` 经 runner 验证 resume 和第二轮原文件。上述测试本地通过；独立 worker 进程重启的生产验收未由 reviewer 运行。 |
| 1160：任务原件、上传附件、图片引用，未提供资料不自动加入 | 已验证部分 | `app/overseas/studio/service.py:51` 仅冻结显式附件/图片，`:60` 同一 source 契约；`execution.py:34` 仅加载本 conversation 已派发轮次；`context_assets.py:40` 累加冻结输入。`tests/test_studio_context_assets.py:56` 验证同名不同内容及同资源不同 checksum 各有路径。实际 Linux probe 使用七种扩展名的已知字节，不能把这些简单 fixture 当成 Office/字体内容解析验收。 |
| 1160：新 conversation 与任务隔离 | 已验证部分 | `app/overseas/studio/service.py:73` 新建 Conversation；`context_workspace.py:23` 验证 home/round 所属 UUID 根目录；`app/execution/workspace.py:94` 仅绑定本 home/work。`tests/test_studio_context_assets.py:96`、`test_studio_context_safety.py:101` 本地通过；实际三轮沙箱日志各轮 isolated=true，见下文边界。 |
| 1161：原件只读、校验、缺失恢复，工作文件可编辑 | 已验证 | `app/overseas/studio/context_assets.py:67` 校验已有原件并从冻结来源修复；`:99` 比较大小及 SHA256；`app/execution/persistent_mounts.py:38` 原件 ro-bind。`tests/test_studio_context_assets.py:70` 删除/篡改后恢复；`test_studio_context_safety.py:86` 存储失败保留工作文件并标明文件名；本地通过。已有 Linux probe 记录 readonly=true、derived=true。 |
| 1161：控制文件/日志按轮、原文保留、本轮 Skill 完整挂载和未选隔离 | 已验证部分 | `app/execution/workspace.py:31` 按 round 建 control；`app/overseas/execution/materials.py:15` 控制快照独立，`:16` Skill 写到 round_work；`app/execution/persistent_mounts.py:39` 输入/index 只读，`:41` 用 tmpfs 屏蔽历史 Skill；`app/execution/workspace.py:104` 屏蔽旧发现目录，挂载当前 Skill；`execution.py:84` 直接加入原文。`tests/test_studio_persistent_mounts.py:24` 有/无选择与挂载顺序通过；完整已安装 Skill 资源沿用 `materials.py:22` 冻结包入口。没有新增 Skill 记忆行为。 |
| 1162：数据库归属、session 保持、恢复工具不改业务记录 | 已验证 | `app/overseas/studio/restore_context.py:25` 锁任务及接纳门，`:33` 拒绝忙任务或进程未确认退出，`:41` 交叉校验 Turn/Job 归属，`:51` 要求原 session 文件存在，`:55` 核对预演 digest；不新增/更新 Turn、Job 或 Conversation。`tests/test_studio_restore_context.py:41` 校验 session、reply、执行次数不变，`:63` 来源变化拒绝、`:72` 不确定进程拒绝，本地通过。 |
| 1162：来源/冲突索引与旧文件完整可见 | **部分实现，H1 阻断** | `app/overseas/studio/context_migration.py:74` 已覆盖历史版本之间的冲突，`:85` 版本路径可见；`tests/test_studio_context_migration.py:57`、`:76` 通过。新增 persistent 文件与回退增量冲突漏判，实际复现见 H1。 |
| 1162：原子启用、失败保留源文件、可重入 | 已验证部分 | `app/overseas/studio/context_workspace.py:87` 初始临时目录，`:103` 写 manifest，`:109` 原子 rename；`context_migration.py:148` 在复制/删除别名前写 journal。`tests/test_studio_context_migration.py:122` 复制中断、`:180` 索引写失败后重试保留工作副本均通过。H1 表明增量场景仍不完整。 |
| 1163：仅最终明确引用的新增/修改图，历史不变图、原件、Skill、草稿门禁 | 已验证 | `app/overseas/studio/execution.py:75` 启动前建立基线；`work_baseline.py:120` 遍历/哈希失败即中止，`:142` 比较实际收图字节 checksum；`delivery.py:158` 沿用路径归属门禁，`:166` 追加基线校验。`tests/test_studio_work_baseline.py:55`、`:68`、`:80`、`:109`、`:119`、`:147`、`:157` 本地通过，覆盖新图、同大小同 mtime 内容变化、历史原图、protected、原生 session 和混合引用。 |
| 1163：归档版本独立；删除会话含 persistent 而保留归档 | 代码匹配，运行回归未独立复跑 | `app/overseas/studio/execution.py:115` 为每份交付生成独立对象；`service.py:114` 归档调用 protect；`app/overseas/tasks/cleanup_files.py:33` 独立归档保护，`:63` 按 DB Conversation 清理整个会话根，包含新 persistent。`tests/test_studio_work_baseline.py:90` 验证前一交付字节不受工作文件修改影响。本轮 reviewer 未执行完整删除/归档集成场景，不把代码检查当实际删除验收。 |
| 1164：三轮真实 Linux、同名、隔离、缺失、失败/取消、磁盘/路径、共享旧路径回归 | 验证部分完成，整体未通过 | reviewer 本地相关测试 72 passed/12 skipped；磁盘、对象存储、硬链接、Windows junction、跨进程锁用例通过，POSIX/symlink 条件跳过不可算通过。已有 `output/context-isolated-sandbox.json` 三轮证据支持实际挂载可读。`tests/test_overseas_studio_execution.py:151` 不确定执行不重复启动、`:163` session 缺失不替换通过。共享旧路径通过 persistent 属性分支保持，`app/execution/workspace.py:96`；完整 Linux/取消/归档回归由主 Agent 另行汇总，本报告不据尚未完成日志宣称全过。 |
| 1165：本轮无选择记忆 UI；发布与指定旧会话恢复 | 实现部分，未执行发布 | 前端仅 package.json 版本变化，无新增 UI。`scripts/release/overseas-context-deploy.py:47` 固定 .35/adf861b 基线，`:70` 冻结 targets，`:107` 在 switch 前要求备份/停工并恢复验证；`overseas-context-recovery.py:35` 重新确认停工/无任务，`:63` inspect→apply→三次沙箱读取。父流程 `overseas-upload-deploy.py:226` 恢复成功才 switch，`:262` 异常关闭接纳；`package-overseas.py:45`、`:66` 要求新脚本/模块/probe 入包。脚本存在及发布测试日志不能替代实际安装/生产恢复验收，且 H1 会阻止当前候选放行。 |

## 引导真实性、UI 与范围漂移

- 没有新增用户界面或交互，前端变更仅 `hengxin-smart-image/frontend/package.json:3` 的版本号；无本次设计稿对比对象，Stage 1 UI 一致性不适用。
- `app/overseas/studio/execution.py:87` 恢复提示指向真实只读 `.context-files.json` 挂载。但 H1 下该索引的来源声明不真实，已经计入同一 HIGH。
- 新增的是 Spec 已授权的持久目录、迁移、恢复工具、输出基线及发布验证，未发现新增页面/API/业务表；可选 Skill 选择记忆没有实施。此次不对无关既有需求作完成判断。

## 验证与编译原始结果

reviewer 在 backend 目录运行：

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_context_assets.py tests/test_studio_context_migration.py tests/test_studio_context_safety.py tests/test_studio_persistent_mounts.py tests/test_studio_work_baseline.py tests/test_studio_restore_context.py tests/test_overseas_studio_execution.py -q
72 passed, 12 skipped, 2 warnings in 14.35s
```

退出码 0。警告为现有 Starlette/httpx 与 anyio BlockingPortal 弃用提示。12 个条件跳过保留，不当作安全能力通过；H1 的额外真实复现失败不在上述已有测试中。

reviewer 编译本次 11 个 app Python 文件：

```text
.venv/Scripts/python.exe -m compileall app/overseas/studio/context_fs.py app/overseas/studio/context_assets.py app/overseas/studio/context_migration.py app/overseas/studio/context_workspace.py app/overseas/studio/restore_context.py app/overseas/studio/work_baseline.py app/overseas/studio/execution.py app/overseas/studio/delivery.py app/execution/persistent_mounts.py app/execution/workspace.py app/overseas/execution/materials.py
```

原始 stdout/stderr 均为空，退出码 0。只证明 Python 语法编译，无功能通过含义。

独立读取主 Agent 保存的原始日志（未在 reviewer 中重跑）：

```text
output/context-frontend-tests.log
ℹ tests 364
ℹ pass 364
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8869.3714

output/context-frontend-build.log
✓ built in 32.11s

output/context-release-tests.log
156 passed, 72 subtests passed in 5.67s
```

`output/context-isolated-sandbox.json` 原始结果包含 code=0、stderr 空，stdout 为：

```json
{"threeRounds":[{"round":1,"originals":7,"derived":true,"readonly":true,"isolated":true},{"round":2,"originals":7,"derived":true,"readonly":true,"isolated":true},{"round":3,"originals":8,"derived":true,"readonly":true,"isolated":true}]}
```

`tests/studio_context_probe.py:20` 使用真实 sandbox_command 并添加 unshare-net，执行 Python 字节校验，未发起模型调用。这证明文件挂载能力，不证明真实模型生成、字体可用或当前素材足够。读取 `output/context-backend-linux-tests.log` 时全量仍在运行，仅到 71%，本报告不把它列为完整通过。

## Stage 2

**未执行。** Stage 1 存在 HIGH，按 skill 停止；未给代码质量、安全扫描或视觉对比 PASS。修复 H1、固定新快照后需从 Stage 1 重审，再决定是否进入 Stage 2。reviewer 未执行 review-approve，也未写 `.needs-review`。
