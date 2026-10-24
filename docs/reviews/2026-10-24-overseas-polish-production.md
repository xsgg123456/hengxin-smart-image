# 海外三项轻量优化正式实现审查

- candidateId：`8abca6d88623b54ebffc8fdf5ef44f5f54dd44330c9ff438795c83391fc8531c`。
- 范围：正式前端三项 diff、0.2.53 版本、专项测试及 `scripts/release/frontend-polish.py` 静态发布安全。下文 `frontend/` 指 `hengxin-smart-image/frontend/`。
- 合同：Product-Spec.md:1343、Design-Brief.md:221、DEV-PLAN.md:1566 的 2026-10-24 三项优化段落。
- 不包含用户预存 AGENTS.md 修改、既有独立预览、整套多会话功能重新验收或实际生产安装。只写报告，未修代码、提交或批准凭据。
- 结论：**Stage 1 PASS；Stage 2 PASS（本次增量范围）**。本次新增实现未发现 HIGH/MEDIUM 阻断项；既有浏览器回归与依赖风险见下文，不等于全项目无风险。

## Stage 1 · Spec Compliance

| 条目 | 结论和证据 |
| --- | --- |
| 提交/修改图需标签去掉语言，market 不变 | 完整实现。frontend/src/views/overseas/OverseasCreate.vue:43 使用“目标站点”，:44 仍绑定 draft.market；修改入口 OverseasRequirementsResubmit.vue:3 复用同组件。workflow.ts:29 同步校验提示。浏览器专项实查标签仅出现一次、旧标签不存在（tests/overseas-polish.browser.mjs:81）。 |
| 指定六平台及顺序 | 完整实现。frontend/src/views/overseas/platforms.ts:1–8 逐项为 Amazon、Mercado Libre、Walmart、The Home Depot、Shopee、Wayfair，对应指定中文标签。OverseasCreate.vue:35–40 分离 label/value。独立浏览器复跑精确断言完整六项顺序并选择家得宝（tests/overseas-polish.browser.mjs:77–80）。 |
| 英文持久值、新建 Amazon、历史值兼容 | 完整实现。frontend/src/api/overseas/tasks.ts:84 默认 Amazon，:86 清理请求仍保留英文 platform 和 market；OverseasCreate.vue:101 对不在列表的旧平台追加同值选项，无重置赋值。OverseasRequirementsResubmit.vue:23 从旧任务建立草稿，:33–35 原值进入重新提交请求。此项包含源码链路验证，未宣称真实生产提交或数据库写入测试。 |
| 原工作台两行和各列/高度不变 | 完整实现。frontend/src/views/overseas/studio/OverseasStudio.vue:33 保留 rows=2、resize=none；diff 未改变高度算法和列样式，studio.css:71 仅增加发送组 flex。专项在 1920×911、1366×900 比较短文/100 行长文输入框高度相等并断言 rows=2（tests/overseas-polish.browser.mjs:52–58）。 |
| 仅发送旁增加入口 | 完整实现。OverseasStudio.vue:34 添加 StudioTextEditor 与原发送/停止按钮同组，原 Skill 和其他组件保持。formal-1920.png、formal-1366.png 目视按钮可见，未见新增标题行或列宽变化。 |
| 960px/94vw、16px、1.8 行高可编辑弹窗 | 完整实现。StudioTextEditor.vue:3 width=min(960px,94vw)，:5 是双向绑定 textarea，:20 字号16px/行高1.8。dialog-1366.png 目视左右位置对应960px宽度，专项读取实际 computed fontSize=16px（tests/overseas-polish.browser.mjs:60）。 |
| 同步草稿，Enter 换行，Escape/完成保留 | 完整实现。StudioTextEditor.vue:5、:13 直接绑定同一 model，无副本覆盖；:6 完成仅关闭弹窗。真实 Element 组件专项输入两行并分别执行 Escape/完成，原输入框精确等于编辑内容（tests/overseas-polish.browser.mjs:61–70）；本审查者独立复跑通过。 |
| 会话隔离、锁定规则 | 完整实现。OverseasStudio.vue:34 以 activeId 为 key，传入同一个 locked；StudioTextEditor.vue:2、:5 同时禁用入口和输入。use-studio.ts:25 原权限/忙碌/上传/待核实锁定未改，studio-session-state.ts:18–28 model 转发当前控制器。浏览器切换两会话往返草稿正确，完成后按钮禁用（tests/overseas-polish.browser.mjs:72–75）。 |
| 不增加正式示例或预览开关 | 完整实现。正式 diff 仅三项及版本/测试/发布文件；StudioTextEditor.vue:4 使用真实 sessionName。没有新增路由、后端 API 或表。测试假 API 只位于 tests/overseas-polish.browser.mjs:28–44；正式构建日志为 production。 |
| 0.2.52→0.2.53，仅静态发布、备份/原子切换/回退 | 完整实现（代码及隔离测试范围）。frontend/package.json:3 为0.2.53；scripts/release/frontend-polish.py:79–82 核验新包及旧版本，:83–89 拒绝覆盖不同字节的既有静态资源，:90–100 备份入口/压缩入口/package/版本清单并核验哈希，:102–125 拷贝新资源、原子替换入口后验证，:126–132 失败恢复。脚本无 API/执行器重启或数据库命令。独立四项发布测试通过，实际生产安装由主 Agent 后续执行。 |

