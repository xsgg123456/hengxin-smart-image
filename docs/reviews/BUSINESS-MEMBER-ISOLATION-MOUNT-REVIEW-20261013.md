# 成员隔离发布挂载顺序修复：独立增量审查

- 日期：2026-10-13；reviewer：独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`46c769d9e1b1c8f340a8d713c0406a2526334201306e3991751d8d325035f044`。
- HEAD：`a91ecbfe5901bd9351ec584a59f6d5a1737b8380`。
- 继承的已审快照：`99c8fa9dd583842ba26d3a4ee75e0b7c3ac7ba195be4aa359ec50fb87596916b`；报告：`docs/reviews/BUSINESS-MEMBER-ISOLATION-RELEASE-REVIEW-20261013.md`。
- **Stage 1：PASS；Stage 2：PASS。未发现本增量须修复的 HIGH / MEDIUM 问题。**

## 范围与版本边界

审查计划：核实候选及旧报告继承范围；逐项审查挂载规范化合同和两条消费路径；独立复跑发布测试、执行调用链故障注入、编译并验证包内模块闭包；结束时再次核对候选。

已读取 AGENTS、code-review skill、快照协议、旧完整报告及源合同。源合同为 `Product-Spec.md:1081`、`DEV-PLAN.md:1`、`docs/BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md:9`，本修复要求位于后者第28行。

`git diff` 和 `review-status` 一致确认：相对旧已审代码，只有 `scripts/release/member-release-runtime.py:34` 与 `scripts/release/member-release-topology-tests.py:17` 变化；普通 Markdown 发布记录新增根因段。未改前后端、迁移、维护工具、依赖或 UI，旧报告第25–39行的完整业务/发布矩阵与第47–53行未变代码质量结论按该范围继承。未重新声称执行旧全套后端、前端、真实数据库或浏览器验收。

本 reviewer 未连接生产、未停服务、未迁移、未执行人员清理、未改产品代码、未提交，亦未登记 approval。普通 Markdown 报告不改变代码快照。

## Stage 1：Spec Compliance — PASS

| 合同要求 | 结论与证据 |
|---|---|
| 相同挂载仅乱序不得产生拓扑漂移 | ✅ 完整实现。`member-release-runtime.py:35` 解析 inspect 原文，`:37` 仅按 `Destination` 排序；`:57`、`:72` 的拓扑输入均调用 `live()`，`:77` 保存排序后的完整挂载对象。新回归 `member-release-topology-tests.py:17` 验证倒序仍相等；本 reviewer 另以7容器 fixture 执行真实 `topology()`，乱序前后完整拓扑相等。 |
| 保留所有字段，真实路径、权限及其它字段变化仍拒绝 | ✅ 完整实现。`member-release-runtime.py:37` 没有投影、过滤、去重或改写挂载字典。新回归 `member-release-topology-tests.py:26` 验证 Source/RW/Type 和删除挂载。补充调用链实验逐一变更 Source、RW、Type、Destination、Mode、Propagation、Name、额外字段，以及增加/删除挂载，真实 deploy 门禁与 installed verifier 均拒绝。 |
| prepare 与生产切换使用同一规范化原则 | ✅ 完整实现。`member-release-runtime.py:176` 取基线，`:181` 保存，`:197` 重新比较；`member-release-deploy.py:9` 导入同文件，`:54` 读取准备基线，`:55` 在关闭入口前完整比对。独立实验运行真实 `deploy()`：乱序通过拓扑门禁进入下一预检；上述10类变化在该门禁抛错，未进入后续预检/切换。 |
| 安装后逐容器挂载验收也覆盖修复 | ✅ 完整实现。`member-release-verify.py:10` 独立导入同一 runtime；`:28` 使用该模块真实 `live()`，`:30` 与准备基线完整比较。独立实验通过真实 `api_sources()` 遍历三组7容器，倒序通过，真实字段/数量变化被拒绝。外部 IO 使用合成 fixture，不冒充镜像源码或生产命令实测。 |
| 保留三套 Compose、native、共享 Skill 及发布保护 | ✅ 本修复未改相关逻辑。`member-release-runtime.py:59`、`:75`、`:78` 保留标签/配置/ID/native/edge 指纹；`:119` 仍只允许 image/build 变化；`:184` 校验现挂载；`:195` 校验 Skill。旧报告第30–37行覆盖的排空、备份、迁移行保护、验收及失败关入口逻辑继续有效，相关发布回归本轮72项通过。 |
| 修复后重新审查、提交、打包、安装，不沿用失败准备包 | ✅ 源码支持此流程。`package-overseas.py:79`、`:152` 要求干净已提交、已审源码，`:178` 固定新 commit/candidate；`member-release-runtime.py:99` 固定已测镜像ID，`:198` 只有最终拓扑一致才写 PREPARED。本报告只批准当前源码；新提交/新包/实际镜像安装/新 prepare 及部署仍由主Agent后续执行，不能由本报告代替。 |
| 实查/固定包/安装、成员迁移保留及四人清理边界 | ✅ 无需求漂移。发布合同第9–14行六步骤没有被本修复改写；旧报告第25–29、34–38行逐项证据继承。`member-release-deploy.py:23`、`:28`、`:76` 保留迁移/行保护和清理后置边界；本增量没有新增人员、删除或授权行为。 |
| 引导真实性、UI一致性与 Spec 漂移 | ✅ 本增量不涉及页面或文案；两处代码差异均直接对应发布记录第28行。旧报告第39行的 UI 继承边界不变，无新增页面/API/表/组件；本轮无需新增设计数值或邻居页面对比。 |

