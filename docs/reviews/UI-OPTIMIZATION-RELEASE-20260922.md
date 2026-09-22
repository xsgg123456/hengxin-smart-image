# UI 优化发布增量审查

- candidateId：`5dda9462128054638255fa9225dd6d0670e68b9ccde33e7baef2926a76aa88df`。
- Stage 1：**PASS**。Stage 2：**PASS**。限本次发布增量与下列固定脚本，不代表已部署或全产品重新验收。
- 基线：`e206ceb1aae52d2728e7ccefa5be064143dde39053b06e7517db4cf90f624ed5`，承接 `output/sync-2026-09-22/review.md:3` 的合并审查及其明确列出的历史审查链。
- 独立执行 `review-status`，当前 ID 与送审一致，相对已批准基线的受控变化仅 `hengxin-smart-image/frontend/package.json:3`（0.2.0 → 0.2.1）。普通发布 Markdown 不在代码快照内，另读 `DEV-PLAN.md:748`、`Product-Spec-CHANGELOG.md:353` 及本次发布说明全文。
- 未修改实现、未提交、未部署、未登记批准、未写 clean。脚本是 ignored 流程产物，不能仅凭 candidateId 识别；批准其下列字节快照。

| 脚本 | SHA256 |
|---|---|
| output/ui-sync-release-20260922/package.py | `9c4721a67b53f29cc928ade8bbaf26b8c4428c86542fc691cbc2c50d8f5484c7` |
| output/ui-sync-release-20260922/deploy.py | `bcd52058c7276f836f17c6d0fe4da4af629e4777313b14b25304ad2015f65577` |

## Stage 1：Spec Compliance

本次逐项验收依据 `hengxin-smart-image/docs/UI-OPTIMIZATION-RELEASE-20260922.md:5–22`。下表 P 指上述 package.py，D 指上述 deploy.py。

| 验收项 | 结论及证据 |
|---|---|
| 版本、顺序与范围 | 完整。package.json:3 为 0.2.1；发布说明:5–10 与 DEV-PLAN.md:750 同为提交→部署→推送。P:3–4 按执行时 HEAD 标识包。提交前预检包 `output/ui-20260922-bc6f749` 只作打包验证；正式提交后必须重打包，不能将预检包当作提交产物。 |
| 保留既有 UI 和 API 模块 | 完整。review-status 的唯一代码差异为版本，无组件或后端增量，因此承接合并报告:13–21 的保留证据；没有新增页面、文案入口、API 或表。视觉布局未发生本轮变化，邻居视觉对比承接合并报告:30，不声称本轮重跑全 UI。 |
| 白名单、隐私、完整构建源 | 完整。P:9–16 限正式 dist 与 tracked 后端 app/migrations/必要锁文件、Dockerfile；P:19–24 拒绝 map/db/私钥/env、个人用户路径、已知密钥前缀和 Demo 代码标记。独立读预检 manifest 并核验源字节：568 文件全部 SHA256 一致，124 个基线 app 文件；samples/demo-images/tests/cache/env 路径命中为空。Dockerfile.backend:6–8 的 COPY 输入均在白名单。 |
| 现网基线与配置 | 完整。D:19–21 同时比较原镜像标签与全部 app Python 哈希映射；P:29–30 从 bc6f749 取基线并归一换行。D:28–30 沿用现容器 Compose 文件，:44 仅覆盖 API image/build，:53 比较前后完整环境变量。不修改 APP_IMAGE。运行时基线不匹配会在停服务前退出。 |
| Worker、outbox、数据库 | 完整。D:22–25 固定三容器 ID 与原生 CLI PID；:51 只执行 api 的 --no-deps --no-build，:66–67 再比对实例。没有迁移、数据库写命令或付费生成调用。0015 为发布前提，脚本不自行迁移/降级。 |
| 首页切换与文件验证 | 完整。D:54–61 先复制资源，再 os.replace 首页；不删除旧哈希资源。:62–70 校验前端文件、实际 HTTP 首页、就绪与后端 app 字节。预检包根目录非哈希文件仅三种图标与 index.html；当前 Nginx 配置 nginx.vps.conf:19 不启用 gzip_static。 |
| 备份与失败恢复 | 完整（静态路径验证）。D:31–40 先以 0700 目录、0600 env 备份，构建失败尚未替换服务；:73–82 捕获替换后异常，恢复旧首页、可选 gzip、发布清单，并以旧镜像只重建 api。保留业务数据与静态资源。未进行线上故障注入，不能宣称恢复演练已通过。 |
| 持续维护清单 | 完整。D:71–72 写 FRONTEND_RELEASE 与独立 API_RELEASE，记录 overlay、前镜像及 worker ID；不覆盖 API_IMAGE_RELEASE。发布说明:14 明确后续须沿用 composeOverride。 |
| 上线后的真实验收 | 计划完整，尚未执行。发布说明:10、:22 将鉴权、API 路由、真实登录页和实际编号列为发布后工作。D:63–65 仅证明首页和直连 API 健康，不能代替这些后续验收，尤其不能代替经 Web 反向代理访问 API 的检查。 |

