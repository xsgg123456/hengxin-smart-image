# 海外成品库删除发布增量审查

- candidateId：`cfb7af207533421d89b7fef0d29e1c4b90056c535b01589969516da7f84bf705`
- Stage 1：PASS；Stage 2：PASS。
- 范围：`scripts/release/package-archive-deletion.py`、`scripts/release/overseas-archive-deletion-deploy.py`、`scripts/release/test_archive_deletion_release.py`、`hengxin-smart-image/frontend/package.json` 的 0.2.42 版本增量。读取继承模块以核对真实调用关系，不重新批准范围外业务实现。
- 依据：Product-Spec.md:1221 的删除需求及其后认证保护要求；docs/ARCHIVE-DELETE-IMPLEMENTATION-20261019.md 的发布合同。业务提交 897ad3e 的功能审查引用 ARCHIVE-DELETE-REVIEW-FINAL-20261019.md；本报告不替代生产验收。
- 独立 review-status 返回 currentId 与送审编号一致，changedFiles 恰为上述四个文件。审查期间未发现代码快照变化；未修改实现、提交或操作生产。

## Stage 1：Spec Compliance

| 发布验收条目 | 结论与证据 |
| --- | --- |
| 固定基线、版本和已审核打包 | 完整实现。部署脚本:19 固定 0.2.41 → 0.2.42、0018 → 0019，:104 核对两个 release 标记、认证热修复镜像、健康及资源参数。打包脚本:10、:12、:22 将新版本、迁移和必需文件绑定到实际执行的 p 模块；package-overseas.py:180 的 build 检查已提交源码及审查快照，采集全部 backend/app Python 文件，因此认证客户端、映射与删除代码均进入包；新增认证客户端另有必需项约束。frontend/package.json:3 仅版本改变。 |
| 停止接纳、排空及可恢复备份 | 完整实现。部署脚本:210 将新函数绑定到 d 全局；继承 overseas-upload-deploy.py:183 的 deploy 依次关闭入口、停止 API、排空执行者、调用备份后迁移；overseas-studio-ux-deploy.py:116 的 backup 验证独立恢复和原行指纹。没有把旧迁移函数作为闭包遗留调用。 |
| 只增加删除凭据表、原业务行保持 | 完整实现。部署脚本:79 检查国内 0030、海外 0018 及既有表；:173 要求已完成备份和执行者停止，比较备份前指纹，仅运行 overseas_0019，验证新增表集合恰为 overseas_archive_deletions、全部原表行指纹不变。失败不自动降级数据库。测试:45 覆盖缺备份、未排空、schema/config 漂移、迁移异常、原行变化、额外表和原表缺失。 |
| 海外 API、worker、维护循环及共享前端同时更新 | 完整实现。部署脚本:26 分别接受 auth worker 与旧 outbox 目录；:92 从每个实际 ExecStart 精确替换目录，保留 worker 参数；:128 只写 WorkingDirectory/ExecStart，:201 验证生效 drop-in。继承 deploy:230、:231、:233、:246 顺序切换原生服务、API、启动服务并发布前端。测试:85 和 :164 覆盖分离目录、认证 drop-in 及 worker 参数保持。 |
| 国内、身份、凭据代理和业务文件保持 | 完整实现。部署脚本:25、:53、:59、:75 对不同国内目录及 broker 的 PID、配置文件、权限、socket inode、源码摘要取快照；:141 保存并比较。settings:48 记录环境、安全参数及附属组，切换:128 和安装:201 比较。继承 overseas-upload-resources.py:34 校验国内/身份拓扑、挂载、原生配置及海外无关容器均不变。代理没有重启或写入指令。 |
| 健康、版本、文件摘要和失败封闭 | 完整实现。部署脚本:201 调用继承 installed；overseas-upload-deploy.py:156 校验 API/native 源码哈希、进程 cwd、健康和资源；:183 的部署异常处理重新关闭入口、保留阶段证据且禁止盲目重放。脚本:215 拒绝优化模式，避免断言失效。 |
| 生产现有归档不作破坏性测试 | 完整实现。新增脚本无业务 DELETE 请求；新增测试使用 tmp_path、Mock，不触及生产。生产页面仅打开确认并取消仍是主 Agent 部署后验收事项。 |

部分实现、未实现、Spec 漂移：未发现。新增表来自已批准业务迁移；本次新增代码仅包装和部署该功能。UI 一致性、引导真实性及邻居页面视觉比较：N/A，本次 package.json 只有版本号变化，无页面/样式/文案修改；业务视觉证据由前述功能审查承担。

## Stage 2：Code Quality

- 质量：PASS。新增文件分别 26、218、215 行，均低于 300 行；包装、部署与测试职责分离。部署函数通过末尾显式模块赋值接入继承链，调用方 d.main/deploy 在其模块全局查找新函数，安装校验链仍保留先前资源约束（部署脚本:198、:210）。
- 测试真实性：PASS。测试:45 的迁移前后指纹、:85 的真实 systemd ExecStart 文本形态、:132 的漂移矩阵、:164 的不同 cwd、:188 的 Python -O 子进程、:199 的递归脚本导入打包检查均对应可达路径。独立执行新增与既有发布测试共 85 项及 48 个 subtests 通过。测试模拟系统服务，不声称已验证真实服务器切换。
- 安全扫描：PASS。三个新增脚本未命中 eval、前端密钥前缀、硬编码密码/令牌、shell=True 等扫描项。部署脚本:28 的 socket/auth 绝对路径是固定生产校验目标，:59 只读取认证文件元数据，不读凭据内容；:33 SQL 仅拼固定表常量；:92 使用已固定目录和受控 systemd argv，没有用户输入 shell 拼接。
- 既有依赖风险：frontend/package.json:3 未改变依赖。此次构建日志中的 pnpm 配置警告和审计的 36 high/34 moderate/1 low 为现有输出，不应描述成“无漏洞”；critical 为 0。本次没有引入依赖变更，不以该证据宣称全部依赖安全。
- 发布门禁：入口:218 保留 release-retention.managed；release-retention.py 的 managed 在执行 deploy 前核对台账 current 与真实镜像，漂移即阻断。主 Agent 告知已经另行按恢复凭据对账，本审查未远程复核该操作；生产发布仍须实际通过门禁。

## 验证原始输出

独立执行：

```text
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_archive_deletion_release.py scripts/release/test_studio_ux_release.py -q -p no:cacheprovider
.....................................................................................            [100%]
85 passed, 48 subtests passed in 2.65s
```

独立 `python -m py_compile` 检查三个新增脚本成功，无输出。初次系统 Python 运行 pytest 返回 `No module named pytest`，随后使用项目虚拟环境完成上述验证。

读取本次前端编译原始日志 `output/archive-delete-release-build.log`：

```text
> hengxin-smart-image-frontend@0.2.42 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 32.65s
```

读取审计原始日志 `output/archive-delete-release-audit.log`：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
71 vulnerabilities found
Severity: 1 low | 34 moderate | 36 high
```

结论仅批准上述 candidate 的发布代码增量。主 Agent 可用相同 candidateId 和本报告登记两阶段 PASS；打包产物、真实安装和生产页面验收须继续按发布合同执行，不得把本报告作为已上线证明。
