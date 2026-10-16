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
已记录生产历史Turn、Upload、Material、Job、ArchiveAsset表内容摘要及7个persistent inputs文件（62,131,818字节）摘要；迁移及服务切换后逐项核对完全一致。

首次生产镜像安装测试：2457 passed、199 skipped、1 deselected、1 failed，失败为已有进程清理的/proc读取退出竞态（ProcessLookupError）。生产未进入prepare/deploy。新增确定性回归在修复前2 failed/3 passed，限定捕获已消失进程异常后，进程及任务清理专项19 passed；权限不足仍阻止清理，扫描不会漏掉后续存活同组进程。修复后重新审查、提交和发布包验证。

四项功能的独立code-reviewer两阶段PASS，功能快照`509b5598a547f5626bc9317d7a73cbf0b0c1ae3e71e3df263f1729848bfcb060`；报告在output/materials-archive-release/REVIEW.md。窄屏96px媒体规则做静态核查，本轮未做窄屏浏览器实测。

## 生产发布完成

- 功能提交`3c433dd`；安装测试发现的进程退出竞态修复提交`8f991b4`。最终发布为`overseas-20261016-8f991b4`，版本0.2.39。
- 增量独立审查Stage 1/2 PASS，最终代码快照`7e0cbc6180a5b97bb55d31c0de2fb7cdbaaa29bf6b1ff1b6ad75449c26a844d3`，报告`output/materials-archive-release/PROC-RACE-REVIEW.md`。其专项反证复现旧行为2 failed/3 passed，修复后19 passed。
- 最终发布包1360文件、5,678,718字节；SHA256 `4695b6f09596df985cddfddd4dd07b0f97503bd1f68773857768c88dab2ab47d`。隐私审计和归档哈希通过，预览页面不进入正式产物。
- 初次镜像源码检查发现db.py与发布包不一致，尚未部署即被门禁拦截。刷新构建上下文文件时间并使用既有no-cache选项后，628个后端文件哈希全部一致；未断言具体缓存内部根因。最终新提交同样重新构建和逐文件验证。
- 最终实际安装镜像：**2463 passed、199 skipped、1 deselected、15 warnings，524.91秒**；容量专项**4 passed，7.38秒**。条件跳过及既有deselect不计为通过。
- 最终镜像`sha256:c05feb5677766667da738d8a5b17bac1b15301476c32c4ebb2bfa24a89a10c74`；安装镜像、上传容量、原生执行环境及Skill验证通过。
- 发布关闭海外接纳，队列、unacked、未完成Job和删除任务均为0，稳定排空后停止执行器并备份。仅海外schema从0016新增列表可见状态表至0017，国内schema保持0029；海外API/原生服务/前端切换后恢复公共入口。
- `PHASE=complete`，`verification.json`确认sourceHashes、domesticIdentityUnchanged、skillsVerified均true；保留管理成功凭据已登记，pending=false。国内原生服务仍为domestic-20261015-4c64c1a，身份服务未变。
- 备份`/opt/hengxin-backups/overseas-20261016-8f991b4`已校验，并实际恢复至无网络、无宿主端口的临时PostgreSQL验证库。恢复schema为0016，5张历史表摘要与发布前一致；恢复使用no-owner/no-acl，仅验证数据和schema，未声称还原权限配置。临时容器已删除，生产数据库未执行恢复。
- 发布前后历史5表摘要完全一致；Codex inputs仍为7文件/62,131,818字节，聚合摘要`eab8a73a5a0b9a5612e163d6682cf2396ac966b490496eba0ceb12aa3407d1be`不变。原始附件未物理删除。

## 正式入口视觉与交互

在`https://zhitu.qhhengxin.top`真实登录页面验证：

- 成品库120px封面已显示完整首图和“共2张”；点击直接打开1/2原图，右箭头切到2/2场景图，键盘Left返回1/2。
- 查看成品详情，点击第二张直接进入2/2；Esc关闭原图后详情保留，焦点回到对应预览按钮。
- 原任务11条素材来源记录包含8份不同内容，生产右侧实际显示8项，紧凑缩略图和移除图标正常。原11条记录及历史消息保留。
- 点击素材移除入口，确认文案为“仅从任务素材列表移除，不影响历史消息和已发送文件。”随后取消，未移除生产真实素材。真实删除/恢复/引用发送行为的完整验证在隔离环境完成。
- 生产截图：`output/materials-archive-release/production-cover.png`、`production-next.png`、`production-materials.png`、`production-remove-confirm.png`；上线凭据、备份恢复和前后摘要同目录留存。
- 本轮未触发生产模型生成、未删除实际业务任务。已关闭本轮临时本地Vite服务和隔离PG/Redis/MinIO测试环境；此前供用户确认的独立预览服务保留。
