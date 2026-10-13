# AI 工作台 0.2.27 前端说明补丁独立审查

## 快照、范围和结论

- candidateId：`fecc3532590fc653eb35eacc65306512cedf45006b4c4d4946222fd50816e1a6`；基线：`442c4d3a5ffdc639c85268b564ad5538c464406c`。
- 范围：`frontend/package.json`，海外 `OverseasCreate.vue`、`OverseasMaterialsPanel.vue`、`OverseasRequirementsResubmit.vue`、`OverseasRequirementsReview.vue`、`types.ts`，以及 `scripts/release/frontend-static.py`、`test_frontend_static.py` 的本次 diff。前端路径均位于 `hengxin-smart-image/` 下；同步检查发布计划和变更记录。
- 依据：`Product-Spec.md:1012` 的新工作台/旧流程兼容要求，及 `docs/AI-STUDIO-RELEASE-20261013.md:40` 的说明修复与仅静态发布计划。业务大审查继承 `AI-STUDIO-FORMAL-20261013.md`，0.2.26 发布增量继承 `AI-STUDIO-RELEASE-20261013.md`（均在本目录）。
- **Stage 1：PASS。Stage 2：PASS。无本次增量 HIGH/MEDIUM 问题。** 审查开始和结束的 `review-status` 均匹配送审候选，未发现受控代码变化。
- reviewer 仅新增本报告，未修代码、未提交、未部署、未写 `.needs-review`。主 Agent 应以同一 candidateId 登记 `review-approve`；本报告不代替 0.2.27 生产切换后的验收。

## Stage 1：Spec Compliance

### 完整实现

| 条目 | 证据及验证 | 结论 |
| --- | --- | --- |
| 新建/studio 重提显示四节点 | `OverseasCreate.vue:107` 默认非预览且非 legacy 选择 studio；`:88` 渲染选定列表；`types.ts:61`、`:62` 共享四节点及对应描述。`OverseasTasksPage.vue:3` 的新建入口未传 workflow，因此正确使用 studio；真实 SFC 的 SSR 分支验证为 4/4。 | 实现 |
| legacy 重提及旧预览保持七节点 | `OverseasRequirementsResubmit.vue:3` 传递真实 `task.workflow`；`OverseasCreate.vue:107` 对 legacy/preview 保留旧列表；旧预览调用见 `src/overseas-preview/CreatePage.vue:1`。真实 SFC 的 SSR 验证为 7/7。生产旧任务由 `backend/migrations/overseas/versions/0012_studio.py:15` 保留 legacy，`backend/app/overseas/tasks/queries.py:32` 明确返回 workflow；不依赖省略字段猜旧任务。 | 实现 |
| 审核四节点和描述同序、旧审核保留 | `OverseasRequirementsReview.vue:51`、`:52` 按同一 workflow 分支选 STUDIO_STAGES/STUDIO_DESCRIPTIONS 或七节点描述；`:33` 用相同索引渲染。`:60` 的 studio 确认文案仍明确等待设计师发送才执行。 | 实现 |
| 资料区不承诺审核后自动分析 | `OverseasMaterialsPanel.vue:28` 改为审核通过后才能继续 AI 设计，与新工作台等待主动发送、旧任务仍需审核的共同条件一致。 | 实现 |
| 版本 0.2.26 → 0.2.27，仅前端切换 | `frontend/package.json:3`、`frontend-static.py:35`、`:37`、`:67` 目标一致，`:69` 严格检查前置 0.2.26。部署写入范围为静态资源、前端 package 与 FRONTEND_RELEASE；`:78`、`:88`、`:104` 无后端/数据库/服务控制调用。独立执行实际 deploy 测试验证后端哨兵文件不变。 | 实现 |
| 保留资源、可恢复入口、PDF.js 严格审计 | `frontend-static.py:25`、`:28` 只复用 collector，不调用海外发布器；`package-overseas.py:72`、`:89` 限定 PDF.js 6.4.299 的路径、版本、原始字节。`:70` 禁止覆盖不同旧资产，`:77` 备份，`:98` 原子入口切换，`:109` 失败恢复。真实 dist 836 资源审计与 28 项发布测试通过。 | 实现 |

### UI 一致性、部分实现、未实现、Spec 漂移