部分实现、未实现、Spec 漂移：本次送审的发布准备范围内无；线上部署结果不在已完成结论内。Stage 1 无 HIGH，继续 Stage 2。

## Stage 2：Code Quality

- 质量：P 36 行、D 83 行，脚本语法解析通过；受控代码只变版本字段。命令使用参数列表，没有 shell 拼接执行；release 限制前缀及字母数字，归档使用 data filter，清单路径作 resolve containment 校验（D:4、:8、:13、:15）。无本轮新增注入执行或硬编码凭据。
- 安全：备份敏感配置限制权限（D:32–37），发布清单仅含文件哈希及镜像/实例信息，未输出 env 内容。打包隐私检查属于特定模式扫描，不等同任意秘密检测；本轮审查未发现新增泄漏。既有依赖审计 **high 62 / moderate 39 / low 5 / critical 0**（audit.json:4445–4450）继续明确保留，不将 critical 0 描述为无漏洞。本轮未改依赖或锁文件。
- 测试真实性：reviewer 独立核对预检 manifest 的 568 个摘要对应当前真实文件，而不是仅相信打包输出；独立类型检查退出 0。脚本回退只做控制流检查、无故障注入证据；生产容器环境、磁盘写入、Docker 重建与业务登录仍须部署执行后提供证据。既有单测和浏览器覆盖见基线报告:35–65，不重复计算为本轮独立执行。
- 视觉：版本字段与发布流程不改变渲染代码；本轮无新页面可与邻居进行新的差异比较。承接合并报告:30 的实际视觉证据，不能延伸为全响应式或真实登录验收。
- 非阻塞运行边界：脚本按普通 `python` 运行，不能使用关闭 assert 的优化模式；发布包依赖提交后固定源码和 dist，需按授权顺序重打包。回滚依赖文件系统和 Docker 可用，不覆盖进程被强杀或主机断电；备份留作人工恢复。以上不增加本轮产品范围。

## 编译及核验原始输出

reviewer 独立执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：标准输出为空，退出码 **0**。

主 Agent production 构建日志 `output/ui-sync-release-20260922/build.log` 末尾（reviewer 已读取）：

```text
dist/assets/index-BuxHZSNb.js                                                       1,619.43 kB │ gzip: 534.62 kB
✓ built in 32.02s
```

reviewer 独立语法与预检 manifest 核验原始输出：

```text
package.py syntax PASS 9c4721a67b53f29cc928ade8bbaf26b8c4428c86542fc691cbc2c50d8f5484c7
deploy.py syntax PASS bcd52058c7276f836f17c6d0fe4da4af629e4777313b14b25304ad2015f65577
manifest 568 baseline 124
excluded []
nonhash frontend ['frontend/apple-touch-icon.png', 'frontend/favicon.ico', 'frontend/favicon.svg', 'frontend/index.html']
source hash verification True
```

`git diff --check` 退出 0，只有 Git 的 CRLF→LF 提示。结论允许主 Agent 登记同一 candidate 的两阶段 PASS；不替代之后的提交、正式重打包、线上验收与 push 结果。脚本变化需按新 SHA256 复核。
