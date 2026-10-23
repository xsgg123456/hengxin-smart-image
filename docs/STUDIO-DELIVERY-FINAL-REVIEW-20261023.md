# 海外正式图片交付与漏收恢复：独立两阶段复审

## 审查结论与快照

- 最终 candidateId：`ad0ae03ab93121c235ac5cd119b0e792a338a799ba8b6217ea0fa09b4afaab8c`。
- Stage 1（Spec Compliance）：**PASS**。初审 HIGH H1 已修复；本次未发现未修复的需求实现缺陷。
- Stage 2（Code Quality）：**PASS**。本次范围内未发现需要阻断发布的质量或安全问题。
- 结论是上述代码快照的两阶段审查结果，**不是生产发布、指定图片恢复或页面验收已经完成的声明**。主 Agent 仍需完成发布计划的操作验收，并用 `review-approve` 登记同一快照；本 reviewer 未登记凭据、未写 `.needs-review`、未修改业务代码、未提交。
- 初始送审编号为 `7751d86eeaaf6db4914daf1cd995465c716ee3ad2d225ed8c36cb286971fab12`，开始时 `review-status.currentId` 匹配。审查期间新增 `test_overseas_credentials.py` 修订后重新 prepare，当前编号变为上述 `ad0ae…`。已读取新差异并独立重跑认证测试，旧编号结论不覆盖新内容。

## 审查范围与依据

依据：`Product-Spec.md:1322` 的本轮完整章节、`docs/STUDIO-DELIVERY-FIX-20261023.md:1` 的七项计划、初审报告 `docs/STUDIO-DELIVERY-REVIEW-20261023.md:1`、code-review skill 及 `docs/HARNESS-REVIEW.md`。

本报告中 `studio/` 指 `hengxin-smart-image/backend/app/overseas/studio/`，`tests/` 指 `hengxin-smart-image/backend/tests/`，`release/` 指 `scripts/release/`。

范围包括新增 `studio/{native_rollout,native_images,delivery_evidence,image_recovery}.py`，修改的 `studio/{delivery,execution}.py`，新增三个业务专项测试、修改的执行与认证测试，两个发布脚本及发布测试。`AGENTS.md:150` 是用户预存的内容修订路由规则，已读差异；不归为本轮新增业务功能。普通文档同步已查阅。

Markdown 兼容边界：主 Agent 明确并已在 `docs/STUDIO-DELIVERY-FIX-20261023.md:15` 记录，本轮双重原生证据用于“无 Markdown 原生公开展示”及“放宽历史 native baseline 的明确补交”；已有本轮 Markdown 正式交付保留原有文件、归属、baseline 门禁。`studio/delivery.py:167` 对已证明 native 图再核原字节，普通 work 图继续在 `:177` 检查本轮变化。此审查没有将新增桥接解释为取消既有 Markdown 入口。

## Stage 1：逐条对照