- 已实际打开 `output/studio-production/create-local-after.png`，与 `create-before.png`、邻居 `tasks.png` 对照。1280×720 中四节点和换行描述完整显示；侧栏、表单、白色卡片、蓝色按钮与基准一致。布局沿用 `OverseasCreate.vue:15`、`:84`、`:111` 的既有结构/CSS，本次无样式改动。
- 补丁截图来自主 Agent 用 CUA 打开的当前正式 dist、仅本地身份 fixture（127.0.0.1:3018），不冒充生产身份联调。生产新版本截图应在发布后补验，见计划 `docs/AI-STUDIO-RELEASE-20261013.md:40`。
- 范围内未发现部分实现、未实现或无需求依据的新页面/API/表；四节点说明对应既有已审工作台能力（`types.ts:61`）。

## Stage 2：Code Quality

- 本次五个前端源码文件分别 155、97、47、99、84 行，两份 Python 文件 126、73 行；均未超过 300 行，扫描无新增 `any`。共享文案避免创建/审核重复维护（`types.ts:61`；`OverseasCreate.vue:103`；`OverseasRequirementsReview.vue:43`）。
- 独立安全扫描本次源码未命中硬编码密钥、危险 HTML/eval、暴露前端密钥变量或 shell=True。collector 的 PDF.js 例外仍为固定依赖字节对照，非通用二进制放行（`package-overseas.py:92`、`:97`、`:102`）；实际 836 资源通过审计。
- 发布测试实际操作临时目录及真实 deploy 控制流：保留旧资源/后端哨兵、损坏包拒绝、同名资源冲突拒绝、切换后校验失败恢复旧 HTML/gzip/版本（`test_frontend_static.py:37`、`:45`、`:51`、`:57`）。collector 专测包含压缩资源敏感内容、PDF.js 版本/字节错误及路径例外边界（`test_package_overseas.py:58`、`:89`、`:106`），不是仅断言常量。
- 验证边界：311 项前端测试未直接覆盖此次四节点组件分支，既有 `tests/overseas-requirements.test.ts:25` 仍测七节点契约。reviewer 额外编译实际 SFC 并以 Vue/Element Plus SSR 验证新建、studio 重提、legacy 重提、旧预览四种可达输入，辅以当前 dist 浏览器截图；没有把 SSR 当作真实提交/审核交互测试。SSR 隔离容器提示缺少 z-index 注入，分支断言全部通过，截图未出现对应显示异常。
- 视觉对比结果同 Stage 1；仅描述和节点减少，原表单、按钮、间距和卡片保持一致（`OverseasCreate.vue:86`、`:133`）。没有需要本次阻断的问题。

## 原始验证输出

Reviewer 独立复跑：

```text
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_frontend_static.py scripts/release/test_package_overseas.py -q
............................                                             [100%]
28 passed in 0.45s
```

Reviewer 独立读取实际 dist 并执行 collector、语法检查；未绕过 clean gate 生成正式包：

```text
{"assets": 836, "bytes": 15964617, "privacy": "PASS", "pdfjsAssets": 191, "noBackendFiles": true}
PYTHON_SYNTAX_PASS 2 files
```

Reviewer 实际 SFC 的 SSR 分支断言原始输出（只在内存编译，未改源码）：

```text
new-default: 4 steps PASS
studio-resubmit: 4 steps PASS
legacy-resubmit: 7 steps PASS
old-preview: 7 steps PASS
SSR harness warnings: ["injection \"Symbol(elZIndexContextKey)\" not found."]
```

已读取主 Agent 完成的构建日志 `output/studio-hotfix-build.log:3`、`:4`、`:754`：

```text
> hengxin-smart-image-frontend@0.2.27 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 37.12s
```

既有 pnpm 配置提示仍存在（该日志第 1 行提示忽略 package.json 的 `pnpm.overrides` / `pnpm.onlyBuiltDependencies`），本次未改依赖配置。

已读取前端测试日志 `output/studio-hotfix-tests.log:317`：

```text
ℹ tests 311
ℹ suites 0
ℹ pass 311
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8735.491
```

结束时独立 `review-status`：

```text
currentId: fecc3532590fc653eb35eacc65306512cedf45006b4c4d4946222fd50816e1a6
reviewedId: 030c9183b95327d0dd4448fe8360978baa941ba1bbf5772a0b3a2e1df867daea
approved: false
```

`approved: false` 表示尚待主 Agent 登记本报告，不是代码审查失败；上述 PASS 仅适用于本候选。
