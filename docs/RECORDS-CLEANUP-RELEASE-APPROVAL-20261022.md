# 记录筛选与安全清理联合发布 · 第二候选独立审查

- candidateId：`9b97053824ea3a40a3af959a6b1f587428a62f41123ba26d5fb27643249e87b1`。
- **Stage 1：PASS。Stage 2：FAIL。** 原 HIGH 已关闭；本候选有 1 项 MEDIUM 文件大小不符合 code-review 标准，不能登记两阶段 PASS。文件名含 APPROVAL 不代表批准，以本段结论为准。
- 审查范围：相对已批准业务快照 `e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced` 的七文件：`scripts/release/domestic-record-filters-{runtime,deploy,verify,native}.py`、`scripts/release/package-record-filters.py`、`scripts/release/test_record_filters_{release,native}.py`。下文未写目录的 Python 文件均位于 `scripts/release/`。
- 已读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、Product-Spec/DEV-PLAN 顶层授权、联合发布合同全文及首候选失败报告，并核对复用的排空、原生、隔离恢复、镜像安装和打包代码。业务与 UI 继承 `docs/CLEANUP-UNIFICATION-APPROVAL-20261022.md:3`、`docs/RECORDS-SCOPE-REVIEW-20261022.md:1` 已审范围，不重跑全业务。
- reviewer 只读实现并写本报告，未修复、未提交、未打包、未部署、未访问生产、未 spawn、未写 clean。审查开始和结束的 currentId 相同，changedFiles 精确为上述七文件，未发现代码漂移。

## Stage 1 · 原 HIGH 闭环

首候选的问题是异常处理依赖过晚写入的 `CLEANUP_MAY_HAVE_DELETED`，早期排空失败时可能留下旧清理器运行。本候选 `domestic-record-filters-deploy.py:77` 进入异常处理后记录恢复阶段、重关入口、暂停通道；`:91` 无条件遍历 DELETE/RETENTION，`:94` 对单个停止失败落 `STOP_REQUIRED` 后继续下一个。`:63` 标记仍先于清理器启动，继续承担不可回滚的证据职责，不再控制是否补停。

不是仅依赖单测数量：独立复现调用真实 `retention-management-drain.py:62` 的 stop 函数，仅模拟第二服务 PID 从快照20漂移至21。`:66` 的真实快照断言在第二服务停止前失败，部署真实 except 分支补停两个清理器，未存在重启标记。原始输出：

```text
error=Cleanup process drift
drain_stop_attempts=["hengxin-retention"]
handler_stop_attempts=["hengxin-domestic-deletions", "hengxin-retention"]
cleanup_restart_marker=False
recovery_phase=drain
REAL_DRAIN_EXCEPTION_RECOVERY_PASS
exit_code: 0
```

该复现使用临时目录、pytest MonkeyPatch 和 cutover fixture，不操作系统服务。`test_record_filters_release.py:167` 的13阶段注入现在无条件断言两个补停；`:194` 另覆盖 API 早期停止失败、首个 cleanup 停止超时仍继续第二个；`:222` 保留首扫失败及标记先写证据。原 H1 判定关闭。

## Stage 1 · 合同逐项对照

