# 素材整理与成品浏览 0.2.39 验收

## 范围与实现

用户批准独立预览后授权四项正式开发、测试、中文 Git 提交和生产部署。

- 素材移除只写任务+SHA256可见性状态；源 Material/Upload、对象存储、历史 Turn、Job冻结载荷和Codex持久输入均保留。
- 任务内按内容去重；改名同内容合并，同名不同内容不合并；显式重新上传恢复显示，普通历史引用和新会话不恢复。
- 成品卡片120px封面（窄屏96px），原图完整等比缩放；封面和详情共用同套原图查看器。
- 点击目标索引、上一张/下一张、键盘、计数、缩放旋转、切图复位、Esc返回；单图不显示切图箭头。

## 已完成的本地验证

- 前端全量：387 passed，typecheck及正式生产构建通过。
- Linux后端全量：2566 passed，200 skipped，0 failures/errors。
- 发布工具全量：617 passed、1 skipped、237 subtests passed。
- 真实PostgreSQL专项：17 passed，包括同内容并发上传、隐藏/上传两种锁顺序、0016存量升级0017、旧表和国内数据库快照保持。
- 真实PG/Redis/MinIO/HTTP隔离链路Phase17–21通过；未运行模型或CLI出图。
- 真实浏览器：引用broken.pdf、输入草稿、点击右侧移除并确认，右侧计数降为0，输入和已选附件保留；点击发送成功形成历史消息，随后停止隔离队列任务。
- 真实HTTP：移除后的历史附件字节仍可下载；重新上传原件返回restored；PNG改名同内容返回existing且列表一条；同名异内容另存一条；再次隐藏后旧上传URL仍可读，再传恢复一条。
- 真实浏览器：成品封面直接1/2，下一张2/2且末端禁用；键盘Left回1/2；缩放1.2/旋转90°后切图复位为1/0°；详情第二图打开2/2，Esc保留详情并恢复焦点。
- 单图验收使用隔离数据库中单独建立的归档快照，task_id为空，模拟原任务已删除；真实对象存储图片可预览1/1，prev/next节点为0。不将此视为生产删除操作测试。
- 当前依赖审计：critical=0；既有high=36、moderate=34、low=1，本轮未修改依赖。

原始日志及截图：`output/materials-archive-release/`，包含frontend-tests.log、frontend-build.log、release-tests.log、postgres-tests.log、real-http.json、material-removed.png、archive-cover.png、archive-next.png、archive-single.png。输出目录不打进发布包。

## 失败与修正记录

首轮环境hx-management-test缺文档解析依赖且两个测试模块同名，未完成收集；改用已有完整依赖测试镜像并调整新发布测试文件名。
随后混合Linux全量：3178 passed，201 skipped，5 failed。1项接口清单漏新素材移除路由，补齐契约；4项发布测试因容器无git失败，已在具备git的宿主完整复跑通过。最终Linux后端全量：**2566 passed，200 skipped，15 warnings，308.13秒**；无失败或错误。200项条件跳过不宣称已验证；新增PG并发和迁移在单独17项真实PG测试中通过。

## 发布保护与状态

已只读确认生产基线0.2.38 / overseas-20261016-106d07d，国内schema0029、海外0016，国内native固定domestic-20261015-4c64c1a。
新发布器复用现有全拓扑、镜像安装验证、容量验证、关闭海外接纳、排空、完整备份校验与失败保持关闭机制；0017仅新增列表状态表。
已记录生产历史Turn、Upload、Material、Job、ArchiveAsset表内容摘要及7个persistent inputs文件（62,131,818字节）摘要，发布后将核对。

此记录目前为发布前验收，生产部署结果在完成后补录。

首次生产镜像安装测试：2457 passed、199 skipped、1 deselected、1 failed，失败为已有进程清理的/proc读取退出竞态（ProcessLookupError）。生产未进入prepare/deploy。新增确定性回归在修复前2 failed/3 passed，限定捕获已消失进程异常后，进程及任务清理专项19 passed；权限不足仍阻止清理，扫描不会漏掉后续存活同组进程。修复后重新审查、提交和发布包验证。

独立code-reviewer两阶段PASS，最终快照`509b5598a547f5626bc9317d7a73cbf0b0c1ae3e71e3df263f1729848bfcb060`；报告在output/materials-archive-release/REVIEW.md。窄屏96px媒体规则做静态核查，本轮未做窄屏浏览器实测。
