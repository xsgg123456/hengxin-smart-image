# 内网 Codex 运行依赖修复审查 · 2026-11-11

**当前状态：同一批准快照的部署后证据复核通过，见文末「线上验收证据复核」。以下原审查章节保留部署前时点的待验说明；已完成项由文末附录更新，不再视为当前阻塞。**

## 快照与结论

- **Stage 1：PASS（本轮代码实现范围）。**
- **Stage 2：PASS（本轮代码质量与安全范围）。**
- **可批准 candidateId：`10e0a86542ddf018e4478b68b1be29195cd8f972c3b505afca7c1ad446b16637`。** reviewer 完成阅读/测试后再次执行 review-status，currentId 仍与该候选一致。
- 初始送审 `9681447bc87ce3b98a9eaf6613e75859a7b3b4cdf1f9c87e172c427f727281c5`；审查中发现修改为 `472bbe0c5acf172d1a35e0234da00f59da96db9c0262e26282d64dc41f1aebae`，随后收到最终候选并重新复核全部新增差异。初版结论没有直接覆盖新版本。
- 既有批准基线：`bc6c7c26b148e39b0589889dc4347fcd13ab60d2240235944a0cf01a24bab222`。既有代理/HTTP 登录等其他变更不重复授予本轮审查结论。
- **这不是线上交付完成判定。** 安装后最终路径探针、服务/队列恢复、账号和用户任务保护、真实模型工具日志人工核对，仍须由主 Agent 按合同完成并记录。候选目录通过不能代替最终安装路径通过。

## 审查范围与来源

代码路径以下统一相对 `hengxin-smart-image/`：

- `backend/app/execution/workspace.py`、`runtime_check.py`、新增 `office_render.py`。
- `backend/tests/test_execution_runtime_resources.py`、新增 `test_office_render.py`。
- `infra/local_codex_worker.py`、`codex-runtime-packages.txt`、`install_codex_runtime.py`、`verify_codex_runtime.py`、`verify_codex_model.py`、`CODEX-RUNTIME.md`。
- `scripts/migration245/fix_runtime.py`、`test_fix_runtime.py`。

来源：仓库根 `Product-Spec.md:1452`、`DEV-PLAN.md:1668`、`docs/INTRANET-CODEX-RUNTIME-FIX-20261111.md:7` 及只读诊断。追加 LibreOfficeKit 的合同补充亦已读取。只读核对固定摘要的 `scripts/migration245/upgrade_codex.py` 作为部署依赖，不把它重新归类为本轮新代码。

## Stage 1 · Spec Compliance

