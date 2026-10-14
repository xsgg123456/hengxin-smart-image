# 海外删除修复与确认框简化发布

## 授权与范围

用户于2026-10-14明确要求两项一起上线并提交Git。发布前端0.2.30、海外API、海外原生worker/outbox；国内与统一身份服务保持原运行实例。数据库保持国内0028、海外overseas_0014，不执行迁移。真实失败任务保留，不用其做破坏性验证，不触发收费模型。

## 执行计划及完成标准

1. 只读复核：核对当前0.2.29、生产拓扑、schema、海外持久化任务与Celery/broker状态；证据可追溯且无状态未知的执行器。
2. 准备交付：更新版本与打包入口，补充无迁移发布编排，使用既有完整Compose配置及只改image/build的覆盖层；构建、依赖审计、发布脚本回归及独立两阶段审查通过，提交精确已审快照。
3. 安装及备份：从已提交源码打包并验证隐私与哈希；服务器构建实际镜像并执行安装测试；关闭海外入口后验证503、停止API接纳，连续两次确认任务和broker为空，再停止outbox后二次排空才停worker；备份数据库、配置、原生指针与前端入口。
4. 切换与验收：仅切换海外API/原生服务和共享前端；验证镜像与文件哈希、挂载、队列、技能只读目录、健康/匿名权限、正式静态资源及真实浏览器弹框。已知失败任务用安装后真实权限只读inventory验证，不执行删除。
5. 记录交付：记录提交、版本、发布包哈希、备份和验证结果。失败时关闭海外入口、保留执行器状态证据，排查后恢复已备份应用版本；禁止自动恢复数据库覆盖新数据。

## 当前结果

已于北京时间2026-10-14 08:24:53完成发布。功能证据见[修复记录](OVERSEAS-DELETE-LINK-FIX-20261013.md)和[最终功能审查](reviews/OVERSEAS-DELETE-FINAL-20261013.md)。

- 发布前只读复核：生产0.2.29、0028/overseas_0014；海外pending=0，Celery active/reserved/scheduled均为空，broker队列和unacked均0；磁盘可用46G。
- 同uid999重新检查失败任务，仍准确复现旧代码 `Linked workspace cannot be erased`，任务版本5及删除回执时间未变。
- 前端0.2.30正式构建含vue-tsc通过，Vite 4708模块、50.20秒；发布打包规则25项通过。日志 `output/overseas-delete-release-build.log`。
- 锁文件及依赖未改；本轮依赖审计critical=0、high=70、moderate=48、low=5。保留原始 `output/overseas-delete-release-audit.json`，不把既有依赖告警称为零漏洞。
- 首轮发布审查发现优化模式保护本身使用assert会被Python优化删除；已改为显式RuntimeError，真实 `-O` 与 `PYTHONOPTIMIZE=1` 子进程均在生产动作前拒绝，发布编排13项测试通过。

## 正式交付与验收

- 代码提交：`2abcdfc64ea4714fa898a6df8aae98c21ad44758`，`fix(overseas): 修复删除失败并简化确认弹框`。版本0.2.30；发布标识 `overseas-20261014-2abcdfc`。
- 已批准快照：`159d164b5c9f4250034089caf34b0feacbe5d559ec48f254a109864d7ae755b1`，独立[最终发布审查](reviews/OVERSEAS-DELETE-RELEASE-FINAL-20261014.md) Stage 1/2 PASS。该快照与已提交源码一致。
- 包含1,449个文件（其中1个release manifest），8,628,512字节；隐私审计及归档读回PASS。包SHA256：`ed82cb9899c92d72dbd7f81808a9ac1095105dd38c0d2376ddebb31439bdd7c8`；服务器上传后重验全部1,448个内容文件一致。
- 实际安装镜像：`sha256:f1fae9a88be22da6d54c681167915d3336d0f3ce1bae529c677991b9de008514`。镜像内563个后端文件哈希通过；无网络测试 **1888 passed / 184 skipped / 1 deselected / 15 warnings**，382.62秒。跳过/排除遵循既有生产包测试入口（外部环境及未打包的开发/前端源文件验证）；未发起模型调用。
- 08:21:22开始关海外入口，轮询确认503后停止API接纳；停outbox前后分别连续两次确认jobs、deleting、active/reserved/scheduled、broker及unacked为空，才停止worker。08:24:49恢复入口，08:24:53全部校验完成。重载后首个健康探测短暂503，由既有重试成功恢复，最终状态complete。
- 备份目录：`/opt/hengxin-backups/overseas-20261014-2abcdfc`；保存海外PostgreSQL dump（pg_restore --list可读）、完整配置、原生服务指针、原前端入口、原发布标记和代理配置，COMPLETE标记存在。备份留在服务器受限目录，不纳入Git；未执行数据库迁移或恢复覆盖。
- 海外API及两原生进程的实际镜像、工作目录、源文件哈希、挂载、并发5和overseas.cli队列通过；14份/181文件技能目录与只读沙箱校验通过。国内/统一身份容器ID、国内原生进程PID及工作目录不变，相关健康及匿名权限检查通过。
- 正式入口HTML及引用静态资源逐项哈希通过。Chrome通过既有钉钉身份重新登录，刷新后打开真实任务“测试”的“重试删除”：任务名称和归档保留说明可见，输入框0个，“确认删除”已可用；点击“取消”后两条任务仍在。生产截图及结构化结果：`output/release/overseas-20261014-2abcdfc/delete-confirm-production.jpg`、`browser-verification.json`。
- 新安装代码在真实outbox环境、uid999、只读数据库事务下重新检查两条失败任务：原先均因CLI链接失败的inventory现在均PASS，各1个对象、1个专属目录。任务版本仍为5/2，删除回执时间和各4个工具链接不变；未发送生产DELETE请求，未重试、清理任务或修改已归档成品。界面历史“删除失败”状态保留，用户可以自行点击重试。
- 原始验收证据在 `output/release/overseas-20261014-2abcdfc/`：`package-audit.json`、`installation-tests.log`、`verification.json`、`SKILLS_VERIFIED.json`、双轮排空记录、`task-one-after.json`、`task-two-before.json`、`task-two-after.json`、`final-release.json`。生产工作目录 `/opt/hengxin-releases/overseas-20261014-2abcdfc` 保留各阶段日志与恢复指引。
