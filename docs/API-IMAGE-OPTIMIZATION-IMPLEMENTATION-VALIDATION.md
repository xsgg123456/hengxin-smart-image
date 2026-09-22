# API 换套图正式实现验证 · 2026-09-22

本轮交付为正式前后端代码与本地验证，尚未生产部署、未发起收费上游生成。UI按已确认预览实现，真实HTTP联调使用隔离数据库、内存对象存储与模拟上游。

## 六项交付

- 通道级最多10张并行；保留在途任务与批次，11张按10+1。正在第二批时修改第一批、修改更早任务均不能突破上限。逐项租约/心跳，过期进程迟到写入被拒绝。
- 请求失败按1/2/4秒最多3次自动重试；成功项保持。已收到生成回执则只重收结果，耗尽支持单项或整套失败项重试。返回的网络超时按用户要求有限重试；进程丢失且无法确认停止仍需管理员核实。配置/密钥/额度错误保留通道暂停。
- 正式记录页52px缩略图、操作人及格式化时间；静默轮询不卸载详情、不清输入/滚动。错误可见但保留已显示结果。
- 全成功ZIP使用当前选定结果的一致快照、顺序01起名；对象读取校验长度/校验和，临时文件流限制内存占用。失败可重试。
- 单图修改冻结当前图、可选JPG/PNG标注图和用户文字；不内置业务提示词，服务端限制10MiB。成功发布新版本，失败保留旧结果；未知POST重用原幂等键及输入。
- 版本持久化，历史对比/下载/确认恢复；恢复后再修改递增编号。0016迁移回填旧结果V1并保留旧在途租约。旧图和标注受引用保护，操作记录带实际操作者。

## 验证证据

证据目录：`output/api-optimization-preview/`（测试产物不入Git）。

| 验证 | 命令/结果 |
| --- | --- |
| Windows后端全套（审查修复前） | `.venv/Scripts/python.exe -m pytest -q`：820 passed，158 skipped，54.35s；backend-full.log |
| 最终Linux后端全套 | 临时容器内 `python -m pytest -q`：924 passed，64 skipped，89.70s；backend-linux.log。源目录只读、代码复制至tmpfs、独立PostgreSQL schema。本次API数据库测试全部执行，跳过项属于其他模块专用环境/WSL/开关条件。 |
| 审查修复专项 | 跨任务/跨批次并发及删除/标注保护：23 passed；concurrency-fix.log |
| 完整修改执行链 | 首次生成与原图不同；修改4次失败保旧版本/邻居，手动重试仍用冻结基础图和标注；1 passed，revision-execution.log |
| 前端全套 | `node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts`：153 passed，0 failed；formal-frontend-tests.log |
| 前端类型 | `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：退出0 |
| 正式构建 | `node node_modules/vite/bin/vite.js build`：退出0，39.22s；formal-build.log |
| 浏览器真实HTTP | real-flow.cjs / real-evidence.json：上传标注、请求已受理但响应丢失、同键确认仅新增一版、其他结果不变、历史恢复、ZIP下载、轮询保输入及400px滚动位置；无页面错误。上游为fixture，未验证真实生图效果。 |
| 视觉 | real-revision-1440.png、real-revision-1280.png、real-history-1280.png，与已确认预览样式一致。 |
| ZIP产物 | real-restored.zip，11个有序文件，CRC全部通过；领域测试校验真实字节与恢复快照。 |

## 审查修复

独立审查复现了跨批次突破并发上限，以及入队覆盖任务状态导致在途任务可删除。已改为通道级租约上限、固定在途任务/批次、全项状态汇总和删除实际项检查；原复现变为 running=10/extra_claim=False、DELETE409，并加跨任务与跨批次PG回归。

Linux初次运行缺少infra与前端契约挂载；补齐后全套通过。新增执行测试初次误用全项时间推进帮助函数，导致邻居nextAttemptAt被测试自身修改；已改成仅推进目标项并通过。以上均未改弱断言。

## 实现依据

并发执行使用每线程独立Session，短事务领取后再做网络I/O，遵循 [SQLAlchemy官方会话并发说明](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)；线程池显式限制10，参照 [Python concurrent.futures](https://docs.python.org/3.13/library/concurrent.futures.html)。

生产发布需应用0016迁移并更新API与专用API Worker、前端；旧Worker需停止领取并排空在途任务，避免新旧执行协议混跑。本轮未执行发布。
