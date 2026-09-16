# Phase 11A 真实业务收尾验收

日期：2026-09-11。当前状态：真实验收、回归、清理及独立两阶段审查通过，待用户验收。最终审查见 [PHASE11A-CLOSEOUT-FINAL-REVIEW.md](PHASE11A-CLOSEOUT-FINAL-REVIEW.md)。

## 输入与隔离

- 使用实际 `ecommerce-wallpaper-swap` 1.0.1 包，SHA256 `0351184cb27e5ea1793b331911324f4f36b6e200c2683408676fb25afa3af440`。从用户原任务只读提取前两张模板图与同一替换素材，未修改已上传 Skill。
- 独立环境 `hx-p11a-e3d7cadd6e59bdf7`：随机私有端口、独立 PostgreSQL/Redis/MinIO、非 root WSL Worker、独立队列与执行目录。正常开发环境仍使用自己的数据库和默认并发 1。
- 使用既有 Linux Codex CLI 0.153.4，通过生产适配器和实际沙箱调用真实 imagegen。输出原生尺寸按用户已确认例外验收，不缩放伪造模板尺寸一致。

## 串行、版本与恢复

任务 `c003957f-f36e-4ef8-9b5e-20ac0f8f13cb`，三个轮次沿用同一 session `01a09042-04cb-7272-bb39-a0d6522855bb`。

| 轮次 | 实际 PID | 结果 |
| --- | --- | --- |
| 初始双图 | 12624 | 两张可解码原生图片，执行一次，exit 0 |
| 单张修改 | 14372 | 第一张新版本，第二张原版本不变，执行一次，exit 0 |
| 重启后整套修改 | 15834 | 两张新版本，同会话续接，执行一次，exit 0 |

- 同一幂等键重放返回原受理结果；另一竞争返工请求返回 409。
- 单张修改后归档 `8786bddd-5dee-4a01-ae15-a3d1eabd645a`，重启和整套修改后，其版本引用、下载字节 SHA256 与原归档一致；最初版本字节也仍一致。
- 整套修改在真实 CLI 完成、平台发布前注入 Worker 子进程退出。任务进入 uncertain，返工/重试门禁关闭，实际返工请求返回 409；重复投递原消息 3 次，仍只有一个 attempt、execution_count=1。
- 启动正常 Worker 后由现有核实流程恢复发布原产物，没有新增 CLI 调用；所有已采样执行进程结束。此故障是隔离 Worker 的定点注入，不是外部随机断电测试。

## 浏览器实测

隔离前端 3009 连接独立 API。任务详情显示替换素材缩略图，点击加载原图；真实 Codex 播报随生成更新；Worker 中断期间显示待核实并禁用返工，服务重启后点击“重试加载过程”恢复完成状态。结果显示第一张 v3、第二张 v2。

实际点击“下载整套”下载 `Phase11A-serial.zip`，ZIP CRC 通过，两张图片均可解码，逐张 SHA256 与接口当前版本完全一致。这是浏览器生成下载包的验证，独立于脚本另外生成的 ZIP 校验。

## 回归与证据

- WSL 完整后端 `python -m pytest -q -p no:cacheprovider`，通过 `phase11a_regressions.py` 在独立 `_test` 数据库执行：**637 passed，0 skipped，10 warnings，44.78 秒**。警告为既有依赖弃用及 SQLAlchemy 提示。
- 前端 `pnpm test`：**79 passed**；`pnpm build` 包含 Vue 类型检查：**退出 0，36.65 秒**。固定 Node 24.18.1 / pnpm 10.33.4。
- 独立环境无模型 smoke：并发 1→2→1、服务重启、资源清理通过；环境辅助模块 19 项测试通过，图片证据模块 3 项测试通过，均包含在上述全量测试中。
- 完整机器报告与下载图存于本轮忽略输出目录；公开播报不是模型原始日志，usage 按 CLI 实际返回值记录，不推算缺失数据。

## 并行与故障结果

