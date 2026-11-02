# 原生执行器独立发布基线补丁审查

- 审查者：独立 code-reviewer，2026-11-02；按 `.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md:5` 执行。
- 首次 candidateId：`48e7d34149831fa942a742803a5b43b06beff537ab614d44173cc3c05e60758e`。
- 最终送审 candidateId：`33e0ddfa935a236b08b4812ac07ac7603c4c1d4e6c95d20e307449df57df2090`。
- 最终结论：**Stage 1 PASS / Stage 2 PASS**，仅适用于最终候选 `33e0ddfa…`。当前 HIGH 0、MEDIUM 0；首次候选的1项MEDIUM已修复并复验。
- 范围：相对 HEAD `edfa075` 的5个发布工具、5个发布测试文件及源文档补充。业务源码、前端和数据库迁移没有新改动；两项现有 management 依赖只是进入发布白名单。
- 需求依据：`docs/STUDIO-MESSAGE-METADATA-20261102.md:21`、`:25`，`Product-Spec.md:1386`，`DEV-PLAN.md:1602`。完整业务已审候选 `8b5a21f9…` 的逐项证据见 `docs/reviews/MESSAGE-METADATA-COMBINED-20261102.md:1`；本次不把旧 native 布局当作 API 布局。

## 快照变化及审查边界

初始候选的 `scripts/release/test_outon_native.py` 有317行，违反技能规定的300行上限，判为 MEDIUM。主 Agent 将6个独立基线测试移到 `scripts/release/test_outon_native_baseline.py:13`，仅绑定两个 fixture 方法，没有继承原测试类造成重复收集；原文件238行，新文件94行。重新固定最终候选后，从 Stage 1 复核了测试前提、断言和所有发布变化，独立重跑仍为84项。该问题已修复，初始候选结论不直接覆盖最终候选。

reviewer 只读取私有基线，不将源字节、环境配置或账号数据复制进报告。发布代码之外的临时隔离测试文件位于忽略的 output 目录，不构成生产代码。生产实际安装、迁移和线上验收由主 Agent 后续完成，本报告不冒充这些执行结果。

## Stage 1：Spec Compliance — PASS

| 需求条目 | 代码及验证证据 | 结论 |
|---|---|---|
| API 与两个 native 单位分别读取真实基线，不用 API 摘要代替 native | `scripts/release/outon-baseline.py:27` 采集 API；`:31` 按各单位实际 `/proc/PID/cwd` 读取18路径；`:42` 记录 base64 或明确 null | 完整实现。独立读取私有基线，API19项、两个 native 各18项，逐字节与实际307文件源树一致 |
| 采集时确认进程和目录，拒绝不安全文件 | `outon-baseline.py:32` 拒绝未运行，`:35` 核对 WorkingDirectory，`:40` 拒绝符号链接和非文件，`:43` 复核 PID | `scripts/release/test_outon_contract.py:84`、`:97`、`:103`、`:110` 覆盖实际读取/不存在、停机、目录不符、采集期间重启，完整实现 |
| 制品只包含每单位路径摘要或 null，严格闭合集合 | `scripts/release/outon-package.py:34` 转摘要且验证 base64；`scripts/release/outon-runtime.py:54` 要求准确两单位、准确18路径、64位十六进制或 null；`:73` 安装包必检 | `test_outon_contract.py:36`、`:48` 与 `test_outon_safety.py:54` 验证不嵌入私有字节、缺单位/多路径/错误摘要均拒绝，完整实现 |
| 共享 cwd 的两个单位必须使用相同基线，其他服务不得共用源码 | `outon-package.py:43` 与 `scripts/release/outon-native.py:68` 双重检查；`:77` 保留其他服务共享目录拒绝 | `test_outon_contract.py:58`，`test_outon_native_baseline.py:65`、`:77` 真实临时目录验证，完整实现 |
| prepare 状态绑定制品，不能改变保存的 native 或 API 基线后继续 | `scripts/release/outon-deploy.py:21` 核对 manifest 文件摘要，`:23` 比较 native 与 API 完整映射，`:53` 保存 manifest 的 native 映射 | `test_outon_safety.py:70` 修改 prepared 映射后在镜像查询前拒绝，完整实现 |
| 已知 native/API 历史差异允许，未知漂移仍拒绝 | `outon-native.py:87` 按该单位基线核对并对照 protected 源树，不改白名单外保护；`outon-deploy.py:48` 仍严格核对 API | `test_outon_native_baseline.py:17` 接受已固定差异；`:52` 未知漂移在写入标记前拒绝，完整实现 |
| 不同 native 目录分别备份各自原字节，新增文件明确不存在 | `outon-native.py:194` 按独立 root 映射备份；`:201` null 必须不存在；`:208` 复制后核对各自旧摘要，完成全部备份才在`:212`记录开始写入 | `test_outon_native_baseline.py:26` 两目录不同旧内容分别保留，`:84` 新文件目录碰撞拒绝；`test_outon_native.py:140` 新 helper 备份为 null，完整实现 |
| 白名单仅19 API/18 native，补齐现有 models/skills 依赖 | `outon-runtime.py:23` 与 `outon-baseline.py:8` 同名单；`outon-package.py:72` 强制两个 management 文件与 API 基线字节一致 | `test_outon_release.py:59` 精确数量/路径断言；独立验证这两个文件本地、HEAD、实际 API 三者完全相同，完整实现 |
| 新 queries 平台调用依赖闭合，旧 Skill 分组/开关不被重新配置 | `hengxin-smart-image/backend/app/overseas/studio/queries.py:141` 两参调用；`management/skills.py:31` 两参实现；`management/models.py:25` 已有 platforms 字段。只发布现有代码，不调用写配置方法 | 实际布局97项全部通过，包括真实平台筛选；新增依赖没有新业务实现，API原样复制，完整实现 |
| 其余源码、配置、进程和业务保护不放宽 | `outon-native.py:36` 保留全树/配置/其他PID保护，`:43` 只容许18路径旧或新摘要；`:47` 安装完成强制新摘要；`outon-deploy.py:30` 至`:37` 保留配置、Skill、其他容器保护 | `test_outon_native.py:117`、`:163`、`:177` 覆盖无关新增文件、部分安装损坏、完整安装缺helper，完整实现 |
| 排空、正常停止、迁移/备份/实际镜像测试等发布门禁保持 | `outon-deploy.py:99` 失败/skip不签测试凭据；`:138` 测试通过才gate；`:186` 迁移/native通过才切API；`outon-native.py:96` 原停止保护不变 | `test_outon_native.py:42`、`:52`、`:76`、`:95`、`:206`、`:215` 与 `test_outon_safety.py:142`、`:165` 原故障用例重跑通过，完整实现 |
| 真实 native 源码加最小覆盖在隔离环境验证 | `output/message-ci/pack_native.py:9` 从实际源树构建、`:11` 仅覆盖白名单，Dockerfile先清除测试镜像旧 app；`output/message-ci/run_native.py:21` 临时PG网络与只读容器运行 | archive布局独立核验通过，7模块97项通过、无skip，完整实现；原始输出见下文 |

