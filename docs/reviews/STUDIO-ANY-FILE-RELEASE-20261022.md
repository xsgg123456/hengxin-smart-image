# 海外任意格式附件 0.2.48 发布增量独立审查

- candidateId：`b706bcb51b6d4b1515457a1b904a3b4dfd3e89177d59f6b736b0459c5bf75cee`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。本轮没有遗留 HIGH / MEDIUM 阻断。
- 范围：`Product-Spec.md:1` 的追加发布授权、`docs/STUDIO-ANY-FILE-PRODUCTION-20261022.md:5` 的四步发布合同；本轮发布代码为 `hengxin-smart-image/frontend/package.json:3` 及新增的三个 `scripts/release/*any-file*` 文件。审查其实际继承的打包、部署、备份、恢复和保护链路。
- 使用 `.agents/skills/code-review/SKILL.md`。只执行读取、隔离测试和本报告写入；没有修改产品/发布代码、提交、部署、登记批准或写 clean。
- 本报告批准的是发布候选代码与本地准备验证；**不是生产发布完成证明**。真实提交后 tar 审计、Linux 安装镜像/500 MB 容量、备份恢复及线上上传下载仍须执行，不计为已通过。

## 快照及此前功能审查

开始与结束前均执行 `python .codex/hooks/harness.py review-status`：当前编号均与上方 candidateId 相同；相对旧批准候选 `1f1a7ee0768ade40924a66e9b92ac6557a06a5ea55e4914d65c8df209aa37b01`，仅以下四个文件变化：

```text
hengxin-smart-image/frontend/package.json
scripts/release/overseas-any-file-deploy.py
scripts/release/package-any-file.py
scripts/release/test_any_file_release.py
```

因此本次没有将旧结论直接覆盖变化后的功能代码：实际功能代码及其测试哈希未变，旧独立报告 `docs/reviews/STUDIO-ANY-FILE-20261022.md:21` 的逐项验收仍对应相同实现。版本文件只有 0.2.47 → 0.2.48 一处差异，没有依赖变动。主 Agent 审查中补充生产文档的验证记录，不改变受控代码快照。

## Stage 1：Spec Compliance — PASS