- 并行任务 `f2f5d46f-781d-4502-8ac4-da19ae8c47af` / `c171e142-94b4-4a90-ab1a-bea3efb55158`，PID 分别 17073 / 16825，独立 session `01a0904a-69ed-7803-8f94-5ea81f199ac6` / `01a0904a-683d-7a80-a3cb-b002034f56df`。两个任务均只有一个 attempt、execution_count=1、exit 0。
- 50 个采样点同时观察到两任务的真实 CLI 进程，首尾采样间隔 102.9 秒；进程树采样 RSS 峰值约 200.0 / 197.9 MiB。报告保留全部 296 个资源采样点和 CPU ticks；RSS 是各进程求和，可能重复计共享页，不等于物理内存净占用。
- 两张发布图片分别与所属 session 的原生产物哈希一致。以实际生产 sandbox 挂载运行双向读写探针，另一任务目录不可读写，哨兵内容不变。
- 启动后早期取消任务 `a9a37e2d-8215-4e39-81d3-c21f24fac5c6`：receipt reason=cancelled、exit -15、执行约 0.235 秒。这证明启动后的取消，不声称覆盖图像工具长时间运行中的取消。
- 专用 10 秒超时任务 `59c6460d-480d-406e-8369-28c637492157`：receipt reason=timeout、exit -15、执行约 10.189 秒。两项 attempt 均 finished，已采样根进程和后代进程无残留，未自动再次执行。
- 完整脚本退出 0；报告 `status=passed`、`cleanupComplete=true`、`cleanupErrors=[]`、`defaultConcurrencyRestored=true`、并发 1。清理三个专用容器/卷及执行目录；正常 `hx-local-test` API/Outbox/存储和真实 WSL Worker 仍运行。专用前端 3009 已停止。
- 可复验证据：`output/playwright/phase11a-closeout/report.json`、`regression.txt`、初始两图和实际浏览器下载的 `Phase11A-serial.zip`；原机器报告保留在 WSL `/home/hengxin/runtime/phase11a-closeout-results/`，不纳入 Git。

## 验收边界

本阶段覆盖壁纸 Skill 与所选两张实际模板图；商品、文字 Skill 未提供，不宣称已测，仍留 Phase 14。像素尺寸一致性按已确认例外跳过，生产规则和部署验收要求不变。本阶段不替代钉钉双端实机登录和 Linux 生产部署验证。

## 审查后的验证补强

首次独立审查 Stage 1 PASS / Stage 2 FAIL，指出的是验收脚本的漏检窗口，不是此次真实任务发生重复执行或清理失败。整改要求：每轮唯一 attempt 且有完整执行身份、恢复沿用原 attempt、截止后仍严格确认业务终态、超时耗时有容差断言、父进程快速退出仍可追踪回收后代。

原始真实报告保持不改写；后续辅助脚本的反例测试和无模型环境复验独立记录，不冒称新代码又执行了一轮收费生图。已对原始串行记录重新核对三轮各一个 attempt、PID/出生身份/CLI 版本非空。

- 每轮 attempt 唯一性、期待轮次集合及执行身份、恢复 attempt 不变已加入检查；取消/超时必须达到匹配的 round/job 终态，10 秒配置的 receipt 容差为 9–30 秒。
- 新增 Linux subreaper 托管，每个命令/服务先建立内核后代收养关系再启动。监督进程持续回收后代，只有收到 ECHILD 后发出的完成凭据才能声明清理成功；不依赖先轮询捕获后代，不按进程名称批量终止。
- 针对性环境/监督进程/证据测试：**41 passed，49.09 秒**；最终隔离 PostgreSQL 全量回归：**656 passed，0 skipped，10 warnings，91.21 秒**。日志 `regression-final.txt`，包括关闭发现轮询后快速退出父进程、子进程 setsid、TERM 再派生后代、重复 TERM、缺失清理凭据拒绝通过和外部进程保留。
- 修复后的独立无模型环境 `hx-p11a-f27a57f15ed37d44` 实测启动、并发 2→1、服务重启及清理全部通过；`supervisor-smoke.json` 记录 `fullRegression=passed`、`smoke=passed`、`cleanupComplete=true`、错误列表为空，辅助环境没有提交模型任务。Docker 标签复查无本轮容器残留。
