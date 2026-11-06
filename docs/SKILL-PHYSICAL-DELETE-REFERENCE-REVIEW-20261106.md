# Skill 多发布引用与再次发布差异审查

- candidateId：`d0f9a69016298f4d42eec4b116ced6d23c1aa9c989f4d78dae025336730f4901`。
- 基线：HEAD `50d70958e13d5065b21f5c706cc7c616bf4fa0eb`；批准候选 `a420ec57b625adc0e8e118b10a2c6c5d4781b1de3221b159e86a8e4c3c5cf55e`。完整基线证据见 `docs/SKILL-PHYSICAL-DELETE-FINAL-REVIEW-20261106.md:8` 和 `docs/SKILL-PHYSICAL-DELETE-TYPES-REVIEW-20261106.md:24`。
- 范围：相对基线全部差异，包含 7 个受控文件、实施合同新增多 release 规则及 CHANGELOG。受控文件为 `skill_maintenance.py`、`skill_references.py`、`test_skill_physical_maintenance.py`、前端 `package.json`、`skill-physical-package.py`、`skill-physical-runtime.py`、新增 `skill-physical-upgrade-tests.py`。
- 已读取 AGENTS.md、code-review Skill、HARNESS-REVIEW 协议、完整实施合同、Product-Spec.md:1415、DEV-PLAN.md:1642 及两份基线报告。只审查、运行隔离测试及写本报告；没有修复代码、提交、部署、生产 GC 或调用模型。
- 独立比较 review-state 的批准/候选全部文件摘要，仅上述 7 个受控文件变化；批准报告原始 SHA256 匹配凭据。开始和报告完成时 currentId 均为本候选。审查期间主 Agent 删除 CHANGELOG 末尾多余空行，并在 `docs/SKILL-PHYSICAL-DELETE-VALIDATION-20261106.md:51` 补记 0.2.65 切换、无 GC 恢复及本轮验证；已复核该文档 diff，属于证据说明，不改变实施合同或受控代码。复核 diff --check 已无错误。没有用旧结论覆盖新代码。

路径简写：M/=`hengxin-smart-image/backend/app/overseas/management/`，E/=`hengxin-smart-image/backend/app/overseas/execution/`，T/=`hengxin-smart-image/backend/tests/`，F/=`hengxin-smart-image/frontend/`，R/=`scripts/release/`。行号均针对本候选。

## Stage 1：Spec Compliance — PASS

未发现 HIGH/MEDIUM/LOW 未关闭问题。代码要求完整实现；0.2.66 正式发布和生产回收仍为后续执行验收，不由本报告推定完成。

