# 批量画布与参考图 · 已确认的独立交互预览

此目录保留独立预览，不调用生成服务。用户已于2026-11-05确认当前方案并授权正式开发、提交和部署；正式范围与验收见根目录 `docs/STUDIO-BATCH-ANNOTATION-20261105.md`，正式实现位于 `src/views/overseas/studio/`。以下记录原预览的规划与运行方式。

## 规划与完成标准

1. 复用 OverseasShell、StudioSessionList、StudioMaterials、StudioAssetImage、AnnotationCanvas、AnnotationMarks 及生产工作台样式。PreviewTurns 由生产 StudioTurns 原样派生，仅增加批量入口。使用已有六张灯具样图并明确示例性质。提供 baseline=1 查看生产组件的原单张编辑器与相同外壳，桌面同视口对照。
2. 大画布展示六张图，缩放/平移、逐图框选/画笔、选图及单图精细编辑共享草稿。标注意见、参考图以图片 ID 绑定。只把有标注的图片带回输入区；参考图但无标注者提示排除且保留草稿。完成标准：仅标第2、4张时，输入区只有2项。
3. 单图沿用1380px弹窗和原 AnnotationCanvas；右侧新增本地参考图，逐张选择本产品实拍/成品效果参考/自定义用途。选择自定义后显示自由输入框，必填且不能只有空白；自定义内容在核对、带回、发送及历史材料中完整保留。切换预设用途时保留自定义草稿，实际提交以当前选项为准；各类型仍单独填写参考说明。支持多图、预览、替换、删除、读取错误重试。无标注单图可带回，在工作台补意见。完成标准：未填用途/说明时明确阻止确认；批量和单图均可使用自定义用途，返回编辑与发送历史不丢失。
4. 带回工作台前展示材料核对；确认后不自动发送。支持继续编辑、更新不重复、取消修改。关闭弹窗保留本次页面草稿，刷新重置。模拟发送展示冻结的实际材料/意见，不伪造生成结果。完成标准：两个图片的参考图不串、发送历史不会随草稿后续编辑而变化。
5. 类型检查、生产预览构建、浏览器功能与视觉验证、独立两阶段审查。桌面1920/1440、窄屏390检查主控件可达；错误/空态/移除/取消/重开/输入校验均覆盖。

## 运行

在 frontend 目录运行 `node node_modules/vite/bin/vite.js --config preview-batch-annotation/vite.config.ts`。
入口 http://127.0.0.1:3036/preview-batch-annotation/index.html
原组件对照入口附加 `?baseline=1`。基准模式不提供新增功能。

验证命令：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-batch-annotation/tsconfig.json`；`node node_modules/vite/bin/vite.js build --config preview-batch-annotation/vite.config.ts`。

所有新增操作仅保存在浏览器当前页面内存；文件本地读取，不上传真实服务。与本预览无关的业务按钮只说明预览边界。网络隔离另以浏览器验证确认。真实生成效果、后端持久化、跨设备同步不属于本次预览验收。
