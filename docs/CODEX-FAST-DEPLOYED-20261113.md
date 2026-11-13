# 国内、国外 Codex Fast 部署验收

2026-11-13 晚，用户明确恢复部署授权后完成内网 `hengxin-ai-245 / 192.168.1.245:8080` 切换。此前等待期间只准备包，未自动部署。

| 项目 | 验收结果 |
| --- | --- |
| 国内前后端 | `3b38a2c445149d4a0d12c4145cc90f9e173ab4aa`，上一成功版本 `9a884b7` |
| 国外前后端 | 同上，上一成功版本 `2bc8acc7` |
| 共享业务 | 保持 `2bc8acc7ecf412626a6a635a9413b1644b55417e` |
| 发布工具 | `31249944c5fea417`，工具代码提交 `fa59432` |
| 发布事务与入口 | pending 为空，ingress/workers 均 open |
| 正式健康检查 | 国内/国外 ready、身份 config 均返回 JSON HTTP 200 |

国内工作台、API 图片 CLI 修改会话、国外全部协议 runner 的实际运行源码均有 `-c service_tier="priority" -c features.fast_mode=true`；覆盖首轮和续聊，不依赖旧会话速度配置。原模型、思考强度、Skill 选择及上下文保持。主工作台仍为 `gpt-6-astra` / `high`。本次未发收费模型任务测速度，不宣称固定倍数或端到端耗时保证。

发布沿用已构建两包，国内 SHA256 `63d8814acd9ae6353732e04e1580bbe75448c9361e002101640674dee307f8bc`，国外 `35fa80a6a14b66a453dc2cc1c125b0132fbc2cf0be062837597896a9c95d2cb3`。重新核对每个包内文件摘要及隐私扫描后，使用正式 stage.py、受限 prepare-fast 和原 deploy 状态机，逐组备份、排空、切换、运行环境及其它组身份核验；没有迁移数据库、更新依赖或重跑旧联合迁移。

国外 runner 的国内间接引用由专用维护入口处理，仅放行固定已审提交和该文件旧/新 SHA 对应的一行 Fast 参数变化。普通 prepare 仍拒绝跨业务改动；维护类型记录到事务。恢复、回退和两版保留继续使用原分组命令。两组自动清理均 complete，本次净释放均为 0，不声称额外释放空间。

验证：业务改动隔离回归 39 passed；维护工具两阶段独立审查通过，本地全套 409 passed、5 skipped、15 subtests passed；服务器最终工具路径在只读根目录、独立 /tmp、无网络的 bwrap 沙箱测试 407 passed、5 skipped、15 subtests passed。跳过项不作为验证通过。安装切换工具时业务台账未变。

正式浏览器核验：国内新建换图、只换产品工作台及已有会话正常显示，Skill 勾选默认未选；国外工作流任务列表刷新后正常显示。仅查看页面，没有发送测试会话或改动用户附件。

本地原始证据（Git 忽略）：`output/fast-release-domestic.log`、`output/fast-release-overseas.log`、`output/fast-maintenance-tool-install.log`、`output/fast-production-postcheck.json`、发布包旁 `.audit.json`。审查见 [维护报告](reviews/CODEX-FAST-MAINTENANCE-20261113.md) 和 [业务报告](reviews/CODEX-FAST-20261113.md)。
