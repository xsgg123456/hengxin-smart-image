# 记录筛选与安全清理联合发布 · 最终候选独立审查

- candidateId：`d8b96549500601afbecbdbf29b68cc3a1423bbeeff53581e185fd2dd677c281b`。
- **Stage 1：PASS。Stage 2：PASS。** 本范围未发现待修复 HIGH/MEDIUM。主 Agent 可对同一候选登记两阶段 PASS；本结论是源码审查通过，不是生产部署验收通过。
- 范围：相对已批准业务快照 `e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced` 的8文件：`scripts/release/domestic-record-filters-{deploy,native,runtime,verify}.py`、`scripts/release/package-record-filters.py`、`scripts/release/test_record_filters_{release,native,backup}.py`。下文省略目录的 Python 文件均在 `scripts/release/`。
- 已读取 code-review skill、快照协议、Product-Spec/DEV-PLAN最新授权、联合发布合同全文、第二候选审查及业务批准/验证记录。本 reviewer 只读代码、独立运行本地验证并写本报告；没有修改代码、提交、部署、访问生产、spawn、写 clean 或登记批准。

## 快照与拆分复核

不是仅依据“原样移动”的声明：独立读取本候选文件映射，将 `test_record_filters_backup.py:9` 开始的完整主体插回 `test_record_filters_release.py:259` 的安装接线测试之前，再从映射移除新增 backup 文件，使用 `.codex/hooks/review_files.py:40` 的换行归一摘要及 `:52` 的完整快照算法重算。内存重组，不写回代码。输出如下：

```text
reconstructed_lines=327
reconstructed_previous_candidate=9b97053824ea3a40a3af959a6b1f587428a62f41123ba26d5fb27643249e87b1
expected_previous_candidate=9b97053824ea3a40a3af959a6b1f587428a62f41123ba26d5fb27643249e87b1
exit_code: 0
```

重建结果精确等于第二候选编号，证明其他受控文件全部保持，包括5个发布生产脚本、原生测试、先前已审业务/UI；被移动主体的每个字符和原位置一致。新增模块 `test_record_filters_backup.py:2` 导入 copy/pytest，`:4` 复用原 module/save/RELEASE，`:6` 创建独立 verify 模块实例，满足原 fixture 的运行前提。3个测试及1个 fixture 全部保留：`:9` 全表/列枚举、`:27` backup_env、`:43` restore/schema/column比较和 helper恢复、`:59` 失败不落COMPLETE且恢复 helper。原安装接线测试仍在 release `:259`。

## Stage 1 · 合同逐项对照

详细既有源码审查与真实 drain 异常复现见 `docs/RECORDS-CLEANUP-RELEASE-APPROVAL-20261022.md:9`、`:27`；以上完整快照重建证明可继承这些未变实现的证据。本轮已再次读取5个生产脚本和3个测试，逐项核对如下。

| 联合发布合同条目 | 结论与证据 |
| --- | --- |
| 1. 生产版本/schema/在途/服务/保护基线只读核实 | 代码完整。runtime `:28`/`:33` 固定国内0032、海外0020及旧前端0.2.48；`:57`/`:68` 准备前后拓扑核对，deploy `:21`/`:31` 切换前复核拓扑与在途查询。合同现场证据位于 `docs/RECORDS-CLEANUP-RELEASE-20261022.md:23`，本 reviewer 未重新连接生产，不将其称为自己的实测。 |
| 2. API、前端、三个原生更新；env/策略/凭据/资源及无关服务保持 | 完整实现。deploy `:46`/`:48`/`:54` 切换原生、API、前端；native `:72` 验证后端manifest全部哈希和共享模块，`:109` 统一校验前置条件后 `:123` 仅写三服务drop-in；runtime `:46` 保持配置，`:72` 保持其它容器/配置/非目标PID及环境摘要，`:95` 校验安装镜像与资源；native `:133` 复用环境/argv/策略核验。native测试 `:81`/`:101`/`:111`/`:138`/`:166` 和release `:88`/`:245` 本轮独立运行通过。 |
| 2. 原生准备与隔离smoke、完整恢复材料 | 完整实现。native `:86` 复用现有CLI环境、生成受控配置，`:92` 以codex用户运行临时目录smoke，成功后写PREPARED；`:100` 保存旧drop-in字节和摘要。native测试 `:129`/`:185` 通过；Linux UID1001真实smoke仍需主 Agent 在发布prepare执行。 |
| 3. 中文提交、0.2.49不可变包、隐私/哈希及隔离镜像安装 | 源码准备完整，实际执行待主 Agent。package `:11` 要求cleanup源码和回归文件，`:26` 拒遗漏/preview，`:34` 固定版本及schema并复用已审打包/安装流程。release `:29`/`:43`/`:52`/`:60`/`:64` 检查打包约束，`:259` 检查隔离安装接线。不得将文本接线检查称为实际镜像安装通过。 |
| 4. gate、暂停、drain、完整备份/隔离restore先于switch，无强杀、无迁移 | 完整实现。deploy `:35` 至`:46` 严格按序；verify `:26` 覆盖所有public表行/列/schema，`:37` 要求执行器与清理器已停，`:54` 完整dump，`:60` 隔离恢复，`:63` 再核源库后才写COMPLETE；deploy `:44`/`:52` 再验指纹。release `:147`/`:213` 与backup `:9`/`:43`/`:59` 通过。真实drain、SIGTERM和PG隔离恢复底层继承第二报告 `:36`/`:37` 的未变证据。 |
| 4. 失败保持关闭、暂停、补停两个cleanup，不倒库、不重放 | 完整实现，第一候选H1保持关闭。deploy `:77` 记录恢复阶段，`:82`/`:86` 尝试关闭/暂停，`:91` 无条件逐个停止DELETE与RETENTION，单个异常记录后继续；`:18` 拒重放。release `:171` 覆盖13注入阶段，`:194` 覆盖早期失败及第一个stop失败仍执行第二个，`:222` 验证清理标记先写；本轮均通过。第二报告 `:9` 的真实drain控制流复现可继承，未将mock单测冒充生产服务实测。 |
| 5. 首扫、历史失败正常重试、保护对象和正式入口/窄屏 | 自动门禁接线完整。deploy `:63` 先标记再启动cleanup，`:66` 首扫后再校验安装并开放；verify `:73` 验证401鉴权与默认mine契约，`:88` 校验首页字节。两条历史失败重试、保护文件字节及引用、正式登录筛选/自动清理页/窄屏截图和临时验收会话撤销，均留给主 Agent 部署后实际验收，本报告不宣称已完成。 |
| UI一致性、引导真实性、Spec漂移 | 本轮8文件无页面、文案、API或表增量；仅授权发布工具及测试。未发现新增业务范围。UI沿用已批准业务快照和 `docs/RECORDS-SCOPE-REVIEW-20261022.md:1` 的实渲染证据；本轮没有新UI对象，不虚构新页面/邻居页面或生产截图检查。 |

