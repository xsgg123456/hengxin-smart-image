# 海外最终收图可靠性发布终审 · 2026-10-24

- 最终 candidateId：`f394a797f71eea0a006d3fb3ce56de845ea232e51125c2abb9b35d6f344c2dd5`。
- **Stage 1：PASS。Stage 2：PASS。未发现本次受审范围内剩余 HIGH 或 MEDIUM。**
- 本轮直接审查：4 个发布/打包/独立补收运行脚本、3 个发布测试文件、前端版本声明，以及实际继承的 prepare/deploy/installed/backup/drain/Skill 校验调用链。采用 `code-review` 两阶段流程，Stage 1 通过后执行质量、安全与编译检查。
- 核心与前端行为继承 R5 独立两阶段 PASS，依据逐文件摘要核对，详见下文；没有将旧报告直接套用到变化文件。
- 排除用户已有的 `AGENTS.md` 修改。本 reviewer 未修改产品代码或 Skill，未调用模型、连接生产、部署、提交或登记批准。**生产尚未部署本版本，本报告不是生产交付完成证明。**

## 依据、范围与快照

已读取 `.agents/skills/code-review/SKILL.md:25`、`docs/HARNESS-REVIEW.md:5`、`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:3`、`Product-Spec.md:1336`、`DEV-PLAN.md:1558`。最新要求以实施合同第 7 行为准：用户主动删除原任务，取消八图恢复，发布不得依赖历史补收请求或恢复删除内容。

最初交接编号 `cc61f5964f36fbff8a678aff27b1df3d97d49a72b4a2059e1b3feacbee134df3` 已作废。主 Agent 在审查开始后通知 `test_studio_delivery_release_repair.py:171` 新增 `d.closed` 离线替身，防止测试探测真实入口，并重新固定为上述最终编号。本报告全部实测与哈希核对使用新编号；最终检查没有继续漂移。

完整 1934 文件 manifest 已保存到 `output/studio-delivery-reliability-20261024/reviewer-release-final-snapshot.json:1`，采用仓库 `review_files.snapshot/digest/identity` 规则，包含文件模式和仅 CRLF 归一的摘要；当前 identity 精确匹配最终 candidate。

R5 manifest 为 `output/studio-delivery-reliability-20261024/reviewer-r5-snapshot.json:1`，对应 `3dd0d892a821a09dbefdb71663f6cfd8a060b3c0de72de27322742c1ee6ffe4d`。逐文件比对 1564 项，1561 项完全相同，仅以下 3 项不同；原范围没有新增或删除文件：

1. `scripts/release/studio-delivery-reliability-20261024.py`。
2. `scripts/release/test_studio_delivery_release_repair.py`。
3. `scripts/release/test_studio_delivery_reliability_release.py`。

其中 backend 603 项、frontend 源码/测试 732 项全部相同；release 229 项中其余 226 项相同，包括既有 runtime/helper、打包入口和独立补收运行脚本。结构化证据：`output/studio-delivery-reliability-20261024/reviewer-release-final-comparison.json:1`。R5 未包含 `frontend/package.json`，本轮另查其相对 HEAD 唯一差异为第 3 行 `0.2.50` → `0.2.51`，与发布及打包目标一致。所有本次相对 HEAD 的受控差异都落在上述范围或排除的 `AGENTS.md`，没有遗漏另一组未审产品文件。

据此继承 `docs/reviews/STUDIO-DELIVERY-FINAL-20261024.md:10` 的核心及前端两阶段 PASS、测试和真实组件视觉证据。RELEASE-R3 没有历史完整 hash，因此**不声称与 RELEASE-R3 完成逐字节历史比对**；本轮重新检查当前 7 文件及完整发布调用链。

## Stage 1：逐项符合性

下表 `release/` 均指 `scripts/release/`，`backend/`、`frontend/` 均以 `hengxin-smart-image/` 为前缀。

