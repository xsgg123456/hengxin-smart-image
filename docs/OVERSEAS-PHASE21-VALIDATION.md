# Phase21 本地验证

- `python hengxin-smart-image/infra/overseas/regression.py`：1953 passed，17项既有宿主条件跳过，295.24秒；包含真实PG六作业十二领取者最多五槽、幂等/回滚、迁移、失联占位和Linux进程退出。日志 `output/phase21-backend-final.log`。测试容器使用init，避免测试进程PID1导致旧supervisor主动拒绝启动；临时PG/Redis/容器均清理。
- `IDENTITY_TEST_IMAGE=hengxin-smart-image-backend:phase20 python hengxin-smart-image/infra/identity-test/run.py --phase21`：Phase17–21真实三服务HTTP全部PASS；真实Redis出站投递、游标恢复、取消403/409/确认退出、改派撤权、国内数据不变。日志 `output/phase21-http.log`；临时环境已清理。
- `pnpm test`：273 passed、0 failed；`pnpm typecheck`退出0；`pnpm build`成功，36.67秒。日志 `output/phase21-{frontend-tests,typecheck,build}.log`。
- `node tests/overseas-execution.browser.mjs`：空态、事件游标续传、取消确认/409/成功/响应不确定、确认中导航、未知状态、离页清理、改派与401/403、只读、390px祖先裁切通过；既有任务故障浏览器也通过。浏览器故障用例使用隔离HTTP替身，后端真实性由上项实测补足，不冒充真实模型执行。
- 独立审查者额外复跑Linux/PG专项27项、浏览器和孤立worker元数据/CLI启动检查通过。审查快照 `099af606aad6f47adadb999c38c488890269fd5ee5efe7d8db5c5b07bb6c8a5c`，报告 `docs/reviews/OVERSEAS-PHASE21-REVIEW.md`。

首次全量的1项旧迁移head断言和8项测试容器PID1环境问题已修正，最终全量无失败。所有旧跳过项不算已验证。

本阶段为执行基础，方案/图片业务协议留Phase22/23。未收费执行、未部署、未推送；自动清理关闭。资源阈值与PID视图边界见Phase21运行说明。已有预览/技能/package/locales改动保留，不纳入本阶段提交。下一步Phase22。
