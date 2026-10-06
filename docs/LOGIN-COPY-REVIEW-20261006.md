# 登录页品牌文案独立审查 · 2026-10-06

- candidateId：`55d9c466020ac347bfcd75a9b8a5cf53a7fb229ef4c029775bb7f2b9a52149d6`
- Stage 1：PASS；Stage 2：PASS。未发现本轮新增 HIGH / MEDIUM 问题。
- 范围：本轮 git diff 的 11 个受控文案/资源文件，以及 Product-Spec、Design-Brief、DEV-PLAN、变更记录和品牌 README。不是对全产品历史功能重新验收。
- 只读审查代码；仅新增本报告，不修复、不提交、不登记批准。按 code-review skill 执行。

## Stage 1 · Spec Compliance

本轮要求以 Product-Spec.md:3 为准，品牌沿用要求见 Product-Spec.md:277、Design-Brief.md:55，交付步骤见 DEV-PLAN.md:3。

| 要求 | 结论与证据 |
| --- | --- |
| 品牌副标题“企业 AI 生图平台” | 完整实现。branding/source/build_vectors.py:63、64；branding/logo-horizontal.svg:1、2、3 与 logo-horizontal-white.svg:1、2、3；frontend/src/assets/images/brand 下对应两 SVG 内容与品牌源文件逐字节一致。 |
| 主标题“让恒鑫每个团队，都能高效创作好图” | 完整实现。frontend/src/locales/langs/zh.json:132；由 frontend/src/components/core/views/login/LoginLeftView.vue:14 渲染。浅色桌面截图文字匹配。 |
| 副标题“图片生成、智能修改、素材复用，一站完成” | 完整实现。frontend/src/locales/langs/zh.json:133；LoginLeftView.vue:15 渲染。浅色桌面截图文字匹配。 |
| 彩色/反白 SVG、PNG、生成源与无障碍说明同步 | 完整实现。生成源:63、64；两 SVG 的 title/aria-label:1、2；frontend/src/views/auth/dingtalk-login.vue:12、17；branding/preview.html:15；branding/README.md:3、11。独立打开两张 2280×800 PNG，均为新副标题，未裁切。 |
| 浏览器标题和页面描述同步 | 完整实现。frontend/index.html:4、9；审查浏览器读到“恒鑫智图 · 企业 AI 生图平台”。 |
| 保持布局、图形、配色和登录行为 | 匹配。dingtalk-login.vue 本轮仅两个 alt 变化，样式/脚本无变动；LoginLeftView.vue 无 diff。XML 结构对照 HEAD：两横版 SVG 的图形组、品牌名称组完全一致，viewBox 均为 0 0 570 200；副标题字体尺寸25、基线165、字距9保持原值（生成源:63）。 |
| 引导真实性 | 无新增操作引导或不存在入口。新增文案为用户确认的产品定位，登录入口行为保持。既有图片修改实现可见 frontend/src/views/hengxin/api-image-edits/ImageConversationEditor.vue:6，已有生成入口由 Create.vue:5 选择 RealCreate.vue；本轮不将文案核对等同真实生图业务验收。 |
| Spec 漂移 | 无。未新增页面、API、数据库表、组件或权限变更；git diff 的变动均落在明确要求内。 |

上述相对代码路径均以 `hengxin-smart-image/` 为前缀。完整实现如上；部分实现/未实现：本轮范围内无。

## Stage 2 · Code Quality

- 命名、类型、职责：PASS。既有 i18n key 与资源名称沿用，没有新增 any、函数或分支。build_vectors.py 为76行；dingtalk-login.vue 为258行。生成资源长路径行不属于手写逻辑膨胀（生成源:32、44）。
- 安全：PASS（限本轮差异）。扫描修改的 Python/Vue/HTML 中 eval、innerHTML、危险 HTML 注入、密钥前缀、前端 KEY/SECRET/TOKEN 和绝对用户路径，未发现匹配；差异仅静态字符串/字形路径，没有 SQL、外部资源引用或新增输入执行。两 SVG 无 text 节点，字体已转路径，不依赖客户端安装字体。
- 测试真实性：217项既有测试覆盖业务回归，不冒充新增文案专项测试。文案专项证据是代码精确核对、SVG结构断言、实际 PNG/页面截图，及主Agent记录的1920/1280/390宽度和标题断言（docs/LOGIN-COPY-VALIDATION-20261006.md:6）。没有为了静态替换新增镜像测试。
- 视觉对比：已实际打开旧页面渲染证据 output/annotation-release-20260924/production-login.png，与新 output/brand-login-light.png 对照；蓝色按钮、表单间距、插画、H标志、两栏结构保持。视口不同，不声称逐像素相等；代码无样式差异作为补充证据。新副标题均落在品牌画布内。
- 已查看 output/brand-login-dark.png 和 brand-login-mobile.png，反白资源及窄屏品牌显示完整；深色截图通过直接添加 html.dark 获取，仅证明反白资源显示，不代表完整主题切换验收。既有手机断点隐藏左侧介绍，未要求在手机新增该区块。
- 独立 IAB 实查获得新浏览器标题，但本地无 API 导致启动500错误壳层，未独立进入完整登录页；完整页视觉证据来自主Agent提供的生产构建截图。真实钉钉登录、在线API及生产环境没有验证，不据此宣布通过。

## 编译与测试原始输出

读取主Agent运行日志，未重复执行构建；output/brand-build.log:4、5、437：

```text
> hengxin-smart-image-frontend@0.2.18 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 32.79s
```

output/brand-tests.log:225：

```text
ℹ tests 217
ℹ suites 0
ℹ pass 217
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 4449.2262
```

日志存在 npm/pnpm 配置警告，不是本轮新增代码错误。首次 dev/build 自动声明文件冲突由主Agent记录；最终成功日志及已还原的声明文件为本次依据。

## 快照复核

审查起始及报告完成后执行 `python .codex/hooks/harness.py review-status`；当前 currentId 均为上述 candidateId，审查代码快照未变化。approved=false 为尚未登记本轮批准的正常状态。主Agent可用同一 candidateId 和本报告登记两阶段 PASS；不得将结论覆盖后续改动。