| 合同条目 | 结论、实现及验证证据 |
| --- | --- |
| 1. 只读核实生产版本、schema、在途、服务及保护基线 | 发布前检查接线完整。`domestic-record-filters-runtime.py:28`、`:33` 强制国内0032/海外0020/前端0.2.48；`:57`、`:68` 准备前后拓扑一致，deploy `:21` 切换前再次比较、`:31` 核实在途查询可读。合同 `docs/RECORDS-CLEANUP-RELEASE-20261022.md:23` 后记录主 Agent 的现场证据；reviewer 未重复连接，不把22对象/45 facts写成独立实测。 |
| 2. API/前端/三个国内原生安装新代码 | 完整实现。deploy `:46`、`:48`、`:54` 顺序切原生/API/前端；native `:72` 核验全部 manifest 后端文件及共享cleanup必需模块；`:123` 只写精确三服务的受控 drop-in；runtime `:95` 核验API镜像身份和健康。native测试 `:166` 真写临时文件检查哈希损坏和缺模块拒绝。 |
| 2. 保持 env/凭据/资源/argv/策略，海外及其他容器保持 | 完整实现。runtime `:46` 仅允许API image变化并额外保持build；`:72` 校验其它容器ID/image/mount、配置文件、非目标原生PID及环境摘要；`:99` 保持容器资源限制。native `:133` 复用 `retention-management-native.py:119` 的cwd/policy/env/argv检查，`:138` 限定配置文件集合仅受控override变化。测试release `:88`、`:245` 与native `:137` 覆盖漂移拒绝。 |
| 2. 原生准备、备份、受控配置与烟测 | 完整实现。native `:86` 复用当前CLI环境，底层 `member-release-runtime.py:152` 先核对依赖锁再复用venv；native `:100` 保存原drop-in字节与SHA256，`:109` 切换要求备份/准备/排空标记、所有PID为0、文件和预生成配置无漂移。`:19` 的smoke限定UID1001、真实导入路径及TemporaryDirectory，正向清四类合法链接、负向拒未知链接并保留sentinel；`:94` 成功才写NATIVE_PREPARED。native测试 `:81`、`:92`、`:101`、`:110`、`:185` 验证接线。Linux真实UID1001 smoke由生产prepare执行，本地mock测试不冒充已执行。 |
| 3. 中文提交、0.2.49不可变包、隐私/哈希和隔离镜像安装 | 准备代码完整，真正提交及制品执行仍待主 Agent。package `:11` 强制cleanup模块和测试，`:26` 拒遗漏及独立预览，`:34` 固定版本/schema。复用 `package-overseas.py:180` 从已审干净commit逐文件读取和隐私扫描，`:206` 绑定commit/candidate及哈希，`:214` 归档写前写后验证。`overseas-deploy.py:29` 校验镜像源文件哈希、network none安装测试成功才写镜像凭据。测试release `:29`、`:42`、`:51`、`:59`、`:64` 覆盖包约束。 |
| 4. 入口关闭、暂停、排空不强杀，cleanup先停 | 完整实现。deploy `:35` 关闭入口、停API、暂停后排空；`retention-management-drain.py:65` 先停两清理器，`:71`、`:74` 验证CLI/variants及API持久交接，`:80` 所有原生PID须0。API stop复用 `api-retry-deploy.py:130` 的docker timeout=-1；原生stop复用 `retention-management-native.py:90` 的SIGTERM和限时等待，无SIGKILL。release测试 `:147` 检查调用次序，原异常缺陷另有上节真实控制流复现。 |
| 4. 完整数据库备份、隔离restore、全表指纹，之后才切换 | 完整实现。verify `:26` 枚举全部public表所有行列及schema；`:37` 要求两停止标记；`:54` 完整pg_dump；`:60` 隔离恢复比对，`:63` 再比源库，`:65` 最后写COMPLETE。复用 `member-release-backup.py:114` 使用生产PG镜像、network none临时数据库。deploy `:42`、`:44`、`:52` 在切换/恢复消费者前校验。release测试 `:213`、`:259`、`:293`、`:309` 覆盖未完成备份阻止切换、列/schema比较与失败不落COMPLETE。没有本轮迁移或自动倒库入口。 |
| 4. 失败阶段记录、入口关闭、暂停及清理补停，不倒库 | 完整实现；原H1关闭。deploy `:77` 至`:96` 保存阶段、分别尝试关闭入口/暂停/两个清理器，记录需要人工恢复的失败；`:18` 拒绝重放。测试release `:167`、`:186`、`:194`、`:222` 及独立真实drain复现支撑。该保证针对可执行的恢复动作；不把停止请求成功解释为所有基础设施故障均可自动修复。 |
| 5. 首扫、失败会话正常重试、保护对象、正式入口/窄屏验收 | 首扫和恢复入口门禁接线完整：deploy `:63` 至`:71` 先标记、启动、等待首扫，核验安装后才解除暂停/开入口；`retention-management-verify.py:40` 使用数据库时钟，`:53` 要求持久完成回执与新鲜心跳，`:83` 验证未重启。verify `:73` 验证记录路由鉴权与默认mine、`:88` 核对首页字节。两条失败会话重试、22保护对象/45facts复核、正式登录筛选/清理页/窄屏截图及撤销验收会话属于部署后的现场验收，本报告不宣称已完成。 |
| UI一致性、引导真实性、Spec漂移 | 七文件无页面、文案、API或表增量；本轮为已授权发布工具，未发现额外业务功能。原UI沿用上述已批准业务快照和视觉证据，本次没有新视觉对象，不以静态脚本检查声称完成生产页面视觉复验。 |

