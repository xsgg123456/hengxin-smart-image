# 2026-09-23 详情图提示词区分

## 范围

`jd-detail-screen-swap` 和 `jd-detail-screen-swap-790x1500` 在壁纸模式下追加“镜头指屏内前置镜头或开孔位置，”。两个主图 Skill 及其他名称保持原句，首次与返工共用此规则，多素材继续使用“这些”。不修改 Skill 内容、绑定、模型或收图协议。

## 验证

`pytest tests/test_task_prompt.py tests/test_single_revision_materials.py tests/test_revision_execution.py tests/test_codex_runner.py tests/test_execution_process.py tests/test_local_skill_execution.py -q`：52 passed、3 skipped、2 项既有依赖弃用 warning；`python -m py_compile app/execution/prompts.py` 通过。

参数化断言覆盖四个实际 Skill、相似但不匹配名称、首次/单张返工与单/多素材。此为确定性提示词修改，不创建收费生图任务，图片视觉效果未重新测试。

## 生产发布方式

只替换原生 Codex Worker 使用的 `backend/app/execution/prompts.py`。校验旧文件 SHA256，备份后暂停消费，复检 active/reserved/scheduled 均为空，再停止服务、原子替换、编译和启动；出错恢复备份。已执行轮次不追溯修改。

## 生产结果

已于2026-09-23部署。备份：`/var/backups/hengxin-detail-prompt-20260923T034519Z/prompts.py`。生产新文件 SHA256 与本地一致：`1969541b82651cd5558a5dc1955992b9cdad3bd7fbcfd7af1e3154c72e39c21e`。

直接加载生产模块验证四个 Skill × 首次/返工 × 单/多素材，共16项全部通过。Worker 服务 active，PID706711，celery消费队列恢复，最新数据库心跳 ready，CLI版本0.156.1。

独立审查 Stage 1/2 PASS，报告见 DETAIL-PROMPT-20260923-REVIEW.md；交付前 review-status 显示 approved=true、changedFiles=[]。回退时同样暂停消费并确认空闲，再恢复上述备份、编译并重启专用 Worker。
