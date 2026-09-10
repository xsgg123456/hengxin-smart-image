# Phase 9 验证记录

日期：2026-09-10。真实链路、隔离、真实故障恢复与回归通过；独立审查结果见 PHASE9-FINAL-REVIEW.md，用户验收后进入 Phase10。

## 真实服务器链路

Ubuntu 24.04、codex-cli 0.153.4、专用 codex 用户；Bubblewrap 0.9.0，精确路径 /opt/hengxin-runtime/bwrap 的 AppArmor userns 许可经用户批准，系统全局限制仍为1。CLI与同版本 codex-code-mode-host 只读挂载。

执行 `infra/verify_phase9_live.py --output-dir <独立结果目录> --codex-binary <固定CLI> --auth-file <认证路径>`：报告 `output/phase9-live/report.json` 为 passed，cleanupErrors=[]。

- HTTP 上传两张既有测试图片，安装冻结 Skill 包，创建模板及异步任务。
- task：9fb942d0-22b9-42ca-9029-0cddb5a1cdb0；round：d89ebe2a-6b95-4ec3-ae1c-e7305590a0bc。
- session：01a088f6-1ed2-75e2-85a8-5dd215bd6e43；原生图像调用 exec-5a35917a-ee58-4b11-9bfd-f8bf9382e47e。
- 约104秒后 API 状态为待查看，真实 PNG 910×1728，通过会话/本轮生成事件/文件哈希校验，MinIO 下载完成。本地图片 `output/phase9-live/result.png`。
- task/request/round/attempt/session/image_versions/execution_count 均为1；完成前后重复同键请求不增加执行。
- 数据库冻结并发1、timeoutSeconds=3600、automaticRetries=0。
- 测试服务和临时卷清理完成；生产业务未部署。

## Linux 隔离与会话

运行 `infra/verify_phase9_sandbox.py <CLI> <认证路径>`，原始工具输出转录 `output/phase9-sandbox.log`：

- A 任务不能读取或修改 B 任务文件，本轮 work 可写，control 与 Docker socket 不可见。
- kill 隔离监督进程后，setsid 后台子进程停止写入，证明独立 PID 命名空间收敛整个树。
- 两任务真实 session 分别为 01a088fa-9591-7750-a7c6-7a31fe26d8c4 与 01a088fa-c086-70e0-ab9a-a66607d940d4。
- 首任务进程退出后，使用新 round 目录与持久 home 按精确 ID 续接，成功返回原记忆；测试 home 清理完成。

## 自动测试与浏览器

- `python infra/verify_phase8.py --build --browser`：Linux 后端 245 passed、0 skipped、2项依赖弃用提示。真实 PG/Redis/MinIO/Celery 回归、重复投递、并发屏障、取消、删除、Worker SIGKILL 不盲重跑均通过。
- 同一脚本浏览器：三入口实际提交、幂等头、离页执行、下载/ZIP字节、401重连恢复、删除通过，pageerrors=0；最终 PHASE8 INTEGRATION PASS，独立Compose卷已清理。日志 `output/phase9-final-regression.log`，截图 `output/playwright/phase8-*.png`。
- Windows 后端 229 passed、16项POSIX测试跳过；Linux上述245项无跳过，Windows不能替代Linux验收。
- 前端 `vue-tsc --noEmit`：退出0；`tsx --test tests/*.test.ts`：51 passed、0 failed；`vite build`：退出0，41.68秒。构建日志 `output/phase9-frontend-build.log`。

## 真实 Worker 硬退出恢复

`infra/verify_phase9_live.py ... --crash-before-publish` 第二轮 passed。第一次测试因脚本将待核实公开状态误判为终态失败而提前退出；修正等待逻辑后补跑通过，未修改业务恢复代码。

- 在真实 CLI 生成、来源校验和 MinIO 上传完成后，测试 Worker 子进程 `os._exit(71)`，故障标记在服务器日志中确认存在。
- 观察到待核实门禁，随后由真实 reconcile 检查旧进程身份、真实原生生成日志及图片哈希，轮换凭证并恢复发布。未mock provenance或恢复服务。
- task 26c97577-8d9a-4cc5-8690-d9cc0b9241ac；round b70e089e-2357-4a90-a8e4-2e0dbb0fec91；session 01a08901-f78c-7502-a595-78d5e600d258。
- 910×1728 PNG成功回传，task/request/round/attempt/session/image_versions/execution_count 均为1；recoveredAfterWorkerExit=true、observedUncertain=true、cleanupErrors=[]。
- 原报告位于服务器专用测试结果目录 phase9-live-recovery-02；本地最小字段记录 `output/phase9-live-recovery-summary.json`。自动审批拒绝原始Worker日志跨环境下载，改为在服务器只读提取布尔故障标记及无凭据计数，日志未导出。

## 边界

以上证明平台传输、隔离和状态行为，不等于三个真实业务 Skill 的效果验收或容量压测。Phase10返工UI、Phase11归档、Phase13统计页面和Phase14生产发布尚未完成。

本机两个子代理测试临时目录因隔离身份ACL差异，主Agent不能移动；独立reviewer已将其移至output/phase9-reviewer-test-cleanup，代码目录已清理，双方快照一致。服务器各次独立测试服务与临时卷清理完成，先前脚本遗漏的专用临时目录亦已定向清理。
