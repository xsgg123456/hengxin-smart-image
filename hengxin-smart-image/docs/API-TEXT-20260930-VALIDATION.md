# API 文案操作与创建预填验收（2026-09-30）

范围：用户手动修复文案、单张文字修改、创建默认提示词；不含生产部署、Git提交或真实模型收费测试。

## 验证结果

- 后端 Linux 完整回归：1419 passed、79 skipped、15 warnings（154.67s）。断网容器只读挂载仓库；条件跳过包括独立数据库等场景，非全环境通过。日志：output/api-text-backend-full.log。
- 后端最终补验：39 passed、2 warnings（12.05s），覆盖最终旧请求幂等兼容及修订执行/保护/快照。日志：output/api-text-backend-final.log。
- 后端全部 API 专项：139 passed、0 skipped、2 warnings（29.12s）；独立临时PostgreSQL及SQLite，含并发、旧冻结快照、0022升级降级、空旧类型回退。临时数据库容器已清理。compileall通过。
- 前端：pnpm test 207/207；pnpm typecheck、pnpm build退出码0。日志：frontend/tests-latest.log、frontend/build-latest.log。
- 实际Vue页面隔离浏览器：scripts/api-text/browser.mjs，Chromium、1440/1920/390视口；所有API拦截、非本地请求阻断，未连接生产。output/playwright/api-text/result.json errors为空。
- 浏览器覆盖：默认提示词与完整原文一致、已有和显式清空草稿保留；修复空意见、未知响应相同key/载荷确认、禁重复；失败保留V1、继续重试、新V2；纯文字无标注上传；圈注对应意见、导出PNG标注上传；历史类型；窄屏按钮和弹窗不横向裁切。截图同目录。

## 行为与边界

修复输入为当前成品+原始底图；文字修改为当前成品+可选标注。服务端按kind构建内置提示词，不接受客户端覆盖固定规则。新输出沿用原source_id尺寸锚点、动态size、Pillow Lanczos及PNG。成功新增版本，失败保留当前版本。

前端及队列行为经过隔离验证，真实Sunburst的字体清晰度、杂色修复和布局保持效果本轮未新增验证，提示词不能保证像素完全一致。历史冻结请求保持旧输入，不用新逻辑改写历史重试。部署时须运行0022迁移并同步前后端，当前尚未部署。
