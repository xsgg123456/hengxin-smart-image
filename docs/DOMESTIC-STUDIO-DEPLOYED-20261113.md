# 国内 AI 工作台生产部署验收 · 2026-11-13

已部署至 `hengxin-ai-245`，正式入口为 http://192.168.1.245:8080/domestic/ 。五工作台、独立成品库、超管 Skills 管理已接入真实系统。初始绑定按用户要求全部留空。

## 版本与发布凭据

- 功能提交：`ddb23175a46e6f886332a736fc951adc7c711bc5`。
- 实际运行应用：`2bc8acc7ecf412626a6a635a9413b1644b55417e`，包括原生账号服务标准库依赖修复；国内、海外、共享三组的 backend_commit/frontend_commit 均一致。
- 发布工具提交：`6c7b6af6bca4e7a1cc6f3ce57345bc786e3ae77b`，修正 Docker CHOWN/CAP_CHOWN 等价名称核验。工具安装在 `/opt/hengxin-intranet-tools/releases/290f3a7a25e263cb`，current 已指向该版本；该提交没有应用源码变更，无需重建应用。
- 事务：`/var/lib/hengxin-release/intranet-transactions/domestic-studio-1794543549803218345`，最终 phase=complete、pending=null、migration_pending=false。
- 国内 schema 从 0032 迁移到 0043，海外仍为 overseas_0026。两个发布标记均为 open、root:root、0644；没有手工写标记放行。
- `/`、`/domestic/`、`/overseas/`、`/shared/`、国内和海外 ready、身份 config 七项 HTTP 均为 200。最终 release verify 检查实际源码、数据身份、配置和三组版本通过。

## 验证证据

完整实现由 [R14](reviews/DOMESTIC-STUDIO-FINAL-R14-20261113.md) 两阶段通过；原生导入和 capability 两个最小增量分别由 [原生导入审查](reviews/DOMESTIC-STUDIO-NATIVE-IMPORT-20261113.md)、[权限名称审查](reviews/DOMESTIC-STUDIO-CAPABILITY-20261113.md) 两阶段通过，并按对应 candidate 登记批准后提交。

- R14 独立发布测试 401 passed、9 subtests passed；后端两组 76/37 passed，前端 564 passed，类型检查、国内/海外构建、六宽度视觉和五入口交互通过。跳过补测与替身边界见原报告。
- 三个实际发布包均从应用 Git 提交构建，逐文件清单、scope/commit、SHA256 和隐私检查通过；没有直接打包工作区。
- 最终安装路径工具测试 396 passed、9 subtests passed、5 项环境条件跳过；隔离 PostgreSQL/UID 迁移的完整验证在本地 401 项套件完成，不把安装跳过算成通过。实际内网 Docker 的网络隔离、后台等待、请求封控与资源保留 smoke 全部通过，测试资源剩余 0。
- 国内 publisher 以实际镜像、只读根目录、无网络测试容器验证 API UID 可以访问 socket、其它 UID 被拒绝。最终权限核验器从新工具安装路径执行 20 项测试全通过后，才执行既有前向恢复和完整 verify。
- 正式 Chrome 登录态从真实菜单逐一打开五工作台：布局、样式、空白对话及无预填内容正常；五页均显示未配置并禁用发送。新品有归档入口，三个替换页无归档入口。相机入口的教程弹层实际打开，显示对应标题和“教程待补充”。
- 正式成品库为独立一级菜单，空库显示 0 套；管理中心 Skills 管理显示空目录和文件夹上传入口，工作台绑定页五项均“未绑定/未配置”，数据库只读计数为 0。浏览器错误日志为空。

原始证据保存于本地 `output/domestic-studio-packages-2bc8acc7ecf4/`、`output/domestic-studio-packages-6c7b6af6bca4/forward-recovery.log` 和 `output/domestic-studio-production-after.json`；不提交可能包含部署环境信息的原始运行目录。

## 发布中问题及收敛

首次 prepare 在停止服务、数据库迁移之前发现系统 Python 的账号服务误引入 starlette；通过既有 recover 取消该准备事务，修复导入位置并重建后全部原生导入和两侧 runtime_check 通过。

第二次候选完成备份和迁移后，开放前核验因 Docker 返回 CAP_CHOWN 而保守拒绝。真实权限未扩大，入口保持封控；工具修复只接受 CHOWN 或 CAP_CHOWN 的精确单项集合，额外能力仍拒绝。新版工具经审查、提交和安装测试后，通过原有 recover 完成同一应用事务，未回退数据库、未修改冻结候选清单或绕过核验。恢复后使用验证过的台账推导 21 服务清单，切换 current 工具时服务身份保持不变。

## 验收边界

真实 Skill、教程内容由用户后续上传配置；当前未调用真实模型生成图片，不能把未绑定时的页面验收称为模型效果验收。会话 CRUD、跨成员权限、归档独立副本、删除与 ZIP 等已在隔离环境测试；本次正式浏览器检查没有制造或删除生产业务资料。
