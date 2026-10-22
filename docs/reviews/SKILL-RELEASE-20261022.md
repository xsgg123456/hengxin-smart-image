# Skill 发布增量独立审查（2026-10-22）

- 最终 candidateId：`61902f176f05f3a6998fcf9ddb17c88f40804d0dc7101a6df778feea5aa78bc3`。
- 最终结论：**Stage 1 PASS；Stage 2 PASS**。初始候选发现的 HIGH 发布阻断已修复，最终范围内无未解决 HIGH / MEDIUM。
- 审查范围：`hengxin-smart-image/frontend/package.json` 版本 0.2.46→0.2.47；`scripts/release/` 下 `overseas-skill-availability-deploy.py`、`overseas-skill-availability-owner.py`、`package-skill-availability.py`、`test_skill_availability_release.py`。
- 上一已批准产品快照：`a2fcd69bdff5dde51098f5d3b31294bb07a27668d15826309f3f94d44367eae5`，报告 `docs/reviews/SKILL-AVAILABILITY-20261022.md`。本次只审发布增量与其继承调用链，不重复产品 UI 审查；没有连接或修改生产，没有提交、修复代码或登记批准。
- 快照变化已复核：初始 `382c335c21a7f6b0ccbbaaa613a889ffd490599490ea643a361a93f9cc9d35e0` 因 R1 拒绝；修复包选择和真实隐私回归后为 `a5f5906b26f3e26d548bcaae5055fc1d40aaa6f7856886ca22fdebebad4be82c`；测试文件顶部删除 4 个空白行、恢复 300 行上限后固定为上述最终候选。主 Agent 修改源码，审查者重新读取变更、从 Stage 1 复核并重跑最终专项；旧候选结论不自动覆盖新快照。

## Stage 1：Spec Compliance — PASS（修复复核后）

### 初始 HIGH R1：打包器自身隐私字面量阻断 — 已修复

需求：`Product-Spec.md:1295` 授权打包与生产发布；`DEV-PLAN.md:1536` 要求包清单及发布故障测试通过，`:1537` 要求隐私审计通过后准备切换。

初始候选实际（本段行号属于初始候选）：`scripts/release/package-skill-availability.py:14` 将全部 `PACKAGING_HELPERS` 放入 SUPPORT，`:15` 设为 REQUIRED，`:25` 无条件选入这些文件。继承的 `scripts/release/package-overseas.py:199` 对每个真实选入源码执行 `privacy_check`。新选入的 `scripts/release/package-delivery.py:26` 含扫描器自身的 `/Users/` 字面量，`:30` 含 PRIVATE KEY 合成反例字面量；其 `:55` 的精确例外只有 backend 测试文件，`:65` 因而拒绝该文件。

独立使用当前真实文件集合及当前 packager 的 `selected`、`normalized`、`privacy_check` 扫描，原始输出：

```text
selected source files: 648
Privacy scan failed: scripts/release/package-delivery.py
```

当时未执行正式 build（尚未批准/提交），但上述调用与正式 build 的 `:190`～`:202` 扫描路径相同，且失败文件已跟踪。该问题是新增包选择范围导致的可复现发布阻断，并非泄漏真实密钥。

测试盲区：`scripts/release/test_skill_availability_release.py:264` 用空字节构造 REQUIRED 文件，只运行 `validate`，没有对新选入的真实打包器内容执行隐私扫描，因此此用例通过不能证明真实包可构建。

修复与复核：当前 `package-skill-availability.py:13` 仅增加生产入口、owner helper、迁移与后端用例，`:21` 沿用既有 selected；本地打包工具与本地发布测试不进生产包。`:12` 仍保留本地 PACKAGING_HELPERS 已提交校验。当前 `test_skill_availability_release.py:293` 对 git 实际文件集合执行 selected/normalized/privacy_check，并明确断言本地工具排除。审查者独立检查真实源码加正式 dist 的 1266 个文件，隐私、assets 与 REQUIRED 全通过；同时展开包括裸 `module()` 与属性 `.module()` 的 26 个生产传递 helper，全部可选入。没有放宽隐私规则。

### 逐条发布合同核对

