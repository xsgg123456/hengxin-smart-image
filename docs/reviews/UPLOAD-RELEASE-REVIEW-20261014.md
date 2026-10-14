# 上传发布独立审查 · 2026-10-14

- candidateId：`507200f4f1d695fa0e5eff3020781cb4bbcc8e90dc1968206480906c885e628b`
- 范围：本次工作树的 `overseas-upload-deploy.py`、`overseas-upload-proxy.py`、`test_overseas_upload.py`，`package-overseas.py`、`test_package_overseas.py`、前端 package.json 版本和 CHANGELOG 差异。已提交 e700d87 产品功能不是此次重新验收范围。
- 依据：Product-Spec.md:1129–1135、docs/UPLOAD-RELEASE-20261014.md:5–13、生产只读预检输出。
- 使用 `.agents/skills/code-review/SKILL.md`；不修改产品代码、不提交、不部署、不登记批准。
- 审查结束前 review-status 仍返回上述 currentId，无代码漂移。

## Stage 1：FAIL

### HIGH · API 停止期间检查静态 upstream，导致发布必经路径失败

Spec 要求备份排空后切换并完成生产部署（Product-Spec.md:1135）。实际 `scripts/release/overseas-upload-deploy.py:206` 先停止 API，`:216` 调用 install_inner，直到 `:220` 才启动新 API。`scripts/release/overseas-upload-proxy.py:50` 在 install_inner 内执行 `nginx -t`。

生产预检 inner location 的 upstream 是 `http://overseas-api:8000`（output/upload-proxy-preflight.json:1）。Docker 停止 API 后其网络 DNS 名无法解析，Nginx 配置检查失败，使流程落入异常分支，海外入口保持关闭；新 API 与前端无法发布。恢复配置后的 nginx -t 同样仍可能遇到停止的 upstream（overseas-upload-proxy.py:57）。

审查使用本机已存在的同版本 `nginx:1.27-alpine`，新建隔离网络及两个仅供审查的容器，配置静态 overseas-api upstream；API 运行时和停止后分别执行 nginx -t。原始输出：

```text
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
hx-upload-review-api
2026/10/14 09:06:18 [emerg] 58#58: host not found in upstream "overseas-api" in /etc/nginx/conf.d/default.conf:1
nginx: [emerg] host not found in upstream "overseas-api" in /etc/nginx/conf.d/default.conf:1
nginx: configuration file /etc/nginx/nginx.conf test failed
```

最后命令退出码 1。审查容器和网络已全部清理，未访问或变更生产。应将 inner 安装及语法验证安排在新 API 已启动后、shared web reload 前，并保留 COMPLETE 备份门槛。补充测试证明这一真实顺序；现有测试在 `test_overseas_upload.py:25` 将 install_inner 整体 mock，未检测该依赖。

### 范围内逐项对照

| 要求 | 结论与证据 |
| --- | --- |
| 发布版本 0.2.33，海外0015/国内0028，不迁移 | 静态实现：frontend/package.json:3；overseas-upload-deploy.py:25–38；package-overseas.py:21。部署仅 up api，无 migrate 调用。 |
| 两层只改海外 location | 实现：overseas-upload-proxy.py:4–25，仅替换唯一海外匹配，保留 upstream 和周围字节；测试 test_overseas_upload.py:40–53 校验国内内容保留及歧义拒绝。 |
| 单文件500 MB并给 multipart 64 KiB | 实现：overseas-upload-proxy.py:6、infra/nginx.overseas-upload.inc:3；500000000 + 65536 = 500065536。 |
| 不停忙 worker | 实现：overseas-upload-deploy.py:52–74，连续两次空队列，停 outbox 后再验证，之后才停 worker；继承故障矩阵运行通过。 |
| 完整备份前不写 inner | 实现：overseas-upload-deploy.py:212–216；overseas-upload-proxy.py:45–49 检查 COMPLETE、备份原配置后写。 |
| 不改国内/identity资源、不删业务 | 实现：overseas-upload-deploy.py:132–148 校验容器、mount、原生进程、配置；:220 只切海外 api；无删除业务或恢复数据库指令。继承测试覆盖国内重启/挂载漂移。 |
| prepared 基线防漂移 | 实现：overseas-upload-deploy.py:77–87、:178–184，验证 overlay、Compose、topology、代理原配置；proxy.py:39–41 验证双代理。 |
| 切换顺序可实际执行 | **未实现：上述 HIGH**。 |
| 前端发布后才开放海外入口 | 静态顺序实现：overseas-upload-deploy.py:233–239；目前受 HIGH 阻断，不能声明生产完成。 |
| 失败关闭入口、恢复inner，不重放或恢复数据库 | 静态实现：overseas-upload-deploy.py:174、:253–267；proxy.py:53–58 恢复确为此次写入的文件。当前停止API期间恢复验证也受 HIGH 影响。 |
| 包含新代理配置及发布脚本 | 实现：package-overseas.py:29 将 include 加入 EXACT/REQUIRED；:82–85 的 overseas 脚本选择规则覆盖两个新脚本；实际归档需在提交后生成，未声称已验收归档。 |
| 上传边界部署后验证 | 静态实现：overseas-upload-proxy.py:61–72 检查双层配置及公开/内层请求；只探测头部准入，不代表实际500 MB完整文件上传。生产执行待修复。 |
| UI与正式页面视觉 | 本次代码差异无页面变更；正式页面验收属部署后步骤，目前未执行，不能声称通过。 |
| Spec漂移 | 此次差异均对应 Product-Spec.md:1135 及发布记录，无新增页面/API/表。 |

## 验证证据

独立执行项目 venv 的 pytest，原始结果：

```text
.........................................      [100%]
41 passed, 26 subtests passed in 2.23s
```

测试命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_upload.py scripts/release/test_package_overseas.py -q`。系统 Python 无 pytest，因此切换项目 venv 后成功；未安装依赖。

读取主 Agent 构建原始日志 output/upload-release-build.log:1–8、:769（未再次构建），原始片段：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.33 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 36.92s
```

## Stage 2：未执行

Stage 1 有 HIGH，依据 skill 停止，不登记 Stage 2 PASS。主 Agent 修复后重新 review-prepare，新的 candidate 必须从 Stage 1 起审查；此报告不能批准新代码。