| Spec / 计划要求 | 结论 | 证据与验证 |
| --- | --- | --- |
| 首轮无 Markdown，接收原生公开图片 | 完整实现 | `studio/native_images.py:70` 读取完成的 generation，`:88` 读取公开 image 输出，`:113` 取哈希交集；`studio/delivery.py:160` 桥接。`tests/test_studio_delivery_bridge.py:41` 使用真实可解码 PNG，断言字节和宽度。 |
| 同会话、同轮次、最终回复、完成事件一致 | 完整实现 | `studio/native_rollout.py:67` 校验 session_meta；`studio/native_images.py:60`、`:71`、`:96`、`:106` 校验 session/turn/final；`:191` 限定一个追加完成轮且与 CLI 最终正文一致。`studio/execution.py:57` 在执行前固定 cursor，`app/overseas/execution/runner.py:141` 解析时绑定 previous_session。 |
| 生成字节、公开展示字节、最终文件一致 | 完整实现 | `studio/native_images.py:12`、`:75`、`:102`、`:115` 计算和关联 SHA256；`studio/delivery.py:175` 对实际通过图像解码的文件复核。`tests/test_studio_native_images.py:91`、bridge `:88` 验证展示不匹配及文件被改写拒绝。 |
| 多图 | 完整实现 | `studio/native_images.py:54`、`:76`、`:113` 收集多张，最多 100 张；bridge `:114` 用蓝、绿两张不同尺寸真实 PNG，断言两张均收取。 |
| 只生成未展示的过程图不收 | 完整实现 | `studio/native_images.py:115` 必须有公开相同字节；native tests `:80` 拒绝未展示及其他工具输出；bridge `:100` 验证文字称生成而无公开图时有提示。 |
| 草稿、否定交付不收 | 完整实现 | `studio/delivery.py:76`、`:87`、`:160` 复用负面与分区门禁；`studio/native_images.py:213` 处理历史无清单情况；bridge `:51`、native tests `:238` 覆盖中英文负面。 |
| 失败、取消、停止、未完成轮不收 | 完整实现 | `studio/native_images.py:141`、`:154`、`:179` 拒绝当前失败/截断；历史只跳过已失败轮，不把其图当成功输出；真实 runner 在 `app/overseas/execution/runner.py:142` 核验进程退出和终止原因后才进入收图，`:164` 仍需有效 lease 的 finish 才发布。native tests `:116`、`:222`；认证测试 `tests/test_overseas_credentials.py:51` 通过真实 runner 错误分支验证无图发布。 |
| 最终显式清单优先，历史亦一致 | 完整实现；初审 H1 已关闭 | `studio/delivery.py:157` 优先显式清单；修复后的 `studio/native_images.py:211` 先调用同一个 `references`，`:217` 拒绝原 final 清单外图；无清单才在 `:213` 整体排除草稿。native tests `:65` 覆盖清单外拒绝、清单内接受、外链清单、草稿/正式章节混合。正常补交和维护入口分别经 `delivery_evidence.py:29`、`image_recovery.py:82` 共用此门禁。 |
| 同会话明确补交旧 native，来源及原字节可核验 | 完整实现 | `studio/delivery_evidence.py:20` 限定同 session 显式旧路径；`studio/native_images.py:201` 只返回成功正式交付证明；`studio/delivery.py:168` 仅对 proof 放宽 baseline，`:175` 校验字节。bridge `:64`、`:106` 验证可补交与无证据拒绝。 |
| 跨会话、输入、Skill、无来源旧文件拒绝 | 完整实现 | `studio/native_images.py:24` 限定 session PNG 路径；`app/execution/final_delivery.py:45` 保留 native/work 边界、输入与 Skill 保护；native tests `:116` 有跨 session/turn、越界拒绝。未修改国内收图协议。 |
| 相同来源与内容不重复新增、计数、归档 | 完整实现 | `studio/execution.py:40` 读取同会话已收 Picture；`studio/delivery.py:182` 去重；`studio/image_recovery.py:98`、`:134`、`:153` 维护幂等。bridge `:64`、`:114` 及 recovery tests `:81`、`:207` 验证；本轮无自动归档调用。 |
| work 图片保持本轮新增/变更门禁；已有 Markdown 兼容 | 完整实现 | `studio/delivery.py:177` 保留 `check_work_version`；bridge `:78` 验证旧 work 被拒绝，`:56` 验证显式 work 清单优先。`tests/test_overseas_studio_execution.py:106` 走 runner 验证多张 Markdown 图片。 |
| 解析异常、文件校验失败保留文字与提示 | 完整实现 | `studio/delivery_evidence.py:7`、`:17` 固定提示且不泄露原始异常；`studio/delivery.py:185`、`:190` 区分旧图无证据及称生成未交付；bridge `:88` 与执行 validate 的 reply 保留。 |
| 存储失败不丢文字，不伪装成功；可补交 | 完整实现 | `studio/execution.py:124` 单图捕获存储错误，`:137` 给出补收提示。bridge `:114` 真实两图、第二图上传失败、下一轮只补失败图，并断言最终无重复上传。 |
| 不扫描输出目录猜测交付 | 完整实现 | `studio/native_rollout.py:19` 只定位指定 session rollout；`studio/native_images.py:70`、`:88` 只消费显式事件；输出文件仅由证明或 final 引用选取。既有 baseline 目录快照不用于发现交付。 |
| 维护入口受限，绑定任务/会话/轮次/成功退出 | 完整实现 | `studio/image_recovery.py:30` 调用权限锁与 settings.manage，`:41`、`:44` 校验归属，`:46`、`:51` 核验成功退出和 outbox；`:64` 校验指定 events SHA256，`:65` 核验 exit receipt，`:70` 至 `:78` 对照数据库正文/会话/cursor/result。recovery tests `:112` 覆盖权限、状态、归属及证据失败。 |
| 维护原图哈希、图像有效性和原事件稳定 | 完整实现 | `studio/image_recovery.py:82` 至 `:94` 验证原成功公开交付、真实文件哈希、解码及 events 二次读取；`:149` 在第二事务重验。recovery tests `:219`、`:247` 验证证据/图片变化及伪 PNG 拒绝。 |
| 排空、暂停、删除竞态保护 | 完整实现；真实 PG 并发未实测 | `studio/image_recovery.py:36` Task 锁→`:39` Gate→`:40` Job，与 `app/overseas/tasks/deletion.py:33`、`app/overseas/execution/claims.py:100` 相容；两事务都检查删除、暂停、排队和活动任务。recovery tests `:187` 证明事务间删除/排队/解暂停阻止写入。 |
| 持久存储台账，上传或数据库失败可重试 | 完整实现 | `studio/image_recovery.py:124` 第一事务提交 ExecutionObject，`:147` 第二事务复查，`:167` 锁内写对象；`:111` 确定性 ID/object key。recovery tests `:160`、`:174`、`:219` 覆盖失败台账、上传后 DB 回滚及台账丢失；不产生无台账的新对象。 |
| 幂等补入图片与执行结果，记录审计 | 完整实现 | `studio/image_recovery.py:168`、`:175`、`:177`、`:179` 同事务写 Picture/result/event/audit；recovery tests `:81` 断言重复调用只有一张图、一个对象、一条审计。 |
| 保留用户原话、会话、次数、时间；不重跑、不归档 | 完整实现 | 维护写入限定在 `studio/image_recovery.py:168` 至 `:180`，未赋值用户文字/session/execution_count/started_at/completed_at，无模型/归档入口。recovery tests `:81` 对照原执行三项值，检查任务仍 studio。 |
| 证据截断、重复字段、读取大小限制 | 完整实现 | `studio/native_rollout.py:9`、`:37`、`:46`：单行 64 MiB、累计 512 MiB、重复 JSON 字段/无换行/非对象拒绝；`:102` cursor 身份与边界检查。native tests `:124`、`:183`、`:195`、`:209` 覆盖限制。 |
| 链接、硬链接、越界 | 完整实现；本机符号链接测试跳过 | `studio/native_rollout.py:21`、`:99` 复用 `studio/context_fs.py:27`、`:70` 的逐级无链接、安全 fd 和读取前后身份核验；图片复用安全 reader。native tests `:164`、`:171` 和 recovery tests `:239`。Windows 未授权创建 symlink 的跳过不记为通过。 |
| 当前生产基线增量，仅海外执行服务 | 完整实现 | `release/studio_delivery_runtime.py:16` 文件 allowlist，`:72` baseline 哈希、`:78` 全保留树校验；`release/studio-delivery-deploy.py:18` 读取真实 cwd/argv，`:27` 复制旧目录。`:105`、`:120` 仅 stop/start 指定海外 worker。 |
| 保留权限、Skill、国内、模型、提示词，无迁移 | 差异符合 | `release/studio_delivery_runtime.py:141` 仅改 WorkingDirectory/ExecStart 路径；`studio/execution.py:61` 与 `:70` 模型参数和提示词未改；allowlist 不包含权限/Skill/国内/迁移。拓扑守卫见 runtime `:149`、deploy `:156`。 |
| 安装测试回执、排空、备份、验收后才恢复接纳 | 完整实现；实际操作验收另列 | `release/studio-delivery-deploy.py:65` 校验安装测试与 manifest 绑定；`:88` 至 `:108` 暂停排空、停止并备份；runtime `:200` dump 与 restore --list；deploy `:162` 恢复需验收回执并保持原 gate 值。发布 tests `:108`、`:142`、`:155`、`:181`、`:193`。 |
| 指定原 PNG 补回原任务，页面预览/下载/可归档 | 代码入口具备；生产验收未由 reviewer 执行 | 目标 task/turn/SHA 位于 `docs/STUDIO-DELIVERY-FIX-20261023.md:9`，受限入口见 `studio/image_recovery.py:120`。本 reviewer 未连接生产或进行页面操作；不得用本报告宣称该目标已完成。 |

