# Phase 18 真实本地 API 联调

## 规划与验收矩阵

1. 复用 Phase17 唯一 Docker 网络、三进程、PostgreSQL 两库及 Redis harness；独立迁移国内0027、海外0003。只读挂载仓库，临时运行目录、环境白名单；只清理本轮资源。
2. 所有海外身份先走真实统一身份换票登记为 pending；用明确 test-corp 与 p18-admin,p18-admin2 调用正式 bootstrap 命令，再由真实成员API配置五角色，禁止首次登录提权。
3. 真实HTTP断言五角色 capabilities、四种非管理员访问列表/详情/审计/修改均403；分页、姓名/部门/状态/角色筛选、多角色授权pending、即时撤权和停用、版本409、最后管理员409、审计持久和独立重新请求、国内管理员cookie隔离及海外变更国内会话不变。
4. --serve 保留五角色、双管理员、pending及双业务测试身份供 localhost:3013 浏览器测试。外部钉钉 provider 是唯一替身，业务API、数据库与Redis均为真实组件。

执行：`python hengxin-smart-image/infra/identity-test/run.py --phase18`；浏览器联调加 `--serve`。测试身份：p18-operator、p18-operator_manager、p18-designer、p18-design_manager、p18-admin、p18-admin2、p18-pending、p18-dual。浏览器端口由每次 runner 输出的 LOCAL PORTS 给出。真实 PostgreSQL 并发竞态验收见成员后端测试证据。

## 执行证据

2026-10-12 实跑：`python hengxin-smart-image/infra/identity-test/run.py --phase18 --serve --origin http://127.0.0.1:3015`。

唯一资源前缀 `hx-p18-67ba06759d36`，国内/海外/身份映射端口60070/60071/60072；仅本轮资源。正式海外业务运行head `overseas_0003`，国内仍0027，双方核心表未混用。

输出 `PASS ALL Phase 17 real HTTP integration` 与 `PASS ALL Phase 18 real HTTP integration`。覆盖结果：

| 真实HTTP/数据库断言 | 结果 |
|---|---|
| 未登记bootstrap拒绝；九个身份首次登记pending；显式双管理员初始化；重复同配置幂等；另行提权拒绝 | PASS |
| 五角色登录兑换及/me能力；四非管理员列表/详情/审计/修改403 | PASS |
| 分页无重复；姓名/部门/状态/角色过滤；空结果；非法查询422、未知成员404 | PASS |
| pending激活兼任运营设计、角色去重、能力并集 | PASS |
| 陈旧版本409无部分更新；非法body422；错误Origin403 | PASS |
| 旧会话升权立即可访问、撤权立即403、停用撤销会话401 | PASS |
| 四次成功修改对应四条审计；JSON字段白名单；真实PG计数一致；新管理员会话读取一致 | PASS |
| 双管理员退为一名后，最后管理员禁用或去角色均409 | PASS |
| 国内super_admin的原cookie和改名cookie均不能访问海外成员API；双业务海外operator仍403 | PASS |
| 海外改角色及禁用不影响同身份国内管理员角色或会话 | PASS |

`--serve` 保留五角色、双管理员、pending、双业务身份。真实浏览器验收已通过：五角色及dual共6种身份，菜单/直链拒绝、多角色修改并GET回读、审计、刷新、切换、统一退出；390px窄屏横滚到编辑列并打开表单，保存按钮完整可见。Phase17四授权组合也已回归。见 `frontend/PHASE18-MEMBERS.md`（相对于代码根目录）。测试服务保留供独立审查，审查后由主线程清理并回写结果。`--origin` 只覆写本轮公开Origin，默认serve仍兼容localhost:3013。

同日独立使用默认internal网络复跑 `python hengxin-smart-image/infra/identity-test/run.py --phase18` 返回0。再次输出Phase17/Phase18全部PASS，三个API正常关闭，`CLEANED hx-p18-b2196435623c`；随后docker ps -a与network ls该精确前缀均无结果。前端专用serve拓扑保持独立，不受此次清理影响。

收尾：独立reviewer也完成浏览器及PG复验后，主线程停止本轮3015（核实PID47352为本项目Vite），runner收到TERM正常退出0。子Agent的serve会话句柄已不再可访问，因此主线程按精确名称删除本轮runner/Redis/PostgreSQL及网络；`docker ps -a`和`docker network ls`筛选`hx-p18-67ba06759d36`均无残留。全量测试专用`hx-overseas-p18-pg-test`、`hx-overseas-p18-redis-test`及匿名卷也已清理。原3012/PID48608预览和既有`hx-management-pg-test`保留。
