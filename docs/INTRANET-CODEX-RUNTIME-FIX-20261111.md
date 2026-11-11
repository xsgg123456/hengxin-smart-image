# 内网 Codex 执行环境修复与验收

2026-11-11 用户明确授权：直接修复公司内网 `.245`，验证海外 PPT 读取，并检查国内 Codex 执行环境，从依赖与部署流程消除根因。旧公网不变，不更换模型或账号，不覆盖用户工作区。允许完成验收所必需的少量真实模型调用；优先无模型探针，不批量生成。

## 有序计划与完成标准

1. 固定实际环境、运行身份、依赖与在途任务基线；复现内层命令失败，确认 PPT 原件。完成标准：来自真实路径和 UID 的错误及文件校验，不只运行 `--version`。
2. 补齐系统沙箱、文档、图片与脚本工具依赖，保存可重放依赖清单；必要时调整只读挂载，保留隔离和精确代理约束。完成标准：两业务实际 UID 的外层加 Codex 内层沙箱能够执行命令、读写自己的工作目录，并拒绝越权写入及跨任务访问。
3. 验证文档与图像能力。完成标准：真实产品 PPT 全部 2 页文本、2 个媒体文件可读，PPT 转 PDF 再转页面图片成功且目视核对；验证 Python/Node、ZIP、PNG/JPEG 与常用 DOCX/XLSX/PDF 基础读取。明确不支持或未测能力，不声称无限格式支持。
4. 单测/编译及独立两阶段快照审查，按已审范围安装。需要重启执行服务时先停止消费并排空，未知状态不得强停；保留原配置与代码回退证据。完成标准：安装后的两业务相同探针通过、账号和生产任务保持、队列与健康恢复。
5. 最小真实模型验收：海外读取原 PPT 的隔离副本并报告文本/图片证据，国内验证命令、图片读取及执行结果；必要时一张受控图片修改。完成标准：工具日志证明读取/处理实际发生，不以模型自然语言承诺、任务 succeeded 或程序 --help 替代。结果写回本文。

## 依据

根因见 [只读诊断](INTRANET-OVERSEAS-PPT-DIAGNOSIS-20261111.md)。官方沙箱文档说明 Linux 优先使用 PATH 中的 bwrap，并推荐发行版安装及精确 AppArmor profile，见 https://learn.chatgpt.com/docs/sandboxing 。不关闭全局 AppArmor/userns 限制，不使用关闭沙箱的 CLI 参数。

状态：已部署并通过本次执行环境验收。

## 真实探针发现与修复补充
标准LibreOffice CLI在Codex默认禁网内层使用SingleOfficeIPC socket时被拒绝，单补缓存不足。改用官方LibreOfficeKit无IPC初始化，提供libreoffice/soffice的离线PDF转换子集，只读挂载；默认网络限制、主机隔离和凭据边界保持。原生转换在限时独立子进程中完成，父进程解析校验PDF、原子发布、清理私有profile；不静默支持其它格式或任意CLI选项。两真实UID已成功渲染2页。先前媒体项计数包含ZIP目录项，实际为2个媒体文件，已更正；原PPT字节未变。

## 部署前验证

- 两真实 worker UID（1001、1002）的 `candidate-probe3` 均通过：内层命令，工作目录写入及主机敏感路径/只读目录隔离，Python/Node，PNG/JPEG/WEBP，DOCX/XLSX 读写和 PDF 渲染，损坏 PPT 拒绝，原资料 PPT 两页/两个媒体/502 字符、两页渲染。跨工作区隔离另由现有 Linux workspace/persistent mounts 回归覆盖。
- 真实 Linux 候选源码十个模块：274 passed、零 skipped；部署事务故障注入：17 passed。转换异常覆盖原生非零退出、超时及零退出但 PDF 损坏：保留旧产物并清理私有临时目录。
- 两页渲染已目视检查：第一页 A9 滑板车封面，第二页中文产品信息与细节，字体和图片正常。
- 系统依赖补装 116 包、升级/移除均为零；版本清单及安装日志留在内网私有维护目录。此时尚未替换生产 workspace；后续以安装后结果为准。

## 生产安装与验收结果

2026-11-11 北京时间约12:01完成安装，随后真实模型验收通过。唯一目标 `192.168.1.245`；旧公网未操作。

