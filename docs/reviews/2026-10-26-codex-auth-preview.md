# Codex 账号独立交互预览审查

- 日期：2026-10-26；审查角色：独立 code-reviewer。
- 最终 candidateId：`d304615b4af3c84beeb24dde34f04dc317f60cd2175e2ce4919e80a3f9990ec4`。
- 初次 candidateId：`2b66eff4ebdaccb5ce665163acb12a5ef65b8f67c9bf81ef3db7858586677d63`。
- 范围：`hengxin-smart-image/frontend/preview-codex-auth/` 全部 11 个新文件；下文短路径均相对此目录。正式 src 仅作为复用与视觉证据读取。用户既存 AGENTS.md 改动不属于本次审查范围。
- 合同：用户只要求基于现有前端一比一制作交互预览；以 PLAN.md:3–10 为本次完整范围，Product-Spec.md / Design-Brief.md 的既有系统作为上下文，不把本轮拟议功能写成正式需求。
- 结论：**Stage 1 PASS；Stage 2 PASS**。当前无未解决 HIGH / MEDIUM 问题。仅批准独立演示的实现，不证明官方托管授权接入、真实登录、后台保存、权限或任务续接已验收。
- 方法：逐文件静态审查；reviewer 实际查看三张既有浏览器截图；独立运行类型、构建、内存模型断言及本地 API 阻断探测。浏览器交互证据由主 Agent 提供，reviewer 没有重复操控浏览器或访问生产。

## 快照变更与已解决问题

审查期间主 Agent 修改了 AccountPage.vue 的首次启用成功文案。旧版本统一显示“继续原会话”，对未配置账号不成立，属于 Stage 1 引导真实性问题。新版本在写入账号前保存 firstConnection，分别给出首次启用、换号、原账号续期文案，见 AccountPage.vue:52–57；主 Agent 对首次配置重新运行了完整浏览器流程，DOM 返回“账号已启用，可用于当前业务的 Codex 调用。”。

收到新 candidateId 后重新检查该差异，独立复跑类型和构建；新候选全部 10 个受控文件内容哈希一致，最终 review-status currentId 为上述新编号。旧编号不作为批准对象。报告本身不改源码，不登记 review-approve，不写 .needs-review。

## Stage 1：Spec Compliance — PASS

| PLAN / 范围条目 | 结果与实现证据 | 验证 |
| --- | --- | --- |
| 仅独立预览，不改正式需求、src、后端、生产 | 完整实现。main.ts:9–14 独立入口和样式；vite.config.ts:12–15 独立 demo 构建目录；PLAN.md:3、10 明确边界 | git status 仅显示该新目录及排除的既存 AGENTS.md；src/Spec/DEV-PLAN 无改动 |
| 复用原框架、菜单、页头、主题 | 完整实现。App.vue:2、26 直接导入 OverseasShell；main.ts:5–7、11–24 复用主题及 prototype.css；原 src/views/overseas/OverseasShell.vue:3–7、17–19 直接使用 ArtSidebarMenu / ArtHeaderBar | 实际查看 baseline-settings.png 与 domestic.png，同视口侧栏、页头、卡片、字体、按钮一致；预览条是明示新增内容 |
| 国内/海外真实导航结构，管理中心追加 Codex 账号 | 完整实现。navigation.ts:9–17 区分国内 API 换套图与海外工作流、各自管理项；App.vue:16–18、31–33 切换业务 | 截图国内导航与基准一致；QA.md:10–12 记录跨业务切换 |
| 同一组件覆盖两业务，数据内存隔离 | 完整实现。App.vue:13 使用 side/revision 作为 key；model.ts:10–15 创建独立账号/审计数组；24–31 仅更新指定 side | reviewer 实际运行 activate/remove/scenario 断言，国内变化后海外序列化数据保持完全一致 |
| 未配置、可用、授权失效、网络异常 | 完整实现。model.ts:3、7–8；AccountPage.vue:6–12；App.vue:9–11、34–35 状态演示切换 | QA.md:9、14–15；网络失败不冒充授权失效，检测连接结果分支见 AccountPage.vue:41–50 |
| 重新授权保留旧配置，检测成功后明确启用 | 完整实现。AuthorizationDialog.vue:15–18、25–30；48–59 仅改弹窗局部状态，AccountPage.vue:52–57 在 activate 事件后才修改配置 | QA.md:9、14 的成功、失败、重试、取消路径；失败/取消不调用 model.activate |
| 换账号需确认，续期账号不一致拒绝启用 | 完整实现。AuthorizationDialog.vue:20–22、27、30、43、51 区分 mismatch 和 replace，并要求 acknowledged | QA.md:11–12 的不一致拒绝、未勾选禁用、勾选启用 |
| 移除二次确认且不影响另一业务 | 完整实现。AccountPage.vue:24–26、59；model.ts:29–31 保留审计并清空当前账号字段 | QA.md:15 与 reviewer 模型断言 |
| 授权码、等待、检测、成功、超时、重新获取 | 完整实现。AuthorizationDialog.vue:4–30、39–59；授权码明确 DEMO-ONLY，180 秒计时与模拟超时均进入 expired | QA.md:9、13–14；过期禁止复制/前往，失败可模拟恢复后重试 |
| 示例账号/授权码显式标记，不打开真实登录、不采集密码/token | 完整实现。App.vue:7–8；AuthorizationDialog.vue:7–9、13、30、47、56；model.ts:9 | 静态核对授权按钮仅切换说明，复制仅写 DEMO-ONLY，无密码/凭据输入控件；API 实查403 |
| 提示对应已实现行为 | 完整实现。首次配置修订后 AccountPage.vue:53–56 三种成功语义一致；AuthorizationDialog.vue:8–9 的“演示”按钮对应说明切换；App.vue:14、36 对非本功能页面与退出提供演示解释 | 已解决首次配置错误续接提示；未发现死引导 |
| 类型、构建、核心流程、窄窗、独立审查 | 完整实现。tsconfig.json:2–4；vite.config.ts:12–15；style.css:11–12、19；本报告 | 两次独立类型/构建均成功，以修订后的输出为准；QA.md:9–18 覆盖核心故障及尺寸，截图确认窄窗内部滚动/页脚可见 |

