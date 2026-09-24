# 轮次素材发布准备（2026-09-24）

版本：前端 0.2.6；发布标识 `materials-20260924-<commit前7位>`。

发布范围：前端素材追溯与画布交互优化；API、outbox、API 图像 worker、API 图像 outbox 更新同一完整后端镜像。数据库保持 0017，历史回填由操作员另行执行。

原生 worker 仅同步 execution 下 codex_runner.py、materials.py、material_backfill.py、material_bindings.py、material_capture.py、material_history.py、material_literals.py。保留现有模型、凭据、skill、超时和并发配置。其 app 模块依赖为既有配置、任务模型/attempts、文件模型、skills 校验器与 diagnostics。

完成标准：打包保留现有隐私白名单审计；旧 Compose 链包含当前 annotation overlay；停接并排空后备份。覆盖前保存每个原生文件的存在状态和内容；回退恢复既有文件、删除此次新增文件，任何恢复/健康验证失败都保持入口关闭。上线校验必须导入新素材采集模块；回退校验兼容旧版模块。

验证计划：Python/Shell 语法检查、既有 11 个恢复场景、真实临时目录下新增文件/原有文件回退及白名单拒绝测试。实际镜像安装和生产验收由主 Agent 另行执行。

本地验证结果：11 个恢复场景全部通过；6 个文件系统/清单测试通过，涵盖既有新增模块恢复、原本缺失模块删除、部分安装失败回退、备份失败无修改、非法路径/存在标志拒绝、七文件发布清单一致性。Python AST、Git Bash `bash -n` 与 `git diff --check` 均通过。未执行生产操作、未提交 Git、未登记审查批准。
