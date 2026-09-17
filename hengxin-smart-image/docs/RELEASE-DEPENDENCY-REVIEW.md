# 发布依赖增量独立审查

日期：2026-09-17。使用 code-review skill。

candidateId：`1d611e9e314d85e29487f9e07b859c6cf5d3de7bb9e7b0db1aa00f007cd1045d`。

**Stage 1：PASS。Stage 2：PASS。结论仅限本次 tar 安全补丁增量。**

承接已批准候选 `9146276c4efa3fd86d5102947dd8e93e9fd2f748a7d06aa6dced68c75c589d34`，既有业务审查见 `hengxin-smart-image/docs/PROMPT-FORMAT-REVIEW.md:3` 及其引用的 `LOCAL-SKILL-REVIEW.md:3`。本次范围仅 `hengxin-smart-image/frontend/package.json`、`hengxin-smart-image/frontend/pnpm-lock.yaml`。下文 frontend 路径相对 `hengxin-smart-image/`，其余相对仓库根。依据 `DEV-PLAN.md:5` 的发布收尾验收，不重新验收已审业务、真实生图或线上部署。

## Stage 1 · Spec Compliance

| 要求 | 结论与证据 |
| --- | --- |
| tar 固定到修复 critical 的版本 | 完整实现。`frontend/package.json:128` 新增 overrides，`:129` 精确指定 7.5.19。GitHub 官方公告 GHSA-23hp-3jrh-7fpw 明确受影响版本 <=7.5.18，修复版 7.5.19。 |
| 同步锁文件 | 完整实现。`frontend/pnpm-lock.yaml:7` overrides 与 manifest 一致；`:3497` 包版本及 integrity、`:4680` oxide 依赖引用、`:7177` snapshot 全部一致。完整 diff 只有该 override、tar 版本与 integrity 变化，无其它包升级。安装树 `frontend/node_modules/.pnpm/lock.yaml:8`、`:3497`、`:4680`、`:7177` 同步，实际 tar package.json:5 为 7.5.19。 |
| audit critical=0 | 匹配。`output/deploy/release-audit.json:4183` 为 0；此次报告不把其余告警当成已修复。 |
| 测试、类型、构建通过 | 匹配。`output/deploy/release-frontend-tests.log:117` 共110、`:119` pass110、`:120` fail0、`:122` skipped0；`output/deploy/release-frontend-build.log:5` 实际脚本为 vue-tsc --noEmit && vite build，`:11` 转换4351模块，`:355` built in29.50s。 |
| 改动边界、引导真实性、Spec 漂移 | 匹配。只读 review-status 显示相对已批准候选只有上述两个文件；完整 diff 不含脚本、业务、UI、文案、权限变化，无新增功能或死引导。 |
| UI 一致性 | 本增量无页面、组件、样式或运行时 UI 依赖版本变化，不新增视觉验收项，承接已审业务范围。未宣称本轮重新执行浏览器视觉回归。 |

部分实现：无。未实现：无（限本次增量要求）。Stage 1 无 HIGH，进入 Stage 2。

官方来源：[GitHub Security Advisory](https://github.com/advisories/GHSA-23hp-3jrh-7fpw)，审查时实际读取。

## Stage 2 · Code Quality

| 项目 | 结论与证据 |
| --- | --- |
| 配置质量与范围 | PASS。`frontend/package.json:128` 使用单个精确 pnpm override，没有改业务源码、生命周期命令或构建白名单。锁文件属于生成文件，不以300行源码限制要求拆分；没有新增 any、重复逻辑或错误处理路径。 |
| 兼容性 | PASS（现有构建路径）。`frontend/pnpm-lock.yaml:3499` 要求 Node >=18，`frontend/package.json:6` 固定24.18.1，审查终端 node --version 实际为v24.18.1；安装的 `@tailwindcss/oxide@4.1.14` package.json:36 请求 tar ^7.5.1，7.5.19满足同一范围。类型检查和生产构建成功佐证当前工具链兼容。未额外模拟每个平台的 oxide 下载解包回退分支。 |
| 测试真实性 | PASS（增量边界）。`frontend/package.json:22` 使用实际 tsx --test；日志110条测试通过、0跳过。测试覆盖任务、绑定、HTTP等既有回归，不能单凭这些测试证明 tar 漏洞不可利用；漏洞修复依据实际解析版本、官方公告与 audit，未冒称执行漏洞PoC。 |
| 新增代码安全扫描 | PASS。对两个文件完整 diff 检查：仅固定 tar 版本及 registry integrity，没有新增密钥、eval、HTML/SQL注入、绝对路径或暴露变量。 |
| 既有依赖安全债 | 保留。`output/deploy/release-audit.json:4180` low5、`:4181` moderate39、`:4182` high62、`:4183` critical0。这些未改变的依赖告警不属于本次补丁修复范围，也不能由本报告视为全库安全通过。 |
| 视觉对比 | 不适用本次依赖增量。没有新页面，未重新打开邻居基准页面；本报告不覆盖新的视觉结论。 |

## 编译与测试原始输出

节选自 `output/deploy/release-frontend-build.log:4`、`:11`、`:355`；完整日志保留在原路径：

```text
> hengxin-smart-image-frontend@0.0.0 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4351 modules transformed.
```

```text
✓ built in 29.50s
```

构建日志`:1`、`:2` 保留 npm 配置兼容告警，`:14` 保留登录页面同时静态与动态导入的告警；均非本次 diff 引入，不宣称无告警。

`output/deploy/release-frontend-tests.log:117` 原始结果：

```text
ℹ tests 110
ℹ suites 0
ℹ pass 110
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2637.8377
```

快照检查：审查开始/结束均运行只读 review-status，currentId 与本报告 candidateId 相同，changedFiles 仅两个送审文件，未发现审查期间代码变化。报告 Markdown 不改变候选。主 Agent 应使用 review-approve 登记同一 candidateId 两阶段 PASS；reviewer 未修改代码、登记批准、写 clean、提交或部署。