部分实现：无。未实现：本轮合同内无。正式后台、官方认证、实际任务续接不在本轮合同，不能列成现有功能已通过。

Spec 漂移：未发现超出独立预览的新增业务实现。示例操作记录属于账号管理展示（AccountPage.vue:17–19、model.ts:17–18），其他菜单明确显示“此独立预览仅演示 Codex 账号配置”（App.vue:14），没有接入既有业务服务。

## Stage 2：Code Quality — PASS

| 项目 | 结论与证据 |
| --- | --- |
| 类型、结构、文件大小 | 新代码无 any。AccountPage.vue 61行、App.vue 37行、AuthorizationDialog.vue 61行、main.ts 29行、model.ts 32行、navigation.ts 32行、style.css 19行、index.html 2行、vite.config.ts 16行、tsconfig.json 5行，均小于300行。页面、状态模型、授权弹窗、导航职责分离，见各文件导入/导出。类型检查 exit 0。 |
| 计时器与切换业务边界 | AuthorizationDialog.vue:45、60 清理倒计时和检测 timeout；AccountPage.vue:39、44、60 清理检测 timeout；App.vue:13、34 的 key 确保切换业务/演示状态时卸载旧页面和弹窗。已取消组件不会继续写配置。静态证据覆盖，未声称实测等待完整180秒。 |
| 失败处理 | AuthorizationDialog.vue:47 对复制失败有人工复制提示；17–18、48–59 对网络失败可重试；AccountPage.vue:41–50 区分授权与网络失败。提交仅在显式启用事件发生，未发现取消覆盖账号。 |
| 测试真实性 | QA.md:9–15 覆盖 UI 成功、失败、超时、换号拒绝/确认、取消、移除与两业务隔离；reviewer 模型断言仅作为数据隔离补充，不替代浏览器证据。首次配置错误由实际浏览器验证发现并修订。未将这些模拟测试推论为生产登录/续接验收。 |
| 安全扫描 | 扫描本目录 eval、dangerouslySetInnerHTML、innerHTML、VITE_*KEY/SECRET/TOKEN、密钥前缀、绝对用户路径、any、fetch、axios，仅命中 index.html:2 的 CSP 允许来源，没有硬编码密钥/动态执行/真实请求代码。AuthorizationDialog.vue:47 仅复制公开示例码。 |
| 业务网络隔离 | vite.config.ts:3–12 拒绝 /api/ 并固定使用无代理的 demo 配置；index.html:2 connect-src 限制为同源、3033 HMR与图标服务。main.ts:25–29 删除正式路由并安装预览路由，没有 initRouter 正式守卫；App.vue:4、36 覆盖退出行为。reviewer GET 本地管理 API 得到403。图标服务属于视觉资源，不是业务/认证 API。 |
| 视觉对比 | reviewer 用 view_image 实际看 baseline-settings.png、domestic.png、dialog-390.png。原框架横向起点、侧栏宽度、顶栏、蓝色按钮、白卡及圆角一致；新内容沿用 hx-page/hx-heading/hx-admin-settings-card（AccountPage.vue:2–6、17），原 prototype.css:2–8、41–44、73 提供字号/间距。QA.md:18 测量两者 sidebar231px（含边框）、header104px、page x251、card x259、radius16px。窄窗截图明确可见取消/模拟完成按钮，style.css:11 与19限制 body 滚动和响应式排布。 |

