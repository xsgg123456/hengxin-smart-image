# Phase 17 真实本地 API 联调

## 规划与完成标准

1. 一次性 Docker internal 网络、PostgreSQL 两个空库、独立 Redis；真实执行国内与海外各自 Alembic。完成标准：版本分别到本 Phase 目标，互不混表。
2. 三个独立 uvicorn 进程加载正式应用；仅测试入口替换外部钉钉 provider，固定四个虚拟成员。完成标准：通过真实 HTTP 完成四种授权组合。
3. 验证 ticket、OAuth state、cookie 隔离、单边停用、退出和故障关闭。完成标准：所有断言通过，finally 删除本次唯一命名容器及网络。

执行入口：`python hengxin-smart-image/infra/identity-test/run.py`。仅依赖本机 Docker 和现有 `hx-management-test:local`、`postgres:17`、`redis:7` 镜像；不拉镜像、不读取项目 .env、不访问生产、真实钉钉或收费服务。默认使用 internal 网络、不发布端口；`--serve` 为本地浏览器端口转发使用普通独立 bridge 网络，仅绑定 127.0.0.1 三个随机端口，Ctrl+C 后自清理。代码只读挂载、运行目录 /tmp、子进程白名单环境变量，provider 替身限定在测试目录。

## 2026-10-12 实际执行结果

最终 API 命令 `python hengxin-smart-image/infra/identity-test/run.py` 返回 0，输出 `PASS ALL Phase 17 real HTTP integration`，并输出 `CLEANED hx-p17-6922e0272833`。此前两轮通过并清理的资源为 `hx-p17-23b02792be8f`、`hx-p17-e314aa36bf29`。

| 断言 | 结果 |
|---|---|
| 两个空库分别执行完整 Alembic | 国内 0027、海外 overseas_0002；对方核心业务表不存在 |
| 双授权、仅国内、仅海外、均未授权 | 四组真实 HTTP 登录与会话兑换通过；未授权 403 |
| ticket 业务绑定、重放、篡改、过期 | 均拒绝；过期检查包含 Redis 原始 TTL 为 1–60 秒及实际到期删除 |
| cookie 独立 | 不同业务 cookie 不认证；将对方 token 改用目标 cookie 名仍 401；HttpOnly/Path/SameSite 检查通过 |
| 海外成员停用 | 海外 403、国内仍 200 |
| 单业务退出与全局退出 | 海外单边退出国内仍 200；统一退出两侧均 401 |
| OAuth 浏览器 state 绑定、重放、失败消耗 | 均通过；缺少 X-HX-Request 头被拒绝 |
| 本地业务与上游身份会话过期 | 两侧均 401；测试只修改临时库/临时 Redis 中的到期时间 |
| 身份进程停止 | 已登录的两业务请求均 503，失败关闭 |

真实浏览器命令（前端目录）`node tests/unified-identity-real.browser.mjs`，使用既有 Playwright runtime（`PLAYWRIGHT_MODULE` 指向其 `playwright/index.mjs`）。测试前启动 Vite `--mode development --host localhost --port 3013`，国内/海外/身份代理分别指向本次 49973/49974/49975。身份 public origin 为 `http://localhost:3013`。

浏览器四组合全部 PASS：双入口授权状态、入口页未调用国内 bootstrap、海外进入/刷新/切换、统一退出后三个 `/me` 均 401、无 JS 异常。只替换外部钉钉换码，页面及业务请求均连接真实 API，无业务接口拦截。浏览器使用每组合独立 context，provider code 仅测试环境允许 `both/domestic/overseas/neither`。

浏览器资源 `hx-p17-8f770d0be97b` 验收后已停止并清理；该次运行在加入 SIGTERM 正常退出处理前启动，因此人工终止保活阶段返回非零，不是测试断言失败。最新脚本支持完成验证后正常 SIGTERM 结束保活。早期脚本自身 httpx context 重入问题已修复并完整重跑。

边界：本记录覆盖独立真实 API 与正式浏览器入口，不代表真实钉钉企业配置或生产部署验收。国内一期完整回归及独立审查由主 Agent 单独汇总。

## 2026-10-12 最终安全改动后复验

在业务兑换加入 Origin 校验、有效新 ticket 对应成员 pending 时撤销浏览器旧会话后，重新执行 `python hengxin-smart-image/infra/identity-test/run.py --serve`。本轮唯一隔离资源前缀 `hx-p17-6e9b93470d8e`；国内/海外/身份端口为 52366/52367/52368。完整 API 断言再次输出 `PASS ALL Phase 17 real HTTP integration`，含国内 0027、海外 overseas_0002 独立迁移及上表全部项目。

Vite 以 localhost:3013、development 模式启动，三个代理指向本轮端口。`node tests/unified-identity-real.browser.mjs` 返回 0，both/domestic/overseas/neither 四组合全部 PASS，正式页面独立启动、海外刷新与切换、全局退出及无 JS 异常均通过。

额外通过容器内 stdin 临时 Python/httpx 脚本验证两侧真实 HTTP（未修改测试或实现文件）：

- 同一有效 ticket 携带 `Origin: https://evil.invalid` 兑换返回 403；随后携带正确 Origin 可成功兑换，证明拒绝跨来源且未提前消费 ticket。
- 独立登录 both 与 neither 两个统一身份，以 both 的已有业务 cookie 兑换 neither 的有效 ticket，返回 403；旧 cookie 随后访问该业务 `/me` 返回 401，直接重放原 cookie 也返回 401。同时原 both 统一身份 `/me` 仍为 200，排除了上游身份撤销导致假阳性。国内与海外均通过。

浏览器验收后正常 SIGTERM 停止本轮 runner，脚本返回 0 并输出 `CLEANED hx-p17-6e9b93470d8e`。已确认该前缀三个容器及网络不存在、3013 无监听；既有 `hx-overseas-p17-pg-test`、`hx-overseas-p17-redis-test` 等容器保留。
