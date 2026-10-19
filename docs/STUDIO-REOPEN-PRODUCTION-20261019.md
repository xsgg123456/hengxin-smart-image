# 工作台完成与解冻发布验收

用户授权正式开发、中文 Git 提交、打包并部署生产。2026-10-19 已发布 0.2.43，功能及发布配置提交 `1c28ee2`，发布标识 `overseas-20261019-1c28ee2`。两阶段独立审查通过，快照 `f8adb677ed1b16f72dd5f811f293b6973ed0028acce3e4306b89835b112b8842`，报告见 `reviews/STUDIO-REOPEN-IMPLEMENTATION-20261019.md`。

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

## 生产发布与数据保护

只读核实基线：0.2.42，`overseas-20261019-daf9d5e`，海外 `overseas_0019`、国内 `0030`；本次无数据库迁移。正式入口已确认是用户原始已完成灯具任务。

发布前已记录该任务 1 个会话的 166 个 session/persistent 文件摘要，位于服务器 `/opt/hengxin-backups/studio-reopen-before-files-20261019.json`，发布后逐一复核。未读取或导出认证凭据内容。

- 发布包 1224 个文件、5,458,615 字节，SHA256 `75595ac6181c10e6ad4c4ade2e19a3d5c815b8edc82555d3f7eecf223244beb5`。隐私审计、解包文件集合与逐文件摘要校验通过；独立预览未打入生产。
- 正式镜像 `sha256:1a406c0ad954788dbe5b6c004005dcea6005e318995dc716e1d86d3fcc808854`。镜像内 536 个后端文件与提交匹配；实际安装测试 2028 passed、160 skipped、1 deselected、6 warnings，437.79 秒；按既有发布入口排除本地 CLI 专项和源码接口对照项，条件跳过不计作验证。容量 4 项通过。
- 入口关闭后排空 worker active/reserved/scheduled、队列/unacked 与数据库在途任务，正常停止执行服务。备份在隔离数据库恢复并验证全部行指纹；本次 `SCHEMA_UNCHANGED` 核验通过，没有迁移或业务数据删除。
- 备份 `/opt/hengxin-backups/overseas-20261019-1c28ee2`；发布目录 `PHASE=complete`、`INSTALLED_VERIFIED`、`verification.json` 均存在，部署命令退出码 0。海外 API、原生 worker/维护循环及共享前端均已切换，海外入口恢复。
- 发布后逐一比较原任务的 166 个 session/persistent 文件 SHA256 全部相同。国内与身份服务保持，国内原生服务及共享凭据代理状态/进程/配置/源码与发布准备时完全一致；Skill 校验通过。国内 18008、海外 18018 健康检查均 200，线上前端版本为 0.2.43。
- 部署日志：`output/studio-reopen-production-build.log`、`output/studio-reopen-production-prepare.log`、`output/studio-reopen-production-deploy.log`；包和审计位于 `output/release/overseas-20261019-1c28ee2/`。

## 正式入口视觉验收

从正式域名打开用户原始“直杆实木布罩灯-乡村风”任务，目视确认四个绿色勾及“全部完成”、只读历史和原两张图片，独立“查看归档成品”“解冻工作台”按钮均展示。

点击查看归档，打开实际归档 UUID `a814e3b5-8998-46b4-982e-6eff91ce7912`，品名、品牌、SKU、归档人/时间及两张 1600×1600 原成品均正常。关闭后打开解冻确认，说明回第三步并保留原会话；点击取消。生产任务仍为 `completed:3`，解冻事件数为 0，未触发模型调用或替用户改变任务状态。

已目视核对实际生产截图：`output/studio-reopen-ui/production-completed.png`、`production-archive.png`、`production-reopen-confirm.png`。完整完成/解冻/续用协议闭环在独立环境验证，生产验证真实入口与只读/确认取消分支。
