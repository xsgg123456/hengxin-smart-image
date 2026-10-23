# 无 Markdown 历史原生图片补收：独立增量审查

- candidateId：`6277f3a553dd9f6e4a0b07f8d9020df18b1ab47dc1a735d4a36b368662c54080`。
- 上一批准：`ede03b314995060169e2f6ae7a67991e11308983d6476bd2c8b90a03856d6fb4`。
- Stage 1（Spec Compliance）：**PASS**。
- Stage 2（Code Quality）：**PASS**。
- HIGH / MEDIUM / LOW 缺陷：未发现。

## 范围与快照

本次仅审查 `hengxin-smart-image/backend/app/overseas/studio/image_recovery.py` 的新增无链接分支及 `hengxin-smart-image/backend/tests/test_studio_native_recovery.py`。下文 `studio/`、`tests/` 分别指该 backend 下 `app/overseas/studio/`、`tests/`。

依据：`Product-Spec.md:1322` 本轮完整章节，新增合同在 `:1330`；code-review skill；`docs/HARNESS-REVIEW.md`。逐行读取两个变更文件及 `delivery.py`、`delivery_evidence.py`、`native_images.py`、`native_rollout.py`，并读取既有 recovery 测试及两份前序报告。

审查开始、测试后 `review-status` 均显示同一 candidate，changedFiles 仅上述两个文件。另独立读取 Git 暂存版 image_recovery，按快照规则归一 CRLF 后计算 SHA256，与上一批准文件摘要精确匹配。因此 `git diff -- image_recovery.py` 展示的 import、单业务轮约束、原生无链接收集分支确为相对已批准版本的全部生产差异，未误审暂存旧版本。测试文件是本候选新增文件。既有业务/发布模块及用户 AGENTS.md 改动与上一批准快照一致。

完整业务审查承接 `docs/STUDIO-DELIVERY-FINAL-REVIEW-20261023.md:23`，发布时序增量承接 `docs/STUDIO-DELIVERY-RECEIPT-REVIEW-20261023.md:19`；本报告不重新批准其他版本。未修代码、未提交、未登记批准、未写 `.needs-review`。

## Stage 1：Spec Compliance

