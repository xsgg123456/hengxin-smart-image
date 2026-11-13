# 国内工作台发布原生导入增量审查

- candidateId：`dfbdbd168c3ed48e7058b2f00ff9dab3992757dcb2e30272134a0f8045ab1476`。
- 基线 HEAD：`ddb23175a46e6f886332a736fc951adc7c711bc5`，完整功能审查基线为 `docs/reviews/DOMESTIC-STUDIO-FINAL-R14-20261113.md`（包含末尾空白差异复核附录）。
- **Stage 1：PASS。Stage 2：PASS。未发现本次增量阻断问题。**
- 范围仅为 `hengxin-smart-image/backend/app/execution/release_gate.py` 与 `hengxin-smart-image/backend/tests/test_release_gate.py` 的增量及原生账号/凭据导入、HTTP/WebSocket 门禁、健康白名单、后台等待的受影响闭环。文档增量为 `docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:15`。不重复全系统审查、不重复前端构建与视觉验收，不将 R14 证据冒充本次重跑。
- 已读取 AGENTS、code-review SKILL、HARNESS-REVIEW、Product-Spec/DEV-PLAN/Design-Brief 当前顶部原文与 R14 报告。先完成功能核对和针对性运行，再执行质量、安全与编译检查。未改受控代码、未提交、未批准、未连接生产、未写 `.needs-review`；根目录既有 `=12.1,` 未操作。

## Stage 1：需求符合性

本次属于 `Product-Spec.md:15` 的安全发布验收与 `DEV-PLAN.md:13-21` 的原生身份/候选安装验证修复；没有新增业务需求。首次 prepare 失败及取消状态为主 Agent 交接的生产事实，本 reviewer 没有自行连接生产确认，故本报告只批准代码增量。

| 范围内要求 | 结论与证据 |
| --- | --- |
| 系统 Python 原生账号及凭据服务保持标准库可导入 | 完整实现。`backend/app/account_management/service.py:13` 通过 `credential_broker.py:16` 导入 gate。`release_gate.py:2-5` 顶层仅标准库，`release_gate.py:69` 才在 HTTP 拒绝分支导入 JSONResponse。本轮实际用系统 `/usr/bin/python3 -S -B`、`env -i` 导入账号服务与 broker，断言 sys.path 不含 site/dist-packages、sys.modules 不含 starlette、所有非 app 模块均属于标准库，结果 `CLEAN_SYSTEM_IMPORT_PASS 3.14.4 external_modules= []`。 |
| HTTP 维护响应保持 | 完整实现。`release_gate.py:64-73` 的条件、503、中文 detail、Cache-Control:no-store 和提前返回均与基线一致，仅调整导入位置。`tests/test_release_gate.py:71-95` 本轮实际验证关闭时业务 GET 与健康 POST 为 503，开门后业务 GET 为 200。 |
| 健康 GET 白名单、WebSocket 拒绝保持 | 完整实现。`release_gate.py:9-10,64-68` 三条固定路径及 GET 判断未改；`tests/test_release_gate.py:86-93` 实际验证国内健康 GET 为 200、WebSocket 为 1013。海外健康及身份 config 的具体白名单字符串通过与 HEAD 差异核对未变，未另称这两条路由已做生产实测。 |
| marker 安全判断与后台等待保持 | 完整实现。`release_gate.py:13-55` 与 HEAD 无逻辑差异；`tests/test_release_gate.py:56-68,98-104,124-171` 实际验证无效目录/权限/链接关闭、stop 终止等待、真实 Redis/Celery 闭门不消费且开门后消费。测试使用固定隔离地址 `redis://127.0.0.1:35440/15` 和随机队列，本轮没有跳过。 |
| 凭据 socket 与发布中断保持闭门 | 完整实现。`credential_broker.py:74-81` 使用同一 marker 决定 bind 时权限；`tests/test_release_gate.py:107-121,174-225` 本轮验证 socket 初始 000、开门后 0660，以及实际 SIGKILL 后 marker 仍关闭且业务 HTTP 503。后一个用例的发布编排/健康探测有替身，不能代表生产 systemd 全链故障演练。 |
| UI、文案真实性及 Spec 漂移 | 本次无 UI 变更。差异只涉及 import 与回归测试，未新增页面、接口、表、权限或业务能力；`Design-Brief.md:1-3` 对应前端未变化。既有 UI 的完整结论引用 R14，本次视觉比较不适用。 |

