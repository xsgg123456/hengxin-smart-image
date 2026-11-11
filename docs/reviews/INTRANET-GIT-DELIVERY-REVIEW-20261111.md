# 内网改动 Git 交付独立审查 · 2026-11-11

## 候选、范围与结论

- **candidateId：`f13d73eedf87c773327d8006e923f1a1b4f7aec5df508e2f1d62696a16e492b7`。** 基线 HEAD `04b7c39`，分支 main。
- **Stage 1：PASS；Stage 2：PASS。** 结论适用于本次全部待提交内容的代码、文档、证据覆盖及入库适宜性；未发现 HIGH/MEDIUM 阻断问题。
- 范围：相对 HEAD 的 40 个已跟踪修改、75 个原有未跟踪文件，以及本报告，共 **116 个文件**。依据 `Product-Spec.md:1`、`:1452`，`DEV-PLAN.md:1`、`:1668`，`docs/INTRANET-GIT-HANDOFF-20261111.md:3` 和所引用的内网合同。未扩展为全仓库所有历史功能重新验收。
- 主 Agent 明确授权整理、补文档、分批提交和推送 main。本 reviewer 只读代码、复核保存证据、运行本地隔离测试并新增本报告；未修复源码、未连接生产、未调用模型、未提交/推送、未执行 review-approve。
- **PASS 不代表整个内网副本的全部业务验收通过，也不代表 Git 已提交或推送成功。** 这些状态由相应证据分别判定，详见 `docs/INTRANET-245-ACCEPTANCE-20261110.md:3`、`docs/INTRANET-DOMESTIC-E2E-20261111.md:25`。

## 快照核对及证据继承

既有最后代码审查为 [Codex 运行时报告](INTRANET-CODEX-RUNTIME-REVIEW-20261111.md)，候选 `10e0a86542ddf018e4478b68b1be29195cd8f972c3b505afca7c1ad446b16637`。该报告在批准后追加线上证据，旧凭据中的报告摘要已失效；不能直接沿用旧批准。

本轮从 `.codex/review-state.json` 读取旧批准文件摘要与新候选摘要，逐路径比较得到 698 项差异：695 项为 `frontend/dist-lan-ip/` 构建文件退出受控快照，另外三项为 `.gitignore`、`scripts/migration245/build_sandbox_proxy_test.py`、`scripts/migration245/fixtures/workspace_before_lan_proxy.py.fixture`。**其余受控业务代码与最后审查快照相同**。本轮重新审查这三项和普通 Markdown 整理，核对全部既有报告的范围、失败后复审链及现有测试输出，没有将初次失败报告当作 PASS。

`harness.py review-status` 因旧报告摘要变化按预期拒绝，原始输出如下；这不是本轮新候选的通过凭据：

```text
Harness hook failed: 审查报告已修改或凭据失效，请重新执行 review-prepare 和两阶段审查
```

随后仅调用项目 `review_files.snapshot/identity/changes` 只读重新计算当前内容，没有修改状态或绕过提交门禁：

```json
{"currentId":"f13d73eedf87c773327d8006e923f1a1b4f7aec5df508e2f1d62696a16e492b7","candidateId":"f13d73eedf87c773327d8006e923f1a1b4f7aec5df508e2f1d62696a16e492b7","candidateDifferences":[]}
```

主 Agent 须用本报告为同一候选重新登记两阶段 PASS；后续受控文件变化必须重新固定快照和复核。普通报告不属于代码快照，但本报告一经批准，不应再修改而继续使用旧报告摘要。

## Stage 1 · Spec Compliance

下表代码路径以 `hengxin-smart-image/` 为前缀；报告与根文档路径从仓库根开始。

