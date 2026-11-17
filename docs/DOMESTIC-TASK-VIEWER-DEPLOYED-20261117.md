# 任务中心只读浏览优化发布记录

2026-11-17，用户授权开发、中文Git提交和部署后，已通过官方内网流程发布国内前端 **0.2.77**，业务提交 `93718b7e42227018ee295d7319b43d234966fe6d`。目标 `hengxin-ai-245 / 192.168.1.245:8080`；最终verify成功，pending为空，正式页面验收通过。

## 交付与测试

- 任务中心只读会话支持展开/退出，保留会话选择、阅读位置和同步。图片卡片及查看器复用正常工作台，支持分组切换、缩放拖动、文件名/进度、原图下载及Esc返回。管理员文件仍经原有受限GET读取，没有新增写权限或后端接口。
- [开发验证](DOMESTIC-TASK-VIEWER-VALIDATION-20261117.md)：599项前端测试、类型检查、国内生产构建通过；开发服务及构建产物各通过16组隔离浏览器检查，分别112/111个只读业务请求；正常工作台图片路径、ZIP、异常取消回归通过。
- [独立审查](reviews/DOMESTIC-TASK-VIEWER-20261117.md)两阶段PASS，批准快照 `9bffde69c80fd48a83d329dbf7f4f5fa11373ef0285abfabfc79e35009041992`，交付代码与快照一致。
- 官方package_release从固定提交构建domestic包；Node24.18.1、pnpm10.33.4，冻结锁安装、类型检查、生产构建通过。1102项有效载荷，5914656字节，SHA256 `dc0bcf04881301021d923f86aa8af818d7c965ae4521793220663b4fa91b58d7`。逐文件摘要、敏感路径/密钥及禁止文件扫描通过；身份与迁移模块固定摘要保持。
- 依赖无变更，审计critical=0，既有high=39、moderate=35、low=5；没有宣称消除既有依赖告警。

## 正式发布与页面验收

上传专属包 `lan-domestic-20261117-task-viewer-93718b7.tar.gz`，远端SHA256一致；执行官方stage、普通prepare `--scope domestic --mode frontend`、deploy和verify。仅切换国内静态前端，不运行数据库迁移、角色调整或后台任务重启。

| 组 | 当前前端 | 当前后端 |
| --- | --- | --- |
| domestic | `93718b7e42227018ee295d7319b43d234966fe6d` | `02ddb53749a9e16580a965b64ea13ffdd19aef51` |
| overseas | `3b38a2c445149d4a0d12c4145cc90f9e173ab4aa` | `3b38a2c445149d4a0d12c4145cc90f9e173ab4aa` |
| shared | `2bc8acc7ecf412626a6a635a9413b1644b55417e` | `2bc8acc7ecf412626a6a635a9413b1644b55417e` |

发布前后比较21个容器ID/启动时间/镜像，只有hengxin-lan-domestic-ui变化；其余20个容器及9个原生服务的PID/启动时间保持。国内上一成功前端4541b95、后端02ddb53保留，可按普通国内分组回退，不倒灌数据库或覆盖其他业务。

正式 `/domestic/` 入口HTML、脚本、TaskPage实现、CSS与图标共10个资源HTTP200，摘要与包逐项一致。通过独立Chrome验收页打开真实任务与会话，页面升级公告显示93718b7e4222；实际操作展开、查看本轮三图并切至2/3，原图清晰显示；附件与结果面板的生成标签显示六图，打开6/6确认查看器覆盖抽屉；Esc关闭返回面板、关闭抽屉和退出展开恢复原页，同步时间持续更新，只读页脚保留。直接查看了正式页面截图；生产会话内容和截图不入Git。未修改业务消息/任务、未代发或停止执行。

窄屏与缩放拖动/下载/故障注入在隔离浏览器验证；本次正式页面验收不冒充真实OS标签切换测试，前次切页修复的该项生产验证边界保持原记录。已打开的旧页面需整页刷新加载新前端。

## 两版保留与自动清理

事务 `/var/lib/hengxin-release/intranet-transactions/lan-domestic-20261117-task-viewer-93718b7-1794911128626711850`。自动清理complete、errors为空；保留全部组两版及容器/进程/挂载等实际引用，当前/上一国内前端及在用02ddb53后端均保留。

同口径 `release-sources+lan-root+ledger+docker-LayersSize` 从3938270357降至3907783829字节，净释放 **30486528字节**。删除超出两版且无人引用的3d05c0a源码（24375296字节）、上传包及发布事务（6111232字节）；镜像释放0。业务数据库、图片、素材、账号及在用依赖不在清理范围，未知遗留目录保持未接管。

原始证据位于Git忽略的output：task-viewer-{package,production-before,production-baseline-verify,production-stage,production-prepare,production-deploy,production-final-verify}.log，task-viewer-{package-audit,dependency-audit,production-http,runtime-before,runtime-after}.json，以及playwright/task-viewer、task-viewer-build、studio-viewer-regression。发布日志与业务内容未纳入提交。
