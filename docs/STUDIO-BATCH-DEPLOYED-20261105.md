# 海外批量画布 0.2.64 部署记录

功能提交：`68afe2a1fe3c5648779a00bf36ae8a01a32a0f71`。独立审查两阶段PASS，批准快照 `6b97aef93e64853191bd2afab7fe8679667e3500f24309d6b35a29cfe13ec387`。

正式入口：<https://zhitu.qhhengxin.top/?release=0.2.64#/overseas/tasks/d456700c-c888-4825-b9a5-4a5abd82bbfb>。版本查询参数用于让旧浏览器缓存重新获取入口。

## 发布结果

- 从固定提交隔离安装并生产构建，Vite 38.96秒完成；发布包5,156,101字节，隐私审计PASS。SHA256：`d7d175cf888b0b8d9fe077e63c30fbc10058a48ade2dee21471a7850f10ef500`。
- 实际候选镜像从安装路径以实际UID运行，独立PostgreSQL测试 **106 passed、0 failed、0 skipped**，102.72秒。
- 在途任务和导入排空，正常停止API/native；数据库0026备份在独立PostgreSQL恢复验证，无迁移、无生产回灌。
- native按真实服务身份验证新提示词绑定与旧payload兼容，API仅切换镜像。新镜像：`sha256:30681c68650019ee8b4f5e6c3c30fe810a47f4a7de540273f03cae02eb90c943`。
- 前端0.2.64已安装；入口和JS/CSS线上原始字节与包校验一致，`RESUMED`已记录。海外与国内ready均HTTP200。
- `INSTALL_TESTS_PASSED`、`backup/COMPLETE`、`NATIVE_INSTALLED`、`NATIVE_VERIFIED`、`API_VERIFIED`、`frontend-backup/INSTALLED.json`均存在且发布运行器校验通过。

发布及恢复目录：`/opt/hengxin-studio-batch-studio-batch-20261105-68afe2a/work`。本地证据为Git忽略的 `output/batch-annotation-preview/deploy-*.log`、`deployment-receipt.json`；包审计在 `output/release/studio-batch-20261105-68afe2a/`。

## 共享SVG的换行对齐

首次前端切换在任何前端写入前，因13个公共SVG原始字节碰撞被拒绝。逐个比对确认旧CRLF变新LF后完全相同：`favicon.svg`及`samples/{product,text,wallpaper}-{0,1,2,3}.svg`。原因是旧工作区复制的静态文件与固定Git导出构建的换行不同。

一次性对齐操作经独立两阶段审查（见 `STUDIO-BATCH-STATIC-RECONCILIATION-REVIEW-20261105.md`），严格限制完整碰撞集合和内容等价；确认均0644、UID/GID 0/0，无特殊权限位。以非优化Python运行，全部原字节与校验和先备份，再原子替换，保留所有者和权限。没有修改发布包、manifest或放松发布校验；随后原frontend全量门禁及resume均通过。

原文件和收据保存于发布目录 `work/public-svg-newlines/`，操作脚本同时留在该私有目录；脚本SHA256 `e9ffd8be2b13c8c66cf58e4a935c1afeb464d631590a9e683d76da259185f769`。如需回到精确旧字节，先核验收据的old/new哈希，再从此备份原子恢复对应文件；不得覆盖后来发生实质变更的资源。

## 正式浏览器验收与限制

已从正式入口登录并打开用户现有任务，核对实际7/6/2/1张分组，目标六张A+图片的“批量标注”弹窗成功打开。标题、工具、逐张标注提示、仅已标注图片带回、参考图入口及零张时禁用确认均可见。新入口脚本为 `/assets/index-VvkpgXmW.js`；原无查询参数的旧浏览器缓存曾加载旧脚本，带版本入口已加载新按钮。

**线上视觉与参考图选择验收未全部完成。** 扩展选择本地文件因缺少文件URL访问权限失败；尝试用系统文件选择器时，电脑操作工具因无法可靠确认Windows当前浏览器URL而中止本轮电脑操作。此后没有继续操控浏览器、修改扩展权限或换工具绕过限制。未取得正式六张图片全部加载后的最终截图，也未完成线上参考图用途输入/窄屏验收，不能把DOM可见当作完整视觉通过。

对应功能已在正式Vue组件的隔离浏览器中完成26项检查及1920/1440/390截图目视，前端527项回归、类型检查、生产构建通过；后端Linux/PG127项通过，详见 `STUDIO-BATCH-VALIDATION-20261105.md`。全后端原有9项基线失败和既有依赖审计限制仍保留在该记录中。本轮没有发送真实改图请求或触发付费生成。
