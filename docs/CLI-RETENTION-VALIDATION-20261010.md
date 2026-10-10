# CLI 自动清理本地验证（2026-10-10）

本次只在本地开发、隔离数据库和临时文件中验证，没有部署生产、开启生产清理、提交或推送，也没有调用收费模型。生产启用需要用户另行确认。

## 验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| Linux 后端完整回归，同时开启两组独立 PG 测试 | 1617 passed，17 skipped；无失败 | `output/retention-linux-tests.log` |
| API 原有数据库并发专项 | 12 passed | `output/retention-api-pg-tests.log` |
| 保留与清理修正专项 | 47 passed，4 个 Windows 链接权限跳过；链接用例已在上述 Linux 全套通过 | `output/retention-fix-tests.log` |
| API 未知状态保护与会话专项 | 27 passed | `output/retention-unknown-tests.log` |
| 前端单测 | 221 passed | `output/retention-frontend-tests.log` |
| 前端类型检查、正式构建 | 通过 | `output/retention-final-typecheck.log`、`output/retention-frontend-build.log` |
| API CLI 隔离浏览器 | 7 组检查通过，errors 为空，独立审查者复跑 | `output/playwright/api-image-conversation/result.json` |
| 旧 CLI 隔离浏览器 | 6 项交互通过，errors 为空，独立审查者复跑 | `output/playwright/legacy-retention/checks.json` |
| Python 编译、Git 空白检查 | 通过 | 本地 `compileall`、`git diff --check` |

Linux 跳过的 17 项是既有的 root/Bubblewrap 技能隔离测试 16 项和专用非 root WSL 运行环境测试 1 项；不包括本次保留/路径清理用例，也不包括两组 API 数据库并发测试。模型执行使用受控执行器，未将模拟结果声称为真实收费模型调用。

提交前补充：全量暂存后执行 `git diff --cached --check`，发现此前未跟踪文件 `backend/app/retention/models.py` 与 `backend/tests/test_retention_concurrency.py` 各有一处文件末尾空行提示。上表空白检查仅覆盖当时已跟踪差异；本次保留已审代码快照，未将全量暂存检查记为通过。

## 关键行为与修正

- 24 小时缓存边界、7 天历史边界及有效操作续期；查看和轮询不续期。
- 正式版本、当前成品、原图和素材保持；无引用候选通过持久对象回执回收；其他会话/冻结快照引用仍保留。
- 缩略图写入尚未结束、文件/对象清理失败时等待重试；pending 状态拒绝新会话活动。
- 同父资源行锁保护清理、提交、采用和领取；重复清理幂等，首次启用有新宽限期。
- 已修复首轮审查发现的旧 CLI 结束时间/租约保护遗漏、材料提示被覆盖，补齐真正调用新路径清理函数的越界和链接测试。
- 已修复第二轮审查发现的 API 未知状态保护遗漏；item、turn、job 都必须处于明确终态才允许清理。
- 修正旧 API PG 测试夹具漏建现有 CLI 会话表的问题，以完整业务结构建随机测试 schema；未为测试改动 API 原业务逻辑。
- 过期后保留正式图片，清除旧候选/草稿，明确确认新会话；正常缓存回收仍续接原会话。现有文字修改、标注、原尺寸输出、采用和停止交互回归通过。

维护入口与生产前置条件见 [CLI 保留操作说明](../hengxin-smart-image/docs/CLI-RETENTION.md)。独立审查与最终快照结论见 [验收报告](CLI-RETENTION-ACCEPTANCE-20261010.md)。
