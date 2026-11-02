# 图需语言及归档六字段最终差异复核

审查日期：2026-11-02。按 `.agents/skills/code-review/SKILL.md` 执行独立两阶段差异审查；未修改代码、未提交、未登记批准。

## 候选与范围

- 本次 candidateId：`a1eb4c2a58bd081efa0de3ee7027b5bbaca41a5f1c1960614f592bf77b7cfdc3`。
- 上轮 candidateId：`7d1fa3d7af3d619fb6cb3d0f826f401df8bd70a29e98c583acfd6adf8e8d6ac6`。完整两阶段报告为 `docs/reviews/REQUIREMENT-LANGUAGE-20261102.md:1`；本报告与其共同构成最终证据，不将旧报告直接当作新候选的批准。
- 已完整读取 AGENTS、code-review skill、`docs/HARNESS-REVIEW.md`、`docs/REQUIREMENT-LANGUAGE-20261102.md` 及上轮报告。复核范围仅为两候选差异、受影响迁移原文与测试真实性、分批回归及修正回归证据。无新增产品需求。
- 唯一代码差异：`hengxin-smart-image/backend/tests/test_studio_material_list_migration.py:68` 的 additions 字典新增 `'overseas_tasks': (None,)`，原会话/上传补列预期及所有断言均保留。
- 快照证明：读取当前 candidate 文件映射，使用 `.codex/hooks/review_files.py:35` 的 digest 与 `:47` 的 identity；仅将上述测试的映射替换为其 HEAD 原文 digest，重算结果精确等于上轮 candidateId。当前 `review-status` 返回 currentId 精确等于本次 candidateId。由此确认其余受控代码（业务、前端、发布脚本、依赖、框架规则）无变化；不是仅依赖主Agent口述。

```text
current candidate: a1eb4c2a58bd081efa0de3ee7027b5bbaca41a5f1c1960614f592bf77b7cfdc3
replace only changed test with HEAD: 7d1fa3d7af3d619fb6cb3d0f826f401df8bd70a29e98c583acfd6adf8e8d6ac6
repair archive matches current backend files: 645
```

## Stage 1 — Spec Compliance：PASS

以下逐项保留完整合同覆盖，并明确本轮影响；代码证据及前次行为验证详见所引报告行。

| 合同项 | 最终复核结论与证据 |
|---|---|
| 必填语言、四值顺序、默认空、前后端拒绝缺省/空/非法 | 完整实现，未变；前报告 `:16`，对应 schemas.py:23、languages.ts:1。 |
| 新建平台空、提示与必填；已有平台/品牌及其他校验保留 | 完整实现，未变；前报告 `:17`、`:18`，含可达历史 TikTok Shop 重提证据。 |
| 语言保存、详情显示、重提回填与审核快照 | 完整实现，未变；前报告 `:18`、`:19`。 |
| 归档顶部六项、标签一致、自动独立快照、来源删除后可读 | 完整实现，未变；前报告 `:20`、`:21`。 |
| 历史可空、未知未设置、不猜测、不覆盖；历史任务继续读取/审核/设计/归档 | 完整实现；前报告 `:22`、`:23`；本次新增测试预期正是 nullable 列兼容要求。 |
| 0025 增量迁移、只补真实关联历史归档、国内隔离 | 完整实现；`hengxin-smart-image/backend/migrations/overseas/versions/0025_requirement_language.py:11` 添加无默认 nullable 列；`:14` 的 COALESCE/关联条件未变。本次真实PG回归包括新迁移测试，5 passed。 |
| 权限、幂等、版本、market/remarks 兼容；不改 Skill、不增模型调用 | 完整实现，未变；前报告 `:25`、`:27`，唯一新增字典项不改变运行时。 |
| 前端/后端/浏览器/构建与独立审查 | 代码验收证据已覆盖；前报告 `:51` 起及本报告原始证据。分批修正回归，不宣称全套一次全绿。 |
| 0.2.59、基线0.2.58/0024、10 API/8 native、原native archive service保持 | 发布工具实现完整，未变；前报告 `:26`、`:28`。 |
| 排空、备份、恢复、迁移、配置/国内/Skill/五人授权保持、入口验收、不触发生产任务 | 发布工具实现完整，未变；前报告 `:27`、`:29`。生产安装、部署及正式入口验收仍待后续执行。 |

本次断言有效：测试先在 overseas_0016 建真实历史任务（`test_studio_material_list_migration.py:33`），随后 `migrate(env)` 升到 head（`:53`；实现 `test_overseas_database.py:43`），snapshot 使用 `SELECT *`（后者 `:144`）。0025 在任务表末尾新增 language，因此旧元组追加 None 是真实预期。`:71` 仍逐表逐行精确相等，旧业务列、行数、顺序变化都会失败；没有删除断言、切片截断新列或跳过任务表。国内完整快照和 forward-only 断言仍在 `:72`、`:73`。

