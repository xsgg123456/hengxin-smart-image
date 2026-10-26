# Codex 账号页打包文件名修复：独立两阶段差异审查

- 日期：2026-10-26；执行者：code-reviewer；技能：`.agents/skills/code-review/SKILL.md`。
- candidateId：`98086c8f797d5d8a3ad55f70b4754bb830faa0c8a8022afbd45df249d01d860d`。
- Stage 1：PASS；Stage 2：PASS。仅批准本次源码差异，不表示正式发布包或生产部署已完成。
- 基线：提交 `f3c762c`；完整功能报告 `docs/reviews/2026-10-26-codex-account-management-fixed.md:1`，批准快照 `221eb46d7566ebd1c405387eca031661c0a66f4039fd38ada295fab55975e339`。
- 范围：国内 wrapper 从 `frontend/src/views/hengxin/admin/codex-auth.vue` 改名 `codex-account.vue`，以及 `frontend/src/router/management-preview.ts:7` 的组件路径映射。下文 frontend 相对 `hengxin-smart-image/`。用户预存 AGENTS.md 修改不审、不提交。
- 输入：已读取完整实施合同 `docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:1`、既有完整功能报告、当前 diff 和 `docs/HARNESS-REVIEW.md:1`。按主 Agent 交接只复核上述差异与基线，不重新宣布全量历史功能通过。

## Stage 1：Spec Compliance

| 条目 | 结论与证据 |
| --- | --- |
| 修复生产包资产审计失败 | 完整实现。`management-preview.ts:7` 将 codex-auth 的内部组件位置映射为 codex-account；新 wrapper `codex-account.vue:1` 的模板及导入与 f3c762c 旧文件归一换行后完全相等。构建日志实际产出 `codex-account-COu4M9KU.js`；独立实际 collect_assets 645 文件通过。 |
| 公开路由、菜单与权限不变 | 完整保持。`router/modules/index.ts:20` 仍为 codex-auth，`:22` 路由名和 path 使用原 path，只有 component 使用映射；角色仍 super_admin。本次 diff 未修改该文件。 |
| 真实动态注册能找到新组件 | 完整实现。`RouteRegistry.ts:53` 转换路由后 addRoute；`RouteTransformer.ts:121` 将组件字符串送入 loader；`ComponentLoader.ts:17` 使用 views glob，`:30` 拼接直接路径。10 个 mode/query 组合均返回新路径且文件存在；实际 Vite 变换 glob 包含新 wrapper、排除旧 wrapper，exit 0。 |
| 管理预览原行为不变 | 完整保持。`management-preview.ts:3` 仍仅 monitor/settings 有预览映射；`:6` 仍同时要求 mock 与显式 query。`tests/management-preview.test.ts:5` 独立通过。codex-auth 在 production/development/demo/mock/undefined 与两种 query 的全部组合都指向正式新 wrapper。 |
| 其他布局不变、无额外产品功能 | 完整保持。新 wrapper `codex-account.vue:1` 仍渲染相同 domestic AccountPage，`:3` 导入相同模块。源码差异只有文件改名及映射一行，AccountPage、弹窗、样式、外壳和邻居页面无差异。无新增页面/API/表/业务状态；不存在额外 scope creep。 |
| 凭据、任务、API合同保持 | 完整保持。`api/codex-auth.ts:33`、`:46` 双业务前缀仍 codex-auth；该文件和所有后端/发布脚本相对基线没有差异。合同中的凭据隔离、任务保留、授权流程与发布策略沿用已批准实现，本次不改变它们。 |

部分实现：无。未实现：无。HIGH：无。进入 Stage 2。

## Stage 2：质量、安全与测试真实性

