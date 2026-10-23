# 多会话交互预览（待确认）

这是用户要求的独立前端预览，不代表正式功能上线。使用真实现有 OverseasShell、StudioMaterials、StudioTranscript、StudioMarkdown 和既有预览图片组件及样式。未改正式业务入口、API、Product-Spec、DEV-PLAN 或 Design-Brief。

从 frontend 目录启动：

```powershell
node node_modules/vite/bin/vite.js --config preview-studio-sessions/vite.config.ts --host 127.0.0.1
```

地址：http://127.0.0.1:3031/preview-studio-sessions/index.html

试用：在主图方案发送消息，立即切到详情页方案再次发送；两会话并行运行。每个模拟轮次约31.5秒，可用页头测试按钮提前结束或模拟失败。切换保留各会话草稿、Skill和引用。会话最多保留10个；重命名、删除位于各行菜单。运行中须先停止再删除。图片勾选仅属于当前会话，归档按任务汇总并保留来源。完成任务须有归档且所有执行已结束。

所有操作仅在内存中模拟，不调用真实Codex，不写真实任务或成品；刷新后重置，上传只在浏览器本地预览。工作目录/模型上下文隔离与真正后台并发须在方案确认后另行实施。

验证：

```powershell
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-studio-sessions/tsconfig.json
node node_modules/vite/bin/vite.js build --config preview-studio-sessions/vite.config.ts
```

最终构建输出 dist-preview/studio-sessions（Git忽略）。浏览器验证记录在 output/studio-sessions-preview/validation.md。

追加预览：页头提供设计中、已完成、解冻确认三个快捷状态；切到已完成会结束模拟生成，并在没有归档时补充一张示例成品。该操作仅用于预览。完成态所有会话只读，仍可切换查看；解冻须确认，取消保持只读，确认后保留会话/草稿/成品且不自动生成。
