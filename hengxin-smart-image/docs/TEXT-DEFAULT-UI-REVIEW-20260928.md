# 文字默认 Skill 前端残留清理 · 独立审查

日期：2026-09-28。审查角色：code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。本报告仅覆盖本次窄范围变更，不作为全产品重新验收。

- candidateId：`7fa6c543e691396f6c4d9aaca318dd64cba5aada652c514974626527de8c6684`。
- 源文档：根目录 `Product-Spec.md:3`、`Product-Spec-CHANGELOG.md:3`、`Design-Brief.md:3`、`DEV-PLAN.md:3` 本次新增条目。
- 代码范围：`frontend/src/views/hengxin/admin/settings.vue`、`frontend/src/views/hengxin/admin/SkillDefaults.vue`、`frontend/src/views/hengxin/model.ts`。下文代码路径相对 `hengxin-smart-image/`，根目录证据另行标明。
- 本次不提交、不发布、不删除修改入口。reviewer 仅写报告，不改实现、不登记批准。

## Stage 1 · Spec Compliance

以下逐项覆盖本次 Spec，未将旧版文字默认 Skill 要求重新当成实施依据。

| 当前要求 | 结论与代码证据 | 验证方式 |
| --- | --- | --- |
| 系统配置仅保留壁纸/商品默认绑定 | 完整实现。`frontend/src/views/hengxin/admin/settings.vue:11` 遍历专用标签，`frontend/src/views/hengxin/model.ts:8` 精确包含 wallpaper、product 两键 | 独立 diff、代码核对；浏览器证据补充见后文 |
| Skill 管理同义入口同步清理 | 完整实现。`frontend/src/views/hengxin/admin/SkillDefaults.vue:6` 使用同一标签源，`:3` 提示明确限定壁纸、商品 | 独立代码核对及打开根目录 `output/text-default-ui-skills.png` 目视检查，两选择项，无文字默认选择器 |
| 壁纸/商品默认绑定继续可编辑、可保存 | 完整实现。`settings.vue:11` 原 v-model 与可用 Skill 过滤保持；`SkillDefaults.vue:7`、`:29` 维持按模块过滤、清空、不可用项提示；`:42` 保留保存载荷 | 代码路径审查；浏览器实际编辑证据补充见后文 |
| 保存其他配置不得隐式清空历史文字绑定 | 完整实现。`frontend/src/views/hengxin/admin/settings-editor.ts:11` 克隆全量 defaultSkillIds，`:64` 从原 draft 传回三键；`SkillDefaults.vue:34` 接收全量响应，`:42` 保留原 text | 核对读入→仅两项编辑→三项提交的数据路径；隐藏选择项没有删除数据对象字段 |
| 全局任务类型标签保留 | 完整实现。`frontend/src/views/hengxin/model.ts:7` 的 labels.text 原样保留；新专用对象独立导出 | 独立 diff 与全文件核对 |
| 历史文字 Skill 和后端兼容字段保留 | 完整实现。`SkillDefaults.vue:25`、`:42` 继续容纳 text；`frontend/src/api/management.ts:19` 原 API 原样保留；后端与目录代码不在本次变更中 | git diff 范围核对；截图历史文字 Skill 目录行仍显示，不应误判为默认选择器残留 |
| 新文字任务继续内置提示词 | 完整实现且未改动。`backend/app/modules/tasks/service.py:56` 为文字任务冻结 text_snapshot；`backend/app/modules/tasks/snapshots.py:29` 文字分支绕开 Skill 绑定 | 只读代码审查，不宣称本轮重新执行真实收费改图 |
| 整套修改/单张修改只评估 | 完整遵守。`frontend/src/views/hengxin/components/TaskDetail.vue:9` 整套入口、`frontend/src/views/hengxin/components/ResultCard.vue:12` 单张入口均保留且无 diff | 源文档 `Product-Spec.md:7` 将建议明确标为未实施，验证文档记录评估 |
| 继承表单、自适应网格 | 完整实现。`settings.vue:11` class 未变，`frontend/src/views/hengxin/prototype.css:12` 两列、16px gap，`:33` 600px 以下单列保持；`SkillDefaults.vue:2`、`:5` 保留现有 Card/Form | diff 未新增 CSS；实际渲染目视证据见后文 |

部分实现：无。未实现：无。HIGH：无。引导真实性：`SkillDefaults.vue:3` 新文案对应现存壁纸/商品默认绑定流程，没有新增死入口。Spec 漂移：无，未新增页面、接口、表、组件或执行行为。

## Stage 2 · Code Quality

