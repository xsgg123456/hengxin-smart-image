# 部署回收遗漏修复独立审查（2026-10-20）

- candidateId：`63f77b7535460a50253801eb53fb3c854b7d2363f670904817aa57c8a378d1d3`
- 审查范围：本候选相对 HEAD 的发布回收代码、测试和源文档差异；新增 `release-retention-failures.py`、`test_release_retention_failures.py`、`test_release_retention_dangling.py`。阅读 Product-Spec.md 顶部 2026-10-20 条目、DEV-PLAN.md 对应计划、docs/RELEASE-RETENTION.md 和 docs/RELEASE-RETENTION-FIX-20261020.md。
- Stage 1：**FAIL**（1 项 MEDIUM）。Stage 2：**未执行**，Stage 1 尚未通过。
- 本报告仅审查本地候选，不替代服务器工具安装后的哈希、preview 和服务/会话保护验收。未运行生产清理、发布或服务变更。

## Stage 1 发现

### M1：没有连字符的裸业务名称被错误纳入自动退休范围

**位置：** `scripts/release/release-retention-failures.py:8`、`:9`。

**要求：** Product-Spec.md:4 规定“无法确定业务……的记录继续保护”；docs/RELEASE-RETENTION.md:58 及本次交接明确以 `domestic-`、`overseas-`、`identity-` 前缀识别范围。

**实际：** `release.partition('-')[0]` 在没有连字符时返回完整名称，因而 `overseas`、`domestic`、`identity` 也会通过 `group in GROUPS`。这些名称是台账和 managed 接口接受的合法名称（`release-retention-state.py:11`、`release-retention.py:59`），不是由格式校验排除的不可达输入。可先登记失败基线，随后解除候选保护并自动退休，超出声明的前缀白名单。

**独立复现：** 临时真实 Store，使用现有 Docker 命令夹具；建立 `pending['overseas'] = {'phase': 'failed', 'image': image(3)}`，调用 `record`，再令 `successCounters['overseas'] = 1`，调用 `preview` 和 `retire`。原始输出：

```text
scope= overseas
preview= ['overseas']
pending= []
retired= ['overseas']
```

**修复标准：** 范围识别显式要求完整连字符前缀；补裸业务名称、其它未知名称不能登记自动退休基线/不能退休的回归。已知三个前缀的正常生命周期仍需通过。此问题尚未证明影响现有生产记录，因此定为 MEDIUM，不夸大为已发生的生产误删。

## Stage 1 逐项对照

