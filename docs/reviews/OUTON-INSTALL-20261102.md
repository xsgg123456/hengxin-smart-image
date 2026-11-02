# OUTON 安装与目标站点移除审查

- 日期：2026-11-02；独立 reviewer：outon_review。
- 最终 candidateId：`ddb0da3ae29f2612b80cab0f6b58a65c66f255e89ae3c067c5e34f845bbc4474`。
- 结论：**Stage 1 PASS；Stage 2 PASS（代码与部署前审查）**。未解决 HIGH / MEDIUM：0。
- 此结论允许主 Agent 为上述代码快照登记 review-approve；不代表生产已经安装、生产完整数据库恢复演练已经通过或正式页面已经验收。
- 发布状态：用户最新要求“代码改完先不要部署，还有其他问题”。本轮仅完成本地审查，发布暂停；不执行生产变更，等待用户补充。主 Agent 报告仅已上传源包压缩文件，尚未安装或切换服务；本报告不将上传视作安装成功。
- 范围：本轮未提交变更中的任务 schemas/requirements、前端任务 API/共用表单/workflow、对应测试与版本 0.2.58；七个 `scripts/release/outon-*.py`、三个 `test_outon_*.py`、源包哈希 manifest。需求依据为 `Product-Spec.md:1364`–1368 的批准段；不是对整份历史 Spec 的重新验收。

## 快照变化与复核

1. 初始候选 `23b87e58d8cd8969b786377cd12c132b722efe42e030f8597d81c19451c2e25d`：Stage 2 发现恢复测试使用不同数据库名的 HIGH 缺陷，未批准。
2. 主 Agent 修改 `scripts/release/outon-database.py:42`–49 与 `scripts/release/test_outon_safety.py:164` 后，候选变为 `a2d3f540f6c192e26e6883cb29e5db9c8641608c45842c7ea23a2b7157361d9d`。重新检查 Stage 1，改动只影响隔离恢复验证，不改变业务范围；复跑发布工具测试。
3. 本地真实浏览器发现 `hengxin-smart-image/frontend/tests/overseas-polish.browser.mjs:77` 的旧平台顺序断言失败，主 Agent 对齐 `src/views/overseas/platforms.ts:1` 的既有顺序。重新检查 Stage 1 并复跑该浏览器脚本，PASS。
4. reviewer 启动的本地 Vite 自动生成过 `src/types/import/components.d.ts`；停止该进程后已恢复审查前内容，最终该文件无 diff。没有修改产品实现、提交或登记批准凭据。

## Stage 1：Spec Compliance — PASS

