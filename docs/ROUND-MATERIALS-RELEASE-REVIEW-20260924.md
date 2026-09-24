# 执行材料发布增量独立审查（2026-09-24）

- candidateId：`2771bb95df27365459c36c64909f55ee33ae38713537bb34ab8991284701c477`。
- 已批准功能基线：`705f639df9cd82a877e006e6aa58580f1bf5961d3a2d929ae27c901e1c045b20`；完整功能两阶段证据见 `docs/ROUND-MATERIALS-CANVAS-FINAL-REVIEW-20260924.md:1`。
- 按 code-review skill 执行；先核对发布需求，再审代码质量和独立测试。本次无实现修改、生产操作、提交或登记批准。
- **Stage 1 PASS；Stage 2 PASS。增量内无未关闭 HIGH / MEDIUM。** 结论为发布代码审查通过，不代表生产已部署、安装镜像测试或线上验收通过。

## 快照与范围

开始及结束的 `harness.py review-status` 均为以上 candidateId；与批准基线只有以下 8 个文件不同，未发现审查期间代码漂移：

1. `hengxin-smart-image/frontend/package.json`
2. `scripts/release/image-inputs-deploy.sh`
3. `scripts/release/image-inputs-frontend.py`
4. `scripts/release/image-inputs-native.py`
5. `scripts/release/image-inputs-worker.py`
6. `scripts/release/package-image-inputs.py`
7. `scripts/release/test_release_native.py`
8. `scripts/release/test_release_recovery.py`

需求依据：`hengxin-smart-image/docs/ROUND-MATERIALS-CANVAS-RELEASE-20260924.md:3`、`:7` 至 `:11`，及 `docs/ROUND-MATERIALS-RELEASE-PREP-20260924.md:3` 至 `:11`。已读 `Product-Spec.md:745` 的功能边界；本次后来授权的发布要求以主 Agent 交接和发布文档为准。两份 PERFORMANCE 文档和原有 29 个功能文件不在增量审查范围。

## Stage 1：Spec Compliance

| 发布要求 | 结论与证据 |
| --- | --- |
| 0.2.6、materials 发布标识 | 匹配。`frontend/package.json:3` 为 0.2.6；`package-image-inputs.py:16` 与 `image-inputs-deploy.sh:6` 使用相同日期和七位提交哈希格式。这里 frontend 路径省略 `hengxin-smart-image/`，其余脚本省略 `scripts/release/`。 |
| 沿用实际完整 Compose overlay 链 | 匹配。`image-inputs-deploy.sh:20` 至 `:25` 追加当前 annotation overlay，再加新 overlay；`:43` 至 `:59` 在中断前核对 live image、环境、命令。`image-inputs-frontend.py:34` 至 `:38` 写回相同基链。 |
| API、两个 outbox、API worker 使用同一镜像 | 匹配。`image-inputs-deploy.sh:37` 生成共用 image/build 配置，`:157` 至 `:159` 启动四服务；既有 migrate 配置保留但无迁移调用，`:69`、`:152` 要求数据库 0017。 |
| 安装测试固定镜像，先验证再中断 | 匹配。`image-inputs-deploy.sh:64` 无网络 compileall；`:67` 要求 `INSTALL_TEST_IMAGE_ID` 精确等于当前镜像 ID，早于 `:131` 停接。具体专项运行和凭据写入由主 Agent 在服务器完成，本审查没有伪称已执行。 |
| 只更新七个 native execution 文件 | 匹配。`image-inputs-native.py:8` 至 `:11` 固定七文件；`:55` 至 `:59` 只按白名单安装；`image-inputs-frontend.py:45` 至 `:48` 记录同一集合。材料模块导入链覆盖在这七个文件中，其余依赖为既有模块。真实 manifest 测试通过。 |
| 不改模型、Skill、凭据、并发、超时 | 匹配。native 白名单不含配置/环境；新 Compose override 只替换 image/build（`image-inputs-deploy.sh:37`），不重写环境/命令；worker pool 校验仍为 5（`image-inputs-worker.py:45`）。 |
| 停接、排空后备份和替换 | 匹配。`image-inputs-deploy.sh:73` 至 `:76` 前置无在途/PID 检查，`:131` 至 `:148` 停 web/API/outbox、暂停、排空 API/native，之后数据库及应用备份；`:153` 才开始修改 native。 |
| 保存既有文件、删除本次新增文件，部分安装可退 | 匹配。`image-inputs-native.py:23` 至 `:37` 保存存在标志和内容，`:62` 至 `:72` 恢复旧内容或删除原本缺失文件。真实临时文件系统测试覆盖完整/部分安装回退、幂等恢复、备份失败不改原件。 |
| 上线导入新模块、回退兼容旧版 | 匹配。`image-inputs-worker.py:89` 至 `:93` 仅新验证模式导入材料采集/回填/runner；上线 `image-inputs-deploy.sh:156` 使用新模式，回退 `:121` 使用旧模式，不要求旧版存在新增模块。 |
| 回退失败不开放、保留数据库及业务数据 | 匹配。`image-inputs-deploy.sh:84` 至 `:88` 失败保持入口关闭和 paused；`:107` native restore、`:110` 应用还原、`:111` manifest 恢复，然后 `:117` 至 `:125` 旧服务健康通过才开放。`:116` 明确保留数据库，没有 pg_restore 数据恢复调用。11 个实际 recover 函数桩场景独立通过。 |
| 包白名单和隐私审计保留 | 匹配。`package-image-inputs.py:22` 至 `:35` 白名单增加 native helper；`:39` 至 `:49` 拒绝链接、数据库/密钥/映射/字节码、凭据名及敏感内容；`:54` 至 `:69` 哈希 manifest 和标准化归档。新增 helper 不包含运行数据。实际打包审计仍由主 Agent 提交/批准后执行。 |
| 生产安装哈希、队列、健康、公开页及历史回填 | 代码承接匹配。`image-inputs-deploy.sh:31` 至 `:39` 包哈希检查，`:156` 至 `:167` 新旧队列/健康及页面检查；安装文件二次哈希、鉴权展示和用户指定历史回填属于发布操作验收，由主 Agent 按发布文档第 4/5 步另行完成，脚本没有主动发起生成或扩大回填范围。 |