### UI 一致性、引导真实性与 Spec 漂移

- 无新增页面、组件、样式、公开 API 或数据表。`git diff` 及新增文件范围均为后台接收/维护/发布及测试，因此无新页面需要与设计稿或邻居页作视觉对比。没有将代码静态审查当作视觉验收。
- 新增提示“联系管理员补收，无需重新生成”有 `studio/image_recovery.py:120` 受限维护入口和 `studio/delivery_evidence.py:29` 正常明确补交支持。提示未承诺自动重试、自动归档或自动重跑。
- 没有发现本轮范围外功能漂移。维护入口复用既有 ExecutionObject 与 Audit（`studio/image_recovery.py:17`、`:23`），未新增迁移或权限页面。

## Stage 2：质量、安全与测试真实性

| 项目 | 结论与证据 |
| --- | --- |
| 结构与体量 | 新增生产模块分别 33、116、181、222 行，发布脚本 206、211 行；修改的 delivery 195 行、execution 158 行，专项测试亦均少于 300 行。职责分为 rollout 读取、原生证据、桥接、维护事务、发布执行与系统操作。无新增 `Any`/动态 eval。证据：上述模块完整读取与行数检查。 |
| 错误处理 | `studio/delivery_evidence.py:17` 固定安全警告，`studio/execution.py:136` 单图存储失败保留其他成功图与正文；维护异常抛出回滚，第一事务台账保留（`image_recovery.py:146`）；发布失败写私有 phase/attention，不盲目再次切换（deploy `:80`、`:195`）。 |
| 并发与事务 | 维护两个事务均重新取权限、Task/Gate/Job 锁并重新验证证据，上传时持 Task 锁与删除互斥；确定性 object key 防止重试散落对象。对照既有删除与业务 publish 锁序未发现新增锁序倒置。**这些是代码证据；SQLite 测试不证明 PostgreSQL 真正阻塞、死锁或并发时序已测。** |
| 文件与数据安全 | rollout 的 JSON 重复字段、大小、cursor、文件身份、链接限制；图像统一 validate_image，proof 哈希核验。维护只从受限执行根和同会话原生路径读取，不依据调用方传来的任意路径。见 `native_rollout.py:46`、`:93`，`native_images.py:24`，`image_recovery.py:58`。 |
| 密钥/注入扫描 | 对新生产模块和发布脚本检索 `eval(`、HTML 注入入口、前端密钥前缀、硬编码口令、OpenAI/Anthropic 密钥模式，无命中；人工检查 `studio_delivery_runtime.py:33` 使用 subprocess 参数数组无 shell，`:145` 限制 systemd argv，`:58` 限制清单路径与哈希，`:175` 生成的 gate 代码仅用固定 action 和严格布尔值。绝对路径是本机部署/沙箱协议边界，不包含凭据。 |
| 发布恢复健壮性 | `studio-delivery-deploy.py:80` 拒绝重复 switch，`:103` 排空后再核 worker 身份，`:110` 切换前重验来源/安装内容，`:126` 核进程 cwd/argv/PID、Celery 队列和 API 健康，`:162` 验收前不恢复接纳。失败后的恢复是私有 `RECOVERY.md` 指令及主 Agent 人工核实流程，脚本没有自动回滚或自动恢复数据库；不能把“留下恢复指引”称为“已验证回滚”。 |
| 测试真实性 | native parser 夹具故意只有 PNG 签名，用于解析器哈希关联；bridge 和 recovery 改用 Pillow 真图并经实际 validate_image，后者连真实 SQLAlchemy 模型和事务。桥接存储失败用例两张字节不同，确实第二张失败而第一张保留。维护测试含上传成功后 DB 异常，非只测纯函数。 |
| 认证测试变更 | `tests/test_overseas_credentials.py:121` 保存合法 rollout 原始 bytes，`:136` 认证拒绝后比较原始 bytes；原有禁止 dispatch、错误分类和 session 不变断言在 `:126`、`:132` 保留。此改动修正旧 `'{}'` 假夹具假设，没有删除关键断言，独立 18 项通过。 |
| 测试盲区 | Windows 两个符号链接用例跳过；本 reviewer 未执行 Linux/PG/生产页面测试。发布测试 mock 系统调用证明控制流，不代替真实 systemd 切换、备份恢复和原图预览。未执行的能力均不写成通过。 |

