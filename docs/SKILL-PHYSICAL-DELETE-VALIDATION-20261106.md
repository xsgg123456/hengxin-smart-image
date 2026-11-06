# Skill 真实删除验证记录

已部署生产 0.2.66，并完成中央安装库与上传暂存回收，实际净释放 6,833,905,664 字节。最终生产验收见 [生产记录](SKILL-PHYSICAL-DELETE-PRODUCTION-20261106.md)。下列候选阶段的“尚未部署”等描述记录当时状态，以末尾最终结果为准。

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

全程不调用真实模型，不能据离线检查宣称已验证真实模型续聊。最终生产回收与上线证据见末尾及生产记录。

## 正式构建声明修正

第一次正式 Git 隔离构建被源文件稳定性检查拦截：临时 Vite 浏览器测试进程将自动组件声明裁去未访问页面的 15 项，生产构建会重新补齐。已停止本次临时 Vite，重新运行生产构建并通过；`components.d.ts` 恢复内容与功能前 `67dc766` 完全一致。只补回生成的类型声明，没有修改运行代码或放宽发布校验；新快照另行独立审查。

## 0.2.65 切换与生产引用核查修正

- `50d7095` 正式制品完成隔离 Git 构建、隐私及哈希检查；生产安装 API 172 PASS、publisher 173 PASS、native 58 PASS、native-root 14 PASS。排空、数据库备份隔离恢复、实际 native 路径安装测试、全部服务及前端切换验证完成。
- 私有回收 dry-run 在任何修改前拒绝 `Unaccounted historical Skill input`。只读追查确认 138 个 Job、276 份磁盘 input 均有归属：按原始发布引用有 38 组，按内容去重有 35 组。旧核查错误地先按内容去重，再以发布号比对，误报 14 份输入。
- 已核对安装库仍与发布前 exact tree 相同、当前 schema 1/发布号未变、无 preparing/pending/GC 收据，历史基线完整一致。保存无 GC 取消凭据，恢复原 execution gate 与业务访问；没有删除生产文件，也没有回滚会话数据库。
- 修正 owners 的核查模式保留全部 Job 引用，维护核对完成后才按内容去重。真实 SQLite 多 release 同内容回归先复现失败，修后 dry-run/实际回收成功；同内容但未被任务引用的第三个有效 release 仍拒绝。独立相关后端 52 PASS、发布 21+5 PASS（Windows 与 WSL）；生产实际 Compose 链只读合并检查通过，原历史挂载及业务配置不变。
- 补充发布目标 0.2.66，基线为已运行的 0.2.65；本节为回收前验证，实际释放以以下最终验收为准。

## 0.2.66 最终生产验收

- 代码 `5379b83`；批准快照 `d0f9a69016298f4d42eec4b116ced6d23c1aa9c989f4d78dae025336730f4901`，独立两阶段 PASS，最终 review-status 匹配。
- 正式 Git 隔离构建、隐私及制品哈希通过。生产安装 API 175 PASS（1 项 root 用例由 root 组覆盖）、publisher 176 PASS、native 58 PASS、native-root 14 PASS，实际 native 安装目录验证通过。
- 私有维护回收完成，350 个清理目标；安装库由 6,856,118,272 降至 287,694,848 字节，上传暂存由 265,678,848 降至 196,608 字节。历史副本新增 0 字节，净释放 6,833,905,664 字节；独立 du 复核一致。
- 当前 8 个 Skill 的真实 UID 999 沙箱读取与只读挂载通过；33 个历史会话、35 组内容、138 份历史输入读取通过，全部 276 份冻结输入有归属。8 张历史业务表及 51,841 个执行文件系统条目的保护比较通过；全部 236 个 Job 上下文指纹前后一致。
- 已解除维护状态并恢复业务。生产浏览器核对当前 8 个 Skill、新删除说明、原任务历史文字/图片/附件与可用的输入框及 Skill 选择；仅查看、取消确认，没有删除当前 Skill 或发送测试消息。
- 本地已校验的可恢复备份保留；服务器本次临时备份副本已删除，避免额外占用。临时浏览器测试容器、网络和隧道已结束。
- 仍未验证真实模型续聊；全仓旧测试失败及依赖告警保留上文原始边界。
