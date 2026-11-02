# 海外工作台与图需轻量调整审查

日期：2026-11-02。审查人：独立 code-reviewer；按 `.agents/skills/code-review/SKILL.md` 执行。

## 快照与范围

- 初始 candidateId：`0e0ba872e3ad423c6255c94075d525fc26d6b57ed3fc6a550e7fcd4a789c6732`。
- 最终 candidateId：`8dc65e9ed55c45815ed4a294bc70b44b3d1c426b6b747a097548f63443437652`。reviewer 通过 `review-status` 独立确认 currentId 相同；本报告对该快照中下述业务范围给出 Stage 1 PASS、Stage 2 PASS。
- 仅审查 Product-Spec.md:3–6 本轮四项需求及其业务 diff：`OverseasCreate.vue`、`platforms.ts`、`OverseasStudio.vue`、新增 `StudioDownload.vue`、`studio-download.ts`、新增下载单测与浏览器测试、既有生命周期测试新增组件 stub。下文前端路径相对于 `hengxin-smart-image/frontend/`。
- `AGENTS.md`、`.agents/skills/release-builder/SKILL.md` 为既有用户修改，明确排除，不对其作批准结论。
- 审查期间观察到构建生成的 `src/types/import/components.d.ts` 删除 16 个声明，以及浏览器测试脚本变化；最终 git diff 已确认生成声明恢复。浏览器脚本补齐 materials mock、调整真实 Element 下拉等待、缺省 placeholder 的 null 断言与窄屏收起动作，已复核，未改变产品实现。最终业务 diff 与已审实现一致，没有用初始快照结论直接覆盖新代码。

## Stage 1：Spec Compliance

业务范围结论：PASS；无 HIGH / MEDIUM 功能问题。逐条如下。

| Spec 条目 | 结果与代码证据 | 验证证据 |
| --- | --- | --- |
| 沿用当前会话勾选/全选，归档旁增加下载及数量 | 完整。`src/views/overseas/studio/OverseasStudio.vue:24` 接入按钮，`:81` 按当前会话及 selected IDs 取图；原 `StudioTurns.vue:13`、`:16` 保持组全选和单选 | `tests/studio-download.browser.mjs:75` 起实际勾选、全选下载；desktop.png |
| 空选禁用、打包加载、防重复 | 完整。`src/views/overseas/studio/StudioDownload.vue:2`、`:15`、`:16` | reviewer 独立运行 `tests/studio-download.test.ts:52` 起组件测试通过 |
| 部分/全部原图 ZIP，无需归档，保留字节/格式/尺寸 | 完整。`src/api/overseas/studio-download.ts:10` 仅接受原图 content 路径，`:11` 获取原图，`:13`–`:16` 不做画布转码；`:20` 复用 ZIP。`src/views/hengxin/download-helpers.ts:42` 以原字节存储 | browser 测试使用 archived:false、archiveId:null，下载 1/2 图并比较全部原字节；reviewer 另用 Python ZipFile 校验两 ZIP，CRC 均通过，条目数 1/2 |
| 失败提示、可重试、不下载残缺 ZIP | 完整。`StudioDownload.vue:20` 转交既有错误处理；`:21` 复位加载；`studio-download.ts:17` 释放租约，任一步失败不返回 ZIP；`use-studio.ts:39` 及 `OverseasStudio.vue:18` 显示错误 | 单测空选/外部地址/403/取消及按钮失败重试；browser 实际 503 后重试成功 |
| 切任务/会话取消未完成下载 | 完整。`OverseasStudio.vue:24` key 含 actor/task/session；`StudioDownload.vue:13` 卸载 abort，`:19` 保存前再次检查 | 单测组件卸载不保存；browser 延迟原图请求并切会话，下载计数不增加。切任务由同一 key/unmount 机制提供代码证据，未单独做跨任务浏览器场景 |
| 保留归档流程 | 完整。`OverseasStudio.vue:24` 归档禁用条件、事件及按钮原样保留 | git diff 核对；既有生命周期测试与全量 428 条通过 |
| 提交/修改任务名去示例 placeholder | 完整。`src/views/overseas/OverseasCreate.vue:24`；修改入口 `OverseasRequirementsResubmit.vue:3` 共用表单 | 新建/历史模型组件测试；browser 任务名称 input 无 placeholder 属性 |
| 平台顺序、中文标签、默认 Amazon、历史平台兼容 | 完整。`src/views/overseas/platforms.ts:1`；`OverseasCreate.vue:102` 追加历史选项；`src/api/overseas/tasks.ts:84` 默认值 | 组件测试逐项比较六项值及历史值，browser 逐项比较中文选项和默认值 |
| 三项品牌下拉、初始空、必填、历史兼容 | 完整。`OverseasCreate.vue:40`、`:100`、`:101`；`tasks.ts:84` 初始空、`:89` 必填；`requirements.ts:5` 与 `OverseasRequirementsResubmit.vue:23` 保留历史数据 | 组件测试检查三项顺序、旧品牌附加和模型未覆盖；browser 检查初始提示并选择 OUTONLIFE |
| 复用现有布局/控件/下载能力，仅隔离验证不发布 | 完整。`StudioDownload.vue:2` 复用 ElButton；`OverseasCreate.vue:40` 复用 ElSelect；`studio-download.ts:2`–`:3` 复用 image cache/ZIP | diff 无后端/API/表/部署配置变更；browser 仅允许 localhost/127.0.0.1 并拦截业务 API |

