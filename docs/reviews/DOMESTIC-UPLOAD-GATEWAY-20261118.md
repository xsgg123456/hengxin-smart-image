# 国内工作台附件网关审查

候选快照 `c8fe0c477157414133a1c5fd6bb17ffdbf227c9a724fdb5b53a06fc19b18477c`。审查开始和编译、测试后运行 `review-status`，两次 currentId 相同。范围为 Product-Spec.md:3、本次变更记录、scripts/release/intranet 下的 release_cli.py、domestic_upload_routes.py、domestic_upload_maintenance.py、domestic_upload_probe.py 及两份对应测试。

## Stage 1 · Spec Compliance · PASS

| 验收项 | 实现与证据 |
| --- | --- |
| 国内任务会话、兼容工作台均可传原先被拦的 PPTX | `hengxin-smart-image/backend/app/modules/domestic_studio/router.py:29、146、186` 注册相同上传处理。网关在 `scripts/release/intranet/domestic_upload_routes.py:5、29` 匹配这两类路径。隔离候选 Nginx → 国内 API → PostgreSQL、MinIO，两路 10,695,475 字节 PPTX 均得到 POST、HEAD、GET 200，下载 SHA-256 均与输入相同。见 `output/domestic-upload-limit-20261118/gateway-attachment-evidence.json:2、9、22`。 |
| 接受非空单文件至 500,000,000 字节，允许 65,536 字节封装开销 | `hengxin-smart-image/backend/app/overseas/upload_limits.py:2`、`hengxin-smart-image/backend/app/overseas/studio/files.py:42`、`hengxin-smart-image/backend/app/modules/domestic_studio/router.py:155` 保留文件校验。`scripts/release/intranet/domestic_upload_routes.py:3、24` 配置整包上限 500,065,536。独立在实际基线生成的 Nginx 配置运行边界测试，两端点的上限整包均完整到达计数上游，额外一字节均获 413。见 `scripts/release/intranet/test_domestic_upload_routes.py:152`。 |
| 维持原身份、会话归属及存储校验 | `hengxin-smart-image/backend/app/modules/domestic_studio/router.py:147、149` 继续要求用户及可写会话，`hengxin-smart-image/backend/app/modules/domestic_studio/file_service.py:35、50、64` 校验大小、归属并写入存储。隔离两路均得到数据库 ready、MinIO 字节数正确、其它用户请求 404，见上述证据 JSON 第 17、30 行附近。 |
| 其它国内、海外、身份及静态代理保持原行为 | 原配置 SHA-256 经独立计算与 `scripts/release/intranet/domestic_upload_maintenance.py:17、52` 相同。重新渲染与存档 candidate.conf 字节一致，SHA-256 为 `536c4869578cc9d6c0a874e2b46428f02a6762cbac3d7a5e2aa7a1eb970cf9bd`。渲染仅插入一个首尾锚定的 location，原配置其余字节保留，见 `scripts/release/intranet/domestic_upload_routes.py:24、30`。五条邻近路径实测仍返回 413，见 `scripts/release/intranet/test_domestic_upload_routes.py:172`。 |
| 仅平滑重载网关、异常恢复并保留发布历史 | `scripts/release/intranet/domestic_upload_maintenance.py:128、140、145、149、156、159` 校验挂载、候选语法，持久化 pending 后写入并验证，再推进台账。既有 `scripts/release/intranet/split_config.py:73、103` 原 inode 写入并执行 nginx -t、nginx -s reload。`scripts/release/intranet/domestic_upload_maintenance.py:82、98、109` 恢复配置并验活。应用/回退过程中注入部分写入、重载失败、探针失败，断言恢复原配置与台账，见 `scripts/release/intranet/test_domestic_upload_maintenance.py:105、145`。 |

范围内全部需求完整实现。六份代码变化均用于这次网关维护、探测及验证。无页面、交互文案、数据库结构或业务服务改动，UI 和视觉比对不适用。

## Stage 2 · Code Quality · PASS

- 发布互锁覆盖主入口及包入库。`scripts/release/intranet/release_cli.py:18、28、33、45、58` 核验参数、主机、root 身份、独占锁和待处理维护。`scripts/release/intranet/stage.py:84` 已拒绝存在未决事务时入库。反向互锁、错误选项、幂等、保留后来海外历史分别见 `scripts/release/intranet/test_domestic_upload_maintenance.py:171、166、57`。
- 恢复逻辑限定为原件向目标的连续写入前缀，只接受已知中间态。`scripts/release/intranet/domestic_upload_maintenance.py:71、94、100`。独立以归档基线和候选配置遍历正向 3,385 个、反向 2,777 个写入偏移，均可识别；未识别的手工改动保留并拒绝覆盖，测试见 `scripts/release/intranet/test_domestic_upload_maintenance.py:145`。
- 维护、路由和探针职责独立，各新增文件均少于 300 行。安全扫描覆盖六份代码，未命中硬编码密钥、动态执行或 shell=True。真实探针固定内网入口，禁用 curl 默认配置、使用参数数组和超时，并核验应用返回的 JSON，见 `scripts/release/intranet/domestic_upload_probe.py:8、26、36、43`。配置绑定的目标、权限及 inode 检查见 `scripts/release/intranet/domestic_upload_maintenance.py:24`。
- 测试层次分明。网关边界使用真实 Nginx；文件持久化与跨用户读取使用真实隔离 API、PG、MinIO；故障注入测试替换重载和探针，验证真实磁盘写入与台账还原。核对归档的发布工具回归末行为 `595 passed, 10 skipped, 21 subtests passed in 24.26s`，见 `output/domestic-upload-limit-20261118/local-release-regression.log`。跳过项保留其原有环境条件。生产变更后的运行身份、实际响应和最终台账由执行维护时验收。

独立运行 Python 编译的原始输出如下。

```text
Compiling 'scripts/release/intranet/domestic_upload_maintenance.py'...
Compiling 'scripts/release/intranet/domestic_upload_routes.py'...
Compiling 'scripts/release/intranet/domestic_upload_probe.py'...
Compiling 'scripts/release/intranet/release_cli.py'...
Compiling 'scripts/release/intranet/test_domestic_upload_routes.py'...
Compiling 'scripts/release/intranet/test_domestic_upload_maintenance.py'...
```

独立运行隔离真实 Nginx 边界用例的测试输出如下。

```text
test_upload_boundaries_and_neighboring_routes (__main__.NginxTests.test_upload_boundaries_and_neighboring_routes) ... ok
test_only_one_location_added (__main__.RenderTests.test_only_one_location_added) ... ok
test_rejects_unexpected_base_or_reapplication (__main__.RenderTests.test_rejects_unexpected_base_or_reapplication) ... ok

----------------------------------------------------------------------
Ran 3 tests in 1.083s

OK
```
