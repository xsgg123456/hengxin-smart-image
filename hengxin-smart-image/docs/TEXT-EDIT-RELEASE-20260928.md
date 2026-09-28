# 单图文字替换生产发布 · 2026-09-28

2026-09-28 13:17（Asia/Shanghai）生产切换完成，随后在线核验通过。功能提交 `e282255`：单张原图、可选复用 CLI 标注画布、内置冻结提示词、历史 Skill 任务兼容。发布代码 `0ebb3bc`，前端 0.2.11、迁移 0020。已本地提交，未推送远端；用户授权生产发布，未执行收费生成。

## 实际发布结果

- 发布标识：`text-edit-20260928-0ebb3bc`，归档789文件、4905427字节；SHA256 `7a4046bc644421ed076b2d4fe38297d7f41fffca06e39d5d2aedc66aa68668f0`，本地/上传后校验一致。
- 镜像：`hengxin-smart-image-backend:text-edit-20260928-0ebb3bc`；ID `sha256:8df57e8dc1a2406c4bad871694b88499fa5f59395a19cce06c650c4c304f4e37`。实际镜像断网、无生产挂载测试1282通过/76环境跳过/1仓库源码对照排除，166.68秒。排除/跳过不计为通过。
- 发布增量独立 Stage 1/2 PASS，批准快照 `92d05a54d9398ad57b76aa38e1cf2734cef92e05d48e68963d89443ccc46474e`，见 `TEXT-EDIT-RELEASE-REVIEW-20260928.md`。功能与发布代码均按凭据提交。
- 关闭入口后 API 与原生 CLI 排空通过；备份完成后迁移0019→0020。数据库dump491271字节且pg_restore --list可读，备份COMPLETE存在。原生51个包兼容检查通过；原生Worker和API Worker就绪（并发5）。API Worker启动初次就绪探测尚未发现节点，按预定重试后成功，未触发回退。
- 五个后端服务逐一验证镜像ID、原环境/命令及300个文件SHA；原生app158文件和前端484文件（含package.json）全部匹配。完整原11层Compose配置保持，末尾追加本次覆盖。容量准入仍关闭。
- schema0020与可空skill_version_id、新builtin_prompt JSON列核对通过；原生Worker active，API暂停解除。ready200，PostgreSQL/Redis/MinIO均up。
- 登录态auth/me、CLI列表、历史CLI详情、API换图列表和壁纸Skill目录均200；空原图文字任务422拒绝且无生成。临时测试会话已撤销，撤销后401；匿名auth/me401。
- 发布前后CLI成功49/失败12/取消2，API成品116，数量一致。发布后五容器及原生服务日志无Traceback/ImportError/ModuleNotFoundError/CRITICAL。未改写历史任务或开启模型调用。
- 公网HTTPS首页及入口JS/CSS均200、哈希与构建一致。独立浏览器实际渲染钉钉登录页，无白屏；唯一控制台401来自预期的匿名auth/me。未使用真实钉钉交互验证登录后画布，画布完整流程证据见本地验收报告。

服务器发布目录 `/opt/hengxin-releases/text-edit-20260928-0ebb3bc`，备份目录 `/opt/hengxin-backups/text-edit-20260928-0ebb3bc`。本地证据在 `output/release/text-edit-20260928-0ebb3bc/`：包审计、安装测试、部署日志、verification.json、auth-smoke.json、runtime-check.json、public-login.png。旧镜像和旧资源仍保留，线上入口为 https://zhitu.qhhengxin.top/ 。

后续维护沿用线上API labels中的完整Compose链，并带末层 `/opt/hengxin-releases/text-edit-20260928-0ebb3bc/api-override.yaml`；不要只用基础compose启动旧镜像。当前发布信息保存在API_RELEASE.json、API_IMAGE_RELEASE.json、FRONTEND_RELEASE.json和TEXT_RELEASE.json。上线后回退须遵守文末约束。

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