| 合同条目 | 代码实现结论与证据 | 线上边界 |
| --- | --- | --- |
| 1. 固定真实环境、UID、在途与 PPT 基线 | **完整实现。** `scripts/migration245/fix_runtime.py:122` 从服务实际 `/proc/PID/status` 获取 UID/GID/附加组；`:186` 校验已知源码摘要；`:193` 固定运行环境；`:216` 调用既有安全排空。根诊断 `docs/INTRANET-OVERSEAS-PPT-DIAGNOSIS-20261111.md:13` 记录命令启动前 panic。 | reviewer 未连接生产。媒体数量已按合同补充更正为 **2 个媒体文件**，原 3 项包括 ZIP 目录项；不沿用初稿的错误计数。 |
| 2. 依赖及必要只读挂载，保留隔离与代理约束 | **完整实现。** `backend/app/execution/workspace.py:65` 保留 clearenv、用户/PID/IPC/UTS namespace 和 cap-drop；`:90` 仅追加字体/LO 配置只读挂载；`:115` 只读映射固定 bwrap，拒绝符号链接/硬链接/目录；`:124` 只读映射两个离线转换别名，PATH 优先但无禁用沙箱参数。`infra/codex-runtime-packages.txt:2` 列明系统依赖；`infra/install_codex_runtime.py:25` 核对主机/身份/版本，`:31` 模拟安装并拒绝删除或现有包升级。 | 最终安装路径仍须验证。依赖安装器不承担升级已有系统包或通用 npm 依赖安装。 |
| 3. 文档/图片/Python/Node 能力 | **完整实现指定验收入口。** `infra/verify_codex_runtime.py:34` 实际 Python/Node 写入；`:38` PNG/JPEG/WEBP；`:43` DOCX/XLSX 往返；`:48` DOCX/XLSX 转 PDF；`:54` 无效 PPT 拒绝和临时目录清理；`:60` PPT ZIP/XML/媒体解码、LO→PDF→PNG、页数及文本。`:97` 拒绝 root；`:111` 使用共享外层和 Codex 内层沙箱。 | 原 PPT 与视觉结论来自主线程实测；reviewer 没有以本地 Windows 单测冒充 Linux 转换或目视验收。isolation 字段证明列出宿主路径不可见/系统写拒绝，不等同穷尽所有跨任务场景。 |
| 4. 测试/审查、安全部署、回退 | **完整实现。** `scripts/migration245/fix_runtime.py:200` 停服前备份；`:216` 排空与账号入口门控；`:220` 再验候选/配置；`:231` 明确 renderer 为0755；`:234` 真实身份运行探针；`:237` 验服务队列；`:248` 部分启动失败重新排空，未知状态保留；`:264` 仅恢复本事务文件。`:172` 两 worker 增加 ExecStartPre；`:167` 国内、海外、账号 daemon 三份 workspace 均配套 renderer。 | 安装后的服务恢复和账号/任务保持仍须记录。脚本恢复不确定时会报 RECOVERY_UNCONFIRMED，不能视作自动回退成功。 |
| 5. 最小真实模型验收 | **完整实现受控取证入口。** `infra/verify_codex_model.py:33` 要求既有 broker；`:38` 独立临时目录；`:64` 短期凭据且检查无 refresh token；`:68` 现有模型协议；`:90` 保存工具日志；`:98` 核对 2页/2媒体，并独立解析/保存 PDF 与两页 PNG；`:126` 保存续轮事件/工具；`:137` 筛查原生编辑及输入引用。不向业务库写入测试任务。 | **尚未完成真实模型验收。** 关键字检查是初筛，不是独立证明；主 Agent 必须按 call_id 核对成功输出、两页 view_image、国内 Python/Node 和同一次 imagegen 的输入图引用。续轮工具文件包含首轮，应按续轮边界判断实际读取。 |
| 补充：默认禁网内层的 LO IPC 失败 | **完整实现。** `backend/app/execution/office_render.py:42` 采用 LibreOfficeKit；`:57`、`:63` 检查 ABI 大小；`:76` 严格限定 PDF 转换子集；`:100` 输入输出限制于 /work 或 /tmp；`:112` 校验 OOXML 基本结构；`:120` 私有目录、限时子进程；`:127` 独立解析 PDF 后原子发布。`runtime_check.py:24` 每次启动也真实 DOCX→PDF。 | 不是 LibreOffice 全 CLI 兼容器；不支持的选项明确报错。不得声称任意格式、任意 Skill 依赖全部支持。 |

UI 一致性及邻居页面视觉对比：**不适用**。本范围无页面/样式/组件/用户引导变更。`infra/CODEX-RUNTIME.md:12` 明确服务预检边界，`:16` 明确独立脚本不替代业务按钮和数据库投递验收；PPT 目视核对属于附件验收。

Spec 漂移：**未发现**新增页面/API/表或无关功能。文档依赖、只读 renderer、预检、受控验收与事务直接对应合同第 2–5 步和追加的 IPC 根因说明。见上表具体位置。

## Stage 2 · Code Quality

### 已解决的审查问题