| 合同条目 | 结论 | 证据 |
|---|---|---|
| 最终回复实际图片，无固定措辞；历史同会话图片可再次交付 | 完整实现，继承核心 PASS | backend 全部与 R5 相同；`backend/app/overseas/studio/delivery.py:92`、`native_images.py:209`。R5 报告逐项覆盖最终引用优先、历史 work/native 及工具失败后恢复。发布代码不增加模型输出门槛。 |
| 1. 正常退出和精确轮次边界，中途确认不是终态 | 完整实现，继承核心 PASS | `backend/app/overseas/studio/completion.py:49`、`native_rollout.py:109`、`backend/app/overseas/execution/runner.py:138`；R5 187 项核心及 362 项接线证据按原范围继承。 |
| 2. 私有字节快照、落盘、捕获失败保持恢复依据和任务活动 | 完整实现，继承核心 PASS | `backend/app/overseas/studio/delivery_job.py:124`、`delivery_snapshot_fs.py:130`、`delivery_recovery.py:19`；这些文件摘要未变。 |
| 3. 逐图持久恢复、幂等和租约；取消/删除禁止迟到发布 | 完整实现，继承核心 PASS | `backend/app/overseas/studio/delivery_job.py:22`、`:70`、`:99`；`backend/tests/test_studio_delivery_fencing.py:39`。没有因取消旧图恢复而修改该保护。 |
| 4. 保存中显示实际数量、已保存图立即显示、全齐完成、自动退避、跨轮独立版本 | 完整实现，继承核心 PASS | `backend/app/overseas/studio/delivery_job.py:38`、`:103`、`:174`；`frontend/src/views/overseas/studio/StudioTurns.vue:31`。组件、DTO、样式和浏览器测试摘要未变。 |
| 5. 故障与平台验证、独立审查 | 完整实现代码验证 | 本轮独立 173 PASS + 48 subtests，0 skip，详见原始输出。另读取 Linux 最终 native 报告及 JUnit：98 PASS/0 skip/0 failure/0 error，绑定 R5 核心；未声称本轮重新执行全部核心或 Linux 套件。 |
| 6. 取消八图恢复，prepare 无需 request；残留旧 request 不触发补收 | 完整实现 | `release/studio-delivery-reliability-20261024.py:95` 只做 preflight、保存 Skill 状态、继承 prepare；没有加载 repair 模块或执行 `pin/run/hold`。`release/test_studio_delivery_reliability_release.py:59`、`:72` 分别验证禁止加载 helper、request 不存在/残留无效内容均不读取或生成补收标记。 |
| 6. installed 只校验已安装代码/配置/Skill，不修旧任务数据 | 完整实现 | `release/studio-delivery-reliability-20261024.py:128` 调继承 installed 后对比 Skill 状态；`release/overseas-upload-deploy.py:156` 验镜像/源码/原生目录/健康；`release/test_studio_delivery_release_repair.py:120` 对 absent/stale request 均验证只有 installed→open，旧 request 字节不变，无补收标记。 |
| 6. deploy 直接继承发布、仍要求有效 installed receipt | 完整实现 | 新入口 `:134` 直接 `return s.deploy(...)`；`release/overseas-studio-sessions-deploy.py:267` 验 receipt 的 image/manifest/target 后才 `_deploy`。当前 adapter 实测 `release/test_studio_delivery_reliability_release.py:188` 对三种漂移均在切换前拒绝。 |
| 6. 当前生产基线、API/worker/outbox、权限与 Skill 清单 | 完整实现校验接线；实际生产核查由主 Agent 执行 | 新入口 `:19` 固定 0.2.50→0.2.51、`overseas-20261024-71ed440` 和镜像摘要；`:54` 验 Compose 尾链、原生目录/argv、broker 和国内原生进程。`release/overseas-studio-sessions-skills.py:14` 验 15 包/227 文件、同目录身份与只读挂载；`:86` 固定并逐字对比 Skill 启停数据。 |
| 6. 关闭入口、排空、备份隔离恢复校验、再切换 | 完整实现 | `release/overseas-upload-deploy.py:211` 按 close→停 API→drain→backup→before_switch→switch 顺序执行；`:83` 排空后逐个停 outbox/worker。`release/overseas-studio-sessions-deploy.py:121` 有时限及连续两次空队列要求。`release/overseas-studio-ux-deploy.py:122` 调隔离 restore_check 并比对全表指纹，成功才写 COMPLETE；`release/member-release-backup.py:119` 只恢复到隔离临时 PostgreSQL 容器。 |
| 6. 数据漂移/未完成备份/未停执行器拒绝；不迁移、不改国内或 Skill | 完整实现 | 新入口 `:101` 在 COMPLETE、EXECUTORS_STOPPED、schema、数据指纹、Skill 启停均匹配后才写证明；`:148` 明确替换旧 migrate hook。测试 `release/test_studio_delivery_reliability_release.py:122`、`:130` 实际覆盖这些拒绝路径；无调用 migration compose。继承资源校验保留完整环境和权限。 |
| 6. 安装专项绑定实际文件、无生产配置或模型调用 | 完整实现调用契约；实际安装待发布执行 | 新入口 `:111` 从 manifest 发现新增故障测试，在无网络容器只读挂载实际 installed target，使用镜像解释器；成功后才写绑定 image/manifest/target 的 receipt。测试 `release/test_studio_delivery_reliability_release.py:171` 验证参数和 receipt；本轮没有把 subprocess 替身当生产镜像实测。 |
| 6. 失败保持关闭，旧补收标记不触发 hold 或修复 | 完整实现 | `release/overseas-upload-deploy.py:263` 在异常时重新 close、确认关闭、恢复内层代理、停 API、写 FAILURE；不强停未知 executor、不恢复生产数据库。`release/test_studio_delivery_release_repair.py:147` 走真实继承 deploy，在 installed Skill 漂移时断言两次 close、最后停 API、没有 open；`:191` 验残留补收标记只保留、异常原样上抛。 |
| 保留独立补收能力，但不触碰已删任务 | 完整实现 | helper/runtime 均与 R5 相同且脱离发布入口；`release/studio-delivery-repair-runtime.py:98` 显式调用后端 repair，`backend/app/overseas/studio/image_recovery.py:37`、`:38` 拒绝任务不存在/删除凭据，`delivery_repair.py:54` 拒绝会话删除。独立运行测试仍验证八图字节、权限、排空、重复幂等和失败不解锁。 |
| 6. 原图恢复取消；发布后现有任务入口/预览下载、恢复接纳、中文提交推送 | 代码支持；真实交付尚未执行完 | 新入口不含旧 taskId 或恢复动作，继承 `release/overseas-upload-deploy.py:248` 开入口并验证。生产部署后的浏览器验收、实际安装证据及 Git 推送由主 Agent 后续完成，不计作本报告已执行能力。 |
| 非零/取消/缺成功回执不冒充成功，不能重新生图掩盖 | 完整实现，继承核心 PASS | `backend/app/overseas/execution/runner.py:138`、`backend/app/overseas/studio/delivery_context.py:49`；发布入口与 helper 均无模型执行调用。 |

