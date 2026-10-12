# 二期前端修订验收 · 2026-10-12

## 范围
统一钉钉身份授权后选择业务，国内与海外业务授权/数据独立。当前仍是本地模拟预览，未接真实钉钉、AI 或数据库；不部署、不提交。

- 登录去除模拟身份场景表单与底部说明；业务入口只保留国内业务、海外业务，无权限禁用并显示暂无权限。
- 删除 SKU 颜色，覆盖类型、提交/校验、方案/详情、成品检索和示例。
- 海外管理中心复用一期 Art 侧栏、表格、卡片与 hx-admin 布局，五菜单为调用统计、执行监控、用户与角色、Skill 管理、系统配置。
- 默认本地管理员便于评审；运营/设计角色隐藏管理菜单，直接访问被拦截。管理员提交工作区按运营能力使用，设计审核切换设计角色。
- 管理配置是独立内存草案，成员配置不改变当前模拟身份，Skill/系统配置不冒充已接执行器。统计来自当前海外任务，不虚构请求次数/Token/费用。

## 验证证据
- `pnpm test`：250/250 通过，output/overseas-revision-unit.log。
- `pnpm build:overseas` 和 `pnpm run build`：包含 vue-tsc，日志 output/overseas-revision-build.log、overseas-revision-production-build.log。
- `node tests/overseas-preview.browser.mjs`：5组通过；统一登录无测试控件、授权失败、四业务权限、无权直链、无颜色的多SKU流程、返工/审核/归档、隔离、响应式及退出。
- `node tests/overseas-shell.browser.mjs`：4组通过；一期复用导航、文件校验/任务删除、全局搜索、国内入口和实际卡片圆角一致。
- `node tests/overseas-management.browser.mjs`：5组通过；海外任务统计与执行记录、成员CRUD及禁用确认、Skill CRUD及停用确认、配置校验/保存/重置/跨页保留、非管理员菜单及直链、390px与零业务API/页面异常。
- 截图：output/playwright/overseas-20261012/（登录、双入口、无颜色提交、完整流程）；output/playwright/overseas-revision-20261012/（管理五页和窄屏）。
- Playwright 全部独立临时 context，不访问生产数据。

## 预览
http://127.0.0.1:3012/overseas-preview.html 。刷新原页面，点击钉钉登录、海外业务；左侧展开管理中心。顶部可切换体验角色。
