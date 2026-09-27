# CLI 成品验收整改独立审查

日期：2026-09-27。审查角色：code-reviewer；执行 `.agents/skills/code-review/SKILL.md`。仅本地审查，未修改产品代码、提交、部署、调用收费模型或补收生产任务。

## 结论和候选范围

**Stage 1：PASS。Stage 2：PASS（限下述本轮范围与验证边界）。未发现需阻断本轮的功能或安全问题。**

candidateId：`30fec908031bb4340fccfd915ce402f552a5d5a2056d7af1b0256247004d7810`。

最初派发 ID 为 `ad51bc3595841b209a98ee9aed398577dd42ea7e42e1e165b1b0877d64c11be7`。审查期间主 Agent 清理意外生成的 `.pnpm-store` 缓存后更新为 `6119868a612c20ab8e763be4a99f88c03447bebcdfa70adad40b6ecc820e788e`，再移除本轮 `frontend/dist-delivery-check` 构建输出，得到最终 ID。本报告评估当前源码；末次 review-status 的 currentId 匹配上述最终 ID，变更清单已不含这两类产物，观察到的产品源码范围未变。旧 candidate 文件清单未留存，不能声称独立逐哈希重建了旧缓存差异；没有将未手工审查的构建输出计入源码批准范围。

以下 `app/`、`tests/` 均相对 `hengxin-smart-image/backend/`。范围为 execution 下 events、final_delivery、delivery_markdown、delivery_acceptance、delivery_snapshot、delivery_storage、delivery_state、codex_runner、intervention、observation；worker/reconcile、repair_delivery；tasks/queries、observations；pyproject.toml、uv.lock 和对应变更测试。前端只改 `frontend/tests/execution-progress.test.ts`。查阅 git diff 和未跟踪的新交付模块，未把仅看已跟踪 diff 当作完整审查。