完整实现见上表；增量内部分实现/未实现：无。Spec 漂移：未新增业务页面、API 或表；本次是已批准功能的发布机制与版本增量。UI 代码相对批准基线未变，视觉和交互沿用最终功能审查报告证据，本次不重复浏览器视觉验收。

## Stage 2：Code Quality、安全与测试真实性

- 单一职责和规模：新增 `image-inputs-native.py:14`、`:23`、`:40`、`:55`、`:62` 分离路径校验/备份/原子替换/安装/恢复；77 行，测试 104 行，其余受审脚本均少于 300 行。固定 FILES 和明确动作入口，未引入外部依赖。
- 安全：`image-inputs-native.py:15` 拒绝白名单之外路径，`:18` 拒绝文件链接与越界解析；`:43` 拒绝既有临时文件，`:50` 原子替换；`:64` 拒绝缺项、多项和非 bool 标志。恢复失败由 deploy `:107` 传入保持关闭分支。新增内容未发现硬编码密钥、动态 eval 或拼接外部 SQL。
- 凭据边界：`image-inputs-worker.py:16` 至 `:19` 沿用既有进程环境传递，不打印环境；部署产生的 private compose 文件沿用 `image-inputs-deploy.sh:3` 的 umask 077。代码中 `/opt`、`/proc` 为部署目标路径，非泄露开发者私有路径。
- 测试真实性：`test_release_native.py:17` 至 `:39` 创建真实目录和旧/新内容，实际调用安装/恢复；`:52` 删除最后一个源文件触发中途失败，不是 mock 成功；`:68`、`:78` 验证非法 manifest，`:87` 运行真实 frontend helper 校验七文件 manifest 和 overlay。
- 恢复测试 `test_release_recovery.py:10` 提取实际 recover 函数，`:54` 注入九个关键失败节点，`:68` 检查成功恢复校验先于开放，`:70` 检查 native 恢复先于重启，`:73` 检查 web 启动失败重新关闭。它们是控制流桩测试，不冒充真实 Docker/systemd 生产验收。
- 验证限制：本机 Windows 文件测试未实测 Linux uid/gid；代码通过 copy2/chown/chmod 保存所有者和权限（`image-inputs-native.py:33` 至 `:36`、`:46` 至 `:49`）。服务器安装和服务联调仍待主 Agent 执行，不影响本次增量代码两阶段结论。

## 原始验证输出

独立使用 bundled Python `C:/Users/82358/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` 运行 `scripts/release/test_release_native.py`，exit 0：

```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.261s

OK
```

独立设置 `BASH=D:/Apps/Git/bin/bash.exe`，运行 `scripts/release/test_release_recovery.py`，exit 0：

```text
PASS success
PASS api-drain
PASS native_restore
PASS app_restore
PASS old_start
PASS old_verify
PASS api-resume
PASS api-verify
PASS native_verify
PASS health
PASS web_start
```

独立对六个受审 Python 脚本执行 ast.parse，对部署 shell 执行 `bash -n`：

```text
PYTHON_AST_OK 6
BASH_SYNTAX_EXIT=0
```

`git diff --check` exit 0，仅 Git 既有 CRLF 转 LF 提示，无差异格式错误。危险模式扫描未检出新增 eval/HTML 注入/前端敏感变量或硬编码密钥。

主 Agent 提供的正式构建原始日志已读：`output/materials-release-20260924/frontend-build.log:4`、`:419`。本次不重复构建未改变的 UI；日志原文：

```text
> hengxin-smart-image-frontend@0.2.6 build
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4469 modules transformed.
✓ built in 34.95s
```

日志包含既有 npm 配置提示和 dingtalk-login 静态/动态导入分包提示，未见构建失败。依赖锁文件无增量；主 Agent 提供的 audit 既有高危项不记为本次修复或新增通过证据。

收尾 review-status 原始关键字段：

```json
{"currentId":"2771bb95df27365459c36c64909f55ee33ae38713537bb34ab8991284701c477","reviewedId":"705f639df9cd82a877e006e6aa58580f1bf5961d3a2d929ae27c901e1c045b20","approved":false}
```

报告只批准上述候选的八文件发布增量，与已批准功能基线合并使用。由主 Agent 以本报告登记同一 candidateId 的两阶段 PASS；不得用旧报告批准其它候选，不写 `.needs-review`。生产安装测试、打包审计、部署和历史回填的最终结果须单独记录。
