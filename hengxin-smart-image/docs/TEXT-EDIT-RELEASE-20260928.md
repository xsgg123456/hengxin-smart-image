# 单图文字替换生产发布 · 2026-09-28

用户已授权 Git 提交、打包与生产部署。功能提交 `e282255`：单张原图、可选复用 CLI 标注画布、内置冻结提示词、历史 Skill 任务兼容。目标前端 0.2.11、迁移 0020。本记录随实际发布结果更新；当前为准备阶段。

## 生产基线与发布步骤

只读实查主机 racknerd-058889d：前端 0.2.10，API/两个 outbox/API Worker/派生消费者均为 `performance-20260927-e765df7`，原生 CLI Worker active；schema0019、CLI/API 无在途任务、API paused=false、容量准入保持关闭，ready200。

完整 Compose 链来自正在运行的 API labels，共11层至 `/opt/hengxin-releases/performance-20260927-e765df7/api-override.yaml`。发布仅在原链末尾增加本次镜像覆盖，不重建资源/队列/凭据配置；部署前再次检查基线与队列。

流程：已审功能提交 → 版本/发布增量审查提交 → 白名单包与隐私扫描 → 实际镜像断网安装测试 → 停接纳并排空 → 数据库/源码/入口/配置备份 → 0019→0020 → 同步原生与容器服务 → 前端原子入口切换 → 线上核验。

## 已有验证证据

- 业务实现验收与独立审查见 `TEXT-EDIT-20260928-VALIDATION.md`、`TEXT-EDIT-20260928-REVIEW.md`；后端1354通过/113跳过，前端197通过。
- 0.2.11 构建：`pnpm test` 197通过；`pnpm build`（含vue-tsc）成功、32.63秒，恢复构建生成的无关组件声明后单独vue-tsc退出0。
- `pnpm audit --prod --json`：critical=0，high=33、moderate=30、low=1。本轮无依赖变更；不声明依赖全部无漏洞，既有告警未在本次功能部署中升级修复。
- 证据目录：仓库根 `output/text-release-*`、`output/text-production-before.json`；实际归档与生产核验追加至本记录。
- 本次发布专项14项通过。独立扩展历史发布回归44项中42通过、1失败、1 Windows符号链接权限跳过；失败是未改动的 `test_release_native.py:100` 仍期望 annotation 末层，而旧 `image-inputs-frontend.py` 使用 materials 末层。此旧前端脚本不在新包白名单，本次不改写其历史语义，不宣称全历史回归通过。

## 回退约束

切换前保留完整旧 Compose 链、镜像、原生 app、前端入口/元数据与可读取的数据库dump。入口尚未开放时，失败恢复旧代码及配置，保留新增schema，不恢复dump覆盖业务数据。

一旦新入口开放，可能已有无 Skill 任务；此时不能直接回旧代码。失败先关闭入口、暂停接纳并保留新代码，排查后前向修复或单独制定兼容回退。排空不确定时不强停或重启未知 Worker。生产部署不自动执行收费生成，不据此宣称真实文字效果验收通过。