| 合同条目 | 结论、代码位置及证据 |
| --- | --- |
| 任意格式、三入口、原件保真、500 MB/100附件、权限隔离、图片安全预览 | 保持完整实现。本轮无功能漂移，沿用上述旧报告逐条结论，证据覆盖 `hengxin-smart-image/backend/app/overseas/studio/files.py:26`、`backend/tests/test_studio_any_file.py:17`、`frontend/src/api/overseas/studio.ts:48`、`frontend/src/views/overseas/studio/OverseasStudio.vue:29`（后三者均位于 `hengxin-smart-image/`）。没有新增解析、解压、执行或收费生成行为。 |
| 固定当前生产基线并发布 0.2.48 | 完整实现。`scripts/release/overseas-any-file-deploy.py:13` 固定前后版本、镜像、release、国内原生目录；`:40` 校验国内0032、海外0020和四张现有表。继承的 `overseas-archive-deletion-deploy.py:104` 校验镜像健康、3 GiB、restart、原生路径及覆盖优先级。独立测试 `test_any_file_release.py:184` 对版本/镜像/目录标签/环境/覆盖/内存/restart漂移逐个拒绝。生产基线来源为主 Agent 只读实查，本 reviewer 未重复连接生产。 |
| 保留现有 owner 和任意 Skill 状态/版本，不 seed、不迁移 | 完整实现。新入口没有导入 skill-availability 的部署/owner修改链；`overseas-any-file-deploy.py:48` 要求唯一有效现有UUID，`:56` 固定实际环境与schema；`:79` 与备份全部业务行指纹精确比对；`:91` 安装后再次核验 owner/schema/Skill行指纹；`:101` 覆盖旧迁移 hook。`test_any_file_release.py:139` 用自定义禁用状态和版本证明不假设全开或版本1；断言 compose/run 未调用、没有 MIGRATION_STARTED。`:167` 覆盖安装后状态漂移。 |
| 先关闭接纳并验证，再稳定排空，禁止强停未知在途任务 | 完整实现。`overseas-upload-deploy.py:183` 的顺序为关闭并确认边缘入口、停API、排空、备份、切换；`:69` 要求连续两次空闲，`:83` 在停outbox后再做连续两次检查才停worker。`overseas-images-deploy.py:136` 绑定真实503探测。独立62项包含继承的 `overseas-hotfix-tests.py:102`、`:160`、`:180`、`:189`、`:204` 的顺序、忙/未知/二次排空失败路径。 |
| 备份隔离恢复及原数据保持 | 完整实现。实际绑定 `overseas-studio-ux-deploy.py:122`：停执行器证据、无在途、完整行指纹、dump、隔离恢复、前后指纹相等，最后才 COMPLETE。`member-release-backup.py:114` 恢复到无网络临时容器和独立卷，核对指纹后仅清理该容器/卷。新入口`:79` 在切换前再次检查全部原行。本 reviewer 将现有备份故障测试绑定本候选的真实 `u.backup`，独立复跑成功、恢复失败、源行漂移三分支通过；未运行真实数据库恢复。 |
| 保留国内、身份、broker、环境及会话 | 完整实现。`overseas-any-file-deploy.py:19` 固定国内三服务目录；继承 `overseas-archive-deletion-deploy.py:59`、`:75` 保存broker进程、socket、认证元数据与源码指纹；`:128` 只新增海外WorkingDirectory/ExecStart指针并比较全部环境/组；`overseas-upload-resources.py:28` 校验国内/身份拓扑、旧挂载和配置；`member-release-runtime.py:112` 严格比较除image/build外的Compose内容。`test_any_file_release.py:105` 证明owner及任意其他环境值改变会失败。 |
| 失败关闭、拒绝盲目重放、禁止生产数据库恢复 | 完整实现。`overseas-upload-deploy.py:184` 拒绝已有DEPLOY_STARTED；`:208` 保存恢复指导；`:261` 失败重新关入口、停API、保留阶段，不强停worker、不自动恢复数据库；`overseas-any-file-deploy.py:34` 明确本轮无迁移。继承故障矩阵 `overseas-hotfix-tests.py:125`、`:153` 及 `test_studio_ux_release.py:61` 经本轮测试实际执行，覆盖切换前后失败。 |
| 不可变打包、隐私及安装包门禁 | 完整实现。`package-any-file.py:10` 固定版本/迁移/必需文件；`package-overseas.py:180` 要求已批准快照、干净已提交源码、Git内容与工作树一致、打包前后快照一致，`:166` 检查每个tar条目及摘要。独立执行真实文件选择/隐私/资产白名单/完整validate：1268文件、629资产、134必需项通过。`test_any_file_release.py:216` 检查实际运行依赖闭包和缺项拒绝。尚未创建真实发布tar。 |
| Linux源码摘要、安装测试、500 MB后才prepare/deploy | 完整接线，实际运行待发布。`overseas-deploy.py:31` 先核对镜像源码再执行安装pytest，成功才写INSTALL_TEST_IMAGE_ID；`overseas-upload-resources.py:21` 对同一镜像3 GiB隔离测试容量；`member-release-runtime.py:99` 及 `overseas-upload-deploy.py:186` 要求测试凭据与实际镜像相同。安装测试明确排除本地Codex宿主模块与缺前端源码的跨栈契约用例，不能称为毫无排除的全量。 |
| 安装后健康、版本、正式页面和上传下载验收 | 代码门禁完整，线上步骤待执行。`overseas-upload-deploy.py:156` 核对镜像/原生源码、运行PID、Skills只读验证及健康；`:239` 发布前端并验证，再开启入口；`overseas-any-file-deploy.py:91` 增加owner/schema/Skill保持验收。正式页面、任意文件上传及原件下载由生产合同第4步要求人工执行，本报告不将旧隔离浏览器结果当线上证据。 |

部分实现/未实现：本次发布代码范围内无。生产执行尚未发生，明确列为后续执行门禁。Spec漂移：无新增产品页面/API/表；新脚本和版本变化均对应追加发布授权。

## Stage 2：Code Quality — PASS

