# 固定生产执行模型 · 2026-09-17

用户要求生产模型固定 `gpt-6-astra`，推理强度 `high`。首次调用与返工 resume 均显式传入 `--model gpt-6-astra -c model_reasoning_effort="high"`，参数在对应子命令内生效，不依赖账户默认模型。未修改提示词、Skill 或历史任务，未自动重试失败任务。

- 发布：`model-20260917-0bb0454`，API/Outbox 镜像同名标签；原生 Worker 已同步代码并重启。
- 批准快照：`0bb045467430d622862ddc3483a30b47df7324d1143f5e6bdbf905ac5c2691d1`；独立两阶段审查见 ASTRA-HIGH-REVIEW.md。
- 回归：执行、观测、工作区、返工、提示词专项 62 passed / 1 skipped（Windows 无 POSIX 符号链接专项）；编译通过。返工测试注入错误模型会失败。
- 生产 CLI 0.153.4 实际接受 resume 模型参数；同隔离环境 config/read 返回 model=gpt-6-astra、model_reasoning_effort=high，model/list 确认 high 受支持。仅执行配置查询，没有模型生成请求。
- 发布包 SHA256：`0e28d69e38595a86486cbb0afe0fee1b011626909f7b9bcff183b0e2dca3ec36`。
- 备份：`/opt/hengxin-backups/model-20260917-0bb0454`；发布材料：`/opt/hengxin-releases/model-20260917-0bb0454`。
- 部署脚本确认无在途任务，备份后部署，Worker active、服务 ready；真实生图效果与调用 usage 仍需后续新任务验收。
