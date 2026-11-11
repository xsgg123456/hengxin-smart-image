# 内网 HTTP readiness 路径修正增量审查

- candidateId：`c6a2ca04ddd3845dacaa90b44714e1bda49a82621adc2936e099e5178cc6532c`。
- 基准：已批准 `8c20163fb511e67f29694b0d396198e573891ebf02eae991d67ce82fe9fc3b0d`，完整审查见 `docs/reviews/INTRANET-IP-ACCESS-REVIEW-20261111.md`。
- 范围：仅 `hengxin-smart-image/scripts/migration245/ip_access.py:148`、`:149` 两个 readiness URL；按 code-review 技能独立增量审查，不重复整套功能验收，不连接服务器，不修改实现。
- **Stage 1：PASS；Stage 2：PASS。** 结论限于本候选两行修正及其与已批准基准的组合；不代表修正后的真实部署或 OAuth 已验收。由主 Agent 登记 review-approve。

## 快照核验

reviewer 独立运行 `review-status`：

```text
{"currentId": "c6a2ca04ddd3845dacaa90b44714e1bda49a82621adc2936e099e5178cc6532c", "reviewedId": "8c20163fb511e67f29694b0d396198e573891ebf02eae991d67ce82fe9fc3b0d", "changedFiles": ["hengxin-smart-image/scripts/migration245/ip_access.py"], "approved": false}
```

将当前文件中两 URL 还原为 `/health/ready` 后，按 LF 归一计算 SHA-256，精确匹配批准快照中的该文件哈希，证明只有这两处变化，无额外代码变化：

```text
reconstructed previous file: 381e8984eb7bd1ff1d83215b91ba7e6d45afd8378ff0af479309c7e9ef250fc2
approved file: 100644:381e8984eb7bd1ff1d83215b91ba7e6d45afd8378ff0af479309c7e9ef250fc2
```

## Stage 1 · Spec Compliance

| 条目 | 证据 | 结论 |
| --- | --- | --- |
| 合同 `docs/INTRANET-IP-ACCESS-20261111.md` 第 4 条：部署验证健康；国内地址正确 | `ip_access.py:148` 请求 `http://127.0.0.1:18008/api/v1/health/ready`；`backend/app/main.py:42` 注册 `/api/v1` 前缀，`backend/app/health.py:49` 声明 `/health/ready`。两者拼接与请求路径完全相同。 | 完整实现，PASS |
| 同条：海外地址正确 | `ip_access.py:149` 请求 `http://127.0.0.1:18018/api/overseas/v1/health/ready`；`backend/app/overseas/health.py:13` 前缀 `/api/overseas/v1/health`、`:54` 路由 `/ready`，`backend/app/overseas/main.py:26` 无额外前缀注册。 | 完整实现，PASS |
| 健康失败仍阻止成功并回退 | `ip_access.py:155` 至 `:161` 继续要求 HTTP 200，重试至期限后抛错；`:192` 在写入成功标记之前调用检查，`:194` 至 `:196` 异常时 restore 并重抛。两行替换未改变上述行为。国内 `backend/app/health.py:53` 仍以 503 表示未就绪。 | PASS |
| Spec 漂移、引导及 UI | 两个常量路径替换，无页面、接口定义、权限、引导或视觉代码变化；完整基准报告保留既有范围结论。本轮无新增 UI 需重新视觉比对。 | 无漂移 |

本次范围内无部分实现或未实现条目，无 HIGH/MEDIUM 问题。

## Stage 2 · Code Quality

- PASS：`ip_access.py:148` 至 `:149` 沿用固定 loopback 主机、原端口，仅补全已有业务路由前缀；无命名、类型、结构或文件长度变化，无新依赖。
- PASS：相同两行无密钥、动态输入、shell、eval、SQL 或权限放宽；`ip_access.py:147` 保留禁用代理的 opener，`:155` 保留超时；没有新增安全问题。
- 测试真实性与边界：独立复跑 `scripts/migration245/test_ip_access.py:49` 起 3 项，覆盖配置准备隔离、payload 篡改拒绝、运行源码基线漂移拒绝。它们不覆盖真实 HTTP 请求，不能单独证明服务就绪。实际路径另由上述独立源码路由对应及主 Agent 的真实环境证据支持；本 reviewer 未运行线上 apply。
- 视觉对比：本候选无 UI 改动；此前报告的页面渲染比较结论仍对应相同前端文件，不声称本轮重新打开浏览器。

## 编译与测试原始输出

reviewer 对当前 Python 源码调用内置 `compile()`，未产生构建文件：

```text
compile(): PASS
```

reviewer 执行 `python -m unittest discover -s hengxin-smart-image/scripts/migration245 -p test_ip_access.py -v`：

```text
test_changed_frontend_refused_before_apply (test_ip_access.AccessPreparation.test_changed_frontend_refused_before_apply) ... ok
test_prepare_does_not_modify_live_configuration (test_ip_access.AccessPreparation.test_prepare_does_not_modify_live_configuration) ... ok
test_unexpected_live_source_refuses_prepare (test_ip_access.AccessPreparation.test_unexpected_live_source_refuses_prepare) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.138s

OK
PREPARED: payload hashes, source baseline, compose and nginx validated
PREPARED: payload hashes, source baseline, compose and nginx validated
```

## 真实环境交接证据与未验收边界

以下是主 Agent 此次任务消息提供的实查结果，不是 reviewer 独立连接或原始日志：目标机原 Docker Healthcheck 使用国内 `http://localhost:8000/api/v1/health/ready`、海外 `http://localhost:8000/api/overseas/v1/health/ready`；curl 两个原 `/health/ready` 路径返回 404，两个修正路径返回 200。首次 apply 时浏览器曾成功打开 `http://192.168.1.245:8080`，随后因错误健康路径触发自动回退；交接时已回到旧 compose，API 均 healthy。

上述交接说明修正动机，与独立源码证据一致。修正后的部署需主 Agent 单独执行并验收；钉钉回调按用户授权暂搁置，真实 OAuth 和业务生成仍待验收。不得以本报告 PASS 代替这些运行态结果。