1. **原 MEDIUM：315 行超限，已解决。** `scripts/migration245/fix_runtime.py:298` 最终为298行；新增 wrapper 155行，范围内所有 Python 文件不超300行。重读最终事务逻辑，并重新执行17项故障测试，未以删空行推定行为不变。
2. **原 MEDIUM：模型证据不足，已解决至受控取证入口要求。** `infra/verify_codex_model.py:93` 增加查看图/转换/编辑调用筛查；`:100` 独立 PDF 页数检查、保存 PDF/两页图；`:126` 保存续轮证据。由于工具日志仍须人工按调用对应关系核对，脚本 report.json 不能单独宣称合同通过，边界如 Stage 1。
3. **追加检查：renderer 可执行权限和失败路径，已覆盖。** `fix_runtime.py:231` 安装0755，`test_fix_runtime.py:95` 验三份 renderer 的权限参数；`test_office_render.py:43` 覆盖超时和原生返回0但产出损坏PDF，均证明旧结果保留且临时目录清除。

### 安全、质量与测试真实性

- **静态安全扫描通过。** 范围内无硬编码密钥、shell=True、eval、SQL 拼接或关闭沙箱。`fix_runtime.py:292` 唯一动态执行先经固定路径、root 所有权、不可组写/全局写、无符号链接祖先及固定 SHA-256 校验（`:29`、`:288`）。本地 helper 摘要与常量一致：`d6e34d3911ba8772021ea7254557bb90f7efb62376df2eca84e76f8ecd6e5b01`。固定绝对路径是限定 .245 发布目标，不是凭据泄露。
- **默认隔离保持。** `workspace.py:69` 仅将只读工具目录置于 PATH 前端；`:70` 把缓存/配置落到私有 tmp；`:94` 仍只可写本任务 home/work。`office_render.py:59` 只传 Batch=true，不启用宏；官方24.2.7.2源码默认未启用 EnableMacrosExecution 时使用 NEVER_EXECUTE，见 [LibreOffice官方源码](https://github.com/LibreOffice/core/blob/libreoffice-24.2.7.2/desktop/source/lib/init.cxx#L2604)。该结论不扩张成对所有解析器漏洞的保证。
- **原生进程边界清晰。** `office_render.py:65` 保存后验文件头并 fsync，`:73` 仅子进程 os._exit，父进程`:122` 限90秒、`:129` 解析实际PDF、`:133` 原子替换。失败不会先破坏旧产物。正常调用仍处于原有两层沙箱，没有新增网络权限。ABI前缀已比对 [官方LibreOfficeKit头文件](https://github.com/LibreOffice/core/blob/master/include/LibreOfficeKit/LibreOfficeKit.h)，实际安装版本运行由主线程双UID实测覆盖。
- **恢复边界通过。** `fix_runtime.py:141` 比对内容、权限、组、设备/inode，仅恢复本事务写入；`:254` 活跃 worker 重新排空；`:256` 不确定PID/状态拒绝强停；`:273` 恢复不确认则保留现场并报错。`test_fix_runtime.py:141`、`:162`、`:170`、`:180`、`:214` 覆盖部分写入、部分启动、检查失败、第三方覆盖和恢复验证失败。
- **测试真实性符合边界。** `test_execution_runtime_resources.py:21` 检查两种资源布局和只读映射，`:41` 拒绝目录冒充可执行文件；没有声称它运行真实bwrap。`test_fix_runtime.py:41` 明确模拟POSIX权限/身份/探针，`:228` 另验父目录权限；`:196`/`:204` 验renderer清单/语法失败发生在排空前。`test_office_render.py:43` 故障发生于真实父进程转换函数内，并检查旧文件与清理结果，不只是对mock返回值断言。
- **无未解决 HIGH/MEDIUM 代码问题。** 没有用未执行的线上功能填充“已验证”。

## reviewer 本地验证与原始编译输出

初轮后端七模块（未发生变更的过程/收集等回归亦覆盖）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_execution_runtime_resources.py tests/test_execution_workspace.py tests/test_execution_proxy.py tests/test_execution_process.py tests/test_execution_outputs.py tests/test_overseas_studio_execution.py tests/test_overseas_execution.py
88 passed, 5 skipped, 2 warnings in 20.68s
```

最终候选四个直接相关模块：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_office_render.py tests/test_execution_runtime_resources.py tests/test_execution_workspace.py tests/test_execution_proxy.py
.....................s..................                                 [100%]
39 passed, 1 skipped in 1.10s
```

Windows跳过的POSIX用例不计为通过；初轮的两条警告是 Starlette TestClient/httpx 与 anyio BlockingPortal 弃用提示。

最终候选部署故障测试：

```text
python -m unittest -v test_fix_runtime
Ran 17 tests in 0.734s
OK
```

编译使用 `compile(p.read_bytes(), str(p), 'exec')`，未导入执行生产部署脚本。原始输出：

```text
COMPILE PASS backend/app/execution/workspace.py 132 lines
COMPILE PASS backend/app/execution/runtime_check.py 48 lines
COMPILE PASS backend/app/execution/office_render.py 155 lines
COMPILE PASS backend/tests/test_execution_runtime_resources.py 54 lines
COMPILE PASS backend/tests/test_office_render.py 61 lines
COMPILE PASS infra/local_codex_worker.py 88 lines
COMPILE PASS infra/install_codex_runtime.py 49 lines
COMPILE PASS infra/verify_codex_runtime.py 129 lines
COMPILE PASS infra/verify_codex_model.py 149 lines
COMPILE PASS scripts/migration245/fix_runtime.py 298 lines
COMPILE PASS scripts/migration245/test_fix_runtime.py 238 lines
```

主 Agent 提供的独立运行补充（不冒充 reviewer 执行）：最终候选 Linux10模块 `274 passed in 4.85s` 零skip，事务17通过；真实UID1001/1002的candidate-probe3通过 DOCX/XLSX PDF、原PPT2页2媒体502字符/2页渲染、无效PPT拒绝、脚本/图片格式与列出的只读隔离。主线程已目视检查原PPT渲染。最终部署及真实模型验收尚待，不从上述候选探针推断已完成。

本报告不执行部署、修复、真实模型调用或 review-approve，不向 `.needs-review` 写 clean。主 Agent 可据本报告对最终候选登记两阶段 PASS，再按合同完成最终安装及工具证据验收。


## 线上验收证据复核（部署后追加）

**结论：本轮已授权范围线上验收 PASS；Stage 1 PASS / Stage 2 PASS 保持。** 本轮仅只读审查保存的生产探针、事件日志、工具记录和实际产物；未改代码、未部署、未重新调用模型。review-status 显示当前与批准 candidate 均为 `10e0a86542ddf018e4478b68b1be29195cd8f972c3b505afca7c1ad446b16637`，changedFiles=[]，approved=true。

下面证据路径相对仓库根的 `output/runtime-fix-20261111/`，属私有验收材料，不应打入公开发布包。该目录的三个 `*-workspace.py` 是**部署前备份**，根 `report.json` 是旧候选路径探针；均未冒充安装后代码或探针。

| 验收项 | reviewer 已核对的证据 | 结论 |
| --- | --- | --- |
| 批准代码已安装 | `final-queues-health.json:1` 回执记录三个候选 SHA；reviewer 对批准本地源码统一LF后重新计算，workspace=`37e9cac126ca2c59315f4c45c880d6db151f87244ea2905bee43fe64c522279e`、runtime_check=`32c9a56fbca053dd6987f4a8ba14318773f25430772cb37842db77843f6998f8`、office_render=`8cbd0f825e385b748578c6fd4e5ce8577dff3219f60cf764ffe182bc94094c1b`，三项均MATCH True；`final-health.json:1` 记录国内/海外/账号daemon三处workspace和renderer一致、renderer均0755。 | PASS |
| 最终安装路径双身份功能 | `domestic-installed-report.json:1`、`overseas-installed-report.json:1` 分别为UID1001/1002与实际release下workspace路径；均通过内层命令、Python/Node、PNG/JPEG/WEBP、DOCX/XLSX读取与PDF渲染、损坏PPT拒绝、列出的路径隔离；原PPT2页/2媒体/502字符/2页渲染。 | PASS（指定探针范围） |
| 服务、队列与依赖健康 | `installed-health.json:1` 有两次启动自检成功和17个运行容器；`final-health.json:1` 六个服务active；`final-queues-health.json:1` 国内celery、海外overseas.cli均恢复，active/reserved/scheduled/database计数均0；两个ready接口HTTP200，PostgreSQL/Redis/MinIO均up。 | PASS |
| 既有配置与资料保护 | `installed-health.json:1` 六份服务env摘要比较均不变；`final-health.json:1` 原PPT未变、临时模型目录0。部署脚本及独立probe不写业务任务库的边界保持。 | PASS（已列配置、原件与临时目录） |
| 国内Python/Node及查看输入图 | session=`01a1c8c5-41d3-7443-b23b-7dc41511620c`，UID1001，50.479秒，`domestic-model/report.json:3`；`events.jsonl:7`、`:9` 明确两命令exit0且分别输出256×256；`tools.json:10` 同次工具脚本对`/work/input.png`调用view_image。 | PASS |
| 国内原生图片修改及交付 | `domestic-model/tools.json:16` 的call_id=`call_24b83a70c18546d3bd53d9038046ca3a`明确调用image_gen__imagegen，referenced_image_paths仅`/work/input.png`；`events.jsonl:11` 从该session generated_images复制生成文件，exit0；`report.json:11` collector一张1254×1254。reviewer实际解码并目视`domestic-result.png`：蓝底、中心白圆，与受控修改要求一致。 | PASS；原图256×256，成图1254×1254，不声称保持原像素尺寸 |
| 海外Skill与PPT实际读取/转换 | session=`01a1c8c5-413a-7960-bb1d-df5f64577811`，UID1002，64.313秒；`overseas-model/events.jsonl:5` Skill读取exit0；`:7` 证明使用`/opt/hx-tools/libreoffice`；`:9` ZIP/XML读取2页/2媒体并给出实际文字；`:11` LO转换exit0；`:13` Poppler/pdfinfo exit0、2页、171037字节。工具call_id及对应输出一致，非仅模型自报。 | PASS |
| 海外页面查看与产物 | `overseas-model/tools.json:80` 对page-1/page-2分别调用view_image；reviewer独立解析`product.pdf`确认2页，并解码/目视两张1601×900 PNG：A9蓝紫滑板车封面、中文产品信息页，字体与图片正常，最终回复与画面相符。 | PASS |
| 同session续轮真实读取 | `overseas-model/resume-events.jsonl:1` session未变，`:4` 新轮Python实际读取model-evidence.json并exit0，输出`HX-RUNTIME-c08399bf28ff`，`:5`最终回复同marker；`resume-tools.json:158`/`:169` 的call_id=`call_9bc2adf243874a018074592531be994e`调用与输出对应。 | PASS；不是仅从聊天上下文复述marker |

图像证据SHA-256：国内成图 `c272e4e241ed6417781e85f40430fa20ffb65eedb85ef7ed3af3ad44a628f632`；海外第一页 `8c24cf13839542c59a74e7e025c7aded428b221f7d47021fab0c4397f1e6b174`；第二页 `74a92743dcd2fe8584a53f25116910dfdb3051ea166f6f46a9256d935985f12f`。

证据保留边界：view_image/imagegen含base64的大型输出被脚本12000字符过滤器省略，不能声称该部分完整原始输出已归档。本次结合明确工具调用、命令成功日志、同session生成文件、collector结果和reviewer实际解码/目视进行交叉核验，达到本轮功能验收；未把任意call关键字或任务结束单独当成通过。业务页面按钮、端到端数据库投递、其它任意格式/Skill依赖及全量生产数据不变性未在本次独立脚本中穷尽验证，仍沿用原审查中明确的范围限制。
