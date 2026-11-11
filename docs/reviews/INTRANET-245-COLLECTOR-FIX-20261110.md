# 内网 245 采集器目录排除修复审查

- candidateId：`897e538cc43f3286484363de2327be412bde6c5ef368ed73dd025cf6e57d80ab`。
- 范围：`hengxin-smart-image/scripts/migration245/collect_runtime.py`（下称 C）及 `collect_runtime_test.py`（下称 T）。仅审查目录排除修复及其回归影响，不重新批准 transport、安装器或整个迁移。
- 依据：`Product-Spec.md:3`；`docs/INTRANET-245-PLAN-20261110.md:89`、`:98`、`:102`、`:104` 的完整当前代码、哈希清单、排除历史数据、旧机只读要求；主 Agent 提供的本次修复范围。
- 方法：读取 code-review skill、完整阅读两文件、执行本地单测、额外目录矩阵及错误主机测试、内存语法编译。未连接服务器，未修改代码。
- 结论：**Stage 1 PASS；Stage 2 PASS。** 无 HIGH / MEDIUM 阻断项。本结论不代表生产采集已成功、114 个实际遗漏文件已回收或新机安装已完成；这些必须由主 Agent 根据真实执行结果验收。

## 快照

审查开始及报告写入前的 `review-status` 均返回上述 currentId，changedFiles 仅为本次两文件，未观察到审查中代码变化。原始文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| C | `EB57E85AD7A7348FA9626FD6751CC001E1D80BF0CA2B9DE35E0DB0FA910B61A6` |
| T | `8D1CFDE702C908D51D7997EAAA797AEC027080F9803579A487114B38817B776C` |

旧报告把递归排除 execution 判为通过的结论不再适用于本次目录完整性判断；本报告按当前实现重新验证。主 Agent 负责登记同一 candidateId 的 review-approve；本审查没有写 clean 或自行批准。

## Stage 1 — Spec Compliance：PASS

| 条目 | 结论与证据 |
|---|---|
| 完整包含应用 execution/sessions 源码 | 完整实现。C:31–44 提取哈希函数，C:35 仅在代码根层合并 ROOT_DATA；应用子目录不受该数据目录名单影响。T:12–13、20–21 精确断言 app/execution、app/overseas/execution、app/sessions 和根配置全部存在。新增测试实跑通过。 |
| 根级任务、运行态、授权、会话、日志不进代码清单 | 完整实现。C:19、35–37 剪枝六个根级目录。T:14–15 覆盖 execution/runtime/.codex/grants；审查额外矩阵覆盖六个 ROOT_DATA 在根级全部排除、在 app 内全部保留。 |
| 缓存、虚拟环境和仓库目录仍递归排除 | 完整实现。C:18、35–37 对五个 EXCLUDED 在所有层级剪枝；额外矩阵分别在根和 app 下放置文件，全部排除。 |
| 四个代码根及来源主机限制保持 | 完整实现。C:12–17 固定四根；C:48–49 拒绝错误 hostname，C:75–76 校验 cwd 白名单和 resolve。额外测试验证错误主机在任何 subprocess 前抛错，固定根数为 4。 |
| 代码输出为摘要，不复制源码正文 | 完整实现本次文件清单范围。C:42–43 仅保存 SHA-256、长度、权限；额外测试逐项比对实际字节摘要和元数据。C:40–41 保持跳过链接及非普通文件。 |
| 旧机只读及既有私有传输约定 | 本次修复保持。C:27–28、50–94 仅查询服务与读取配置，新增 C:31–44 无写入。C:98 仍需通过既有受保护 transport 使用；完整 collect 输出还包含运行环境和配置正文（C:69–80、88、93），不能误称整个采集结果只有哈希，也不能直接输出到公开控制台。transport 不在本次审查范围。 |
| Spec 漂移 | 未发现。新增纯哈希函数及回归测试对应完整代码清单要求（C:31、89；T:9），没有新增产品行为或扩大四根来源范围。 |
| UI、设计与引导真实性 | 不适用。两文件为无 UI 的采集脚本与测试（C:1、97；T:8、24），不需要页面或邻居视觉比较。 |

本范围未发现部分实现、未实现或 HIGH 项，因此进入 Stage 2。

## Stage 2 — Code Quality：PASS

- 结构：C 共 98 行、T 共 25 行，均小于 300 行。C:31–44 的 file_hashes 将目录遍历与运行环境读取分离，函数命名和 ROOT_DATA 作用域明确；不引入第三方依赖或类型规避。
- 测试真实性：T:10–21 创建真实临时目录，直接调用生产函数并比较完整路径集合；旧递归排除规则会漏掉三个 keep 路径而导致断言失败。测试并非用不可达输入绕过问题。额外矩阵覆盖 8 个应保留、16 个应排除文件，同时验证摘要、长度、权限；错误 hostname 测试实际进入 collect 并断言没有调用 run。
- 安全扫描：两文件检索 eval/exec、shell=True、password 赋值、常见硬编码 API key 前缀及危险 HTML 模式，无匹配。完整逐行阅读确认 C:28 使用参数数组调用子进程；C:36–41 仍不跟随目录或文件符号链接。本修复未扩大 CODE_ROOTS，也未新增执行命令或秘密日志。
- 非阻断测试边界：本地 Windows 临时目录不能证明真实 Linux 文件树或远程运行结果；本次未重新做 symlink 实测。相关防护代码没有改变（C:34、37、40），本次目录层级逻辑已通过实际文件树验证。没有把本地单测称为生产验收。

## 编译与验证原始输出

命令：`python -m unittest discover -s hengxin-smart-image/scripts/migration245 -p collect_runtime_test.py -v`；随后用内置 `compile(bytes, filename, 'exec')` 编译两文件。退出码 0，原始输出：

```text
test_execution_source_is_kept_and_root_runtime_data_is_excluded (collect_runtime_test.CodeInventoryTests.test_execution_source_is_kept_and_root_runtime_data_is_excluded) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.018s

OK
Syntax compile PASS: collect_runtime.py, collect_runtime_test.py
```

独立审查补充验证（临时目录及 mock，不连接网络），退出码 0：

```text
PASS exclusion matrix: 8 kept, 16 omitted; hashes/size/mode verified
PASS host guard: rejected before subprocess
PASS fixed code roots: 4
```

报告前快照原始输出：

```json
{"currentId": "897e538cc43f3286484363de2327be412bde6c5ef368ed73dd025cf6e57d80ab", "reviewedId": "cd3df50e4eb053f62984c511693cd2e564b7a5665d0f912b882e63661cd7993e", "changedFiles": ["hengxin-smart-image/scripts/migration245/collect_runtime.py", "hengxin-smart-image/scripts/migration245/collect_runtime_test.py"], "approved": false}
```
