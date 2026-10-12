# Phase19 图需任务、指定设计与改派验证

## 范围与复用

执行合同见 [Phase19合同](OVERSEAS-PHASE19-CONTRACT.md)。海外任务、SKU、审计事件、幂等请求和出站事件独立持久化，版本迁移至0004；国内保持0027。任务创建必选有效设计，五角色范围查询，主管/超级管理员改派并检查版本，改派后立即按新负责人授权。

直接复用Phase18权限策略、成员身份与权限事务锁；一期与海外共用中立幂等哈希和锁算法，各自注入业务记录模型。前端直接续建原OverseasCreate、OverseasWorkspace和OverseasTaskInfo，真实API适配与预览编排分离。

本阶段保存基础图需，状态为“图需已保存”。资料上传在Phase20、CLI调度在Phase21接入；不创建生图作业、不发布outbox、不伪造分析状态。

## 当前证据

- 国内共享幂等回归：`python -m pytest tests/test_tasks.py tests/test_tasks_concurrency.py tests/test_single_revision_inputs.py -q -p no:cacheprovider`，40 passed，包含真实PG竞争与历史请求哈希兼容。
- 海外后端专项176 passed；冻结历史迁移后13 passed。涵盖事务回滚、五角色/兼任范围、非法候选、创建/改派幂等与真实PG等锁失权竞争。详见 [后端记录](OVERSEAS-PHASE19-BACKEND.md)。
- 真实三API、两库、Redis：`python hengxin-smart-image/infra/identity-test/run.py --phase19 --serve --origin http://127.0.0.1:3015`，Phase17/18/19全部PASS；4任务、7SKU、7事件、7未发布outbox、7幂等记录，国内所有public表及行内容前后一致。详见 [HTTP集成](OVERSEAS-PHASE19-INTEGRATION.md)。仅外部钉钉provider为替身。

后端全量：Docker Linux Python运行 `python -m pytest -q -p no:cacheprovider`，代码根挂载`/workspace`、工作目录`/workspace/backend`，设置TEST_DATABASE_URL、API_IMAGE_TEST_DATABASE_URL、TEST_OVERSEAS_DATABASE_URL、TEST_OVERSEAS_MEMBERS_DATABASE_URL、TEST_IDENTITY_REDIS_URL指向本次独立PG/Redis。输出 `1870 passed, 17 skipped, 15 warnings in 315.63s`，退出0。17项跳过仍为既有专用宿主条件（Linux Skill、非root WSL、root/只读Worker/Bubblewrap），未计为通过。首次仅挂backend导致3个infra脚本导入失败，改为挂载完整代码根后全量通过，没有改测试规避失败。

后端构建：`docker build -t hengxin-smart-image-backend:phase19 -f infra/Dockerfile.backend .`，退出0。

前端：`pnpm test` 264/264；`pnpm typecheck`退出0；正式Vite构建36.56s、独立预览构建40.64s。真实五角色/兼任浏览器与故障脚本通过，含创建刷新、候选与任务分页、幂等重试、改派409、即时失权、1366/390视口和祖先裁切检查。Phase18成员故障回归通过。原预览完整流程5组、管理5组、框架4组通过，后两组由主线程独立执行，errors=[]，管理预览api=[]。见 [前端验收](../hengxin-smart-image/frontend/PHASE19-TASKS.md)。

正式提交依赖闭包：主线程`git archive HEAD hengxin-smart-image/frontend`导出已提交基线，覆盖本阶段14个正式代码/测试文件，不带工作区的未跟踪模拟预览、package.json/locales既存修改；node_modules仅复用已安装依赖。隔离目录执行`pnpm build`（含vue-tsc），退出0、4587 modules transformed、built in 43.62s。证明正式任务页不依赖未提交的模拟预览闭包。隔离构建未改当前工作树候选。

首轮独立审查发现唯一MEDIUM：无task.create成员的空态误提示提交。已按allowed区分引导并新增浏览器断言，重跑前端264项、typecheck及完整故障浏览器通过。401故障仍通过页面重载验证，避免把移动端菜单浮层当成后端错误路径；没有使用force点击绕过UI。修复后的正式隔离构建再次通过（含vue-tsc、4587 modules、31.72s），完整输出 `output/phase19-clean-build-final.log`。

最终独立复审Stage1/Stage2均PASS，候选`2e405fc0c88515c49e0973d64575ff25de5da34f6d654e2e5f2d04d0b1ffee01`起止一致；报告 [最终审查](reviews/OVERSEAS-PHASE19-REVIEW-FINAL-20261012.md)。首轮独立后端98项、前端专项3项、类型、真实/故障浏览器、邻居4项通过；新fresh reviewer重核合同、修正差异并独立重跑类型、完整故障浏览器、邻居4项和读取最终构建日志。四步验收完成。

本轮3015、独立PG/Redis/三API及网络已停止并清理，原3012与既有hx-management-pg-test保留。清理临时隔离构建目录的命令被自动审批以“blocked by policy”拒绝，未提供更具体原因，因此`output/phase19-clean-0bbbc212689141c5a9750de3497933a2`保留（含只复用本地依赖的node_modules junction）；未绕过拒绝，不影响受控代码与验收。构建日志保留在output。

本次仅本地开发与验收，未部署、未执行生产迁移、未连接真实钉钉或调用收费模型。下一阶段为Phase20资料上传、解析与文件授权。

提交前仅清理故障浏览器测试多余EOF空行，fresh reviewer以字节差异、语法检查和前完整报告复核，Stage1/Stage2均PASS。最终提交快照为`f8ee28817724abffbbb55bbb9d5bbf107b65407a1e6abfe37a5b008be3269117`；凭据报告 [提交快照复核](reviews/OVERSEAS-PHASE19-REVIEW-SNAPSHOT-20261012.md)。未将空白变更自行视为已审。