安全问题：范围内未发现。代码质量阻断项：无。截图是本次独立预览与既有基准的比较，不将“同框架”解释为业务正文像素相同。

## 独立验证原始输出

修订后的类型检查命令：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-codex-auth/tsconfig.json
```

stdout/stderr 为空，进程 exit_code=0（reviewer 工具返回）。

模型断言原始输出（运行时使用示例账号，未写文件）：

```text
PASS: activate/remove/scenario preserve overseas account; remove keeps audit history
```

本地阻断实查原始输出：

```text
HTTP/1.1 403 Forbidden
Vary: Origin
Date: Mon, 26 Oct 2026 03:35:50 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 41

Preview does not connect to business APIs
```

修订后的独立构建命令：`node node_modules/vite/bin/vite.js build --config preview-codex-auth/vite.config.ts --mode demo`，exit_code=0。完整 stdout：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for demo...
transforming...
✓ 4479 modules transformed.
rendering chunks...
computing gzip size...
dist-preview/codex-auth/preview-codex-auth/index.html                                          0.59 kB │ gzip:   0.43 kB
dist-preview/codex-auth/assets/login_icon-C4TVlUS8.svg                                         4.23 kB │ gzip:   1.48 kB
dist-preview/codex-auth/assets/403-BdWuHcJA.svg                                                4.61 kB │ gzip:   1.55 kB
dist-preview/codex-auth/assets/yd-BrGqJ6Cs.png                                                 4.63 kB
dist-preview/codex-auth/assets/sd-C0PQtrty.png                                                 4.75 kB
dist-preview/codex-auth/assets/500-DANzffU6.svg                                                4.93 kB │ gzip:   1.76 kB
dist-preview/codex-auth/assets/404-BzxNMzaO.svg                                                5.12 kB │ gzip:   1.94 kB
dist-preview/codex-auth/assets/icon4-DoSzj0bv.webp                                             5.76 kB
dist-preview/codex-auth/assets/icon3-T3qq4dG7.webp                                             5.87 kB
dist-preview/codex-auth/assets/logo-horizontal-white-CobeGVdD.svg                              5.97 kB │ gzip:   2.47 kB
dist-preview/codex-auth/assets/logo-horizontal-BpaRC5RP.svg                                    6.09 kB │ gzip:   2.53 kB
dist-preview/codex-auth/assets/icon6-WLywVSyq.webp                                             6.31 kB
dist-preview/codex-auth/assets/icon2-CpZimU24.webp                                             6.71 kB
dist-preview/codex-auth/assets/img1-D1-edq2V.webp                                              7.52 kB
dist-preview/codex-auth/assets/icon5-BXFopm_n.webp                                             7.93 kB
dist-preview/codex-auth/assets/icon7-Bv7tEJJc.webp                                             8.18 kB
dist-preview/codex-auth/assets/img7-4tHQ8_RR.webp                                              8.69 kB
dist-preview/codex-auth/assets/img9-C5GNNLTv.webp                                              9.21 kB
dist-preview/codex-auth/assets/img5-O9OJMad4.webp                                              9.48 kB
dist-preview/codex-auth/assets/img8-B6h2fA3L.webp                                              9.58 kB
dist-preview/codex-auth/assets/img4-puXkhAjD.webp                                              9.83 kB
dist-preview/codex-auth/assets/icon1-DYDLnOGV.webp                                            10.08 kB
dist-preview/codex-auth/assets/img6-PBedqv72.webp                                             10.90 kB
dist-preview/codex-auth/assets/draw1-Ce1WF34i.png                                             11.32 kB
dist-preview/codex-auth/assets/img3-2dukXPv_.webp                                             12.13 kB
dist-preview/codex-auth/assets/bg-DrCBEYh-.webp                                               12.35 kB
dist-preview/codex-auth/assets/img2-B4YC9Se8.webp                                             14.02 kB
dist-preview/codex-auth/assets/lf_icon2-CrdSAdav.webp                                         25.02 kB
dist-preview/codex-auth/assets/bg_light-WsVMpqKz.webp                                         67.25 kB
dist-preview/codex-auth/assets/bg_dark-BoZNsetB.webp                                          70.59 kB
dist-preview/codex-auth/assets/index-bO8ksejU.css                                              0.19 kB │ gzip:   0.12 kB
dist-preview/codex-auth/assets/index-BPxqj_XC.css                                              0.82 kB │ gzip:   0.42 kB
dist-preview/codex-auth/assets/index-dJSX_KvK.css                                              1.41 kB │ gzip:   0.46 kB
dist-preview/codex-auth/assets/el-drawer-BhCnIJJ3.css                                          3.51 kB │ gzip:   0.88 kB
dist-preview/codex-auth/assets/el-form-item-BWkJzdQ_.css                                       4.75 kB │ gzip:   0.89 kB
dist-preview/codex-auth/assets/index-D7vbzVQY.css                                             10.35 kB │ gzip:   2.09 kB
dist-preview/codex-auth/assets/dingtalk-login-h_dZrNYT.css                                    22.10 kB │ gzip:   3.93 kB
dist-preview/codex-auth/assets/index-iglFForh.css                                            269.90 kB │ gzip:  42.65 kB
dist-preview/codex-auth/assets/index-BQLDY7Rg.js                                               0.85 kB │ gzip:   0.50 kB
dist-preview/codex-auth/assets/index-nWZQsY7K.js                                               0.85 kB │ gzip:   0.50 kB
dist-preview/codex-auth/assets/index-DdMl85aQ.js                                               0.85 kB │ gzip:   0.50 kB
dist-preview/codex-auth/assets/ArtException.vue_vue_type_script_setup_true_lang-CyEXBY0G.js    0.97 kB │ gzip:   0.60 kB
dist-preview/codex-auth/assets/index-BNw1IE3g.js                                               1.44 kB │ gzip:   0.78 kB
dist-preview/codex-auth/assets/el-drawer-Dx__ZZt1.js                                           4.94 kB │ gzip:   2.27 kB
dist-preview/codex-auth/assets/Iframe-DQDxFGo4.js                                              6.11 kB │ gzip:   2.64 kB
dist-preview/codex-auth/assets/index-BJRxYQ_d.js                                               6.21 kB │ gzip:   2.87 kB
dist-preview/codex-auth/assets/index-D-rdnrPZ.js                                               6.75 kB │ gzip:   4.20 kB
dist-preview/codex-auth/assets/index-D-CwAF-j.js                                               8.80 kB │ gzip:   3.80 kB
dist-preview/codex-auth/assets/index-CbQq76GL.js                                               9.37 kB │ gzip:   4.90 kB
dist-preview/codex-auth/assets/dingtalk-login-0dwwlvdy.js                                     16.31 kB │ gzip:   6.38 kB
dist-preview/codex-auth/assets/el-form-item-Rbwo6o6S.js                                       30.44 kB │ gzip:  10.05 kB
dist-preview/codex-auth/assets/index-DPyEbKN9.js                                              31.04 kB │ gzip:  10.45 kB
dist-preview/codex-auth/assets/index-CNrkWaD4.js                                              78.91 kB │ gzip:  31.76 kB
dist-preview/codex-auth/assets/index-KbVapyyn.js                                             725.92 kB │ gzip: 254.65 kB
✓ built in 39.11s
```

最终快照核对：`review-status` 返回 currentId=`d304615b4af3c84beeb24dde34f04dc317f60cd2175e2ce4919e80a3f9990ec4`；尚未批准是正常状态，主 Agent 应使用同一 candidateId 登记本报告的两阶段 PASS。