### UI、部分实现、未实现及 Spec 漂移

本补丁没有页面、文案、CSS、组件、业务 API 或数据库字段改动。UI/引导/邻居视觉无新审查对象，沿用 `docs/reviews/MESSAGE-METADATA-COMBINED-20261102.md:23` 起的前一完整审查与真实浏览器证据，不声称本轮重新打开过页面。所有新增发布行为对应当前合同补充，没有新增业务范围。生产运行步骤尚未执行，不将后续发布工作误报为已完成。

## Stage 2：Code Quality — PASS

- 结构：最终10个Python变化文件均不超过300行，内存 compile 全部通过。基线规范集中在 `outon-runtime.py:54`；采集、制品、预检、安装各自单一职责。原文件超长 MEDIUM 已修复，见上述快照记录。
- 测试真实性：`test_outon_native_baseline.py:26` 使用两个真实临时目录、不同旧字节并比较实际备份摘要；`:52` 的故障确实进入预检和安装拒绝路径。systemd、chown、重启均有 mock，因此这84项只证明发布逻辑，不冒充真实服务部署。实际 Linux/PG 的另一组测试用于补足 native 布局与业务导入依赖。
- 安全：对5个发布工具扫描 eval、危险 HTML、前端密钥变量、常见硬编码密钥前缀，无命中。新增外部进程调用沿用参数列表，`outon-baseline.py:18` 无 shell 拼接。固定生产目录和 `/proc` 路径是发布工具既有职责；`outon-native.py:20` 拒绝链接，`outon-runtime.py:79` 制品路径约束保持，没有新增放宽。`outon-package.py:41` 仅将私有旧源字节转摘要，制品不嵌入 nativeSources。
- 范围保护：安装循环仅 `outon-native.py:198` 的18路径；未用整个 API app 覆盖真实 native 目录。隔离镜像中的删除/整树COPY仅发生在临时 Docker build 层，不是生产安装逻辑，`output/message-ci/pack_native.py:35` 的 Dockerfile 与 `run_native.py:21` 的独立容器证据明确区分。
- 测试模块拆分没有重复收集：新 `NativeBaselineTests(unittest.TestCase)` 仅复用 fixture 函数，`test_outon_native_baseline.py:13`；独立复跑恰好84项，无 skip。
- `git -c core.safecrlf=false diff --check` 无输出，退出0。最终快照通过 `review-status` 只读核对为 `33e0ddfa…`；报告本身不改变代码候选。

