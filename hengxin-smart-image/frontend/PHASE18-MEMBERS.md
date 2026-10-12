# Phase18.3 前端实施与验证

1. 身份请求支持 PATCH、查询参数、结构化错误；成员 DTO、分页和五角色合同严格验证。验收：单测覆盖状态码、非法响应与请求体。
2. 续建 OverseasMembers，props 适配真实与预览，保留 ArtTable/表单。真实姓名部门只读、多角色、筛选分页、禁用确认与冲突刷新。验收：正常/空/加载/失败可见且可恢复。
3. 抽取既有海外框架，正式入口复用侧栏和 header；只按服务端 members.manage 显示已交付菜单。验收：直链、撤权、网络错误清授权和敏感内容，统一切换/退出正常。
4. 类型检查、全量单测、正式/预览构建及隔离浏览器故障回归；真实联调由主 Agent 协调，最终审查提交由主 Agent 负责。

复用：ArtSidebarMenu、ArtHeaderBar、ArtTable、海外既有管理样式和 Element Plus；预览专有 adapter 不进入正式成员页。开发端口3015，不停止3012。

## 2026-10-12 验证记录

- `pnpm test`：261/261，包含成员请求合同、PATCH允许字段、角色/版本DTO、capabilities失败关闭；既有身份fixture同步服务端新增字段。
- `pnpm typecheck`：退出码0；正式与海外预览构建通过，生成类型完成整理后再检查。
- `node tests/overseas-members-real.browser.mjs`：真实隔离PG/Redis/身份/国内/海外HTTP，五角色及国内管理员兼海外普通成员共6种身份全部通过。管理员多角色编辑、GET回读与审计、刷新、其他身份403、统一切换与退出验证；外部钉钉provider使用明确替身，无生产访问。
- `node tests/overseas-members-faults.browser.mjs`：只读身份、多角色、分页第2页、状态/角色筛选回第1页、延迟加载、空态、禁用确认、409刷新、断网重连、401/403、撤权收菜单、国内API隔离通过。loading mask、empty提示、error提示逐层检查overflow裁切祖先，所有边界断言通过。
- `node tests/unified-identity-real.browser.mjs`：both/domestic/overseas/neither四组合真实业务会话与统一退出通过；`unified-identity-faults.browser.mjs`：503/403/统一退出故障重试通过。
- 原预览 `overseas-management.browser.mjs` 5组、`overseas-shell.browser.mjs` 4组、`overseas-preview.browser.mjs` 5组通过；全程无浏览器异常，模拟路径无业务API请求。
- 正式卡片computed `borderRadius=16px`，复用Art `data-box-mode`初始化；既有shell脚本比较海外与一期卡片模式和圆角一致。正式内容继承layout-content布局。390×844真实测试确认表格scrollWidth>clientWidth，滚动到操作列并打开编辑，保存按钮全部处于视口内；并非只检查整页横向溢出。
- 截图：根目录 `output/playwright/phase18/members-real.png`、`members-real-mobile.png`。

补测修复：原加载过程把total置0，Element Plus分页器会因总页数收缩自动发出page=1，从而覆盖用户第2页请求。现加载中保留总数、清空旧行；失败仍清空总数/行/编辑态，防止旧授权操作。浏览器明确等待page=2响应，再断言最后请求仍page=2，随后筛选断言page=1。

正式代码依赖仅 `api/overseas/members.ts`、`OverseasShell.vue`、`OverseasPortal.vue`和续建`admin/OverseasMembers.vue`，以及统一身份请求/入口/Portal；不导入预览adapter或session。`members-preview.ts`、`OverseasManagement.vue`传参和`PreviewApp.vue`共享shell改动仅供保留的预览工作区。最终独立审查、候选固定与提交由主Agent执行，本记录不代替审查凭据。