输入为 `AGENTS.md`、上述 skill、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:3` 的2026-09-27完整章节、`DEV-PLAN.md:3` 同日完整章节，以及 `docs/CLI-ACCEPTANCE-ADVERSARIAL-REVIEW-20260927.md` 的原发现。全产品历史功能不在本次重新验收范围。

## Stage 1：逐项 Spec 对照

| 当前条目 | 结论与代码证据 | 验证证据 |
| --- | --- | --- |
| 本轮完整最终交付优先，历史网络 error 不单独否决 | 完整实现。`app/execution/events.py:55` 将过程错误与完成状态分离；`:86` 完成后固定 final_text；`final_delivery.py:20` 使用同一解释结果 | `tests/test_delivery_acceptance_flow.py:48`，三路径 reset 用例 |
| 异常 usage、重复终态、非零退出不单独否决 | 完整实现。`events.py:91` 终态去重、`:100` 单独计量；`delivery_acceptance.py:19` 要求真实整数退出码但不限于0；`intervention.py:117` 保留可信用量 | 同一三路径测试的 usage、duplicate、nonzero 组；`test_reconnect_delivery.py:39` |
| 可靠 session、最终 turn 和停止证据；未知最终性不误成功 | 完整实现。`events.py:42` 校验 thread；`:64` 后续实质事件清除旧答复；`:87` 核对显式 turn 身份；`delivery_acceptance.py:19` 缺停止回执抛 uncertain；`worker/reconcile.py:106` 检查原进程身份 | `test_reconnect_delivery.py:65` 尾部事件、`:78` 未归属文本、`:107` 旧 turn；`test_delivery_acceptance_flow.py:91` unfinished/failed/mismatch |
| 正常、续接、恢复共享验收 | 完整实现。`codex_runner.py:169` 两次 invocation 均走 accept_delivery；`worker/reconcile.py:138` 同入口；`worker/repair_delivery.py:50` 人工重收也复用 | 18组三路径集成对照，真实 collector 和发布事务，CLI 边界模拟 |
| 内联/引用式图片和下载链接、列表图片、去重、排除代码 | 完整实现。`delivery_markdown.py:92` 用 CommonMark token 结构；`final_delivery.py:31` 预览/下载去重 | `test_final_delivery_markdown.py:9` 各格式，`:25` 代码排除，`:41` 引用显示顺序 |
| 完整数量及明确顺序，不候选凑数 | 完整实现。`final_delivery.py:89` 精确张数，`:96` 编号全集及排序；没有扫描候选补位 | `test_final_delivery.py:125` 缺少/过量，`:175` 编号变体，`:245` 展示顺序 |
| 历史、跨任务、输入、逃逸、坏图、超限继续拒绝 | 完整实现。`final_delivery.py:48` 本地路径边界及历史名单、`:75` 硬链接；`:106` 安全读取、`:112` 原图完整解码验证 | 原 final_delivery 负例；新快照身份、链接、摘要及超限回归；没有新增画质或尺寸门槛 |
| 验收后受控持久目录冻结身份、槽位、摘要、字节 | 完整实现。`delivery_snapshot.py:20` 目录边界、`:30` 身份、`:85` 严格加载、`:126` 字节 fsync 后原子 manifest 提交；CLI 仅挂载 home/work，`workspace.py:102` 不暴露 control | `test_delivery_snapshot.py:20` 幂等，`:29` 归属，`:46` 提交前中断，`:59` 损坏；冻结后的恢复无需原文件 |
| 保存/发布异常进入自动补收，不重新调用模型 | 完整实现。`codex_runner.py:197` 后续持久化；`:206` 已停止后的异常留待恢复；`delivery_state.py:11` uncertain 且保留证据；`reconcile.py:138` 恢复快照 | `test_delivery_recovery_flow.py:22` 三路径第二张 PUT 丢回执，删除原事件/回执/原图后恢复；`:67` 发布提交前后异常 |
| 未冻结完成不能声称已保存 | 完整实现。`codex_runner.py:181` 仅在 accept_delivery 返回后设 deliveryReady；`delivery_state.py:29` 未 ready 显示 uncertain | 快照 replace 故障测试证明无提交标记时 load 返回 None；异常分支代码检查 |
| 相同文件身份、恢复不增文件/版本、保留发布门禁 | 完整实现。`delivery_storage.py:23` round/slot/content 稳定 UUID，`:33` 现存身份核对；`app/modules/tasks/results.py:9` 短事务中 valid 门禁 | `test_delivery_storage.py:43` 同内容不同槽位与重试，`:70` 两阶段 commit 前后故障；恢复测试文件/版本计数 |
| 取消、执行权、当前轮次持续检查 | 完整实现。`delivery_storage.py:18` 每步 active，`delivery_state.py:14` token/轮次/取消；`reconcile.py:38` CAS 换权；`claims.py:91` 当前轮次与租约；最终 publish 再检查 | `test_delivery_storage.py:112` PUT 后失权；`test_delivery_recovery_flow.py:91` 待保存取消；既有 `test_execution_reconcile.py:97` |
| 显示“图片已生成，正在保存”，持久发布后才成功 | 完整实现。`tasks/observations.py:22` pending 的 storing/label；`tasks/queries.py:19` 列表状态，`:136` 统计及筛选；终态优先 | `tests/test_observation.py`、`test_task_queries.py` 新断言；`frontend/tests/execution-progress.test.ts:17` 继续轮询至真正成功且终态覆盖 pending |
| legacy manifest 保留旧合同 | 完整实现。`worker/reconcile.py:132` 显式协议识别，`:144` 无协议继续旧 collector/provenance/partial 合同；未知版本不降级 | `test_execution_reconcile.py:241` 未知协议负例及全量恢复回归 |
| 不改模型、Skill、提示词、并发、超时、不部署和生产补收 | 未见 Spec 漂移。变更集中在本轮模块；`codex_runner.py:147` 模型参数仍为既有值 | git diff 范围核查；本 reviewer 无外部修改动作 |

完整实现如表；本范围没有确认的部分实现或未实现项。展示验证属于 API/轮询契约验证，不代表浏览器视觉验证。没有新增或修改页面布局、设计稿、前端产品组件，本轮邻居页面视觉比较不适用；未把未做的视觉比较写成通过。

## Stage 2：质量、安全与测试真实性

- 模块按解析、冻结、保存、状态职责拆分，变更产品文件均少于300行：`codex_runner.py` 238行、`delivery_markdown.py` 145行、`delivery_snapshot.py` 148行、`worker/reconcile.py` 179行。新增 Python 函数的完整类型标注仍较少，但遵循既有模块风格，未发现由此导致的功能缺陷。
- 安全检查：目标目录 grep 未见新增 eval、前端危险 HTML 插入或密钥字面量。`delivery_markdown.py:95` 放开 URL 白名单仅供结构解析，不渲染 HTML、不抓取链接；`final_delivery.py:48` 随后执行文件边界校验。快照不可写入模型沙箱，`delivery_snapshot.py:52` 对普通文件、单链接、inode、大小再校验；不能将普通模型 JSON 当平台已验收快照。
- 事务与错误处理：`delivery_storage.py:45` 先创建稳定 staging 记录，PUT 后再标 ready；含糊成功不删对象；`delivery_state.py:14` 已提交 succeeded 不被异常回调覆盖。`results.py:12` 发布再查执行权，未放松既有可见性门禁。
- 测试是真实业务入口，不只是 mock collector 返回成功：`test_delivery_acceptance_flow.py:16` 仅替换 CLI，后续真实受理/收图/保存/发布和HTTP读取；`test_delivery_recovery_flow.py:29` 明确模拟远端已写但回执丢失，再验证文件ID与版本数量。没有把 SQLite 单进程回归描述为 PostgreSQL 多 Worker 竞态实测。
- 依赖核对：`pyproject.toml` 和 `uv.lock` 固定 markdown-it-py 4.0.0；使用方式符合[官方 v4.0.0 文档](https://markdown-it-py.readthedocs.io/en/v4.0.0/using.html)。CommonMark 默认允许 HTML 的[官方安全边界](https://markdown-it-py.readthedocs.io/en/latest/security.html)在这里由“不渲染，只提取 token”规避，文件安全另由 collector 判定。CLI 事件结构参照 [OpenAI exec_events 源码](https://github.com/openai/codex/blob/main/codex-rs/exec/src/exec_events.rs)，没有把所有部署版本都假定为带 turn_id。

## 原始验证输出与边界

Reviewer 独立执行（backend目录）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_delivery_acceptance_flow.py tests/test_delivery_recovery_flow.py tests/test_delivery_snapshot.py tests/test_delivery_storage.py tests/test_final_delivery_markdown.py tests/test_reconnect_delivery.py
91 passed, 1 skipped, 2 warnings in 13.88s
exit_code: 0
```

