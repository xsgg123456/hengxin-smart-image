# 工作台、Skill 与四项合并发布独立审查

- candidateId：`ad0843abf633a7710f2bb13f7c16da45b3fd0595bb9448cf998964c70417db99`。
- Stage 1：**PASS**。Stage 2：**PASS**。本次未发现需要修复的 HIGH/MEDIUM 问题。
- 范围：Product-Spec.md:1089–1098 四项增量、DEV-PLAN.md:1366–1370，以及候选全部未提交实现。对旧批准候选 `1ada934facfa9b633aa2c0d0a91a4a544b8b5ce5a2890bc61f27f2d091039920` 的12个变化文件逐项复核；上传/时间部分以已读的 MATERIAL-TIME-FINAL-20261014.md 完整逐条报告、快照差异核实和本次抽查/浏览器重跑共同作为证据，不宣称重新验收整个历史产品。
- 审查步骤：固定候选 → 逐条需求/调用链 → 独立定时器、真实包与浏览器验证 → 质量/视觉/安全 → 再核候选。使用 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md`。
- 快照一致性：开始与结束 review-status 的 currentId 均为上述候选。中途独立 Vite 产生 components.d.ts 自动生成删减；已按主线程要求停止本人3019服务，恢复该文件到原候选（该文件原本等于HEAD），再次确认候选完全一致。没有将中途变化版本混同为已审版本。未修实现、未提交、未部署、未登记批准、未写 clean。

## Stage 1：Spec Compliance

以下代码路径以 `hengxin-smart-image/` 为根。

|需求|结论及实现位置|验证证据|
|---|---|---|
|两类图需不限扩展名，PPT/PPTX等可上传|完整实现。backend/app/overseas/materials/parsers.py:32–41 无扩展名白名单；frontend/src/api/overseas/materials.ts:25–29、views/overseas/OverseasMaterialsPanel.vue:18 同步。|相对旧批准无变化；本次独立 material-time.browser.mjs 实际页面PPTX上传/提交PASS。|
|每类一份、非空、20MiB|完整实现。parsers.py:33–38、materials/service.py:65–68、frontend/src/api/overseas/materials.ts:26–33。|旧审逐条边界证据保持有效；本次读取代码保留原限制，合并全回归通过。|
|可解析继续解析，不可解析保留原件并进入人工审核|完整实现。parsers.py:44–91、service.py:51–81；提交及重提共用绑定校验。|旧审真实字节下载/补充/重提测试证据未变；本次浏览器 failed PPTX 携带真实materialId提交PASS。没有宣称PPT在线解析。|
|鉴权、旧自动分析文字要求、不可执行上传内容|完整实现。materials/service.py:29–37；materials/files.py:96–110；studio/queries.py:14–19、30–40；plans/snapshot.py:22–30。|调用链复核：原件ready和解析failed独立，未知扩展octet-stream；旧审安全边界无变更。|
|全系统北京时间，固定格式，不改UTC存储|完整实现。frontend/src/utils/beijing-time.ts:2–30；旧审报告逐项列明国内/海外任务、审核、资料、管理、归档全部调用位置；admin/OverseasLiveActivity.vue:10–11/24/45 筛选显式+08:00。|快照证实时间代码完全未变；独立7项时间测试PASS，America/Los_Angeles浏览器将原始UTC微秒时间显示为2026-10-14 08:59:59。|
|真实SKILL.md首个H1、frontmatter描述、无标题回退|完整实现。backend/app/overseas/management/installed_catalog.py:65–92 先校验字节、跳过frontmatter、CommonMark取首个H1，无标题回退旧displayName；description取校验包。|test_overseas_installed_titles.py:18–35覆盖代码块、注释、Setext、内联样式、无标题；:39–100真实安装包及回退。独立11项PASS。|
|管理、工作台与默认选择一致|完整实现。management/skills.py:2–6 和 studio/queries.py:7/80 共用listing；frontend/src/views/overseas/admin/OverseasLiveSkills.vue:16、OverseasLiveSettings.vue:8/38–40 共用API名称；StudioSkillSelect.vue:2–6展示同一数据。|后端真实管理/工作台请求相等，freeze_selected名称相等（test_overseas_installed_titles.py:58–69）；代码核对默认下拉数据源。|
|英文ID、安装包、历史冻结不变|完整实现。installed_catalog.py:20–21身份算法未改，:88派生dict，:123–140冻结仍按release/checksum；studio/queries.py:67历史取turn.skill_name。|标题测试:52–69验证manifest字节未改、checksum/release保留；:73–95验证缓存后篡改503、新旧安装与旧简称冻结分别读取。|
|工作台完整描述可读|完整实现。StudioSkillSelect.vue:2–10 下拉名称+全文、已选说明弹窗；studio.css:2–4自动换行/滚动。|独立真实浏览器1366px/390px下拉与说明全文断言通过，稳定弹窗截图可见描述末尾。|
|自动静默，手动loading独立，无重叠请求|完整实现。use-studio.ts:33–53仅manual置loading，共享reading，finally复位。|overseas-studio.test.ts:124起在途自动请求加入手动刷新/无重叠/网络重试；本次独立测试与浏览器PASS。|
|空闲30s、执行2.5s、完成停止|完整实现。use-studio.ts:29–31由activeTurnId选频率、completed停定时器；操作结束:73/83重调度。|overseas-studio.test.ts:92–108实际hook假时钟边界29999/30000、2499/2500及completed；浏览器执行期间自动拉取、完成停止PASS。|
|隐藏暂停、返回同步、卸载停止、错误重试|完整实现。use-studio.ts:18/26/31/43–55/95；权限错误停，手动可重试；operation挡旧响应。|测试:110–147覆盖可见性、卸载监听/迟到响应、403/网络错误及竞争；独立执行PASS。隐藏前已发请求可完成，但不继续调度。|
|草稿、Skill、附件、选择与滚动保持|完整实现。use-studio.ts:7–8局部状态不由read覆盖，:40–41只更新服务端快照和事件；StudioTurns.vue:4以turn.id稳定key。|测试保留本地状态；真实浏览器引用附件、选择Skill、输入草稿、设置scrollTop后自动刷新，逐项相等断言PASS。|
|四项合并发布准备|代码准备完整。frontend/package.json:3为0.2.31；scripts/release/package-overseas.py:16，overseas-hotfix-deploy.py:27–30/95 固定目标0.2.31、基线0.2.30与既有schema。|版本diff仅更新预期常量，无迁移/安装包变更。实际安装/备份/排空/切换/生产验收属于主线程下一步，尚未完成，不记作生产PASS。|

部分实现/未实现：本次实现范围内无。Spec漂移：无新业务API/表/页面；新增组件、派生标题函数及测试直接服务以上需求。上传“原件保留/可提交”和Skill“查看说明”均有真实实现，无死引导。

## Stage 2：Code Quality

- 结构与类型：PASS。新组件StudioSkillSelect.vue共20行，use-studio.ts共97行，installed_catalog.py共140行；新增职责集中，沿用类型Studio与现有API。没有新增any、动态HTML或硬编码密钥。markdown-it-py已在backend/pyproject.toml:19与uv.lock中固定，未新增依赖。
- 安全：PASS。installed_catalog.py:57–61先完整性校验，:90再次校验树时间戳；标题只是token文字提取，前端StudioSkillSelect.vue:4–10用Vue插值，未执行HTML。历史包读取和身份算法不变。已扫描新工作台/目录代码中eval、innerHTML、v-html及秘密前缀，无匹配。上传安全沿用上表权限和受限解析进程。
- 测试真实性：PASS。标题测试创建真实安装树、使用实际管理/工作台HTTP处理、检查冻结包字节和缓存后篡改；刷新测试挂载真实hook，边界时钟、在途手动加入、权限、旧响应、卸载均有可达断言；浏览器API为隔离mock，实际Vue、Element组件和DOM参与交互，不把mock当生产集成。
- 视觉：PASS（本次修改区域）。reviewer独立打开本地3019工作台及邻居提交/审核页，亲自查看refresh-desktop.png、skill-mobile.png、material-time-upload.png、material-time-review.png；白色圆角卡、Art外框、蓝色按钮一致，依据Design-Brief.md:169/187。390px选项长文换行可滚动到末尾，说明ElDialog限制94vw及60vh。原测试弹窗截图截到入场动画，reviewer只在忽略的output/reviewer-studio.browser.mjs中增加600ms截图等待并重跑，亲自查看稳定后的skill-description-mobile.png，正文完整、无横向溢出。未修改送审测试或生产代码。
- 依赖审计边界：主线程记录critical0、既有high70/moderate48/low5，本候选不改依赖；这不是对所有历史依赖的无风险担保。

## 编译和测试原始输出

已读当前构建日志output/workbench-release-build.log:3–4及末行，未重复构建：

```text
> hengxin-smart-image-frontend@0.2.31 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 38.33s
```

已读output/studio-frontend-typecheck.log（vue-tsc --noEmit），output/studio-frontend-tests.log与output/workbench-release-backend-full.log原始汇总：

```text
ℹ tests 347
ℹ pass 347
ℹ fail 0
2007 passed, 185 skipped, 15 warnings in 263.39s (0:04:23)
```

reviewer独立运行，退出码均0：

```text
pnpm exec tsx --test tests/overseas-studio.test.ts tests/beijing-time.test.ts tests/beijing-time-component.test.ts
ℹ tests 21
ℹ pass 21
ℹ fail 0
.venv/Scripts/python.exe -m pytest tests/test_overseas_installed_titles.py -q
11 passed, 2 warnings in 3.34s
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
PASS: America/Los_Angeles browser renders Beijing list/review time; unparsed PPTX uploads and submits to review
```

日志包含既有pnpm配置字段提示及Starlette弃用警告，无本次失败。独立浏览器使用主线程提供的Playwright模块、本人启动的本地3019服务和隔离API；600ms截图补证脚本首次路径调用错误，纠正工作目录后重跑PASS，未将失败调用计入通过。

## 交接边界

两阶段PASS只批准上述代码候选。后端全量为主线程Linux只读无网络证据，185 skip不计验证通过；reviewer独立后端测试为Windows真实临时安装树/TestClient。未连接生产、未调用模型、未做生产安装和部署，不代表生产已修复。主Agent可按协议登记本报告与同一candidateId；后续代码变更必须重新固定候选。生产镜像安装、备份/关接纳/排空、切换及真实浏览器验收仍由发布阶段完成。