| 合同要求 | 结论与证据 |
| --- | --- |
| 新规则：每个任务原始发布引用参与核对 | 完整。M/skill_references.py:52 新增默认开启的内容去重开关，`:78` 关闭时按 Job.id 保留每个任务；原属主、Conversation/Turn、删除状态检查没有绕过。M/skill_maintenance.py:29 关闭去重，`:30` expected 保留 owner/release/name/checksum 四元组。T/test_skill_physical_maintenance.py:45 真实 SQLite 创建第二 Job/Turn，同会话、同内容、不同 release，并真正准备两轮 control/round 输入。 |
| 新规则：归属核对后才按内容保全去重 | 完整。M/skill_maintenance.py:47 在所有输入验证完成后按 owner/name/checksum 合并；M/skill_references.py:83 preserve 默认内容去重不变。T/test_skill_physical_maintenance.py:67 同时跑 dry-run 和实际 GC，证明 2 jobs、4 inputs、1 historyContent；历史文件原字节及两个原 payload 不变，旧 release 仅剩 manifest，两份冻结清单仍解析并找到原历史文件。 |
| 新规则：真正无归属输入仍拒绝 | 完整。M/skill_maintenance.py:43 仍比较完整四元组；T/test_skill_physical_maintenance.py:91 用真实存在且内容有效的第三 release 替换一个磁盘输入，两个 Job 均未引用该 release，dry-run/实际回收都拒绝，安装库 fingerprint 和历史字节保持。不是用非法 checksum 代替无归属情形。 |
| 目标1：独立实体/小型索引/复用/完整字节、空目录与下载 | 完整，继承未变实现证据：M/skill_objects.py:21、`:87`，M/installed_catalog.py:57，M/skill_downloads.py:28，T/test_skill_object_storage.py:46。本次只改变核对引用枚举，不改变实体格式、读取或下载。基线完整报告:16 对应逐项验收仍适用。 |
| 目标2：真实清理中央、旧包及暂存，历史保留，完成后成功、净释放、失败恢复 | 完整。M/skill_cleanup.py:61、`:114`，M/skill_publication.py:35、`:91`，M/skill_preparation.py:90 未变；独立重跑清理/准备账本测试。本次正例实际删除旧树、负例证明没有删除，而非只断言接口返回。 |
| 目标3：在途阻删、不强停、更新继续读取旧冻结内容 | 完整。M/skill_references.py:23、`:27` busy/lock 判断未变，新开关只作用于终态 owners；M/skill_publication.py:133、M/skill_cleanup.py:74 未变。独立重跑 T/test_skill_physical_history.py:134、`:152` 等历史测试。 |
| 目标4：本会话副本、原清单核对、缺失补齐、非 Studio 保全、原 payload/文件不变及持久化 | 完整。E/skill_content.py:19、E/skill_history.py:22、`:89`、M/skill_references.py:64、`:83` 保全实现未变；新增跨 release 正例及独立历史/耐久/准备回归覆盖。新枚举没有跳过 owner 校验或 fsync。 |
| 目标5：旧索引可解析、引用驱动 GC | 完整。M/installed_catalog.py:35、`:180` 未变；M/skill_maintenance.py:27 修复丢失 release 的误报，`:66` 仍在全部任务排空后核对。T/test_skill_physical_maintenance.py:67、`:111` 证明真实回收后旧 manifest 及历史仍可用，没有按时间/开关推定删除资格。 |
| 目标6：API/worker 只读、publisher 受控写、历史根/业务/属主限定 | 完整。M/skill_publication.py:20、M/skill_references.py:44、`:64` 未变。R/skill-physical-runtime.py:105 仅接受唯一、exact source/target、bind、可写且环境根一致的既有挂载；`:129` 强制原 mount 全部选项不变，`:132` 全配置比较。新增测试覆盖错误 source/type/read_only/env、重复 bind、选项变化及 API 非授权挂载。 |
| 顺序1：存储兼容及安装/冻结/下载验证 | 完整，继承未变 M/skill_objects.py:21、M/skill_install.py:118 和 T/test_skill_offline_objects.py:36 的基线证据；本次维护测试实际使用旧 schema 树并保留原索引。 |
| 顺序2：真实文件历史保全与跨会话/链接拒绝 | 完整，E/skill_history.py:12、`:22` 和 T/test_skill_physical_history.py:87、`:179`、`:204` 未变，独立历史/清理回归再次通过。 |
| 顺序3：首次/末项、重试、权限/冲突、磁盘错误、并发及持久恢复 | 完整。未变 M/skill_publication.py:152、M/skill_publisher.py:25 和 T/test_overseas_skill_transfers_failures.py:42 继承基线完整报告:29；独立重跑清理、准备和历史耐久，未改变事务/恢复路径。 |
| 顺序4：现有确认框、真实释放提示、前端类型/构建/浏览器 | 运行实现全部未变；F/package.json:3 仅 0.2.65→0.2.66。继承基线完整报告:32、`:56` 的前端 529 项、类型/构建及实际页面/邻居比较。本轮未重新运行前端或打开浏览器，不将旧生产构建称为 0.2.66 新构建。 |
| 顺序5：固定快照、中文提交、制品隐私、安装身份、基线、排空、备份、国内服务 | 工具完整，正式执行待主 Agent。R/skill-physical-package.py:36 要求当前 0.2.65，`:118` 要求目标 0.2.66；独立用实际 baseline-0.2.65.json 验证 17 文件范围通过，0.2.64 被拒。`:62` 受审提交/干净源码、`:84` 隐私、`:112` 固定提交构建等门禁未删。R/skill-physical-deploy.py:28、`:88`、`:144` 仍核对候选/实际配置、安装证明和排空。 |
| 顺序6：迁移前备份、全历史核对、原索引、净回收量及生产健康 | 工具完整，生产 GC 尚未完成。R/skill-physical-maintenance.py:88、R/skill-physical-backup.py:137、`:162`、R/skill-physical-recovery.py:29 未变。新规则使合法多 release 可核对，并未跳过私有 UDS、维护关闭接纳、DB 恢复验证、全部 reader 切换或最终历史/净占用门禁。不得把本轮测试临时树释放量当生产释放量。 |

UI 一致性、引导真实性与 Spec 漂移：没有 UI 模板/样式、公开路由、表结构、产品功能变化。新引用规则对应实施合同 `docs/SKILL-PHYSICAL-DELETE-20261106.md:26`，再次发布版本和 exact bind 继承对应 `Product-Spec-CHANGELOG.md:958`。没有部分实现或未实现代码项；正式发布、迁移和实际净量属于明确待执行步骤。

## Stage 2：Code Quality — PASS

Stage 1 通过后审查质量、安全与验证真实性；未发现新增缺陷。

