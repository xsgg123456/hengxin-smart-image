# 内网发布工具 LAN 绑定及迁移版本表修复复核

- candidateId：`15f14f9282bd58afa0c22eb836c62e1f4f80cfc0ea3c0f680551363f022a4d23`。
- 已批准基准：`39ff5e2b95ef21a0a0000ab2679e534e779c21d6ab03e3ac612042f386019e54`，报告 `docs/reviews/INTRANET-RELEASE-TOOLS-REVIEW-20261111.md:1`。
- 范围：`scripts/release/intranet/snapshot.py` 和 `scripts/release/intranet/test_release.py` 相对基准的差异；完整内网工具测试回归。依据 `.agents/skills/code-review/SKILL.md` 两阶段执行。
- Stage 1：**PASS**。Stage 2：**PASS**。仅批准本候选代码，不等于生产安装及无重启验收通过。
- reviewer 未连接服务器，未修改实现、旧报告或审查凭据，未提交代码。

## 快照与差异证据

最终候选 `review-status` 原始输出：

```text
{"currentId": "15f14f9282bd58afa0c22eb836c62e1f4f80cfc0ea3c0f680551363f022a4d23", "reviewedId": "39ff5e2b95ef21a0a0000ab2679e534e779c21d6ab03e3ac612042f386019e54", "changedFiles": ["scripts/release/intranet/snapshot.py", "scripts/release/intranet/test_release.py"], "approved": false}
```

审查过程中主 Agent 又修复海外迁移版本表，原候选 `669bf26cb7bcfb2ff9d797ae6db5c8e116df4a410754363d216c4ea84c3f073f` 不予登记通过。本报告重新从 Stage 1 复核最终候选并重跑全部测试。

对最终内容做纯内存逆变换：移除 `snapshot.py:78` helper，将 `:112` 调用还原为旧内联 loopback 检查，撤回 `:62` 固定表选择并还原旧 SQL；移除 `test_release.py:2` 的 io 导入和 `:81`、`:92` 两个新测试。两个重建内容的 SHA256 均与 review-state 中旧批准快照相同，确认不存在未说明的同文件改动。原始输出：

```text
BASELINE_RECONSTRUCTION scripts/release/intranet/snapshot.py True
BASELINE_RECONSTRUCTION scripts/release/intranet/test_release.py True
```

## Stage 1：Spec Compliance

`Product-Spec.md:1458`、`DEV-PLAN.md:1674` 引用的合同逐项核对如下；未变实现沿用已批准基准的逐项证据，由快照文件哈希证明其内容未变，不把基准中的生产待验收项升级为通过。

| 合同条目 | 结论与证据 |
| --- | --- |
| 固定内网目标、旧公网不动（合同第 5 行） | PASS。`snapshot.py:80` 请求固定 LAN 地址，与旧 `hengxin-smart-image/scripts/migration245/unify_release.py:491` 健康检查一致；`release.py:171` 主机门禁未变。 |
| 固定 Git 构建、隔离目录与摘要（第 7 行） | PASS，基准实现未变；`package_release.py:63`、`:141`、`:184`，`stage.py:15`；完整测试回归通过。 |
| 共用锁、原子台账、真实源码/前端/解释器/数据库（第 8 行） | PASS。锁和持久化未变（`release.py:15`、`:176`）；`snapshot.py:85` 仍捕获实际来源、`:112` 必须调用前端摘要校验、`:128` 保留 schema/data。`:81` 对实际 HTTP 字节 SHA256 严格比较，没有删去或绕过校验。 |
| 备份、排空、切换、健康及运行环境、失败恢复；前端仅切 web（第 9 行） | PASS，基准实现未变；`release.py:106`、`:112`，`engine.py:159`、`:212`，`operations.py:70`、`:111`；完整测试覆盖原事务和恢复用例。 |
| 状态不明阻断、不强杀、不倒灌、不覆盖 venv、依赖/迁移变更阻断（第 10 行） | PASS，基准实现未变；`engine.py:58`、`:193`，`release.py:88`，`snapshot.py:41`；完整测试回归通过。 |
| 保留版本及在用引用，不自动清理（第 11 行） | PASS，`release.py:116`、`:126`、`:141` 未变；新增 helper 仅 GET/读响应/比较，无删除操作。 |
| 此次仅工具安装和只读初始化，不重启、不调用收费模型（第 13 行） | 实现 PASS。`release.py:41` 在 `capture` 成功后才保存台账；`snapshot.py:78` 无业务变更和模型调用。生产无重启事实仍须主 Agent 安装后验收。 |
| 参数、锁、重复执行、漂移、依赖、正常及失败恢复测试（第 17 行） | PASS。全量 79 tests、7 subtests 通过；新增 `test_release.py:81` 同时覆盖仅 LAN URL 可访问与错误 index 摘要拒绝。 |
| 最终安装路径、真实运行环境、应用和数据未重启（第 18、19 行） | 仍为生产验收待执行，本 reviewer 不连接服务器。代码支持保留，证据 `snapshot.py:113`、`:128`；不能用隔离测试代替实际验收。 |
| 日常命令与限制（第 23 至 54 行） | PASS，`release.py:164` 注册和 `:41` init、`:126` recover、`:141` rollback、`:151` cancel 均未变；本次没有增加命令、配置或发布行为。 |