| 交付要求 / 合同 | 结论、实现及证据 |
| --- | --- |
| 保留全部用户修改，精确排除构建、私有配置与证据 | **完整实现。** `.gitignore:19` 仅新增明确的 dist-lan-ip 目录，`:20` 排除 output，`:3` 排除私有 env，`:37` 排除审查状态。独立 `git check-ignore -v` 验证这些路径命中，历史 fixture 不被忽略；无删除的已跟踪源码。 |
| main 工作约定与门禁保留 | **完整实现。** `AGENTS.md:179` 规定 main 开发但不免除审查、测试和提交检查；`:180` 的禁止自动推送 main 与用户本次明确要求推送不冲突。[规则报告](MAIN-BRANCH-POLICY-REVIEW-20261110.md):15 起已逐项审查。 |
| 内网独立副本、只读采集与选择性导入 | **已有实现与独立审查覆盖，本轮无业务增量。** `scripts/migration245/collect_runtime.py:31`、`transport.py:18`、`build_compose.py:133`、`install_files.py:58`、`data_copy.py:130`、`data_policy.py:50`；对应 [采集](INTRANET-245-COLLECTOR-REVIEW-20261110.md):22、[采集遗漏修复](INTRANET-245-COLLECTOR-FIX-20261110.md):20、[部署模块](INTRANET-245-DEPLOYMENT-REVIEW-20261110.md):33、[审计裁剪](INTRANET-245-AUDIT-POLICY-REVIEW-20261110.md):21、[原生/种子最终复审](INTRANET-245-NATIVE-SEED-REVIEW-20261110.md):23。DATA/NATIVE 首轮 FAIL 保留为历史，最终复审覆盖其修复，不误记为未关闭缺陷或初轮通过。 |
| 内网入口、原生服务、沙箱代理及重启通信目录 | **已有实现与独立审查覆盖。** `scripts/migration245/build_native.py:1`、`build_edge.py:28`、`build_sandbox_proxy.py:1`、`hengxin-lan.tmpfiles.conf:1`；[Edge/Sandbox 最终复审](INTRANET-245-EDGE-SANDBOX-FIX-REVIEW-20261110.md):11、[开机目录报告](INTRANET-245-BOOT-DIRS-REVIEW-20261110.md):5。原 nginx 临时目录 HIGH 已经后续复审关闭。 |
| HTTP 登录安全、浏览器加密/复制、Skills ZIP 及菜单模式 | **完整实现且报告链覆盖。** `backend/app/core/config.py:12`、`browser_auth.py:42`；`frontend/src/utils/browser-crypto.ts:2`、`clipboard.ts:2`、`views/overseas/admin/skill-folder-zip.ts:37`、`SkillFolderActions.vue:35`；`scripts/migration245/build_lan_frontend.ps1:7`、`ip_access.py:146`。[HTTP 主报告](INTRANET-IP-ACCESS-REVIEW-20261111.md):17 逐项核对合同；[健康路径修复](INTRANET-IP-HEALTH-REVIEW-20261111.md):5、[reload 修复](INTRANET-IP-RELOAD-REVIEW-20261111.md):19、[菜单修复](INTRANET-DOMESTIC-MENU-REVIEW-20261111.md):21 补齐后续增量。本轮前端代码无新变化。 |
| Codex 取码代理、显式 loopback、CLI 升级与安全排空 | **完整实现且报告链覆盖。** `backend/app/account_management/device.py:19`、`backend/app/execution/workspace.py:74`；`scripts/migration245/fix_account_proxy.py:20`、`upgrade_codex.py:166`。[代理报告](INTRANET-CODEX-AUTH-PROXY-REVIEW-20261111.md):15 与 [CLI 最终复审](INTRANET-CODEX-UPGRADE-RECHECK-20261111.md):9 覆盖实现及故障恢复；升级初审 HIGH 由最终复审关闭。 |
| 实际 Codex 内层、文档/图像依赖、真实身份验收 | **指定范围完整。** `backend/app/execution/workspace.py:90`、`office_render.py:76`、`runtime_check.py:24`；`infra/install_codex_runtime.py:29`、`verify_codex_runtime.py:97`、`verify_codex_model.py:33`；`scripts/migration245/fix_runtime.py:167`。运行时报告:26 起覆盖合同，:107 起记录线上安装、真实 UID、真实模型、PPT/图片和续轮证据。复用已审证据，不声称本 reviewer 再次远端执行。 |
| 修复历史迁移补丁测试，不修改生产行为 | **完整实现，本轮独立验证。** `scripts/migration245/build_sandbox_proxy_test.py:16` 从固定 fixture 读取，规范 LF 并校验 SHA；`:81` 起仍验证基线漂移、已打补丁拒绝及精确逆变换。fixture 与 `git show 04b7c39:hengxin-smart-image/backend/app/execution/workspace.py` 规范 LF 后完全相同。源码补丁器未改变，fixture 不是可发布模块。 |
| 说明一次性脚本使用范围 | **完整实现。** `scripts/migration245/README.md:3` 说明固定主机/版本、拒绝强行重复运行；`:18` 说明两种测试命名、POSIX 与真实 PG 条件；`:20` 写明历史来源、摘要及当前回归位置；`:24` 限定实际执行前检查，不把入库当作执行。 |
| 文档状态真实且不扩大验收范围 | **匹配。** `docs/INTRANET-245-RESULTS.md:3`、`:82` 至 `:86` 分开当前专项 PASS 和全业务待验；`docs/INTRANET-245-ACCEPTANCE-20261110.md:3` 明确是标准而非全量结果；`docs/INTRANET-DOMESTIC-E2E-20261111.md:17`、`:25` 分开计划和已有证据。IP/AUTH/UPGRADE 的后续状态分别见 `docs/INTRANET-IP-ACCESS-20261111.md:53`、`docs/INTRANET-CODEX-AUTH-FIX-20261111.md:30`、`docs/INTRANET-CODEX-UPGRADE-20261111.md:38`，没有把旧空账号、旧 CLI 或回调未保存冒充最新状态。 |
| 分批不遗漏依赖和运行配套文件 | **完整覆盖。** 独立检查主 Agent 的 `output/submission-batches.json`：五批分别 3/80/9/17/7 文件，合计116；含全部待交付路径及本报告。第2批包括前端新增封装/ZIP、所有调用点/测试、package.json/pnpm-lock、历史 fixture 与迁移配套；第4批包括 workspace、renderer、runtime_check、worker、安装器/包清单、两探针及事务测试。`infra/CODEX-RUNTIME.md:20` 与 `fix_runtime.py:167` 明确成套发布。workspace 合并代理和运行时增量置于第4批，所以这些是一次完整交付的有序提交，不宣称第3批可单独部署最终功能。 |