| 检查 | 证据与结论 |
| --- | --- |
| 命名、结构、兼容性 | M/skill_references.py:52 的 keyword-only 参数默认 True，现有 preserve/preparation 调用不变；M/skill_maintenance.py:47 明确核对/保全去重时点。6 个受审 Python 文件均可编译，分别 102/120/163/166/135/64 行，无超过 300 行。 |
| 失败关闭及安全扫描 | M/skill_maintenance.py:43 在任何回收开始前拒绝未知输入，`:79` 以后才进入准备/保全/发布。R/skill-physical-runtime.py:106、`:129` 不放松历史路径身份和挂载选项。受审 Python 全文扫描 eval、innerHTML、前端密钥前缀、密钥/密码模式、用户绝对路径无匹配；没有新增动态 SQL、网络暴露或真实密钥。固定生产路径为既有白名单。 |
| 测试真实性 | T/test_skill_physical_maintenance.py:45 真创建两个数据库 Job/Turn 并 materials.prepare，`:67` 真 GC 后读取历史，`:91` 第三 release 先 frozen_package 验证有效再证明拒绝。R/skill-physical-upgrade-tests.py:30 至`:56` 的手工合并单测不足以单独证明 Compose 合并，本 reviewer 另跑真实 Docker Compose config；结果见下。 |
| 实际 Compose 合并 | reviewer 用 Docker Compose 5.1.3、隔离临时 JSON、生产式 API 只读库/publisher 原生 bind/其他服务配置，先 config 归一基线，再应用新 overlay 的 volumes=[]，实际 config 输出通过 check_overlay，publisher 原 mount 逐字段相等；不启动容器。主 Agent 另对生产实际 Compose 链只读 config 验证，日志 `output/skill-physical-20261106/actual-compose-upgrade-check.log:1` 已读取，保持历史 mount/API/业务配置。 |
| 视觉 | F/package.json:3 仅版本变动；继承完整基线报告:56 的真实确认/失败/成功/窄屏与邻居页面目视对比，不把本轮无 UI 变化伪报成重新打开页面。 |
| 既有风险边界 | 完整基线报告:124 的 9 项既有全后端失败与`:154` 的依赖审计风险仍保留；本轮未改依赖、锁文件或相关失败模块。PASS 不代表全后端无既有失败或依赖无漏洞。 |

Docker 官方合并规范说明 volumes 以 target 为唯一键追加/合并；本轮不使用 `!reset` 清空指令，且已实测空 overlay 列表保持原挂载：[Docker Compose merge](https://docs.docker.com/reference/compose-file/merge/)。

## 原始验证输出

reviewer 独立执行五个后端文件：maintenance、history、preparation_accounting、history_durability、physical_cleanup（Windows 项目 .venv），无 skip，exit 0：

```text
52 passed, 2 warnings in 91.08s (0:01:31)
```

两个 warning 是既有 Starlette/httpx 与 anyio 弃用提示；本轮没有模拟整机掉电，不把 Windows fsync 行为称为新的 Linux 持久化验证。未变 Linux 真实身份基线证据可继承，0.2.66 正式安装仍须重新执行。

reviewer 独立 Windows 发布测试，exit 0：

```text
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.392s

OK
.....
----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

reviewer 独立 WSL Ubuntu 发布测试，exit 0：

```text
.....
----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.313s

OK
```

WSL 启动另提示 localhost 代理未映射；测试不依赖外网，测试进程均成功。

reviewer 独立真实 Compose、编译、基线及快照核验原始输出：

```text
5.1.3
REAL_COMPOSE_EXISTING_BIND_EXACT_PASS
COMPILE_OK 6
REAL_0265_BASELINE_17_FILES_PASS 17
STALE_BASELINE_REJECTED Unexpected physical baseline
PRIOR_REPORT_HASH_VALID True
BASE_HEAD 50d70958e13d5065b21f5c706cc7c616bf4fa0eb
```

主 Agent 生产实查日志（本 reviewer 读取，没有另连生产）：

```text
production-resume-no-gc.log:
API_PUBLISHER_NATIVE_FRONTEND_CONTEXT_VERIFIED_GATE_CLOSED
READ_ONLY_MAINTENANCE_CANCELLED_NO_GC
RELEASE_RESUMED_REQUIRES_BROWSER_VISUAL_ACCEPTANCE_GC_SEPARATE
all-release-input-check.json:
{"jobs": 138, "frozenReleaseReferences": 38, "inputs": 276, "unaccounted": 0}
actual-compose-upgrade-check.log:
{"status": "ACTUAL_COMPOSE_MERGE_VERIFIED", "existingHistoryMountUnchanged": true, "apiAndBusinessConfigurationUnchanged": true}
```

旧 `unaccounted-inputs.json:1` 是 35 个去重 owner 内容、276 inputs、14 个误报路径；新逐 Job 核对是 38 个 release 引用、0 个未归属。二者口径不同，不能将 14 个路径误报写成 14 个无主内容或已删除内容。恢复日志只证明主 Agent 记录的未 GC 恢复过程，不是本 reviewer 的独立生产全树重验。

## 交接

本报告仅批准同一 candidateId 的两阶段代码审查，由主 Agent 用 review-approve 登记。后续必须完成受审提交、0.2.66 完整构建/隐私检查、真实安装角色测试、最新生产基线及恢复验证、维护排空、17 文件统一 reader 升级、私有 UDS 回收、全量历史保全/下载选择准备/国内服务健康与同范围净释放验收。正式发布尚未开始，不能宣称生产已回收或真实模型续聊已验证。
