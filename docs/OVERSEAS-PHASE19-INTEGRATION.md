# Phase19 真实两库 HTTP 集成验收

## 执行方式与隔离

复用 `hengxin-smart-image/infra/identity-test/run.py`、Phase17 三服务启动及 Phase18 显式注册/管理员授权。新增 `--phase19` 自动顺序执行 Phase17、18、19；`--serve` 全部通过后保留服务供真实前端浏览器使用。

```powershell
python hengxin-smart-image/infra/identity-test/run.py --phase19 --serve --origin http://127.0.0.1:3015
```

依赖本机已有 Docker 镜像 `postgres:17`、`redis:7`、`hx-management-test:local`，不安装新依赖、不调用真实钉钉或收费服务。每次随机创建 `hx-p19-<随机值>` 专用网络及 postgres/redis/runner 容器，只删除本次记录的精确名称。国内、海外使用独立数据库，迁移版本分别为 `0027` 与 `overseas_0004`；不连接既有 `hx-management-pg-test`、`hx-overseas-p19-pg-test` 或用户数据库。

仅钉钉 provider 在测试入口替换，任务、成员、身份票据、业务会话均通过真实 HTTP 服务；新增身份先真实登记为 pending，再通过已初始化管理员 API 授权。新增 `p19-operator2`、`p19-designer2`；保留 Phase18 五角色及原 fixture，供正式前端验证。

## 2026-10-12 当场结果

上述命令完成以下输出后进入 serve：

```text
PASS migration domestic 0027
PASS migration overseas overseas_0004
PASS ALL Phase 17 real HTTP integration
PASS ALL Phase 18 real HTTP integration
PASS Phase19 candidates validation persistence five-role scope filtering pagination idempotency
PASS Phase19 assignment old/new access stale409 current replay disabled recovery multi-role
PASS Phase19 fresh-session persistence exact event/outbox/request counts and all domestic rows unchanged
PASS ALL Phase 19 real HTTP integration
```

另执行 `python -m compileall -q hengxin-smart-image/infra/identity-test`，退出码 0。

Phase19 断言覆盖：

- 候选仅启用设计/设计主管，跨页无重复、搜索命中；纯管理员/运营排除；停用设计从候选移除且创建拒绝，恢复后重新兑换会话。
- 空白名称、重复 SKU（去空白与大小写）、空 SKU、额外 files 字段、非设计/空设计和缺幂等 key 拒绝；设计/设计主管/纯超管不能冒充运营创建。
- 多 SKU 创建真实持久化，created/version=1，创建事件一条；同 key 同内容重放同任务，不同内容409；另一个操作者同 key 独立。
- 五角色及第二运营/设计的精确可见任务集合；主管 mine；分页前 SKU 搜索/范围筛选、完整任务 ID、状态、稳定分页、边界参数、详情403/404。
- 仅设计主管/超管可改派；相同设计409、陈旧版本409、同 key 冲突409；旧设计立即403，新设计获得 task.design；重放创建返回最新版本；停用现设计后主管可接续改派；兼任运营/设计者改派后保留本人创建读取，但失去设计动作。
- 新登录会话读取 version=3 和审计；精确数据库计数为 4 任务、7 SKU、7 事件、7 outbox、7 幂等请求。失败和重放未增加记录；全部 outbox 未发布；海外没有国内 jobs 表。
- Phase19 前后对国内所有 public 表名及每张表完整行内容进行快照比较，相等。Phase19 仅操作海外会话，未以忽略会话表方式规避隔离断言。

本次 serve 初始实例为 `hx-p19-e17cfd73ee99`，主机端口国内 `64703`、海外 `64704`、身份 `64702`。端口每次随机，这组仅是本次执行证据，不得作为固定配置。前端 origin 为 `http://127.0.0.1:3015`。

## 验证边界

本报告只证明隔离测试环境下的真实 HTTP 与 PostgreSQL 持久化。PG 并发等锁/事务故障专项由后端测试单独验收；浏览器页面、真实钉钉企业凭据、生产部署、文件上传及分析执行不由本 harness 证明。Phase19 不启动业务 Worker，不消费 task.created 出站事件。