完整实现如表；本次变更无部分实现、未实现、HIGH 问题或 Spec 漂移。UI 一致性与邻居页面视觉对比不适用：没有产品页面或视觉变更。

## Stage 2：Code Quality

| 检查 | 结论与证据 |
| --- | --- |
| 结构和规模 | PASS。`snapshot.py:78` 将单一 HTTP 校验提取为 helper，`:112` 保留原调用顺序；snapshot 141 行、test_release 204 行，均未超过 300 行。 |
| 异常与完整性 | PASS。`snapshot.py:80` 保留 10 秒超时和 context manager；`:81` 检查完整响应摘要，错误抛出后 `release.py:46` 的初始化快照无法完成，`:48` 保存不会执行；无吞异常分支。 |
| 测试真实性 | PASS。`test_release.py:82` 的 stub 拒绝任何非实际 LAN URL，旧 loopback 实现会失败；`:87` 验证匹配摘要成功，`:88` 验证错误摘要抛出指定异常。使用 BytesIO 模拟响应，不能证明真实网络监听，生产连通性留给安装阶段；`snapshot.py:112` 已静态核对真实调用链。 |
| 安全 | PASS。两变更文件扫描未出现 eval、shell=True、HTML 注入或硬编码凭据；`snapshot.py:80` 固定地址无用户输入拼接，helper 未增加 shell、SQL、权限或写入操作。 |
| 版本边界 | PASS。旧批准文件哈希的内存重建验证成功，未变功能继续依据旧完整报告。审查结论严格绑定本 candidateId，后续代码变更必须重新固定快照。 |

补充 schema 分支复核：`snapshot.py:62` 对 domestic 使用 `alembic_version`，对 overseas 使用 `overseas_alembic_version`，与 `hengxin-smart-image/backend/app/overseas/db.py:9` 及 `hengxin-smart-image/backend/migrations/overseas/env.py:19`、`:29`、`:39` 的实际迁移设置一致。`:65` 拼接对象仅来自这两个固定字面量，循环输入也为内部固定两侧，没有用户输入进入 SQL。`test_release.py:92` 执行真实 schemas 函数，mock 数据库元信息与子进程，并断言两侧完整 SELECT 及不同返回版本；旧统一表名代码会失败。第 8 行合同的真实数据库版本核验因此满足本次修复范围。

未发现最终差异需修复的 HIGH/MEDIUM 问题。

## 独立验证原始输出

命令：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
................................................................. [ 82%]
..............                                                           [100%]
79 passed, 7 subtests passed in 12.19s
```

进度行拼接自首次及轮询返回；退出码 0。对 `scripts/release/intranet/*.py` 和旧 `unify_release.py` 的全部 11 个文件调用 Python `compile()`，不生成编译产物：

```text
PYTHON_COMPILE_OK 11 files
```

本轮未改前端构建输入，未重做前端打包；基准报告记录的前端编译证据继续适用于未变内容。本报告不声称真实生产 init/verify 已成功，也不把主 Agent 提供的旧 Linux 测试描述为 reviewer 亲自执行。

由主 Agent 用本 candidateId 与本报告登记两阶段 PASS，再进行已授权的安装、init/verify 和无重启实证。不得向 `.needs-review` 写 clean。
