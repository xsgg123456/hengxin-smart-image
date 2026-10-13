# 海外二期需求与复用背景（2026-10-12）

> 本文原任务清单已由根目录 `DEV-PLAN.md` 顶部的 Phase 16–25 正式计划替代。实施顺序、子任务状态、验收及新窗口交接只在 `DEV-PLAN.md` 维护，禁止按本文件旧“当前执行”段直接开工。

## 开发授权与范围
用户授权开始本地开发，禁止重复造轮子。先拆分任务，按独立验收逐项实现。生产部署、迁移、真实收费调用、自动清理不在本次授权内。已验收前端预览作为直接续建基础，不重新制作页面。

## 确定业务合同
- 统一钉钉企业身份认证；国内和海外授权/会话独立，只有海外权限也能完成身份登录。
- 同机独立服务、数据库/凭据、私有图片存储/凭据、队列/缓存及执行目录；国内超级管理员不继承海外权限。
- 海外CLI独立最多5个执行作业，分析/生图/返工共享海外额度；人工审核不占名额。账号暂可相同，认证配置和可写会话目录独立；日后只换海外账号。
- 五角色：operator运营（本人提交），operator_manager运营主管（全部海外运营任务/统计），designer设计（分配本人），design_manager设计主管（全部海外设计任务、代处理及改派），super_admin超级管理员（全部海外数据及成员/配置/改派）。暂不分团队。2026-10-13更新：每人只能一个角色，超级管理员拥有全部海外查看和操作权限，包括提交及审核；正式实现待同步。
- 运营提交必须指定已启用设计人员，图需文件/竞品表至少一份，多SKU无颜色。设计主管/超级管理员可改派并留审计，原设计撤权，执行中作业不因改派自动重启。
- 六节点运营提交→AI分析→设计确认→AI生图→逐图审核→归档，不含资料审核/退回运营/待分配。修改意见重新分析，单图返工只影响目标图片，全SKU通过才能整套归档。
- 默认整套分析、按SKU生图、单图返工；任务/方案/图片/执行版本分别记录，幂等和乐观并发防重复/覆盖。超时沿用一期机制，未知进程先核实不得盲重试。正式资料/成品/版本保留，自动清理默认关闭。

## 技术栈及复用约束
沿用现有Python3.12、FastAPI0.139.2、SQLAlchemy2.0.51、Pydantic2.13.4、Celery5.6.3、PostgreSQL、Redis、MinIO；前端沿用Vue3/Element Plus/Art Design Pro。版本以现有pyproject、锁文件为准，不升级依赖。设置隔离使用Pydantic Settings现有能力（官方https://fastapi.tiangolo.com/advanced/settings/）。

直接复用：frontend既有overseas业务页面和Art框架、AnnotationCanvas；backend/app/db/session.py连接池、storage/minio_store.py、errors.py、http_timing.py、execution/process.py及workspace.py、公共事件脱敏、输出校验等。
适配后复用：auth/dingtalk.py身份交换（拆除国内角色绑定）；files上传/下载（注入海外授权）；tasks幂等/租约/outbox/claim（海外表和状态）；execution物料/提示词/交付（海外协议）；management统计/Skill/配置接口（海外数据源）。不能直接挂载含国内业务查询的router，也不能复制整套backend再改名字。
只新增海外特有业务：五角色策略、设计分配、图需资料解析协议、排版方案版本、SKU执行编排。共享逻辑只保留一个实现，按需增加显式配置/依赖参数并做一期回归，避免提前大规模重构。

## 十个任务
|编号|交付与验收|复用基础|关键文件与依赖|
|---|---|---|---|
|T1|独立配置/启动入口、同机隔离运行清单；缺海外配置拒绝启动，不回退国内环境；独立DB/存储/队列的隔离集成验收|core/config、db/session、MinioStore、错误与计时中间件|backend/app/overseas/{config,main}.py；core/config.py；infra/compose.overseas.yaml、.env.overseas.example；tests/test_overseas_configuration.py；无依赖|
|T2|统一身份认证后双业务会话；海外单独授权用户可登录，国内cookie不能直接访问海外|auth/dingtalk、sessions及现有登录页/BusinessEntry|backend/app/modules/auth/{dingtalk,router,sessions}.py；app/overseas/auth/；frontend/src/api/auth.ts、views/auth/；依赖T1|
|T3|五种单角色、超级管理员全权限、成员启停、接口/查询/文件权限共用策略；越权拒绝、主管全域、超级管理员管理权限|一期权限依赖、用户管理表格与表单|app/overseas/{models,permissions,members}.py；migrations/overseas/；frontend/src/views/overseas/admin/及overseas-preview/access.ts；依赖T2|
|T4|真实图需提交/列表/详情，多SKU、必选设计，主管改派及审计，重放幂等|现有OverseasCreate/Workspace/TaskInfo、一期幂等策略|app/overseas/tasks/；frontend/src/views/overseas/{OverseasCreate,OverseasWorkspace,OverseasTaskInfo}.vue；frontend/src/api/overseas/；依赖T3|
|T5|上传/解析PDF、Word、Excel等，至少一份资料；原件/解析版本保存，文件读取按所属任务授权|files验证/流式传输、MinioStore、前端ElUpload/资料预览|app/overseas/materials/；app/modules/files可注入公共方法；frontend/src/views/overseas/OverseasMaterialPreview.vue；依赖T3，可与T4并行|
|T6|海外CLI专用队列，集群总并发≤5，排队/取消/失联恢复/事件流；同账号也不串会话|一期执行门闩、租约/outbox、workspace/process、事件输出/容量预留|app/overseas/execution/；app/execution/公共可注入接口；infra海外worker配置；依赖T1/T4/T5|
|T7|整套资料分析，结构化方案验证/修改/确认；冻结资料/Skill/方案版本，重复确认拒绝|CLI执行器、Skill版本快照、OverseasDetail方案界面|app/overseas/plans/；frontend/src/views/overseas/OverseasDetail.vue；依赖T6|
|T8|按SKU生图、单图标注返工、多版本、审核与整套归档；已成功SKU不重复运行，跨页并发拒绝|一期AnnotationCanvas、图片版本/交付验证、ElImage，现有海外Pictures/Archive|app/overseas/{generation,pictures,archives}/；frontend/src/views/overseas/{OverseasPictures,OverseasAnnotation,OverseasArchive}.vue；依赖T7|
|T9|管理五页接真实海外统计/监控/成员/Skill/配置；非管理员受限，统计口径可追溯|一期管理公共组件/统计事实思路/Skill校验；现有海外admin页面|app/overseas/management/；frontend/src/views/overseas/admin/；依赖T3/T6/T8|
|T10|统一入口全流程联调、真实隔离环境数据库/文件越权测试、5并发/失联/改派竞争、一期回归、备份恢复方案|现有pytest、PG隔离测试、Playwright、harness审查协议|backend/tests/test_overseas_*；frontend/tests/overseas-*.browser.mjs；infra验证脚本及docs验收报告；依赖T1–T9|

T1→T2→T3→(T4与T5)→T6→T7→T8→T9→T10。每任务类型/编译、测试、功能验收和独立review，没验过不标完成。真实钉钉/生产资源验收要等部署授权，不用模拟结果代替。

## 当前状态入口

查看根目录 `DEV-PLAN.md` 的“新窗口交接与当前事实”和“Phase 16”。本文件不维护实施状态；当前任务状态与验证证据以根计划为准。前端已有模拟预览，不代表正式五角色/设计分配/真实接口已经完成。