| 条目 | 当前结论及证据 |
|---|---|
| 0.2.47 版本、国内 0032、海外 0019→0020 | 完整实现。`frontend/package.json:3`（路径前缀为 `hengxin-smart-image/`）；`scripts/release/overseas-skill-availability-deploy.py:13`、`:36`、`:46`、`:50` 固定版本与 schema；package `:10`～`:11` 同步 manifest。新测试 `:53` 和 `:74` 实测通过。 |
| 分离的真实前端/海外版本、镜像及原生指针基线 | 完整实现。deploy `:17`～`:21` 固定输入基线，`:58` 核验版本、镜像、健康、内存、重启策略、两个海外指针与 drop-in 优先级。`:74` 保留 broker group/socket 条件，`:77` 调国内/broker检查；测试 `:216` 的漂移矩阵通过。生产基线来源为主 Agent 只读证据，本审查未重复实查。 |
| 唯一账号绑定，私有 root:root 0600 片段，prepare→switch 防漂移 | 完整实现。owner `:14` 检查 regular file/非链接/权限/精确 UUID，`:28` 验证 active 且唯一 super_admin 权限；`:38` 固定 owner+摘要。deploy `:89` 保存绑定，`:81` overlay 每次重新 pinned，`:103` 迁移前再查。继承 `overseas-upload-deploy.py:91` 在关闭入口前重算 overlay 并与已准备值比较；新测试 `:39` 确证 owner 漂移时不 close/drain/backup/switch。 |
| 仅 API 追加绑定环境，保持其余运行配置与资源 | 完整实现。deploy `:81` 只向 API 注入唯一键；`:87` 经 owner `:45` 规范化仅该键，再交继承的严格 Compose 比较。`overseas-studio-ux-deploy.py:83` 保留所有原海外 restart 与非 API 镜像；`overseas-upload-resources.py:28` 保留国内/身份 topology、挂载、配置、其余容器 ID 与原生文件。新测试 `:164` 及继承资源故障测试通过。 |
| 正常排空、备份隔离恢复、故障闭锁，不恢复旧库 | 完整实现。`overseas-upload-deploy.py:66` 两次稳定空队列，`:82` 停 outbox 后再次排空才停 worker；`:218`～`:236` 按关闭→排空→备份→迁移→切换执行。`overseas-studio-ux-deploy.py:123` 绑定隔离恢复及精确行指纹，`member-release-backup.py:114` 在 network none 临时数据库恢复核验。upload deploy `:262` 失败重关入口并停止 API，不自动恢复数据库；继承故障矩阵通过。 |
| 只增加 0020 表与两行，保留旧表列和业务行 | 完整实现。deploy `:103`～`:129` 检查 COMPLETE、EXECUTORS_STOPPED、备份行指纹，固定 owner，执行目标迁移；随后检查旧列摘要、全部原行摘要、新表集合及指定两行。`:50` 精确断言两项 enabled/version=1，表总数 2。新测试 `:185` 覆盖缺备份/排空/配置漂移/迁移异常/行列改变及多表/丢表。 |
| 真实安装包与容量测试后才能准备及切换 | 实现具备，但真实执行尚待 R1 修复后。`overseas-upload-deploy.py:277` build 调实际镜像测试和容量测试；`overseas-deploy.py:31` 比对镜像源码哈希并在 network none 运行后端测试；`overseas-upload-resources.py:23` 固定 3 GiB 容量测试。`overseas-archive-deletion-deploy.py:146` 及 upload deploy `:185` 校验镜像凭据一致。 |
| 安装探针只读验证本人权限及初始目录 | 完整实现。owner `:59` 的 PROBE 显式 `SET TRANSACTION READ ONLY`，从真实配置取得 UUID，查 active/权限、所有成员 can_toggle 唯一性及目录两项；`:84` 核对实际 API 环境唯一键后调用探针。无创建登录态、切换 Skill 或生成请求。测试 `:248` 覆盖环境缺失与探针失败。 |
| ready 顺序及最后开放入口 | 调用链正确。`overseas-upload-deploy.py:234` 使用 compose up `--wait` 后才 start native，再调用新 installed；compose 的 `infra/compose.overseas.yaml:132` API healthcheck 为 `/health/ready`。owner 探针不依赖 native ready，随后基类 `overseas-upload-deploy.py:173` 等待 worker ready、空队列与 HTTP readiness，再发布前端、开放入口并复查。未发现 owner probe 位于继承 ready 前导致必然竞态的证据。 |
| 包闭包、隐私、不可变已审提交 | 完整实现，R1 已修复。当前 package `:13`、`:21` 保留生产闭包；真实文件隐私/assets/REQUIRED 与26个 helper闭包验证通过。继承 `package-overseas.py:180` 有 clean tracked、approved snapshot、commit字节比较及回读归档哈希检查。真正按提交产包由主 Agent 执行，本报告不冒充其完成。 |
| 发布后权限/目录/工作台/正式页面验证 | 尚未执行，属于主 Agent 发布后验收，不是本次已完成证据。本增量不改变页面布局，UI 复核沿用上述产品审查范围；不把“生产部署已完成”写入本报告。 |

