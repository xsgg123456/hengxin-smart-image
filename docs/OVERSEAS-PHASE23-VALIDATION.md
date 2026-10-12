# Phase23 本地验收记录

本阶段实现按SKU生图、私有图片与不可变历史版本、原图标注返工、逐图审批、全部通过后整套归档以及授权ZIP下载。海外迁移0008，国内仍0027。本地验收完成。

## 已运行证据

- 真实三API、两库、Redis、两个MinIO隔离拓扑：`IDENTITY_TEST_IMAGE=hengxin-smart-image-backend:phase20 python infra/identity-test/run.py --phase23`，Phase17–23全部通过。新增覆盖一个SKU成功/另一SKU失败、重复重试仅新增一个作业、原件字节和鉴权、只返工B且保留A审核、B的旧蓝图与新绿图历史、旧版拒绝、全部通过后幂等归档、ZIP仅包含冻结红/绿图片、陌生设计与无业务角色管理员拒绝。国内数据库快照及全部对象etag不变。`output/phase23-http.log`。
- 真实API浏览器：`tests/overseas-pictures-real.browser.mjs`，设计/运营查看真实图片及历史，归档后只读，品名品牌SKU过滤与实际ZIP下载，窄屏无横向溢出、无页面错误；没有route mocks。截图`output/playwright/phase23/real-*.png`与`archive-mobile-*.png`，主Agent已查看移动成品库截图。
- CLI使用离线可执行文件，真实进程启动、退出、事件解析和交付发布；图片为32×32红/蓝/绿fixture。验证流程与字节隔离，不代表收费模型图像质量或真实Codex生图能力验收。
- 前端最终278单测、typecheck及生产构建通过（35.73s）；mock浏览器覆盖审核/返工意见确认、409保留、断网冻结正文和幂等键、失败SKU重试、归档门槛、检索分页空错、撤权及窄屏初载。修复窄屏初次加载侧栏未关闭、JPEG/WEBP下载后缀问题。日志`output/phase23-frontend-{test,build}.log`。
- 后端24项HTTP/协议/PG竞争专项通过，前轮含0008迁移回填组合27项通过；审查另发现原图改名复制仍可发布返工版本。独立Linux复现确认，新增回归测试先红（1失败/16通过），随后在对象存储前增加冻结原图checksum拒绝；修后20项相关测试通过，独立reviewer协议17项通过。
- 首次全量2011通过、17项既有宿主条件跳过、2失败。0008离线回填误用在线inspect已补等价PG SQL，并实际运行回填两次验证槽位；旧计时测试并发使用单一SQLite连接，改独立临时文件数据库连接，保持并发计数断言。专项18通过，新增PG回填测试补fixture导入后1通过。连接语义依据[SQLAlchemy官方文档](https://docs.sqlalchemy.org/en/21/dialects/sqlite.html)。完整重跑最终2016通过、17既有宿主条件跳过、15警告（315.76s），日志`output/phase23-backend-rerun.log`。跳过项不计通过。
- 修复后真实Phase17–23 HTTP/私有存储/子进程全流程再次通过，日志`output/phase23-http-final.log`；原始失败与修复日志均保留，不把首轮失败写成通过。

## 边界

原有专用预览文件与用户改动保留；正式图片、标注、归档组件复用布局及共享AnnotationCanvas，不导入模拟adapter。单图10MiB，SKU交付总256MiB，归档原件总1GiB，ZIP使用有界临时流。原件与正式产物不自动清理，临时测试环境仅清理本次随机命名资源。

独立审查`docs/reviews/OVERSEAS-PHASE23-REVIEW.md` Stage1/Stage2均PASS；最终快照`2475f62359e31fbad2d390a9ec45a0c98142f171853db46325d8b7d7d5e00040`。真实联调临时资源已清理，保留既有服务及用户预览。