**部分实现/未实现：** 本次 Git 整理及代码准入范围没有遗漏；实际提交、推送和远端 HEAD 验证由主 Agent 在批准后完成。全业务 UI/API 投递、全角色/手机、账号跨有效期刷新、最终组合改动后整机重启及长期观察仍为未完成范围，不能因本报告 PASS 自动关闭（`docs/INTRANET-245-RESULTS.md:82`、`:85`、`:86`）。

**引导真实性、UI 与 Spec 漂移：** 本轮新增只有忽略规则、历史测试 fixture 和说明文档，没有新增页面/API/表。前端代码与已审版本相同；HTTP ZIP 的“已发起下载”与服务端不回收语义已由 `SkillFolderActions.vue:35` 及 HTTP 报告:24 验证。本轮复用 HTTP 报告:30、:38 实际 Chromium 候选/邻居页面对比与裁切修复证据，没有重新打开页面或虚构本轮视觉实测。运行时独立脚本不代替产品业务按钮的边界写于 `infra/CODEX-RUNTIME.md:16`。

## Stage 2 · Code Quality

| 项目 | 结论与证据 |
| --- | --- |
| 本轮增量质量 | **PASS。** `build_sandbox_proxy_test.py:16` 仅切换稳定历史输入并强校验，166行；fixture112行且不作为生产模块；既有生产补丁器保持不变。未用跳过或放宽断言隐藏 anchor drift。 |
| 测试真实性 | **PASS（明示范围）。** reviewer 独立本地跑历史补丁测试7通过、2 POSIX 跳过；主 Agent Linux同套覆盖9项全部通过。原补丁函数仍由受审源码AST提取执行生成argv（测试:31），不声称启动了真实Codex。数据PG用例需显式启用（`data_seed_test.py:14`），本轮13项跳过不算通过；保留既有真实PG独立17项零skip证据，其中13项真实PG、4项单测，且相关代码无变化。 |
| 编译与结构 | **PASS。** reviewer 编译38个变化Python文件和1个fixture，无导入执行部署脚本；全部不超300行，最高 `fix_runtime.py` 298行。新前端封装/ZIP结构与类型沿用 HTTP 报告:34；本轮541项前端测试、vue-tsc和生产构建通过。 |
| 入库秘密与产物扫描 | **PASS（静态检查范围）。** 对115个既有待交付文件扫描私钥块、常见真实key/token格式、秘密赋值与危险执行模式；无真实凭据、NUL二进制或大于1MB文件。两处秘密赋值命中是 `build_sandbox_proxy_test.py:92`、`:112` 合成哨兵。固定主机地址和部署绝对路径属于维护范围，非秘密。未将 output、模型素材、env、审查状态或静态构建加入清单。 |
| 危险模式复核 | **无本轮新增安全问题。** `frontend/src/directives/business/highlight.ts:68`、`:75` 的 innerHTML 为原有高亮/固定SVG代码，diff仅改复制封装；不是新增任意HTML入口。`fix_runtime.py:288` 至 `:292` 的动态加载先校验固定helper路径及哈希，其安全边界由运行时报告:50审查，当前摘要仍相同。本轮历史fixture仅作为本地测试源码输入，先校验固定SHA。 |
| 配套与错误路径 | **PASS。** `fix_runtime.py:22`、`:167`、`:231` 保持workspace/renderer/runtime_check清单与0755安装；`install_codex_runtime.py:29` 的包清单同批。原独立报告中排空、恢复失败、第三方覆盖、输出损坏等故障证据保留，不以成功构建替代这些检查。 |
| 文档与证据可追溯 | **PASS，含一项非阻断提示。** 本轮检查165个Markdown相对链接；其中旧 `MAIN-BRANCH-POLICY-REVIEW-20261110.md:11` 的报告链接带 `:3`，标准Markdown文件解析可能打不开。目标文件存在，本报告提供有效 [开机目录报告](INTRANET-245-BOOT-DIRS-REVIEW-20261110.md) 索引，未修改历史已审报告。其余相对文件目标存在。 |