范围内未发现新增业务功能漂移：deploy `:103` 只做授权新增表，owner `:59` 只读探针，package `:10` 固定本次发布；具体产品行为沿用已批准产品快照。

## 测试与编译原始输出

审查者运行，全部为本地测试，生产操作被测试替身隔离：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_skill_availability_release.py scripts/release/test_studio_ux_release.py scripts/release/test_overseas_upload.py -q
137 passed, 72 subtests passed in 3.46s

hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_archive_deletion_release.py scripts/release/test_overseas_images.py scripts/release/test_overseas_images_recovery.py scripts/release/test_overseas_upload_recovery.py -q
135 passed, 48 subtests passed in 4.87s
```

Python 四个新增文件使用 `compile(source, filename, 'exec')`，原始输出：

```text
overseas-skill-availability-deploy.py 148 COMPILE_PASS
overseas-skill-availability-owner.py 91 COMPILE_PASS
package-skill-availability.py 35 COMPILE_PASS
test_skill_availability_release.py 294 COMPILE_PASS
```

初次使用系统 Python 失败：`No module named pytest`；随后使用项目现有 venv 获得上述结果，未安装或更改依赖。

前端构建由主 Agent 执行，审查者读取 `output/skill-release-20261022/frontend-build-pinned.log`，末行原始输出：

```text
✓ built in 33.10s
```

修复后独立联合回归及最终候选专项原始输出：

```text
138 passed, 72 subtests passed in 3.64s

hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_skill_availability_release.py -q
79 passed, 24 subtests passed in 1.81s

REAL_SOURCE_PRIVACY_AND_ASSET_AUDIT_REQUIRED_PASS 1266
DEPLOY_HELPER_CLOSURE_PASS 26
```

## Stage 2：Code Quality — PASS

- 结构与大小：deploy 148 行，owner 91 行，package 24 行，最终 test 300 行。部署编排、私有账号绑定、包选择独立；命名沿用继承模块既有约定。代码位置：deploy `:80`、`:90`、`:104`、owner `:13`、`:35`、`:42`、package `:13`、test `:293`。修复过程出现的304行测试文件已压减4行空行，复核后最终专项全部通过。
- 测试真实性：owner 漂移用例调用真实 prepared_settings，确认关闭入口之前失败；迁移矩阵比较旧列、旧行与表集合；真实源码隐私回归补齐空 fixture 的盲区。证据：test `:35`、`:181`、`:293`，上述独立复测。运行中的 Docker/systemd操作由 mock隔离，真实安装与线上权限仍是发布阶段验证，不能用这些 mock 结果替代。
- 安全扫描：新增四个 Python 文件未命中 eval、innerHTML、前端密钥变量或硬编码密钥模式；真实选入源码和 dist 审计通过。owner `:13` 的 UUID/权限检查，`:26` 插值前 canonical UUID验证，`:70` 只读事务，`:85` 不输出个人 ID；deploy `:145` 禁止 -O，继承入口再检查优化与root。固定 /opt 路径属于已授权生产基线，非开发者目录泄漏。
- 异常处理与运行保护：deploy `:104` 迁移开始标记前先核备份和原行，继承 upload deploy `:262` 对任何阶段失败闭锁；owner installed `:85` 失败不写验证凭据；资源完整性与配置差异逐项限制见 Stage 1。没有自动旧库恢复或付费生成调用。
- UI/视觉：本次 5 文件增量没有页面或样式变动；`frontend/package.json:3` 仅版本。按照派发范围不重复产品视觉审查，沿用产品报告 `docs/reviews/SKILL-AVAILABILITY-20261022.md` 的本地视觉证据；正式线上页面验收仍由主 Agent 部署后执行。

最终 PASS 仅授权主 Agent 对本报告指定快照登记审查凭据；不代表已提交、已产生不可变归档、已完成镜像安装测试或已部署生产。
