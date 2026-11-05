# 批量标注最终候选复审与业务哈希关联

日期：2026-11-05。candidateId：`782a7ddf7236b2a23294a8bcafaf8d1875f2f86b4f114755cd8ecb5d6c7f7d3b`。

**Stage 1：FAIL；Stage 2：未执行。不能登记两阶段 PASS。**

范围：`scripts/release/studio-batch-*.py`、`scripts/release/test_studio_batch*.py`（15 文件）及既有调用 helper；业务部分关联 `docs/STUDIO-BATCH-FINAL-FEATURE-REVIEW-20261105.md` 的 33 文件。依据：code-review skill、HARNESS-REVIEW、发布计划全部条目及正式实施合同发布条目。未修改代码、提交或操作生产。

## HIGH R4 剩余：恢复复制半写后，真实入口仍不能重入

- 合同要求发布计划恢复段“中断后可从真实 state/guard 重新进入”；上轮 R4 明确要求避免恢复留下既非旧哈希亦非新哈希的半文件。
- `scripts/release/studio-batch-native.py:66` 用 `shutil.copy2(record['backup'], path)` 直接覆盖 native 源文件。复制中进程退出或 I/O 故障可留下空文件/半文件。
- `scripts/release/studio-batch-recovery-state.py:41` 只允许完整旧/新哈希，第 42 行拒绝半文件。重试 `studio-batch-recovery.py:45` → `sku-deploy.py:29` → `studio-batch-runtime.py:46` 先调用此 guard，无法到达 restore。API/native 已停止，即使原始备份正确也无法按文档命令恢复。
- 测试盲区：`scripts/release/test_studio_batch_reentry.py:99` 的 copy 替身先完成 original_copy 才抛错，仅覆盖完整旧字节复制后的窗口。
- 实际复现：调用该测试 `ReentryTests().exercise('copy')`，将其 original_copy 传输替换为向目标只写 `b'old'` 后抛 `OSError('interrupted partial file copy')`；其他真实临时文件、backup、markers、recover、sku.state/guard 不变。首次异常由测试捕获，下一次真实 state 失败：

```text
PARTIAL_COPY_REAL_ENTRY_RETRY: RuntimeError Native recovery source drift
```

修复验收：恢复也采用校验后的同目录临时文件原子替换，保持权限/属主；定义严格的临时残留重试规则，不能放宽 live 哈希保护；新增部分写入、replace 前/后中断的真实入口测试，重新固定 candidate。

## Stage 1 全部发布条目

下表“匹配”指源码与本地回归，不代表生产步骤执行。简写文件均位于 `scripts/release/`。

