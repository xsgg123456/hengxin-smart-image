# API 单张修改互斥模式 · 本地验收

范围：Product-Spec.md 文首“API 单张图片/文字修改互斥”、DEV-PLAN对应四步。正式功能代码已接入，尚未提交或部署；未执行收费模型生成。

- 后端新增image_edit独立模板/策略；text_edit升v2，text_repair不变。单一类型校验，服务端模板不可被客户端prompt覆盖。沿用1/2张编辑输入、源尺寸/PNG、冻结重试、旧快照与版本记录。存储类型无枚举约束，无需迁移。
- 前端真实RealRevisionDialog单选模式，按用户/任务/图片/基版本/模式隔离草稿与标注；模式切换清理可释放的已上传缓存。预览（含导出准备）、固定模板查看、上传、提交和未知确认期间锁定模式。未知请求恢复原类型、幂等键和冻结载荷。操作类型在DTO校验与历史标签中支持image_edit。
- 共享AnnotationEditor增加可选previewState事件；画布begin允许已有手柄从图片边界开始拖动，仍限制空白区域新建标注；不变更CLI输入和提示词。正式图片/文字模板逐字与后端一致，由契约测试覆盖。

## 已运行的验证

1. 后端执行者在backend目录运行 `.venv/Scripts/python.exe -m pytest tests/test_api_image_edit_modes.py tests/test_api_text_operations.py tests/test_api_image_versions.py -q`：42 passed；全量`pytest -q`：1350 passed、174 skipped、15 warnings（106秒）；`compileall -q app/modules/api_image_edits`通过。Windows/数据库等条件跳过不计为通过。
2. 前端`node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts`：209 passed、0 failed，原始日志output/image-edit-frontend-tests.log。首轮测试断言少了“任何”两字，按实际模板纠正断言后全量通过，不改变互斥要求。
3. `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`及`node node_modules/vite/bin/vite.js build`：两者退出0。日志output/image-edit-typecheck.log、output/image-edit-build.log；包含既有打包提示。
4. 真实生产Vue页面、现有组件和HTTP客户端的隔离浏览器脚本`frontend/tests/api-image-edit-modes.browser.mjs`：API_IMAGE_EDIT_MODES_BROWSER_PASS。校验默认空意见、固定模板、两套意见/框选/上传草稿、预览及上传锁、图片带标注真实HTTP载荷、网络响应丢失后刷新/重开确认原请求、文字请求不带图片标注，1920/1280/600视口可操作。证据output/image-edit-browser.log、output/playwright/api-image-edit-modes/checks.json及截图。

5. 既有annotation-workspace.browser.mjs全量通过：16组方图/长图、1920/1280/600/390、框选/画笔，仅API路径（CLI仅有fixture，不能算执行证据）。验证首笔/后笔、输入意见/侧栏滚动、缩放手柄、100%、滚轮锚点、空格/中键平移及取消。日志output/image-edit-annotation-regression.log，截图output/playwright/annotation-workspace。先前390布局挤压、平移提示遮挡及贴边手柄起点边界失败均已修复后重跑通过；不修改既有回归断言。

6. CLI专项隔离回归通过：output/image-edit-cli-regression.mjs抽取旧inline-annotation脚本的CLI段，实际导航tasks/index，验证历史V1、框选/画笔/平移、上传无意见拒绝、完整意见导出、网络未知后同key/body重试且只上传一次；日志output/image-edit-cli-regression.log及同名目录checks.json。旧inline完整脚本在API段因新增完整提示词导致pre定位不唯一而提前失败，未将其计为通过；本轮API载荷由新的模式脚本覆盖。

浏览器使用新建隔离context，全部业务API被本地fixture拦截，外部图标服务请求被阻断记录；未访问生产业务数据。图像为几何测试素材；这证明软件分流与冻结行为，不证明模型能百分百遵从文字/画面语义边界。图片和文字同时需要修改时仍按产品要求分两次操作。

开发核对参考：Vue官方组件事件文档 https://vuejs.org/guide/components/events ，Pydantic官方Literal类型文档 https://pydantic.dev/docs/validation/dev/api/pydantic/standard_library_types/ 。沿用现有依赖，无新包。
