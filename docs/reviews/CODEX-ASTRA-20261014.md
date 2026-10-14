# Codex 0.162.1 / 海外 Astra high 独立审查

- candidateId：`76baf1bcac410f886379be0b2fdf06e800993a80ce86da37e08b1a59012dc695`
- 审查日期：2026-10-14；角色：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH / MEDIUM 阻断问题。
- 本结论批准本轮实现与发布脚本，不代表生产切换已经完成。审查期间未执行生产写入、未修改实现、未提交、未登记批准凭据。
- 范围：Product-Spec.md:1100 的三条需求、Product-Spec-CHANGELOG.md、本轮计划 `docs/OVERSEAS-CODEX-ASTRA-20261014.md`；`hengxin-smart-image/backend/app/overseas/studio/execution.py`、新增模型参数测试、`infra/.env.vps.example`、三个 `scripts/release/overseas-codex-*.py` 和 `test_overseas_codex_deploy.py`。复用发布工具与既有工作台实现作为依赖追踪，不重审项目全部历史功能。
- 开始及结束复核 `review-status` 均为上述 currentId；未发现送审期间代码快照变化。普通 Markdown 报告不进入代码快照。

## Stage 1：Spec Compliance — PASS

| 需求 / 标准 | 实现与验证证据 | 判定 |
|---|---|---|
| 国内、海外指定 CLI 0.162.1；独立目录保留旧版（Spec:1102） | `scripts/release/overseas-codex-prepare.py:12` 固定版本，`:16` 独立 runtime，`:31` 包校验与安装；`overseas-codex-deploy.py:147` 只生成双端 VERSION/BINARY 环境覆盖，`:169` 检查双端实际版本。`output/codex-astra/domestic-smoke.log:1` 记录旧 pin 0.156.1、新 sandbox 0.162.1、私有认证副本及临时目录清理。生产切换结果尚待部署后验证。 | 完整实现 |
| 国内模型保持原样（Spec:1102） | `overseas-codex-deploy.py:72` 国内 drop-in 不覆盖 ExecStart / WorkingDirectory；`:147` 环境只含两个 CLI 版本字段；`:139` 与 `:182` 比较国内源码完整树；`test_overseas_codex_deploy.py:33` 检查无模型覆盖。产品代码差异仅海外 StudioProtocol 参数。 | 完整实现 |
| 海外新会话与续接均显式 gpt-6-astra / high（Spec:1103） | `backend/app/overseas/studio/execution.py:40` 先构造共同 model / effort，再于 `:43` 分支续接；`backend/tests/test_studio_model_selection.py:8` 两种参数化路径均断言模型、推理、sandbox、原始 session ID。真实日志 `output/codex-astra/smoke-pass.json:51` 起的 checks 包含每轮 turn_context，均为 gpt-6-astra / high；source_hash 与本地模块 SHA256 一致。 | 完整实现 |
| 不改图片工具模型、提示词、Skill、会话与任务隔离（Spec:1103） | execution 唯一差异为 `:41` 模型参数；workspace / prepare / publish 逻辑未改（`:20`、`:49`、`:114`）。`backend/app/execution/workspace.py:32` 仍按任务、轮次隔离，`:63` 保留 Bubblewrap；模型测试禁止 `--last`。自行复跑 `test_overseas_studio_conversations.py:16`、`:38` 与 execution/正式交付测试通过；真实烟测 `overseas-codex-smoke.py:52` 保留同一 session 的记忆，`:65` 新 identity 得到独立 session。 | 完整实现 |
| 新旧会话参数、沙箱、事件、图片收取与失败路径先验证（Spec:1104） | `overseas-codex-smoke.py:18` 使用真实 prepare_workspace / sandbox_command / execute / parse_events；`:61` 使用真实 collect_delivery；`:38` 从 CLI session 日志读取模型与 effort。真实 smoke 结果单图 1254×1254、无交付警告、临时文件清理成功。当前 execution.py SHA256 为 `43f8bbde87bdc7a57679284e95dfae70600993ce814b4abb805e2396f84792c8`，与烟测凭据相同。故障回归证据见下节。 | 完整实现 |
| 关闭双端接纳并排空后切换 worker/outbox（Spec:1104） | `overseas-codex-deploy.py:29` 精确关闭双端业务路由，`:44` 验证503，`:155` 停 API；`:156` 先 DB/Celery/broker 连续两次空闲，`:157` 停双端相关 outbox，`:159` 再连续两次空闲才 `:160` 停 native worker。`member-release-drain.py:13` 检查 active/reserved/scheduled、实际队列、各优先级 backlog 和 unacked，`:37` 探测实际运行进程 cwd/env；未知探测抛错。发布故障测试9例通过。 | 完整实现 |
| 实际版本、模型、健康及鉴权检查后完成发布；不改数据库、前端、身份服务（Spec:1104） | `overseas-codex-deploy.py:169` 验证实际双端 CLI 与海外 new/resume 参数；`:179` 验证就绪，`:181` 验证容器及配置拓扑，`:183` 验证双端 schema 不变，`:186` 调用公共健康/匿名鉴权；任何异常 `:192` 重新关闭入口。`member-release-verify.py:129` public 覆盖三端健康与鉴权。没有 migration、前端写入或身份服务重建动作。 | 完整实现；生产验收待执行 |
| 安装完整性、基线模块树、配置 hash（计划:8、:12） | `overseas-codex-prepare.py:37` SHA512 校验下载包，`:49` 拷贝完整 vendor 树与 flat 入口，`:63` 拒绝 runtime 链接；`:78` 固定原 execution 基线，`:87` 比较完整树仅一个模块变化。`overseas-codex-deploy.py:101` 切换前核对新旧源码和 runtime 全树，`:109` 将烟测/测试凭据绑定源码及 runtime，`:115` 配置文件集与 hash 只允许本轮三个 drop-in、两个 env 新增。 | 完整实现 |
| 失败留闭、禁止盲目重放、保留回退材料（计划:12） | `overseas-codex-deploy.py:133` 拒绝已有 DEPLOY_STARTED；`:142` 保存 edge、topology、runtime、unit 原文；`:192` 异常路径关闭入口并记录恢复指引，不自动停未知任务或恢复数据库。`:99` 检测已有同名覆盖。`test_overseas_codex_deploy.py:81`、`:95`、`:110` 证明关键失败行为。 | 完整实现 |

