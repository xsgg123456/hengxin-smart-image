# AI 工作台 0.2.26 发布增量独立审查

## 快照、范围与结论

- candidateId：`030c9183b95327d0dd4448fe8360978baa941ba1bbf5772a0b3a2e1df867daea`。
- 基线：`ee1139e`。范围为相对该提交的发布增量：`scripts/release/package-overseas.py`、`overseas-update-deploy.py`、`overseas-update-runtime.py`、`overseas-update-tests.py`、`test_package_overseas.py`，以及 `hengxin-smart-image/frontend/package.json`、`docs/OVERSEAS-CHANGELOG.md`。源计划为 `docs/AI-STUDIO-RELEASE-20261013.md:7` 至第 12 行六项标准。
- 业务实现、迁移业务语义及既有 UI 审查继承 `docs/reviews/AI-STUDIO-FORMAL-20261013.md:5` 记录的最终候选与两阶段 PASS。本轮不把版本号增量扩展为整套业务重审。
- 审查开始及结束均独立运行 `review-status`，currentId 与上述候选一致。审查期间仅源计划补充验证记录，未发现受控代码变化。
- **Stage 1：PASS。Stage 2：PASS。** 仅批准上述快照的发布代码增量；不等于服务器安装测试、数据库迁移或生产发布已经完成。
- reviewer 未修改实现、未执行部署、未提交、未写 `.needs-review`；由主 Agent 用同一 candidateId 和本报告登记 `review-approve`。

## Stage 1：Spec Compliance

### 完整实现

| 计划条目 | 审查证据及验证 | 结论 |
| --- | --- | --- |
| 1：从前端 0.2.25 / 海外 0010 开始 | `scripts/release/overseas-update-deploy.py:35` 检查安装测试镜像 ID、数据库 0010 和现网 package.version 0.2.25；`:67` 切换前再次核查镜像、数据库和拓扑。 | 实现 |
| 1：拒绝非管理员多角色和启用无角色 | `scripts/release/overseas-update-runtime.py:33` SQL 与 0011 的数据前置条件相符；`overseas-update-deploy.py:46`、`:73` 在准备和部署前均调用。独立执行此实际 SQL，覆盖管理员多角色、非管理员多角色、启用无角色、待授权无角色和单角色五种组合，接受/拒绝结果全部正确。该补充验证使用内存 SQLite，不冒充生产 PostgreSQL。 | 实现 |
| 1：管理员归并并保留审计 | 已审业务迁移 `hengxin-smart-image/backend/migrations/overseas/versions/0011_single_member_role.py:23` 先全体验证，`:39` 删除管理员多余角色，`:40` 增版本，`:42` 记录 before/after；`:49` 建立 user_id 唯一约束。本轮包的 REQUIRED 明确包含该迁移，见 `scripts/release/package-overseas.py:36`。 | 实现；生产迁移结果待部署后验收 |
| 2：发布 0.2.26 / 海外 0012 / 国内 0027 | `hengxin-smart-image/frontend/package.json:3`、`scripts/release/package-overseas.py:16` 与 `:162` 一致；`overseas-update-deploy.py:23` 核查包声明，`:93` 核查实际海外版本。0011 的 down_revision 为 0010（迁移文件 `:8`），0012 的 down_revision 为 0011（0012 文件 `:5`）。 | 实现 |
| 2：只替换海外 API、worker/outbox 和共用前端 | `scripts/release/overseas-update-runtime.py:22` 固定海外 API、PG、原生 unit；`:28` SQL 固定海外数据库；`:44` 核查 compose project。`overseas-update-deploy.py:50` overlay 只覆盖 api/migrate，`:82`、`:92`、`:95` 仅操作海外 compose；`:98` 对共用 web 仅执行 nginx 检查/reload。国内/identity 六个容器 ID 在 `:29`、`:72`、`:102` 前后对照，无国内迁移命令。 | 实现 |
| 3：已审、已提交的源码打包 | `scripts/release/package-overseas.py:135` 先检查 clean、读取审查状态和 HEAD；`:151` 从提交取字节并与当前文件核对；`:165` 再检查 clean、HEAD 和 candidate 未变。`scripts/release/package-delivery.py:65` 拒绝未批准候选。 | 实现 |
| 3：必需文件、正式入口、隐私和哈希 | `scripts/release/package-overseas.py:26` REQUIRED 包含 0011/0012、工作台路由及部署依赖；`:106` 检查版本、禁止 preview、检查入口资源；`:123` 检查归档成员、类型和字节哈希。独立读取真实工作树与正式 dist：44 项必需文件全部存在，540 个源码文件、836 个前端资源通过实际隐私/入口检查。 | 实现 |
| 3：服务器无缓存构建、隔离安装测试、精确镜像 | `scripts/release/overseas-update-deploy.py:129` 只复用 first-release 的 build 函数，未调用其 prepare/deploy。`scripts/release/overseas-deploy.py:25` 使用 `--no-cache`；`:38` 以镜像 ID、`--network none` 验证源码哈希；`:44` 同一 ID、`--init --network none` 运行安装测试，成功后 `:46` 才写 INSTALL_TEST_IMAGE_ID。update prepare/deploy 再核对此 ID。 | 实现；服务器执行尚未发生 |
| 4：关入口、排空、停止执行器、备份、迁移 | `scripts/release/overseas-update-deploy.py:79` 至 `:93` 的顺序为 close → 停 API → drain → 停 outbox → 再核查空闲 → 停 worker → 再核查 pending → 备份 → 标记迁移开始 → 迁移。`overseas-update-runtime.py:91` 检查 active/reserved/scheduled 明确回复；`:107` 海外 pg_dump 后执行 pg_restore --list 验证可读。故障/顺序专项独立复跑通过。 | 实现 |
| 4：worker 就绪、后端/前端/代理验证后开放 | `scripts/release/overseas-update-runtime.py:159` 等待同一唯一节点 stats 和队列回复，强制 concurrency=5、仅 overseas.cli；`:176` 验证镜像、源码、unit、三类后端健康、前端和原生源码字节。`overseas-update-deploy.py:101`、`:104` 在恢复 edge 前执行验证，`:107` 开放后补公网校验。 | 实现 |
| 5：失败关闭海外入口，禁止旧程序重启/数据库回滚 | `scripts/release/overseas-update-deploy.py:113` 异常处理只再次关入口并停止海外 API，不调用数据库降级、恢复旧代码或停未知 worker；`overseas-update-runtime.py:97` 排空超时拒绝进入停执行器阶段。`overseas-update-tests.py:96` 对 drain/backup/migrate/native/publish/verify/public 七处注入失败，断言闭合入口且无 restore/downgrade；`:104` 确认排空失败不停止 unit。 | 实现 |
| 6：发布验收路径与无收费生成 | `scripts/release/overseas-update-deploy.py:57` 校验正式域名健康、首页字节和匿名 401/403；`:110` 记录迁移、镜像及备份。脚本无生成业务请求。角色唯一约束、超级管理员能力、正式浏览器交互需主 Agent 在部署后按 `docs/AI-STUDIO-RELEASE-20261013.md:12` 实查，计划 `:20` 明确未宣称发布成功。 | 代码路径实现；线上验收待发布执行 |

