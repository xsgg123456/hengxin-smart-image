# 工作台开放文件输出 · 发布验收

状态：2026-10-24 13:06（北京时间）完成生产部署及真实文件验收；部署退出码 0，PHASE complete。

## 发布身份与根因

- 版本：`0.2.52`；发布：`overseas-20261024-b6289eb`。
- 产品提交：`b6289ebfa9d69bd0b27c003bb0d978a48a135c5a`。
- 发布包 SHA256：`26a2ec96e5d32c20233092a3782e671da18f138a742fe3f0332bed5fd46e9b51`。
- 1344 个归档文件，5663763 字节；允许清单、隐私检查、归档回读与上传后逐文件校验通过。生产原始故障资料未进入 Git 或发布包。
- 生产镜像：`sha256:cf820fad7103eeeb6e7217ca12a10353f9ad94d69eaa4bf3b2cc57096aec872c`；与 INSTALL_TEST_IMAGE_ID、PREPARED、UPLOAD_CAPACITY_IMAGE_ID 三项凭据一致。安装源码逐文件哈希核对通过。
- 本次故障是素材查看被误判为待交付图片，接收失败无限重试又把已正常退出的执行转成 uncertain。原始记录回放确认模型只执行一次，最终文档可下载、下一轮可提交。
- 图片保留原有预览、修改、下载、归档；其他格式按原件展示下载。自动收取一轮后结束，未保存项可手动取回；复用逐文件副本、对象台账、下载以及原生 outbox，不新增执行服务或模型调用。

## 独立审查与回归

- [最终代码审查](STUDIO-OUTPUT-FINAL-REVIEW-20261024.md)：两阶段 PASS。修复旧审查发现的 work/snapshot 双入口重复收取，覆盖图片/文件两种顺序及后续轮独立交付。
- [打包副本映射审查](STUDIO-OUTPUT-PACKAGE-REVIEW-20261024.md)：两阶段 PASS。1963 项受控快照只排除了用户预先修改的 AGENTS.md；正式 dist 640 文件逐字节一致。
- 本地相关后端：885 passed、43 skipped；最终关键回归：50 passed，包含本次生产原始事件/rollout/文档回放；私有事故测试实际执行，没有 skip。
- 前端：396 passed、类型检查及正式构建通过；浏览器覆盖部分成功、继续发送、原件下载、手动取回重试及移动端溢出。
- 发布脚本：31 passed。Linux 实际镜像的隔离 PostgreSQL 专项：62 passed；额外实际 PostgreSQL 新增表创建、重复迁移、外键/唯一约束及旧数据保留：1 passed。
- 实际 Linux 镜像全量测试：2499 passed、206 skipped、1 deselected，0 failed，用时 716.50 秒；跳过和排除项没有计为通过。实际镜像容量专项：4 passed。
- 原生执行器实际安装目录专项：571 passed、3 skipped，0 failed，用时 143.19 秒；使用镜像内 Python、只读挂载实际安装目录执行。
- 实际镜像通过真实 Redis/Lua/HTTP/原生消费流程取回图片和文件、重复取回去重：1 passed。隔离测试使用独立临时容器和数据库，不连接生产库，结束已清理。
- 依赖审计 critical 0；既有依赖 high 37、moderate 37、low 3，锁文件本次未变化。该结果不表示依赖无漏洞，后续依赖治理独立处理。

## 安装与生产验证

- 关闭新执行入口、排空执行器后完成备份及隔离恢复校验，备份位于 `/opt/hengxin-backups/overseas-20261024-b6289eb`，COMPLETE 已确认。海外仅新增输出文件表至 overseas_0022，迁移前后原表、原列、原行保持；国内 0032、身份服务、Skill 内容及启停绑定保持。
- API healthy；worker/outbox 均 active，工作目录均为 `/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend`。前后端版本标记均为 0.2.52 / b6289eb；部署和全部安装检查退出码 0。
- 精确故障任务 `5a190d2a-d2f5-4b20-b72f-2808a5483a1d` 在核对原始完成事件、退出状态及执行组已停止后收敛为 succeeded；执行次数仍为 1。验收后任务的四次既有执行均 succeeded、各执行一次，未新增模型任务。
- 正式 Chrome 页面会话 2 显示“已完成 · 有草稿”，原文字、压缩包草稿、Skill 保留，发送可用，原“执行状态待核实，禁止重新执行”和“正在接收图片”不再出现。旧事故的自动保存提示仍作为历史提示显示，不锁定会话。
- 会话 2 点击“取回文件”，从原生实际工作目录取回 `产品学习记录.md`，显示文件卡片并实际下载成功；会话 1 同时取回 `01_white.jpg` 的工作文件和本轮副本、整套 ZIP。图片仍为原来的 8 张，未新增重复图片；重复取回 ZIP 后仍只有一个 ZIP 输出记录。
- ZIP、图片和文档均通过正式前端下载到本机，逐字节 SHA256 与服务器原件一致，见下表。ZIP CRC 校验通过，含 8 张成图和 1 张整套预览；图片大图预览正常，修改/归档入口保留。刷新会话后 ZIP 卡片和 8 张图片仍在。
- UI 验收时首次重载曾出现短暂空白；再次重载后页面恢复并完成上述操作，捕获的控制台 error/warn 为空。未据此断言空白原因，也未声称已修复独立的首屏性能问题。

| 实际下载 | 字节数 | SHA256 |
| --- | ---: | --- |
| 产品学习记录.md | 10514 | `50ee11dc00615081307ec2d9bcf1ca1cc92c70b0dc0941e874a155b3087928da` |
| OUTON_乡村风主图_8张_1600x1600.zip | 6643273 | `e49db14155d5abeaf8ba6b02036423f42442605b153ae5f0d45d12070d6a0747` |
| 01_white.jpg（沿用既有图片 ID 文件名下载） | 584738 | `4cdb8fcd611314ffb329e16aab8cf20ad9a02c902f9508d06b0806f55dfacffb` |

本机私有证据保留于忽略目录：`output/studio-output-production-before-ui.json`、`output/studio-output-production-after-ui.json`、`output/studio-output-production-downloads.json`。生产页面截图为 `output/studio-output-production-md.png`、`output/studio-output-production-files.png`、`output/studio-output-production-image.png`。不将原始客户资料和截图打包发布。

## 验收边界

没有重新调用生产模型或重新生图。真实原始输入在隔离测试中回放；生产验收使用该任务仍存在的图片、压缩包和文档。已被删除或覆盖且没有本轮副本的文件无法恢复。