范围内无部分实现、未实现或确认的 Spec 漂移；Stage 1 无 HIGH，继续 Stage 2。

## Stage 2：代码质量、安全与测试真实性

- **结构通过。** `release_gate.py:69` 延迟加载只供 HTTP 响应使用的依赖，保留原生调用者的标准库边界，没有改异常吞吐或开放门禁的条件。两个文件实际为 74、225 行，均低于 300 行；没有新增无关抽象或类型逃逸。
- **测试前提成立。** `tests/test_release_gate.py:24-33` 使用真正独立的解释器进程及 `-S -B`，从 backend 目录导入真实 service/broker，移除发布环境变量以验证未配置 gate 的原有默认；不是通过 mock 抹掉 starlette。新增测试继承 `:20-21` 的 Linux root 限制，本轮在 WSL root 实际运行通过。额外 `env -i` 系统 Python 检查消除了 PYTHONPATH 意外引入第三方包的可能。闭门行为由上述真实 gate/socket/Celery 用例补足。
- **安全扫描通过。** 对两个增量文件检索 eval/exec、shell=True、动态 HTML、前端密钥变量、常见密钥前缀及开发者绝对路径，无命中。新增子进程调用 `tests/test_release_gate.py:31-33` 使用固定 argv、无 shell、20 秒超时且 check=True；没有用户输入或凭据输出。`release_gate.py:13-37` 的 root/权限/单链接/O_NOFOLLOW 校验未改，没有新增确认的安全问题。
- **视觉/前端构建不适用。** 本次受控差异只有这两个 Python 文件，不重复 R14 已完成且此次未受影响的前端验收。

## 原始验证输出

本 reviewer 独立执行（backend 工作目录，WSL root）：

```text
PYTHONPATH=. TEST_RELEASE_GATE_REDIS_URL=redis://127.0.0.1:35440/15 /tmp/hengxin-domestic-studio-python/bin/python -m pytest tests/test_release_gate.py -q

.......                                                                  [100%]
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 1 warning in 7.21s
```

测试源码 `:127` 当前直接指定隔离 Redis 地址；上述环境变量不是测试连接来源。1 warning 是已有 TestClient 依赖弃用提示，不是失败或跳过。

干净系统环境导入与两个增量文件的 Python `compile(..., 'exec')` 原始输出（命令为 `env -i PATH=/usr/bin:/bin /usr/bin/python3 -S -B -`，脚本通过标准输入提供，未修改代码）：

```text
CLEAN_SYSTEM_IMPORT_PASS 3.14.4 external_modules= []
PYTHON_COMPILE_PASS app/execution/release_gate.py lines= 74
PYTHON_COMPILE_PASS tests/test_release_gate.py lines= 225
```

两次命令退出码均为 0；WSL 启动同时打印了宿主 localhost 代理转发提示（工具显示编码异常），未影响执行。`git diff --check` 退出码 0，仅文档 CRLF→LF 提示。第一次递归依赖检索用 Windows 不展开的 `*.py` 路径失败，已改用 `rg -g '*.py'` 对实际目录完成检索，不影响测试或编译结果。

审查开始及结束 `review-status` 均返回 currentId=`dfbdbd168c3ed48e7058b2f00ff9dab3992757dcb2e30272134a0f8045ab1476`；changedFiles 仅上述两个 Python 文件，未发现审查中代码变化。`approved:false` 是尚未由主 Agent 登记本次凭据的预期状态。

主 Agent 可按同一 candidateId 和本报告登记两阶段 PASS 后继续已授权的中文提交与重新构建部署。此结论不表示生产已修复或上线；正式安装后原生身份导入和入口版本核验仍由发布流程执行。