当前无待修 HIGH/MEDIUM；上述旧链接为 LOW 可读性问题，不影响代码或证据存在性。未把历史报告“无问题”当作本轮不检查的理由，当前快照差异、fixture历史真实性、入库安全及清单覆盖均已独立核验。

## 原始验证输出与来源

Reviewer 独立执行 `python -m unittest -v build_sandbox_proxy_test`（工作目录 `hengxin-smart-image/scripts/migration245`），退出0：

```text
Ran 9 tests in 0.201s
OK (skipped=2)
```

两项跳过原因为 `requires Unix file modes` 和 `requires Unix symlinks`，不记作本地通过。历史字节对照原始结果：

```text
FIXTURE_EQUALS_GIT True SHA256 35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75
```

Reviewer 使用 `compile(path.read_bytes(), str(path), 'exec')` 编译，不执行模块顶层。原始输出如下（路径前缀统一为 `hengxin-smart-image/`，仅去除重复前缀）：

```text
COMPILE PASS backend/app/account_management/device.py 43 lines
COMPILE PASS backend/app/core/browser_auth.py 47 lines
COMPILE PASS backend/app/core/config.py 142 lines
COMPILE PASS backend/app/execution/workspace.py 132 lines
COMPILE PASS backend/tests/test_execution_proxy.py 75 lines
COMPILE PASS infra/local_codex_worker.py 88 lines
COMPILE PASS backend/app/execution/office_render.py 155 lines
COMPILE PASS backend/app/execution/runtime_check.py 48 lines
COMPILE PASS backend/tests/test_account_device_proxy.py 46 lines
COMPILE PASS backend/tests/test_execution_runtime_resources.py 54 lines
COMPILE PASS backend/tests/test_intranet_http.py 127 lines
COMPILE PASS backend/tests/test_office_render.py 61 lines
COMPILE PASS infra/install_codex_runtime.py 49 lines
COMPILE PASS infra/verify_codex_model.py 149 lines
COMPILE PASS infra/verify_codex_runtime.py 129 lines
COMPILE PASS scripts/migration245/build_compose.py 247 lines
COMPILE PASS scripts/migration245/build_compose_test.py 192 lines
COMPILE PASS scripts/migration245/build_edge.py 170 lines
COMPILE PASS scripts/migration245/build_edge_test.py 132 lines
COMPILE PASS scripts/migration245/build_native.py 238 lines
COMPILE PASS scripts/migration245/build_native_test.py 257 lines
COMPILE PASS scripts/migration245/build_sandbox_proxy.py 151 lines
COMPILE PASS scripts/migration245/build_sandbox_proxy_test.py 166 lines
COMPILE PASS scripts/migration245/collect_runtime.py 98 lines
COMPILE PASS scripts/migration245/collect_runtime_test.py 25 lines
COMPILE PASS scripts/migration245/data_copy.py 273 lines
COMPILE PASS scripts/migration245/data_copy_test.py 284 lines
COMPILE PASS scripts/migration245/data_policy.py 117 lines
COMPILE PASS scripts/migration245/data_seed_test.py 76 lines
COMPILE PASS scripts/migration245/fix_account_proxy.py 114 lines
COMPILE PASS scripts/migration245/fix_runtime.py 298 lines
COMPILE PASS scripts/migration245/fixtures/workspace_before_lan_proxy.py.fixture 112 lines
COMPILE PASS scripts/migration245/install_files.py 193 lines
COMPILE PASS scripts/migration245/install_files_test.py 123 lines
COMPILE PASS scripts/migration245/ip_access.py 224 lines
COMPILE PASS scripts/migration245/test_fix_runtime.py 238 lines
COMPILE PASS scripts/migration245/test_ip_access.py 92 lines
COMPILE PASS scripts/migration245/transport.py 106 lines
COMPILE PASS scripts/migration245/upgrade_codex.py 243 lines
```