| Spec 条目 | 实现与证据 | 结论 |
| --- | --- | --- |
| 完整安装指定 OUTON 包，脚本/参考/字体/素材保持 | `scripts/release/outon-source.py:33` 读取完整 tree；`outon-skill.py:60`–71 合并并验证完整 bundle。reviewer 对原目录及 `output/outon-install/source/amazon-outon-image-brief-to-prompts` 全部文件独立计算 SHA-256：各 51 文件均与 `docs/OUTON-SOURCE-MANIFEST-20261102.json:3`、`:249` 对应条目一致 | 完整实现 |
| 仅两份来源 JSON 做相对路径适配，不改原目录 | `outon-source.py:10`–28 只更新来源字段；`:47`–48 再核原目录。独立 JSON 递归比较仅有 manifest 中 fonts.sources、logos.source 和 font-reference 中 sources.source 叶子变化；其余 49 文件字节相同；清单见 manifest `:495` | 完整实现 |
| 既有 Skill 内容、分组、开关不变 | `outon-skill.py:23` 保留 previous.items；`:66`–69 复制并逐包验签；`:99` 比较旧 manifest；`:84`、`:101`–102 比较安装前后完整 availability 表。安装器不执行数据库写入 | 完整实现 |
| 新增 Skill 未分组、默认关闭，不自动关联平台 | `outon-skill.py:85` 要求不存在该 name 配置行；管理实现 `backend/app/overseas/management/skills.py:23`–27 对不存在行返回 False / []，安装后比对表未变。数据库 id 实为 Skill name，区别于 catalog 对外 UUID；此前对此提出的疑点已撤销 | 完整实现 |
| API / Worker 可读取完整实际包 | `outon-skill.py:103`–116 分别调用容器和降权原生 Worker verify，比较 release、包数和目录设备/inode；实际线上结果尚待安装后取得 | 校验机制完整实现；生产执行待验收 |
| 提交及修改图需删除站点输入，平台/品牌/SKU保留 | `frontend/src/views/overseas/OverseasCreate.vue:33`–42 保留平台与品牌、移除站点；`OverseasRequirementsResubmit.vue:3` 共用该表单。真实 SFC 用例 `tests/overseas-requirements-component.test.ts:80` 同时覆盖新建/修改；本地真实浏览器检查站点输入数量为0 | 完整实现 |
| 新任务不传或空 market 通过，仍限制类型/长度 | `backend/app/overseas/tasks/schemas.py:23` 默认空值、最长60；前端 `src/api/overseas/tasks.ts:90` 与 `src/views/overseas/workflow.ts:23` 删除必填。`backend/tests/test_overseas_market_optional.py:14`、`:33` 覆盖省略、空、空格、历史文本、长度上限及其他必填项 | 完整实现 |
| 历史值兼容、修改保留，不迁移/清空历史记录 | `backend/app/overseas/tasks/requirements.py:90`–91 仅显式传入时赋值；前端 `OverseasRequirementsResubmit.vue:24` 回填任务草稿并 cleanDraft 提交。`test_overseas_market_optional.py:43`–66 验证省略保留、审核历史不变及显式空/省略幂等冲突；组件测试 `:75` 验证历史“美国”随请求保留 | 完整实现 |
| 测试、审查、正式页面核验后交付 | 单元/API、构建、本地浏览器证据见下文；生产镜像安装测试、Skill双运行时校验、管理页未分组/关闭、新建与重提正式页面尚待部署步骤执行 | 部署前代码审查完成；最终交付验收待执行 |

UI 无新增设计，改动仅删除既有共用表单项。实际对比 `output/playwright/overseas-polish/create.png` 与邻居 `formal-1366.png`：沿用同一侧栏、背景、白卡、蓝色按钮与边框，表单保留两列结构，无新增站点占位或死引导。对应实现 `OverseasCreate.vue:18`–42；浏览器证据生成点 `tests/overseas-polish.browser.mjs:51`、`:82`。这是本地实际 Vue/Element 渲染，API 使用受控 fixture，不是生产截图。

Spec 漂移检查：本轮未新增业务页面、API、数据库表、迁移、分组默认关联或额外开关；新增工具用于批准的生产安装和两文件发布。封闭 API 文件清单 `scripts/release/outon-runtime.py:22`；版本更新 `frontend/package.json:3`。

## Stage 2：Code Quality — PASS

| 检查 | 证据与结论 |
| --- | --- |
| 职责与规模 | 七个新增发布工具分别负责源包、bundle、环境、发布、数据库、静态资源、Skill安装；69/91/135/68/220/100/78行，均小于300行。业务变更复用既有表单与 Schema，未引入 any；见 `outon-deploy.py:44`、`outon-database.py:25`、`outon-frontend.py:27` |
| 发布边界 | `outon-runtime.py:29`–54 校验基线镜像、仅两个API文件、路径/链接、manifest全文件哈希及多余文件；`outon-deploy.py:20`–41 校验原生 PID/源文件、Skill树与其他容器；`:135`–149 两次空闲检查后只停API/暂停consumer，不重启原生Worker |
| 失败恢复与数据保护 | `outon-database.py:15`–22 要求旧API关闭且consumer暂停；`:42`–55 在独立容器同名数据库恢复并比较全表/列/revision；`:82`–91 校验备份凭据与当前库一致；`outon-deploy.py:152`–162 只允许切换前恢复旧API。HIGH缺陷已修复，见下节 |
| 前端安全切换 | `outon-frontend.py:31`–55 先查碰撞、备份，再上传资源和替换入口；`:74`–87 仅在当前资源仍匹配时回滚，保留两代hash资源。测试 `test_outon_release.py:137`、`:147`、`:156` 覆盖回滚/碰撞/后续发布 |
| 安全扫描 | 新业务代码未新增执行字符串/HTML注入/密钥；发布脚本用参数列表调用subprocess、SQL表名白名单、严格包路径校验。`outon-runtime.py:38`–45、`:61`；来源文件发布前隐私扫描 `outon-source.py:54`–56、`outon-package.py:30`。生产固定路径为安装边界，不是意外泄露本机来源路径 |
| 测试真实性 | 独立复跑后端3文件48项、OUTON工具3文件26项；关键历史值/幂等测试实际走HTTP与数据库事务。脚本单元测试大量mock，仅证明分支与命令构造，不声称生产安装完成。真实PG恢复补充证据如下；浏览器旧断言已修复并实跑PASS |

