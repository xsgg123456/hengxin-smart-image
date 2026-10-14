# 海外 Codex 0.162.1 与 Astra high 发布

用户明确授权生产升级，并追加国内 CLI 同步升级至 0.162.1。当前海外 native 发布 overseas-20261014-7479264，CLI 0.156.1。此轮修改海外工作台启动参数和双端原生 CLI 版本；国内模型设置、前端、API 镜像、数据库结构与身份服务无变更，因此不提升前端 0.2.32 或重做界面发布。

## 执行规划与验收

1. 固定工作台新建/续接参数为 gpt-6-astra、high；保留会话 identity、workspace-write、原生对话及 Skill。参数、历史续接和既有工作台测试通过。
2. 官方 npm 指定平台包 0.162.1-linux-x64 校验 SHA512 后安装至独立目录；保留配套 code-mode host 和资源。复制当前完整 native 安装，只替换已核实基线哈希的工作台模块，使用原依赖环境；安装包与源码哈希验证通过。
3. 隔离临时工作目录内运行新版 CLI 的新建/续接和图片工具烟测；记录实际模型/推理，测试资料在 finally 清理；不产生生产业务记录。模型调用限必要验证，失败不自动替换用户指定模型。
4. 独立两阶段代码审查通过并绑定快照。使用现有双端入口关闭与 DB/Celery/broker 排空逻辑；停止已确认空闲国内 CLI worker、海外 worker/outbox，备份配置，切换专用 systemd drop-in（海外原生代码及双端版本环境），启动并验收后恢复入口。
5. 确认双端实际 CLI 0.162.1、海外工作台启动参数、健康及鉴权；国内 native 源码及所有容器身份保持。失败时入口保持关闭，核实空闲后移除本轮 drop-in 恢复原版本，不回滚业务数据库。

## 验证与发布结果

首次切换在入口关闭检查处安全中止，API 与执行器尚未停止；核实两路随后均返回 503，说明 Nginx graceful reload 存在生效延迟。已恢复原入口。入口检查增加最多 20 秒轮询，两路同时确认关闭才继续，超时仍中止。

2026-10-14 14:29（Asia/Shanghai）完成生产切换并恢复双端入口。第二次切换已排空并启动新版，但首次 Celery 就绪探针撞到启动窗口，保持入口关闭；确认 worker ready 后重新连续两轮核实 DB/active/reserved/scheduled/broker/unacked 全空。恢复步骤的拓扑检查需要 API 处于运行状态，移至 API 启动后执行；API 启动初期的 connection reset 通过有界重试恢复。未强杀任务、未重放整个切换脚本、未恢复数据库。

- 国内与海外实际 worker 环境读取：binary 均为 `/opt/hengxin-runtime/codex-0.162.1/codex`，配置及实际版本均为 `0.162.1`。
- 海外实际导入工作台模块：new 与 resume 均显式 `--model gpt-6-astra -c model_reasoning_effort="high"`；国内仅增加版本及 binary 环境覆盖。
- 官方平台包 SHA512 验证、46 项 runtime 文件哈希、完整 native 基线与新目录哈希通过。旧 runtime 与旧 native 目录保留。
- 实际新版 CLI 四轮烟测：Astra/high 新建、续接记忆、原生图片工具输出一张 1254×1254 图片、新会话独立；临时资料清理。国内现有沙箱中新版启动通过。
- 生产镜像隔离回归：576 passed、3 skipped；独立审查复跑工作台 274 passed；发布回归最终 13 passed；编译、diff 检查及双阶段审查通过。无前端变动，未进行视觉验收。
- 恢复入口后的独立实查：双端 ready 均 200，双端 auth/me 未登录均 401。容器身份与配置拓扑保持；schema 仍为国内 0028、海外 overseas_0015。
- 代码提交：`d2ac7d1`、`dedbc18`。审查报告见 `docs/reviews/CODEX-ASTRA-20261014.md` 与 `docs/reviews/CODEX-ASTRA-RELOAD-20261014.md`。
- 脱敏本地证据：`output/codex-astra/verification.json`、`smoke-pass.json`、`installed-tests.log`、`domestic-smoke.log`。服务端发布凭据位于 `/opt/hengxin-releases/codex-astra-20261014/`；初次失败归档保留，最终以 `verification.json` 为完成证据。

运行限制：发布脚本对 worker 首次探针和 API 启动期 connection reset 仍可能安全中止；本次已在原状态逐项验收恢复，不能盲目重跑该一次性脚本。合成烟测证明本轮流程，不能视为对所有历史业务会话的全量验收。
