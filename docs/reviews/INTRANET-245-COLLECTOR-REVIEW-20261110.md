# 内网 245 运行时采集器审查

- 最终 candidateId：`35daacf21ffa831956e65e60f8a07250a0837e6e4184096cee7109338fda2ce8`。
- 范围仅 `hengxin-smart-image/scripts/migration245/collect_runtime.py`（下称 C）与 `transport.py`（下称 T）。`data_copy.py` 虽出现在全仓候选变更清单中，**不在本报告批准范围**。
- 依据：主 Agent 提供的用户授权、`docs/INTRANET-245-PLAN-20261110.md:7`、`:17`、`:20`、`:89`、`:98`、`:102`、`:104`；已确认 Product-Spec.md 存在，本次不重新审查既有产品功能。
- 方法：完整静态逐行审查、无网络本地替身测试、内存编译与 Paramiko 5.0.0 实现核查。未连接任何服务器、未运行真实采集、未修复代码、未提交。
- 结论：**Stage 1 PASS；Stage 2 PASS。可以在主 Agent 核准同一快照及指定脚本路径后执行本次运行元数据采集。此结论不代表迁移完成，也不授权运行未审模块。**

## 快照变更与复核

初始候选 `9f92ff57a855c45269f06a258867bb841c20577b7f5477ad864894ba1cfd926f` 存在无目标通道超时、源代码根未限制的问题；中间候选 `05befd3c7273084cd80aa4ca4eb47db82140de84fe758a7e07051fa14c7bcb33` 补充超时和源根约束，但目标仅 stat、跟随链接的问题仍在。已向主 Agent 反馈。主 Agent 修改后，重新读取两个完整文件并复核上述最终候选；没有以旧结论覆盖新版本。

最终原始文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| C | `F2205A319A352245FA482D8AB3EA6DD627298E4A995A2265E0EC001BE72E6AF8` |
| T | `E3792B1A011BA747016A8F88821E2F31A96F4CEF6E6F38C727F8A2D749E47C6B` |

报告写入前运行 review-status，currentId 与最终 candidateId 一致。未登记 review-approve，未向 .needs-review 写 clean。

## Stage 1：Spec Compliance — PASS

| 验收项 | 结论与证据 |
|---|---|
| 旧机只读，不安装、归档、停服、改配置 | 完整实现。C:27–28、34–35、44–46 仅调用 docker ps/inspect 与 systemctl show；C:51–88 只读 proc、配置及文件哈希；T:102 使用 python3 -B 标准输入执行，不在旧机落脚本或 pyc。没有数据库导出、服务变更命令。 |
| 固定两台主机、原 SSH key 与 known_hosts 强校验 | 完整实现。T:15–30 采用 SSHClient 系统 known_hosts + RejectPolicy，固定 IP/key，禁用 agent 和额外 key 搜索，核验 hostname；C:32 再校验旧机身份。此为代码验证，未实测远程身份。 |
| 实际容器与七服务有效配置 | 完整实现当前采集范围。C:11、20–23、34–65 筛三组 Compose 项目并要求 16 容器，逐个读取七服务的实际 PID/environ/cmdline/cwd，inactive 或 PID 无效退出；C:62–72 保存 unit/drop-in 与指定 nginx/AppArmor 配置。后续配置转换不在范围。 |
| 只采集授权代码根，排除业务数据及授权会话 | 完整实现本次固定来源。C:12–19、59–60 将 cwd 限定四个已确认发布代码根，拒绝路径解析变化；C:75–81 不跟随链接并剪枝 execution/sessions/grants/logs/runtime/.codex 等。未访问 /home/codex 授权根、数据库、任务对象存储。这里只保存代码哈希，不复制代码文件内容。显式 token-grants 名称的增强建议见下。 |
| 当前原生代码与前端版本摘要 | 完整实现当前采集范围。C:74–88 保存普通文件 SHA-256/长度/权限及指定前端 release.json。原生代码或容器镜像实体复制、完整交付包链接清单属于后续模块，未据此宣称完成。 |
| 凭据不入本地代码包、不打印 | 完整实现指定入口。C:92 仅向私有 SSH stdout 输出整体结果；T:63–89 经内存流直接写目标，日志只有目标名称、字节数、哈希和耗时，stderr 不回显。本地测试用哨兵秘密验证成功与错误输出均不含原内容。不得将 C 单独直接运行到用户控制台。 |
| 目标路径 guard、私有权限、禁止覆盖 | 完整实现。T:34–37 拒绝路径分隔符和点路径；T:51–60 lstat 核验全部列明祖先为 root 所有真实目录且不允许组/其他用户写，normalize 必须保持原路径，目标根无组/其他权限；T:61–62 用 wx 独占新建并在写入前 chmod 0600。链接、宽权限、解析变化、同名文件替身测试均拒绝。 |
| 完整性错误退出 | 完整实现。T:80–87 对源非零状态、任何 stderr、目标 SHA-256 不一致抛错；对应本地替身失败用例均通过。失败留下的私有候选文件不等于获准产物，重试不得覆盖。 |
| 超时与输出阻塞 | 满足本次采集入口。C:28 子进程 45 秒；T:21–24 连接/auth/banner/channel/hostname 有时限，T:50 SFTP 60 秒，T:63、84 命令 60 秒，T:69 传输循环检查 30 分钟上限。stdout/stderr 顺序读取可能遇到输出窗口背压，但不再无限等待无数据的 stdout。循环上限不是独立看门狗，不能据此承诺精确 30 分钟强制终止旧端 Python。 |
| UI、视觉、引导真实性 | 不适用：两文件都是运维脚本，无页面和设计稿，不需邻居页面截图。 |
| Spec 漂移 | 未发现本次范围新增产品功能。身份/Skills 数据复制、部署、域名切换均未作为已实现能力审查。 |

