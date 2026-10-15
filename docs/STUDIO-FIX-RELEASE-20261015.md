# 工作台两项修复与 0.2.35 发布

用户授权：修复 Skill 显式触发和执行失败误报，测试、提交 Git 并部署生产。执行消息展示保持；不安装 lxml，不发生产收费模型测试。

## 实施计划与边界

1. 源需求/计划同步后，明确 CLI web_search 双 id 兼容范围，只接受 item_<数字>→exec-UUID，保留后者与旧播报 ID 一致；其他重复键仍拒绝。
2. 正文读取与最终结算共享解码，事件异常有安全提示/诊断码；仍要求退出正常、明确完成、有效回复及正确会话。
3. 前端所选冻结 Skill 使用 $name，位于首轮身份之后/原文之前，未选不添加；附件、原文与隔离挂载保留。
4. 只读核实已知历史纯文字误报，必要时受限恢复：校验进程退出、原始记录SHA256、会话/任务归属、正文一致、无其他轮次和图片，原子发布与审计，保留完成时间及执行次数。默认只读，apply明确写入；不重跑CLI。
5. 版本0.2.34→0.2.35，无迁移，复用当前attachments发布入口。保留海外0015、99原生指针、3GiB内存、500MB双代理与镜像保留策略；独立审查后提交和实际镜像测试，再备份排空切换。

## 验证证据

- 定向解码、工作台runner/API、公开文字及旧交付测试：86 passed、1 skipped；恢复/Skill/解码/runner专项43 passed。
- 新Skill与既有会话/执行测试32 passed；发布入口/恢复/打包/保留策略143 tests及48 subtests通过。
- 真实生产记录只读内存回放：旧解析器invalid_event_stream；新解析器error=null、turn_completed=true，最终正文787字符保持一致。原始文件SHA256为3416c49bed752794172761ddf8703ba6cdbb2ac58c355adea7666e1371e54fb3。未修改服务、文件或数据库。
- 当前全量前端363 passed；完整后端、正式构建、浏览器、审查和安装镜像验证待补。
- 生产旧轮次确实读取了所选SKILL.md，命令退出0；新$name的拼接和发现目录通过隔离测试核对，未以生产收费模型测试冒充验证。

## 当前状态

代码已完成，独立两阶段审查PASS；candidateId=af036d9b6998d282605c941967712cc4e59f7fb61818291812ba404c958b0ab8，报告docs/reviews/STUDIO-FIX-20261015-R1.md，已登记同一快照批准。发布和历史恢复仍待执行。

- 正式pnpm build（含vue-tsc）通过，Vite 46.03秒；前端363测试通过。两套正式dist隔离浏览器通过，包含公开文字、失败/停止/刷新、Skill选择保持、桌面/390px。refresh脚本首次默认端口3018拒连，改环境变量指向实际3026后通过，未修改测试断言。
- Windows后端全量2210 passed、314 skipped、8 failed；7项为Linux安全文件API不可用、1项为Windows符号链接权限。未放宽安全文件检查，正在Linux隔离容器重验。
- 依赖审计critical=0；high=70/moderate=48/low=5，与上一发布记录一致，不将既有告警冒称不存在。
- 生产只读预检：0.2.34 / overseas-20261014-3b09fbc，两海外原生服务active，在途任务0、删除0、工作台轮次1，磁盘可用65GiB。
- Linux整仓只读挂载、无网络隔离容器全量：2344 passed、188 skipped、15 warnings，280.40秒；Windows的8个环境失败在Linux回归通过。日志output/studio-fix-backend-linux.log。
- 生产CLI 0.162.1技能发现探针：临时HOME/CODEX_HOME复制相同SKILL.md，SHA256 ed941bd6203c06d02e4d9b9dca4cd25115aa2dab4ecf0b177af62b5e91886bb3；unshare --net无网络、无认证，仅initialize/initialized/skills/list，返回amazon-new-product-aplus、scope=user、enabled=true、errors=[]，临时目录已清理。证明二进制发现能力，不冒称新生产推理已执行技能。
