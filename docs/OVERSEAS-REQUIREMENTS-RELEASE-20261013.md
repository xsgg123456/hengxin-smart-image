# 设计人工审核与资料阅读验收（2026-10-13）

## 范围与流程

按已确认预览实现海外运营提交、设计人工审核、退回运营修改重提，以及资料预览和鉴权下载。新提交只有设计通过后才能排队分析，后续保留方案确认和逐图审核。原有在途任务不回退。前端0.2.25，海外数据库0010，国内数据库0027。

## 发布前证据

- 前端301项测试通过；正式 `pnpm build` 包含类型检查，退出0。日志 `output/requirements-frontend-tests.log`、`output/requirements-build.log`。
- 后端2051 passed、17 skipped（宿主环境专用条件），退出0。日志 `output/requirements-backend-final-full-20261013.log`。跳过项不计验证通过。
- 真实 PostgreSQL、Redis、MinIO 和身份HTTP验证：PDF/DOCX/XLSX/CSV上传原件字节一致、未审核无AI、角色/任务范围、退回重提、并发幂等唯一分析作业、历史资料鉴权和国内数据未变；测试环境未启动外部AI。日志 `output/requirements-http-20261013.log`。
- 增量发布/打包失败注入38项通过，日志 `output/requirements-release-tests.log`。
- 正式入口6分支CSS依赖检查通过；构建资产逐字节隐私审计826文件通过。
- 依赖审计critical=0；现有依赖包含high/moderate项，本轮未宣称依赖零漏洞。审计 `output/requirements-audit.json`。
- 浏览器使用真实压缩构建及真实隔离API：PDF三页翻页、125%缩放、缩略图跳转；放大窗口文件切换；原件下载SHA256与上传文件一致；设计退回后运营可看到原因、修改说明并重新送审（任务版本1→2→3→4，设计再次通过后进入分析中）。截图 `output/requirements-qa/`。
- Word和表格提供安全内容阅读，明确标识非原始版式，原始格式通过鉴权下载本地软件核对。PDF为原件画布阅读，不执行文档脚本。

## 发布与线上验收

实际安装测试、独立审查和生产部署均已完成，最终结果见下。

- 安装门禁发现构建镜像内部分文件与发布包哈希不一致；发布构建禁用缓存，并在运行安装测试前逐项比对镜像内后端文件与发布清单，失败禁止切换。
- 构建上下文的文件元数据缓存也会复用旧字节；最终包解压使用 tar -xzmf（不恢复归档中的统一时间戳），随后仍由清单核验内容及镜像文件哈希，未删除或放宽安装门禁。

### 最终结果

- 已上线：0.2.25，发布 `overseas-20261013-a65b8b4`，代码提交 `823fc85`、`a65b8b4`。包 SHA256：`91bd1cdcae0f9ed962f8532deb8bb87929e8a3b385019f714712b026c4c609d8`。
- 最终镜像 504 项后端文件哈希全部匹配；安装测试 1798 passed、161 skipped、1 deselected、15 warnings，347.96s。隔离无网络安装容器未配置 PostgreSQL 等服务，因此相关条件项跳过；数据库、并发与真实HTTP另有前述隔离服务测试，不把跳过项计为通过。
- 最终发布脚本测试48项通过（`output/requirements-release-final.log`）。
- 海外数据库 `overseas_0010`；API、worker/outbox 运行正常，worker 并发5且仅订阅海外队列。国内业务及身份服务容器 ID 未变化。
- 备份：`/opt/hengxin-backups/overseas-20261013-a65b8b4`，数据库备份清单验证通过。
- 首次切换的工作进程就绪探测早于 Celery ready，入口按门禁保持关闭；待工作进程就绪后，重新执行相同镜像、清单、数据库、备份、空闲与未触及容器校验后继续。入口代理重载短暂503经有限重试后恢复，再执行完整公网核验。没有回退数据库、跳过检查或重启国内服务。日志 `output/requirements-production-resume-final.log`，服务器 `verification.json` 记录完成。
- 正式入口实查：提交页七节点、并排上传卡片、任务列表、旧任务详情、PDF原件画布及缩略图、放大阅读；控制台 error 为0。PDF worker HTTP 200、Content-Type application/javascript。
- 正式下载实际获得368541字节原PDF，SHA256与用户已有原件一致。只读查看已有生产任务，未触发付费分析或修改其状态。
- 生产当前没有待人工审核/退回任务，因此这两种页面状态及完整退回重提审批链以隔离真实API验证为依据，未冒称生产写入链已执行。原有任务不补插审核节点，新提交生效。
- 生产截图：`output/requirements-qa/production-materials.png`、`production-tasks.png`、`production-pdf.png`。浏览器桌面断点验收后已恢复默认尺寸。

