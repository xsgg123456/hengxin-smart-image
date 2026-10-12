# Phase 20 本地验收记录

## 交付范围

- 沿用海外独立身份/权限/数据库配置，复用一期 multipart、安全文件名、MinioStore、FileDelivery 与 OwnedStreamResponse。国内默认10MiB上限不变，海外显式20MiB。
- 新增 overseas_materials / overseas_material_versions 与冻结迁移 overseas_0005；原件、checksum、上传者、任务归属、解析版本和错误可追溯。
- 五种文档实际提取文字；旧DOC、扫描PDF、加密/损坏/超限内容明确拒绝。资料作为文本数据，前端无HTML执行，后端不计算宏/公式或访问链接。
- 原件私有访问、解析失败重试、未绑定删除墓碑及物理删除重试；绑定后不可重试/删除。权限变更、改派后下一请求重验任务范围。
- 至少一份成功资料才能完整提交。POSTtasks兼容Phase19无资料保存及既有幂等哈希；带资料创建和补交分别原子绑定/事件/outbox，不创建CLI作业。正式状态submitted为“图需已提交”。
- 复用既有表单、上传、资料预览与Art布局，增加实际上传进度、错误/重试/确认删除和原件操作。

## 已执行证据

- `python infra/identity-test/run.py --phase20 --serve --origin http://127.0.0.1:3015`：Phase17/18/19/20全部真实HTTP检查PASS，原始日志 `output/phase20-http.log`。独立PG双库、Redis、双MinIO；只有钉钉provider是测试替身。验证真实CSV字节/解析、坏PDF失败和重试版本、20MiB/空文件/类型、所有权、冻结资料、补交、幂等、改派后旧设计拒绝、国内ID接口拒绝、国内全表及对象未变化。
- `OVERSEAS_VERIFY_IMAGE=hengxin-smart-image-backend:phase20 python infra/overseas/verify_resources.py`：双向PG/Redis/MinIO凭据隔离、最小权限、私有桶、匿名拒绝、独立挂载、0005重复迁移及依赖故障恢复PASS；临时资源已清理。日志 `output/phase20-resources.log`。
- Linux解析28项通过；含真实PDF/DOCX/XLS/XLSX/CSV、XML实体/ZIP炸弹、乱码/空内容/超限、15秒进程超时回收及600MiB申请被512MiB地址空间限制拒绝。
- 实际PG资料/任务71项、故障9项、迁移14项专项通过。绑定/删除/重试/重复绑定竞争、未知提交保留原件、上传中撤权、事务回滚及0004→0005保留任务数据有对应测试。
- 前端最终 `pnpm test` 270 passed；`pnpm build` 类型检查和正式构建通过，预览构建通过。日志 `output/phase20-frontend-tests-final.log`、`output/phase20-frontend-build-final.log`、`output/phase20-preview-build.log`。
- 既有独立预览的流程5项、管理5项、Shell4项全部PASS，零业务API请求/页面异常，未将模拟数据接入正式页面。日志 `output/phase20-preview-*.log`。

最终完整后端回归 `python -m pytest -q -p no:cacheprovider`：**1926 passed、17既有宿主条件跳过**，268.21秒，日志 `output/phase20-backend-final.log`。复验已覆盖首轮3处旧断言更新（补交能力、路由白名单、迁移数量）；数据库/Redis专项使用临时专用容器，不访问原有服务。

最终真实HTTP再次PASS（`output/phase20-http-final.log`），额外验证真实DOCX+CSV双资料、国内真实上传ID不能在海外读取或绑定；环境自动清理。最终真实资料浏览器、故障浏览器与Phase18成员回归分别见 `output/phase20-materials-real-final.log`、`output/phase20-materials-faults-final.log`、`output/phase20-members-faults-final.log`，全部PASS。

PDF原件通过鉴权后在独立原生PDF查看窗口展示；opener为空，切页/关闭预览/离开组件释放URL并关闭窗口，弹窗拦截有提示及下载替代。完整Chromium新headless实测PDF正文实际可见，1页加载完成；主Agent目视 `output/playwright/phase20/pdf-preview.png` 确认。390px关闭侧栏后检查文字/按钮祖先裁切并截图 `materials-real-mobile.png`。

生成声明恢复到既有完整HEAD后，`pnpm typecheck`再次退出0（`output/phase20-typecheck-final.log`）。以HEAD导出再仅覆盖12个正式前端候选文件，使用HEAD的package/locales及既有依赖，在独立目录执行 `pnpm build` 再次通过（34.59秒，`output/phase20-clean-build.log`），确认无需未提交预览依赖。该目录 `output/phase20-clean-8367bd406fb144e997f19de6b2594789` 清理命令经路径和junction核验后仍被自动审批以 `blocked by policy` 拒绝，未尝试绕过，保留Git忽略目录及证据。

## 边界与后继

本阶段未部署、未推送、未执行收费模型；正式AI分析仍在Phase21/22后续接入。不支持OCR和旧DOC，提示用户转文字PDF/DOCX。未绑定中断上传的保留/清理策略遵循后续维护阶段，当前不自动删除。既存未提交预览入口、package/locales/技能修改不混入本次提交。

独立 code-reviewer 两阶段均PASS，快照 `6da26831e9068bf6fdfa1d4930cff787ee8ac49899453b82c33dbcd1b4782f50`；审查者独立复跑Linux40项与3条浏览器套件通过，详见 [审查报告](reviews/OVERSEAS-PHASE20-REVIEW-20261012.md)。

收尾：本轮隔离HTTP/MinIO/PG/Redis容器与网络均已清理，3015测试服务已关闭；原有3012预览和hx-management-pg-test保留。自动审批拒绝的临时clean构建目录保留，不进入Git。
