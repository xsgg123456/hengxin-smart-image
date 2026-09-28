# 单图文字替换 · 2026-09-28 实现与验证

后续发布状态：用户另行授权提交和部署后，0.2.11/schema0020 已上线，详见 `TEXT-EDIT-RELEASE-20260928.md`。下文保留本地开发阶段的测试范围与证据，真实生成效果仍未验收。

## 范围

新建文字任务仅一张原图，修改意见必填，标注可选。直接复用 AnnotationEditor/AnnotationCanvas 与既有标注导出、草稿和幂等提交。服务端不再查文字 Skill，新增不可变内置提示词快照，首轮、重试与返工使用该任务的快照；历史 Skill 任务保留旧语义。新增迁移 0020 放宽任务 Skill 外键空值并添加 builtin_prompt，未修改生产数据库。

本轮不包含生产部署、Git 提交、收费生成或逐像素合成。用户示例“防窥钢化膜→张帅钢化膜”用于界面与请求验收，未生成真实修改图片，不声明模型效果或字体还原已通过。

## 自动化验证

- 后端：`.venv/Scripts/python.exe -m pytest -q --tb=short`，最终 `1354 passed, 113 skipped, 15 warnings in 160.93s`。日志 `output/text-backend-verified.txt`（仓库根目录下，忽略文件）。TEST_DATABASE_URL/API_IMAGE_TEST_DATABASE_URL 指向独立临时 PostgreSQL 16 容器的 hx_text_test 库，不访问生产。113 项未满足各自 opt-in 环境条件，未计为通过。
- 前端：`pnpm test`，`197 passed, 0 failed`；`pnpm build`（包含 vue-tsc），exit 0，`built in 29.29s`。日志 `frontend/text-task-tests.log`、`frontend/text-task-build.log`。
- Python app/migrations compileall 与 `git diff --check` 通过；Git 有现有 CRLF/LF 提示，无 whitespace error。
- 新增后端用例验证无任何 Skill 时受理、意见/单图限制、辅助图资格/所有者/大小/类型、冻结提示词不随新部署漂移、首轮与同会话返工编排及结果版本、已知启动前失败的重试保留标注、SQLite/PostgreSQL 增量迁移保留旧记录及 FK。CLI 子进程与对象 IO 使用测试替身，结果编排和路由/持久化实际执行。
- 历史 CLI 测试辅助函数显式构造旧 Skill 任务（包括旧多图文字任务），继续验证历史执行，不将这些记录当新 API 准入行为。Skill 最新快照测试改用仍需 Skill 的商品任务及模板。
- 全量 opt-in 测试首次发现 API PostgreSQL fixture 漏建现有 image_variants 表；补齐测试表集合后通过。另一次测试库命名未满足旧队列测试要求的 `_test` 后缀，改为独立 hx_text_test 后重跑。未放宽测试保护或更改 API 业务逻辑。
- 迁移使用项目现有 Alembic；批处理在 PostgreSQL 发出 ALTER，在 SQLite 按批处理迁移，已按[官方批处理文档](https://alembic.sqlalchemy.org/en/latest/batch.html)核对，并用两种数据库实跑。

## 浏览器实际操作

Playwright CLI 独立会话，真实前端 development 模式连接临时 SQLite + MemoryStore 的实际 FastAPI 路由，登录身份为隔离测试用户。没有连接生产或执行后台模型。测试启动脚本 `output/text-browser-api.py` 使用 TemporaryDirectory，退出销毁临时库。

1. 上传用户示例 PNG，画布显示原始尺寸 496×749；未画标注且未填意见时阻止预览，填入“将防窥钢化膜改成张帅钢化膜，保留28°及其他内容”后确认，POST /tasks 返回 202，进入真实任务详情，无 Skill 绑定错误。
2. 新建另一任务，框选标题，填写编号 1 意见，预览显示编号定位图。确认后先上传标注图，任务 POST 返回 202；请求只有一个 sources 原图及单独 annotationFileId，没有模板或 Skill 字段，任务详情仍一个输出位置。截图 `output/text-annotation-preview.png`。
3. 画笔绘制、撤销、100% 缩放、拖动手柄平移、移除原图实操通过；移除后画布消失。首次坐标绘制因画布不在视区未命中，使用 scrollIntoViewIfNeeded 后复验通过，不计作产品缺陷。
4. 窄屏 768×900：意见框实际 x46、y691.6、宽664、高73，页面 scrollWidth=768；意见区沿用既有内部滚动，未见横向挤出，原图加载正常。截图 `output/text-narrow.png`；full-page 截图的固定顶栏位置对应截图时滚动位置。
5. 模拟首次提交返回503后，名称等输入锁定；点击“确认上次提交”使用完全相同请求内容与 Idempotency-Key，到实际测试 API 返回202。返回值验证 `unknownLocksInputs=true, sameKey=true, sameBody=true`。控制台此条503为主动注入的预期故障。
6. 单独 mock 模式打开已有壁纸任务的“修改这张”，原 CLI 单图画布、意见区、版本标签与工具正常显示。截图 `output/text-cli-neighbor.png`，与新页面实际对照；共用画布代码未复制，原入口默认文案保持不变。

## 审查与交付状态

独立两阶段报告见 `TEXT-EDIT-20260928-REVIEW.md`：Stage 1/2 均 PASS，独立专项 28 passed，独立浏览器无标注实际受理 202、列表/详情 200，并对照 CLI 邻居。已登记批准快照 `ef78a2638abcce9111b9c4ecac6319430c49c72d92a22256c9b644e5cb1bc142`。本文件不代替审查凭据。部署与真实生成质量验收仍单独执行。
