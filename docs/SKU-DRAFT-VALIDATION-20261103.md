# SKU 回填及个人草稿验收记录

当前阶段：已提交并完成生产 0.2.60 / overseas_0026 发布及正式页面验收。发布代码为 7cb3e0a；完整记录见同日生产文档。

## 功能与编译

- 前端全量 `pnpm test`：461 passed，0 failed/skip；日志 `output/sku-frontend-unit.log`。
- `pnpm typecheck`、正式 `pnpm exec vite build` 成功；最终构建耗时 1 分 43 秒，构建后审查快照保持一致。
- 最终正式 dist（127.0.0.1:3040）的隔离浏览器脚本 `frontend/tests/overseas-requirement-drafts.browser.mjs` 通过：单 SKU、多记录选择、迟到查询隔离、4 个后台附件加 2 个手动附件、去重、失败重试、保存失败与本地恢复、配额错误仍保存服务器、多账号/多标签隔离、窄屏、未知提交稳定请求键、审核 6 附件、成功清空。
- 独立首轮审查发现查询返回会中断同时启动的手动上传并残留 busy。修复为查询期间禁止附件选择/清空、应用来源前检查真实上传状态、面板卸载释放 busy；新增两个方向的延迟浏览器断言。原失败报告保留在 `output/sku-release/REVIEW.md`，不能作为通过凭据。

## 后端与安装态

- 新草稿/来源/租约/流式传输专项：39 passed、4 个 PostgreSQL 项仅在 Windows 未运行；它们已在以下 Linux/PostgreSQL 安装态执行。
- 第一轮候选镜像：18 模块、161 passed、0 skipped（123.33 秒），证据 `output/sku-release/candidate-tests.stdout`。
- 最新候选完整海外 93 模块：808 passed、3 failed、0 skipped（652.77 秒）。两处为新增 API 路径与历史请求体测试预期需同步，另一处为测试容器未挂载既有 Skill 预览 seed 文件。
- 更新两处测试及补挂精确只读 fixture 后，三个相关模块定向复验：41 passed、0 skipped（17.37 秒）。保留原失败日志，不声称首次全量全绿；证据 `candidate-full.stdout`、`supplement-tests.stdout`、`supplement-metadata.json`。
- 本机全后端非 integration 回归：2625 passed、375 skipped、41 deselected、10 failed。其中 8 个涉及 Windows 不支持的 Linux 安全文件打开能力；上述 2 处测试预期更新后本地专项 40 passed。Linux 结果验证受影响海外业务。
- 多附件提交/审核/历史重提及草稿提交专项另有 22 passed；数据库基础 9 passed。源码无生产数据写入测试。
- 发布工具 `python -m unittest discover -s scripts/release -p 'test_sku_*.py' -q`：58 passed、0 skipped。

## 真实上游

生产 API 实际 httpx 客户端与真实密钥只读验证：ASSK 当前 0 条；SP-XLLHBC01-BT 为 1 条/1 附件；H-ZGD000901-US-G 为 3 条/各 1 附件。旧演示数据不能代替当前响应。

新候选镜像实际 source/transfer 模块完成 SP-XLLHBC01-BT 流式下载：PPTX 988361 字节，SHA256 `49bcc8571ef7295b0a211ceae2fac45a033e9193d4b581813e63803facffc9b7`，ZIP 头与长度校验通过，耗时 1.31 秒。下载写入临时文件后由隔离 sink 校验，没有生产对象存储或数据库写入。证据 `output/sku-release/real-upstream-transfer.json`。

真实页面已验证该记录品牌、任务名、设计师回填，并提示无效平台 BELEEV 与缺失品名/语言；不猜测缺失值。本机网络导致查询偶发失败及附件地址校验拒绝，未放宽下载安全限制；生产网络的新模块真实下载通过。

## 依赖与边界

- 前端依赖未改变；`pnpm audit --prod --json` critical=0，high=39/moderate=38/low=5，与上一发布记录相同，不声称无依赖告警。
- 密钥仅从服务器环境读取；源码、前端产物扫描未发现用户提供的密钥。正式包仍需隐私审计。
- 最终已审提交的安装包必须再次跑安装测试；生产备份/迁移、后台线程和正式页面验收不能由以上候选测试替代。

最终正式包安装 164 passed、0 skipped；发布修复后 62 单测通过。生产 SKU 回填、异步附件导入/下载（哈希一致）、刷新及离开恢复、历史详情可读均实测通过。两业务 readiness=200，任务仍9条；保留1份验收草稿，未创建任务或触发生图。首次发布中止和恢复经过保留在生产记录，未将失败抹去。
