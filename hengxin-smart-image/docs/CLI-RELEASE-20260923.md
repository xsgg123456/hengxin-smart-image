# CLI 优化生产发布 · 2026-09-23

## 授权与范围

用户明确要求打包最新代码部署生产，再提交Git。本次发布专用原生Codex Worker所用七份Python文件：execution下codex_runner、intervention、prompts、materials、workspace，以及worker/reconcile和modules/tasks/attempts。包含新首轮失败自动干预，保持已上线的主/详情图指令区分及单张修改。服务器与项目CLI均维持0.156.1。

前端和API没有本轮新实现，使用当前在线版本；不执行数据库迁移、不重试历史失败任务、不创建收费生图调用。

## 发布包

- 版本：`cli-20260923-auto-intervention`。
- 本地：`hengxin-smart-image/build/releases/cli-20260923-auto-intervention/cli-20260923-auto-intervention.tar.gz`（构建产物Git忽略）。
- 生产：`/opt/hengxin-smart-image/releases/cli-20260923-auto-intervention/release.tar.gz`。
- 包SHA256：`c77f405309cbcefdea73e9d8c2953275d7df6bd694ed11029636299d4871b93a`。
- 审批代码快照：`a4bbb23a84540702a09d190fab3bccc551928e9f88d3e9fc2a15b76d6f67e10c`，独立Stage1/2 PASS。

包只含七份已审源文件及manifest.json。逐文件记录新SHA256和预期生产旧SHA256，白名单检查、编译及敏感文件/开发者路径检查通过；没有.env、认证、会话、数据库或用户图片。生产codex_runner/reconcile/attempts的旧哈希与本地HEAD基线一致，另三份已上线文件与上次发布记录一致；intervention为新文件。

## 部署过程

1. 本地解包覆盖隔离验证目录，从实际发布产物执行专项回归。
2. 上传校验包SHA256，在服务器临时目录复制原app并覆盖包文件，独立进程导入与干预/提示词检查通过。
3. 备份旧文件到 `/var/backups/hengxin-cli-release-20260923T060822Z`（0700）；保留manifest中的新文件标记。
4. 暂停专用Worker消费，复核active/reserved/scheduled均0，数据库CLI running/collecting/cancelling/uncertain轮次数0。
5. 停止 `hengxin-vps-codex-worker.service`，逐文件原子替换并编译；导入实际安装模块检查后启动服务。任一步失败恢复全部原文件，新引入intervention文件按清单移除，再启动旧Worker。

## 验收结果

- 发布前完整后端回归：895 passed、166条件跳过、15项既有warning。
- 从解包产物执行8份相关测试：117 passed、2项既有warning，13.84s。命令：`python -m pytest tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py tests/test_task_prompt.py tests/test_single_revision_prompt.py tests/test_single_revision_materials.py tests/test_codex_runner.py tests/test_revision_execution.py tests/test_execution_reconcile.py -q`。
- 服务器包临时环境与已安装实际模块的独立进程检查均PASS：四Skill首轮差异、四Skill统一单张指令、干预门禁、会话不一致拒绝、累计用量。
- 七个实际文件与包内SHA256全部一致。
- Worker新PID876456，systemd active，新鲜数据库心跳ready，CLI/isolation/authenticationConfigured均true，capacity/concurrency仍5；celery队列恢复。
- `/usr/local/bin/codex`及`/home/codex/.local/bin/codex`均返回codex-cli 0.156.1。
- API容器running/healthy，API图片Worker及两类outbox容器仍running。
- 本次没有付费图片生成，因此不把部署检查说成真实图片质量或成功率验收。

## 回退

先暂停消费并确认无活动及待核实CLI轮次，再停止专用Worker。按备份manifest恢复有旧哈希的六个文件，删除本轮新增intervention.py及对应pyc；编译恢复文件并启动Worker，检查最新ready心跳和队列。原CLI二进制、认证、Skill正文、业务图片和数据库均未更改。