## reviewer 独立运行证据

### 业务专项

工作目录：`hengxin-smart-image/backend`。业务代码在初始 candidate 与最终 candidate 之间未改动；期间唯一新增代码差异为下列另测的认证断言。

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_native_images.py tests/test_studio_delivery_bridge.py tests/test_studio_image_recovery.py tests/test_overseas_studio_execution.py -q
............................s........................................... [ 67%]
..................................                                      [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
106 passed, 1 skipped, 2 warnings in 21.49s
exit_code: 0
```

### 发布专项

工作目录：仓库根目录。

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_studio_delivery_deploy.py -q
.........s..........................                                     [100%]
35 passed, 1 skipped in 0.55s
exit_code: 0
```

### 新 candidate 认证测试

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_credentials.py -q
..................                                                       [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
18 passed, 2 warnings in 7.16s
exit_code: 0
```

### 编译及差异检查原始输出

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m compileall -q hengxin-smart-image/backend/app/overseas/studio/delivery.py hengxin-smart-image/backend/app/overseas/studio/delivery_evidence.py hengxin-smart-image/backend/app/overseas/studio/execution.py hengxin-smart-image/backend/app/overseas/studio/image_recovery.py hengxin-smart-image/backend/app/overseas/studio/native_images.py hengxin-smart-image/backend/app/overseas/studio/native_rollout.py scripts/release/studio-delivery-deploy.py scripts/release/studio_delivery_runtime.py hengxin-smart-image/backend/tests/test_overseas_credentials.py
stdout: <empty>
stderr: <empty>
exit_code: 0

git diff --check
warning: in the working copy of 'AGENTS.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
exit_code: 0
```

编译检查与认证测试针对最终工作区；两条依赖弃用警告没有被静默省略，亦未因此扩大依赖升级范围。

## 交付边界

主 Agent 提供的 Windows 更大范围回归、前端 typecheck、Linux 实际安装目录回归与真实 rollout 只读重放，不冒充为 reviewer 亲自执行。实际服务切换、数据库及目标原图备份、指定 PNG 补收、正式页面预览/下载/可归档、二次恢复幂等与恢复接纳后健康，仍按 `docs/STUDIO-DELIVERY-FIX-20261023.md:5` 至 `:9` 留操作证据。特别是代码审查 PASS 不授予“生产已经完成”结论。
