# 海外图片交付修复独立审查（初审）

- 送审 candidateId：`74f6cacd8b5108a1eae854c63533ab0db889802b867ddceab4c10274f4973d1f`。
- Stage 1：**FAIL**。发现 1 项 HIGH，历史证据绕过原轮最终交付清单。
- Stage 2：**未执行**，依 code-review skill 在 Stage 1 HIGH 处停止；本报告不得用于登记两阶段 PASS。
- 范围：`Product-Spec.md:1322` 末章、`docs/STUDIO-DELIVERY-FIX-20261023.md:1`，海外原生图片接收、历史补交、受限恢复、worker 增量发布脚本及对应测试。未访问生产、未修业务代码、未提交。
- 快照：审查开始 `review-status.currentId` 与送审编号一致。审查中主 Agent 修改了 `native_images.py` 及其测试；中途 currentId 为 `298ac8554404ce338bdd02fd39a6e556bf5c69885736107dfd939186c0e6b7f5`，随后仍有修改。因此旧候选结论不能批准当前代码；须重新 prepare 并独立复核。
- `AGENTS.md` 的既存一行内容修订属于送审快照，未发现本轮业务实现据此新增功能。正式 UI 无改动，本轮没有新增页面或设计稿对比对象。

## Stage 1 问题

### HIGH H1：历史公开图片证据忽略原轮最终显式清单

Spec 原文：`Product-Spec.md:1324`，“最终回复显式列出图片时以明确交付清单为准，避免把此前过程图混入”；`Product-Spec.md:1326`，历史补收必须有此前成功轮的公开图片交付证据。

送审版本 `hengxin-smart-image/backend/app/overseas/studio/native_images.py:201` 的 `read_history` 只用 `any(non_delivery(...))` 排除整轮负面描述，其后把全部原生生成与公开输出哈希匹配的图片当作历史正式交付，没有应用 `references(final)` 的显式清单。当前轮 `delivery.py:157` 却正确以显式清单为准，两个入口的门禁不一致。

可达影响：第一轮公开展示 A，最终只列 B，A 在第一轮未收取；第二轮明确引用 A 时，`delivery_evidence.py:29` 获取 A 的历史 proof，`delivery.py:168` 因 proof 绕过 baseline。维护入口 `image_recovery.py:82` 同样使用该历史 proof。原轮明确排除的过程图可被当作正式历史图补收。

本地复现基于 `test_studio_native_images.py` 的脱敏事件夹具，没有访问生产：原轮生成并公开展示 `exec-1.png`，原轮 final 仅列 `![图](/work/final.png)`（Windows 管道中的中文出现编码替换，但 Markdown 路径保持），调用 `read_history(home, SESSION, {native_path})`。原候选实际返回非空 proof：

```text
historical_target=/home/runner/.codex/generated_images/4b04db11-7ce7-4ec1-a979-333333333333/exec-1.png
historical_proof={'/home/runner/.codex/generated_images/4b04db11-7ce7-4ec1-a979-333333333333/exec-1.png': '3064001f9933ee70c48b14f22ec2c487a2c1e205167f7eeed4e9fe1e088a458e'}
EXPECTED empty proof because explicit final list excludes target; ACTUAL accepted=True
```

修复验收：历史与当前使用一致的最终选择规则；历史清单外图不可补收；清单内图可以补收；草稿段和正式段并存时按现有段落门禁选择正式图，不能用全局草稿判断误拒合法正式图；无显式清单时才使用符合要求的原生公开图片证据。覆盖正常续聊及维护恢复入口。

主 Agent 收到问题后已修改实现并添加测试；上述是原候选缺陷，不代表已完成对新候选的复审。

## Stage 1 逐条核查

下列“代码符合”限定所列代码和本地证据，不等于生产验收或整轮批准。