- 已批准快照 `10e0a86542ddf018e4478b68b1be29195cd8f972c3b505afca7c1ad446b16637`，独立 Stage 1/2 PASS，见 `docs/reviews/INTRANET-CODEX-RUNTIME-REVIEW-20261111.md`。
- 发布排空记录：两 worker 的 active/reserved/scheduled/database 均0、消费者已暂停；停止共享服务后安装，真实UID preflight通过；再启动并恢复国内 `celery`、海外 `overseas.cli`。
- 国内、海外、账号三处 workspace 与 renderer 文件哈希均等于候选，renderer权限0755。两 worker 的 ExecStartPre 实际完成一页 DOCX 转 PDF；依赖缺失或命令沙箱失败会阻止接单。
- 六份服务环境配置与备份SHA256一致；六个原生服务active，17个容器运行，两业务readiness均HTTP200。PPT原件SHA256未变，验收独立临时模型工作目录已清理（0残留）。
- 安装后 `installed-probe` 两实际UID全部通过，同部署前完整覆盖；证据 `output/runtime-fix-20261111/domestic-installed-report.json`、`overseas-installed-report.json`、`installed-health.json`、`final-health.json`。

### 海外真实模型

既有账号broker、gpt-6-astra/high、真实外层及内层沙箱；会话 `01a1c8c5-413a-7960-bb1d-df5f64577811`，首轮64.313秒、退出0、turn.completed、无执行错误。

1. 实际读取挂载的原Skill（命令exit0）。
2. `call_dba89d9c5b2d4123b3a08e696b344d4e` 通过Python ZIP/XML读取资料，2页、2个媒体，随后LibreOffice转换成功，PDF171037字节。
3. `call_e4218d5d15494b0fa893af5d579bce9a` 的pdftoppm/pdfinfo退出0、PDF页数2；两张PNG完整可解码。
4. `call_50145f897f3e4e23b4fd15e25a836076` 实际调用两页view_image；模型报告第一页A9蓝紫三轮车、第二页黑字红色重点的产品信息，与人工查看的页面一致。
5. 续接同session，`call_9bc2adf243874a018074592531be994e` 实际重读JSON退出0，返回上一轮marker，续轮完成。

保留 `output/runtime-fix-20261111/overseas-model/` 的report/tools/events/resume-tools/resume-events、reply、PDF、两页PNG；stdout的本机终端编码显示不影响保存的UTF-8文件或模型读取。

### 国内真实模型

真实国内UID1001与既有broker，会话 `01a1c8c5-41d3-7443-b23b-7dc41511620c`，50.479秒、退出0、turn.completed。

- 实际Python和Node读取原图均为256×256，命令exit0，并调用view_image。
- `call_24b83a70c18546d3bd53d9038046ca3a` 调用原生imagegen，引用 `/work/input.png`；没有用脚本绘制替代生图。
- 后续 `call_a2395bd0629842d9ab248d341f9a5d18` 实际复制原生生成文件并写标记，exit0；生产collector收集1张图片、无warnings，1254×1254。已人工检查确为蓝底中央白圆。输出尺寸是模型实际返回值，未宣称原图尺寸保持不变。
- 证据 `output/runtime-fix-20261111/domestic-model/` 的report/tools/events/reply及domestic-result.png。

### 已验证范围与边界

本次覆盖共享Codex执行环境、PPT全文和页面读取、PDF渲染、Word/Excel基础读写与渲染、常用图片格式、Python/Node、原生图片编辑与结果收集、会话续接、隔离和启动依赖门禁。国内已删除任务的数据库/对象/执行目录核查见 `INTRANET-DOMESTIC-DELETE-CHECK-20261111.md`，未为了本次验收重复删除任务。

真实模型验收通过生产安装代码及真实服务身份直接执行，未通过业务API创建新任务、未改写用户原对话；不代替所有页面按钮、并发或所有文件格式的完整业务验收。工具记录过滤了超过12000字符的输出（图片base64），保留调用、命令执行返回、实际产物和报告；未把过滤后的缺少图片返回记录描述成独立逐调用输出证明。已通过实际文件、调用记录、collector及人工目视交叉验收。

原失败消息保留，用户可在原海外会话发送“重新读取产品资料.pptx”继续；无需把PPT手动转图片。源码与可重放依赖清单已留在工作区，本次未提交或推送Git。
