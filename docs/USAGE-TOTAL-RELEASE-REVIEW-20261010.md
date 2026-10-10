# 累计生成统计 0.2.21 发布增量独立审查

- 日期：2026-10-10；角色：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md` 和 `release-builder/SKILL.md`。
- candidateId：`bef57e4d4d30daba87afbeca666be809de61a18dcb18c47a5f40c18365b00c50`。审查开始、结束的 `review-status.currentId` 均相同，没有发现审查期间代码漂移。
- 范围：`frontend/package.json` 的版本增量、Product-Spec-CHANGELOG 发布记录、`scripts/release/package-usage-total.py`、`usage-total-deploy.py`、`usage-total-runtime.py`、`usage-total-verify.py` 及两个专项测试。复核所调用的既有打包和运行辅助函数。下文脚本路径相对 `scripts/release/`。
- 排除预存 `.agents/skills/dev-builder/SKILL.md` 修改。功能基线为已提交的 `16a79f6`；独立执行 `git diff --stat 16a79f6 -- hengxin-smart-image/backend hengxin-smart-image/frontend/src` 输出为空。既有业务 UI 和统计逻辑不重复宣称重新验收，其证据见 `docs/USAGE-TOTAL-REVIEW-20261010.md:1`。
- 本报告审查发布工具是否可进入正式打包和部署流程，不代表生产发布已完成。没有执行 SSH、部署、提交或修改实现。

## Stage 1 · Spec Compliance：PASS

逐项覆盖 `docs/USAGE-TOTAL-RELEASE-20261010.md:7` 的五项发布步骤和边界，以及 `Product-Spec.md:942` 的发布限制。

| 要求 | 结果与证据 |
| --- | --- |
| 独立提交发布增量，前端 0.2.21，保留无关改动 | 完整实现。`hengxin-smart-image/frontend/package.json:3` 为 0.2.21；`Product-Spec-CHANGELOG.md:595` 记录发布授权；`package-usage-total.py:35` 调用已提交检查，既有 `package-management.py:79` 仅允许已声明的预存 skill 修改。实际提交由主 Agent 后续执行。 |
| 白名单、已提交来源、审查凭据、SHA256 | 完整实现。`package-usage-total.py:13` 限定源码与四个辅助脚本，35–48 行取已提交 HEAD 内容并与本地归一化后比较、拒绝链接、扫描隐私；61–69 行记录 commit/candidate/文件哈希并复查 HEAD 和凭据；既有 `package-management.py:39` 拒绝归档越界并读回验证字节。 |
| 实际镜像安装测试通过后才允许部署，凭据绑定发行版 | 完整实现。`usage-total-deploy.py:25` 校验 release/schema/version 与文件哈希；42–54 行先删除旧凭据，构建后使用不可变 image ID、断网运行镜像内 pytest；38–39 行凭据包含镜像 ID 与 release.json SHA256；58–59 行部署前逐项匹配。真实服务器安装测试尚未执行，不能用本地工具单测替代。 |
| 备份入口、版本与 compose，只读数据库且不迁移 | 完整实现。`usage-total-runtime.py:59` 仅 SELECT schema；88–102 行创建不复用备份目录，保存旧配置、路径、API inspect、执行器身份、入口、package 和三个标记，最后写 COMPLETE。deploy 无 migrate、backfill、任务更新或通道暂停调用。 |
| 仅更换 HTTP API，保留运行配置 | 完整实现。`usage-total-runtime.py:63` 固定预期旧镜像，66–71 行比对原环境与命令，77–84 行仅覆盖 api image/build 并严格比较其余完整 compose；`usage-total-deploy.py:68` 只 up api 且 --no-deps；70–72 行校验新镜像、环境/命令/挂载/端口并检查 readiness。`hengxin-smart-image/backend/app/main.py:33` 生命周期无后台生成执行循环；`infra/Dockerfile.backend:11` 为 uvicorn HTTP 入口。 |
| API/CLI 执行器、队列、web 不重启；允许新任务自然进入 | 完整实现。`usage-total-runtime.py:14` 列出四类后台与 web，25–38 行捕获容器 ID/StartedAt、原生 MainPID/启动时间及 nginx 配置 inode/hash；deploy 的切换前、API ready 后、成功末尾、失败 finally 均比较身份（64、73、82、102 行）。没有任务总数必须不变、排空或阻止新任务进入的条件。 |
| 原子前端切换，旧静态资源保留，仅 nginx reload | 完整实现。`usage-total-runtime.py:105` 临时文件加 os.replace，112–125 行先安装资源并拒绝碰撞，再切入口/package，旧资源不删除；145 行仅 nginx -s reload。`usage-total-deploy.py:72–78` 在 API ready 后、API-only 验证前 reload，恢复 upstream 解析。 |
| 标记只代表实际更新的服务 | 完整实现。`usage-total-runtime.py:15` 和127行仅写 API_RELEASE、FRONTEND_RELEASE、USAGE_TOTAL_RELEASE；不更新 API_IMAGE_RELEASE 等执行器标记。`test_usage_total_deploy.py:157` 实际临时目录验证旧执行器标记和旧资源保留。 |
| 失败只回退 API 和前端，回退失败明确失败 | 完整实现。`usage-total-deploy.py:66` 在 compose 前标记可能已变更；80行在 publish 前标记可能部分发布；84–105 行独立尝试旧 API、前端恢复、reload，并汇总回退错误；旧 tag 必须仍匹配旧 ID。`usage-total-runtime.py:133` 恢复原入口/package/标记。故障测试覆盖 compose、ready、reload、publish、最终验证及 API 回退本身失败。 |
| 真实只读管理员统计、分页、公共入口与鉴权校验 | 完整实现。`usage-total-verify.py:19` 显式 REPEATABLE READ READ ONLY；21–28 行取真实生产管理员、临时覆盖身份依赖，无 mint token 或持久会话；34–68 行通过真实 ASGI GET 对账累计/首次/修改、日报、跨页事件和去重任务，验证20/50/100及筛选/第二页；70–73 行检查通道和清理关闭；95–120 行检查镜像内源码、schema、ready、标记、部署文件及公网入口/引用资源哈希和匿名401。真实生产响应由后续部署生成。 |
| 不付费生图、不删除业务数据、不更新原生代码、不推远端、不虚报登录 UI | 完整实现。上述工具仅执行构建、HTTP API替换、前端文件切换、只读校验；验证没有生成/采用/删除接口调用。`docs/USAGE-TOTAL-RELEASE-20261010.md:11` 明确登录态不可用时不宣称钉钉登录验收。 |

部分实现：无。未实现：无。新增无需求页面、API 或数据库表：无。此增量不更改 UI 模板/样式，引导与设计一致性沿用已批准功能快照。

## Stage 2 · Code Quality：PASS

- 结构与规模：四个新增工具分别负责打包、编排、服务器文件/容器操作、只读验证，78/122/146/128 行，两个测试51/187行；均低于300行。`usage-total-deploy.py:84` 回退独立执行，避免 API 回退异常阻止前端恢复。
- 安全：`usage-total-runtime.py:19` 私有 JSON 为0600，88行备份目录0700；`usage-total-deploy.py:109` umask077；调用 subprocess 使用参数列表，无 shell=True、eval 或用户输入拼接 SQL。`usage-total-verify.py:86` 校验发行版格式；既有 `management-runtime.py:40` 检查manifest文件路径边界及哈希。只读身份替换局限于独立校验进程，不开放新的网络鉴权入口。
- 隐私：独立对当前实际选中源码366项、四个辅助脚本及 dist 523项执行既有严格扫描，全部通过。确切负向测试 fixture 例外仅位于 `package-delivery.py:24`，50行逐条替换且重复即拒绝；没有全测试目录豁免。白名单不纳入 .env、数据库、用户目录或 session 文件（`test_package_usage_total.py:12`）。
- 测试真实性：本地33测试与10子测试独立复跑通过，覆盖内容筛选/归档往返/隐私拒绝、凭据漂移、旧凭据清除、镜像ID与断网参数、配置保留、执行器变化阻断、部分发布和回退失败。`test_usage_total_deploy.py:157` 对临时文件系统真实发布和恢复；Docker/systemd调用采用隔离 mock，不能据此宣称服务器安装、容器切换或公网验证已实测。
- 视觉对比：本发布增量无 UI 代码变化，相对16a79f6源码diff为空；本轮未重新打开页面。功能视觉和邻居页面实测证据明确归属前轮报告 `docs/USAGE-TOTAL-REVIEW-20261010.md:30`，正式公网资源验证由 `usage-total-verify.py:110` 执行。
- 依赖：未改依赖或锁文件。本轮原始 `output/release/usage-total-prep/dependency-audit.json` 为 critical0/high36/moderate34/low1；不能表述为“无已知漏洞”，它是既有依赖风险，超出本次发布工具增量。符合 release-builder 的无 critical 门槛。

## 编译与验证原始输出

系统 Python 初次测试因未安装 pytest 失败，随后使用项目 backend 虚拟环境成功，不隐藏首次环境错误：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

独立命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_package_usage_total.py scripts/release/test_usage_total_deploy.py scripts/release/test_package_management.py scripts/release/test_package_delivery.py -q`

