# 图需文件与北京时间验证 · 2026-10-14

## 范围与行为
- 两类资料不限扩展名，PPT/PPTX、旧DOC、无扩展名等均可上传；单份非空、20MiB及每类一份仍保留。
- 解析与上传状态分离：失败资料保留原件，可创建、补充、重提进入人工审核；PPT/PPTX未新增在线渲染或文本解析器，下载本地阅读。未知格式以octet-stream附件下载，鉴权/禁止缓存/nosniff保留。
- 时间统一北京时间，国内/海外任务、记录、资料、归档、成员申请和版本历史复用共享工具；UTC持久化不变，海外管理筛选传+08:00。

## 当场验证
- 前端 `pnpm test`：341 passed、0 failed（output/beijing-time-tests.log）。
- `pnpm typecheck`、`pnpm build`：exit 0；Vite built in 50.04s（output/material-time-build.log）。
- Windows后端专项：`pytest tests/test_overseas_materials.py tests/test_overseas_material_parsers.py tests/test_overseas_materials_faults.py tests/test_overseas_requirements.py -q`，59 passed、1 skipped；跳过Linux资源限制专用用例（output/material-time-backend.log）。
- `node tests/overseas-materials-faults.browser.mjs`：通过上传取消、网络/格式错误、解析失败仍可提交、重试、删除冲突、权限撤回及390px窄屏裁切验证（output/material-time-browser.log）。
- `node tests/material-time.browser.mjs`：America/Los_Angeles真实浏览器、隔离模拟接口；列表及审核页将用户原UTC样例精确显示2026-10-14 08:59:59，未解析PPTX上传后提交按钮可用，真实提交请求携带资料ID（output/material-time-smoke.log）。
- 截图已检查：output/material-time-upload.png、output/material-time-review.png。
- TZ=America/Los_Angeles/UTC各6项共享formatter及真实SFC用例通过。

## 边界
浏览器接口为隔离mock，后端API另由真实TestClient/临时数据库和内存对象存储测试；未连接生产、未调用付费模型、未部署、未提交Git。完整Linux回归及独立审查结果追加于下。

## 最终回归与审查修正
- 严格校验非法日期/时分秒，防止JS自动将2月30日归一成3月2日；闰年与范围测试通过。
- 最终 `pnpm test`：342 passed、0 failed（output/material-time-frontend-final.log）。
- 最终 `pnpm build`：exit 0，built in 38.38s（output/material-time-build-final.log），含vue-tsc。
- Linux隔离容器全量 `python -m pytest -q -p no:cacheprovider`：1996 passed、185 skipped、15 warnings，289.86s（output/material-time-backend-full.log）。容器无网络、完整仓库只读挂载，临时测试库；跳过的环境条件用例不计为已验证。首次因挂载缺infra收集失败已通过完整挂载修正。
- 修正后重新运行两份浏览器脚本均PASS。
- 旧 overseas-materials-real.browser.mjs 同步新格式/解析/预审合同及阅读选择器，本轮未启动其所需的完整身份多角色HTTP夹具，未宣称该脚本通过。
