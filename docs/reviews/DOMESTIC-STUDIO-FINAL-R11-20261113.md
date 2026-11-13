# 国内 AI 工作台与联合发布独立审查 R11

## 结论与范围

- **candidateId：`9d5e71a6a199ca959d2558cc2a5d19caab0f088c265afd6d104fe7d1781a7a48`；Stage 1：FAIL；Stage 2：未执行。** 联合发布存在一项 HIGH：正式入口和任务接纳在完整身份、源码和台账核验之前恢复，核验失败后也不会自动重新关闭。
- 审查范围为 `Product-Spec.md:1-13` 的国内五工作台、会话、附件、结果、归档、Skills、身份及国内外隔离，`DEV-PLAN.md:1-18` 的联合发布，`Design-Brief.md:1-3` 及用户确认的 `hengxin-smart-image/frontend/preview-domestic-studio/`；另只读审查候选外 `output/domestic-studio-release-bin/`。下文的 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`。
- 本轮开始及结束前 `review-status` 的 `currentId` 均为以上编号、`approved:false`；未观察到受控代码变化。审查只写本报告及 `output/` 下隔离证据，没有连接生产、修改业务代码、提交、批准或写 clean。此前 FINAL 至 R10 的记录用于定位风险，不将旧快照的测试或结论直接记为本候选通过。
- 本次有 HIGH，依据 `.agents/skills/code-review/SKILL.md` 停在 Stage 1。后文“代码已见”是列出的静态证据及有限测试，不代表该条真实环境验收通过。

## Stage 1 · HIGH：完整核验失败后入口和消费者仍处于恢复状态

`DEV-PLAN.md:16-18` 要求排空和备份后迁移，并在实际身份、健康、三组台账、前端和接口确认后恢复接纳。实际调用顺序如下：

1. `scripts/release/intranet/joint_studio_release.py:112-125` 的 `Upgrade.deploy()` 先调用 `engine.apply()`，其成功返回之后才调用 `finish()`。
2. `scripts/release/intranet/engine.py:164-183` 先关闭入口、排空和完成切换，但随后调用 `u.start_apps(ctx)`、恢复凭据 socket 并写 `applied.json`。`hengxin-smart-image/scripts/migration245/unify_release.py:471-509` 的 `start_apps` 会启动原生 worker、API 及 `domestic-web`；`health` 还要求消费者队列已恢复，并请求正式 `192.168.1.245:8080`。
3. **之后**，`scripts/release/intranet/joint_studio_release.py:131-157` 的 `finish()` 才做 `scope_snapshot.capture(..., domestic_publisher=True)` 和台账登记。`scope_snapshot.py:64-105` 会检查国内 Skill/锁的实际身份与挂载、三组运行源码、运行时和正式前端内容；这些检查可以失败。
4. 若 `finish()` 抛错，`joint_studio_release.py:126-129` 只将阶段改为 `forward-required` 并重新抛出；这里没有关闭已恢复的入口或消费者。`joint_studio_marker.py:19-22` 和 `release_cli.py:29-32` 的门禁只阻止其他发布/清理，不是用户请求或队列消费门禁。对未验证身份、挂载或源码的运行态，有可能已接收新业务，不能将它视为安全排空状态。

**隔离复现：** `output/review-r11-release-failure.py:1-92` 的第一项运行真实 `engine.apply()` 和真实 `start_apps` 控制流程，替换所有主机/systemd/Docker 操作为本地替身，使用普通临时文件模拟 socket 权限；第二项运行真实 `Upgrade.deploy()`，以替身模拟刚刚验证的启动结果，在 `scope_snapshot.capture` 注入身份核验失败。结果显示入口、worker 和 socket 替身仍为恢复状态，阶段为 `forward-required`，而发布门禁仍阻止进一步发布。该试验**没有连接生产，也没有启动真实 worker、Docker、业务 API 或 Unix socket**；其证明的是执行路径和故障分支，实际网络可达性不是本次实测。

```text
ENGINE_APPLY_EVENTS ["app stop: ('domestic-web', 'domestic-api', 'overseas-api', 'identity-api')", 'credentials gated', 'workers restarted', "app up: ('domestic-api', 'overseas-api', 'identity-api', 'domestic-api-image-worker', 'domestic-api-image-outbox', 'domestic-image-variants', 'domestic-outbox', 'overseas-skill-publisher')", 'health {}', "app up: ('domestic-web',)", "health {'frontend': True}"]
ENGINE_APPLY_STATE {'entries': True, 'workers': True} credential_mode 0o600 applied_marker True
.UPGRADE_FAILURE_EVENTS ['apply returned with entries/consumers/socket restored', 'capture runtime fails']
UPGRADE_FAILURE_STATE {'web': True, 'workers': True, 'socket': True} phase forward-required migration_pending True release_guard blocked
.
2 passed, 18 deselected in 4.31s
```

日志：`output/review-r11-release-failure.log`。现有 `unify_release.py:398-416` 排空、`engine.py:197-215` 再排空及 `joint_studio_forward.py:33-65` 的前向恢复是可复用基础，但不能推断本故障后已执行它们。`scope_snapshot.py:58-60,96` 当前直接通过正式 8080 检查三路前端；本次未发现该流程提供隔离、只读的替代验收入口。修复应同时解决先核验再恢复接纳的依赖、完成前失败保持关闭、以及已接纳任务时只前向且安全地排空/恢复；修复后必须重新固定快照，从 Stage 1 重审。

## Stage 1 · 逐项对照和未测边界

| 需求 | 本轮证据与状态 |
| --- | --- |
| 两个新品、三个替换、独立一级成品库和超管 Skills | 代码已见：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-30`、`backend/app/modules/domestic_studio/management_router.py:26`。本轮浏览器仅实际操作模拟的相机工作台和成品库；未以真实身份重新测试五入口及超管权限。 |
| 空白对话、无推荐提示或自动发送 | 代码已见：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27` 和 `frontend/src/views/shared/studio/StudioTurns.vue:3`。模拟工作台输入值为空；未穷举其他入口和所有状态。 |
| 各成员、各入口私有会话及新建/切换/重命名/删除 | 代码已见：`backend/app/modules/domestic_studio/conversation_service.py:18-42,70-105`、`queries.py:41-54,68-76` 和 `conversation_deletion.py:15`。本轮没有重跑跨用户 HTTP、并发或删除链，不能据此宣称全量通过。 |
| 真人姓名、发送时间、左右消息、北京时间 | 代码已见：`backend/app/modules/domestic_studio/queries.py:22-25,74-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；本轮仅使用模拟姓名与时间，没有真实用户验收。 |
| 附件、续聊、结果、图片修改、停止和异常 | 代码已见：`DomesticWorkspace.vue:15-36,81-105`、`backend/app/modules/domestic_studio/turn_service.py:42-116`，复用共享输入和图片编辑组件。本轮没有独立重跑真实执行、标注、停止及全部故障路径。 |
| 部分结果保留、手动取回、未知进程在原节点核实且不重新生成 | 代码已见：`backend/app/modules/domestic_studio/runner.py:23-38,66-83`、`recovery.py:39-65`；浏览器以模拟 API 打开取回对话框，不代表实际文件取回或故障恢复已验证。 |
| 远端写入不明时保留凭据、不重复写同一对象；大附件有界 | 代码已见：`backend/app/modules/domestic_studio/file_service.py:29-70`、`output_intents.py:13-61`、`archive_service.py:214-260`。R10 的 45+21 项隔离测试是旧快照历史证据；本轮未重跑真实 MinIO、128 MiB、迟到写或并发 RSS。 |
| 五个入口教程、无正式内容时待补充 | `DomesticWorkspace.vue:3,33` 以工作台标题显示教程抽屉和待补充；本轮未逐一打开五入口。 |
| 仅新品按名称归档，替换服务端拒绝 | `backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:124-125` 限定范围；`DomesticWorkspace.vue:15,62-64` 仅新品展示入口。浏览器打开归档框但没有向真实服务器提交。 |
| 归档独立副本、所有国内成员可看，源会话仍私人且删源后保留 | `archive_service.py:38-53,164-207,214-260`、`archive_queries.py:59-70`、`conversation_cleanup.py:44-56` 提供复制、校验和清理路径；本轮未重跑跨成员、删源和异常故障注入。 |
| 归档过程、终态、逐图修改、搜索、来源、详情、删除及 ZIP | `archive_service.py:172-207`、`archive_edits.py:8-38`、`archive_queries.py:33-54`、`archive_router.py:36-98`、`frontend/src/views/hengxin/domestic-studio/library.vue:11,37-46` 有对应实现；本轮未重跑这些真实 HTTP 和存储场景。 |
| 超管 Skill 文件夹、校验、同名更新、启停、删除、ZIP、无版本管理和在线编辑器 | `management_router.py:26,77-163`、`frontend/src/views/hengxin/admin/skills.vue:3-7`、`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27` 和 `SkillFolderActions.vue:3-6,38-39` 显示管理及复用路径；本轮未实操真实文件夹或 ZIP，也未完整盘点所有页面/API 漂移。 |
| 五入口固定绑定、初始为空、用户不能绕过、已提交冻结、绑定中禁删停 | `backend/migrations/versions/0033_domestic_studio_bindings.py:10-26`、`bindings.py:30-82`、`policy.py:33-51`、`turn_service.py:42-80` 有相应路径；本轮未重跑权限、竞争或真实 Skill。 |
| 国内外身份、库、对象与队列隔离，共享海外逻辑及既有功能保持 | `backend/app/modules/domestic_studio/router.py:28-29`、`recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114` 可见隔离和接线意图；未重跑全旧业务、真实登录或实际双业务部署，不能断言完全隔离。 |
| 0032→0043、排空、备份、迁移后前向恢复 | `joint_studio_engine.py:18-52,141-157`、`joint_studio_fence.py:26-60`、`joint_studio_packages.py:11-51` 和 `joint_studio_release.py:160-198` 有迁移、锁和前向恢复逻辑；**完整联合发布不通过本报告 HIGH**。本轮故障测试为隔离替身，未演练真实数据库恢复或生产切换。 |
| 构建、测试、两阶段审查、中文提交及内网正式验收 | 本轮类型检查及国内 Vite 生产构建退出码 0，原始输出见下；未独立重跑前端 564 项、后端全量、真实 Skill/模型、安装、提交或部署。Stage 1 FAIL，不能登记两阶段 PASS，也不能宣称交付或上线。 |

