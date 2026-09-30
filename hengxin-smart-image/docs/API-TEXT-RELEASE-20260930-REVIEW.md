# API 文案发布增量两阶段复审

- candidateId：`df867252aef8c9ce63b017833bbad073954e02840472f764f9dd625649e9becd`。
- 范围：功能提交 `835e3af` 之上的 8 个 `scripts/release/*api*text*.py` 发布/测试文件、`hengxin-smart-image/frontend/package.json` 版本及发布文档。已审业务功能不重审。
- 依据：AGENTS.md、code-review SKILL.md、docs/HARNESS-REVIEW.md、Product-Spec.md 文首、DEV-PLAN.md:3–9、API-TEXT-RELEASE-20260930.md:3–11。
- 结论：**Stage 1 PASS；Stage 2 PASS。** 当前发布增量未发现阻断问题。此结论批准代码准备阶段，不代表归档上传、实际镜像安装测试、生产迁移或在线验收已经完成。
- 开始及结束 review-status 的 currentId 均与上述 candidateId 相等，未发现审查期间代码变化。仅将首次失败报告保留为 `API-TEXT-RELEASE-20260930-REVIEW-FIRST.md` 并写本报告；由主 Agent 登记同一候选的批准凭据，不写 clean。

## Stage 1：Spec Compliance

下表路径除注明外相对仓库根目录。

| 逐项要求 | 结论及证据 |
| --- | --- |
| 修复首次 verify 主流程阻断 | 完整实现。api-text-verify.py:62 直接调用 validate_kind_column，:65 显式断言版本。test_api_text_verify.py:42–127 实际执行 main()；成功断言 5 服务、3 native 文件、4 前端文件、schema 和 3 公网资源；错误 0.2.13 文件与 manifest 哈希保持一致，因此拒绝结果确实来自版本断言。 |
| 0.2.14 与 0021→0022 | 完整实现。frontend/package.json:3；package-api-text.py:120–127 检查两份提示词、迁移、版本、四个运行脚本；api-text-deploy.py:66–84 固定迁移前后 schema。既有 backend/migrations/versions/0022_api_text_operation_kind.py:5–19 新增 nullable varchar(20)，回退保留字段；verify.py:15–16 验证约束。 |
| 提示词归档和 native 同步 | 完整实现。package-api-text.py:19–20、100、120–123 显式纳入两个 txt；api-text-runtime.py:12–15、93–106 复制 Python 与指定资源、拒绝缺失资源/符号链接、恢复可读权限及所属者。test_api_text_runtime.py:45–75 使用真实临时文件验证字节和缺失资源拒绝。Dockerfile.backend:8 复制完整 backend。 |
| 已提交、已审源码及白名单/哈希 | 完整实现。package-api-text.py:24–34 限定来源，:72–109 校验 Git HEAD、已审快照、源码字节、两次状态及 manifest SHA；:37–49 对归档回读精确比对。test_package_api_text.py:25–45 验证排除运行数据、敏感信息、路径穿越与脏树。实际发布包尚待提交后生成。 |
| 固定旧镜像并保留全部 Compose 配置 | 完整实现。api-text-runtime.py:47–70 从运行容器提取完整 config_files 链，核对 api-size-20260929-bf7dabd、环境、命令与依赖锁文件；新层仅 image/build。test_api_text_runtime.py:16–42 用 11 层链验证全部保留，未覆盖资源或网络字段。 |
| 实际镜像断网安装门禁 | 完整实现、真实执行待发布。api-text-deploy.py:57–66 使用 docker build、实际镜像 network none pytest、check=True，记录 IMAGE_ID 并在 deploy 前重新核对。:12–22 仅排除依赖仓库 infra 的六组工具测试和前端源码接口对照；对应源码依赖见 backend/tests/test_local_codex.py:9、test_local_codex_control.py:12、test_phase11a_checks.py:11、test_phase11a_environment.py:17、test_phase11a_supervisor.py:28；ports 测试依赖 local_codex 模块。本地 mock 测试不能作为实际镜像测试结果。 |
| 关闭接纳并排空、完整备份后迁移 | 完整实现。api-text-deploy.py:72–84 停 web/api/消费者，暂停 API，排空两类执行服务并确认零在途；停止 variants 后备份。api-text-runtime.py:73–90 执行 pg_dump、pg_restore --list，备份 native、入口、版本与完整配置，最后写 COMPLETE。test_api_text_deploy.py:123–162 覆盖备份失败不迁移、停止 variants 先于备份。 |
| fail-closed 与数据库不覆盖 | 完整实现。api-text-deploy.py:104–159：排空不明不重启 worker；开放后失败保留新执行器并关闭入口；普通回退恢复旧 app/入口/标记/Compose，保留 schema；回退失败再次关入口。test_api_text_deploy.py:117–155 模拟上述失败并验证状态与事件；无恢复业务数据库命令。 |
| active 标记更新、历史 API_SIZE 保留 | 完整实现。api-text-runtime.py:83–89、123–126；api-text-deploy.py:136–144；api-text-verify.py:9–12。test_api_text_runtime.py:77–92 与 test_api_text_deploy.py:106–112 检查真实文件发布和回退后 API_SIZE 原字节不变。 |
| 上线哈希、schema、配置、健康、公网检查 | 完整实现。api-text-verify.py:35–85 核对五服务镜像ID/文件/配置、native与前端SHA、nullable列、版本、服务、接纳状态、ready、公网HTML与JS/CSS及匿名401；新增 main 测试执行到输出。真实环境验证仍待主 Agent 发布后执行。 |
| 历史数据、新交互与无收费生成 | 发布边界匹配。docs/API-TEXT-RELEASE-20260930.md:7–9 要求读取历史及打开交互、不提交生成；verify.py:69–71 仅查询状态统计；脚本没有调用生成接口。历史任务详情与新交互的真实页面检查是部署后的验收项。 |
| 文档、UI、Spec 漂移 | 匹配。DEV-PLAN.md:3–9 明列准备、镜像测试、部署及在线验收；发布记录没有宣称本轮上线成功。frontend/package.json:3 仅版本变化，没有新增页面/API/表。业务 UI 已属 835e3af 审查范围，本次无新增视觉内容，邻居渲染对比不适用。 |

