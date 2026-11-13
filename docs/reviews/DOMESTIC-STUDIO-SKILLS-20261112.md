# 国内 Skills 管理独立审查 · 2026-11-12

- candidateId：`b9bf9b5216a2a6f4a661be2c2e83f47a47aa58b0f8b2a0d9a6e02af8a075064a`（主 Agent 提供；本次未重新固定，也未批准）。
- 范围：国内管理中心 Skills 的权限、五入口绑定、完整目录上传与差异确认、ZIP、启停、删除、业务隔离、发布恢复与并发，以及共享海外实现的影响。工作台、执行器、成品库不在本阶段通过范围；发送防绕过与冻结只审查后续接入边界，不宣称端到端完成。
- 基准：`Product-Spec.md:1-10`、`DEV-PLAN.md:1-10`、`Design-Brief.md:1-5`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-25`、`frontend/preview-domestic-studio/Skills.vue:3-11`；按 `.agents/skills/code-review/SKILL.md` 审查。
- **Stage 1：FAIL；Stage 2：未执行**。存在 HIGH 问题；本报告不能用于 `review-approve`。审查期间没有修改生产代码；工作区含大量已有未提交和未跟踪文件，未独立核实审查期间所有文件均无变化，候选快照一致性须由主 Agent 的 harness 校验；本报告不覆盖后续版本。

## Findings

### HIGH 1：两位管理员保存绑定会静默覆盖对方

并发可靠性在审查范围内，`DEV-PLAN.md:5` 要求并发验证。`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:28-39` 加载并提交五项完整旧快照；`backend/app/modules/domestic_studio/management_router.py:31-38,144-148` 接口没有任何预期版本或原值；`backend/app/modules/domestic_studio/bindings.py:36-59` 虽持有锁，却把请求全部五项写回。两人同时从全空读取，甲绑定 camera、乙绑定 case：甲保存后乙的旧 camera=null 会删除甲的绑定，两个请求都成功。锁只保证串行，不能发现过期编辑。`backend/tests/test_domestic_studio_bindings_pg.py:65-85` 测试发送与绑定锁，并未覆盖两个陈旧管理草稿。应增加冲突检测或可证明不会丢失独立变更的协议，并验证真实 PG 两客户端。

### HIGH 2：删除保留全部实体，持续增长，未达到参考海外删除的行为

`Product-Spec.md:7` 要求参考海外删除，海外真实删除明确为回收无用中央实体（`Product-Spec.md:1482-1483`）。国内 `backend/app/modules/domestic_studio/skill_publication.py:45-58,81-84,120-130` 把该名称所有历史哈希目录列入 retained，包括删除时当前包；因此解除绑定后删除只移除目录索引，包本体仍保留，反复更新/删除可无限累计。`backend/tests/test_domestic_skill_publisher.py:103-110` 实际断言删除后旧包仍可读，未证明无引用内容回收或净释放量。保留潜在运行引用是安全选择，但无完整引用跟踪不能推断所有旧包必需；当前实现也没有国内维护回收入口（`backend/app/modules/domestic_studio/skill_publisher.py:31` 禁止 maintenance）。须建立可靠引用保护及可恢复回收，或者明确由用户批准改变需求；不能宣称与海外删除一致或资源回收完成。

### MEDIUM：正式目录不符合确认预览的绑定信息与入口

预览 `frontend/preview-domestic-studio/Skills.vue:9` 为每行展示绑定工作台、设置绑定操作；实际 `frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:17-22,50-55` 国内目录不含绑定列和行内设置绑定，只能切页逐个检查。已确认预览是视觉和交互依据（`Design-Brief.md:1-5`）。这是代码与预览直接对照，未作实际浏览器渲染或数值比对。

## Stage 1 逐项核对

- **权限，代码具备，实测证据待复核**：`management_router.py:23-26,70-148` 路由依赖 `manage_system`；`app/modules/auth/permissions.py:5-9` 仅 super_admin；发布端 `skill_publication.py:23-29` 复核用户状态、角色和身份来源。`tests/test_domestic_studio_management.py:61-71` 覆盖拒绝；本审查未亲自运行。
- **五入口初始空、绑定与解除，部分实现**：`0033_domestic_studio_bindings.py:11-26` 只建表不插入默认项；`bindings.py:30-33` 缺失项返回空；`DomesticStudioBindings.vue:17-23,35-39` 五项编辑保存；并发丢失见 HIGH 1。
- **上传、完整校验、同名差异、ZIP，代码接入；实际交互未独立验证**：`management_router.py:70-101,120-128` 转发上传、校验、安装和包下载；`OverseasLiveSkills.vue:2-3` 复用上传组件；`OverseasSkillCatalog.vue:22` 国内启用 ZIP 模式。`test_domestic_skill_publisher.py:78-100` 含单文件上传、同名差异断言；该用例不是完整目录和真实浏览器 ZIP 验证，复用组件原有回归结果由主 Agent提供，未独立复跑。
- **启停、绑定保护，代码具备**：`skill_state.py:28-49` 开关检查版本，停用前检查绑定；`skill_publication.py:100-119` 删除前检查绑定和发布版本。测试 `test_domestic_skill_publisher.py:90-96` 检查绑定删除拒绝；物理删除缺陷见 HIGH 2。
- **隔离，代码具备边界，生产环境未验**：`installed_skills.py:16-36` 约束国内 context 与生产目录；`management_router.py:28,46-62` 使用国内根目录、独立 socket；`skill_publisher.py:13-31` 国内 transfer 目录及国内 publication。独立服务进程及目录配置、真实部署尚未验证（`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:16-17`），不能认定已上线可上传。
- **发布恢复，部分证据**：共享 `app/overseas/management/skill_publication.py:35-73,91-108` 通过 journal 与数据库提交判断恢复；`app/overseas/management/skill_publisher.py:21-44,124-151` 启动、定期和写入前恢复；国内提供自己的 audit/gate（`skill_publication.py:33-34,92-95`）。`tests/test_domestic_skill_publisher.py:128-162` 模拟未提交日志和提交失败重试；该测试不能替代真实进程掉电、提交后清理异常以及 PG 0034/0035 迁移验证。
- **后续执行边界，未接入**：`policy.py:33-53` 拒绝客户端自选并要求可信绑定；`bindings.py:71-79` 定义同锁冻结，但执行链未接入（`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:17`）。历史请求持久冻结及变更后不改写未验证。
- **无版本管理 UI**：`skills.vue:3-6` 只有目录和绑定页签；国内目录 `OverseasSkillCatalog.vue:4,22-26` 隐藏平台分类并复用文件操作。未做浏览器全路径核验。
- **Spec 漂移**：`management_router.py:125-128` 有单文件读取 API，为复用文件包能力；未发现独立版本管理 UI。没有完成全仓库漂移穷举，不得据此宣称无其他漂移。

## 验证与缺口

本审查未执行编译、测试或浏览器；因此无编译原始输出。主 Agent 转交的“5、12、39、22 项通过和 vue-tsc 通过”属于转述，并非本审查取得的原始输出，不能视为独立验证。真实 PostgreSQL 仅已被告知覆盖至 0033，0034/0035 的升级、回退策略、隔离及发布恢复尚需真实 PG 证据。未验证浏览器中实际上传多层目录、完整 ZIP 字节、两管理员陈旧绑定保存、发布进程崩溃后的所有提交阶段及共享海外完整回归。Stage 2 的安全扫描、代码质量、实际视觉对比均未执行。
