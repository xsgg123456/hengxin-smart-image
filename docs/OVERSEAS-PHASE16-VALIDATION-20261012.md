# 海外 Phase 16 验证记录

范围：配置入口、独立数据库迁移、同机资源隔离与就绪检查。正式身份授权、五角色、业务任务与 CLI 调度属于后续 Phase；本报告不将这些标为完成。

## 复用与变更

- 配置复用 `Settings` 校验，海外前缀环境无 `.env` 回退；国内入口拒绝海外上下文。
- 数据库复用 `app/db/session.py`，海外拥有独立 metadata、迁移树和版本表。双方迁移拒绝另一业务版本标记。
- 复用 `MinioStore`，只增加可注入 HTTP 客户端与禁止自动建桶的选项；一期默认行为保持不变。
- 独立 Compose 声明数据库、Redis、MinIO、执行目录卷；初始化/迁移/应用分离凭据。没有启动一期 Worker 冒充海外执行器。
- 本轮未修改前端代码；前端存在此前预览的未提交改动，回归结果单独记录。

## 当前证据

1. 配置、健康检查、存储复用和数据库池相关单测：`pytest -q tests/test_minio_policy_revalidation.py tests/test_delivery_storage.py tests/test_db_pool_budget.py tests/test_overseas_configuration.py tests/test_overseas_health.py`，**65 passed**。在隔离 Linux 测试容器运行，未访问生产。
2. 数据库专项：`pytest -q tests/test_overseas_database.py`，**12 passed**。使用本轮创建的 `hx-overseas-p16-regression-db`，随机数据库自动清理；包含国内完整迁移、海外重复迁移、双方错库拒绝与国内数据快照保持。
3. 前端：`pnpm typecheck` 退出0；`pnpm test` **250 passed / 0 failed**。日志 `output/overseas-phase16-frontend-tests.log`。仅是既有预览回归，不证明正式业务接入。
4. 镜像：在代码根目录执行 `docker build -t hengxin-smart-image-backend:overseas-phase16 -f infra/Dockerfile.backend .`，退出0。日志 `output/overseas-phase16-build.log`。随后在实际镜像执行 `python -m compileall -q app migrations`，退出0。
5. 完整后端回归：**1703 passed, 17 skipped, 15 warnings in 304.38s**，退出0，日志 `output/overseas-phase16-backend-final.log`；同时设置独立 `TEST_DATABASE_URL`、`API_IMAGE_TEST_DATABASE_URL`、`TEST_OVERSEAS_DATABASE_URL`。17项跳过未计作通过。首轮容器未加 `--init`，pytest为PID1触发一期监管器父进程消失保护，结果8失败/1695通过/17跳过；修正容器启动方式后监管器专项26通过/1跳过，无需修改一期监管器代码。最终全套使用 `docker run --rm --init`、独立Python缓存目录和 `pytest -q --disable-warnings -p no:cacheprovider`。
6. 真实 Compose 资源测试：`OVERSEAS_VERIFY_IMAGE=hengxin-smart-image-backend:overseas-phase16 python infra/overseas/verify_resources.py`，退出0，日志 `output/overseas-phase16-resources.log`。直接运行实际构建镜像：双向PG认证、MinIO GET/PUT、Redis凭据拒绝；应用DML成功而DDL和版本表写入拒绝；隐藏桶不可见、匿名拒绝；API非root、无管理/迁移凭据、仅挂自己的网络卷，UID10001可写三个目录；初始化和迁移重复成功；分别停止PG/Redis/MinIO得到ready503、live200，恢复后ready200。两栈临时资源均清理。国内为独立替身，不接一期实际服务。
7. 独立审查复跑专项：配置、健康、真实迁移、存储与连接池共 **77 passed**。Stage 1 / Stage 2 **PASS**；HIGH 0、MEDIUM 0，LOW 1为可选防护分支测试补强。审查快照 `2b819922af2b0630eee81560cbb10b047a297121abbc956f2395d6ea91f1cae8`，两阶段正式结论见 `docs/OVERSEAS-PHASE16-REVIEW-20261012.md`。
8. 前端既有预览浏览器回归：`node tests/overseas-preview.browser.mjs` 5组、`node tests/overseas-shell.browser.mjs` 4组、`node tests/overseas-management.browser.mjs` 5组全部通过，页面异常均为空。三份日志为 `output/overseas-phase16-browser-{preview,shell,management}.log`；预览仍使用模拟数据。

## 交付边界

没有部署生产、运行生产迁移、调用收费模型或启用清理。五角色与业务授权在 Phase 17–18 落地，海外 CLI 独立总并发限制将在 Phase 21 实测；当前配置上限5不能替代调度验收。同机资源共享宿主机故障域，生产配额、备份和真实身份认证在后续阶段验收。