| 要求 | 结论和证据 |
| --- | --- |
| 历史成功回复无 Markdown 也可补收 | 完整实现。`studio/image_recovery.py:83` 构造受限 workspace，`:87` 调用正式 `collect_delivery`；成功必须有输出且无任何警告（`:89`）。`tests/test_studio_native_recovery.py:39` 真正调用 recover，dry-run 后 apply 成功，保留原文。 |
| 业务会话只有指定一轮 | 完整实现。`image_recovery.py:44` 查询同 Conversation 最多两条 Turn，结果必须为指定 Turn 唯一 ID；两事务均经 `_locked`（`:138`、`:161`）。测试 `test_studio_native_recovery.py:57` 把第二个业务 Turn 移回同会话，断言无 Picture/台账写入。 |
| 原生记录只有唯一成功轮，最终文字完全相同 | 完整实现。`image_recovery.py:86` 明确传空 cursor，从记录起点核验；`delivery_evidence.py:15` 调用 `read_current`，`native_images.py:191` 遍历全部轮次，`:193` 拒绝第二个完成轮或正文不等，`:196` 拒绝无完成轮。测试 `test_studio_native_recovery.py:62`、`:65` 覆盖多原生轮和正文不符。 |
| 任务、会话、Turn、Job 和实际成功退出绑定 | 完整保持。`image_recovery.py:36` 至 `:55` 校验任务状态、会话和 payload 归属、Job 成功/退出/取消/lease/outbox；`:67` 核对 events SHA256，`:68` 至 `:81` 校验 exit receipt、最终正文、session、数据库游标和 result。既有 `tests/test_studio_image_recovery.py:112` 参数化覆盖失败、取消、错误归属与权限。 |
| 生成、公开呈现和文件三者内容一致，不能跨会话 | 完整实现。`native_rollout.py:67` 绑定 session_meta；`native_images.py:71` 要求 generation 的 thread/turn 明确匹配，`:96` 绑定公开输出 turn，`:113` 仅返回公开哈希与生成哈希交集。`delivery.py:175` 再比对实际解码文件哈希；`image_recovery.py:88` 限定本 session 原生目录。新测试 `:79`、`:82`、`:84` 分别覆盖未呈现、文件损坏、会话不符。 |
| 多轮无法绑定、草稿/否定、失败/停止/未完成一律拒绝 | 完整实现。`delivery.py:160` 复用原有 non_delivery；`native_images.py:141` 拒绝失败事件，`:106` 拒绝失败完成，`:179` 拒绝未闭合轮；`image_recovery.py:89` 把空输出与警告都变为维护失败。新测试 `:65` 至 `:78` 同步修改数据库/CLI/native 的草稿正文，确实到达草稿门禁，`:81`、`:83` 覆盖截断/失败。既有 native tests `:116` 覆盖取消等错误事件。 |
| 原证据稳定，事务间再次校验 | 完整保持并覆盖新分支。`image_recovery.py:91` 再读 events 并与原 raw 等值比较；`:162` 第二事务再次完整取证，`:163` 比对两次来源与 checksum 字典。`tests/test_studio_image_recovery.py:219` 验证 events、image、ledger 事务间变更阻止存储。Python comprehension 在 `:89` 的 path 为局部变量，不覆盖 `:65` 的 events 路径。 |
| 排空、删除保护、持久台账、幂等、审计 | 完整保持。`image_recovery.py:38` 至 `:54` 拒绝删除和未暂停/未排空；`:111` 同会话来源+哈希去重；`:149` 至 `:159` 第一事务持久登记台账，`:176` 再验台账，`:180` 至 `:193` 同事务写 Picture/result/event/audit。新成功测试 `:43` 至 `:45` 重复恢复只有一图一台账；既有 recovery tests `:160`、`:174`、`:187` 覆盖存储失败、DB 回滚和状态竞态。 |
| 保留原话/session/次数/时间，不改回复制造链接，不重跑模型、不自动归档 | 完整实现。新增分支 `image_recovery.py:83` 至 `:92` 只读取；写入仍限定在 `:180` 至 `:193` 的图片、deliveryError、result、版本、事件和审计。新测试 `test_studio_native_recovery.py:48`、`:49` 验证原文/次数；既有 recovery tests `:81` 比较原执行时间并核验 task 仍为 studio。无 CLI 或归档调用。 |
| 显式 Markdown 补交语义保持 | 完整保持。新增分支仅在 `not links` 时运行；`image_recovery.py:93` 至 `:108` 原证明路径不变。既有 recovery 测试全部重跑，覆盖正式显式引用、历史去重、无来源和错误引用拒绝。 |
| 正常首轮/多图/续聊、显式清单优先、重复补交、work 新增门禁、错误提示 | 本增量未改正常执行路径。`delivery.py:157`、`:177`、`:182`、`:185` 仍分别控制清单、work 变化、去重与提示；`tests/test_studio_delivery_bridge.py:41` 至 `:114` 本次独立重跑，含两张不同内容真图、部分存储失败和明确补交。 |
| 不扫输出猜交付；证据大小、链接/硬链接/越界保护 | 完整保持。`native_rollout.py:19` 仅定位指定 rollout，`:46` 有单行/总量限制，`:99` 使用安全 reader；`native_images.py:24` 限定标准 session PNG 路径；`delivery.py:168`、`:173` 复用路径边界和安全读取。native tests `:124`、`:152`、`:164`、`:195` 重跑；Windows 符号链接一项跳过，不能算已验证。 |
| 保持国内、权限授权、Skill 配置、模型/提示词，无迁移 | 差异符合。全部生产改动仅为 `image_recovery.py:26`、`:44` 至 `:46`、`:83` 至 `:92`，没有修改服务模块、公开 API、数据库结构或前端。维护权限仍由 `:33` 的 settings.manage 校验。 |
| 安装验证、指定“123”任务补收、浏览器预览下载、恢复接纳 | 代码具备入口；现场验收待执行，不纳入已验证结论。受限操作入口为 `image_recovery.py:133`，默认 dry-run。主 Agent 拟独立安装维护模块、绑定摘要且不改已上线 worker manifest，是操作计划；本 reviewer 未连接生产，未验证该安装或目标恢复结果。 |

