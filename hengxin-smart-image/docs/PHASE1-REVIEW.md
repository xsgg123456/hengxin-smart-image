# Phase 1 最终独立审查

2026-09-09。**Stage 1 PASS；Stage 2 PASS（仅本地 Phase 1 新增及承接改动）**。未发现本范围内阻断缺陷。依赖风险未消除，本结论不代表可以发布或全产品验收完成。

按 `.agents/skills/code-review/SKILL.md` 从 Stage 1 重审。依据 DEV-PLAN.md Phase 1、Product-Spec.md:297、319、431、435，以及 Design-Brief.md:5、13、15。Phase 2–14 不计为本轮缺失项。以下 src/package 路径相对 `hengxin-smart-image/frontend/`，scripts/output 路径相对仓库根。

## Stage 1：Spec Compliance

| 要求 | 结论与证据 |
|---|---|
| 独立工程承接及固定工具版本 | 完整实现。`package.json:5` 固定 Node 24.18.1、pnpm 10.33.4；本轮读取 node_modules 属性为普通 Directory，无 LinkType。正式与原型 pnpm-lock.yaml SHA256 均为 `7051B856E8CC6406DE785BE301719B13A447C75F3F64F73CE5502068C3EA5667`。独立安装原始摘要见 `docs/PHASE1-VALIDATION.md:11`。 |
| 保留 Art 布局、组件、主题和导航 | 完整实现。`src/views/index/index.vue:3` 保留 ArtSidebarMenu、ArtHeaderBar、ArtPageContent；`src/router/modules/index.ts:7` 保留图片处理及三个子页面、任务/模板/成品。逐文件哈希比较原型 src，未出现 MISSING；路由及 prototype.css 无改动。 |
| 用户、文件、模板、Skill 类型 | 完整实现。`src/types/hengxin.ts:5` User、`:11` FileRecord、`:23` SkillVersion、`:31` Template，核对 API-CONTRACT 数据说明。 |
| 任务、轮次、图片版本、归档类型 | 完整实现。`src/types/hengxin.ts:41` Task、`:61` Round、`:73` ImageVersion、`:82` Archive，包含用户归属、会话/轮次与版本字段。真实存储留待后续，不把展示投影当持久化。 |
| 管理、分页、错误、受理及状态契约 | 完整实现。`src/types/hengxin.ts:92` ExecutionAttempt、`:101` WorkerStatus、`:109` SystemConfig、`:116` 起分页/错误/Accepted；usage、progress 可空，idle 与 unknown 分离。 |
| 集中模拟和共享服务边界 | 完整实现。`src/api/hengxin/client.ts:8` 单一适配入口；`mock.ts:6` 独立内存与计时器；`fixtures.ts:6` 集中种子；`src/views/hengxin/model.ts:17` 读取快照、`:45` 统一写后更新。业务范围 localStorage 搜索仅命中说明注释。`tests/service.test.ts:9`、`:18`、`:35` 证明隔离、受理、串行返工与归档快照。 |
| 模拟标识与真实模式隔离 | 完整实现。`client.ts:5` 仅显式 mock 动态导入；`http.ts:18` 网络失败抛错；`src/main.ts:37` 身份/工作区成功后启用布局；`src/api/auth.ts:7` 禁用/待授权身份阻断；`src/App.vue:18` 重新连接。`src/components/core/layouts/art-header-bar/index.vue:159` 模式标签，`src/views/index/index.vue:13` 工作区状态条。服务故障测试及 api-flow/response-flow 覆盖断连、畸形响应、身份与恢复。 |
| 引导文案真实性 | 完整实现。`src/views/hengxin/components/CreateTask.vue:17` 仅 mock 显示示例按钮，`:62` 真实缺素材提示为“请先上传素材”；`Templates.vue:30` 模式化保存提示、`:35` 中性删除；`Archive.vue:4` 快照提示、`:16` 中性删除。`scripts/phase1/accepted-flow.js:23` 检查真实缺素材提示，response-flow 检查真实空态无样例入口。 |
| 无后端运行、类型检查与构建 | 完整实现。`package.json:10` mock dev、`:11` 默认真实生产构建、`:21` 独立模拟预览构建。审查者本轮独立标签只读打开 3008 与 3007，均实际显示替换壁纸及完整导航；未操作 hx-phase1 会话。最终类型及构建日志见下文。 |