```text
.................................                              [100%]
33 passed, 10 subtests passed in 1.77s
```

独立 AST 语法检查与实际文件扫描：

```text
COMPILE PASS package-usage-total.py: 78 lines
COMPILE PASS test_package_usage_total.py: 51 lines
COMPILE PASS test_usage_total_deploy.py: 187 lines
COMPILE PASS usage-total-deploy.py: 122 lines
COMPILE PASS usage-total-runtime.py: 146 lines
COMPILE PASS usage-total-verify.py: 128 lines
PRIVACY PASS sources=366 helpers=4 assets=523
```

读取主 Agent 本轮原始日志 `output/release/usage-total-prep/build.log`（不是 reviewer 重跑前端构建）：

```text
dist/assets/index-CMgexOgT.js                                                       670.46 kB │ gzip: 230.78 kB
dist/assets/echarts-DSKumXTW.js                                                     748.03 kB │ gzip: 244.46 kB
dist/assets/index.vue_vue_type_style_index_0_lang-D82PisoR.js                       813.93 kB │ gzip: 275.57 kB
dist/assets/index-3OWe9E-h.js                                                       963.15 kB │ gzip: 307.72 kB
✓ built in 38.74s
```

主 Agent 工具测试原始日志 `output/release/usage-total-prep/tool-tests.log`：

```text
...........................................................                                   [100%]
59 passed, 51 subtests passed in 1.26s
```

HIGH/MEDIUM 新增阻断缺陷：无。两阶段 PASS 仅适用于记录的 candidate 和上述范围；主 Agent 需用 review-approve 登记相同快照后提交，实际镜像安装和生产验证仍必须执行并保存证据。
