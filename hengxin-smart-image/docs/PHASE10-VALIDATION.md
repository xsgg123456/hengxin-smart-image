# Phase 10 验证记录

2026-09-10；技术验证通过，待用户验收。独立两阶段审查见 PHASE10-FINAL-REVIEW.md。

## 实现范围

- `POST /tasks/{id}/rounds` 真实异步受理，带幂等键；task UUID、slot、意见校验，重试需当前失败轮次 sourceRoundId 和原意见/范围。任务行锁、PG幂等锁及未结束轮次唯一约束跨用户生效。
- 详情按实际状态和原执行器可用性开放返工/重试；待核实与所有未结束状态禁用。返工执行保持原任务执行器和session，已知未spawn失败可以重试首次初始化，已有session绝不替换。
- 新轮次带入冻结原素材/Skill与当前图片版本；本轮结果使用连续局部slot，单图目标映射原任务slot。
- 本轮完整清单可逐slot声明生成文件或失败，成功图片仍须原生事件/哈希匹配；未知额外文件、越界、历史覆盖均拒绝。发布成功slot新版本，失败slot保留旧版本；无成功、部分成功、全部成功分别显示失败、部分失败、待查看。
- 前端使用原详情抽屉、图片卡片和意见弹窗，按身份/任务/目标保留草稿与提交快照。组件关闭重开和401重登恢复原请求；未知响应只重放原键，受理回执保留到该轮次结束。浏览器完全重载的跨进程草稿持久化不在本期承诺中。

## 自动测试

- Windows：`pytest backend/tests --basetemp=output/phase10-full-local -p no:cacheprovider -q`，268 passed、18 skipped。跳过均依赖Linux或PostgreSQL，由Linux全套补齐。
- Linux隔离验证：`python infra/verify_phase8.py --build --browser --phase10`，修复状态聚合后的后端287 passed、0 skipped；包含独立PG连接、真实HTTP两用户返工/重试竞争与同键重放。原始日志 `output/phase10-final-integration.log`。
- 前端：`tsx --test tests/*.test.ts` 56 passed；`vue-tsc --noEmit` 零错误；`vite build` 通过，3303模块、37.56秒。原始日志分别为 `output/phase10-frontend-tests.log`、`output/phase10-typecheck.log`、`output/phase10-frontend-build.log`。
- 新专项覆盖：部分失败保留旧slot及历史、未知图片不伪成功、真实provenance解析接入恢复并仅一次发布、currentPath新工作目录与精确resume参数、已知未spawn失败的人工重试、配置变更不切换任务执行器。
- 依赖弃用与测试未登录空主键警告不代表失败；未引入外部依赖或数据库新结构，既有迁移重复执行仍验证。

## 审查修复

第一次独立审查记录Stage1 HIGH：只看本轮成功会误把仍缺图片或其他slot仍失败的任务显示整套待查看。现按整套slot聚合任务状态，并同步列表部分失败/error/待查看筛选和ready统计；单轮仍记录实际成功。新增回归按“初次部分失败→只修改已成功图→仍部分失败→修好缺图→整套待查看”逐步验证，相关6项专项通过；新reviewer独立相关40项通过，完整两阶段结论以PHASE10-FINAL-REVIEW.md为准。

验收脚本的三处问题已修：409错误体使用统一code/message；Outbox物理列为id；历史版本选择点击可见ElSelect外壳。它们不作为业务失败计数，也不使用未跑完的旧集成日志宣称最终通过。

## 最终浏览器与集成结果

最终 `verify_phase8.py --build --browser --phase10` 退出码0：PHASE10 API PASS、PHASE10 BROWSER PASS、PHASE8 INTEGRATION PASS，pageerrors=0，独立Compose卷已清理。

- 单张异步返工、并发同键重放、异键争用、排队/执行拒绝新轮次；非目标slot版本、对象键与hash不变，历史文件仍可读取。
- 浏览器实际填写单张和整套意见；409后关闭重开草稿仍在；服务端真实202后故意丢响应，确认重放保持原key/body/roundId，未建额外轮次。
- 离开页面后后台完成；历史图片选择实际加载旧文件，执行与反馈记录完整。截图 `output/playwright/phase10-revisions.png`，受控fixture图片为纯色测试图，非业务效果图。
- 首次生成、401身份恢复、下载/ZIP、删除与Worker硬退出待核实保护的旧流程回归通过。

## 交付边界

平台返工使用隔离fixture验证API/PG/队列/MinIO/浏览器行为，明确标记测试来源且不伪造session。执行适配层用受控CLI事件验证续接参数、当前材料、来源及失败保留；真实CLI返工图片效果按原DEV-PLAN放在Phase14，不将本期fixture宣称为真实AI效果。未部署生产、未提交或推送代码。