跳过是 Windows 不授予符号链接创建权限，`test_delivery_snapshot.py:99`；硬链接检查执行。警告为 Starlette/httpx 及 anyio BlockingPortal 弃用提示。

```text
.venv/Scripts/python.exe -m compileall -q app/execution app/worker/reconcile.py app/worker/repair_delivery.py app/modules/tasks/queries.py app/modules/tasks/observations.py
exit_code: 0
output: ""
```

主 Agent 全量测试日志由 reviewer 实际读取 `output/cli-delivery-full-tests.txt`：

```text
1183 passed, 171 skipped, 15 warnings in 76.88s (0:01:16)
```

跳过包含独立 PostgreSQL 连接、Linux/真实执行条件和 Windows 符号链接权限；这些不视为已验证。未连接真实模型或生产 MinIO，也未验证多 Worker/真实 PostgreSQL 并发。

本轮前端原始工具输出由主 Agent 提供，未写完整独立日志；不引用目录中旧110条测试日志冒充本轮结果：

```text
node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts
tests 176, pass 176, fail 0, cancelled 0, skipped 0
duration_ms 4279.7005
exit_code: 0
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
exit_code: 0
output: ""
node node_modules/vite/bin/vite.js build --outDir dist-delivery-check
vite 7.1.7
4469 modules transformed
built in 45.47s
exit_code: 0
```

报告仅批准所述代码范围与快照；须由主 Agent 用同 candidateId 登记 review-approve，不向 `.needs-review` 写 clean。生产仍未部署，历史任务仍未据此宣称恢复。