完整实现如上；本次限定范围无 HIGH、无未实现阻断项。服务器运行结果仍须执行后验收，不能用本地替身证明真实服务器已经成功。

## Stage 2：Code Quality — PASS

- 结构：C 共 92 行、T 共 106 行，分别负责采集和传输，均小于 300 行；C:27、31、T:15、34、40、95 职责明确。纯 Python 无 any，未使用动态 eval/exec 或 shell=True。
- 安全：T:84 对目标 shell 参数使用 shlex.quote；C:28 以 argv 调用子进程；T:18 拒绝未知 host key；T:82 不回显来源错误。对两个完整文件的密钥样式、eval/exec、shell=True、password、危险 HTML 模式检索无命中（rg 返回 1、输出空）；人工阅读未发现硬编码秘密，IP、key 文件名和发布目录属于已授权连接配置。
- 测试真实性：本地替身实际调用 T:40 的 transfer，而非只测试摘要函数；覆盖独占写入、权限/链接 guard、源错误、stderr 脱敏、目标哈希差异及正常字节流。没有声称替身验证了真实 SSH/SFTP 或 Linux 路径语义；wx 的排他标志同时查阅本机 Paramiko SFTPClient.open 实现确认。
- 超时 API 依据：[Paramiko SFTP 文档](https://docs.paramiko.org/en/stable/api/sftp.html) 支持通过 get_channel 设置超时；[Channel 文档](https://docs.paramiko.org/en/stable/api/channel.html) 说明通道超时和窗口背压。最终实现已显式设置关键通道时限。
- LOW，C:18–19：可以显式增加 `token-grants` 名称排除，防止未来在代码根下出现同名目录。当前真实授权根在 /home/codex 且不属于四个 CODE_ROOTS，此项不阻断本次固定采集。
- LOW，T:100–102：CLI 只核验脚本 basename，并不能证明任意目录同名脚本就是本次已审版本。主 Agent 应使用本报告范围内绝对路径和快照执行；未来可将入口绑定同目录解析后的脚本路径。
- LOW，T:43–44、90–92：目标连接在 try 外，目标连接失败时来源连接没有显式 finally 关闭；一次性 CLI 退出会释放连接，建议后续改成统一生命周期管理。此问题不造成旧机写入或凭据输出。

## 编译及本地验证原始输出

通过 Python compile(bytes, filename, 'exec') 在内存中编译两文件，未生成代码文件；随后调用传输函数的无网络替身用例。命令退出码 0，原始 stdout：

```text
compile PASS: collect_runtime.py
compile PASS: transport.py
PASS basename rejection: 6 cases
PASS transport success
PASS transport symlink
PASS transport public
PASS transport normalize
PASS transport existing
PASS transport exit
PASS transport stderr
PASS transport checksum
```

没有执行生产功能测试；没有测试或批准 data_copy.py。仅主 Agent 可按同一最终候选、限定范围和本报告两阶段 PASS 登记批准；其他模块仍须独立审查。
