# 图片处理菜单新建语义审查

- 日期：2026-09-22；审查者：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- 最终 candidateId：`d76d3b64ce52c3cecfcc573ce84c66f373361e585e913b50587e074d19c4ea0d`。
- 范围：`Product-Spec.md:3`、`DEV-PLAN.md:3` 的本次新增条目；`hengxin-smart-image/frontend/src/utils/navigation/jump.ts` 的增量；新增 `hengxin-smart-image/frontend/tests/new-task-menu.browser.mjs`。下文源码路径以 `hengxin-smart-image/frontend/` 为根。不是全产品重新验收，也不代表生产发布完成。
- 快照变化：最初候选 `9afa9ad15c1c63d9a20420db3cc860551cee3d9204ab51f8f9a1e862bc1ce908` 后测试调整为关闭抽屉、展开菜单、等待 DOM；随后 `d4e3dfb017dcb9aef85d120a17b23d6dd8a295de74ac0e92977cbce0de26c6d5` 增加测试第 12 行运行中状态前提，形成最终候选。已读取最终测试全文。review-status 实测 currentId 与最终候选一致，受控变化仅 jump.ts 与新增测试。

## Stage 1：PASS

| 本次 Spec 要求 | 结论及证据 |
| --- | --- |
| 三个菜单每次直接进入独立新任务 | 完整实现。`src/utils/navigation/jump.ts:22` 精确匹配三个路径并创建 UUID；第 48、65、74 行覆盖直接、父级回退、首个子菜单跳转。`tests/new-task-menu.browser.mjs:19` 逐个真实点击三菜单。 |
| 同页重复点击也清空素材、任务信息、受理回执 | 完整实现。`src/views/hengxin/use-create-task.ts:17` 将 newTask 纳入会话；`task-creation-session.ts:5` 初始化空 sources/name/sku/note 与独立 submission，第 18 行以 identity/mode/query 分区。浏览器测试第 24–31 行断言空名称、无回执、无素材，并重复点击验证名称清空。 |
| 前任务未完成时创建入口仍可用 | 完整实现。测试第 12 行明确等待排队中或执行中，再关闭详情并点击菜单；执行日志 PASS。不会以已完成任务代替用户反馈前提。 |
| 旧任务保留、历史由任务中心访问 | 完整实现。jump.ts:22 只有 router.push，不调用取消或删除接口；测试第 33–35 行重新打开原任务详情并核对原任务名称。 |
| 未确认请求保留原幂等键、不自动重放 | 完整实现。`task-creation-session.ts:11` 的旧会话 Map 保留；`task-submission.ts:16` 捕获原 submission，第 27 行使用其原 input/key；导航无 send 调用。`tests/task-creation-session.test.ts:25` 验证恢复后原键/原输入，`:78` 验证切入口再回旧会话仍 uncertain 且请求数为 1；`:98` 验证迟到回执隔离。均在 125 项通过结果内。 |
| 其它菜单导航不变 | 完整实现。jump.ts:25 非目标路径原样传 router.push；外链判断第 41 行与第 69 行维持原逻辑。 |

部分实现：无。未实现：无。Spec 漂移：无新增页面、API、表或组件；UUID 参数直接服务本次新建语义（jump.ts:22）。引导真实性：专项确认新建表单没有“查看已受理任务”回执按钮（测试第 25 行），保留原任务可访问。

## Stage 2：PASS

- 代码质量：jump.ts 共 75 行，新增私有 helper 单一负责目标路径变换，三个分支复用；参数 string，未引入 any 或重复提交状态实现（jump.ts:22、48、65、74）。
- 安全扫描：对两个变化代码文件扫描 eval、dangerouslySetInnerHTML、innerHTML、VITE 密钥前缀、SECRET/TOKEN、用户绝对路径及常见密钥前缀，无命中。UUID 仅作为前端会话分区，不作为身份凭据；身份隔离继续由 task-creation-session.ts:16–18 提供。
- 测试真实性：新增测试使用真实菜单、表单、抽屉和 URL，不 mock 导航函数；第 12 行显式验证前任务处于排队或执行中。旧 uncertain 状态依靠现有会话测试，不宣称新增浏览器用例已覆盖真实服务器断网；此次未修改提交器，已有故障路径回归通过。
- UI 一致性与视觉对比：无模板或样式变更。审查者通过 CUA 打开独立 `scenario=menu-review-20260922`，实际查看壁纸表单并点击商品菜单，确认 URL 生成 newTask；加载结束后截图对比两页标题、分区卡片、浅色背景、侧栏选中态保持既有共用设计。默认场景被另一标签页占用时未重置或修改该场景。审查标签页已关闭。证据关联 jump.ts:22 与测试第 19–31 行；此次未做全视口/像素级设计重验。
- HIGH / MEDIUM 问题：未发现。生产 Worker 执行与部署不在本次审查范围。

## 编译与验证证据

主 Agent 提供的 typecheck 退出码为 0；该命令无文本输出，本报告不伪造其输出。审查者直接读取以下原始日志。

`output/new-task-menu-tests.log` 末尾原始输出：

```text
ℹ tests 125
ℹ suites 0
ℹ pass 125
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 5197.7216
```

`output/new-task-menu-browser.log` 原始输出：

```text
PASS: three menu entries create fresh sessions, repeated same-menu click resets draft, accepted receipt not reused, previous task retained
```

`output/new-task-menu-build.log` 原始输出节选（完整构建输出保存在原日志）：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4369 modules transformed.
rendering chunks...
dist/assets/index-BIIK6Ygp.js                                                       1,615.79 kB │ gzip: 533.72 kB
✓ built in 36.68s
```

日志另含既有登录页同时静态与动态导入的拆包提示，无构建失败。仅主 Agent 可据本报告对同一最终 candidateId 登记两阶段 PASS；本审查未执行 review-approve、未写 clean、未提交代码。
