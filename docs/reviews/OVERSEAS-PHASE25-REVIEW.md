# Phase25 独立两阶段审查

审查日期：2026-10-13。最终 candidateId：`5072f0ce8509b03da3c96a7a7efa528f3d4db52fffb7bff580ffec078003f294`。基线：Phase24 `e0c2acc`。使用 `.agents/skills/code-review/SKILL.md`。

范围：Phase25 全流程验收合同、DEV-PLAN 25.1–25.3；新增四个 Python 验收/恢复/关闭模块、run/checks 接入、七组真实浏览器入口及四个旧真实浏览器断言修订、交付文档。下文代码路径相对 `hengxin-smart-image/`。既存预览、技能、package/locales 等用户改动不属于本次审查或提交。生产部署、真实钉钉、收费模型、目标主机灾备指标不在本次通过范围。

审查依据已读取：AGENTS.md、审查协议、Product-Spec.md:956 的正式开发授权及其引用的完整海外业务合同、DEV-PLAN.md:178、Phase25 合同、全栈验收与部署清单。没有以主线声称通过代替日志与源码检查。

## 快照变化及问题闭环

初始候选 `1a3e313e2bc5764e70ca8bc4e40ce935099ac76d8a0653368502fb823f229841` 审查发现 MEDIUM：checks.py 新增后 311 行，违反 skill 的 300 行上限；另计划总览 Phase22–24 与完成事实不一致。已通知主线，未自行修复。

主线抽取 `infra/identity-test/shutdown.py:4`，checks.py 降为 300 行，更新计划总览。重新从 Stage1 核对：`checks.py:295` 进入关闭函数；`shutdown.py:6` 等待所有 API 退出，随后对象恢复；`run.py:87` 确认 runner 正常退出后才调用数据库恢复。异常不放行数据库恢复，engine/Redis 在 finally 关闭。此抽取没有变更业务实现或浏览器断言。review-status 实查 currentId 与上述最终候选一致；旧候选结论不用于批准新版本。

## Stage1：PASS

|合同/计划条目|结论与代码证据|实际证据|
|---|---|---|
|25.1 统一身份、五角色与兼任|完整。`infra/identity-test/checks.py:134` 身份四授权组合与票据/Cookie检查；`:247` 起复用 Phase18–24；`frontend/tests/overseas-fullstack-real.browser.mjs:7` 串行七组真实浏览器|`output/phase25-http-reviewed.log:15` 起授权及失效检查；`output/phase25-browser.log` 六身份/七组全部 PASS|
|必选设计、多SKU、资料及六节点|完整。`phase19_checks.py`、`phase20_checks.py` 由 checks 顺序执行；`phase22_checks.py:15` 真实离线子进程方案/重分析/确认；`phase23_checks.py:25` 真实图片、部分失败恢复、返工历史、审核归档；`phase24_checks.py:14` 统计/Skill/配置|最终 HTTP 日志 40–62 行各阶段 PASS；浏览器真实资料/方案/图片/管理 PASS。离线子进程证据不等于模型质量验收|
|宽窄屏、空/错/冲突/无权限|完整覆盖已交付范围。真实脚本保留菜单、直链、刷新、资料失败重试、409草稿及窄屏断言；`frontend/tests/overseas-management-faults.browser.mjs:69` 空列表、`:80` 冲突草稿等是既有故障注入证据|本轮七组真实浏览器日志；既有 Phase24 已审故障证据单独承接，未冒称本轮真实服务发生所有人工注入故障|
|25.2 资源级双向隔离|完整。`infra/overseas/verify_resources.py:45` 新建独立账号拓扑、`:78` 检查非root/API秘密/卷网络；本轮业务联调拓扑与最小权限凭据拓扑分开验证|`output/phase25-resource-isolation.log:1` 起：PG/MinIO/Redis互访拒绝、DML允许DDL拒绝、私有桶，三资源故障ready503/live200及恢复PASS|
|所有派生资源按当前权限撤权|完整。`phase25_checks.py:43` 汇总资料原件、方案、图片全部历史、任务/jobs/events与ZIP；`:100` 改派后直接403，列表/统计不可见；`:113` 禁用再启用旧cookie仍拒绝、新登录可读；`:119` 还原|最终 HTTP `:63` PASS。五角色新权限读取内容哈希一致；既有5作业executionCount不变，国内全表快照与对象etag不变|
|并发5、重复、失联、取消与竞争|完整。`backend/tests/test_overseas_concurrency.py:36` 12线程争6作业仅5成功，租约失效仍占槽；`:64` 幂等与事务回滚；`test_overseas_runner.py:100` 取消竞争、`:114` 租约失效拒绝发布；`phase21_checks.py:12` 真实Redis/outbox及事件撤权|完整后端回归2038通过；`infra/overseas/regression.py:39` 注入真实PG测试连接，并非无数据库跳过；最终 HTTP `:47` PASS|
|25.3 对象备份恢复|完整。`object_restore.py:23` 内容size/SHA256/type清单；`:50` 随机创建两空桶，源→备份→恢复；`:63` 匿名AccessDenied；`:72` 只删除本轮成功创建目标，不删除源|最终复跑12对象、937字节，全部哈希与类型一致、源etag不变，日志`:77` PASS|
|数据库备份恢复与静止边界|完整。`database_restore.py:7` 限定调用者随机PG容器；`:22` 所有public表行排序哈希/数量及sequence位置；`:46` pg_dump自定义格式→新空库pg_restore；`:54` 完整比对、源不变；`:61` 只删成功新建恢复库|最终复跑`:78`：27表/序列、360行、99683字节，全部一致，随后CLEANED。serve浏览器轮459行与110472字节属不同数据量，未混作同次快照|
|交付清单、外部边界与本地提交|完整准备。`docs/OVERSEAS-RELEASE-CHECKLIST.md:5` 起列资源/身份、迁移/排空、独立认证、备份/恢复/回滚及关闭自动清理；`docs/OVERSEAS-FULLSTACK-VALIDATION.md` 列可复跑入口及未验范围|未把17跳过计通过；真实钉钉/收费图片质量/生产配额/目标沙箱/RPO与RTO保留未验。审查批准与本地中文提交由主线随后登记，不假称已经提交|