## Stage 2：Code Quality

- 代码质量通过：8 文件均可编译，60–171 行，低于 300 行；打包、运行操作、控制器、上线验证分别承担职责。api-text-deploy.py:104–159 明确错误恢复及再抛出；runtime.py:19–30 子进程 check=True、SQL ON_ERROR_STOP，命令参数数组传递。脚本使用正常 Python 启动；不得用 `python -O` 跳过这些断言门禁。
- 测试真实性通过：22 测试独立重跑；特别检查 verify main 正常和错误版本路径、实际 txt 复制、部分发布恢复、排空未知和开放后失败。Docker/SQL/systemd 使用 mock，证明控制逻辑，不证明远端命令可用；实际镜像/生产验收是后续独立门禁，不以此宣称通过。
- 安全/隐私通过（本次增量）：package-api-text.py:24–34 白名单排除运行数据，:52–69 扫文本、压缩与二进制资源，:83–108 校验源码及快照；runtime.py:40–44 限制哈希文件在源目录内，:99–106 阻止符号链接写入；deploy.py:34 私有 umask，runtime.py:74 备份目录700。私有配置只写本机私有工作目录，不打印环境值。对本次文件扫描未发现 eval、shell=True、前端秘密变量或硬编码凭据；固定 /opt 路径为明确部署目录，非个人路径泄漏；verify.py:60 的列名来自固定四项列表，无用户SQL拼接。
- 独立产物扫描：313 个已跟踪白名单源文件、当前选入的发布脚本、487 个生产静态文件通过现有 privacy_check / audit_asset；包含压缩资源解压扫描。此处不等同尚未生成的最终归档审计。
- 既有依赖风险保留：output/audit-api-text.json 原始统计 critical 0 / high 33 / moderate 30 / low 1。package.json 仅版本改动、无依赖升级；本次 PASS 不表示全项目无漏洞，未把已有审计风险当作新增发布缺陷。
- 未发现新增 scope creep 或需修复的 HIGH/MEDIUM。业务视觉不在本次版本字段/发布工具增量范围，不虚构浏览器复测结果。

## 验证原始证据

独立执行 `python -m unittest discover -s scripts/release -p 'test_*api_text*.py' -v`，exit 0，结尾原始输出：

```text
----------------------------------------------------------------------
Ran 22 tests in 0.299s

OK
```

独立 compile(source, filename, 'exec') 编译输出：

```text
scripts\release\api-text-deploy.py 163 compile PASS
scripts\release\api-text-runtime.py 126 compile PASS
scripts\release\api-text-verify.py 90 compile PASS
scripts\release\package-api-text.py 131 compile PASS
scripts\release\test_api_text_deploy.py 171 compile PASS
scripts\release\test_api_text_runtime.py 95 compile PASS
scripts\release\test_api_text_verify.py 130 compile PASS
scripts\release\test_package_api_text.py 60 compile PASS
Privacy PASS: 313 tracked selected sources; selected new release scripts;  487 production assets
```

读取已有 `hengxin-smart-image/frontend/build-release-api-text.log`，未重复构建。主 Agent 报告命令 exit 0，日志原始摘录：

```text
> hengxin-smart-image-frontend@0.2.14 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

vite v7.1.7 building for production...
transforming...
✓ 4485 modules transformed.
✓ built in 32.57s
```

日志包含既有 pnpm 配置字段忽略、静态/动态重复导入提示，构建完成。全量 release 历史 annotationoverlay 测试失败由主 Agent 记录，本次未重跑该无关套件，未声明全量 release 测试通过。未 SSH、未部署、未收费、未修改实现。后续由主 Agent 批准该快照并继续真实归档/镜像及上线验证。
