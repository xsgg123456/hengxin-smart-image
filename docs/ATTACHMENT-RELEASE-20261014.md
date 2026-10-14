# 附件下载发布记录（2026-10-14）

用户已授权提交 Git、使用最新部署脚本上线、按保留规则清理旧镜像，并验证生产附件下载及页面显示。

## 发布计划与验收

1. 版本更新至 0.2.34。发布范围为取消上传附件在线预览、资料卡片长文件名换行、原件浏览器流式下载及错误提示。保留生成图片展示、上传 500 MB 和附件数量上限。功能依据 Product-Spec 本轮附件下载条目。
2. 适配最新发布入口：从现网 0.2.33 升级，无数据库迁移；沿用实际生效的 `99-overseas-upload.conf`，保护其余原生配置；保持 API 3 GiB 和两层上传代理限制。独立审查、故障测试通过后提交。
3. 构建正式前端、进行依赖和发布包隐私审计；服务器实际安装镜像测试通过后，关闭海外接纳、排空任务、完成可校验备份，再切换 API、原生执行器和前端。
4. 使用最新 `release-retention` 包装器记录成功版本并清理：每个业务保留当前及上一个成功版本，同时保护容器引用、在途和失败候选；仅清理规则允许的本项目镜像及专用构建器缓存。
5. 验证生产源码与资源哈希、服务健康、代理、原生实际目录及无关业务不变；从正式页面检查资料卡片、工作台和长文件名，实际下载已有附件验证文件名/字节与原件一致。不得以 HEAD 或健康接口代替完整下载和视觉检查。

实施与验证证据见 `docs/ATTACHMENT-DOWNLOAD-VALIDATION-20261014.md`；发布结果将在实际部署后补记。

## 发布前实查
- 生产现版本 0.2.33；海外在途任务 0；两个原生服务生效目录均为 overseas-20261014-00720c0，99 配置已生效。海外 API 3,221,225,472 bytes；可用内存约 4 GiB，磁盘可用 65 GiB。
- 镜像台账 pending 为空；海外 current 为 00720c0、previous 为 7479264，当前清理预览无可删除项。部署成功后再推进保留台账。
- 0.2.34 正式前端构建成功（31.35 秒）。依赖审计 critical 0、high 70、moderate 48、low 5，既有依赖风险未在本轮升级处理。
- 将使用现有任务的 86,062,183 bytes Excel 和 47,131,519 bytes PPTX 验证下载，以数据库原件 SHA256 为比对基准。

## 发布入口验证

以下命令均在仓库根目录的 PowerShell 执行，只使用临时文件和模拟服务，不操作生产。本轮结果保存在会话工具的控制台输出中，未另存日志文件；不将历史日志冒充本轮日志。

专项回归命令：

```powershell
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_attachments.py scripts/release/test_overseas_upload.py scripts/release/test_overseas_upload_recovery.py scripts/release/test_package_overseas.py scripts/release/test_release_wiring.py -q
```

结果：106 passed、48 subtests passed。覆盖附件入口切换故障矩阵、配置退化拦截、99 指针更新及90/95保留、旧入口隔离、代理原文保持、恢复入口回归和打包必需文件。

发布目录全量命令：

```powershell
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release -q
```

结果：383 passed、1 skipped、165 subtests passed、1 failed。唯一失败为 `test_release_native.py:100` 的 `test_frontend_manifest_matches_seven_native_files`：测试期望 Compose 链末项为 annotation，实际已追加 materials。该项属于已记录的历史失败；此前证据日志为 `output/api-edit-review-tests.log` 和 `output/native-studio-release-tests.log`，保留规则文档也记录过 HEAD 复现。本轮未修改该测试及其实现，未把它计为通过。

历史命名测试不在默认发现范围内，另行执行：

```powershell
$releaseTests = Get-ChildItem scripts/release/*-tests.py | ForEach-Object { $_.FullName }
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest @releaseTests -q
```

结果：113 passed、3 skipped、26 subtests passed。

`hengxin-smart-image/backend/.venv/Scripts/python.exe -m compileall -q scripts/release` 与 `git diff --check` 均退出码0。以上离线验证不替代正式发布镜像安装测试和部署后验证。

## 部署结果：0.2.34 已上线

