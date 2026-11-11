# 内网 nginx 启动竞态与回退增量审查

- candidateId：`1727aa01ca08192c1d0da00cee2abb1bfa7cf16104447c0c21efca05f4fd08da`。
- 批准基准：`c6a2ca04ddd3845dacaa90b44714e1bda49a82621adc2936e099e5178cc6532c`。沿用 `docs/reviews/INTRANET-IP-HEALTH-REVIEW-20261111.md` 及其引用的 ACCESS 完整报告中未变化部分。
- 范围：`hengxin-smart-image/scripts/migration245/ip_access.py` 的 nginx 重载重试、apply/restore 接入和回退 finally；同目录 `test_ip_access.py` 的新增故障测试。下文代码路径均相对该目录。
- 使用 `.agents/skills/code-review/SKILL.md`；不修改实现、不部署、不连接服务器、不扩大整套功能验收。
- **Stage 1：PASS；Stage 2：PASS。** 无 HIGH/MEDIUM 问题；一项 LOW 计时说明及测试边界见下。由主 Agent 登记同一 candidateId，不写 clean。

## 快照核验

独立执行 `python .codex/hooks/harness.py review-status`：

```text
{"currentId": "1727aa01ca08192c1d0da00cee2abb1bfa7cf16104447c0c21efca05f4fd08da", "reviewedId": "c6a2ca04ddd3845dacaa90b44714e1bda49a82621adc2936e099e5178cc6532c", "changedFiles": ["hengxin-smart-image/scripts/migration245/ip_access.py", "hengxin-smart-image/scripts/migration245/test_ip_access.py"], "approved": false}
```

## Stage 1 · Spec Compliance

源合同为 `Product-Spec.md:3` 引用的 `docs/INTRANET-IP-ACCESS-20261111.md`，按合同全部条目核对本次影响范围：

| 条目 | 证据与验证 | 结论 |
| --- | --- | --- |
| 1：内网入口、网段限制、上传/SSE 与 loopback | `ip_access.py:50` 的配置生成及 `:102` 的服务配置准备不变；新逻辑只重载既定容器（`:204`、`:206`）。沿用基准报告对应实现结论。 | 无增量偏差 |
| 2：origin、Cookie、企业权限与真实登录验收边界 | `ip_access.py:112` 至 `:114` 的 origin 配置未变；快照变化不含鉴权代码。`:212` 仍要求独立验证登录。 | 无增量偏差；真实钉钉登录未验收 |
| 3：HTTP 随机数、摘要、ZIP、复制与图片入口 | 快照变化仅两份 Python 文件，未变化的前端适配与视觉证据沿用 ACCESS 报告。 | 无增量偏差 |
| 4：最小覆盖、健康与故障回退 | `ip_access.py:138` 至 `:149` 捕获命令失败，重新执行 nginx 配置验证及 reload；`:204`、`:206` 应用时统一使用。`:207` 健康通过后才写成功标记，`:209` 失败继续回退。`test_ip_access.py:73` 实际模拟首次配置验证成功、reload 失败、下一轮成功。 | 完整实现，PASS |
| 4：回退阶段故障不得阻止 edge 重载尝试 | `ip_access.py:153`、`:154` 先恢复配置，`:155` 至 `:159` 在 compose 或 web 重载异常时仍调用 edge reload。`test_ip_access.py:81` 验证 compose 失败；reviewer 额外模拟 web reload 失败并断言调用顺序及异常传播。 | 完整实现，PASS |
| 不重建原生 worker/任务数据 | `ip_access.py:18` 服务清单不变，`:156`、`:202` 保留 `--no-deps`；新增逻辑只有 nginx exec，不增数据库或 worker 操作。 | PASS |
| UI、引导真实性、Spec 漂移 | `ip_access.py:138`、`:152`、`:204` 为部署容错，无新页面、接口、表或产品功能；`:212` 不冒称完整验收。没有新增 UI 需要渲染对比。 | 无漂移 |

