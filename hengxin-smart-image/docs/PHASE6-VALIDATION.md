# Phase 6 验证记录

2026-09-09；范围：真实原图上传/预览/下载、稳定用户归属、开发身份及共用逻辑删除审计。真实钉钉、模板/Skill、任务执行和回收清理仍属后续阶段。

## 当场执行证据

- `docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml build api`：exit 0，Python Linux镜像固定依赖；新增Pillow12.3.0，uv.lock共56项记录。本轮没有升级既有依赖。
- `python hengxin-smart-image/infra/verify_phase6.py`：exit 0。真实PG/MinIO、重复迁移、文件原字节及元数据/所有者、私有bucket匿名403、空/坏/截断/超限拒绝、API/PG/MinIO重启保留、跨用户共享、停用/待授权/匿名拒绝、MinIO停机503与恢复重试全部PASS。容器内pytest：`56 passed, 2 warnings in 3.08s`，无skip；Python compileall通过。最终输出`PHASE6 INTEGRATION PASS (isolated volumes)`。
- 同一脚本启动独立HTTP前端和Playwright会话，`scripts/phase6/files-flow.js`返回`PHASE6 BROWSER PASS`：三入口真实上传、首传503后重试保留名称/意见、预览与原图下载、刷新后按fileId读回、20张边界、URL角色伪造无效、无workspace启动依赖、pageerror=0。JPEG结束标记后附加NUL的真实图片上传下载后，文件bytes与原fixture完全一致。1024px宽度无横向溢出。
- `python hengxin-smart-image/infra/verify_phase5.py`：exit 0，`PHASE5 INTEGRATION PASS`；API/outbox重启不丢受理、真实Celery执行、重复投递单次完成、Redis停机恢复、Worker SIGKILL回滚重试全部PASS。容器pytest `56 passed, 2 warnings in 11.27s`。
- 前端目录 `npx --yes pnpm@10.33.4 test`：38 tests / 38 pass / 0 fail / 0 skip，1640.1206ms。`npx --yes pnpm@10.33.4 build`：exit 0，vue-tsc零错误、Vite `built in 44.16s`。既有分包提示保留。
- 现有模拟前端Playwright回归：`scripts/phase3/create-flow.js`三入口创建/SKU/整套返工PASS；`scripts/phase3/version-flow.js`单张失败保留/原位置重试/其余7槽不变/历史下载/ZIP/归档幂等/删除确认PASS；两者pageerror=0。

原始日志在仓库`output/playwright/phase6-integration.log`、`phase6-queue-regression.log`、`phase6-frontend-test.log`、`phase6-frontend-build.log`。截图`phase6-real-upload.png`、`phase6-narrow-upload.png`及review邻居模板页对照。输出目录被Git忽略，长期结论以本文及审查报告为准。

## 审查修复与回归

1. 初审发现匿名12MiB上传先写完整临时文件后401。修为身份依赖先执行再解析multipart，实际接收上限10MiB+64KiB封装开销，单文件自身严格10MiB。入口回归证明匿名/声明超限写盘0，未提供或伪造Content-Length的分块流提前停止并关闭临时文件；单请求只接受一个file。
2. 复审发现合法JPEG尾部附加字节会被前端误拒绝下载。修正文件类型识别，不裁剪原字节；真实Pillow fixture同时覆盖单测及浏览器实际下载。
3. 测试修正：生产历史开发身份用例显式关闭测试队列开关，避免Phase5测试环境的ENABLE_TEST_JOBS=true干扰待测身份路径。完整Phase5/6容器回归均通过。

第三轮fresh独立审查：Stage 1 PASS、Stage 2 PASS，剩余HIGH/MEDIUM为0；报告见PHASE6-REVIEW.md。四步验证已通过，交用户验收；后续业务接口仍501，不计作本阶段完成。

## 隔离与保留边界

集成测试使用随机hx-phase5-test-/hx-phase6-test- Compose项目、独立3个命名卷、随机端口和凭据；未写开发数据库。结束删除对应测试容器/卷，关闭独立浏览器和临时前端进程。开发环境单独升级迁移并显式ENABLE_DEV_IDENTITY=true，服务监听localhost；默认配置及生产仍禁用开发身份。

上传先留下staging元数据，失败补偿或保留failed/staging以便后续核对；非ready文件不公开。自动回收尚未开启。刷新后服务器文件可按fileId读取，但当前表单选择不作为持久草稿恢复；移除只取消表单选择。原图不缩放、大小校验与服务端完整解码均执行。

2个警告来自Starlette/httpx与anyio弃用提示，不是失败。当前没有真实钉钉认证、模板/Skill业务接口或AI生成验收。

## 本地验收入口

真实前端已启动`http://127.0.0.1:3008/#/image-processing/text`，API8008；同源`/api/v1/auth/me`返回稳定ID、operator角色、本地联调用户。GET `/api/v1/health/ready`：200，PG/Redis/MinIO均up。这里的身份来自服务端本地配置，尚不是钉钉登录。实际本地环境与前述测试卷分离；本轮测试未向开发库写入测试图片。

可以上传、预览及下载素材；顶部关于后续接口的提示来自尚未实现的Skill/模板接口，生成按钮保持禁用。Phase6用户验收后下一步Phase7模板与Skill版本管理。
