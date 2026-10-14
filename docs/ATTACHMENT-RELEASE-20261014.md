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
