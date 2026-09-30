# 多图参考图片修改 · 正式实现验收

用户确认本地预览并授权开发；API卡片按钮改为“修改图片”。本轮仅本地实现，不自动提交Git、部署或收费生成。

## 实现

新图片修改v2按当前成品、对应原图、共用素材、可选标注顺序冻结；旧v1快照保持原1/2图；文字与文案修复保持原逻辑。页面展示实际参考图、原文件放大、输入计数和确认预览。独立草稿与未知请求恢复保持隔离，缺失参考图明确拒绝图片修改；尺寸仍以最初原图为准。固定提示词使用通用最小修改约束，正式页无业务示例默认意见。

## 验证证据

- 后端专项69通过；完整1382通过、174跳过。真实RelayClient经Mock HTTP核对图像字节/顺序与两轮方图、长图PNG尺寸；旧v1损坏新增参考图时仍按旧冻结输入执行。`output/reference-backend-tool-results.txt`为原工具结果转录及尾部摘要，不是完整stdout。
- 前端单测212通过，见`output/reference-frontend-tests.log`。类型检查及生产构建通过，见`output/reference-frontend-typecheck.log`、`output/reference-frontend-build.log`。
- 隔离浏览器模式流程通过：3/4图确认、真实原图放大、互斥请求、旧v1未知请求恢复、缺失素材提示和多视口按钮可达，见`output/reference-modes-browser.log`。
- CLI隔离浏览器回归通过：历史V1、框选/画笔、原尺寸导出、冻结同key/body重试，见`output/reference-cli-browser.log`。
- 画布16组合通过：800×800/790×1500、1920/1280/600/390四视口、框选/画笔，覆盖意见输入与滚动CTM稳定、框内新增、NW/E/SE手柄、缩放平移、取消回滚、原尺寸导出。见`output/reference-annotation-browser.log`与`output/playwright/annotation-workspace/checks.json`。测试按原图比例落点，窄屏先适度放大使手柄可达，全部断言保留。独立审查见`docs/REFERENCE-EDIT-IMPLEMENTATION-REVIEW-20260930.md`。

## 边界

浏览器业务接口隔离Mock；未调用生产模型或验证模型实际修图质量。后端有条件跳过测试包含未配置独立PostgreSQL环境。收费生成效果、生产部署不在本轮验收范围。