| 需求条目 | 结论 | 代码与验证证据 |
| --- | --- | --- |
| 首轮无 Markdown 仍接收原生公开图 | 代码符合 | `native_images.py:65` 识别 Extension generation，`:88` 识别公开 input_image；`delivery.py:160` 无显式清单时采用证据。`test_studio_delivery_bridge.py:41` 用真实可解码 PNG 校验输出字节与尺寸。 |
| 同会话、同轮次、完成、最终正文一致 | 代码符合 | `native_rollout.py:70` 校验 session_meta；`native_images.py:60`、`:106`、`:183` 校验轮次与最终正文；`execution.py:57` 在启动前固定 cursor。原生专项包含跨 session/turn、缺失 final/complete、正文不一致拒绝。 |
| 生成事件与公开展示字节 SHA256 匹配 | 代码符合 | `native_images.py:12`、`:73`、`:103`、`:114`；`delivery.py:174` 再核实际文件 checksum；不匹配不会返回成品。 |
| 未公开、中间图、明确草稿、失败/取消/截断不收 | 部分实现 | 当前门禁及故障事件由 `native_images.py:137`、`delivery.py:160` 保护；专项覆盖未展示、草稿、失败与截断。历史清单外过程图仍有 H1。 |
| 最终显式清单优先 | 部分实现 / HIGH | 当前 `delivery.py:157` 符合；历史 `native_images.py:201` 不符合，见 H1。 |
| 多图 | 代码有实现，专项验收证据不足 | `_Turn.generated` 字典和 `MAX_IMAGES=100`（`native_images.py:9`、`:78`、`:114`）、`delivery.py:163` 逐图处理。已读测试覆盖数量超限和重复路径，但本审查未见两张不同有效 PNG 同轮均收取的独立端到端结果。不能把单图测试说成多图验收。 |
| 同会话明确补交历史 native，原字节不变 | 部分实现 / HIGH | `delivery_evidence.py:20` 仅针对同 session 显式路径查询历史；`delivery.py:174` 校验原字节，正常补交/重复补交测试通过。但历史资格受 H1 影响。 |
| 跨会话、输入、Skill、无来源旧图拒绝 | 代码符合既有边界 | `native_images.py:24` 路径前缀限制；`delivery_evidence.py:20` 同 session；`app/execution/final_delivery.py:45` 保留 `_local_file`；`test_studio_delivery_bridge.py:106` 覆盖无历史公开证据。 |
| 相同来源与内容不重复入库/计数/归档 | 代码符合 | `execution.py:40` 读取会话内既有 Picture；`delivery.py:182` 去重；恢复 `image_recovery.py:98`、`:133` 同会话去重。`test_studio_image_recovery.py:81`、`:207` 检查幂等及前轮已有图片。无自动归档代码。 |
| 普通 work 图片保持新增/变更门禁 | 代码符合 | `delivery.py:176` 保留 `check_work_version`；`test_studio_delivery_bridge.py:78` 验证旧 work 图片拒绝。 |
| 解析、文件、存储失败保留文字并明确提示 | 代码符合 | `delivery_evidence.py:7`、`:17`，`delivery.py:185`，`execution.py:137`；bridge 损坏/缺失/篡改及恢复存储故障测试通过。 |
| 不能扫描输出目录猜测交付 | 代码符合 | `native_rollout.py:21` 只定位指定 session 日志；`native_images.py:65` 仅消费明确生成/展示事件，实际收图仍按证据路径或 final 引用。 |
| 受限维护、归属、成功退出、成功结果核验 | 代码符合 | `image_recovery.py:30` 权限及 Task/Turn/Conversation/Job 归属；`:56` SHA256、exit receipt、公开正文、事件 cursor 与存储结果一致性。恢复测试包含权限、跨归属、失败、取消、异常 receipt。 |
| 暂停排空、删除竞态保护 | 代码符合；未实证 PostgreSQL 并发死锁 | `image_recovery.py:34` Task 锁后 `:37` gate 再 Job，与 `tasks/deletion.py:33`、`execution/claims.py:100` 的业务发布锁序相容；两事务均重新校验 TaskDeletion/排队活动状态。`test_studio_image_recovery.py:187` 覆盖事务间删除/入队/恢复接纳；这些测试不能证明真实 PostgreSQL 并发。 |
| 持久台账、失败存储、DB 失败重试 | 代码符合 | `image_recovery.py:124` 台账事务先提交，`:147` 第二事务复查，`:167` 存储；`:111` 确定性 object key。`test_studio_image_recovery.py:160`、`:174`、`:219` 覆盖存储失败/上传后 DB 回滚/证据和台账变化。 |
| 补入 Picture 与执行结果，审计且保持原执行信息 | 代码符合 | `image_recovery.py:168`、`:177`、`:181`，只更新结果、交付错误和 version；`test_studio_image_recovery.py:81` 断言 started_at/completed_at/execution_count 不变以及单条审计。 |
| 不重跑模型、不自动归档 | 代码符合 | `image_recovery.py:120` 维护入口只读原证据并写对象及记录，无 CLI 执行和 archive 调用。 |
| 截断/重复字段/读取限制 | 代码符合 | `native_rollout.py:38` 拒绝重复 JSON key，`:48` 单行 64 MiB/累计 512 MiB、换行与 JSON 检验；原生专项覆盖限制与 cursor 身份。 |
| 链接/硬链接/越界保护 | 代码符合；Windows symlink 项跳过 | `native_rollout.py:24`、`:97` 复用 `context_fs.py:27`、`:70` 安全 reader；图片复用 `_local_file` 与 `diagnostics.py:79` 单链接安全读取。硬链接测试通过；该主机 symlink 测试未执行，需 Linux 实测补齐。 |
| 当前生产基线增量，仅海外 worker | 代码符合发布约束；未执行生产验证 | `studio_delivery_runtime.py:16` patch allowlist，`:72` baseline，`:78` retained tree；`studio-delivery-deploy.py:15` 复制实际旧目录并绑定哈希，`:79` 只切指定 worker。 |
| 保持权限、Skill、模型、国内协议，无迁移 | 差异范围符合 | 新 drop-in 仅 WorkingDirectory/ExecStart（`studio_delivery_runtime.py:141`），`execution.py:61` 模型/推理参数未变；送审差异无迁移、国内业务与权限/Skill配置改动。生产保持结果尚需实际比对。 |
| 安装测试、备份排空、验收后恢复接纳 | 代码门禁具备；实际交付待执行 | `studio-delivery-deploy.py:65` 校验安装测试回执；`:90` 暂停排空；`:108` DB备份；`:162` 验收回执后恢复原 gate 值。`studio_delivery_runtime.py:200` dump/list 检查。原图完整备份、真实安装/恢复及页面验收需主 Agent 留实际证据，不能以脚本存在代替。 |
| 指定原图补回原任务，预览/下载/可归档 | 未执行生产验收 | 指定 task/turn/SHA 位于 `docs/STUDIO-DELIVERY-FIX-20261023.md:9`。本 reviewer 未访问生产，尚不能声称图已补回或浏览器已通过。 |

