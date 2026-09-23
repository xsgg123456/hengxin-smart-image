# 原图参照、统一图片上传与模板弹窗 · 正式实现验证

用户认可隔离预览并授权开发，尚未部署、推送或提交。正式源码位于hengxin-smart-image/frontend；后端、数据库、模型与计费均未修改。

## 实现

- API正式与Demo详情复用SharedMaterial、SourceComparison，展示冻结原始输入与当前成品；刷新当前版本后同步对照。旧记录显式null输入可读取，损坏DTO/成品仍严格校验，缺失输入提示及图片失败重试保持。
- UploadInteraction统一图片拖拽、聚焦区Ctrl+V、粘贴按钮；复用每入口的上传和校验。覆盖模板新建/配置、三类CLI创建、CLI问题截图、正式及Demo API输入序列/标注图。单图满额先移除；多图上传可继续追加。文本粘贴、内部排序、禁用及卸载/迟到剪贴板读取隔离。
- TemplateEditor承接已认可的居中布局、最大视口高度、内部滚动、固定头尾。

## 当场验证

工作目录为hengxin-smart-image/frontend。Windows受限执行环境的Node用户信息读取受限，以下命令通过正常宿主执行；浏览器使用独立临时context且finally关闭。

| 命令 | 结果 | 证据 |
|---|---|---|
| `npm run typecheck` | 退出0 | vue-tsc无错误 |
| `node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts` | 161 tests / 161 pass / 0 fail | output/image-inputs-20260923/tests.log |
| `npm run build` | built in 28.66s | output/image-inputs-20260923/build.log |
| `npm run build:demo` | built in 30.55s | output/image-inputs-20260923/build-demo.log |
| `node tests/image-inputs.browser.mjs` | passed:true，6组检查，pageErrors:[] | output/image-inputs-20260923/checks.json及截图 |
| `node tests/core-template-revision.browser.mjs` | PASS，3组检查 | output/core-ui-fixes-2026-09-22/template-revision-checks.json |
| `node tests/compact-upload.browser.mjs` | PASS | 追加、预览切图、移除最后图、拖拽无重复、14图展开收起与窄屏 |

浏览器配置：PLAYWRIGHT_MODULE指向宿主Playwright安装，API_UI_URL=http://127.0.0.1:3014/，DEMO_URL=http://127.0.0.1:3015/。本轮未新增依赖。单测顺序执行避免既有Demo定时状态测试在重负载并发时受影响。

## 浏览器覆盖和边界

正式API组件以浏览器拦截契约响应运行，所有/api/v1请求均拦截，不访问生产服务、不上传真实业务图片、不产生收费生成。验证真实组件调用独立API上传/清理、原图及素材URL、当前版本刷新、显式null历史输入、404重试恢复、JPG/PNG标注限制、满额拒绝与移除后重传、排序不重复上传。

Demo验证模板新建拖拽/Ctrl+V/粘贴按钮、配置加载、1440×900与1280×720居中固定底部，三类CLI创建拖拽/粘贴，CLI单张问题截图拖入/移除/粘贴及文字粘贴不误上传。共享SFC事件单测另覆盖权限拒绝、焦点隔离、禁用和卸载期间异步返回。既有浏览器用例覆盖点击选择与紧凑追加/收起。

这些证据不代表生产浏览器权限、钉钉容器剪贴板或线上真实上传已验收。未调用付费生成。剪贴板按钮受浏览器安全上下文/权限限制，拒绝时提供Ctrl+V或选择文件提示。

独立审查见IMAGE-INPUTS-REVIEW-20260923.md；最终批准快照由harness审查凭据记录。
