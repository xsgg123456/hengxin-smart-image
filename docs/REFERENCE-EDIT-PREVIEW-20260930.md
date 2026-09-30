# 多图参考图片修改交互预览
仅本地preview-reference-edit隔离入口，生产组件和API未改；localhost3017。复用AnnotationCanvas与草稿/导出模块，复制AnnotationEditor到预览目录增加插槽，不修改正式实现。
输入图为IT测试0930111原图4的V1成品、对应原图和共用素材只读副本。顶部三参考图可放大，画布标注自动成为第四图；无标注按三图，文字模式仅一/二图且草稿隔离。示例意见需主动点击；提交只显示演示消息。
验收：独立Vite构建退出0；output/reference-preview-check.mjs浏览器验证三/四图输入、原图放大、文字模式草稿隔离、1280/600布局、无pageerror及无写请求通过，证据output/reference-edit-preview/checks.json及截图。正式后端/多图快照/部署待确认，不宣称已上线。