Stage 1 未发现未实现或部分实现的本轮发布代码要求。现场执行项目明确保留为后续验收，不属于本次源码审查已经验证的结果。

## Stage 2 · MEDIUM

### M1：发布回归文件327行，超过技能300行标准

`.agents/skills/code-review/SKILL.md` 的 Stage 2 明确要求“文件不超300行”。`test_record_filters_release.py:1` 至`:327` 共327行，混合包验证、cutover fixture/异常路径、全库备份恢复以及安装测试接线；其余六文件47至198行。

这不是运行功能缺陷，但不符合本次要求的质量标准，不能写成两阶段PASS。建议将 `test_record_filters_release.py:259` 开始的备份恢复用例及其fixture抽到独立测试模块，保持现有断言和发现范围，重跑专项并重新固定candidate后复核。本 reviewer 不修改实现。

## Stage 2 · 其它检查

- 职责与错误处理：运行时、原生、备份验证、切换、打包已分离；deploy `:77` 保持原异常再抛出，native `:109` 在写服务配置前统一检查全部前置条件；verify `:55` 的临时fingerprint替换有finally恢复。未发现新增重复业务逻辑或缺失类型约束导致的实际错误；Python脚本没有TypeScript any问题。
- 测试真实性：71项实际运行通过。native `:81` 使用真实临时文件备份/写入，`:166` 真算哈希；release `:167`/`:194` 真走deploy异常分支，备份测试 `:293` 真比较预期对象但mock数据库，不能证明生产PG已经恢复成功。独立补充真实drain异常分支，避免只mock drain入口掩盖原H1。`test_record_filters_release.py:321` 是文本接线检查，仅支持存在配置，不当作真正镜像安装证据。
- 安全扫描：对七文件检索 eval/exec、shell=True、硬编码password、sk-ant/sk-proj、VITE敏感变量、危险HTML及个人绝对路径，无匹配。native `:66`、`:68` 限定发布路径并拒绝systemd展开/换行/引号；verify `:30` 对表名正则校验后拼SQL标识符；deploy `:101`/`:115` 拒绝Python优化模式绕过assert。测试fixture的 `private-value` 是合成数据（native测试 `:33`），不是实际密钥。没有本轮待确认的可疑外部库安全模式，因此未发起无关网络检索。
- 绝对路径均为本合同要求的 `/opt` 发布/备份、`/etc/systemd` 三受控配置及只读 `/proc` 核验路径；smoke只在临时目录创建链接，不向 `/opt/codex` 写入（native `:26` 至`:46`）。不将正常发布路径误报为隐私泄露。
- 视觉对比：无新UI，沿用 `docs/RECORDS-SCOPE-REVIEW-20261022.md` 中实际预览/正式本地截图对照。本 reviewer 未重新打开生产页面；正式入口及窄屏仍为合同第5步现场验收，不提前勾选。

## 独立编译和测试原始输出

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest -q scripts/release/test_record_filters_native.py scripts/release/test_record_filters_release.py
.......................................................................  [100%]
71 passed in 1.26s
exit_code: 0
```

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m py_compile scripts/release/domestic-record-filters-runtime.py scripts/release/domestic-record-filters-deploy.py scripts/release/domestic-record-filters-verify.py scripts/release/domestic-record-filters-native.py scripts/release/package-record-filters.py scripts/release/test_record_filters_release.py scripts/release/test_record_filters_native.py
stdout/stderr: (empty)
exit_code: 0
```

```text
domestic-record-filters-deploy.py: 117 lines
domestic-record-filters-native.py: 139 lines
domestic-record-filters-runtime.py: 116 lines
domestic-record-filters-verify.py: 92 lines
package-record-filters.py: 47 lines
test_record_filters_native.py: 198 lines
test_record_filters_release.py: 327 lines
```

审查末 `review-status`：currentId仍为 `9b97053824ea3a40a3af959a6b1f587428a62f41123ba26d5fb27643249e87b1`，reviewedId为 `e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced`，changedFiles仍为上述七文件，approved=false。报告只绑定该快照；修复 M1 后主 Agent 必须重新prepare并复核，不得用本报告登记两阶段PASS。