### 已修复问题

- **HIGH / 已解决：隔离恢复列哈希必然不匹配。** 原实现恢复到 `postgres`，生产为 `hengxin_overseas`，而 `outon-runtime.py:67` 对完整 information_schema.columns 求哈希，包含当前数据库名。官方 [PostgreSQL columns 文档](https://www.postgresql.org/docs/17/infoschema-columns.html) 明确 table_catalog / udt_catalog 包含当前数据库。主 Agent 已改 `outon-database.py:43`、`:46`、`:49` 为隔离容器内同名数据库；`test_outon_safety.py:164` 增加命令断言。reviewer 阅读了真实测试脚本 `output/outon-install/catalog_test.py:1` 及其原始 stdout：不同catalog复现差异、实际pg_dump/pg_restore同名库哈希相同。该小型隔离样本不是生产全库恢复验收。
- **MEDIUM / 已解决：浏览器旧顺序断言阻断本轮UI验证。** `frontend/tests/overseas-polish.browser.mjs:77` 原将Wayfair放末尾，与现行 `src/views/overseas/platforms.ts:3` 第二位不符。第一次实跑 AssertionError；主 Agent 修正后 reviewer 再实跑成功，抵达无站点断言。

### 验证边界

- 后端48项使用 `backend/tests/test_overseas_auth.py:48` 的 `sqlite://` fixture；`outon-deploy.py:124` 传入PG环境变量不会把这组测试变成PG用例。后续执行只能称“Linux已安装镜像中的API契约测试”。真实PG证据当前仅覆盖隔离恢复数据库名问题。
- `outon-skill.py:103`–116 的双运行时读取、全部既有Skill/配置不变、正式管理页未分组及默认关闭，仍须安装后执行并保存证据。
- 本地真实页面通过不替代正式生产新建/重提验收。未把尚未执行的生产测试标成通过。

## 原始验证输出

reviewer 独立后端命令（backend目录）：`.venv/Scripts/python.exe -m pytest -q tests/test_overseas_tasks.py tests/test_overseas_requirements.py tests/test_overseas_market_optional.py`

```text
................................................                         [100%]
48 passed, 2 warnings in 6.81s
```

两项警告为既有 Starlette TestClient 的 httpx / BlockingPortal 弃用提醒，无失败或跳过。

reviewer 独立发布工具命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_outon_release.py scripts/release/test_outon_safety.py scripts/release/test_outon_skill.py`

```text
..........................                                               [100%]
26 passed in 0.66s
```

读取主 Agent 原始构建记录 `output/outon-install/frontend-build.log:3`、`:577`（未重复生成dist）：

```text
> hengxin-smart-image-frontend@0.2.58 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 31.93s
```

读取主 Agent 原始前端单测 `output/remove-market-frontend-test.log` 结尾：

```text
ℹ tests 438
ℹ suites 0
ℹ pass 438
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9277.589
```

reviewer 浏览器实跑 `node tests/overseas-polish.browser.mjs`，本地3032、受控API、真实浏览器/组件；第二次退出码0：

```text
PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/no site input
```

独立源包SHA-256实查输出：

```text
originalEntries 51 exact hash PASS
entries 51 exact hash PASS
changes ['assets/brand/font-reference.json', 'assets/brand/manifest.json'] unchanged files 49
```

主 Agent 真实隔离PG测试原始输出 `output/outon-install/catalog_test.stdout:1`：

```json
{"isolatedPostgres": true, "differentCatalogMismatchReproduced": true, "sameNameRestoreColumnsMatch": true}
```

最终仅批准本文记录的最终快照；旧快照结论不得复用。主 Agent 可通过 review-approve 登记同一 candidateId；遵照用户最新指令暂停发布，部署及生产验收保持未执行状态。