未发现本范围部分实现、未实现或 HIGH。无新增业务页面/API/表；新增验收脚本均对应 Phase25 合同，无 Spec 漂移。菜单修订用真实 capabilities 取代早期“尚未接入业务”断言，并保留禁止模拟角色切换及后端拒绝检查（unified-identity-real.browser.mjs:35、overseas-members-real.browser.mjs:20、overseas-tasks-real.browser.mjs:21）。

## Stage2：PASS

- 结构：新增恢复/验收模块均不超300行；关闭抽取问题已修，checks.py为300行。七组串行入口遇异常或非0退出立即失败（overseas-fullstack-real.browser.mjs:11）。本次无新增类型逃逸或产品依赖。
- 测试真实性：读取真实HTTP和数据库断言，确认未用“有输出文件”代替内容一致；ZIP比较冻结文件内容而非含时间戳的容器字节（phase25_checks.py:55）。PG所有表与序列逐项比对，包含实际方案/图片版本/归档/Skill/配置非空断言（database_restore.py:43）。
- 安全：恢复子进程使用参数数组，不启shell；动态SQL表/序列名来自自有catalog且正则限字符（database_restore.py:28）。MinIO目标为UUID新建桶且记录所有权，PG目标只在本轮随机容器内createdb成功后删除。新文件危险函数/前端秘密模式扫描无命中。现有明文fixture凭据只对应隔离网络，不当作生产凭据。没有生产读取、删除或收费执行。
- 视觉：本轮无UI源码变更，不存在新增页面需要重新设计比对。实际打开查看本轮 `output/playwright/phase24/real-admin.png`（390px完整配置）、既有 `phase24/review-users.png` 与 `phase23/review-neighbor.png` 渲染证据：一致的浅灰底、白卡、蓝按钮、间距与侧栏；窄屏控件未横向溢出。本轮未重启页面作现场视觉验收，Phase24现场比对结论仅适用未变UI，真实七组浏览器为本轮交互证据。
- 17跳过定位：`backend/tests/test_local_skills_linux.py:12` 与 `test_skill_catalog_linux.py:11` 的显式root/nobody/Bubblewrap开关16项；`test_phase11a_environment.py:167` 的既有非root WSL运行时1项。通用容器未完成这些宿主验证，部署清单要求目标主机另验；15条warning保留，不伪称零warning。

## 测试与编译原始输出

读取 `output/phase25-backend.log`、`phase25-frontend-tests.log`、`phase25-frontend-build.log`：

```text
2038 passed, 17 skipped, 15 warnings in 350.51s (0:05:50)
ℹ tests 282
ℹ pass 282
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
> vue-tsc --noEmit && vite build
✓ 4661 modules transformed.
✓ built in 36.33s
```

最终快照实际完整复跑 `output/phase25-http-reviewed.log` 尾部原文：

```text
PASS Phase25 object backup/restore: 12 objects, 937 bytes, SHA256/size/content-type equal; private backup and restore buckets; source unchanged
PASS Phase25 pg_dump/pg_restore: 27 tables/sequences, 360 rows, 99683 backup bytes; all row hashes and sequence positions match; source unchanged
CLEANED hx-p25-b2b81f3b97de
```

真实浏览器原文：

```text
PASS Phase25 all seven real API browser groups
```

最终结论：Stage1 PASS；Stage2 PASS。仅批准所列最终候选及Phase25本地范围。主线使用 review-approve 登记相同 candidateId 与本报告，提交前后核对快照；不写 `.needs-review` clean。
