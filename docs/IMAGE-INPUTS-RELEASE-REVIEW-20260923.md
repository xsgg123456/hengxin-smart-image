# 图片整改生产发布增量独立审查

日期：2026-09-23。使用 code-review 与 release-builder 技能。Stage 1 **PASS**；Stage 2 **PASS**，本增量未发现 HIGH / MEDIUM 阻断项。结论为发布代码可进入执行，不是生产部署成功证明。

最终 candidateId：`fae9bcd2ee24175304d2981f25e535a9746ff6440abda36c99ff89ba80545357`。最初交接为 `2e4bf0a4a6a9d13b9d990d5cc4333f5dba6b9ef0c431453f1199d398e179faec`；审查期间开发服务改写自动生成文件，已通知主 Agent。主 Agent 停止服务并重新 prepare；reviewer 最终独立读取 review-status，currentId 与最终编号一致，并逐项比较 candidate.files 与当前快照，差异为空。只批准最终编号。

范围：`frontend/package.json` 版本及 `scripts/release/` 四脚本、发布授权和计划。三项 UI 功能继承 `docs/IMAGE-INPUTS-REVIEW-20260923.md:5`（提交 ab7de22）；API 多图及迁移继承 `docs/API-REVISION-MULTIREF-REVIEW-20260923.md:3`（提交 b5d8398）。本轮不重新验收整个产品、不操作生产、不修复实现、不提交。原有 PERFORMANCE 文档不在范围。

## Stage 1：需求符合性

| 验收项 | 结论与证据 |
|---|---|
| 授权及版本 | 完整实现。`Product-Spec.md:3`、`DEV-PLAN.md:3` 明确既有站点发布、0017、两份 native 源码范围；`hengxin-smart-image/frontend/package.json:3` 为 0.2.4，构建日志同版。 |
| 真实运行配置匹配 | 完整实现。`scripts/release/image-inputs-deploy.sh:19` 合并实际旧 overlays；`:43` 比对四服务运行状态、image、显式环境和 command，不输出环境值。生产事实来自主 Agent 只读实查，本 reviewer 未再次连接生产。 |
| 停止接纳、排空、不强停 | 完整实现。部署脚本 `:65` 预拒绝非终态 API，`:114` 关闭 HTTP/outbox 后执行排空。`image-inputs-worker.py:54` 取消消费并检查队列、active/reserved/scheduled 与 DB；未知或超时拒绝停止。native `:97` 调用既有 `backend/app/worker/maintenance.py:30` 的排空保护。只有空闲确认后才停止两个 worker。 |
| 备份和0017保留数据 | 完整实现。部署脚本 `:60` 拒绝已有备份，`:124` dump 并用 pg_restore --list 校验；`:128` 备份旧前端与 manifest；`:136` 迁移前设置保守失败标记。`backend/migrations/versions/0017_api_revision_snapshot.py:12` 仅添加可空 JSON 列。回退无数据库覆盖或 downgrade。 |
| native 仅两文件、API五并发 | 完整实现。部署脚本 `:144` 明确只更新 prompts.py 与 image_revision_prompt.py，并保持属主/权限；worker helper `:49` 核对 API 池5与专属队列，`:108` 核对 native 队列和心跳；旧 environment/command 继承不变。 |
| 失败关闭 HTTP、保留 schema/数据 | 完整实现。部署脚本 `:78`、`:84` 回退前再次排空，忙碌直接保守停止回退；`:99` 仅未迁移时恢复 HTTP，迁移后保留暂停及关闭 HTTP。恢复旧文件/镜像而非覆盖数据库。故障回退未在生产注入演练，不声称真实回退已验证。 |
| 保留旧哈希静态资源、最后入口切换 | 完整实现。`image-inputs-frontend.py:12` 追加复制资源，不清空目录；`:25` 清理过时 gzip 首页；`:27` 用 replace 切入口。独立临时目录安装 fixture 通过，见下文。 |
| 产物及安装测试门槛 | 完整实现。`package-image-inputs.py:15` 要求当前批准快照，`:24` 白名单源码/迁移/配置及正式 dist，排除 Demo 图片，`:38` 拒绝敏感后缀和密钥/个人路径模式；`:48` 记录全部文件哈希。部署脚本 `:30` 核验包文件，`:56` 无网络 compileall，`:59` 要求安装测试凭据匹配本次镜像 ID，先于服务中断。实际安装专项测试及线上验收由主 Agent 执行后记录。 |

部分实现、未实现、Spec 漂移：本次发布增量未发现。UI 无新设计变更，继承上述功能审查的视觉比较；另外读取 `output/image-inputs-20260923/release-browser.log:2` 的实际生产构建六组浏览器 PASS，接口数据仍为隔离契约模拟，不代表生产登录后业务验证。

## Stage 2：代码质量、安全及验证

- 四脚本均少于300行，分别负责打包、编排、worker 控制、前端安装；参数限制、命令数组及路径校验明确，未发现新增 eval、shell 拼接用户输入或硬编码凭据。证据：部署脚本 `:6`、`:19`、`:32`；worker helper `:21`。私有 compose 输出受部署脚本 `:3` 的 umask 077 保护。
- 未发现本增量新增安全问题。依赖审计原始结果为 critical=0、high=33、moderate=30、low=1，见 `output/image-inputs-20260923/release-audit.json` 的 metadata.vulnerabilities；不称零漏洞，本轮未修改依赖。
- 安装凭据必须由真实的镜像内专项测试成功后写入；脚本只验证镜像 ID，不替代测试本身（部署脚本 `:58`）。发布后哈希、0017、鉴权401、公开健康及登录页仍需按 `hengxin-smart-image/docs/IMAGE-INPUTS-RELEASE-20260923.md:10` 执行。未运行收费生成。

编译原始输出（独立读取 `output/image-inputs-20260923/release-build.log:4` 及尾部）：

```text
> hengxin-smart-image-frontend@0.2.4 build
> vue-tsc --noEmit && vite build
🚀 API_URL = /api/v1
vite v7.1.7 building for production...
✓ 4445 modules transformed.
✓ built in 30.21s
```

reviewer 独立执行的原始输出：

```text
3 release Python scripts AST PASS
FRONTEND_INSTALL_FIXTURE_PASS: old assets retained; entry switched; stale gzip removed; native manifest limited to 2 files
```

Shell `bash -n` 为主 Agent 提供的服务器纯语法检查证据，reviewer 未在生产执行。初次本地 Python launcher 不可用，改用 bundled Python 后上述独立检查成功。回退故障注入、真正安装镜像及生产线上验收尚不属于本报告的已执行测试，不得把两阶段 PASS 写成已上线。主 Agent 应对同一最终 candidateId 用 review-approve 登记本报告；不写 clean。
