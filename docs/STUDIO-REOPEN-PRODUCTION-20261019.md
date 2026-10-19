# 工作台完成与解冻发布验收

用户授权正式开发、中文 Git 提交、打包并部署生产。目标版本 0.2.43；本文在发布后补充实际版本、产物和正式页面证据。

## 开发验证

- 前端完整测试 312/312 通过，类型检查通过；`pnpm run build` 生产构建通过，沿用既有模式与配置。日志：`output/studio-reopen-build.log`。
- Linux 隔离容器完整后端测试：2196 passed、101 skipped、6 warnings，304.52 秒。启用专用 `studio_reopen_test` PostgreSQL，测试通过临时 schema 隔离。日志：`output/studio-reopen-linux-full.log`。
- Linux/PG 生命周期、原会话协议及归档删除专项 33 passed；包括真实行锁并发、完成与发送竞争、重复操作及原会话文件保留。协议进程为测试替身，不是收费模型调用。日志：`output/studio-reopen-linux-pg.log`。
- Windows 后端全量 1950 passed、339 skipped、8 failed。失败是既有 POSIX 安全文件打开及符号链接权限的平台边界；Linux 全量已覆盖并通过，未放宽安全实现。
- 新发布入口专项 25 passed、24 subtests passed。整个发布脚本套件 813 passed、309 subtests passed、1 skipped、1 failed；失败为 HEAD 已存在的 `test_release_wiring.py::test_cli_managed_wraps_main_outside_failure_handlers[codex-auth-deploy.py]`。认证修复有独立入口协议，不使用通用 managed 包装；本次未修改该入口或放宽断言。日志：`output/studio-reopen-release-tests.log`。
- 依赖审计 0 critical；既有 1 low、34 moderate、36 high 未在此功能发布升级依赖。生产静态资源隐私审计通过，612 个文件，9,977,811 字节；最终包另有完整审计。

## 真实交互验证

使用独立 Docker 网络、数据库、对象存储、测试身份与无执行器环境；真实 HTTP 授权、审核、归档、安装 Skill、删除隔离回归通过。模型调用为零。

CUA 操作正式组件和真实接口：选图归档 → 确认完成 → 四步全部完成、输入锁定 → 查看本任务真实归档详情（三张测试图片）→ 关闭详情 → 确认解冻 → 第③步继续设计、第④步已有归档 → 编辑草稿 → 查看归档并关闭，草稿仍在 → 再次完成成功。

截图：`output/studio-reopen-ui/completed.png`、`output/studio-reopen-ui/reopened.png`。隔离测试图明确标识为本地生成，未使用生产任务做状态变更。

## 生产保护与待执行步骤

只读核实基线：0.2.42，`overseas-20261019-daf9d5e`，海外 `overseas_0019`、国内 `0030`；本次无数据库迁移。正式入口已确认是用户原始已完成灯具任务。

发布前已记录该任务 1 个会话的 166 个 session/persistent 文件摘要，位于服务器 `/opt/hengxin-backups/studio-reopen-before-files-20261019.json`，发布后逐一复核。未读取或导出认证凭据内容。

待完成：审查批准、中文提交、包审计、安装测试、排空与备份恢复验证、服务切换和正式页面验收。以上待完成事项不构成发布成功声明。