完整实现：本次无链接受限补收及已有门禁保持。部分实现、未实现：本次代码范围未发现。UI 一致性/引导真实性/邻居页面视觉比较不适用：本增量没有页面、样式、提示或组件变更（生产差异仅上述三处），不把静态审查当作页面验收。未发现 Spec 漂移；新增能力有 `Product-Spec.md:1330` 明确约定。

## Stage 2：Code Quality

- 结构：维护模块 194 行，新增测试 88 行，均小于 300 行；新增分支复用 `collect_delivery`，没有另写弱化版 native 解析器。证据 `image_recovery.py:83` 至 `:92`、`test_studio_native_recovery.py:1` 至 `:88`。没有新增 Any、动态执行或 SQL 字符串拼接；单业务轮查询使用 SQLAlchemy 条件表达式（`:45`）。
- 安全和失败处理：原生解析/验证警告不会带着部分输出写入（`image_recovery.py:89`）；收图全部无输出也会失败。事件哈希、receipt、正文绑定均在分支之前；两事务都复验权限/状态/证据。秘密、eval、HTML 注入、前端密钥前缀、OpenAI/Anthropic 密钥模式扫描无命中。`:88` 的绝对路径为既有沙箱逻辑前缀，没有引入任意路径读取入口。
- 测试真实性：新增测试复用 `tests/test_studio_image_recovery.py:25` 的真实 SQLite 模型/事务和 Pillow PNG，实际执行 `collect_delivery`、native parser 和 `validate_image`，没有 mock 成功收图。`test_studio_native_recovery.py:14` 把无关旧 Turn 移到另一个 Conversation，同时改其 Job payload，目标会话确实只剩一轮；正文同步到 DB、CLI events 和 native final。九个失败输入分别扰动目标条件，检查 Picture/台账均为零（`:86` 至 `:88`），并非只断言抛错。
- 继承测试证明边界：事务间状态/存储失败用例使用显式链接分支，但生产事务外壳共用；新无链接分支通过成功和九类失败用例。SQLite 不证明 PostgreSQL 的真实阻塞/死锁时序；Windows symlink 跳过；本 reviewer 未执行 Linux 安装环境测试及真实页面操作，不将这些写成 PASS。

## 独立验证原始输出

工作目录：`hengxin-smart-image/backend`。

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_native_recovery.py tests/test_studio_image_recovery.py tests/test_studio_native_images.py tests/test_studio_delivery_bridge.py -q
........................................................................ [ 73%]
..s.......................                                               [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
97 passed, 1 skipped, 2 warnings in 24.31s
exit_code: 0
```

终端分页输出已按产生顺序合并。跳过来源为 `tests/test_studio_native_images.py:178`：OS denies symlink creation。两条依赖弃用警告保留，不扩大本次依赖升级范围。

```text
.venv/Scripts/python.exe -m compileall -q app/overseas/studio/image_recovery.py tests/test_studio_native_recovery.py
stdout: <empty>
stderr: <empty>
exit_code: 0

git diff --check
warning: in the working copy of 'AGENTS.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
exit_code: 0

STAGED_PRIOR_APPROVED_MATCH True
APPROVED ede03b314995060169e2f6ae7a67991e11308983d6476bd2c8b90a03856d6fb4
CURRENT_LINES 194
```

主 Agent 在报告完成时补充：服务器隔离 Docker 绑定已上线 app 和独立安装的新 image_recovery.py，四文件专项 `98 passed, 2 warnings in 35.85s`，Linux 符号链接项通过，业务 worker 未改。此为主 Agent 提供的实装验证，不冒充 reviewer 独立运行；实际安装摘要和日志由其保留。

主 Agent 可为本 candidate 登记两阶段 PASS，继续受限补收、正式页面下载验收和恢复 gate。生产目标 task `3082e683-cd4c-45c2-a1bf-ed15f1e7b879`、turn `f149d4be-68a4-4d9a-a248-4a60f2142a05` 的既有只读重放结果由主 Agent 提供，不冒充 reviewer 的现场操作结果。恢复完成仍需其操作证据，Git 最终提交还须重新暂存本候选工作区内容。