## 原始验证输出

reviewer 首次使用系统 Python，环境缺 pytest，未将该次失败算通过：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

改用项目 `hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`，参数为全部 `scripts/release/test_outon*.py` 与 `test_skill_platform*.py`，最终候选独立复跑：

```text
........................................................................ [ 85%]
............                                                             [100%]
84 passed in 4.06s
```

10个变更文件逐一 `compile(raw, path, 'exec')` 和行数检查，原始输出：

```text
compile_PASS scripts/release/outon-baseline.py lines 51
compile_PASS scripts/release/outon-deploy.py lines 244
compile_PASS scripts/release/outon-native.py lines 235
compile_PASS scripts/release/outon-package.py lines 107
compile_PASS scripts/release/outon-runtime.py lines 141
compile_PASS scripts/release/test_outon_contract.py lines 175
compile_PASS scripts/release/test_outon_native.py lines 238
compile_PASS scripts/release/test_outon_release.py lines 176
compile_PASS scripts/release/test_outon_safety.py lines 238
compile_PASS scripts/release/test_outon_native_baseline.py lines 94
```

独立读取实际私有基线、源树、最终隔离tar后核对摘要/集合/字节，原始输出：

```text
baseline_scope 19 [18, 18]
minimum_dependency_byte_identity app/overseas/management/models.py True
minimum_dependency_byte_identity app/overseas/management/skills.py True
native_tree_files 307 native_business_dependencies_match_API True
native_baseline_tree_consistency True
native_baseline_tree_consistency True
final_archive_native_layout_PASS 177c0ea9daae865e1dac8b369dcfac1d6cef5019779d73bbed4cf29b1da9681b 308 untouched 290
```

最终隔离archive包含307个原始源码文件加新增helper，共308个 app 文件；18白名单路径与本地已审业务代码一致，另外290个文件与实际native原字节完全相同。业务Python依赖与API已有环境版本匹配；API额外测试依赖不作为native业务差异抹除。Dockerfile以root清除仅临时镜像中的 `/app/app` 后COPY该真实布局，最后 `USER 999`；运行容器只读，PG独立无外网网络，不连接生产数据库。7模块覆盖消息元信息SQLite/PG、五人studio授权、文件取回/transport、studio执行与直接平台依赖。

首次303827隔离包运行96项通过，额外平台测试未导入 materials fixture 而setup失败，原始输出保留 `output/message-ci/native-first-layout.stdout:1`：

```text
ERROR tests/test_native_release_layout.py::test_actual_native_skill_platform_dependency
96 passed, 2 warnings, 1 error in 92.03s (0:01:32)
```

主Agent仅为 output 临时测试补入 overseas/materials fixture导入，重新打包为上述177c0ea9；reviewer重新核对所有app字节和白名单，候选业务代码不变。平台测试向实际测试数据库插入 enabled=True、platforms=['Amazon']，断言Amazon返回该Skill、Walmart为空，未靠mock筛选逻辑规避依赖。

最终隔离回归原始输出，reviewer实际读取 `output/message-ci/run_native.stdout:1`，确认构建tag为 `177c0ea9daae`、8步Dockerfile最后为USER 999；stderr为空：

```text
Successfully built 9fffb332a29b
Successfully tagged hx-designer-ci:177c0ea9daae
ISOLATED_TESTS 7
........................................................................ [ 74%]
.........................                                                [100%]
97 passed, 2 warnings in 87.64s (0:01:27)
```

两条warning来自既有FastAPI/Starlette依赖弃用提示，无失败或跳过。此次验证完成后 Stage 1 通过，再完成 Stage 2 的最终安全扫描、diff检查和快照核对。最终 `review-status` currentId仍为 `33e0ddfa935a236b08b4812ac07ac7603c4c1d4e6c95d20e307449df57df2090`。

主Agent可使用同一最终candidateId、本文报告路径和两个PASS登记review-approve。之后仍须从已提交且已审快照重新打包，执行正式制品37模块实际镜像测试且无skip，再按 gate/backup/migrate/native/api/verify/resume/frontend/独立Skill安装顺序完成生产验收。该部署流程由 `scripts/release/outon-deploy.py:105`、`:138`、`:174`、`:184` 和合同 `docs/STUDIO-MESSAGE-METADATA-20261102.md:16` 约束，本报告不表示已经上线。reviewer未修改产品代码、未写clean、未登记凭据、未提交或部署。