### 部分实现、未实现、UI 与 Spec 漂移

- 本轮增量未发现需求缺失或 Stage 1 HIGH。计划第 6 项的生产结果尚未发生，这是发布后的验收步骤，不能用本次审查代替（`docs/AI-STUDIO-RELEASE-20261013.md:12`、`:20`）。
- 本轮前端差异仅为 `hengxin-smart-image/frontend/package.json:3` 的版本号；没有新增 UI、引导文案、页面、API、表或组件。工作台、单角色与邻居页面的实际渲染证据继承前次正式报告的 Stage 2；本轮不声称重新打开了生产新版本页面。
- 版本记录 `docs/OVERSEAS-CHANGELOG.md:3` 与发布计划和已审业务范围一致，未发现本轮 scope creep。

## Stage 2：Code Quality

### 代码质量与故障测试真实性

- 改动的五个 Python 文件分别为 140、195、150、185、178 行，均未超过 300 行；职责划分为包装、部署编排、运行时和测试；五文件独立语法解析通过。位置：`scripts/release/package-overseas.py:135`、`overseas-update-deploy.py:67`、`overseas-update-runtime.py:159`、`test_package_overseas.py:136`、`overseas-update-tests.py:96`。
- 44 个发布专项测试独立复跑全部通过。包装测试实际创建归档并回读成员/哈希（`test_package_overseas.py:136`），还覆盖敏感资源、压缩资源泄漏、必需项缺失、preview、镜像资源版本/字节不符（`:39`、`:58`、`:89`、`:118`），不是只断言常量。
- 部署测试执行真实 deploy 控制流并模拟进程/数据库边界，验证成功顺序及七类故障后的关闭动作（`overseas-update-tests.py:56`、`:96`、`:108`）；这些测试不能证明真实 Docker/systemd/数据库服务已经成功执行。
- 新角色测试原本只模拟 SQL 返回计数（`overseas-update-tests.py:118`）。reviewer 额外用五组真实可达成员数据执行原 SQL，弥补“只验证返回计数分支”的局部盲区；真实 PostgreSQL 切换仍须服务器前置与迁移验收。
- worker 测试覆盖暂缺回复后恢复、超时仍无回复、错误队列（`overseas-update-tests.py:130`、`:139`、`:145`）；实现要求 stats/queues 节点 key 集合完全一致（`overseas-update-runtime.py:167`），不能把不同节点回复合并为就绪。

