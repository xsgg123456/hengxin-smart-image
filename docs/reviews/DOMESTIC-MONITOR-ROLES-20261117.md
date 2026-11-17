# 国内角色收敛与工作台会话只读审查

审查日期：2026-11-17。执行者：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。仅审查、运行隔离验证及编写本报告，未修复产品代码。

## 快照及范围

- 最终 candidateId：`6a29407d3296cd9ae0c13aff39af9f7ebf71d70c70fd97e57d5d9690916b72f4`。补审后运行 `harness.py review-status`，currentId 与此一致。
- 初轮曾确认 `5e8e3e1d3013421fdee91a3857f26451cad5a8a00b8113f149911f9bc083c0b4`；随后检测到外部并行的 `AGENTS.md` 和 `.agents/skills/jd-screen-protector-image-suite/*`，当时拒绝以旧报告覆盖新快照。主 Agent 明确要求保留并补做静态完整性/安全审查，现已完成，见补审章节。**外部文件不属于本次国内产品开发交付、提交或发布范围**；不得借全仓快照凭据扩大生产范围。没有搬移、回退或编辑外部文件。
- 初始 candidateId：`d0ed4743bf338921093dfb1cb6a8e300797b378b0a5238790019fa0d2646ba70`。审查中主 Agent 恢复 Vite 自动生成的 `components.d.ts` 至 HEAD，并修正三个国内管理接口的 403 文案、更新预览 README。已重新读取最终差异：三处文案与超管授权一致，生成声明已无差异；本报告只批准最终候选，不以旧候选结论覆盖未知变化。
- 范围：本轮国内业务 Git 差异及未跟踪的正式实现、测试、`frontend/preview-workspace-monitor/`、`scripts/maintenance/retire_domestic_design_manager.py`；源需求为 Product-Spec.md 顶部 2026-11-17 两节、DEV-PLAN.md 同日联合计划、Design-Brief.md 同日条目。另按派发对外部规则/京东技能做限定静态补审。预存无关文件 `=12.1,` 排除，禁止纳入本轮提交。
- 最终业务补审差异：`F/src/views/hengxin/admin/workspace-sessions/ManagedAsset.vue:25` 将任意 image/* 改为 JPEG/PNG/WebP 预览白名单；`F/tests/workspace-sessions.browser.mjs:100` 增加 SVG 仅下载、不发缩略图请求验证。已从 Stage 1 复核此格式行为及 Stage 2 测试有效性，并独立重跑浏览器通过。其余业务实现沿用已审版本。
- 下文路径简写：`B/`＝`hengxin-smart-image/backend/`，`F/`＝`hengxin-smart-image/frontend/`，`S/`＝`scripts/maintenance/`。每个代码证据均为相对仓库路径及行号。
- 审查结论：**Stage 1 PASS；Stage 2 PASS**。未发现本轮实现的 HIGH 或 MEDIUM 阻塞问题。此结论不等于全部回归、生产角色调整或部署验收完成。

## Stage 1：Spec Compliance — PASS

### 完整实现

| 需求 | 结论与证据 |
| --- | --- |
| 国内仅三种可分配角色，授权/审批拒绝旧主管 | 完整实现。`B/app/modules/auth/domestic_roles.py:2` 三角色白名单；`auth/management_router.py:91`、`auth/membership.py:32` 服务端拒绝；`F/src/views/hengxin/admin/users.vue:7`、`:48` 两入口共用三角色。独立执行 `test_domestic_role_permissions.py:12`、`:33`，国内拒绝、海外主管审批保留。 |
| 旧主管失去管理特权，个人身份兼容 | 完整实现。`B/app/modules/management/activity.py:31`、`api_monitor.py:88`、`api_usage.py:75`、`retention_router.py:17` 收敛；`B/app/modules/auth/dependencies.py:37`、`membership.py:24` 保留历史个人身份；`F/src/router/modules/index.ts:4`、`business-route-access.ts:19` 回收管理菜单。真实 Cookie 测试 `B/tests/test_domestic_role_permissions.py:43` 验证降权后 auth/me 仍成功、管理请求 403、再次升权恢复访问。 |
| 全员身份快照、目标唯一核验，周熹普通化与温晓芳例外超管的操作能力 | 完整实现维护工具，实际生产执行待后续验收。`S/retire_domestic_design_manager.py:22` 导出全部成员/身份/授权；`:42` 核对目标集合、UUID、姓名唯一、单一钉钉身份、原角色、成员状态及操作者；`:53` 最多一个明确超管例外；`:105` 比对当前完整快照。工具按审核后的 ID 清单执行，不按姓名批量盲改。具体两位生产成员映射必须由主 Agent 对生产 manifest/回执核验，隔离测试不能证明生产结果。 |
| 用户角色/授权表同步，审计、dry-run、可重入、原子失败 | 完整实现。`S/retire_domestic_design_manager.py:78` 既有权限锁与全员行锁；`:93` 审计摘要与完成态一致性；`:116` 默认 dry-run；`:118` 双表更新；`:130` 原子审计；`:166` 事务；`:177` 提交后才打印成功。独立运行 `B/tests/test_domestic_role_retirement.py:78`、`:110`、`:135`、`:154`、`:170`、`:181`，覆盖其他成员/身份/25个登录会话保留、漂移拒绝、审计写失败全回滚与真实 PG CLI 导出/重复执行。 |
| 当前角色实时授权、已有任务及个人会话不迁移 | 完整实现。`B/app/modules/auth/dependencies.py:24` 每请求查用户；`B/app/modules/domestic_studio/admin_router.py:17` 所有入口依赖 manage_system。维护脚本只改 UserRecord、RoleAssignmentRecord 和 MemberAudit（`:118`、`:130`），未改任务/会话归属。撤权后四类接口直接 403，见 `B/tests/test_domestic_studio_admin_pg.py:151`。 |
| 无 schema、公共依赖、共享后端及海外角色变更 | 完整实现边界。新增管理路由仅在国内 `B/app/main.py:32`、`:66` 注册；旧角色保留在历史类型/约束中；本轮 Git 差异不含迁移、海外实现或共享服务代码。`F/package.json:3` 只更新版本号，无依赖变更。海外主管审批的参数化用例独立通过，`B/tests/test_domestic_role_permissions.py:33`。 |
| 管理中心指定位置、仅国内超管、五个工作台、不扩展 API 换套图 | 完整实现。`F/src/router/modules/index.ts:24` 在调用与执行后插入；`B/app/modules/domestic_studio/admin_router.py:19` 限五枚举；`admin_queries.py:16` 限国内工作台模型且排除删除中会话。PG 用例 `B/tests/test_domestic_studio_admin_pg.py:71` 覆盖五类及非法工作台422。 |
| 成员/工作台/名称/状态筛选、最近活动排序、同口径汇总、分页/重置/空态 | 完整实现。`B/app/modules/domestic_studio/admin_queries.py:28` 聚合真实轮次/Job状态/活动时间；`:57` 共同 filters 用于计数和分页；`:72` 最近活动降序。`F/src/views/hengxin/admin/workspace-sessions/index.vue:15` 列表控件、`:25` 分页；`use-monitor.ts:62` 筛选回首页及重置。PG 与独立浏览器均验证分页和组合筛选，名称中的 % 不当通配符。 |
| 完整已提交对话、实际 Skill、真实姓名/北京时间、公开回复/过程 | 完整实现。`B/app/modules/domestic_studio/admin_details.py:71` 全轮次排序读取冻结 Skill、用户与回复时间；`:109` 按本会话读取过程分页。`F/src/views/hengxin/admin/workspace-sessions/SessionMessages.vue:5` 每轮消息及真实 Skill，`:15` 复用 StudioProcess，`:27` 北京时间格式器。PG 两轮/501条过程分页测试 `B/tests/test_domestic_studio_admin_pg.py:94`、`:118` 通过；真实 API 页面确实显示 fixture 数据和公开过程，非演示数据。 |
| 附件/引用图/保存图片及文件、面板、预览/下载、同成员切换、返回保留筛选 | 完整实现。`admin_details.py:23` 会话绑定 URL、`:87` 资料；`F/src/views/hengxin/admin/workspace-sessions/SessionDetail.vue:5` 同成员会话栏、`:15` 资料面板；`ManagedAsset.vue:26` 原文件请求、`:33` 预览、`:38` 下载；`use-monitor.ts:57` 切换不重置筛选。独立浏览器完成面板、图片、文件下载和返回筛选验证，真实 API 页面另外实际打开确认资料渲染。 |
| 自动同步、暂停、刷新、最后成功时间、断线保留、迟到响应隔离 | 完整实现。`F/src/views/hengxin/admin/workspace-sessions/use-monitor.ts:22` 按 epoch 提交结果，`:29` 过程增量读全、`:49` 失败保留、`:57` 切换先清理、`:66` 自动轮询与可见状态；`index.vue:55` 恢复同步立即刷新。独立单测/浏览器覆盖迟到详情及列表、过程分页替换、503保留和恢复。无草稿/鼠标/屏幕读取入口。 |
| 管理查看严格只读，管理员自己的工作台操作保持 | 完整实现。`B/app/modules/domestic_studio/admin_router.py:30`、`:43`、`:52`、`:62` 只有 GET/HEAD；`admin_details.py:88` canRecover=false，未调用发送/停止/执行器。`SessionDetail.vue:12` 明确只读，`SessionMessages.vue:15` 复用显示组件，没有发送/重试等动作。独立浏览器断言无输入框/写按钮、28个业务请求全为GET；`B/tests/test_domestic_studio_admin_pg.py:118` 比较业务表快照完全相同。原 owner 路由未修改。 |
| 服务端跨用户例外、普通/旧主管拒绝，跨会话文件与源删除拒绝 | 完整实现。`admin_router.py:17` 实时超管；`admin_details.py:34` 文件归属会话核验，`:38` ready状态，`:42` 结果必须经本会话Turn；`admin_queries.py:16` 删除排除。`B/tests/test_domestic_studio_admin_pg.py:151`、`:170` 实测普通/旧主管/撤权403、跨会话/随机会话404、源删除全入口404，超管仍不能绕过原owner私有API。 |
| 未发送附件不可读、缺失原件明确提示 | 完整实现。`admin_details.py:17` 仅已提交 Turn.snapshot 的附件ID，`:36` 防直接猜ID；`:53` 缺失引用返回明确不可用项；`ManagedAsset.vue:25` 显示真实文件错误。PG `B/tests/test_domestic_studio_admin_pg.py:224` 实测提交前 GET/HEAD404且详情不暴露、提交后可读；`:170` 原件缺失503提示、删除后404。 |
| 不复制会话、不续聊、不改变上下文/任务，审计不重复正文 | 完整实现。`admin_router.py:23` 复用 MemberAudit，仅存操作者/对象ID及有限筛选/操作元数据；`:47`、`:57` 会话事件只有conversationId；`:70` 文件事件只有ID/种类/操作。无聊天正文、搜索文本、文件字节写入。`B/tests/test_domestic_studio_admin_pg.py:118` 业务表全量快照不变且审计字段精确断言。 |
| 已确认视觉、去演示控件、桌面/窄屏、错误/无权限反馈 | 完整实现。`F/src/views/hengxin/admin/workspace-sessions/index.vue:3`、`:5`、`:7` 正式真实页面；`style.css:1` 至`:10` 沿用预览变量与响应布局；`use-monitor.ts:16` 401/403清空敏感内容、关闭同步，`:49` 删除清空。已打开预览、正式列表/详情及邻居页面，并目视查看截图；正式代码无示例身份/占位素材/演示按钮。390px稳定截图和独立浏览器几何验证通过。 |

### 部分实现、未实现、Spec 漂移

本次代码交付范围没有发现部分实现或未实现项，也未发现新增无需求页面、写接口、业务表或运行依赖。独立预览明确为演示，入口由 `F/preview-workspace-monitor/vite.config.ts:3` 隔离，`main.ts:48` 占位页面有明确说明，不混入正式路由。

生产周熹/温晓芳实际角色调整、生产既有成员/任务保持、国内发布排空和两版清理属于 DEV-PLAN.md 第4步的后续执行验收，不在本报告中冒充已完成。

## Stage 2：Code Quality — PASS

| 维度 | 结论与证据 |
| --- | --- |
| 结构与类型 | 新增正式模块职责分离：`B/app/modules/domestic_studio/admin_router.py:1` 76行、`admin_queries.py:1` 83行、`admin_details.py:1` 115行；维护工具184行；`F/src/views/hengxin/admin/workspace-sessions/use-monitor.ts:1` 73行、`ManagedAsset.vue:1` 55行。新增TS无显式any；`F/src/api/hengxin/workspace-sessions.ts:23` 至`:39` 验证响应/同成员/同会话URL。类型编译通过。 |
| 错误与生命周期 | `use-monitor.ts:16` 撤权清空、`:49` 404清空、`:57` 隔离旧请求、`:71` 解除订阅/定时器；`ManagedAsset.vue:55` 取消请求及释放blob；`:28` 下载前再次服务端核验。故障路径有真实组件浏览器与单元测试支撑。 |
| 测试真实性 | PG测试真实 FastAPI 请求和独立schema，权限撤销由另一个已提交事务模拟；`B/tests/test_domestic_studio_admin_pg.py:151`。迁移CLI测试真实子进程/PG提交，而非仅mock函数；`B/tests/test_domestic_role_retirement.py:181`。浏览器fixture仅用于UI/交互，不把模拟HTTP当生产权限证据；另已打开真实HTTP+PG详情核验。 |
| 安全扫描 | 扫描新增实现无硬编码密钥、eval、innerHTML、拼接SQL执行或公开运行token。`admin_queries.py:67` ORM参数化搜索且autoescape；`admin_details.py:86` 公开回复/通用错误，不返回snapshot/process_identity/source_path；`admin_router.py:40`、`:49`、`:59`、`:75` no-store；`F/src/api/hengxin/workspace-sessions.ts:52` 限管理文件URL、禁止重定向。安全边界用PG拒绝测试支持。此结论不代表既有第三方依赖无漏洞。 |
| 视觉 | 实际打开新旧页面而非只数组件。预览与正式版的26px标题、13px说明、190/250px筛选、245px会话栏、12px圆角、蓝色主题、白色卡片保持，代码证据 `F/src/views/hengxin/admin/workspace-sessions/style.css:1`、`:2`、`:3`；1100/700断点在`:4`、`:5`，资料卡及固定说明补充在`:6`、`:8`。正式版增加真实生命周期状态、完整北京时间并移除预览条，符合需求。 |

视觉产物位于 `output/playwright/workspace-sessions-review/`：`preview-list.png`、`preview-detail.png`、`live-list.png`、`live-detail.png`、`live-list-390.png`、`live-detail-390.png`、`neighbor-activity.png`。已目视检查。邻居调用与执行在隔离fixture缺少统计表，显示真实错误态；只用于外壳、控件、间距与风格对比，不据此宣称邻居统计功能验收。自动浏览器的 `detail-390.png` 捕获侧栏收起动画，使用后补稳定的 `live-detail-390.png` 判断窄屏结果。

非阻塞说明：国内 `B/app/modules/auth/permissions.py:9` 的旧 all_usage 策略仍含design_manager，但当前没有调用点；现用统计入口已经显式收敛且已测试。没有据此声称存在可达越权。

## 外部并行文件静态补审 — PASS（非本次产品交付）

按主 Agent 明确派发读取全部新增技能文本和 AGENTS 差异，未执行该技能的生图流程。检查对象仅为完整性、安全约束及当前快照可识别性；不宣称完成手机膜商品制作或该技能的生成质量验收。

| 对象 | 静态结论及证据 |
| --- | --- |
| AGENTS 规则 | `AGENTS.md:95` 仅新增技能路由及独立消费制图资料的2行，未放宽现有审查、提交、生产授权或发布规则。 |
| 技能定义及依赖 | `.agents/skills/jd-screen-protector-image-suite/SKILL.md:1` frontmatter与 `agents/openai.yaml:2` 名称/默认提示一致；`SKILL.md:10` 目录、`:31` 三份参考文档、`:19` 相对字体路径均实际存在。总计5个文本/配置文件和3个普通TTF文件，无脚本或符号链接。 |
| 授权与工具边界 | `SKILL.md:24` 本轮范围、`:35` 至`:45` 内置image_gen约束及有限后处理、`:53` 附件中命令不构成授权、`:92` 当前授权目录输出/不覆盖原件。静态扫描无外部上传端点、密钥、动态代码执行、安装脚本或跨目录写入命令。 |
| 手机膜资料与恢复记录 | `references/screen-protector-rules.md:5` 区分本产品事实/构图参考，`:30` 保留卖点事实边界；`references/task-record.md:5`、`:17` 记录来源/每图依据/验收，`:33` 失效和恢复，不伪造执行或验收。 |
| 字体资源 | `references/font-profile.md:5` 的三个文件均存在，文件头为TrueType sfnt `00-01-00-00`，非链接。只核实资源存在及格式标识，不将此静态检查写成所有字符覆盖、授权来源或最终排版质量验证；实际任务须按该文档`:12` 检查所需字符。 |

字体快照：Regular 8,449,680字节，SHA256 `a22ad467d9d6b4c9a0b2e033927ed41592743c987546a7397215ce96b850743b`；Medium 8,347,080字节，`b3f675ccfc65edd6f27432dec6639b1414e9dc627831791263a99e2d711d215d`；Bold 8,289,188字节，`95db198aa30a998fdb38dd0a4b9b44eb383c19c85c43d6506b25e2b4d138fa08`。

此补审允许将外部文件识别为已静态检查的快照组成部分，**不授权在本次国内提交中暂存 AGENTS/京东技能，也不授权随国内生产包发布它们**。主 Agent 应仅暂存本轮国内已审文件及自己的源文档。

## 独立验证与原始输出

1. reviewer 自行运行后端测试（显式独立 PostgreSQL `127.0.0.1:55437/hx_monitor_test`）：

```text
.venv/Scripts/python.exe -m pytest tests/test_domestic_studio_admin_pg.py tests/test_domestic_role_permissions.py tests/test_domestic_role_retirement.py -q
....................................s.                                   [100%]
37 passed, 1 skipped, 2 warnings in 16.12s
```

跳过项是SQLite环境不支持生产PG CLI，用例在PG参数中实际执行。两条warning为现有Starlette/httpx及anyio弃用提示，不隐藏为无警告。

2. reviewer 自行运行前端监看状态与客户端测试：

```text
pnpm exec tsx --test tests/workspace-sessions.test.ts
✔ 管理接口仅GET、查询参数编码且拒绝个人/跨会话/海外文件地址
✔ 切换与筛选拒绝迟到响应、返回保留筛选
✔ 增量分页全量读完、过程项替换、断线保留快照、403清空所有敏感状态
✔ 源会话删除清空详情且不可留下已删除消息
✔ 下载真实受限地址，403传播给撤权处理且不接受重定向
✔ 自动同步暂停时身份变化仍立即清敏感数据
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 567.1706
```

3. reviewer 自行类型编译，exit_code=0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.73 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

Python新增模块及维护脚本执行 `python -m compileall -q`，编译命令无诊断，退出0。`git diff --check` 退出0，仅现有CRLF规范化提示。此处不把类型检查写成Vite生产构建验收。

4. reviewer 自行运行正式应用浏览器脚本，输出目录单独设置为 `output/playwright/workspace-sessions-review`：

```json
{
  "result": "PASS",
  "checks": [
    "真实请求分页、名称筛选、返回保留筛选、重置",
    "完整已提交消息/实际技能/公开过程、真实图片预览与文件下载、纯只读附件面板",
    "手动增量同步、断线保留最近成功内容、恢复同步",
    "同成员会话切换、迟到响应不串会话、空会话",
    "源会话删除及管理员撤权清除全部敏感内容"
  ],
  "requests": 28
}
```

`report.json` 保留1920/1000/390几何结果、全部请求、errors=[]及unexpected=[]。另用独立CLI浏览器 `wm-review` 将本地3037的API转至18037隔离后端，打开真实页面/文件卡片；完成后已关闭该会话，未操作主 Agent 的 `wm-live`。

5. 最后文案改动后，读取主 Agent 的 `output/monitor-affected-tests.log` 原始尾部：

```text
.......................................s................................ [ 78%]
....................                                                     [100%]
91 passed, 1 skipped, 2 warnings in 22.48s
```

6. 最终图片格式补审：`ManagedAsset.vue:25` 白名单与既有 `B/app/overseas/image_delivery.py:10` 一致。SVG/GIF等附件仍作为文件下载，避免提供实际后端不支持的预览按钮。reviewer 独立重跑最新浏览器脚本，原始结果 `result: PASS`、`requests: 29`，详细证据为 `output/playwright/workspace-sessions-review-final/report.json`。`F/tests/workspace-sessions.browser.mjs:100` 验证 SVG 无预览按钮、下载成功、无 thumbnail 请求；原PNG预览和其余交互继续通过。

最终前端全套与类型检查由主 Agent 执行，reviewer 读取 `output/monitor-frontend-final.log`、`output/monitor-typecheck-final.log`，原始尾部：

```text
ℹ tests 576
ℹ suites 0
ℹ pass 576
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 17334.3252

> hengxin-smart-image-frontend@0.2.73 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

7. 完整Linux回归已结束，保留真实原始结果而不改写为一次全绿。reviewer 读取 `output/monitor-backend-final-linux.log`：

```text
FAILED tests/test_domestic_real_sandbox_linux.py::test_real_sandbox_executes_stub_and_delivers_its_image
1 failed, 3411 passed, 255 skipped, 6 warnings in 639.19s (0:10:39)
```

唯一失败发生在隔离测试容器缺少stub shebang依赖的 `/usr/bin/python3`。主 Agent 为一次性测试容器补齐解释器后，原用例单独复测，无产品代码更改；reviewer 读取 `output/monitor-sandbox-isolated.log`：

```text
.                                                                        [100%]
1 passed, 2 warnings in 4.21s
```

因此记录为“全套原始1个环境失败，修正隔离环境后该用例补验通过”；255个跳过项仍为未执行，不能据此宣称其能力已验证。

## 验收边界

完整Linux回归和环境补验结果按上节原样记录，不能将跳过项称已验证。生产角色apply、版本构建/部署、源账号与任务保持、实际入口及两版资源清理均需主 Agent 后续实查并单独记录。生产包按项目规则在已审提交后构建，本报告不声称已经产出Vite生产包；构建若暴露实现缺陷，必须修复、重新固定candidate并复核。当前两阶段PASS不覆盖后续代码变更，也不扩大国内发布范围。

由主 Agent 使用本报告路径及同一最终candidate执行 `review-approve`；reviewer 未执行approve，未写 `.needs-review` clean。
