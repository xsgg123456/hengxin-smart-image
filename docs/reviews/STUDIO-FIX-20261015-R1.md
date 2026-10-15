# 工作台修复独立审查 R1

- candidateId：`af036d9b6998d282605c941967712cc4e59f7fb61818291812ba404c958b0ab8`
- 审查范围：2026-10-15 Spec/DEV-PLAN 所列 Skill 显式触发、搜索事件双 id 兼容、安全错误、受限历史文字恢复及 0.2.35 发布适配；18 个受控变更文件及关联源文档。未把历史全产品业务当作本次变更。
- 方法：读取 code-review skill、完整 diff、新增文件及调用链；独立执行专项与发布测试；读取主 Agent 本轮编译和浏览器日志。
- 结论：**Stage 1 PASS；Stage 2 PASS。未发现本次代码变更新增的 HIGH/MEDIUM 阻断问题。** 这是代码快照审查通过，不代表生产部署或历史恢复已经执行，也不代表 Windows 全后端通过。
- 快照：审查中 `review-status` 返回 currentId 与上述 candidateId 一致。未修改业务代码，未写 `.needs-review`；批准登记由主 Agent 执行。

## Stage 1：Spec Compliance

| 条目 | 结果与证据 |
|---|---|
| 首轮身份后、原文前使用冻结声明 `$name` | 完整实现。`hengxin-smart-image/backend/app/overseas/studio/execution.py:62` 按身份、Skill、原文、附件顺序构造；`app/overseas/execution/materials.py:24` 从已验证安装包设置名称，`app/overseas/management/installed_catalog.py:133` 核对冻结发布与 checksum。专项覆盖首轮/续聊/切换/取消选择、中文展示名与验证名不同的场景。 |
| 无选择不添加；附件原文隔离保持 | 完整实现。`app/overseas/studio/execution.py:51` 仍按既有安全输入路径写附件，`:65` 条件添加 Skill；`app/execution/workspace.py:93` 至 `:104` 保持只读技能发现目录挂载。`tests/test_studio_skill_trigger.py:44` 逐字比较原文与附件内容。没有收费 CLI 调用；本次证明请求与挂载，不声称已执行新生产模型加载。 |
| 只兼容明确 web_search 双 id | 完整实现。`app/execution/event_json.py:25` 限定 root.item、web_search、唯一重复键 id、两个值、item_数字→exec-UUID、三种 item 生命周期事件；其他重复字段拒绝。`:37` 保留末 id，与旧普通 JSON 消费身份相同。`tests/test_cli_event_json.py:13`、`:20` 覆盖许可与拒绝形态；全局 `_unique_object` 未修改。 |
| 正文与结算共用解析，保留完整回复 | 完整实现。`app/execution/events.py:36` 与 `app/overseas/studio/transcript.py:69` 均调用 decode_event；`tests/test_studio_event_compatibility.py:16` 实际走 runner、持久化和 API，验证回复及搜索条目身份。 |
| 成功仍需 exit0、完成、会话、最终回复；失败不转成功 | 完整实现。`app/overseas/execution/runner.py:140` 检查退出/原因及摘要，`app/overseas/studio/execution.py:87` 要求最终回复；`app/execution/events.py:49` 校验会话。专项含非零退出、超时、缺完成、turn.failed、非法事件和会话冲突；中途工具失败后有效完成通过。 |
| 安全错误提示与内部错误码 | 完整实现。`app/overseas/execution/events.py:8` 白名单映射，`:20`、`:26`、`:34` 覆盖事件记录、作业序列化和历史事件读取；未知内容降为通用提示。`runner.py:144` 日志仅 job UUID 与解析器错误码，不输出原始命令/凭据/堆栈。非法事件 API 用例验证 EVENT_STREAM_INVALID。 |
| 历史恢复默认只读，重新验证证据 | 完整实现。`app/overseas/studio/recovery.py:33` 默认 apply=False；`:39` settings.manage 授权；`:42` 锁任务，`:45` 锁作业并核对任务/轮次/会话/payload。`:56` 要求旧通用失败、已退出、一次执行、已关闭派发；`:61` 拒绝其他轮次与图片；`:68` 校验原始 SHA、`:71` exit receipt、`:87` 完成和会话、`:91` 正文/游标、`:97` 全部消息匹配，`:98` 再读确认事件未变。 |
| 恢复原子发布/审计，不重跑、不改完成时间次数 | 完整实现。`recovery.py:36` 单事务包裹校验、`HANDLER.publish`、作业和事件及 Audit 写入（`:102` 至 `:111`）；完成时间和 execution_count 不赋值。`:51` 已恢复相同证据幂等。`tests/test_studio_text_recovery.py:41` 验证默认不写、显式恢复、次数时间不变、只一条审计；`:105` 验证 publish 失败回滚。 |
| 无布局、lxml、消息隐藏、迁移扩张 | 符合。前端仅 `frontend/package.json:3` 版本变化；无 UI 源码、依赖和迁移变更。恢复为内部维护函数，未新增公开 API/表。 |
| 0.2.35，0.2.34/3b09fbc 基线，保留现有发布约束 | 完整实现。`scripts/release/overseas-attachments-deploy.py:15` 目标/基线/日期，`:39` 固定实际发布标识；`:43` 内存、`:47` 99 指针、`:58` 双代理校验；`:81` 保留 retention 包装。`scripts/release/package-overseas.py:189` 仍记录 0028/overseas_0015。独立发布测试验证入口隔离、日期、版本、指针和包内容。 |