- 通过：修改文件分别 8 行、4 行；无新增 any、异常吞掉、重复业务逻辑或状态。内部组件名与公开产品路由分离在已有解析函数中完成，`management-preview.ts:7`、`codex-account.vue:1`。
- 通过：隐私审计没有放宽。`account-package.py:84` 仍调用 `package-overseas.py:115` 的真实收集器；`:127` 逐文件审计，`:138` 走原 `package-management.py:62`。独立验证旧敏感文件名仍拒绝，完整真实 dist 通过；重命名的文件本身只有 Vue wrapper，不包含凭据。
- 通过：公开 API、权限、安全令牌处理没有变更；本次两个修改文件没有密钥、eval、innerHTML、SQL 或前端秘密变量。依据完整读取及 diff。
- 测试真实性：18 项独立回归包含真实 Vue 模板组件事件、双业务实际 Response 错误解析、生命周期与管理预览；另独立补做 mode/query 矩阵和 Vite 实际 glob 变换，避免只验证字符串映射却未确认模块存在。
- 视觉结论：本次没有重新打开浏览器，使用严格内容恒等检查和零样式/布局 diff 验证本次改名不改变视觉。基线真实浏览器/邻居对比证据见 `docs/reviews/2026-10-26-codex-account-management-fixed.md:78` 起“实际视觉对比”，其适用的 AccountPage、dialog、style 与所有布局文件本次均未改变；不将旧截图宣称为本次新截图。

## 验证原始输出

独立执行：

```text
node node_modules/tsx/dist/cli.mjs --test tests/management-preview.test.ts tests/codex-auth.test.ts tests/codex-auth-component.test.ts
ℹ tests 18
ℹ suites 0
ℹ pass 18
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2851.5583
```

exit_code=0。独立 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：exit_code=0，stdout/stderr 为空。

临时 Node 校验脚本直接调用 managementComponent，5 个 mode × 2 种 query，读取新 wrapper 并与 git show 基线内容比较；Vite transformRequest 实际展开 ComponentLoader 中的 glob：

```text
PASS mapping matrix=10; wrapper identical; Vite actual glob includes new wrapper, excludes old
PASS Vite glob module keys resolve new wrapper, old wrapper absent
```

第一次使用项目 Vite 配置，所有断言通过，但关闭服务器报 `Detected unsettled top-level await`，exit 1，且自动导入插件改写了 `.auto-import.json`。随后用无项目插件的 Vite、显式原 @ alias、关闭依赖发现复验 glob，exit 0；期间一次漏配 alias 的临时验证失败已修正，属于审查脚本配置失败，不算产品编译失败。实际项目完整构建证据见下。

独立导入原 `scripts/release/package-overseas.py` 后对真实 frontend/dist 执行 collect_assets，并反向验证原规则：

```text
ASSET_PRIVACY_PASS files=645
OLD_NAME_STILL_REJECTED: Sensitive asset filename: frontend/dist/assets/codex-auth-test.js
```

exit_code=0。断言新 chunk 存在、旧 codex-auth chunk 不存在。

主 Agent 执行的新生产构建；reviewer 读取原始日志 `output/account-management-frontend-build.log:277` 与末尾，不冒称独立构建：

```text
dist/assets/codex-account-COu4M9KU.js                                                       0.89 kB │ gzip:   0.40 kB
dist/assets/index-f_galMgJ.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 36.83s
```

主 Agent 报告 exit_code=0；reviewer 独立 typecheck 亦通过。正式 account-package 尚需批准、提交后执行，本次 collect_assets PASS 仅证明原失败步骤已修复。

## 快照边界

开始独立 review-status 核对 currentId 为候选 98086c8f。审查 Vite 插件产生 `.auto-import.json` 改动时，currentId 临时变为 b959395b；已立即通知主 Agent，不将该临时快照纳入批准。主 Agent 已恢复审查工具生成文件；报告写入后 reviewer 再次独立 review-status 确认 currentId 恢复为本报告绑定的 98086c8f，changedFiles 只含映射文件及 wrapper 新旧路径。本文不写 clean、不修源码、不执行 commit 或生产操作。