| 检查 | 结论及证据 |
| --- | --- |
| 结构、类型、规模 | 新入口109行、打包20行、测试256行，均小于300行；`overseas-any-file-deploy.py:37` 显式保留原函数引用并在`:101`集中重绑。沿用既有发布框架，没有复制完整切换实现。多层继承需要追踪绑定，本轮已核实真实绑定及运行依赖闭包；未发现旧迁移hook残留执行。 |
| 测试真实性与故障覆盖 | `test_any_file_release.py:31` 继承并绑定实际部署函数，mock系统命令以观察事件顺序；owner漂移在关闭入口前阻断（`:37`），真实环境比较和任意Skill状态都含负例（`:105`、`:139`、`:167`）。不是只验证常量。另独立补验真实绑定备份函数三分支。局限：mock系统边界不能证明生产Docker/systemd/数据库，因此保留Linux和线上门禁。 |
| 安全扫描 | 三个新增文件扫描eval/innerHTML/前端敏感变量/密钥前缀/硬编码password无命中。SQL只读且表名固定（`overseas-any-file-deploy.py:24`）；命令经参数数组调用；owner写入沿用私有文件函数，不输出owner内容；`:106` 拒绝优化模式跳过assert。必需绝对路径为明确生产保护基线，未包含本机用户秘密。 |
| 打包边界 | `package-overseas.py:84` 白名单、`:110` 拒绝符号链接、`:115` 审计实际资产、`:132` 校验固定PDF资源字节。`test_any_file_release.py:240` 审计真实选中文件并排除打包工具、发布测试和私有baseline。发布包可能包含历史部署工具，但当前运行依赖不加载旧Skill迁移/owner修改入口（`:236`）。 |
| UI/视觉 | 本轮只改版本，无UI变化；快照核对确认旧功能报告已实测的页面、邻居及浏览器测试完全未改。沿用 `docs/reviews/STUDIO-ANY-FILE-20261022.md:49` 的实际视觉证据，不虚构重复浏览器验收。 |
| 依赖风险 | `frontend/package.json:3` 之外无依赖差异；已读取本轮audit，0 critical、7 low、51 moderate、72 high。该结果不是“无漏洞”，本轮未增加依赖风险；本审查未扩展为全部历史依赖整改。 |

安全问题：未发现本轮新增问题。质量阻断：无。

## 原始验证输出

本 reviewer 独立复跑：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest scripts/release/test_any_file_release.py -q
................................................ [ 77%]
..............                                                           [100%]
62 passed, 24 subtests passed in 1.43s
```

对实际选中文件及现有0.2.48构建资产执行 `selected`、`no_symlink`、`privacy_check`、`collect_assets`、`validate`，以及三个新增Python文件的 `py_compile.compile(..., doraise=True)`，退出0：

```text
{"actualSelectionAndAssetValidation": "PASS", "files": 1268, "assets": 629, "version": "0.2.48", "required": 134}
PY_COMPILE_PASS 3 files
```

独立以本候选实际 `u.backup` 运行既有恢复故障测试，退出0：

```text
ACTUAL_BOUND_BACKUP_FAULT_MATRIX_PASS: success, restore failure, row drift
```

`git diff --check` 无差异错误；Git仅提示既有文本CRLF将归一为LF。

已读取主 Agent 的 `output/studio-any-file-release-build.log`，原始构建摘录如下；本 reviewer 未重复构建：

```text
> hengxin-smart-image-frontend@0.2.48 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4666 modules transformed.
rendering chunks...
✓ built in 31.77s
```

主 Agent 联合回归日志 `output/studio-any-file-release-tests.log`：

```text
141 passed, 48 subtests passed in 3.02s
```

本轮 `output/studio-any-file-release-audit.json` 原始metadata：

```json
{"vulnerabilities":{"info":0,"low":7,"moderate":51,"high":72,"critical":0},"dependencies":860,"devDependencies":0,"optionalDependencies":0,"totalDependencies":860}
```

功能历史验证与边界保留旧报告：前端352通过、后端focused41通过、相关85通过/7跳过；Windows全量2031通过/357跳过/8失败，原始HEAD同环境复现相同8项平台失败，未把全量写成零失败。真实Linux安装镜像与容量测试、正式上传下载尚未执行。

结束时快照仍为本报告candidateId；批准登记由主 Agent 对该快照执行。后续代码变化必须重新固定快照复核。
