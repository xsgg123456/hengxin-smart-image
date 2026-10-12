# Phase 18 五角色与成员管理实施合同

先策略与接口合同，再后端/前端分别实现，最后真实两库联调、一期回归、独立两阶段审查。本地开发，不部署或调用模型；不重复创建Phase17成员/角色/会话表。

## 18.1 权限与范围

直接复用Phase17 CurrentMember、member_roles及一期Depends授权模式，海外策略独立。每请求读取当前启停和角色；不从浏览器、国内角色、钉钉职称授予权限。多角色取并集，空角色/未知角色/非active拒绝。

| 能力 | 运营 | 运营主管 | 设计 | 设计主管 | 超级管理员 |
|---|---|---|---|---|---|
| task.read / stats.read | 本人提交 | 全部海外 | 分配本人 | 全部海外 | 全部海外 |
| task.create | 是 | 是 | 否 | 否 | 否（可兼任运营） |
| task.design（确认/返工/审核等设计动作） | 否 | 否 | 分配本人 | 全部海外 | 否（可兼任设计） |
| task.reassign | 否 | 否 | 否 | 全部海外 | 全部海外 |
| members.manage / skills.manage / settings.manage | 否 | 否 | 否 | 否 | 是 |

task/stats仅实现可复用策略及SQL范围条件，任务模型和路由在Phase19以后接入，不虚构任务API。列表、详情、动作使用同一权限判定；范围输入为created_by、designer_id，兼任普通运营/设计取两者并集。

海外 `/auth/me` 与兑换响应保留id/name/status/roles，新增 `capabilities: string[]`，采用上述能力名。前端只以服务端能力控制菜单；未交付模块不出现可点击的假入口。此次正式管理中心仅接“用户与角色”。

## 18.2 成员接口与安全

路径前缀 `/api/overseas/v1`，全部使用海外会话，只有members.manage可访问。修改额外复用X-HX-Request与Origin校验。

- GET `/members`：search(姓名/部门，最多100字符)、status(active/pending/disabled)、role(五角色)、page(默认1)、pageSize(默认20，上限100)；响应 `{items,total,page,pageSize}`。
- GET `/members/{id}`：详情，非存在404。DTO `{id,name,department,roles,status,version,createdAt,updatedAt}`。姓名/部门来自已验证钉钉资料，只读，不提供任意新增或删除身份接口。
- PATCH `/members/{id}`：body严格 `{roles: string[],status: 'active'|'disabled',version: int}`，角色去重、只接受五角色，active必须至少一角色；返回最新DTO。版本冲突409，保存失败不部分写入。
- GET `/members/{id}/audit`：返回 `{items: [{id,actorId,action,before,after,createdAt}]}`，至多最近100条；审计和变更同事务。before/after仅角色、状态、版本，禁止身份令牌/密钥。
- 复用既有乐观版本与事务模式。海外PostgreSQL事务级管理锁串行化权限变更/初始化，获取锁后重新读取操作者最新启停/角色，避免等锁期间被撤权还继续授权。不能禁用或移除最后一名active超级管理员；两个管理员并发互相/自行降权也不能清空管理员。
- 停用时撤销本成员全部海外会话。角色变更不强迫重登，但下次请求读取最新角色，旧权限立即失效；不修改国内会话或角色。
- 海外0003给Member增加version、增加海外审计表，迁移兼容已有pending/active成员；不修改国内schema。

初始管理员只通过独立 `OVERSEAS_BOOTSTRAP_ADMIN_CORP_ID`、`OVERSEAS_BOOTSTRAP_ADMIN_USER_IDS` 明确指定。独立命令 `python -m app.overseas.members.bootstrap`，只授权已通过统一身份登记的本企业成员；配置空/成员缺失/已有有效管理员拒绝（已完成同一初始化可幂等无变更）。不得每次登录或进程启动重新提权，不读取国内管理员配置。配置目标身份在部署前由用户决定，本地仅隔离测试身份。

## 18.3 前端复用

直接续建 `views/overseas/admin/OverseasMembers.vue`，复用ArtTable、既有管理卡片/表单与海外框架。通过适配器/props区分旧模拟预览和真实数据，禁止复制整页。真实模式不展示新增/删除、模拟角色切换；五角色多选，姓名/部门只读，状态筛选、分页、空/加载/错误/重试、禁用确认、版本冲突刷新提示完整。

正式海外路由含 `/overseas`、`/overseas/admin/users`；只给members.manage展示管理菜单，直链仍校验。401/403收起敏感内容，当前权限丢失时移除菜单并阻止后续操作；网络故障不能保留可操作的旧授权。刷新/切换/统一退出沿用Phase17。其余管理五页继续独立模拟预览，等待Phase24。

## 验收与分工

主Agent：18.1策略/SQL范围/现有auth响应、主路由接线、迁移回归适配、集成与总体验收。后端worker：members目录、Member.version、overseas0003/env注册、bootstrap配置/Compose例子、成员测试。前端worker：前端适配/成员页/正式框架/权限刷新及前端测试。互不回退其他人的变更，审查与提交由主Agent统一。

完成标准：五角色与兼任的列表/详情/动作范围一致；国内管理员拒绝；普通角色不能调用成员API；真实PG并发保护最后管理员与版本冲突；审计持久化；停用/撤权后的旧会话验证；真实浏览器五角色菜单与直链、编辑多角色、失败/冲突/窄屏；全量回归、编译、独立审查通过。

实现参考：PostgreSQL事务锁自动随事务释放（https://www.postgresql.org/docs/17/explicit-locking.html）；SQLAlchemy populate_existing刷新已加载实例（https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html）。继续使用锁文件版本，不新增依赖。