完整实现：上述挂载顺序修复及保护要求。部分实现、未实现：本次增量源码范围内未发现。生产部署、人员清理及最终线上验收尚未完成，不作为本次源码缺陷或已经实现的线上效果。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：Code Quality — PASS

| 维度 | 结论与证据 |
|---|---|
| 命名、结构、文件规模 | ✅ `member-release-runtime.py:34` 在统一读取入口规范化，避免各消费处重复；文件231行。新测试 `member-release-topology-tests.py:17` 使用独立 deepcopy，文件147行，均低于300行。未增加依赖。 |
| 测试真实性 | ✅ 72项独立通过。新用例基线 skills 挂载 `RW=False`，修改为 True 确实构成权限漂移（`member-release-topology-tests.py:20`、`:26`）；每次变化重建原数据，避免累积污染。本 reviewer 另直接运行真实 topology/deploy/api_sources，覆盖真实读取函数与两个不同模块导入实例，补足新单测本身只调用 live 的边界。 |
| 安全扫描与错误处理 | ✅ 对两份变更文件扫描 eval、innerHTML、前端secret变量、硬编码sk密钥及 shell=True 无命中。新增代码 `member-release-runtime.py:35` 继续使用固定参数数组；`:37` 不吞异常、不丢失权限或未知字段、不生成生产写操作。缺字段仍会失败，未引入静默跳过。 |
| 模块闭包与编译 | ✅ 用当前 `package-overseas.py:60` 的选择器将19份实际发布 helper 复制到独立临时目录，全部 compileall 通过，真实导入 `member-release-deploy.py` 及其依赖成功；五份 member-release 运行模块均存在（`package-overseas.py:29`、`:56`）。72项同时包含维护 CLI 独立目录导入测试（`test_package_overseas.py:140`）。 |
| 视觉对比 | 不适用当前增量：`git diff` 仅两份 Python 文件；未变 UI 沿用旧报告第39行所引用实际视觉证据。本 reviewer 本轮未打开页面，不宣称完成线上视觉验收。 |

安全问题：未发现本增量引入的安全问题。代码质量问题：未发现须修复项。旧依赖风险保留旧报告第52行的范围，不因本修复扩大“全部依赖安全”的结论。

## 独立验证原始输出

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/member-release-tests.py scripts/release/member-release-topology-tests.py scripts/release/test_package_overseas.py -q --tb=short`，exit 0：

```text
........................................................................ [100%]
72 passed in 3.08s
```

额外本地调用链实验使用 Python stdin，保留真实 `live()`、`topology()`、`deploy()` 的拓扑门禁、`api_sources()`；仅 mock 外部命令/文件存在性/摘要/版本，部署成功方向在下一预检处主动停止。所有 fixture 数据合成，未连接 Docker/SSH/生产。exit 0：

```text
REAL_TOPOLOGY_AND_INSTALLED_VERIFIER_ORDER_PASS: 7 containers
DEPLOY_AND_INSTALLED_VERIFIER_DRIFT_REJECTION_PASS: 8 field mutations + mount add/remove
EXTERNAL_IO_MOCKED_NO_PRODUCTION_CONNECTION_OR_MUTATION
```

包内 helper 闭包使用 `compileall.compile_dir(target, quiet=1, force=True)`；编译函数返回 True，随后真实导入发布模块，exit 0，原始输出：

```text
PACKAGED_RELEASE_CLOSURE_IMPORT_PASS: 19 selected helper files
COMPILEALL_PASS: selected release helper closure
scripts/release/member-release-runtime.py: 231 lines
scripts/release/member-release-topology-tests.py: 147 lines
```

`git diff --check` 无输出，exit 0。安全模式 rg 无匹配，exit 1 表示无命中，不是扫描失败。

## 主Agent提供的真实环境补充证据

已读取 `output/member-topology-order-check.py:7` 和 `output/member-topology-order-check.log:1`：调用器在单独进程包装旧 live，按同一 Destination 规则排序，并只规范化已保存基线的数组顺序；第16行连续3次比较完整 topology。脚本没有修改远程源码、配置或服务。以下是主Agent执行产生的日志，不是本 reviewer 再连接生产的结果：

```text
THREE_READONLY_LIVE_TOPOLOGY_COMPARISONS_PASS: all fields retained; only list order normalized
```

该证据支持根因与规范化方案，不等于新发布包已通过实际安装、准备、迁移或最终验收。`output/member-topology-diff.py:8` 的比较器也保留字段差异检测；原始失败范围由发布记录第28行记载。

## 快照交接

审查开始与全部验证结束时 `review-status` 均为同一候选，无代码漂移。验证结束原始输出：

```json
{"currentId": "46c769d9e1b1c8f340a8d713c0406a2526334201306e3991751d8d325035f044", "reviewedId": "99c8fa9dd583842ba26d3a4ee75e0b7c3ac7ba195be4aa359ec50fb87596916b", "changedFiles": ["scripts/release/member-release-runtime.py", "scripts/release/member-release-topology-tests.py"], "approved": false}
```

主Agent可对本候选登记本报告及两阶段 PASS。报告落盘后仍须核对 currentId；后续任何代码变化均重新 prepare/复核。继续按发布记录第28行提交、新打包、重跑安装和准备，随后才可推进生产切换与验收。
