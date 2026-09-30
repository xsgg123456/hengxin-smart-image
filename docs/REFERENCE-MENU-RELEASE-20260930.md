# 多图参考与普通角色菜单生产发布 · 2026-09-30

用户授权提交、打包并部署最新已审功能。前端0.2.16，数据库保持0022。沿用现有api-edit发布工具，只更新已实查基线镜像api-edit-20260930-df0bc8d和目标版本。

步骤：审查发布适配及测试 → 提交中文Git → 正式构建与白名单隐私审计 → 上传校验及隔离镜像安装测试 → 停接纳、排空、备份和切换 → 线上健康、版本、文件哈希及只读菜单冒烟。

发布含多图参考v2和designer/operator仅API菜单。后端共享业务权限不变；不创建收费生成。发布脚本保留失败关闭接纳和回滚机制，不强停未知在途任务。

## 发布完成

2026-09-30 15:26（Asia/Shanghai）切换成功。生产版本0.2.16，发布api-edit-20260930-0784c97，源码提交0784c970f02b33b4fa6ea98290397e6cc1a20547。未推送远端。

- 正式构建31.66秒通过；依赖审计critical0/high67/moderate42/low5，与上次存量一致，本次未修改依赖。
- 发布专项25测试通过，独立审查Stage1/2通过。发布包813文件/4943583字节，SHA256 d43c48f1cd102e8676f7ac775548dc18715b33a8dcb62921acb22b888200f309；隐私扫描、归档回读和服务器传输哈希通过。
- 服务器无生产数据挂载、断网镜像安装测试1369 passed/78 skipped/1 deselected/15 warnings，177.72秒。条件跳过不计为已验证。
- 关闭接纳并排空后完成数据库、native和配置备份；schema保持0022，无迁移。完整Compose链保留，新五后端服务均匹配已测试镜像，每服务314文件哈希正确；native164、前端493文件匹配。ready依赖全部up，native active，API恢复接纳，capacity gate保持关闭。
- 公网首页及JS/CSS200且哈希匹配，匿名身份401；临时真实身份查询旧任务/图片与元数据尺寸一致。四角色公网浏览器均通过：设计/运营仅API菜单及旧任务地址回到新建换图；超管/主管完整菜单，多图修改显示三张真实参考图。pageerror为空，全部业务请求限制GET/HEAD/OPTIONS，未调用收费生成；临时会话撤销确认401。初次UI验收将可选标注占位卡计为图片导致数量断言失败，修正为实际img节点计数后通过，线上代码未变更。

备份目录：/opt/hengxin-backups/api-edit-20260930-0784c97。发布目录：/opt/hengxin-releases/api-edit-20260930-0784c97。后续Compose操作须沿运行labels完整链及本轮api-override.yaml。证据：output/release/api-edit-20260930-0784c97/（package-audit、build、installation-tests、deploy、verification、auth-smoke及四角色browser日志/截图）。