## R10 移动布局复核

在本地 Vite `3053` 和用户确认预览 `3025`，以本 reviewer 的 `output/review-r11-browser.js` 注入模拟 API，打开实际浏览器比较，结果在 `output/review-r11-browser.log`：

| 宽度 | 预览/正式会话头高度 | 预览/正式工具栏高度 | 状态与标题 | 工具按钮及输入按钮 |
| --- | --- | --- | --- | --- |
| 320 | 81 / 81 px | 105 / 105 px | 隐藏；14 / 14 px | 同位置、宽高、字号、图标数 |
| 489 | 81 / 81 px | 61 / 61 px | 隐藏；14 / 14 px | 同上 |
| 490 | 61.5 / 61.5 px | 61 / 61 px | 隐藏；14 / 14 px | 同上 |
| 799 | 54 / 54 px | 69 / 69 px | 显示；15 / 15 px | 同上 |
| 800 | 54 / 54 px | 69 / 69 px | 显示；15 / 15 px | 同上 |
| 1920 | 54 / 54 px | 69 / 69 px | 显示；15 / 15 px | 同上 |

在 320、490、799 px 的模拟已完成状态，正式页依次实际点击并打开取回、归档框，导航到成品库；没有测试这些操作的真实后端写入。截图 `output/review-r11-preview-490.png`、`output/review-r11-formal-490.png`。确认预览的演示用户、演示数据和脚注未作为正式需求。该局部复测不构成整个 UI 的两阶段通过。