### 安全与隐私

- 本轮修改的运行脚本静态扫描未命中新加 eval、innerHTML、暴露前端密钥、硬编码密钥、用户主目录或 shell=True。进程调用继续使用参数数组（`scripts/release/management-runtime.py:20`），新增角色 SQL 为固定只读文本（`overseas-update-runtime.py:34`），无用户字符串拼接。
- 包装使用闭合选择规则、禁止符号链接、对 gzip 解压扫描，PDF.js 例外必须与固定依赖版本和原字节完全相符（`scripts/release/package-overseas.py:45`、`:67`、`:89`）。真实候选源码和 dist 的扫描通过；只有两个既有负向测试 fixture 使用精确字符串例外，定义见 `scripts/release/package-delivery.py:23`、`:50`，没有对整个 tests 目录豁免。
- 服务器敏感环境只在内存读取，失败日志隐藏 private stderr（`scripts/release/overseas-update-runtime.py:78`）；元数据文件强制 0600（`scripts/release/overseas-runtime.py:26`），备份目录 0700（`overseas-update-runtime.py:108`）。
- **既有依赖风险（范围外、未关闭）：** `output/studio-release-audit.json:2804` 的 prod audit 为 critical 0 / high 36 / moderate 34 / low 1。本次锁文件、依赖声明未变，不能据本轮 PASS 宣称“所有依赖无漏洞”，也不能只凭等级计数证明每条均可从生产页面利用。源计划 `docs/AI-STUDIO-RELEASE-20261013.md:18` 已如实记录。既有依赖漏洞分析/升级不属于本次发布脚本增量。
- **既有工具提示：** `output/studio-release-build.log:1` 提示当前 pnpm 忽略 package.json 内 `pnpm.overrides`、`pnpm.onlyBuiltDependencies`。本轮没有修改这些配置；构建实际成功。该提示与非零 audit 均未被隐藏。

### 视觉对比

本次无 UI 代码差异，视觉审查继承 `docs/reviews/AI-STUDIO-FORMAL-20261013.md` 中已打开正式工作台、展开视图、原图查看器和管理邻居页的证据。本轮正式构建版本见 `output/studio-release-build.log:3`；正式域名的部署后视觉验收仍按源计划第 6 项执行，不以此前本地截图替代生产验收。

## 原始验证输出

Reviewer 独立执行：

```text
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_package_overseas.py scripts/release/overseas-update-tests.py -q
............................................                             [100%]
44 passed in 0.46s
```

Reviewer 独立读取实际源码、调用包装选择/隐私/资源/必需项验证函数（未绕过 clean gate 创建正式包）：

```json
{"requiredCount": 44, "actualRequiredMissing": [], "sourceFiles": 540, "assets": 836, "privacy": "PASS", "syntheticExceptionFiles": ["backend/tests/test_public_messages.py", "backend/tests/test_round_materials.py"]}
```

Reviewer 独立语法和角色 SQL 验证：

```text
PYTHON_SYNTAX_PASS 5 files
ROLE_PREFLIGHT_QUERY_MATRIX_PASS 5 reachable role populations (SQLite SQL semantics; not production PostgreSQL execution)
```

已读取本次正式构建日志 `output/studio-release-build.log:3`、`:4`、`:754` 的原始输出：

```text
> hengxin-smart-image-frontend@0.2.26 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 36.00s
```

已读取继承业务基线的前端/后端结果，不声称本轮重新执行这些全量测试：

```text
output/studio-frontend-final.log:317
ℹ tests 311
ℹ suites 0
ℹ pass 311
ℹ fail 0

output/studio-linux-final.log:59
1923 passed, 162 skipped, 15 warnings in 230.07s (0:03:50)
```

审查结束 `review-status` 原始输出：

```json
{"currentId": "030c9183b95327d0dd4448fe8360978baa941ba1bbf5772a0b3a2e1df867daea", "reviewedId": "3a46197dec16d3b836ace63f5772d69eceadb90e6e5ae41851339351f4180bd2", "changedFiles": ["hengxin-smart-image/frontend/package.json", "scripts/release/overseas-update-deploy.py", "scripts/release/overseas-update-runtime.py", "scripts/release/overseas-update-tests.py", "scripts/release/package-overseas.py", "scripts/release/test_package_overseas.py"], "approved": false}
```

`approved: false` 为登记新凭据前的正常状态。两阶段结论只适用于 currentId；主 Agent 登记后再提交和执行发布。服务器无缓存构建、network-none 安装测试、备份、迁移、容器不变和正式浏览器验收必须保留实际输出，不能从本报告推定已完成。