| 条目 | 结论与证据 |
| --- | --- |
| 版本、基线、0026 不迁移 | 匹配。`studio-batch-runtime.py:11`、`:12`；`studio-batch-deploy.py:23`；`polling-database.py:65` 仅备份/隔离恢复。 |
| API 五模块、native 单模块 | 匹配。`studio-batch-runtime.py:13`、`:15`、`:74`；`studio-batch-native.py:34` 精确文件和根路径。 |
| 步骤 1 干净固定提交、正式包审查批准 | 工具匹配，提交待执行。`studio-batch-package.py:20`、`:24`、`:68` 构建前后检查 clean/commit/candidate。 |
| 步骤 2 allowlist、递归依赖、隐私与全部 hash | 匹配。`studio-batch-package.py:31` 来源/隐私；`:49` collect_tests；`:65` 全摘要；`studio-batch-runtime.py:61` 至 `:80` 文件集合/路径/链接/hash。包篡改回归通过。 |
| R2 固定 commit 隔离前端构建 | 已修复。`studio-batch-build.py:47` Git 导出；`:57` 新目录；`:75` 拒绝 tracked dist；`:86` 锁版本；`:91` frozen lock；`:92` 生产构建；`:93` 来源不变；`:99` 来源/产物摘要。构建失败与篡改回归通过；正式包构建待提交后执行。 |
| 步骤 3 prepare 只建镜像、保护资源、实际 Compose | 匹配。`studio-batch-deploy.py:35` compose_info；`:54` COPY；`:59` image-only overlay；`:62` 完整配置对比；`:64` 资源复查。 |
| 步骤 3 实际镜像路径、默认身份、只读测试、隔离 PG | 工具匹配，生产安装测试待执行。`sku-deploy.py:116` network none PG；`:133` 只读 /app/tests、PYTHONPATH=/app、无 user 覆盖；`:106` passed 且无 failed/skipped；`:138` manifest/image 凭据。 |
| 步骤 4 检查在途/导入、停 API 后重查、暂停 consumer | 匹配。`studio-batch-deploy.py:78` 至 `:94`；`:87` docker 无限优雅停止，调用限 60 秒。gate/竞态回归通过。 |
| 步骤 4 禁 SIGKILL、outbox 先停、统一期限 | 匹配。`sku-native.py:96` 首次停机；`studio-batch-recovery-state.py:68` 恢复停止；`:76` 同字节保护复用；`:84` 验证禁强杀；`:86` 统一 60 秒；`:87` 反序。超时保留保护回归通过。 |
| 步骤 4 私有备份、独立恢复、表/schema 对比 | 工具匹配，生产待执行。`polling-database.py:19` gate；`:30` 独立恢复；`:52` fingerprints/schema；`:65` 私有备份；`:85` 安装前验真。 |
| 步骤 5 原备份、原子安装、真实身份探针 | 正向匹配，恢复部分实现。`studio-batch-native.py:18` 原备份；`:39` 临时文件；`:44` 原子替换；`:48` runuser；`:101` 实际路径语义探针；`sku-native.py:180` UID999/cwd。R4 阻断半写恢复。 |
| 步骤 6 native 验证后切 API、刷新网关 | 匹配。`studio-batch-deploy.py:110` API 停止；`:112` 备份；`:115` native verified；`:117` no-deps；`:118` refresh。 |
| 步骤 6 环境、国内、Skill、其他资源保持 | 匹配。`sku-deploy.py:29` 至 `:35`；`studio-batch-deploy.py:128` 环境、`:132` ready；`studio-batch-recovery-state.py:27`、`:48`、`:49` 无关配置/PID/源码。 |
| 步骤 6 前端保留 hash、备份 HTML、公网字节 | 匹配，生产待执行。`sku-frontend.py:28` 部署；`studio-batch-deploy.py:148` hash；`:153` 至 `:160` 公网 HTML/入口 JS/CSS 字节。 |
| 步骤 7 正式 1920/1440/390、交互/历史、不收费 | 后续验收。`docs/STUDIO-BATCH-RELEASE-PLAN-20261105.md:26`；`studio-batch-deploy.py:162` 明确仍需浏览器验收。 |
| candidate 只准 prepare/test | 匹配。`studio-batch-deploy.py:19` release 门禁；候选 gate/恢复拒绝测试通过。 |
| R1 暂停 consumer 与 gate 部分完成 | 已修复。`studio-batch-worker.py:12` 固定 node/PID/pool/队列；`studio-batch-recovery.py:14` 分流；`:49` 补 gate；`:6` pending job 拒绝。partial_gate 测试真实经过 worker CLI。 |
| R3 旧验证 PID 与保护文件重入 | 已修复所报窗口。`studio-batch-recovery-state.py:13` 绑定 phase/PID/hash；`:34` 停机只准原 PID/0；`:76` 同字节保护复用。真实入口 outbox 已停/worker 尚存测试通过。 |
| R4 完整旧字节落盘、部分 marker 退场 | 两窗口已修复，但 R4 未关闭。`studio-batch-native.py:60` restoring；`:69` marker 迁移；`:75` finish 后 start；`test_studio_batch_reentry.py:161`、`:164` 回归通过。半文件仍失败。 |
| pending stop/入队竞态 | 匹配。`studio-batch-recovery.py:52` settled；`:68` 恢复中禁止开放 API；`:71` 先恢复 native，`:72` 后开 API；回归通过。 |
| 切换前 recover、切换后 rollback、不回灌 DB | 部分实现。`studio-batch-recovery.py:46` 阶段门禁；`:75` 至 `:98` 无 DB 回灌，恢复原 native/API/frontend；R4 阻断半写重试。 |
| Spec 漂移/引导真实性 | 本发布范围未发现额外产品功能。`studio-batch-runtime.py:13` 至 `:24`、`studio-batch-deploy.py:174` 与发布操作对应；无新增 UI。 |

## 业务内容关联

实际读取旧业务报告末尾清单，逐文件 CRLF→LF 归一 SHA-256，再按路径排序聚合：33/33 一致。

```text
BUSINESS_FILES 33 AGGREGATE 9c7f2ddeb4f3a8df9fbda78caab8893f5355bea1896c63d29a61f2171d8c00d9
```

旧业务报告 PASS/PASS 可关联本 candidate 的相同 33 文件，不能扩展批准发布代码。业务视觉沿用旧报告实际页面对比证据，本轮未重新浏览；正式生产视觉仍待部署。旧后端基线 9 failures 等限制继续保留，不声称全项目全绿。

## 独立验证原始输出

`python -m unittest discover -s scripts/release -p 'test_studio_batch*.py'`：

```text
......................................
----------------------------------------------------------------------
Ran 38 tests in 1.967s

OK
```

全部本轮 Python 执行无写 pyc 的 compile：

```text
SYNTAX_OK 15 MAX_LINES 225
```

未重复主 Agent 其他 36 项 helper 回归声明；未执行正式包全链构建、生产安装测试、备份、部署、实际回滚或正式视觉。旧 HEAD 构建不等于 0.2.64 正式包构建成功。

## 快照与阶段

两次 review-status 的 currentId 均为本报告 candidateId，approved=false。报告期间主 Agent 收到 R4 后告知将修复代码；本报告全部证据/行号只针对上述旧 candidate，不覆盖后续修改。本报告仅写 Markdown。Stage 1 有 HIGH，按 skill 不执行 Stage 2 质量/安全/视觉审查；修复后必须新 candidate 从 Stage 1 复审，不能登记本快照 PASS。