上述 `app/`、`tests/` 相对路径均以 `hengxin-smart-image/backend/` 为根。未实现/部分实现条目：无。Spec 漂移：无。

## Stage 2：Code Quality

- 解析兼容集中在 44 行的 event_json 模块，没有复制两套政策；恢复 112 行单一职责模块。改动未新增 any、eval、动态 SQL、前端 HTML 注入或密钥字面量。安全扫描命中为零。证据：`app/execution/event_json.py:10`、`app/overseas/studio/recovery.py:33`。
- 恢复权限使用既有权限锁和重新读取成员的路径；`app/overseas/tasks/service.py:10`、`app/overseas/permissions.py:57`。任务锁与正常发消息路径共享，恢复期间其他轮次插入不能绕过正常任务写锁；正文和审计同事务，不调用模型或对象写入。未发现越权恢复或将其他轮次误恢复的新增路径。
- 测试真实性：事件用生产重复键线格式而非已解码 dict；runner 用例仅替换 CLI 边界，实际存储/序列化参与；Skill 用实际 materials.prepare，安装包验证边界单独替身；恢复用真实模型及事务。未将离线字符串测试描述为收费模型效果验证。证据：`tests/test_cli_event_json.py:9`、`tests/test_studio_event_compatibility.py:16`、`tests/test_studio_skill_trigger.py:20`、`tests/test_studio_text_recovery.py:22`。
- UI 视觉项：本次没有新页面或布局差异，邻居页面数值比较不适用；不是声称独立完成截图对比。读取本轮生产 dist 浏览器验证 `output/studio-fix-browser.log:1`、`output/studio-fix-refresh.log:1`，桌面/390px、正文、状态、刷新和选择保持均 PASS。
- 非阻断文档提示：`docs/STUDIO-SKILL-TRIGGER-TODO-20261015.md:4` 仍保留“尚未实施”的前期状态；最终交付时应同步状态，避免读者误判。本项不影响代码快照批准。

## 独立验证原始输出

命令：backend 虚拟环境运行新增四个测试文件。

```text
...........................................                              [100%]
43 passed, 2 warnings in 6.30s
```

两项 warnings 为既有 Starlette/httpx 与 anyio 弃用提示。

命令：backend 虚拟环境运行 `scripts/release/test_overseas_attachments.py scripts/release/test_package_overseas.py -q`。

```text
................................................ [ 87%]
.......                                                                  [100%]
55 passed, 24 subtests passed in 2.87s
```

本轮主 Agent 编译原始输出（`output/studio-fix-build.log:3`，末行）：

```text
> hengxin-smart-image-frontend@0.2.35 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4723 modules transformed.
✓ built in 46.03s
```

浏览器日志原文：

```text
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
```

## 全量验证限制与发布后续

本轮 Windows 全后端输出（`output/studio-fix-backend-full.log`）：

```text
8 failed, 2210 passed, 314 skipped, 15 warnings in 216.45s (0:03:36)
```

逐项读取失败栈：7 项在未修改的 `app/execution/diagnostics.py:85` 因 POSIX safe open unavailable 失败，1 项在 `tests/test_overseas_pictures_protocol.py:55` 因 Windows 无符号链接权限（WinError 1314）失败；不是本次变更的回归证据，亦不能称全量通过。主 Agent 正另在 Linux 无网络只读挂载环境运行全后端；此报告生成时未取得其完成结论。最终交付仍须附该结果、实际安装产物及生产切换/受限恢复证据。不得用本报告替代发布执行验收。
