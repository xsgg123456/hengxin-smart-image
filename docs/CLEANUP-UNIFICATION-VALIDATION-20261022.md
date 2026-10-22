# 自动清理统一修复 · 本地验收记录

用户边界：完成修复、测试和独立审查后停止；不暂存、不提交、不推送、不打包发布、不部署，不操作线上失败记录。本轮没有数据库迁移、依赖升级或前端界面调整。此前换图记录筛选实现保持原样。

## 根因与改动

已通过线上只读复核和隔离 Linux 红测试确认：正常执行器会生成四类 `arg0` 工具符号链接，旧自动清理拒绝所有链接，导致历史清理反复 retry；显式删除另有安全逻辑，两个入口发生分叉。

现在两个入口转发至 `backend/app/execution/cleanup_paths.py`，采用同一套目录描述符、祖先和目标身份复核、不跟随链接、逐层挂载身份和删除后残留检查。Linux 的预检与实际 dir_fd unlink/rmdir 删除共用安全 walker，防止预检后嵌套挂载绕过；Windows 保守预检后使用 rmtree。仅精确路径、已知四个名称、目标 `/opt/codex` 同时匹配才放行链接本身。缓存只清 cache/plugins，整段历史才清 UUID 会话目录。数据库历史清理、对象引用保护和显式删除任务的业务范围保持独立。

补充 `cleanup_diagnostics.py`，让清理阶段、安全拒绝、权限、IO、数据库、缩略图占用、对象存储等失败有稳定错误码；日志不包含原始异常消息、SQL参数、凭据、文件内容或绝对私有路径。原页面和 API 安全文案保持。

## 验证证据

证据目录：`output/cleanup-unification-20261022/`（Git 忽略，保留供本地复核）。

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| 旧实现复现 | 合法工具链接用例失败，`Linked cleanup material`；修复后同一用例通过 | linux-red.log/.xml；linux-target.log/.xml |
| Linux 清理/删除完整专项 | 171 passed，3 skipped；跳过为 Windows junction 专用，已在 Windows 实跑 | linux-target.log/.xml |
| 最终 Linux 后端全量 | 2456 passed，27 skipped，0 failed，377.76s；以下说明跳过范围 | linux-full.log/.xml |
| Windows 针对性 | 63 passed，40 skipped；40项是 Linux 挂载/链接/FD/UID专项，已在 Linux 实跑 | windows-target.log/.xml |
| 真实工具链接目标保护 | 两入口清理前后 `/opt/codex/sentinel` SHA256 相同，缓存后再清历史同样保全 | linux-mount-proof.log |
| 真实跨设备挂载保护 | UUID目录、cache、嵌套目录三处 tmpfs 均拒绝 CROSS_DEVICE，目标内容保留 | linux-mount-final.log |
| 同设备绑定挂载 | 首轮三处实际越界删除测试文件，修复后全部拒绝且外部测试文件完好；正式 pytest 另覆盖8种目录/文件挂载 | linux-bind-red.log、linux-bind-green.log、linux-target.xml |
| 挂载证据及替换保护 | 无法读取/解析 mnt_id 即拒绝；预检后同 inode 自绑定替换，删除前身份复核拒绝 | test_cleanup_mounts.py；linux-target.xml |
| 预检后嵌套挂载竞态 | 缓存/历史两种旧实现实际越界删除测试文件；安全 walker 修复后全部 CROSS_DEVICE，外部测试文件完整 | linux-nested-race-red.log、linux-nested-race-green.log |
| 一次性命令脱敏 | 自动清理和显式删除的 --once 子进程均 exit 1；日志有稳定错误码，无合成 SQL/token/DSN或原始 Traceback | test_cleanup_diagnostics.py；windows-target.xml、linux-target.xml |
| 完整启动生命周期脱敏 | 真实 main 子进程：设置读取、工厂建立、首次心跳、关闭上下文四种异常均安全非零退出 | test_cleanup_diagnostics.py；linux-target.xml |
| 前端单元测试 | 355 passed，0 failed，0 skipped | frontend-tests.log |
| 前端类型检查 | pnpm typecheck / vue-tsc --noEmit，exit 0 | frontend-typecheck.log |
| 前端生产构建 | pnpm build，exit 0；Vite built in 40.60s | frontend-build.log |
| 后端语法编译 | `.venv/Scripts/python.exe -m compileall -q app`，exit 0 | 本轮执行输出 |
| Git 空白检查 | git diff --check，exit 0 | 本轮执行输出 |