| Spec 条目 | 结论及证据 |
| --- | --- |
| 无标签镜像发现、项目归属和别名 | 完整实现。`release-retention-docker.py:55` 合并仓库过滤和项目 label/dangling 查询，`:94` 再核实 RepoTags、RepoDigests 与 label；`test_release_retention_dangling.py:18` 及 `:72` 覆盖其它项目和 inspect 元数据变化。 |
| 三业务 current/previous、全部容器、候选及恢复引用 | 完整实现。`release-retention-docker.py:33` 使用 `docker ps -aq`；`:72` 核对健康、历史完整性、实际镜像存在及 pending/before。`test_release_retention_dangling.py:35`、`:49` 覆盖停止容器和各业务不同版本。 |
| 删除前重查、非强制删除 | 完整实现。`release-retention-docker.py:111` 重算，`:114` 按现有标签或无标签完整 ID 删除，不含 force。`test_release_retention_dangling.py:98` 覆盖新容器/标签/摘要/pending 竞态；`:128` 覆盖删除拒绝后停止缓存回收。 |
| 同业务后续真实成功才退休、未知业务保留 | **部分实现，M1。** 成功计数仅在实际切换时递增（`release-retention-state.py:67`）；`release-retention-failures.py:47` 校验基线、回执、引用和健康；但裸名称超出前缀范围。`test_release_retention_failures.py:41`、`:61`、`:71` 验证正常/其它业务/旧成功。 |
| 部署/恢复现场及成功回执继续保护，审计原子保存 | 完整实现。`release-retention-failures.py:9` 拒绝 before，`:57` 拒绝回执，`:76` 在副本中同时写审计和移除 pending；`release-retention-state.py:119` 临时文件、fsync、replace。故障及引用测试见 `test_release_retention_failures.py:98`、`:136`。 |
| 旧台账种基线、不能倒用旧成功；人工 abandon 与恢复可用 | 完整实现（范围识别受 M1 影响）。`release-retention.py:64` 在锁内先种基线，`release-retention-failures.py:23`、`:68` 兼容缺失字段；恢复和 abandon 保持 `release-retention.py:79`、`:147` 的显式校验。旧台账测试 `test_release_retention_failures.py:82`，既有恢复测试 `test_release_retention.py:95`、`:190`。 |
| 同名构建候选保护、完成发布禁止再构建 | 完整实现。`release-retention.py:70` 阻止已完成 release 的 build/prepare；`:92` 记录构建前候选，plan 同时保护当前同名标签。`test_release_retention_failures.py:178`、`:193` 覆盖失败重建和完成后拒绝重建。 |
| 在途保缓存、无在途时约 2 GB 专属 builder | 完整实现。`release-retention-docker.py:118` 仅 pending 为空才 prune，`:123` 限定 builder 和 2gb；`release-build.py:7`、`:19` 固定名称及 driver。正常退休测试与 `test_release_retention_docker.py:128` 验证命令边界。 |
| 清理失败不改变成功结果/不停止业务 | 完整实现。`release-retention.py:21` 捕获清理异常，调用位于验证成功记账之后（`:114`）；`test_release_retention.py:128` 以及失败退休落盘测试验证返回成功与保护保留。 |
| 数据、图片、卷、会话、认证、CLI 环境、配置链禁止删除 | 本地实现符合。新生产调用范围为 Docker 只读发现、image rm、专用 builder prune 和台账写入（`release-retention-docker.py:18`、`:105`，`release-retention-failures.py:68`）；CLI 集成测试 `test_release_retention_cli.py:67` 断言无 systemctl/rm/docker stop/volume/system 操作。服务器实际前后保护检查尚待主 Agent 安装时执行。 |
| 打包接线与回归 | 完整实现。`test_release_wiring.py:10` 将新 helper 纳入所有 packager 的 allowlist/glob 校验；`:40` 验证 Docker 发布入口的 managed 包装；本次全量发布测试通过。 |
| Git 提交及服务器工具更新 | 当前是审查前置，尚未完成；DEV-PLAN.md:9、:10 要求两阶段 PASS 后执行。本报告不能登记为交付完成。 |

无 UI、页面、引导文案或设计稿变更，UI 一致性不适用。范围内未发现新增业务 API、数据库表或页面等 Spec 漂移；M1 属于明确行为边界不匹配。

### 对 wiring 排除的判断

`test_release_wiring.py:35` 排除 `codex-auth-deploy.py` 有依据：该入口 `prepare` 复制原生源码与服务配置（`codex-auth-deploy.py:12`），`switch` 排空并切换选定原生 worker（`:102`），没有 Docker 镜像构建或发布；main 使用专属 flock（`:178`）。现有 `test_codex_auth_deploy.py:105`、`:120`、`:133`、`:220` 对未证明排空、选定服务停止、失败不盲目回滚及排空失败禁止覆盖作测试，且包含在此次 856 项中。排除的确收敛了 Docker managed 接线检查范围，没有通过排除隐藏本次镜像清理缺陷。

## 独立验证原始结果

命令：`.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest scripts/release -q`

```text
856 passed, 1 skipped, 309 subtests passed in 24.96s
```

退出码 0。实际主目录下解释器位于嵌套的 `hengxin-smart-image/backend`；首次使用交接中的简写 `backend/.venv/...` 不存在，修正路径后执行上述完整测试。没有将失败的启动尝试记为通过。

命令：`.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m compileall scripts/release`

```text
Listing 'scripts/release'...
```

退出码 0。

命令：`git diff --check`

```text
warning: in the working copy of 'DEV-PLAN.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'scripts/release/test_release_wiring.py', CRLF will be replaced by LF the next time Git touches it
```

退出码 0。主 Agent 提供的真实 Docker smoke 和历史 `*-tests.py` 结果属于交接证据，本 reviewer 未重新操作 Docker daemon 或独立补跑历史命名测试，不混算为本次独立执行结果。

## 快照与后续

审查开始和报告完成前 `review-status.currentId` 均等于本报告 candidateId，未发现候选代码变化。审查者仅创建本 Markdown 报告，未修改业务代码、未提交、未写 clean 或登记批准。修复 M1 后必须重新固定 candidateId 并从 Stage 1 复核，再执行 Stage 2；本报告不得用于批准修改后的快照。