部分实现 / 未实现：无。Spec 漂移：无；新增脚本和测试均服务于本轮明确授权范围。UI / 引导真实性 / 设计稿与邻居页面视觉对比：不适用，本轮未修改页面、组件、文案或静态资源；依据本轮完整 git diff 与计划 `docs/OVERSEAS-CODEX-ASTRA-20261014.md:3`。

## Stage 2：Code Quality — PASS

- 结构与命名：prepare 96行、deploy 204行、smoke 77行，均低于300行；安装、切换、烟测职责独立。入口禁止 Python 优化模式，避免安全 assert 失效（prepare:71、deploy:203）；生产发布故障处理留闭（deploy:192）。
- 测试真实性：新参数测试涵盖真实 new/resume 分支（`backend/tests/test_studio_model_selection.py:8`）；既有回归覆盖原 session 缺失不替换、崩溃不重复启动（`test_overseas_studio_execution.py:141`、`:153`）、越界与跨 session 图片拒收、未完成执行不交付（`test_studio_formal_delivery.py:216`、`:229`）。发布测试实际运行 deploy 并注入排空/启动故障，检查调用次序与入口状态（`scripts/release/test_overseas_codex_deploy.py:81`、`:95`）。真实 Linux 烟测弥补 CLI 参数解析、模型可用性、事件及图片工具的 mock 盲区。
- 安全扫描：本轮三个发布脚本未发现 eval、shell=True、硬编码密钥或拼接用户 SQL；绝对 `/opt`、`/etc/systemd` 路径为明确部署目标。tar 解包使用 `filter='data'` 且预先校验包 SHA512（prepare:37、:42）；配置/故障材料复用 root-only 私有写入（`scripts/release/overseas-runtime.py:26`）。用户 prompt 不进入 shell 字符串（smoke:24）。
- 测试边界：9例发布测试覆盖故障中止，不等同完整真实 cutover；576例镜像测试有3例 skipped，未计为通过。Linux 实测日志由主 Agent 提供到本地，审查者已读取并比对源码hash，未再发收费模型请求。生产双端启动、健康、配置与容器身份的最终结果必须由本轮部署产生。

## 原始验证输出

审查者独立执行发布测试：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_codex_deploy.py -q
.........                                                                [100%]
9 passed in 0.18s
```

审查者在 backend 独立执行模型选择、工作台 execution、正式交付、conversation 回归：

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_model_selection.py tests/test_overseas_studio_execution.py tests/test_studio_formal_delivery.py tests/test_overseas_studio_conversations.py -q
274 passed, 2 warnings in 11.04s
```

两项警告为既有依赖弃用：Starlette `httpx` TestClient 与 anyio `BlockingPortal` alias，非本轮引入。

编译命令及原始输出（编译器成功时无文本，退出码由命令回显）：

```text
python -m py_compile scripts/release/overseas-codex-prepare.py scripts/release/overseas-codex-deploy.py scripts/release/overseas-codex-smoke.py hengxin-smart-image/backend/app/overseas/studio/execution.py
py_compile exit=0
```

```text
git diff --check
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'hengxin-smart-image/backend/app/overseas/studio/execution.py', CRLF will be replaced by LF the next time Git touches it
diff-check exit=0
```

读取主 Agent 提供的真实 Linux 隔离镜像日志 `output/codex-astra/installed-tests.log:20`：

```text
576 passed, 3 skipped, 2 warnings in 64.50s (0:01:04)
```

读取国内真实 sandbox 日志 `output/codex-astra/domestic-smoke.log:1`：

```json
{"old_binary": "/opt/hengxin-runtime/codex-0.156.1/codex", "old_pin": "0.156.1", "sandbox_version": "codex-cli 0.162.1", "auth_copy_private": true, "temp_removed": true}
```

审查者首次误用系统 Python 运行测试得到 `No module named pytest`，随后改用项目 `.venv` 完成上述独立测试；不把首次失败当作测试通过。

后续由主 Agent 以此报告路径对同一 candidateId 登记 `stage1: PASS`、`stage2: PASS`；代码变化必须重新固定快照并复核。