下列由主 Agent 执行，reviewer 已读取本地原始日志，未冒称亲自执行：

```text
# output/git-final-frontend-tests.log
ℹ tests 541
ℹ suites 0
ℹ pass 541
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 13305.1972

# output/git-final-backend-tests.log（Windows，相关11模块）
246 passed, 87 skipped, 2 warnings in 12.30s

# output/git-final-migration-tests.log（Windows）
Ran 85 tests in 1.385s
OK (skipped=17)

# output/git-final-linux-tests.log（迁移测试）
Ran 85 tests in 3.425s
OK (skipped=13)
MIGRATION_RESULT {"run": 85, "failures": 0, "errors": 0, "skipped": 13}

# output/git-final-linux-tests.log（同11个后端模块）
BACKEND_EXIT 0
333 passed, 2 warnings in 6.40s

# output/git-final-build.log（build_lan_frontend.ps1先vue-tsc再vite）
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.67-lan.2
vite v7.1.7 building for production...
transforming...
✓ 4830 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 32.91s
```

构建命令中的 vue-tsc 成功没有额外输出；`build_lan_frontend.ps1:22` 若失败会抛错，不能进入后续成功构建。pnpm旧配置位置提示、Starlette/httpx和anyio弃用提示是已记录警告，没有伪装成测试失败或新修复完成。Linux补验补齐了Windows的87项后端跳过及迁移POSIX用例；本轮迁移真实PG13项仍未重跑，不能把85总数说成85通过。真实PG既有独立原始输出在 [原生/种子报告](INTRANET-245-NATIVE-SEED-REVIEW-20261110.md):98 至122，`Ran 17 tests in 26.179s / OK`，零skip；本轮仅继承未变化代码的该证据。

最终补充核对：已读取主 Agent 的 `output/git-final-linux-source-check.json`，6个相关源码及11个测试文件的Linux副本与当前本地源码规范LF后的SHA比较均为true（17/17）；这是主 Agent 保存的同源性验证结果，不冒充 reviewer 远端读取。交付文档已补齐实际测试表、PG复用边界和第3批不能单独部署的说明（`docs/INTRANET-GIT-HANDOFF-20261111.md:20`、`:39`）。这些补充只有普通Markdown变化，未改变受控候选。

Reviewer在报告定稿前再次独立对照分批清单与Git实际待交付路径，并重新计算快照，原始输出：

```json
{"batchCounts":{"1":3,"2":80,"3":9,"4":17,"5":7},"total":116,"duplicates":[],"missingFromPlan":[],"extraInPlan":[]}
{"currentId":"f13d73eedf87c773327d8006e923f1a1b4f7aec5df508e2f1d62696a16e492b7","candidateDifferences":[]}
```

本报告仅提供同一候选的两阶段审查结论。主 Agent 登记新凭据后，仍须逐批核对暂存范围，完成中文提交、推送及远端HEAD一致性验证，才能宣称 Git 交付完成。
