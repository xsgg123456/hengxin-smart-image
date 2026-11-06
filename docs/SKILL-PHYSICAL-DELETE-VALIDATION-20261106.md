# Skill 真实删除验证记录

尚未部署或清理生产。本文件随实际验证补充，不能作为完成凭据。

## 本地验证

- 全前端 `pnpm test`：529/529 PASS；`pnpm run typecheck` PASS。
- 生产构建 `pnpm run build`：Vite 37.98 秒，PASS。`build:overseas` 是隔离预览，不作为生产制品。
- `pnpm audit --prod --json`：Critical 0、High 39、Moderate 35、Low 5。本次未改依赖与锁文件，保留原有告警，不宣称全仓依赖无漏洞。
- 全后端 `.venv/Scripts/python.exe -m pytest -q --tb=short`：2817 passed、442 skipped、9 failed，648.73 秒。修改前 HEAD `67dc766` 独立导出源码复跑四个失败文件，完全复现同 9 项失败、43 passed；仍是此前已有的 Windows/POSIX 文件读取差异、symlink 权限与接口白名单旧断言。未修改这些失败文件或降低安全检查。
- 新增历史/清理真实 SQLite 与私有目录验证：28/28 PASS，包括已存在和缺失历史副本、Studio/非 Studio、运行状态阻止、旧版本冻结、实际执行准备、半途删除失败重试、目录越界、硬链接、Windows junction。
- 全量迁移和清理追加验证：14/14 PASS，包含同一统计范围净释放量、维护 gate、未归属历史 input 拦截、旧版本整体迁移与响应丢失重放。
- 会话技能缓存相关：50 passed、8 Linux 专用 skipped；将在 Linux 安装路径补验。
- 新对象存储：10 passed、2 Linux 专用 skipped；离线安装及原安装/标题/下载篡改相关：24 passed、1 Linux 权限 skipped。
- 发布与去重备份脚本：Windows 21 PASS、WSL Ubuntu 真 root 21 PASS；真实 symlink/FIFO、uid/gid、权限和纳秒 mtime 恢复验证通过。

原始日志存放 Git 忽略的 `output/skill-physical-20261106/`。

## 候选制品

初始候选 `30c53dc6d784f84ffe746c81ac8666655e7bb32696a531e3c92d44cf6bdd9215`。

`skill-physical-20261106-candidate-30c53dc6d784`：5,152,058 字节、755 文件，SHA256 `00c6061f57b7b3a8a326d99af676290a5c12d12e12082458c9ec27e357841ac1`，隐私检查、完整制品 manifest/hash 验证 PASS。

## 故障与恢复补验

- 首轮审查指出准备失败后的新增历史副本应计入最终净释放量。新增持久准备凭据，固定第一次操作前基线；失败重试、维护接管、空库首次安装均有回归验证。
- 发布进程启动及后台恢复持久清理事务；用户刷新页面后仍会自动恢复，修复故障后不依赖旧按钮。
- 第二轮审查指出独立历史副本必须持久落盘后才能删除中央原件。新增文件、目录、owner 祖先及锁文件同步，已有副本重试也执行持久化；故障注入验证失败会阻止删除。
- 最新相关专项合计 50 PASS，日志 `output/skill-physical-20261106/durable-regression.log`。

## Linux 安装与浏览器

- 第二候选 `bf1fca7348ccc784558ef69e2b7b041b33e5992b7771cee46d5d5cfcfdaf61ea`：API UID 10001 测试 167 PASS、仅排除在 root 组单独覆盖的 1 项；publisher root 168 PASS；native UID 999 为 58 PASS；native root 14 PASS。所有必需用例无跳过。
- Playwright 真实 Vue + 隔离后端完整六项检查 PASS、浏览器错误为空。覆盖文件夹 108 文件、二进制/空目录、下载逐文件比对、冲突、更新、物理删除、失败保留和重试。证据 `output/playwright/skill-folders/result.json`。
- 已目视核对确认、删除失败与成功页面。窄屏以动画稳定后的 `output/skill-physical-20261106/narrow-settled.png` 为准，旧脚本的中间动画截图不作为验收证据。
- 最终候选 `aa7725195abd5b5bb5e5fd012c75eac8e7259fa191c19bbfeb5a016c6e57522d`：API 172 PASS（仅排除 root 组覆盖的 1 项）、publisher 173 PASS、native 58 PASS、native-root 14 PASS；安装通过凭据已生成。独立审查两阶段 PASS，另独立重跑专项 50 PASS、发布脚本 21 PASS、前端 529 PASS、typecheck PASS。生产仍未切换。

## 可恢复备份

- 中央安装库 17,678 个文件/目录、逻辑文件字节 6,807,730,066；备份按内容存成 444 个对象，共 219,106,064 字节。
- 索引 SHA256 `7efc8b0f3358a5c846fa955c9862abdb2d571e1cbf14562015605c750736b11a`；压缩归档 SHA256 `2e27acc5bc47c56e7aac000e4a1fa00a47e44be048e6ede0dd7d4aad73388df5`。
- 归档已下载本地，校验归档、索引、全部对象哈希通过；Linux 隔离恢复逐项验证内容、权限、UID/GID、纳秒 mtime 通过。核验后的隔离恢复副本已删除，生产库未动。

全程不调用真实模型，不能据离线检查宣称已验证真实模型续聊。最终生产回收与上线证据待补。
