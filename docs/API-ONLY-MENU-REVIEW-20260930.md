# 普通角色 API 菜单增量独立审查

审查：code-reviewer，按 `.agents/skills/code-review/SKILL.md` 执行；只审查，不修复、不提交、不部署。

最终 candidateId：`9821cfc1a0b28c31b2a82250bc844351518b34ecbfaa8ba9606b6effac3e8aca`。

范围：Product-Spec.md:1、DEV-PLAN.md:1、Design-Brief.md:1 的普通角色菜单收敛；下文 frontend 路径均相对 `hengxin-smart-image/`。对照上一批准快照 `6f1c9282d36ff817f06b236091aa87d3b894214b581828b89b39b33979786c78`，独立核实恰好四个生产代码文件与一个浏览器测试文件变化。先前多图参考功能沿用 `docs/REFERENCE-EDIT-IMPLEMENTATION-REVIEW-20260930.md`，不重新声称审查其功能。

初始送审 `58b94154acbe7a9e45a408b070202478ee48aaeb95443301e69cb7c62195bc25` 后发生代码变化：补充旧别名规范化、持久搜索历史清理及对应浏览器断言；以上均已重新阅读及独立复验。构建生成的 components.d.ts 已恢复，最终对上一批准快照无该文件变化。旧结论不批准初始快照。

## Stage 1 · Spec Compliance · PASS

| Spec 条目 | 实现及证据 | 验证 |
|---|---|---|
| designer/operator 只显示 API 换套图及新建/记录 | 完整实现。frontend/src/router/modules/index.ts:2、10、28、31 仅管理角色保留其他分组；:20-24 保留 API 两项。core/MenuProcessor.ts:67 递归过滤父子菜单；api/auth.ts:10 将真实单角色转换为 roles 数组 | tests/api-only-menu.browser.mjs:8、24-27 四角色菜单逐项断言 |
| super_admin/design_manager 菜单不变 | 完整实现。modules/index.ts:2 允许两角色，:33-40 维持管理子项原权限；business-route-access.ts:14 对管理角色不重定向 | 同一浏览器测试验证两角色五组旧菜单和 API 入口；独立查看 design_manager 实际渲染截图 |
| 默认进入新建换图 | 完整实现。store/modules/menu.ts:59 从过滤后的首菜单推导首页；modules/index.ts:23 新建为首子项；guards/beforeEach.ts:275 根地址执行首页重定向 | browser:50-53 对普通两角色从 `/` 到 create 并等待实际标题 |
| 旧隐藏地址回到 API 入口 | 完整实现。business-route-access.ts:13-17 精确已知业务路由判断，三种旧图片处理别名先规范化；guards/beforeEach.ts:115、203 分别处理已初始化与登录初始化场景 | browser:50-53 覆盖规范路径、旧别名及首页；初始登录路由分支独立代码核查。未声称实测真实钉钉登录 |
| 清理隐藏页持久标签，包含固定标签 | 完整实现。store/modules/worktab.ts:441 在 route-name/resolve 检查前拒绝隐藏路径；:460-475 清理 opened/current，固定标志不能绕过 | browser:29-45 注入任务中心固定标签及旧 wallpaper 别名固定标签，刷新后消失；reviewer 独立运行通过 |
| 搜索不再显示隐藏入口 | 完整实现。components/core/layouts/art-global-search/index.vue:109、172 新搜索基于已过滤 menuList；guards/beforeEach.ts:258-259 在身份取得后清理持久 searchHistory | browser:36-48 注入旧模板历史，刷新后实际 Ctrl+K 弹窗确认不出现 |
| 只收敛前端入口，后端共享权限不变 | 完整实现。最终快照相对上一已批准快照仅 router 三文件、worktab 和 browser 测试变化；后端文件哈希不变 | 直接比较 `.codex/review-state.json` approved.snapshot.files 与 candidate.files |
| 无新增页面/视觉样式 | 完整实现。以上四生产文件均为路由或状态逻辑，无模板/CSS变化；modules/index.ts:20 复用原页面 | 查看 output/playwright/api-only-menu/designer.png 与 design_manager.png：侧栏、标签、标题、卡片继续沿用既有布局，无新增按钮或死引导 |

部分实现：无。未实现：无。Spec 漂移：无新增页面、API、表或组件。

初审发现并已关闭：旧 `/wallpaper/index` 等别名标签原可被静态路由匹配保留；搜索历史原直接显示旧入口。主 Agent 完成上述规范化和清理后，reviewer 两次独立运行真实浏览器测试；最终一次包含搜索历史断言，exit 0。

## Stage 2 · Code Quality · PASS

- 命名、类型和职责：business-route-access.ts:13 集中共用判断，guards/beforeEach.ts:115、203 与 worktab.ts:441 共用；新增代码无 any。helper 24 行、router modules 42 行、guard 289 行，未新增超长文件。
- 既有质量债（LOW、非本轮引入）：worktab.ts:1-571 超过 skill 的 300 行标准，本轮仅增加两条 import 与一条校验；此次不扩大到整文件重构。其异常处理仍在 :477，标签修改保留原职责。
- 测试真实性：browser:10-18 拦截身份与只读 API，运行真实前端组件和路由；:33-40 注入真实持久存储格式，:42 刷新再断言，并实际打开搜索弹窗。四角色各自新 context，不共享测试登录状态。这里验证前端入口与状态迁移，不代表线上身份服务或后端接口权限测试。
- 安全扫描：对四个生产增量文件与测试扫描 eval、dangerouslySetInnerHTML、innerHTML、密钥前缀/暴露变量等，无命中；重定向目标固定站内路径（business-route-access.ts:17），不引入 URL 输入执行、网络权限或后端授权修改。
- 视觉对比：独立查看普通角色 create 与管理角色 records 的实际浏览器截图，菜单被收敛后保留相同 230px 侧栏边界、标签栏与内容区对齐，管理角色旧分组存在。此次无视觉数值改动，无新增页面需要另做设计还原。

## 编译与验证原始输出

主 Agent 最终顺序执行 typecheck、全单测、build，执行会话 87750 exit 0；reviewer 直接读取日志核实。typecheck 的 output/menu-typecheck.log 为 0 字节，无诊断输出。早期构建曾因并行 Vite 生成声明文件产生 UNKNOWN 写入错误，不能作为成功证据；最终重建成功并恢复声明噪声。

output/menu-tests.log 原始结尾：

```text
ℹ tests 212
ℹ suites 0
ℹ pass 212
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 22746.0338
```

output/menu-build.log 原始节选：

```text
vite v7.1.7 building for production...
✓ 4494 modules transformed.
✓ built in 28.50s
```

reviewer 独立运行 `node tests/api-only-menu.browser.mjs`，exit 0，原始输出：

```text
PASS: 四角色菜单、普通角色旧标签清理、隐藏地址/旧别名/首页落地
```

最终结论：本轮限定范围 Stage 1 PASS，Stage 2 PASS；无未关闭 HIGH/MEDIUM。由主 Agent 对上述最终 candidateId 执行 review-approve，禁止登记最初快照或写 clean。测试未调用收费模型、未部署。
