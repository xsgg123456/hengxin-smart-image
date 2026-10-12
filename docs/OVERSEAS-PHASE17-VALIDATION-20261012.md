# Phase 17 本地验证 · 2026-10-12

## 范围与事实

统一身份服务复用既有钉钉provider，不连接国内/海外业务数据库。一次性分业务ticket兑换，国内旧授权兼容，海外成员/角色/会话独立建表。正式前端复用既有登录与业务选择；海外单授权不启动国内业务。具体协议见 `OVERSEAS-PHASE17-CONTRACT.md`，配置/代理/容器互联见 `OVERSEAS-PHASE17-RUNBOOK.md`。

海外五角色关系表在本Phase建立；成员维护、完整动作/范围矩阵属于Phase18，任务和CLI执行属于后续Phase。正式海外入口当前仅真实身份、切换和退出，模拟预览仍单独保留。

## 当场验证证据

| 验证 | 命令与结果 | 证据 |
|---|---|---|
| 后端完整回归 | 隔离Docker中 `python -m pytest -q -rs --disable-warnings -p no:cacheprovider`：1732 passed、17 skipped、15 warnings，325.61s | `output/overseas-phase17-backend-final.log` |
| 前端单测 | `pnpm test`：258 passed、0 failed、0 skipped | `output/overseas-phase17-frontend-final-test.log` |
| 类型与正式构建 | `pnpm build`（含 `vue-tsc --noEmit`）：退出0，Vite built in 36.82s | `output/overseas-phase17-frontend-final-build.log` |
| 后端真实镜像 | `docker build -t hengxin-smart-image-backend:phase17 -f infra/Dockerfile.backend .`：退出0 | `output/overseas-phase17-build.log` |
| 三服务真实API | `python hengxin-smart-image/infra/identity-test/run.py` 与最终 `--serve` 复验：PASS ALL | `OVERSEAS-PHASE17-INTEGRATION.md` |
| 四授权组合真实UI | `node tests/unified-identity-real.browser.mjs`：both/domestic/overseas/neither全部PASS | 同上；只替换外部钉钉provider，未拦截业务API |
| 故障UI | `node tests/unified-identity-faults.browser.mjs`：503重试、403禁用、退出失败重试通过 | `frontend/PHASE17-AUTH.md`；HTTP故障注入单独记录 |
| 既有预览回归 | `node tests/overseas-preview.browser.mjs`、`overseas-shell.browser.mjs`、`overseas-management.browser.mjs`：5+4+5组通过、无页面错误 | `output/overseas-phase17-{preview,shell,admin}-regression.log` |
| 差异格式 | `git diff --check`：退出0 | CRLF/LF提示不影响检查结果 |

后端在Linux容器使用独立临时PostgreSQL/Redis，注入四个 `TEST_*` 连接变量，不读写生产。1732项包含真实独立迁移、Redis一次性消费、身份服务及国内/海外桥接。17个跳过为9个已有Linux root本地Skill、1个已有非root WSL运行时、7个已有Skill目录/bwrap宿主测试；它们不算通过，Phase17没有新增跳过。15个warnings保留在测试结果，不当失败隐藏。

首轮全套测试中途新增旧Cookie撤销用例，而Python已加载修复前模块，得到1项失败；固定代码后重新启动完整测试容器，以上最终1732通过替代该旧结果。没有以单项通过掩盖全套失败。

## 隔离与撤销重点

- 两库分别迁移至国内0027、海外0002，海外没有国内表。
- 错业务ticket、篡改、重放、真实Redis TTL过期均拒绝；错业务Cookie不能认证。
- 单边停用、单业务退出不影响另一侧；统一退出后两侧401。
- 身份进程失联两业务503，恢复/重新认证路径独立处理。
- 最终新增真实HTTP检查：恶意Origin403且不消费ticket；旧统一身份仍有效时，携旧业务Cookie兑换另一pending身份403，旧Cookie随后访问与直接重放都401。两业务均验证。
- 真实浏览器四种组合无国内bootstrap误入，海外刷新、切换及全局退出正常。

## 审查与交接

独立两阶段审查结果及最终candidateId以 `reviews/OVERSEAS-PHASE17-REVIEW-20261012.md` 为准；完成状态由 `DEV-PLAN.md` 顶部记录。不得用此前Phase16或模拟前端的审查凭据代替本Phase。

临时集成网络/容器及测试Vite已清理。原有3012模拟预览保持运行。真实钉钉、生产迁移和公网代理尚未验收，未部署生产、未调用收费模型。下一步Phase18：复用已建海外成员/多角色关系和会话基础，实施五角色权限矩阵、成员维护与真实前端接入，不重复建表或复制鉴权。
