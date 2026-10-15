# 国内代理重载等待独立审查

- candidateId：`5396e6962780aecacb48f0f5ba24f4cdbd8eeda9cf1bf286eabdbbf142b29164`
- 范围：相对已审提交 `217926d` 的 `scripts/release/domestic-gate.py`、`scripts/release/test_domestic_safety.py` 全文及差异；读取 `domestic-deploy.py`、运行器、镜像准备与台账调用上下文。合同为 `docs/DOMESTIC-TASK-DELETION-20261015.md:48`。完整产品基线沿用 `docs/reviews/DOMESTIC-TASK-DELETION-20261015-FINAL.md`，本次没有重新声称完成全产品测试。
- 结论：**Stage 1 PASS；Stage 2 PASS**。未发现本次范围内 HIGH / MEDIUM 缺陷。审查期间两份受控文件未变化；结束时 currentId 与派发编号相同。未操作生产、未修代码、未登记批准凭据。

## Stage 1：Spec Compliance

| 合同条目 | 结论与证据 |
| --- | --- |
| 重载后容许异步收敛，统一30秒期限 | 完整实现。`domestic-gate.py:48` 在循环外建立 monotonic deadline，每次请求与轮末都校验剩余时间；每轮仅短暂等待。30秒指每次路由验证预算，不包括之前的重载命令或整个部署。 |
| 关流两路径×三个入口同轮503 | 完整实现。`domestic-gate.py:12`、`:51`、`:74`，每轮重置 matched；本机18080、直连本机TLS、公网两个路径共六次全部匹配才返回，不能跨轮累计成功。`test_domestic_safety.py:43` 验证入口与事件路径数量，`:55` 验证一次失败后完整重查。 |
| 开流三入口健康200 | 完整实现。`domestic-gate.py:78` 先恢复两份文件、重载，再只取健康路径验证三个入口200。独立补充检查实际调用顺序；部署仍继续执行公开入口与前端校验（`domestic-deploy.py:85`）。 |
| 请求受剩余预算约束；网络故障重试但不放行 | 完整实现。`domestic-gate.py:58` 同一 min(5,remaining) 同时传 curl 与 subprocess；运行器 `management-runtime.py:20` 将 timeout 原样传 subprocess.run，check=True。`:65` 捕获连接/超时异常后将本轮标为不匹配。故障用例 `test_domestic_safety.py:72` 验证6秒预算只产生5秒、1秒两次调用；补充检查常态错误码耗尽期限、瞬态异常后恢复。 |
| 保留发布次序和失败保护 | 完整实现。`domestic-deploy.py:59` 关流完成才停API、排空、备份；`:69`、`:79` 再确认关流；`:92` 失败保存恢复凭据并再尝试关流，不追加未知执行器强停。独立注入首次关流和开流失败，均无 VERIFIED；首次关流失败无 stop。 |
| UI、引导与 Spec 漂移 | 无UI改动，无新增产品行为。相对217926d的backend/frontend/infra diff为空；本次仅调整合同已写的代理等待。设计及视觉邻居对比不适用，既有前端沿用基线报告，不伪称本次浏览器复验。 |