Linux 环境为隔离 WSL Ubuntu、Python 3.12.13 锁定依赖和 PostgreSQL 18.6 UTC、独立网络命名空间、临时 Unix socket，无 TCP。不是生产 PG16.15 镜像，不宣称生产安装包验收。真实挂载证明另开 mount namespace 并在临时 tmpfs 内构造目标，退出后宿主 `/opt/codex` 仍不存在；未修改宿主程序目录。

最终全量27项跳过：22项需要显式可销毁的身份 Redis（本次未启用）；1项需要指定既有 non-root WSL 运行时；3项为本次新增 Windows junction 检查（Windows专项已实测）；1项为既有 overseas Windows junction 检查（本轮未补跑）。不把跳过等同于通过。10条警告为既有 Starlette/httpx 弃用及隔离 root Celery 测试警告。

业务回归实际验证：含真实四类工具链接的缓存→历史链路，原图、素材、正式成品、所有采用版本的对象字节及元数据集合保持；会话删除且统计仅计一次。文件系统拒绝时历史/图片留存；目录已删除后数据库异常会回滚历史变更，重试缺失目录可恢复且不重复统计。真实 PG 定时扫描会按一小时 next_cleanup_at 恢复已持久化 expire_pending，不修改 last_activity_at；59分钟不提前重试，下轮仅回收无引用候选一次。既有并发、活动/不确定状态、采用竞争、共享对象及故障补偿测试一并通过专项。

## 收尾状态

首轮候选 `4cb36e07` 虽通过2436项全量测试，独立审查仍找到同设备bind mount与一次性命令原始异常泄漏两项HIGH，因此未获批准；该次结果保留为 linux-full-pre-bind-fix.log/.xml。已补齐修复及真实回归，重新从 Stage 1 审查，见 [首轮阻塞报告](CLEANUP-UNIFICATION-REVIEW-20261022.md)。

第二轮候选 `a85a4734` 仍被发现预检后嵌套挂载竞态、main 心跳启动异常泄漏，亦未获批准，报告见 [第二轮阻塞报告](CLEANUP-UNIFICATION-FINAL-REVIEW-20261022.md)。该候选全量验证被主动中断，日志 linux-full-pre-walker-interrupted.log/.xml 仅记录中断，不计通过；pytest teardown 的 KeyError 是 SIGINT 中断副作用，不当产品回归结论。最终以安全 walker 和 main 生命周期边界修复，再由新的独立 reviewer 从 Stage 1 审查。

最终完整后端回归与独立两阶段审查均通过，报告为 [最终审查](CLEANUP-UNIFICATION-APPROVAL-20261022.md)。第三候选快照：`e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced`，已通过 harness review-approve 登记两阶段 PASS。564个后端源码/测试/迁移/配置文件全量测试前后与 reviewer 读取结果一致，changed=[]。Git HEAD仍为11069a3aa01eb6cf50b36dc65438e4a38073d2f6，暂存区为空，没有提交、推送或部署。

Linux 临时PostgreSQL、venv和测试目录已停止并删除；原有9个宿主PG进程PID及5432 socket保持，宿主没有遗留任务挂载且 `/opt/codex` 仍不存在。证据为 linux-cleanup.log、linux-host-after-cleanup.json、linux-summary.txt。测试结束后的临时schema/额外数据库查询为空。

Windows 测试临时目录收尾存在工具限制：对本轮 pytest-2377/2378/2379 的安全删除操作被自动审批拒绝，原因仅“Rejected: blocked by policy”。命令未执行，也未改用其他手段绕过；目录保留，不影响产品功能与测试结果，不能宣称所有临时目录已清理。见 windows-temp-cleanup.log。

已知范围外问题继承 [上一轮验证记录](RECORDS-SCOPE-VALIDATION-20261022.md)：极端 Retry-After 在 PostgreSQL Asia/Shanghai 时区可能造成 year 10000 溢出，HEAD 与改动版本均可复现，UTC 两者均通过。本次不修改 limiter 或重试调度；生产数据库只读核验为 UTC，隔离回归使用同一时区，不将其宣称为本次已修。

后续若恢复发布，必须更新实际运行的原生 retention / deletion 执行器并交付新的共享模块；旧 records 仅 API/前端发布入口不足以部署此修复。当前仅本地改动，线上两条失败记录未被本轮重试或改写。
