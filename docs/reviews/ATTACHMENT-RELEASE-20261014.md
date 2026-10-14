# 附件下载发布增量独立审查

- candidateId：`e885f1039c2bf459ca78a90294e012615f80b66dbdf8cb0c35027a2e1d7f9460`
- 前次批准：`a77465aaf536cb052a33d2cd3198be27019496f52a0af51b8dcbe37cf9ac1d51`；功能审查见 `docs/reviews/ATTACHMENT-DOWNLOAD-20261014.md:1`。
- 范围：相对前次批准的六个文件：`hengxin-smart-image/frontend/package.json`，`scripts/release/overseas-attachments-deploy.py`、`overseas-upload-deploy.py`、`package-overseas.py`、`test_overseas_attachments.py`、`test_package_overseas.py`。依赖调用链纳入只读核查。
- 依据：`docs/ATTACHMENT-RELEASE-20261014.md:5`、`Product-Spec.md:1137`、code-review skill 与 `docs/HARNESS-REVIEW.md:7`。开始和结束 review-status 均为本 candidateId，差异仅上述六文件。审查不修改业务代码、不操作生产、不提交、不登记批准。

## Stage 1：PASS（发布代码增量）

| 发布要求 | 结论及证据 |
|---|---|
| 0.2.33 升至 0.2.34、保留本体已审功能 | 完整实现。`frontend/package.json:3`（相对 hengxin-smart-image/）、`scripts/release/overseas-attachments-deploy.py:15`、`package-overseas.py:21`；快照差异证明业务源码和 UI 未变。版本与旧入口隔离测试 `test_overseas_attachments.py:131` 通过。 |
| 无迁移、现网基线与 API 3 GiB | 完整实现。`overseas-upload-deploy.py:41` 只读检查两数据库版本；新入口 `overseas-attachments-deploy.py:36` 检查现版本、00720c0、API 健康和内存。`overseas-upload-resources.py:4` 固定 3 GiB；没有新增迁移命令。故障测试 `test_overseas_attachments.py:90` 验证漂移拒绝。 |
| 99 指针切换且保护其它配置 | 完整实现。新入口 `overseas-attachments-deploy.py:16` 设置实际共享 runtime 的 DROP；`:43` 至 `:51` 检查文件内容、已加载路径和更高优先级覆盖；`overseas-update-runtime.py:162` 只写 DROP。测试 `test_overseas_attachments.py:146` 真正写临时 99 文件并验证旧 90/95 字节不变。 |
| 保留双层代理限制 | 完整实现。`overseas-attachments-deploy.py:27` 校验唯一 location、upstream 和全部限制；`:56` 验证包内 include 与固定指令一致，保存原配置。`test_overseas_attachments.py:116` 比对实际字节并验证错误 include 被拒绝。 |
| 正式包、审查和隐私门禁 | 完整实现。`package-overseas.py:44` 要求新入口，`:164` 从已提交且已审源码构建，`:179` 隐私检查，`:191` manifest 绑定版本、提交、candidate 和逐文件 hash；`:152` 回读归档核验。`test_package_overseas.py:46`、`:80`、`:125`、`:157` 覆盖缺失文件、敏感资源、篡改、版本和新入口入包。实际发布包须提交后另行生成，当前未声称已打包。 |
| 安装测试、容量、停止接纳、排空、备份后切换 | 完整实现。`overseas-upload-deploy.py:286` 调用安装构建与容量测试；`overseas-deploy.py:33` 验证镜像源码并在镜像内执行测试；`overseas-upload-deploy.py:91` 校验安装/容量凭据，`:186` 重验准备基线，`:219` 起依次关闭入口、停止 API、排空、校验备份再切换。`overseas-hotfix-tests.py:112` 成功顺序、`:136` 故障矩阵经 `test_overseas_attachments.py:29` 继承到新入口，独立执行通过。 |
| 最新保留策略 | 完整实现。`overseas-attachments-deploy.py:75` 在部署异常处理之外调用最新 managed；`release-retention.py:57` 串行锁及 pending 保护，成功返回后写 receipt、推进台账再清理；`release-retention-state.py:63` 只在业务镜像改变时推进 current/previous；`release-retention-docker.py:79` 保护所有容器、当前/上一个和 pending，`:112` 每次删除前重验且不强删，仅目标仓库镜像与专用 builder 缓存。全套中的保留测试通过。 |
| 源码/前端/健康/无关业务检查 | 完整实现。`overseas-upload-deploy.py:159` 镜像与原生源码 hash、进程 cwd、队列、服务健康；`:142` 无关业务资源和其它原生配置不变；`:242` 起发布前后验证前端/代理/公网。 |
| 生产完整下载及页面目视 | 发布后验收项，尚未执行，不计为现有代码缺陷或已完成验收。`docs/ATTACHMENT-RELEASE-20261014.md:11` 明确要求实际原件 bytes/name 和页面；本次派发禁止生产操作。主 Agent 部署后必须补证据，不能以本报告替代生产验收。 |