UI一致性/引导真实性：无UI或交互代码变化；承接前报告 `:16` 至 `:20` 的真实交互验证以及 `:35` 已打开实际页面截图与邻居基准的视觉对比，本轮未重复打开页面。Spec漂移：唯一变化为合同要求的历史兼容测试预期，无新增页面/API/业务功能。部分实现、未实现、HIGH：本轮代码范围内均无；生产执行未验收不冒充已完成。

## Stage 2 — Code Quality：PASS

- 测试真实性：新增预期符合真实 PostgreSQL 列顺序及 NULL 语义；原测试全部数据保持、唯一约束、国内隔离、重复迁移、禁止降级断言未删除（上述测试 `:55` 至 `:74`）。新0025测试 `hengxin-smart-image/backend/tests/test_overseas_requirement_language_migration.py:43` 至 `:63` 继续覆盖旧列不变、真实来源/无来源、已有快照不覆盖与重复执行。
- 测试包真实性：独立核对 `output/language-release/batch_repair-manifest.json:2` SHA256 与 tar.gz 一致；归档内645个可映射后端文件逐字节比对当前工作树（仅CRLF归一），全部匹配。`run_batch_repair.py:25` 启动无外网隔离PG，`:35` 传入 TEST_OVERSEAS_DATABASE_URL 并执行4模块，原始结果5 passed、0 skipped。不是无数据库条件下跳过所得PASS。
- 命名/类型/结构：新增一项沿用 additions 的既有表名到tuple映射，文件76行，没有新分支或重复逻辑；`git diff --check` exit 0，仅Git CRLF转换提示，无空白错误。其余结构与类型审查沿用前报告 `:41`，受控内容相同。
- 安全：变更只有静态表名及 None，无密钥、注入、危险函数或执行路径。前报告 `:45` 的安全检查仍对应相同源码；`:46` 已有依赖审计 high39/moderate38/low5 的边界不被本次PASS消除，不声称全项目依赖无漏洞。
- 视觉：前端内容与前报告 `:35` 的实际渲染和邻居对比完全相同，本轮不产生视觉变更。

未解决 HIGH/MEDIUM：无。新增 LOW：无。

## 编译、回归原始证据及边界

主Agent执行、审查者直接读取日志；前轮46个后端与132个发布测试为前轮reviewer独立运行，本轮没有把它们改称自己新跑。

`output/language-release/frontend-build.log:4`、`:8`、`:10`、`:578`：

```text
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4709 modules transformed.
✓ built in 34.82s
```

`hengxin-smart-image/frontend/language-tests.log:1342`：

```text
ℹ tests 448
ℹ suites 0
ℹ pass 448
ℹ fail 0
```

`output/language-release/browser-final.log:1`：

```text
PASS empty platform/language required; four languages create/resubmit/details; null/absent legacy requires selection; historical platform retained; archive six independent snapshot fields and unknowns; 1366/390 visible clipping checks
```

历史Windows全套结果 `hengxin-smart-image/backend/language-regression.log:370`：

```text
8 failed, 2615 passed, 416 skipped, 6 warnings in 476.71s (0:07:56)
```

Linux A批60模块（`output/language-release/batch_a.stdout:139`）：

```text
2 failed, 530 passed, 2 warnings in 351.93s (0:05:51)
```

Linux B批75模块，包含A批两处旧迁移测试修正（清单 `output/language-release/batch_b-manifest.json:78`；结果 `batch_b.stdout:122`）：

```text
1 failed, 1079 passed, 2 skipped, 2 warnings in 527.83s (0:08:47)
```

B唯一失败为本次 studio material 旧迁移预期，日志 `:121` 定位同一测试。修正后最终4迁移模块真实PG回归（`output/language-release/batch_repair.stdout:24`，清单 `batch_repair-manifest.json:4`）：

```text
ISOLATED_TESTS 4
.....                                                                    [100%]
5 passed in 37.53s
```

四模块为 management、materials、studio material list、requirement language；覆盖三处旧预期修正及新0025迁移。A/B批曾失败，最终补跑为受影响模块回归；不能写成同一最终候选全套一次通过，不能简单累加为无重复的测试总数。B的两处skip对应Windows junction（`hengxin-smart-image/backend/tests/test_studio_context_safety.py:142`）和需私有 STUDIO_INCIDENT_FIXTURE 的历史生产样本（`test_studio_open_outputs.py:87`）；它们不构成本次语言功能缺测通过。主Agent另报Windows junction补测1 passed，本报告未读取该次独立原始日志，故不将该口述计作本轮已核验证据。

## 交接

Stage 1 PASS；Stage 2 PASS，仅适用于上述新 candidateId 的代码审查。最终修正回归结果已核实，可由主Agent使用本报告登记同一候选的两阶段凭据；不得写 `.needs-review` clean。普通报告Markdown不改变代码快照。实际发布包安装、生产迁移/部署、正式入口目视/健康/版本/哈希仍需后续验收；本报告没有宣称这些步骤已完成。