部分实现、未实现、死引导、Spec 漂移：本范围未发现。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2 · Code Quality

- 结构和类型：通过。新平台配置8行、独立弹窗24行、发布入口144行以内；StudioTextEditor.vue:13–17 使用明确 model/props/组件实例类型。正式改动没有引入 any、网络副作用或独立草稿副本；沿用既有错误/锁定路径。
- 安全扫描：对新增正式模块与发布脚本检索 eval、innerHTML、危险渲染、秘密变量、密钥前缀和用户绝对路径，未发现匹配风险。平台/会话名均通过 Vue 文本/组件属性呈现（OverseasCreate.vue:39、StudioTextEditor.vue:4），没有增加 HTML 注入入口。
- 发布源与包审计：frontend-polish.py:16–20 只容许用户 AGENTS.md 既有改动，其他 tracked/untracked 源必须提交；:29、:59 固定审查快照，:39–43 校验已提交源码/隐私，:37 复用 collect_assets。package-overseas.py:115–129 对构建资产拒绝链接并执行白名单审计，:132–148 特殊 PDF 资产按固定依赖字节核对。包内含版本/提交/candidate/文件哈希（frontend-polish.py:46–48），安装前后核验（:63–67、:125）。本结论针对由该受控打包流程产出的包及受控发布目录，不视作任意不可信目录导入工具审计。
- 故障测试真实性：scripts/release/test_frontend_polish.py:40–77 使用实际临时文件与 deploy，覆盖保留旧资源/后端、损坏包拒绝、同路径不同字节拒绝、切换后校验失败恢复入口及metadata。不是只检查 mock 调用；本审查者独立运行4项通过。
- 交互测试真实性：tests/overseas-polish.browser.mjs:28–44 只替换 API 响应，页面使用实际 Vue/Element 正式 dist；:52–83 检查 DOM 尺寸、真实键盘输入、回填、会话和禁用态、完整下拉选项。没有把模拟预览当正式功能验证。studio-lifecycle-component.test.ts:47 新增的是组件 mock，因此该单测不独立证明弹窗，证据来自浏览器专项。
- 视觉对比：已打开 `http://127.0.0.1:3032/preview-overseas-polish/index.html` 邻居预览实际渲染，并对照正式 dist 的 formal-1920.png、formal-1366.png、dialog-1366.png、create.png。正式三列、两行输入、发送区按钮与已确认第二版一致；弹窗沿用 Element 白底/圆角/蓝色完成按钮。正式页面没有预览模式切换。截图位于 output/playwright/overseas-polish/，代码对应 OverseasStudio.vue:33–34、StudioTextEditor.vue:2–6、studio.css:71。

### 验证边界与既有风险

- 旧 `studio-sessions.browser.mjs` 本轮未通过：主 Agent 实跑先因缺少 `/tasks/t/materials` fixture 返回404；临时补fixture后等待“有新结果”20秒超时，而旧轮询周期30秒。本报告不将该套标为PASS，也不将未通过自动认定为本次三项造成的产品回归。新专项确实覆盖本次受影响的会话草稿与完成禁用；旧完整多会话回归仍有测试证据缺口。
- 主 Agent 报告 studio-outputs 浏览器回归通过；本审查者未独立重跑该套，结论不依赖其作为弹窗证据。
- `output/polish-audit.json:5176–5180` 记录现有依赖风险计数：critical=0、high=71、moderate=52、low=9。此次未改依赖/锁文件，本报告未逐条判断漏洞可达性，也不宣称依赖安全扫描零问题；范围内新增代码扫描通过不能覆盖此历史风险。
- 尚未执行生产安装、线上真实表单持久化或收费生成。发布基线、备份目录、包哈希、安装后的健康与正式页面需由主 Agent 在部署阶段留证。

## 原始测试与编译输出

审查者独立执行类型检查：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
exit_code: 0
output: ""
```

审查者独立执行正式 dist 浏览器专项（IDENTITY_UI_URL=http://127.0.0.1:3035，PLAYWRIGHT_MODULE 指向已安装运行时）：

```text
PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/site label
exit_code: 0
```

首次无 PLAYWRIGHT_MODULE 运行报 ERR_MODULE_NOT_FOUND；设置现有模块路径后成功，未安装/修改项目依赖。

审查者独立执行发布故障测试：

```text
test_corrupt_archive_rejected_before_backup ... ok
test_failure_after_switch_restores_old_entry_and_metadata ... ok
test_install_preserves_backend_and_old_assets ... ok
test_same_asset_path_changed_rejected ... ok
Ran 4 tests in 0.149s
OK
exit_code: 0
```

已读取主 Agent 全量单测 output/polish-unit.log 的原始输出：

```text
ℹ tests 396
ℹ suites 0
ℹ pass 396
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9529.6199
```

已读取 output/polish-build.log 的原始生产构建输出：

```text
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.53
vite v7.1.7 building for production...
transforming...
✓ 4685 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 40.05s
```

审查前后 review-status 均返回上述 candidateId，未检测到受审代码变化。报告为 Markdown，不修改候选代码；批准登记由主 Agent 对同一快照执行 review-approve，不写 clean。