本轮部分实现：无。本轮未实现：无。Spec 漂移：未发现新增业务页面、后端或数据库；GET /workspace 已明确为 `docs/API-CONTRACT.md:29` 的过渡聚合接口，后续分页/文件引用/Skill 查询等不属于本轮交付。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 类型、结构及错误处理 | 通过。新增 API 文件 3–103 行；`src/api/hengxin/http.ts:9` 外部响应经 unknown/guard，`:35` 拒绝非法 JSON/结构；`validate.ts:13` 起校验身份、模板、任务、归档和受理 ID。新增 API/业务范围无 any 命中。原有 Art 大文件保留，不作为新增文件质量结论。 |
| 写成功后读失败 | 通过。`src/views/hengxin/model.ts:45` 保留写结果，读失败单独提示；`CreateTask.vue:66` 使用受理 taskId 导航。`scripts/phase1/accepted-flow.js:10` 真实 HTTP 拦截返回 202 后 workspace 返回 503，`:30` 检查 POST 仅一次，`:32` 恢复读取，`:36` 任务页轮询，`:39` 离页停止。测试前提可达，没有用写失败冒充成功。 |
| 测试真实性 | 通过。`tests/service.test.ts:9` 改返回快照后重读；`:18` 在生成完成前检查排队与禁止归档；`:35` 检查第 2 张版本与旧归档；`:52`、`:58`、`:67`、`:82` 覆盖断网、HTML、坏 JSON、401、202/204、畸形合法 JSON。缩短模拟计时器不改变状态逻辑。浏览器脚本断言实际结果而非只断言按钮存在；最后 response-flow 的强制重载保证连续执行时重建 bootstrap。 |
| 新增代码安全扫描 | 通过。对 `src/api/hengxin/`、`src/types/hengxin.ts`、`src/views/hengxin/` 搜索 eval、innerHTML、dangerouslySetInnerHTML、密钥前缀及暴露的 KEY/SECRET/TOKEN 变量无命中。`http.ts:43` 起路径 ID 编码，`:13` JSON 请求体；未新增 SQL/任意执行接口。 |
| 视觉对比 | 通过。审查者实际打开 3008 正式与邻居基准 3007，并查看 `output/playwright/frontend-wallpaper.png`、`prototype-wallpaper.png`、`api-disconnected.png`。1440px 两图主体 x=259、摘要 x=1112、摘要宽 300px；卡片、按钮、间距与字体层级匹配。新增模拟提示条使内容下移约 40px，符合标识要求；第二模板示例图片顺序变化属于种子数据差异。`src/views/hengxin/prototype.css:7` 右列 300px/gap 22px、`:8` padding 23px/纵向 gap 20px、`:22` 摘要 padding 22px/图片高 220px，与原型文件哈希一致。 |

### 继承安全风险：发布前整改

`output/playwright/phase1-audit.json:3002` 原始 metadata：low=1、moderate=34、high=40、critical=1，共 76 条依赖告警。锁文件哈希相同证实继承同一依赖集合，不证明不可利用。本轮未逐项验证可达性，未批准上线。`docs/PHASE1-VALIDATION.md` 已列逐项核查、升级和回归为发布前整改；此项不作为新增业务代码缺陷，也不能从 PASS 推导安全发布结论。

## 编译与测试原始输出

以下读取最终代码后的 `frontend/phase1-build.log`、`frontend/phase1-test.log` 原文，完整记录保留在文件。服务及浏览器回归由主线程执行，本审查者读取日志并检查代码/测试前提，没有宣称自己重跑全部脚本。

```text
> hengxin-smart-image-frontend@0.0.0 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3252 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 28.65s
```

构建链 `&&` 后 Vite 成功运行，证明前置 vue-tsc 返回 0；构建退出码 0 另记于 VALIDATION。

```text
✔ 模拟服务隔离快照与实例，空工作区无种子污染 (17.2423ms)
✔ 提交异步受理保留输入，不匹配模板拒绝；不同任务有独立受理标识 (51.1438ms)
✔ 返工串行、单图版本隔离、归档快照和重复归档幂等 (118.1413ms)
✔ HTTP 真实模式网络断连直接报错，不返回模拟数据 (0.6261ms)
✔ HTTP 拒绝 HTML fallback、无效 JSON、未授权响应 (16.1782ms)
✔ HTTP 写操作正确传输 Cookie、请求体和 202 受理；204 不解析 JSON (0.4557ms)
✔ 合法 JSON 的错误结构被拒绝，不能误受理或导致页面崩溃 (3.0965ms)
ℹ tests 7
ℹ suites 0
ℹ pass 7
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 454.5887
```

日志还含 npm 对 pnpm 专用配置 package-manager-strict-version、manage-package-manager-versions 的 warning，未阻断测试与构建。