本范围部分实现/未实现：无。Spec 漂移：无；授权上线的来源是发布记录，不沿用上一轮“本地、不自动部署”的旧执行范围。UI/引导增量：无，UI 一致性和实际视觉比较沿用上一候选独立审查报告的实测证据，本轮未重复打开页面。

## Stage 2：PASS（无新增阻断问题）

- 质量：新入口 75 行，复用已测切换流程；原切换脚本 299 行，未超过 skill 的 300 行标准。版本扩展点位于 `overseas-upload-deploy.py:24`、`:28`，旧入口仍保持旧版本常量。模块隔离由 `test_overseas_attachments.py:131` 验证。
- 安全：新增脚本扫描未发现硬编码凭据、eval、shell=True 或私钥。新入口 `overseas-attachments-deploy.py:73` 在 retention 写入前拒绝 Python 优化模式；原入口 `overseas-upload-deploy.py:278` 再拒绝优化模式并要求 root。release 标识由 `:282` 限定，命令使用参数数组。`test_overseas_attachments.py:35` 实际子进程覆盖 -O 和 PYTHONOPTIMIZE。
- 故障安全：`overseas-upload-deploy.py:259` 失败后重新关闭海外接纳、停止 API，保留故障阶段，不自动恢复数据库或停止可能接纳新工作的执行器；`:187` 拒绝重放。`test_overseas_attachments.py:44` 确认 preflight 失败时无关闭/备份副作用。retention 清理失败位于部署事务外，`release-retention.py:22` 不把成功部署转入失败处理。
- 测试真实性：临时文件系统验证指针及代理；故障矩阵验证时序与禁用动作；打包测试读回真实 tar 并比对 hash。安装、数据库、systemd 的单元测试使用 mock，不能证明远端已安装；实际安装测试入口与生产验收仍需主 Agent 后续执行。
- 既有测试失败（不归因本增量）：`scripts/release/test_release_native.py:100` 断言最后 overlay 是 annotation，但 `image-inputs-frontend.py:43` 最后一项已经是 materials。独立执行全套复现；`git diff HEAD --` 对该测试、image-inputs-frontend.py、image-inputs-native.py 输出为空，确认三文件与 HEAD 一致。旧 0.2.6 流程不在新入口调用链，故不阻断本发布增量；不得声称 release 全套全绿。

## 验证原始输出

独立执行专项（exit 0）：

```text
python -m pytest scripts/release/test_overseas_attachments.py scripts/release/test_package_overseas.py scripts/release/test_release_retention.py -q
................................................ [ 68%]
......................                                                   [100%]
70 passed, 24 subtests passed in 2.82s
```

独立执行发布全套（exit 1）：

```text
python -m pytest scripts/release -q
>       self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E       AssertionError: False is not true
scripts\release\test_release_native.py:100: AssertionError
FAILED scripts/release/test_release_native.py::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed, 383 passed, 1 skipped, 165 subtests passed in 11.79s
```

独立 Python 编译（exit 0，原始 stdout/stderr 为空）：

```text
python -m py_compile scripts/release/overseas-attachments-deploy.py scripts/release/overseas-upload-deploy.py scripts/release/package-overseas.py scripts/release/test_overseas_attachments.py scripts/release/test_package_overseas.py
```

读取本候选前端正式构建日志 `hengxin-smart-image/frontend/attachment-release-build.log:3`、`:571`（非审查者重跑）：

```text
> hengxin-smart-image-frontend@0.2.34 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4723 modules transformed.
✓ built in 31.35s
```

最终：本 candidate 的 Stage 1 PASS、Stage 2 PASS。主 Agent 可按协议登记同一快照；批准代码不等于生产发布/下载/视觉验收完成。