部分实现：无。未实现：无。Spec 漂移：无；新增组件/函数均服务明确需求，未增加业务页面、接口或数据表。引导文案与实际下载/归档行为一致（`OverseasStudio.vue:24`）。

UI：本轮没有独立设计稿；依据 Product-Spec.md:6 与既有 Art/Element 基准。已查看实际浏览器渲染的工作台及相邻提交图需页面截图；新增次级下载与既有蓝色归档主按钮同高，沿用既有间距和圆角；品牌下拉与邻近平台下拉一致。390px 展开模式下下载和归档均完整可见。证据：`output/playwright/studio-download/desktop.png`、`mobile.png`、`form.png`；代码 `OverseasStudio.vue:24`、`StudioDownload.vue:2`、`OverseasCreate.vue:40`。桌面/窄屏截图保留故障演示后的既有错误横幅，不表示重试下载失败。

## Stage 2：Code Quality

业务范围结论：PASS；未发现需要修复的 HIGH / MEDIUM 问题。

- 质量：下载 IO 与按钮生命周期分离，参数采用 StudioPicture 类型，无新增 any；租约 finally 释放、卸载取消、忙碌与空选早退（`studio-download.ts:5`、`:17`；`StudioDownload.vue:13`、`:15`）。新增函数文件 21 行、组件 23 行；两处修改页面分别 152/150 行，未超过 300 行。
- 安全：对四个变更业务文件执行 eval、innerHTML、dangerouslySetInnerHTML、敏感环境变量、密钥前缀、绝对用户路径及 any 模式扫描，无命中。原图 URL 限定同源业务路径（`studio-download.ts:10`），复用鉴权和重定向拒绝（`src/api/overseas/image-cache.ts:44`），文件名经 safeFilename 过滤并添加序号（`studio-download.ts:16`）。没有新增凭据、SQL、HTML 注入入口。
- 测试真实性：新增测试既覆盖纯函数，也挂载真实 Vue SFC 检查禁用、加载、防重复、错误重试及卸载；浏览器脚本运行真实 Vue/Element 控件，API 由本地 mock 提供，断言实际下载字节，覆盖 503 和切会话。reviewer 独立执行新增 4 条单测，均通过。证据 `tests/studio-download.test.ts:23`、`:41`、`:52`、`:77`；`tests/studio-download.browser.mjs:74` 起。
- 测试边界：未将本地 mock 解释为生产鉴权或真实后端验证；未覆盖生产钉钉客户端或超大图内存压力。历史品牌/平台由组件和代码链路验证，未执行真实数据库旧任务保存。以上未改后端及未授权生产测试，不影响本轮前端范围结论。

## 编译与执行证据

全量原始日志：`output/studio-download-tests.log`、`output/studio-download-build.log`。由 implementation worker 执行，reviewer 已读取；编译原始输出节选（完整输出在上述文件）：

```text
> hengxin-smart-image-frontend@0.2.55 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

vite v7.1.7 building for production...
transforming...
✓ 4703 modules transformed.
✓ built in 48.36s
```

原始日志另有 pnpm 配置字段迁移警告，构建退出 0；不将警告记成类型错误。

全量测试原始结果：

```text
ℹ tests 428
ℹ suites 0
ℹ pass 428
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9583.1961
```

reviewer 独立执行 `pnpm exec tsx --test tests/studio-download.test.ts`，退出 0，原始结果：

```text
✔ 所选图片按鉴权原图获取，部分/全部ZIP保留原始字节且同名不覆盖 (22.0461ms)
✔ 空选/外部地址/读取失败/取消不产出残缺ZIP (1.3595ms)
✔ 下载按钮空选禁用，忙碌防重复，失败可重试，卸载不触发保存 (122.1729ms)
✔ 图需表单保持默认及历史值，平台顺序与品牌下拉按要求 (53.842ms)
ℹ tests 4
ℹ suites 0
ℹ pass 4
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1105.7707
```

worker 浏览器测试退出 0；reviewer 已读取 `output/studio-download-browser.log` 并复核脚本、三张真实渲染截图和实际 ZIP 文件：

```text
PASS: 原图部分/全部ZIP字节校验、同名、空选、失败重试、切会话取消、桌面/窄屏裁切、新建表单平台/品牌/placeholder
```

独立 ZipFile 校验：partial.zip 一项 68 字节，full.zip 两项各 68 字节；`testzip()` 均为 `None`，没有 CRC 错误。

不修改业务代码，不执行部署，不写 `.needs-review`。最终同快照批准登记由主 Agent 执行。
