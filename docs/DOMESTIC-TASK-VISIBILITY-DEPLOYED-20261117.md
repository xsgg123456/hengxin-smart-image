# 国内切页误判权限失效修复发布记录

2026-11-17，用户授权发布后，已在 `hengxin-ai-245 / 192.168.1.245:8080` 通过官方流程仅更新国内前端，版本 **0.2.76**，业务提交 `4541b95c2a0f96b8f9395a3d3457b2c43b8f9ac9`。服务器正式 verify 和入口静态资源 HTTP 核验通过，pending 为空。实际生产浏览器切页及上线后视觉验收未完成：用户按 Esc 停止了 Computer Use，此后未继续控制浏览器或另用自动化方式绕过停止。

## 修复与固定交付

- 任务页和管理员会话监听此前把 `suspended`（浏览器暂时隐藏）一律转成403并永久锁定。现在只对真实 `changed/invalid` 身份事件执行撤权清除；全局隐藏遮蔽、返回身份重验和接口401/403处理保持。
- 最终批准快照：`1246362d88ba2d31b949b0bafc4c480ca5d7c958700b39d122deb87d6b6fd7bc`。[独立审查及版本增量复核](reviews/DOMESTIC-TASK-VISIBILITY-FIX-20261117.md)两阶段PASS。
- 本地597项前端测试、类型检查通过；新增5个切页用例在修复前失败、修复后通过。隔离正式页面15项浏览器检查、60个业务请求通过，覆盖五业务列表、管理同步暂停/开启、详情恢复、隐藏期间401、撤权及迟到响应。这里是生命周期事件驱动测试，不是实际OS切标签验收。
- 从固定提交使用官方 `package_release.py --scope domestic` 构建，Node24.18.1、pnpm10.33.4，冻结锁安装、类型检查和生产构建通过。1102项有效载荷，5912699字节，SHA256 `a20814aaf949155c6fb484c49e9df39abc63c326332ad69d2130b7755cb6f4fa`。逐文件摘要、敏感路径/密钥及禁止文件扫描通过；迁移和身份模块摘要保持。
- 依赖未变更；生产依赖审计 critical=0，已有 high=39、moderate=35、low=5，不能将本次审计描述为无已知依赖告警。本次未升级依赖。

## 发布与服务保持

上传包 `lan-domestic-20261117-task-visibility-4541b95.tar.gz`，远端SHA256一致。服务器官方stage、普通prepare/deploy `--scope domestic --mode frontend` 和最终verify全部成功。没有运行迁移、角色调整或后台任务重启。

| 组 | 当前前端 | 当前后端 |
| --- | --- | --- |
| domestic | `4541b95c2a0f96b8f9395a3d3457b2c43b8f9ac9` | `02ddb53749a9e16580a965b64ea13ffdd19aef51` |
| overseas | `3b38a2c445149d4a0d12c4145cc90f9e173ab4aa` | `3b38a2c445149d4a0d12c4145cc90f9e173ab4aa` |
| shared | `2bc8acc7ecf412626a6a635a9413b1644b55417e` | `2bc8acc7ecf412626a6a635a9413b1644b55417e` |

国内上一成功状态为前端3d05c0a、后端02ddb53，数据库仍兼容0044；可通过普通国内分组回退恢复上一前端，不倒灌数据库。发布前后21个容器的ID、启动时间和镜像比较，只有 `hengxin-lan-domestic-ui` 改变，其余20个保持；9个原生服务的MainPID及启动时间保持。

正式 `192.168.1.245:8080/domestic/` 的入口HTML、入口脚本、国内主模块、TaskPage入口与实际实现JS、CSS及图标共10个资源均HTTP200，字节摘要与发布包逐一一致。这证明新产物在正式入口生效，不替代浏览器切页和视觉验收。用户已打开的旧页需要整页刷新才能载入修复。

## 两版保留与自动清理

发布事务：`/var/lib/hengxin-release/intranet-transactions/lan-domestic-20261117-task-visibility-4541b95-1794906094417117272`。自动清理complete、errors为空；按全部组两版和真实引用保留当前资源，国内后端02ddb53仍被当前/上一状态使用，其源码和包保留。

同口径 `release-sources+lan-root+ledger+docker-LayersSize` 从3908566165降至3907771541字节，净释放 **794624字节**。源码与镜像释放0；仅移除已失去两版引用的旧02ddb53发布事务（790528字节），其余差额来自台账目录记账变化。业务数据库、图片、素材、账号和在用依赖不属于清理对象；未知遗留目录保持未接管。

原始证据保存在Git忽略目录：`output/task-visibility-{package,production-before,production-stage,production-prepare,production-deploy,production-final-verify}.log`、`output/task-visibility-package-audit.json`、`output/task-visibility-dependency-audit.json`、`output/task-visibility-runtime-{before,after}.json`、`output/task-visibility-production-http.json`、`output/playwright/task-visibility/report.json`。没有提交生产业务内容或凭据。
