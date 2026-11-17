# 任务中心静默同步修复部署验收

2026-11-17已在 `hengxin-ai-245 / 192.168.1.245:8080` 完成国内前端发布。自动同步此前每3秒触发显式loading，导致刷新按钮和列表加载状态反复变化；本次将后台请求进行状态与可见loading分离，并固定刷新按钮宽度。首次、手动刷新及筛选保留反馈，已有内容后台静默同步；权限、迟到响应、异常及取消逻辑保持。

## 固定交付与验证

- 业务提交：`3d05c0ac7e740ae1af99b87aad31188bb27e19db`，前端0.2.75。
- 已批准代码快照：`52cec67ff9657598f7d84431c5142762699eec4ebdf1feaf77ccab731de69938`；[独立审查](reviews/DOMESTIC-TASKS-POLLING-FIX-20261117.md)两阶段PASS。
- 前端592项测试、类型检查通过；隔离浏览器52个只读请求通过，覆盖两轮真实计时轮询和慢响应期间按钮几何、内容节点、loading/遮罩，以及手动刷新、筛选、异常、撤权和迟到响应。
- 官方打包使用Node24.18.1、pnpm10.33.4，冻结依赖安装、类型检查和生产构建通过。包1102项有效载荷、5913408字节，SHA256 `2774060b0d82dd2ed0809edc993acbfebd79e48a7a49f848e15113c23b0ed32a`；逐文件摘要及包内隐私审计通过。

## 发布结果

包 `lan-domestic-20261117-task-polling-3d05c0a.tar.gz` 上传摘要一致。经服务器官方stage、普通prepare/deploy `--scope domestic --mode frontend` 及最终verify全部成功，pending为空；没有再次执行迁移或存量角色调整。

| 目标 | 当前前端 | 当前后端 |
| --- | --- | --- |
| domestic | 3d05c0ac7e740ae1af99b87aad31188bb27e19db | 02ddb53749a9e16580a965b64ea13ffdd19aef51 |
| overseas | 3b38a2c445149d4a0d12c4145cc90f9e173ab4aa | 3b38a2c445149d4a0d12c4145cc90f9e173ab4aa |
| shared | 2bc8acc7ecf412626a6a635a9413b1644b55417e | 2bc8acc7ecf412626a6a635a9413b1644b55417e |

国内上一成功状态为前后端02ddb53，当前及上一版均兼容0044，允许按官方普通分组流程回退此次前端；不得倒灌数据库或回退到0043应用。0043→0044已完成专项不可重跑。

发布事务：`/var/lib/hengxin-release/intranet-transactions/lan-domestic-20261117-task-polling-3d05c0a-1794903247591450587`。自动清理complete，同口径release-sources+lan-root+ledger+docker-LayersSize从3908930709降到3878083733字节，净释放30846976字节，其中旧c799246源码24186880、上传包和发布事务6656000、镜像0。所有组两版、真实引用和业务数据保持。

## 生产页面实查

使用现有超级管理员登录，在正式任务中心只读核验。同步时间由16:16:24更新到16:20:15、16:20:45，三次按钮采样均为x=1800、y=226.484375、宽84、高36，loading=false；最终截图无加载遮罩，列表正常显示6个任务。生产采样证明跨同步更新的布局稳定，慢响应期间无闪烁由上述隔离浏览器测试覆盖；没有新增付费模型调用或生产测试任务。

用户另外授权的17个未使用历史任务已持久清理，张帅5任务6会话全部保留，另保留甘双荣已使用的1任务1会话；清理前后保留内容摘要一致，详情见 [清理验收](DOMESTIC-UNUSED-HISTORY-CLEANED-20261117.md)。该清理文件净释放0字节，不与本次发布垃圾回收混为一谈。

本地证据位于忽略目录：`output/task-polling-{unit,typecheck,package,production-stage,production-prepare,production-deploy,production-final-verify}.log`、`output/task-polling-package-audit.json`、`output/playwright/task-polling/report.json`、`output/task-polling-production-ui.{json,png}`。未将原始生产业务内容或凭据提交Git。
