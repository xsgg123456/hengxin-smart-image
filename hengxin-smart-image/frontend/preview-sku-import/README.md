# SKU 获取需求 · 独立交互预览

仅供用户评审交互，不改变正式需求文档、生产组件或业务接口。复用正式 OverseasShell、全局样式；CreatePreview 从当前 OverseasCreate 原文复制，只将多 SKU 区替换为查询插槽。对照开关直接渲染正式 OverseasCreate 与 OverseasMaterialsPanel。

启动：在 frontend 运行 `pnpm exec vite --config preview-sku-import/vite.config.ts --mode demo`，访问 `http://127.0.0.1:3038/preview-sku-import/index.html`。

验收范围：
- 单 SKU、获取按钮、查询中、空结果、错误重试、变更 SKU 后拒绝旧结果。
- 单条回填六字段；多条必须选择，取消无修改；异常/空值提示，保留原有值；已有值回填确认。
- PPT/PPTX 分类到图片需求，其他附件到竞品；两类多份；同记录重复获取按 ID 去重；切换记录确认替换。
- 附件导入进度、失败重试/移除、本地多文件添加和下载、非空/500 MB 校验；导入或失败未处理禁止提交。
- 示例提交只显示本地结果，无生产请求、无 API 密钥；上游附件为元数据样例，下载按钮明确说明没有导入真实原件。
- ASSK / SP-XLLHBC01-BT / H-ZGD000901-US-G 字段采用本轮实查快照；日期/状态及设计人选是展示用静态数据。DEMO-* 为明确标记的边界模拟。
- 桌面同视口比较基准与修改页面；窄屏和长文件名可达。

本预览不代表真实查询、服务端下载保存、身份匹配或后续审核/工作台多附件已实现。正式接入须待用户确认。