## 本地测试与编译原始输出

执行目录：`hengxin-smart-image/backend`。

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_native_images.py tests/test_studio_delivery_bridge.py tests/test_studio_image_recovery.py tests/test_overseas_studio_execution.py -q
........................s............................................... [ 70%]
..............................                                           [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
101 passed, 1 skipped, 2 warnings in 22.52s
```

该测试进程启动时针对原候选四个文件完成收集，运行期间工作区已有修改，不能将结果绑定后来新 candidate。两项依赖弃用提示为工具输出，本审查未据此增加外部库升级范围。

```text
.venv/Scripts/python.exe -m compileall -q app/overseas/studio/delivery.py app/overseas/studio/delivery_evidence.py app/overseas/studio/execution.py app/overseas/studio/image_recovery.py app/overseas/studio/native_images.py app/overseas/studio/native_rollout.py
stdout: <empty>
stderr: <empty>
exit_code: 0
```

编译时已是修改中的工作区，只证明该次读取文件可编译。主 Agent 声明的其他 Windows 全套、前端类型检查、发布脚本专项、Linux 安装包测试不冒充为本 reviewer 自行执行结果；应在后续复审附原始日志和新候选关联。

## Stage 2

未执行代码质量、安全扫描、测试真实性专项和视觉对比。Stage 1 HIGH 已通知主 Agent，修复与重新 prepare 后从 Stage 1 复审；本报告不写 `.needs-review`，不登记批准。