- 代码质量：三文件分别 40、49、26 行，均小于 300 行；`model.ts:8` 单一展示范围对象被两个表单复用，避免分散过滤；没有新增 any、类型断言或异常吞没。独立 `pnpm exec vue-tsc --noEmit` 退出码 0。
- 保存异常处理：`SkillDefaults.vue:35`、`:45` 保留读取/保存失败提示及重试；`settings-editor.ts:68` 保留 409 重读、丢弃旧表单和普通错误保留编辑值行为。本次没有更改这些分支。
- 安全扫描：对全部三个变更文件搜索 eval、dangerouslySetInnerHTML、innerHTML、VITE 密钥变量、已知 API key 前缀、any，无命中。新增内容仅标签对象和 Vue 文本/遍历绑定，不引入 SQL、执行函数、密钥或绝对路径。
- 测试真实性：根目录 `output/text-default-ui-tests.txt` 是实际 tsx 运行输出，197/197 通过。抽查 `frontend/tests/settings-monitor.test.ts:64` 范围校验、`:108` 409 冲突、`:143` 重读失败、`:166` 重复提交，均走生产 useSettingsEditor，而非只断言孤立常量。
- LOW 测试盲区：`frontend/tests/settings-monitor.test.ts:79`、`:132` 直接设置 text 是编辑器/API 兼容测试，不能再称为本轮 UI 可达交互；既有 197 项测试没有直接证明删除选择器的 DOM 行为。本轮以浏览器交互和代码证据补充，不将单测总数冒充此行为的自动回归覆盖。

## 原始验证输出

独立类型检查：执行 `pnpm exec vue-tsc --noEmit`，退出码 0，原始输出仅警告，后续无类型诊断：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

主 Agent 构建日志已经由 reviewer 打开核对；完整原始输出：根目录 `output/text-default-ui-build.txt`。关键原文：

```text
> hengxin-smart-image-frontend@0.2.11 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4480 modules transformed.
✓ built in 28.97s
```

构建包含既有 dingtalk-login 静态/动态重复导入提示及 pnpm 配置警告，不是本次三文件引入的问题。未把这些警告写成零警告构建。

测试日志原文末尾（根目录 `output/text-default-ui-tests.txt`）：

```text
ℹ tests 197
ℹ suites 0
ℹ pass 197
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3368.4921
```

## 快照与最终结论

审查中发现 Vite 自动改写 `frontend/src/types/import/components.d.ts`，当时 currentId 为 `5176e77a0fba388f094553e93faf49f558545f5bb054136a45e6d372aef556b5`，已通知主 Agent。该中间快照不能用原 candidate 直接批准。

主 Agent 关闭服务并恢复自动生成差异后，reviewer 再次独立运行 review-status，原始输出为：

```json
{"currentId": "7fa6c543e691396f6c4d9aaca318dd64cba5aada652c514974626527de8c6684", "reviewedId": "92d05a54d9398ad57b76aa38e1cf2734cef92e05d48e68963d89443ccc46474e", "changedFiles": ["hengxin-smart-image/frontend/src/views/hengxin/admin/SkillDefaults.vue", "hengxin-smart-image/frontend/src/views/hengxin/admin/settings.vue", "hengxin-smart-image/frontend/src/views/hengxin/model.ts"], "approved": false}
```

确认当前代码回到原 candidate，最终结论只对该快照有效。approved=false 是主 Agent 尚未登记本报告的状态，不是审查失败。

### 浏览器补证与视觉对比

- reviewer 独立打开根目录 `output/text-default-ui-settings.png` 和 `output/text-default-ui-skills.png`，比较两个相邻管理页面实际渲染：一致的侧栏、白底圆角卡片、蓝色操作、顶部标签与表单控件；设置页默认绑定沿用两列网格，Skill 页沿用纵向表单，无新增样式偏离。依据 `Design-Brief.md:3`，不要求把两个原有不同表单强改成相同布局。
- `output/text-default-ui-browser-settings.txt` 的 Playwright 原始操作使用实际 combobox 和 option，依次清空壁纸/商品、点击保存、等待“当前配置已保存”，重新选择两者再保存；结果 `{"clearedAndSaved":true,"reselectedAndSaved":true}`。对应 `settings.vue:11`、`:15` 的可见控件与保存操作，不是直接调用保存 API 代替交互。
- Skill 页中间记录曾出现定位超时，以及保存提示出现后目录尚未刷新的 productDefault=0；未把中间结果当成通过。最终 `output/text-default-ui-browser-final.txt` 先等待“商品替换 Skill 默认”目录单元格，再读取同一 mock 服务的 defaults，原始结果：

```json
{"defaults":{"wallpaper":"mock-wallpaper-1","product":"mock-product-1","text":"mock-text-1"}}
```

这与 `SkillDefaults.vue:34`、`:42` 的全量读取和透传实现一致，确认本轮浏览器最终状态壁纸/商品仍绑定，历史非空文字绑定保留。

- 证据边界：reviewer 的实时浏览器工具返回 `Unable to load browser request-header policy`；交互原始日志与截图由主 Agent 的隔离 Playwright 会话生成，由 reviewer 独立读取和目视审查。本轮未连接生产配置，未重做真实收费文字任务，未声称验证所有窗口尺寸；移动端网格保持的结论来自未改变的 CSS。

**Stage 1：PASS。Stage 2：PASS。** 无 HIGH/MEDIUM 问题；一项非阻断 LOW 测试覆盖说明见上。主 Agent 可对同一 candidateId 用本报告登记两阶段 PASS；reviewer 未写 clean、未修改代码、未提交或发布。
