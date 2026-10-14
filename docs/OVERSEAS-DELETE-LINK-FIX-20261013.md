# 海外任务删除：临时工具链接修复与简化确认

## 事实与范围

用户反馈任务“测试”（190ad7e8-a09e-4283-b7f6-e9b5762c8bba）删除失败。2026-10-13 以线上维护服务相同 uid 999、代码目录及环境执行只读数据库事务和对象清单检查：任务为 legacy，唯一 analysis Job 已 cancelled、process_exited=true，进程退出核验通过；归档数为 0；删除回执 delete_failed、manifest={}。

实际异常来自 cleanup_files.validate_directories：`Linked workspace cannot be erased`。该 Job 私有目录的 `home/.codex/tmp/arg0/codex-arg0s37Lkj/` 下有四个 CLI 工具符号链接（apply_patch、applypatch、codex-execve-wrapper、codex-linux-sandbox），均指向沙箱内 `/opt/codex`。现有检查拒绝所有链接，误拦截正常 CLI 遗留文件。尚未进入 erasing 阶段。生产无写入、重试或删除操作。

## 有序步骤及验收

1. 固定真实目录布局的回归用例，证明旧校验拒绝正常工具链接。覆盖 legacy Job 与 studio 会话两种目录。
2. 仅允许上述固定深度、固定文件名、`codex-arg0` 临时目录、精确 `/opt/codex` 目标的叶子符号链接；只在支持抗符号链接攻击的 rmtree 环境放行。仍拒绝其他符号链接、目录链接、硬链接、根/父目录链接、错误工具目标和越界路径。只清理任务内链接本身，不能跟随链接删除共享目标。
3. 在隔离 Linux 文件系统及现有 HTTP/SQL 测试夹具验证真实目录删除、归档字节保留、未知链接拦截、失败重试；Python 编译检查和前端类型检查通过。再在线上相同身份只读运行新校验，不触发实际删除。
4. 固定快照，交独立 code-reviewer 两阶段审查。修复完成状态与上线状态分别记录；本轮不自动提交、部署或重试删除生产任务。

链接修复落实 Product-Spec 已确认的“专属目录实际清理、共享资源保留”要求，不改变数据模型、依赖及部署拓扑。

## 用户追加：普通二次确认

用户明确要求移除任务名称输入步骤。先更新 Product-Spec 与 Design-Brief，再按 dev-builder 修改现有 ElDialog 和删除请求：显示目标名称与删除范围，取消零写入，点击“确认删除”发送当前版本；后端不再要求名称，兼容旧客户端仍携带的可选名称字段。保留角色、CSRF、版本并发、进行中禁止重复请求、失败重试和未知网络结果只读核实。

验收：首次删除/取消/重试无输入框；请求只包含 version；无权限、版本冲突、双击和网络失败仍正确；更新关联单测与真实隔离浏览器流程，桌面/390px截图验证，正式前端构建与最终完整快照独立审查。此变更不改变 DEV-PLAN 阶段结构，仅替代旧计划和历史验收中的“名称输入确认”；历史发布/审查记录保持原事实。

## 验证记录

- 新回归用例先在未修改代码上运行：3 failed、6 passed。失败分别为 legacy、studio 正常工具链接删除，以及错误目标纠正后的重试，复现真实缺陷。
- 修复后一次性 Linux 容器（network none、源码只读挂载、既有依赖镜像）运行新用例及现有删除/故障/旧工作流/真实进程组/归档改派集合：38 passed，19.13 秒；2 条既有 Starlette 弃用警告。
- 新增用例涵盖 4 个 CLI 工具链接、legacy/studio 两种目录、studio 归档 ZIP 字节不变、错误目标/未知工具/目录名/位置/链接父目录/硬链接拒绝、错误目标恢复后的删除重试，以及非抗符号链接攻击环境拒绝。
- Python compileall、前端 pnpm typecheck、git diff --check 均退出 0；前端没有修改或重新打包。
- 将候选模块仅加载到独立诊断进程内存，不覆盖服务器源码，使用原维护服务 uid 999 和 `SET TRANSACTION READ ONLY`：inventory PASS，清单包含 1 个对象和 1 个 Job 专属目录。原任务、回执时间及 4 个链接保持不变。证据：`output/overseas-delete-candidate-readonly.json`。
- 第一轮仅 CLI 链接专项审查发现新增测试直接比较 ZIP 下载原始字节会受打包时间戳影响。已改为断言 HTTP 200 后比较解压成员名及原始字节，新 9 项回归再次通过；不改业务归档逻辑。
- 追加简化确认后，Linux 删除/归档/进程组相关集合 39 passed（18.70 秒）；真实独立 PostgreSQL 删除/归档改派竞争 5 passed（6.41 秒），均非生产数据。
- 前端全量 `pnpm test`：335 passed、0 skipped；`pnpm build`（含 typecheck）通过，39.50 秒。原始日志：`output/overseas-delete-confirm-frontend-tests.log`、`output/overseas-delete-confirm-frontend-build.log`。
- 一次性 PostgreSQL、双 MinIO、三 API 的真实 HTTP 删除/归档/技能流程全部通过；正式前端连接这些隔离 API 的浏览器 4 组通过，故障浏览器 2 组通过，均 0 pageerror / 0 模型调用。覆盖管理员普通二次确认、取消零写入、无名称输入、异步真实清理、归档原始字节、四种非管理员拒绝、断网不伪报成功、刷新与失败重试。HTTP 原始日志为 `output/overseas-delete-confirm-http.log`；其中旧打印 `stale/name checks` 仅为未同步的日志标签，执行前请求体和后端已改为 version-only，打印文本在本次运行后才修正；保留原始日志，不将标签当作名称校验证据。
- 实际查看桌面及 390px 长名称确认框截图，名称、范围、归档保留提示和按钮完整可见。截图及结果在 `output/playwright/delete-skills/`，其中 `delete-confirm-desktop.png` 为真实隔离流程、`delete-confirm-mobile.png` 为长名称故障场景。
- 最终独立 Stage 1 / Stage 2 PASS，候选 `db9678d135f34a887f940873784b81d1e0eff97d2cd45b2aeeb931cafb199647` 已登记批准，报告 `docs/reviews/OVERSEAS-DELETE-FINAL-20261013.md`。reviewer 独立 Linux 39 项、前端关键 7 项、最终类型与编译验证通过，并实际打开删除/归档邻居弹框对比。尚未提交、部署或操作生产删除重试。
- 本轮隔离服务已正常退出，5 个临时容器及对应网络由测试入口清理，3022 Vite 已停止。已有容器和生产服务未受影响。
