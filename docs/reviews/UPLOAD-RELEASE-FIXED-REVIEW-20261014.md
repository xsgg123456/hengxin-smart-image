# 上传发布修正版独立审查（审查中止）

- candidateId：`c569628b8b093651e3fdf90822873b5b0ac177eb1699bb77d24f46f96b6e8876`。
- 范围：`overseas-upload-deploy.py`、`overseas-upload-proxy.py`、`test_overseas_upload.py`，`package-overseas.py`、`test_package_overseas.py`、frontend/package.json、CHANGELOG 与发布说明；e700d87 产品功能不重复完整验收。
- 依据：Product-Spec.md:1129–1135、docs/UPLOAD-RELEASE-20261014.md:5–13、code-review skill、HARNESS-REVIEW 协议。
- 结论：**不可批准**。主 Agent 在审查期间发现生产资源容量问题并开始修复；Stage 1 未完成，Stage 2 未执行。以下行号对应送审 candidate，不能用于批准新快照。

## Stage 1：中止，未 PASS

### 已核实项

| 要求 | 证据与结论 |
| --- | --- |
| 旧 nginx DNS 阻断修复 | deploy.py:224 先 installed，:225 才 install_inner，:227–228 才 nginx 检查和 reload。installed:156–172 验证 API running、镜像、源码和健康；test_overseas_upload.py:31–39 验证顺序。旧版在停 API 期间 nginx -t 的必现问题已修正。 |
| 0.2.33，schema 0028/0015，不迁移 | frontend/package.json:3；deploy.py:25–38；package-overseas.py:21。部署只 up 海外 api，没有 migrate 动作。 |
| 双层海外代理范围与请求边界 | proxy.py:4–25 唯一 overseas location 替换、保留上游和其余内容；:6–8 为 500065536 bytes、300 秒、HTTP/1.1、关闭 request buffering。test_overseas_upload.py:54–67 验证国内内容保留与歧义拒绝。 |
| 排空与备份 | deploy.py:47–71 连续两次 DB/broker 空闲、停 outbox 后再次排空、再停 worker；:212–215 验证 COMPLETE 后切换。继承故障矩阵通过。 |
| 不改国内和 identity、不重放、不恢复业务数据库 | deploy.py:132–148 校验原容器、配置、mount、原生进程；:178 拒绝重放，:251–265 失败关入口、恢复 inner、停 API，不停未知忙 worker、不覆盖数据库。 |
| prepared 防漂移 | deploy.py:73–83 校验 overlay 与 Compose；:181–187 校验 topology、代理原配置与 assets。 |
| 前端发布后开放 | deploy.py:233–241 先 publish、frontend 校验，再开放和公共检查；此结论只针对代码顺序，不代表生产已完成。 |
| 代理恢复 | proxy.py:53–58 只恢复与本次 after 文件相等的内容；正常失败分支先关闭入口，再恢复、nginx 检查/reload，最后停止 API（deploy.py:253–260）。不把 API 自身崩溃导致的恢复 nginx 失败宣称已验证；此时仍需人工检查恢复。 |
| 包含脚本与配置 | package-overseas.py:29 将 include 加入 EXACT/REQUIRED；:82–85 overseas 脚本选择规则包含 deploy/proxy。:167–210 取已提交内容、核对审查状态、隐私扫描和归档字节哈希。实际包需提交后生成，本审查未宣称实际归档 PASS。 |
| curl 头部探测前提 | proxy.py:65–72 不发送业务 body；materials/router.py:17–21 在 parse_upload 前执行依赖，core/browser_auth.py:17–19 缺少 X-HX-Request 即 403。因此允许尺寸可提前返回；此探测只证明代理准入，不能证明 500 MB 文件实际上传、读取和内存容量。 |
| UI 与 Spec 漂移 | 差异无页面代码，仅版本变更；均对应 Spec:1135 发布授权，没有新增页面/API/表。正式页面视觉仍是部署后未执行步骤。 |

### 阻断与版本变化

**HIGH · 生产资源容量不匹配。** 只读输出 `output/upload-memory-config.json:1` 记录生产 API `HostConfig.Memory=402653184`（384 MiB），但 `backend/app/overseas/materials/router.py:23` 会读取完整最多 500 MB bytes。当前 candidate 的 overlay 仅允许 image/build，无法解决该容量不匹配。该生产输出由主 Agent 实查保存、本 reviewer 读取核对，未重复连接生产。主 Agent 已明确要求暂停批准并补充资源修复。原始输出：

```json
{"limits": {"mem_limit": "402653184"}, "live": {"Memory": 402653184, "MemoryReservation": 0, "MemorySwap": 805306368, "MemorySwappiness": null}}
```

本 reviewer 测试后首次 review-status 仍为送审 candidate；结束前检测到代码已变化，currentId 为 `6b77977acd6a3b370180086c79af61b23d8fb647830a78fef2e6a2cee6807c11`，新增 overseas-upload-resources.py，deploy.py 已改为 resources.overlay。**旧测试与结论不覆盖此新版本**，需重新 prepare 并 fresh 审查。

主 Agent 随后通报修复完成的新 candidate 为 `013f660dda8355774d169bd7e625309130ba26acc2606cac1a3bf144d79602d0`，由 fresh reviewer 另审，本报告不覆盖该版本。

### 测试盲区提示

继承的优化模式测试 `overseas-hotfix-tests.py:30` 固定执行旧 `overseas-hotfix-deploy.py`，并未执行新 upload CLI。新脚本静态存在相同 -O 防护，但本用例不能作为新版 CLI 实测证据。新资源容量验收应覆盖真实 500 MB 读取，匿名头部测试不能替代。

## 验证原始输出

独立运行送审 candidate：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_upload.py scripts/release/test_package_overseas.py -q
..........................................     [100%]
42 passed, 26 subtests passed in 2.20s
```

读取主 Agent 已有构建日志 output/upload-release-build.log:1–8 与末行，未重复完整前端构建：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.33 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 36.92s
```

## Stage 2：未执行

Stage 1 被资源阻断及代码变化中止。未批准、不写 clean、不提交、不部署。修复后的新快照必须重新从 Stage 1 审查。