- Git 功能及发布提交 `3b09fbc`；审查候选 `e885f1039c2bf459ca78a90294e012615f80b66dbdf8cb0c35027a2e1d7f9460` 两阶段 PASS，报告见 `docs/reviews/ATTACHMENT-RELEASE-20261014.md`。
- 实际使用发布包内最新 `scripts/release/overseas-attachments-deploy.py`，依次执行 build、prepare、deploy；最外层使用最新 `release-retention.managed` 和共用台账，没有重放历史发布脚本。
- 发布包 `overseas-20261014-3b09fbc`：1,284 个文件，5,589,195 bytes，SHA256 `b09fde556a16cfe55d1298d17c2ede71e02508b9a8f5aad1bdaea13967e17601`；隐私、压缩包及服务器传输校验 PASS。
- 服务器实际镜像安装验证：577 个后端源码哈希一致，2193 passed、187 skipped、1 deselected（438.08 秒）；3 GiB 内存下上传容量专项 4 passed。镜像 ID `sha256:0336a72fbb4f3bafd1ccfd41e031e47ae0750fbf30077f17ce0c661750c44185`。
- 北京时间约 20:01:03 关闭海外接纳、排空后备份并切换；20:04:29 开始恢复代理并轮询公开入口生效，最终 PHASE=complete、deploy exit 0。原生 99 指针、生效目录、源码、Skills、挂载及前端资源全部验证；90/95 配置保留，国内与身份服务身份未变。无数据库迁移或业务数据删除。
- 备份 `/opt/hengxin-backups/overseas-20261014-3b09fbc`，COMPLETE 存在。三个公开健康/配置入口 HTTP 200，两层 500 MB 代理边界保持。

## 镜像保留与清理：已执行

- 海外 current 更新为 `3b09fbc`，previous 为 `00720c0`；国内与身份仍保留 `da722ad` / `c9bd4d2`。
- 自动清理已删除旧海外镜像 `hengxin-smart-image-backend:overseas-20261014-7479264`（`sha256:e4a0cc7c067063f5ba11e7f2e9f3a7a1f72c1d713843fd018d9c04ec1e650497`）。当前项目镜像仅上述四个；台账 pending 为空，再次 preview 的 remove 为空。
- 已执行专用 `hengxin-release` builder 的 2 GB 缓存保留清理；未使用全局 prune，未删除业务存储、数据库、备份或原生发布目录。清理结果来自 `/var/lib/hengxin-release/cleanup-result.json`，不是根据镜像日期推断。

## 生产下载与视觉验收

使用用户已登录的正式 Chrome 页面，刷新原任务 `c62d3c51-ad77-4807-8197-ff3597197a34` 后点击两个“下载原文件”。原任务保持待审核、版本1；未提交审核、创建业务任务或调用模型。

| 原件 | 实际下载字节 | SHA256 与数据库原件 |
|---|---:|---|
| PPTX 图片需求 | 47,131,519 | `6d31fffdf4152c28c7da4803c1b8a547cf8cc45075618ea9d88f0d8be8c71d08`，一致 |
| XLSX 竞品表格 | 86,062,183 | `0af5c45cd81bb9ff37452efaf75a30e725e66c2cb2dd45af9553aec87ac2b402`，一致 |

两份文件已在本机 Downloads 完整落盘，中文文件名保持。服务端 GET / HEAD 均200；按钮完成预检后恢复可用，显示“已发起下载，请在浏览器中查看进度。”。完整落盘与哈希校验才记为下载成功。浏览器自动化下载等待发生超时，之后用实际落盘文件完成独立校验；不把工具超时当作产品失败，也不据此宣称固定下载速率。

正式1920px页面截图目视核验：资料为两张卡片，完整名称未互相覆盖；不再显示预览、解析失败、版本选择或放大/新窗口入口。提交图需页面仍显示500 MB，设计人选仅姓名、没有搜索框，上传文案改为下载原件查看。

证据：`output/attachment-release-{build,prepare,deploy}.log`、`output/attachment-release-final-server.log`、`output/attachment-production-download-verification.json`；正式截图 `output/attachment-production-cards.png`、`output/attachment-production-download-feedback.png`、`output/attachment-production-create.png`。

验收边界：生产当前没有可进入工作台的 studio/completed 任务，未为验收改变现有任务审核状态；工作台素材/历史附件及390px长名布局的实际流程证据来自发布前隔离真实服务测试。此次浏览器视口覆盖未在既有Chrome标签生效，已恢复默认，没有将1920px截图当作线上手机验收。未向生产上传500 MB测试数据或做并发压测；500 MB真实边界在实际发布镜像隔离验证。
