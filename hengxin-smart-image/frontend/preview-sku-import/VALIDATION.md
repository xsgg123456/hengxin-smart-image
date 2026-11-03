# 独立交互预览验证（2026-11-03）

范围为 README 中的交互预览合同；不宣称生产 API、身份或文件存储已接入。

- 类型检查：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-sku-import/tsconfig.json`。
- 构建：`node node_modules/vite/bin/vite.js build --config preview-sku-import/vite.config.ts --mode demo`。
- 浏览器验证通过 CUA 在本地 3038 独立页面完成，未请求生产 API。
- ASSK：六字段填入对应表单；1 个附件 ready 后提交按钮启用；点击弹出「图需已提交（预览）」，不创建真实任务。
- H-ZGD000901-US-G：显示3条需求；未选择时使用按钮禁用；选中后显示附件文件名；已有内容时确认覆盖，选择保留后原内容保持；取消选择不导入。
- DEMO-MULTI：4附件，图片需求2份(PPTX、PPT)、竞品2份(XLSX、PDF)；再次获取并确认后仍是4份。
- DEMO-FAIL：1成功1失败，提交禁用；重试后2份就绪且可提交；最终修改后再次验证重试成功与移除确认，计数由2变1。
- DEMO-EMPTY / DEMO-ERROR：明确空态和错误，原任务标题与附件保留。
- SP-XLLHBC01-BT：异常平台 BELEEV、空语言、空品名逐项提示，其他字段回填；未补齐不得提交。
- SKU 改变后保留来源不一致提示并阻止提交，支持重置或重新获取。
- 桌面对照：同视口直接切换正式 OverseasCreate/OverseasMaterialsPanel；新旧基础卡与资料卡宽均1023.6849 CSS px，圆角16px，body内边距23px；右侧流程卡宽300px、圆角16px、内边距20px。原版组件不修改。
- 390px 请求视口：附件卡自动单列，卡宽265.8594、scrollWidth264；文件名无横向溢出。选择弹窗实际宽293.4896、scrollWidth293，正文可滚动，footer处于弹窗内。
- 浏览器错误日志查询结果为空。
- 截图：仓库 output/playwright/sku-import/ 下 baseline.png、preview.png、requirement-picker.png、multiple-attachments.png、mobile-attachments.png、mobile-picker.png。
- 本地多文件选择验证：chooser.multiple=true，同时选择45字节文本和空文件，只加入1份有效文本，空文件错误可见；本地下载产生同名45字节文件，内容校验通过后清理测试下载。500MB上限已写实现，但未在本轮浏览器执行该大文件边界；预览不等于生产验收。