本增量无部分实现或未实现项。上述代码 PASS 不等于部署、实际回退或业务生成验收。

## Stage 2 · Code Quality

- PASS：`ip_access.py:138` 集中封装两处 nginx 命令，apply/restore 共用；实现 224 行、测试 92 行，均未超 300 行。`:146` 只处理子进程非零返回，达到期限重新抛出；`:159` 不吞掉 edge 重载异常。
- PASS：`ip_access.py:143`、`:144` 使用 argv 数组，经 `:23` 的 `subprocess.check_output` 执行，没有 shell 拼接、eval、SQL、硬编码密钥或新增外部地址。容器参数来自 `:157`、`:159`、`:204`、`:206` 的固定调用点。`:222` 仍避免将 Docker 私有输出泄露到终端。
- 测试真实性：`test_ip_access.py:75` 的异常发生在首次 reload，符合所述 PID 尚未生成路径；`:83` 实际注入的是 compose 失败，不能单独声称已测试 web reload 失败。reviewer 的独立补充探针覆盖后者，并覆盖到期异常传播。所有这些测试使用替身，不证明真实 Docker 服务恢复。
- LOW，计时描述：`ip_access.py:140` 的 30 秒是命令失败后的重试窗口，`ip_access.py:24` 的单次子进程 timeout 仍为 180 秒，因此不是严格的 30 秒墙钟上限。当前修复针对快速返回的缺 PID 错误，无无限重试；本项不阻断此次修复，交付描述应准确。
- 视觉对比：快照未变化任何 UI 文件，沿用 ACCESS 报告的实际页面对比；本轮没有重新打开浏览器。

## 编译与测试原始输出

reviewer 对两文件执行内置 `compile()`，并用临时内存替身执行到期失败、web 重载失败两条探针；未修改测试文件：

```text
compile(): PASS (2 files)
deadline failure propagation: PASS
web reload failure still reloads edge: PASS
```

`python -m unittest discover -s hengxin-smart-image/scripts/migration245 -p test_ip_access.py -v`：

```text
test_changed_frontend_refused_before_apply (test_ip_access.AccessPreparation.test_changed_frontend_refused_before_apply) ... ok
test_nginx_reload_waits_for_entrypoint_pid (test_ip_access.AccessPreparation.test_nginx_reload_waits_for_entrypoint_pid) ... ok
test_prepare_does_not_modify_live_configuration (test_ip_access.AccessPreparation.test_prepare_does_not_modify_live_configuration) ... ok
test_restore_reloads_edge_even_when_web_restore_fails (test_ip_access.AccessPreparation.test_restore_reloads_edge_even_when_web_restore_fails) ... ok
test_unexpected_live_source_refuses_prepare (test_ip_access.AccessPreparation.test_unexpected_live_source_refuses_prepare) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.138s

OK
PREPARED: payload hashes, source baseline, compose and nginx validated
PREPARED: payload hashes, source baseline, compose and nginx validated
PREPARED: payload hashes, source baseline, compose and nginx validated
```

## 真实环境交接证据与边界

以下为主 Agent 提供，reviewer 未连接服务器或独立读取原始日志：真实 apply 中 compose 已返回 started，但 nginx entrypoint 尚未写 `/run/nginx.pid`；紧接 reload 失败，旧回退逻辑又因 web reload 失败而未执行 edge reload。随后读取同一容器 `/proc/1` 与 PID 文件证明 master PID 1 和 PID 文件已出现。

主 Agent 补充：目标机用原 nginx 镜像启动 `--network none` 临时容器，entrypoint 延迟 3 秒再执行 nginx；新 `reload_nginx` 等待后在 3.73 秒完成，临时容器已按实际创建 ID 删除，生产服务未变。该交接证据支持修复动机与启动竞态处理，但不代替正式 apply、回退健康或钉钉登录验收。