完整实现范围见上表。未发现部分实现或未实现的本次代码条目；明确保留的待执行项为生产安装、线上验收和 Git 交付。未发现新增页面/API/表、国内业务变更、Skill 内容/选择/安装修改或超范围恢复用户删除内容。

## Stage 2：代码质量、安全、测试真实性与视觉

| 维度 | 结果与证据 |
|---|---|
| 职责与文件大小 | PASS。4 个生产脚本分别 155/34/154/117 行，3 个测试文件 213/219/119 行，全部不超过 300；删除补收接线后入口仅继承部署，不保留额外异常恢复分支。摘要及行数见 `output/studio-delivery-reliability-20261024/reviewer-release-final-quality.json:1`。 |
| 错误处理 | PASS。新入口 `:134` 原样传播继承 deploy 返回值和异常；独立补收异常不被 normal deploy 捕获或执行。继承 fail-closed 由当前 adapter 真实调用层测试覆盖，`release/test_studio_delivery_release_repair.py:147`、`:191`。 |
| 测试前提与断言 | PASS。absent/stale 使用真实临时文件，断言旧内容不变；receipt 分别篡改三个字段，不只测成功路径；数据/Skill 漂移在新 adapter 上执行。installed→open 成功测试替换了底层部署，故仅证明接线顺序；失败测试则保留真实继承 deploy 控制流，仅隔离系统/网络边界，不能等同真实生产故障演练。新增 `d.closed` 替身不改变业务断言，避免离线测试访问线上。 |
| 继承关键保护 | PASS。独立重跑 `release/test_studio_sessions_release.py:184`、`:196` 的两次稳定排空与繁忙超时不停车、`:101` 的无效安装凭据、`release/test_package_overseas.py:118`、`:125`、`:157` 的干净源码/归档字节/manifest 测试。旧 migration 单元测试通过仅说明旧 helper 仍兼容；本轮不执行旧 migrate hook，另有新 adapter 的 no-migration 测试。 |
| **安全扫描** | **PASS：未发现本次 4 个生产脚本引入 eval/exec、shell=True、硬编码密钥、unsafe HTML、暴露的前端密钥变量或密码字面量。** 模式及空结果保存在 quality.json。独立 repair 请求采用 stdin、私有文件和现有 worker 身份，`release/studio-delivery-release-repair.py:30`、`:77`、`:94`；实际发布不加载该 helper。固定绝对路径为授权发布目录或 /proc 检查，不是新增用户输入执行面。 |
| 打包与隐私 | PASS。`release/package-studio-delivery-reliability.py:14` 仅显式纳入 helper；`release/package-overseas.py:84`、`:180` 复用 allowlist、clean/review gate、已提交字节比对和归档回读。私有 request、.env、output 历史证据不被打包，`release/test_studio_delivery_reliability_release.py:29`；版本 0.2.51 一致。 |
| 引导真实性与视觉 | 发布差异无新增 UI，不需要重开部署脚本的“邻居页面”。全部组件/样式/浏览器测试摘要与 R5 相同，继承 `docs/reviews/STUDIO-DELIVERY-FINAL-20261024.md:68` 起的真实组件 desktop/mobile 与既有完成消息对比证据；本轮没有声称独立重新跑浏览器或生产视觉验收。 |
| Spec 漂移 | 未发现。取消旧图自动恢复与最新合同 `:7` 一致；保留显式独立 helper 与通用补收是合同允许范围，不能因包中保留 helper 就推断部署会调用它。真实调用链与回归证明发布不触发。 |

