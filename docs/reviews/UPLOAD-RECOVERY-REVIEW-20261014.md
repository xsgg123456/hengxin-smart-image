# 上传发布恢复独立审查（2026-10-14）

- candidateId：`f311a42df3471d3a88a8f4ff8f500c039b4de625249ab44255b9f3cef6e4b2c0`
- 范围：新增 `scripts/release/overseas-upload-recover.py`、`scripts/release/test_overseas_upload_recovery.py`，以及 `docs/UPLOAD-RELEASE-20261014.md` 的失败记录和恢复规划。原发布包及产品 UI 不重新审查。
- 依据：发布记录第 5、27–29 行的恢复约束；Product-Spec.md 第 6–11 行的成功记账、恢复互斥及禁止数据库自动恢复要求。
- 结论：Stage 1 PASS；Stage 2 PASS。无 HIGH/MEDIUM 阻断。代码审查通过不等于生产恢复已完成，须运行脚本并取得 installed、公开入口及资源验收证据。

## Stage 1：Spec Compliance — PASS

| 范围内要求 | 结论与证据 |
| --- | --- |
| 限定失败现场、禁止重放 | 完整。recover.py:43–55 检查 RECOVERY_STARTED、失败阶段、异常类型、未完成验收、完整备份与相同已测试镜像；recover.py:133–138 固定发布编号并重新验证原包哈希。 |
| 配置、国内服务和资源漂移检查 | 完整。recover.py:59–77 校验 Compose、国内原生 PID/cwd、API 镜像/内存/挂载、其他容器 ID/运行状态/挂载、配置哈希、源码和入口关闭状态。最终 recover.py:104 复验完整资源集合。 |
| 恢复 90、保留 95、增加优先 99 | 完整。recover.py:20–38 校验备份 90 对应基线哈希、当前 90 为本次精确生成文本、其他既有 nativeFiles 哈希一致，99 未占用且高于本目录现有配置；recover.py:80–86 排空后再次核验，再恢复 90 并切换 99。overseas-update-runtime.py:117–121 的备份目录和 :149–157 的写入/daemon-reload 与恢复代码一致。 |
| 排空、启动已测试候选、完整验收 | 完整。recover.py:80 复用双轮排空；overseas-upload-deploy.py:69–76 先确认空闲、停 outbox、再次确认空闲、停 worker。recover.py:87–104 复用 API 健康启动、原生启动、installed、代理安装/检查/reload、前端、公开入口、上传边界及资源验收。 |
| 配置指针与验收兼容 | 完整。recover.py:85 临时设 u.DROP 为 99；overseas-upload-deploy.py:147–149 仅排除本次 99，对恢复后的 90、保留的 95 继续按原基线检查。installed 同时检查 systemd WorkingDirectory 和实际进程 cwd（原 deploy.py:165–175）。 |
| 失败关闭、不恢复数据库、不盲停执行器 | 完整。recover.py:113–122 关闭入口、复核 503、恢复内层代理并停止 API；无失败路径 worker/outbox stop，无数据库恢复。入口开放后的失败不强停可能接收工作的执行器。 |
| 成功台账与清理 | 完整。recover.py:107–112 仅在全部验收后记完成；:141–145 经原包 release-retention.managed 执行 recover。release-retention.py:75–77 要求失败部署快照，:96–99 失败只记失败，:107–114 成功后独立记账与清理。 |
| 文档与范围漂移 | 完整。发布文档 :25–29 区分失败事实与后续恢复规划，未声称已恢复；没有新 API、页面、表或业务功能。UI/设计稿比对不适用，此次没有 UI 改动。 |

## Stage 2：Code Quality — PASS

- 结构和安全：恢复脚本 145 行、测试 99 行，各自单一职责；固定目标发布及 root 检查，拒绝 Python 优化模式；命令复用参数数组，无新增 shell 拼接、eval、SQL 拼接或硬编码密钥。证据：recover.py:125–145、:87–94；依赖命令执行见 member-release-runtime.py:44–51。
- 测试真实性：test_overseas_upload_recovery.py:51–60 验证恢复顺序与没有迁移调用，:63–75 覆盖 installed/public/boundary 三类失败关闭，:78–85 覆盖重放/容量/内存前置拒绝，:88–99 真实临时文件覆盖 90 还原来源和 95 漂移拒绝。独立复跑共 8 个测试通过。
- 测试边界：上述为本地编排与文件测试，Docker/systemd/公网调用采用 mock；未在本审查中执行生产恢复，不能据此声称生产已健康。真实环境验收由 recover.py:90–104 执行并记录。
- LOW 非阻断：recover.py:113 的异常路径没有更新恢复专用失败阶段，原 FAILURE.json 将仍显示首次 verify-installed 失败；RECOVERY_STARTED 可防止重放，但后续排障需结合运行日志。建议保存本次完整执行日志，不依赖旧 FAILURE.json 判断恢复失败位置。
- 视觉对比：不适用；送审范围无页面及样式变化。

## 独立验证原始输出

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_upload_recovery.py -q`

```text
........                                                                 [100%]
8 passed in 0.29s
```

编译命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m py_compile scripts/release/overseas-upload-recover.py scripts/release/test_overseas_upload_recovery.py`

```text
[stdout/stderr 均为空；exit_code=0]
```

审查结束前 `harness.py review-status` 原始输出：

```json
{"currentId": "f311a42df3471d3a88a8f4ff8f500c039b4de625249ab44255b9f3cef6e4b2c0", "reviewedId": "013f660dda8355774d169bd7e625309130ba26acc2606cac1a3bf144d79602d0", "changedFiles": ["scripts/release/overseas-upload-recover.py", "scripts/release/test_overseas_upload_recovery.py"], "approved": false}
```

代码快照与派发一致，未发现审查期间代码变化。本报告不登记批准，不写 clean；主 Agent 可为上述同一 candidateId 登记两阶段 PASS。