## 候选外发布辅助脚本 · 只读审查及限制

- `output/domestic-studio-release-bin/build_committed.py:12-42` 取得 HEAD 并核对三个包的 scope、清单及摘要；`scripts/release/intranet/package_release.py:68-115` 用 Git tree/blob 检查构建源。脚本只取 **当前 HEAD**，不自行证明 HEAD 已对应经批准的候选。当前 HEAD 为 `979e099b63cba11cad4bd5c2f057e263a4ef8193`，尚不含本候选未提交代码；**不得现在打包部署**。修复并重新两阶段通过后，提交并核对 HEAD、审查凭据、提交内容、包清单和各工具版本一致，才能继续。
- `install_committed.py:17-50,54-76` 从 HEAD 的 Git blob 核对 Python 文件并写入版本目录；`run_server_helper.py:19-39`、`server_verify_tools.py:10-37` 和 `server_verify_candidate.py:10-38` 检查提交、主机、目录与摘要。`hengxin-smart-image/scripts/migration245/transport.py:15-27` 使用已知主机密钥和主机名校验。
- `server_installed_checks.py:20-43` 对隔离目录运行测试；`server_publisher_smoke.py:22-101` 使用无网络、只读容器和随机标识清理其测试对象。`server_activate_tools.py:27-57` 使用发布锁、空闲台账、运行状态对照和受管链接；`upload_and_stage.py:42-65` 校验本地和远端包摘要后暂存。上述均为静态核查，不是本轮实际安装、激活、上传或生产安全验证；未执行脚本，不能声称无误触的全部故障路径已测试。
- 这些辅助脚本位于 `output/`、不在 candidateId 受控快照内；实际使用前需重新核对其内容及摘要，并由主 Agent 对提交后的版本和运行时接线负责，不能用本报告把候选外文件自动视作批准。

## 本轮构建与类型检查原始输出

前端类型检查 `pnpm run typecheck`，退出码 0：

```text
> hengxin-smart-image-frontend@0.2.70 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

国内范围 `VITE_RELEASE_SCOPE=domestic pnpm exec vite build --mode production --outDir ../../output/review-r11-domestic-dist --logLevel warn`，退出码 0；此为工作区构建，并非审查通过后的 Git 制品：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r11-domestic-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.

[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
```

本轮未独立运行海外范围构建或本候选后端全量；R10 的定向结果和主 Agent 报告的前端回归不能替代这些未运行项。