## 独立测试与编译原始输出

命令：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_studio_delivery_reliability_release.py scripts/release/test_studio_delivery_release_repair.py scripts/release/test_studio_delivery_repair_runtime.py scripts/release/test_studio_sessions_release.py scripts/release/test_studio_sessions_skills.py scripts/release/test_archive_deletion_release.py scripts/release/test_overseas_upload.py scripts/release/test_package_overseas.py --junitxml=output/studio-delivery-reliability-20261024/reviewer-release-final-tests.xml
```

原始结果末段：

```text
.....                                                                    [100%]
============================== warnings summary ===============================
hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
173 passed, 2 warnings, 48 subtests passed in 14.31s
```

JUnit `reviewer-release-final-tests.xml:1` 为 tests=221（含 48 subtests）、failures=0、errors=0、skipped=0。其中 44 项来自本轮 3 个发布测试，129 项来自继承发布回归。两项警告是已有依赖弃用提示。

编译使用 `compile(path.read_text(encoding='utf-8'), str(path), 'exec')`；同时核对 candidate 摘要与行数，未修改源文件。原始 stdout：

```text
scripts/release/studio-delivery-reliability-20261024.py: COMPILE PASS; 155 lines; candidate MATCH
scripts/release/package-studio-delivery-reliability.py: COMPILE PASS; 34 lines; candidate MATCH
scripts/release/studio-delivery-release-repair.py: COMPILE PASS; 154 lines; candidate MATCH
scripts/release/studio-delivery-repair-runtime.py: COMPILE PASS; 117 lines; candidate MATCH
scripts/release/test_studio_delivery_reliability_release.py: COMPILE PASS; 213 lines; candidate MATCH
scripts/release/test_studio_delivery_release_repair.py: COMPILE PASS; 219 lines; candidate MATCH
scripts/release/test_studio_delivery_repair_runtime.py: COMPILE PASS; 119 lines; candidate MATCH
SECURITY_MATCHES []
CURRENT_ID f394a797f71eea0a006d3fb3ce56de845ea232e51125c2abb9b35d6f344c2dd5
DRIFT_SINCE_START []
```

补充引用证据：已读取 `output/studio-delivery-reliability-20261024/linux-validation/native-retry-final/REPORT.md:1` 并解析其 JUnit，原始属性为 `tests=98, failures=0, errors=0, skipped=0, time=16.197`，绑定 R5 的最后 3 文件 native delta。更早 Linux 基线 2544 PASS、差异 814 PASS、PostgreSQL 2 PASS、链接边界 10 PASS，以及前端 387 PASS/build/browser PASS，按 R5 报告的运行范围和 skip 限制引用，未冒称当前 candidate 又跑全量。后续包构建和生产实际安装仍须保存新的证据。

## 批准与交付边界

本报告支持主 Agent 为 **同一 `f394a797…` candidate 中受审的核心、前端、版本与发布文件差异**统一登记两阶段 PASS：核心/前端凭 R5 全文件 hash 继承，本轮 3 个变化发布文件与当前完整发布调用链重新审查，独立 helper/测试复跑。`AGENTS.md` 仅记录在完整快照，不在批准或提交范围内；普通需求/报告 Markdown 已读取且不属于 harness 代码快照。

如改用不含用户 `AGENTS.md` 改动的干净 worktree 打包，必须在该目录重新固定 candidate，对本报告保存的 1934 文件 manifest 核实唯一受控内容差异确为排除的 `AGENTS.md`，再形成新范围映射报告/凭据；不能复制当前 approval 或用旧编号声称干净目录已批准。本 reviewer 不调用 `review-approve`，也不写 `.needs-review` 的 clean。

代码审查通过不等于部署完成：实际备份排空、目标 0.2.51 安装、健康/现有任务入口、原图预览下载、恢复接纳、中文提交推送的最终结果由主 Agent 后续实测记录。不得恢复用户已删除任务或调用模型制造验收图。
