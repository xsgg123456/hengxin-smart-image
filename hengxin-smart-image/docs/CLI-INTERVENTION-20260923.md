# CLI 首轮换套图自动干预 · 2026-09-23

## 交付范围

最初仅授权本机实现和验证；用户随后明确授权打包部署并提交Git。现已部署生产，发布包、健康检查和回退信息见 [发布记录](CLI-RELEASE-20260923.md)。未重试生产历史任务、未创建收费模型调用。

首次CLI壁纸/商品模板整套任务失败且进程已停止后，自动在同session/home/work发送 `app/execution/intervention.py` 的通用干预提示词，最多1次。先重新核实是否过度否决，再修复明确缺陷，保留已合格结果，最终交齐本批。不会放宽文件安全/图片解码/完整数量校验。

## 执行边界

- 同一业务轮次和认领令牌；队列重复投递不再创建调用。后续单张、整套返工及人工重试不自动干预。
- 明确返回退出回执才可干预；未知/取消/删除/失效租约/缺少原会话不续跑，认证、额度、限流错误不续跑。材料准备、保存图片或发布失败不重生成。
- 首轮与干预共用冻结总超时，第二次只获得剩余秒数。没有剩余预算则结束。
- home/work与初始baseline不变，允许复核并交付首调用中生成的候选。输入、Skill与当前基础图等保护目录仍不能作为成品直接收取。
- 原控制目录完整保留，干预使用同级 `<roundId>-intervention-1`，各有prompt/events/exit。锁内先持久化次数和新目录，清除旧PID，再启动新CLI。不能用第一次退出证据替第二次判定已停止。
- 一个ExecutionAttempt代表该逻辑轮次，始终指向当前调用。首调用量保留在干预标记中，普通结束及异常恢复同样汇总；Worker中断后仅核实并收图，不补发干预。
- 现有执行时间线显示“首次换套图未完成，自动继续处理（1/1）”，无需新增前端页面或数据库迁移。

## 验证证据

最终候选在后端目录执行 `python -m pytest -q`：895 passed、166 skipped、15项既有warning，56.74s。条件跳过项不计通过。

关联回归 `pytest tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py tests/test_execution_reconcile.py tests/test_codex_runner.py tests/test_revision_execution.py tests/test_observed_runner.py tests/test_execution_process.py tests/test_single_revision_prompt.py tests/test_single_revision_materials.py -q`：89 passed、3 skipped、2项既有warning。

`python -m compileall -q app/execution app/worker/reconcile.py app/modules/tasks/attempts.py` 与 `git diff --check` 通过（Git提示既有CRLF归一化）。

新增30项回归使用隔离SQLite/临时文件和真实应用入口/材料/收图/发布逻辑，仅模拟外部CLI：涵盖无交付、缺图、坏路径、断线、非零退出后续接成功；已有候选复用；两次日志/累计用量；连续失败仅2次调用；认证额度、取消、租约和超时；单张/人工轮次排除；第二进程存活、退出后恢复、注册前中断不误用旧PID；恢复无CLI重放；会话不一致拒绝发布。

审查发现原事件汇总可能用后续turn.failed覆盖先前session_mismatch。已在干预门禁逐条检查thread.started必须匹配原session，并加A→B→turn.failed的真实runner回归：不会发起干预。修后两份专项测试30 passed、2项既有warning，编译通过，再跑上述最终全后端回归。

本轮未调用真实模型生成图片，因此不将上述测试视为图像视觉质量或成功率提升的实测结论。
