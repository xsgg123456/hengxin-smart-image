# Phase 18 五角色与海外成员管理验证

## 范围与实现

本地开发，承接 Phase17 的统一身份、海外独立成员与业务会话。实施合同见 [合同](OVERSEAS-PHASE18-CONTRACT.md)，后端操作说明及初始化命令见 [后端记录](OVERSEAS-PHASE18-BACKEND.md)。

- 五角色、兼任角色能力并集；列表 SQL 条件与详情/动作同源。普通运营限本人创建，普通设计限分配本人，两类主管与超级管理员可读全部海外任务。超级管理员不隐含提交或设计动作。
- 成员分页、检索、详情、五角色授权/启停、乐观版本与审计；姓名部门只读。事务锁保护最后有效管理员，等锁后重新授权，停用撤销全部海外会话。
- 显式初始化只作用于已验证登记的海外身份；不在登录或启动自动授予角色。海外迁移0003保留旧成员、角色和状态，国内仍0027。
- 续建既有 OverseasMembers 与 Art 布局，正式入口提供真实成员管理，专用预览继续独立。任务范围策略已可复用，任务接口、上传、生图尚属后续 Phase。

## 验证证据

2026-10-12 本轮全量后端：Docker Linux Python 环境运行 `python -m pytest -q -rs --disable-warnings -p no:cacheprovider`，独立 PostgreSQL17 与 Redis7，设置 TEST_DATABASE_URL、API_IMAGE_TEST_DATABASE_URL、TEST_OVERSEAS_DATABASE_URL、TEST_OVERSEAS_MEMBERS_DATABASE_URL、TEST_IDENTITY_REDIS_URL。

输出：`1812 passed, 17 skipped, 15 warnings in 305.81s`，退出0。日志 `output/overseas-phase18-backend-final.log`。17项跳过均为既有专用宿主条件：9项本地 Linux Skill、1项非root WSL、7项root/只读Worker/Bubblewrap；没有把跳过项计入通过。

专项：成员后端92项通过，无跳过；真实PG六类竞争（自行/互相降权、同版本编辑、等锁期间撤权/停用、并发初始化）及0002存量升级通过。主线程策略/身份/迁移64项通过，日志 `output/overseas-phase18-policy-migration.log`。

后端构建：`docker build -t hengxin-smart-image-backend:phase18 -f infra/Dockerfile.backend .` 退出0，日志 `output/overseas-phase18-build.log`。

真实三API/两库/Redis集成两轮通过：`python hengxin-smart-image/infra/identity-test/run.py --phase18` 与 `--phase18 --serve --origin http://127.0.0.1:3015`。只有外部钉钉provider为替身，详见 [真实HTTP记录](OVERSEAS-PHASE18-INTEGRATION.md)。

前端 `pnpm test` 输出261/261、无跳过；`pnpm typecheck` 退出0；`pnpm build` 与 `pnpm build:overseas` 均成功。详细命令、交互与视觉证据见 [前端记录](../hengxin-smart-image/frontend/PHASE18-MEMBERS.md)。

浏览器：真实五角色及国内管理员兼海外普通成员共6种身份，管理菜单/直链403/多角色保存/审计/刷新/切换/统一退出全部通过；成员故障脚本覆盖分页第2页、筛选回第1页、加载与空态、禁用确认、409刷新、断网/401/403/撤权。空态、加载和错误提示通过逐层祖先裁切检查；390×844可滚动到操作列并打开编辑，保存按钮完整可见。卡片16px圆角与一期邻居一致。

Phase17真实四授权组合、身份故障脚本回归通过；原模拟预览管理5组、框架4组、完整流程5组均通过。测试使用独立浏览器上下文；预览没有调用真实业务API。修复加载清总数导致分页回1的问题，并由浏览器明确断言最后请求仍为page=2。

独立审查 Stage1/Stage2 均PASS，未发现HIGH/MEDIUM问题，报告 [两阶段审查](reviews/OVERSEAS-PHASE18-REVIEW-20261012.md)。审查者独立复跑后端79项（包含真实PG竞争/迁移）、前端261项、类型、正式构建（34.86s）、六真实身份与故障浏览器、一期邻居视觉及首页导航；均通过。最终快照 `b28b81af2f3f97eff9b93dd8a298207fe57e54e1384165f4162a814a61d2921a`，构建生成声明恢复后独立核对一致。Phase18四步验收完成。

本轮3015、测试PG/Redis/三API/网络已清理，原3012和既有测试资源保留。提交只纳入正式Phase18及必需共享header/search适配，其他既有预览与框架规则改动留在原工作区。未推送或部署。

## 边界与下一步

未操作生产，未连接真实钉钉、调用收费模型或部署。本地测试不代替外部认证及生产验收。下一阶段 Phase19 接图需任务、多SKU、提交指定设计、范围查询与改派，复用本阶段策略和成员身份。