部分实现、未实现：无（仅上述增量合同）。Nginx重载确实存在新旧worker交接阶段，官方说明见 [Nginx 控制文档](https://nginx.org/en/docs/control.html)。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
| --- | --- |
| 结构、命名与错误处理 | PASS。`domestic-gate.py:48` 提取共用验证，开关流复用；源码82行、测试184行，均小于300行。deadline不随重试重置；异常不能转为成功。 |
| 测试真实性 | PASS。`test_domestic_safety.py:55` 分别参数化200和503，故意令同一轮第三个入口失败，断言整轮重试；`:74` 用异常和推进时钟检查实际剩余预算。原部署故障测试位于 `test_domestic_deploy.py:74`；reviewer另执行7个补充场景，覆盖持久错误、瞬态网络恢复、open调用顺序及close/open失败传播。模拟只证明控制逻辑，不冒称真实代理已经通过新版本部署。 |
| 安全 | PASS。两份文件扫描未命中eval、前端注入、密钥/令牌模式。`domestic-gate.py:62` 使用参数列表，不经shell；域名和路径为既定常量。`release-retention.py:60` 拒绝Python优化模式，避免assert门禁被禁用。未改变SQL、文件删除及凭据处理。 |
| 时限边界 | PASS。`domestic-gate.py:68` 即使最终探测返回预期，若已过期限也失败。操作系统调度/进程启动可能存在微小墙钟超额，代码不据此放行；不能把请求预算表述为整个发布的硬实时30秒上限。 |

## 独立验证原始输出

项目解释器执行以下命令，exit 0：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scripts/release/test_domestic_package.py scripts/release/test_domestic_deploy.py scripts/release/test_domestic_safety.py
.........................                                                [100%]
25 passed in 0.65s
```

reviewer通过stdin运行隔离补充断言（monkeypatch时钟/网络/部署fixture，临时目录；无生产调用），并用Python内建compile编译两份源文件，exit 0：

```text
DOMESTIC_GATE_REQUIRES_OPERATOR_INSPECTION
DOMESTIC_RECOVERY_REQUIRED_NO_EXECUTOR_FORCE_STOP
DOMESTIC_RECOVERY_REQUIRED_NO_EXECUTOR_FORCE_STOP
SUPPLEMENTAL_PROXY_CHECKS 7 PASS
COMPILE domestic-gate.py PASS
COMPILE test_domestic_safety.py PASS
```

前三行是主动注入门禁故障的预期输出。本次无需重建未变更的前端；不将既有全套结果计入本次25项。

## 同镜像安装测试复用意见（部署约束，非已执行验收）

可以复用**同一不可变ImageID**的既有安装结果。`hengxin-smart-image/infra/Dockerfile.backend:1` 固定基础镜像，`:6`、`:8` 只复制backend；本次镜像输入目录相对217926d无改动。`member-release-runtime.py:99` 按ImageID核对INSTALL_TEST_IMAGE_ID，`domestic-runtime.py:52` 与 `domestic-deploy.py:44` 会继续验证；`release-retention.py:55` 的managed允许prepare前未执行build，不要求伪造一次build。Docker官方支持直接[按ImageID新增tag](https://docs.docker.com/reference/cli/docker/image/tag/)。

主Agent提供的服务器只读证据（reviewer未连接生产复查）：旧安装2407 PASS，ImageID `sha256:6b65ffa999af5ed1740ea066733256e2d141587af4b3a153e7b6d1fd0bdcac12`；旧installation-tests.log SHA256 `27b40cf05c9a78b41f236a27c96dac31762d9329782c5e4ee1ffceb245a035f6`。

复用执行必须满足：

1. 新旧包完整backend清单和内容哈希相等（含新增/删除），Dockerfile及存在的.dockerignore相等；旧INSTALL_TEST_IMAGE_ID、实际旧镜像ID、安装日志成功结论互相一致。新包仍执行自身归档/源码完整性校验。
2. 从该精确ID新增新release tag，再inspect确认同ID；保存显式复用来源、旧安装日志SHA、完整输入比较结果及新旧ID，才登记新INSTALL_TEST_IMAGE_ID。报告如实写“复用2407项既有结果”，不能写新跑2407。
3. 复用、打tag、写凭据及新候选pending登记应处于同一retention锁保护中。旧pending abandon后仅有tag不受清理保护；`release-retention-docker.py:83` 依靠pending保护候选。prepare/deploy继续经managed及既有健康、安装、迁移和原生服务门禁。

这些是条件性可行意见；新包尚未在本审查中验证，不能替代主Agent的实际复用证据。批准本报告只对应上面的两文件候选，由主Agent执行review-approve；不向.needs-review写clean。
