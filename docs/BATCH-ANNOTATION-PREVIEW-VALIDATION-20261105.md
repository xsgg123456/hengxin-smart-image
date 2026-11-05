# 批量画布及单图参考图交互预览验证

本次仅独立预览。正式需求、设计规范、计划及生产 src 均未修改。入口 http://127.0.0.1:3036/preview-batch-annotation/index.html 。图片使用既有六张灯具样图；新增文件本地读取，不上传、不调用AI，刷新后重置。

## 验证范围

- 实际复用现有 OverseasShell、会话列表、素材栏、图片预览、AnnotationCanvas、AnnotationMarks 和工作台 CSS。
- 原生产单张编辑器对照入口 `?baseline=1`；1920×1080下原/新单图弹窗均1380×926，左侧画布复用原组件。新增交互限定右侧参考图区及批量入口/草稿摘要/历史材料入口。
- 1920、1440桌面及390窄屏：整组画布、精细标注、滚动参考区和底部确认按钮。390图片区域已加高避免画布被工具栏挤压。
- 批量框选、画笔、拖动编号、缩放平移、同区精细查看；第2/4张独立意见与参考，只有参考图无标注者排除；关闭重开保留，确认核对后仅带回目标，不自动发送。
- 上传参考图、两种用途、逐图说明必填、放大、替换、删除、坏图重试/阻止提交；异步读取序号防止替换/重试过期结果回写。
- 单批共享草稿、更新不重复、移除已清空图片旧卡片、取消修改、无标注单图补意见、手动模拟发送。发送历史材料及文本冻结，后续编辑不污染。
- 浏览器未发现脚本异常，未请求真实业务 `/api/`。原六张图片未被修改。其他业务功能明确为本预览范围外。

## 当场执行

工作目录 `hengxin-smart-image/frontend`：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-batch-annotation/tsconfig.json
exit 0，无错误输出

node node_modules/vite/bin/vite.js build --config preview-batch-annotation/vite.config.ts
✓ built in 21.61s

node --import tsx --test tests/*.test.ts
514 tests / 514 pass / 0 fail（完整日志见 preview-batch-annotation/regression.log）
```

仓库根目录：

```text
node output/batch-annotation-preview/browser-check.cjs
COMPLETE 35 checks
```

浏览器脚本使用独立 Chromium context，测试后关闭。逐条断言、错误和请求清单见 `output/batch-annotation-preview/validation.json`，可复跑脚本与日志同目录。

## 截图证据

`output/batch-annotation-preview/`：workspace.png、batch-empty.png、batch-marked.png、single-with-references.png、returned.png、send-review.png、baseline-single.png、single-empty.png、batch-1440.png、single-390.png、references-390.png、batch-390.png。

首次交付代码快照 `ed3e2858f2f6c7672905a87834c6faa2177900566b972bb323419642a374b4b5`；独立审查见 `docs/BATCH-ANNOTATION-PREVIEW-REVIEW-20261105.md`。真实后端提交、跨刷新持久化、AI生成效果不属于本次预览验收。

## 同日增量：参考图自定义用途

用户要求保留两种预设用途，增加“自定义用途”，供用户自由填写。范围仍限独立预览，正式需求及生产代码未改。

- `output/batch-annotation-preview/custom-purpose-check.cjs`：16项通过，覆盖三个选项、空值及纯空白拦截、多行输入、预设切换保留草稿且按当前用途提交、单批共享、确认/发送/历史保留、历史快照隔离、390窄屏可填写及无浏览器异常。
- 原浏览器回归35项通过；类型检查exit 0；构建成功24.19s；原前端测试514通过、0失败。
- 截图：`output/batch-annotation-preview/custom-purpose.png`、`custom-purpose-390.png`；已目视检查输入字段与既有参考说明、确认按钮均可见。
- 增量送审快照：`b69796817b9d38516148ccda622bcfba162e6a4e07373f8b45d2d303b7dd50e9`。