本轮发布源码要求无部分实现、未实现项；生产执行和现场验收是尚待完成的后续工作。

## Stage 2 · 质量与安全

- 原M1关闭：release测试由327行减至265行，备份测试70行；全部8文件不超300行。拆分按备份职责形成模块，精确快照重建及71项独立运行共同证明无遗漏。代码位置见 `test_record_filters_release.py:259`、`test_record_filters_backup.py:9`/`:27`/`:43`/`:59`。
- 错误处理保持：deploy `:77` 至`:96` 保存原错误并逐个执行恢复动作；verify `:55` 至`:62` 用finally恢复fingerprint助手。测试使用真实临时文件与实际deploy异常分支；backup测试模拟DB，不等于生产恢复测试。native `:166` 实算文件哈希；release `:194` 验证第二stop确实被调用，断言方向与失败前提正确。
- 安全检索8文件的 eval/exec、shell=True、危险HTML、前端敏感变量、sk-ant/sk-proj及个人路径标记无匹配。native `:66`/`:68` 限制路径和systemd展开字符；verify `:30` 严格限制表名后构造标识符；deploy `:101`/`:115` 拒绝-O绕过assert。native测试 `:33` 的private-value为合成fixture；/opt、/etc/systemd、/proc是已授权发布/核验路径。未发现新的硬编码秘密、可执行注入或范围外破坏动作。
- 视觉对比与业务代码继承上述精确未变快照；本次无新增UI，真实生产视觉验收仍未执行。未新增外部库/API用法或发现需外部确认的可疑模式，不引入无关依赖变更。

## 独立验证原始输出

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest -q scripts/release/test_record_filters_native.py scripts/release/test_record_filters_release.py scripts/release/test_record_filters_backup.py
.......................................................................  [100%]
71 passed in 1.43s
exit_code: 0
```

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m py_compile scripts/release/domestic-record-filters-runtime.py scripts/release/domestic-record-filters-deploy.py scripts/release/domestic-record-filters-verify.py scripts/release/domestic-record-filters-native.py scripts/release/package-record-filters.py scripts/release/test_record_filters_release.py scripts/release/test_record_filters_native.py scripts/release/test_record_filters_backup.py
stdout/stderr: (empty)
exit_code: 0
```

```text
domestic-record-filters-deploy.py: 117 lines
domestic-record-filters-native.py: 139 lines
domestic-record-filters-runtime.py: 116 lines
domestic-record-filters-verify.py: 92 lines
package-record-filters.py: 47 lines
test_record_filters_backup.py: 70 lines
test_record_filters_native.py: 198 lines
test_record_filters_release.py: 265 lines
```

`git diff --check` exit_code=0；仅已有CRLF转LF提示，无whitespace error。

审查开始和测试结束后 `review-status` 均为 currentId `d8b96549500601afbecbdbf29b68cc3a1423bbeeff53581e185fd2dd677c281b`，reviewedId `e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced`，changedFiles精确为上述8文件，approved=false。未发现代码漂移；普通Markdown报告不改变受控代码快照。主 Agent 应登记本报告与同一candidateId，再核对review-status后继续已授权发布；不可据本报告提前宣布生产成功。
