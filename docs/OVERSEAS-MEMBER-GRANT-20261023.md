# 海外成员完整授权

用户2026-10-23要求撤回权限配置预览，直接给温晓芳与张帅相同的海外权限，角色不变。真实只读核验确认两人均为已加入/启用成员，分别为design_manager/super_admin；张帅拥有全部9项能力及Skill开关。唯一ID保存在本轮私有部署材料，不按姓名执行授权。

1. 回滚本轮preview-permissions和预览文档、关闭本轮服务；正式前端无变更。
2. 后端海外配置增加完整授权成员UUID集合。授权计算使用完整管理员策略，存储/接口展示的实际角色仍为design_manager；启用和合法单角色校验先于追加权限。相同姓名及其他设计主管不受影响。
3. Skill开关允许原绑定所有者和显式完整授权成员；仍需skills.manage接口权限，原Skill状态及配置不改变。
4. 隔离测试验证全部能力、非本人任务范围、真实角色不变、同名拒绝、禁用/未加入/无角色拒绝、旧会话重新校验、撤销、原所有者保留、管理及Skill操作审计。
5. 独立两阶段审查。部署仅海外API：从实际运行镜像构建四文件增量镜像，安装包运行测试；保存原镜像/Compose配置和数据库备份，原配置保留，只追加指定UUID绑定。无需迁移/前端发布/原生Worker切换；更新API前核实执行状态及持久恢复边界，不中断工作进程。线上服务探针核实双方全部能力和资源范围一致，数据库角色原样保留，写授权审计；正式HTTP健康接口和当前管理员浏览器做只读冒烟，不伪造目标成员登录会话。保留回退镜像和撤销方法。

此项变更不需要新设计或通用权限管理开发计划；正式页面沿用既有按后端capabilities展示的菜单。后续发布必须保留新增配置，避免授权丢失。

## 验证进展

- 已撤回本轮所有预览源码，正式前端未改；3027预览服务已停止。
- 本地专项6文件128项通过，2项既存弃用警告。覆盖同角色其他成员不扩权、唯一ID绑定、原角色/操作者保留、既有会话撤销、停用/未加入/无角色、Skill真实审计、最后管理员保护及非本人任务修改重提。
- Windows海外回归522通过、103跳过、8失败：7项为安全文件打开缺失POSIX支持，1项为系统无符号链接权限；不宣称Windows全通过。
- 实际生产源文件旧SHA256全部匹配；待发布镜像从运行中海外API镜像派生，仅复制4个后端文件与新测试，无账号ID写入镜像。真实安装测试network none、无生产环境变量/挂载，128通过（19.73秒）。
- 镜像准备阶段修复FROM镜像ID解析和COPY 0600问题，均在安装测试阶段拦截，尚未切换生产。最终已准备镜像a49cedf7f9c3f1b191d5ca716813645f47fb05ee12aff1ac429f82fc18057a18。
- Dockerfile行为核对官方文档：https://docs.docker.com/reference/dockerfile 。
- Linux实际镜像完整海外回归：548 passed、67 skipped、2 warnings，215秒。命令 `docker run --rm --network=none --entrypoint sh hengxin-overseas-member-grant:99cd4b924de55813 -c 'python -m pytest -q tests/test_overseas*.py'`。
- 发布前pause脚本第一次因SessionTransaction没有scalar失败，未暂停/切换生产。已改为sessionmaker.begin，AST提取的实际pause/resume两条代码在原API内运行并显式rollback，两条通过；之后探针与发布前状态完全一致，gate仍False。修正独立送审，镜像业务代码未改变。

## 线上交付结果

- 已部署仅海外API增量镜像，容器c20400df7ce1 healthy。新候选 `3e3178873ff8f25a41c8c5b3cebf719a6fd341a667442f932e4f23f67fc38818` 两阶段PASS并登记，交付review-status approved true。
- 服务探针：双方9项capabilities完全相同，Skill开关均true；温晓芳真实角色design_manager，张帅super_admin，成员版本/状态/角色均与发布前一致。现有1项任务的全部9种权限判定一致，业务任务数量、Skill启用状态/版本、数据库版本overseas_0020不变。已写入full_access_grant审计，操作者张帅、目标温晓芳。
- 其他运行容器的ID/镜像/启动时间严格一致；执行Worker未重启。最终二次探针paused false、activeJobs 0，API healthy。VERIFIED.json是恢复前快照（paused true）；最终状态以FINAL-VERIFIED.json为准。
- 正式Chrome使用张帅现有登录刷新用户与角色页，正常显示温晓芳“设计主管/启用”和张帅“超级管理员/启用”。未代登录温晓芳，未在生产执行删除/重提/Skill切换；这些写路径由隔离测试覆盖，不能声称目标浏览器逐项点击已验收。
- 生产证据、备份和原配置保存在服务器root私有目录 `/opt/hengxin-releases/member-grant-20261023`，包括before.private.json、prepared.private.json、overseas-before.dump（pg_restore --list验证）、grant-overlay.json、all-overseas-tests.log、deploy.log、FINAL-VERIFIED.json。最终脚本SHA256 e10677f011378ea7d9a0dea71ae4e6b9c3d129399bbbd89449e3d705d2c78318；完整复核包reviewed-patch.tar.gz与本地output/member-grant-20261023/patch.tar.gz一致（a5e0d73d587c261247f3be38d5bcefb17419dee42b395abce764460a549a6209）。

## 保留与回退

本轮是API单独补丁，前端版本和原生Worker未发布；后续正式API发布须同时包含四文件代码与OVERSEAS_FULL_ACCESS_MEMBER_IDS配置。当前Compose配置链已包含grant-overlay.json；不要用旧发布指针直接覆盖该授权配置。

撤销授权：在实际生效的Compose覆盖文件把OVERSEAS_FULL_ACCESS_MEMBER_IDS改为JSON空数组 `[]`，沿当前完整Compose配置链仅重建api（--no-deps --no-build），验证温晓芳恢复设计主管默认4项能力及Skill开关false、张帅不变。此操作需先取得对应撤销授权；本轮未执行。

回退代码：先检查执行队列并保留审计；以before.private.json的原始Compose文件/env链为底，额外覆盖api.image为保存的原镜像 `sha256:f208b2cfc9fecaaf1c429a0d0ec4a5768105ab4a932cb9637ffcf61b654124f7`，仅重建api并核验健康及默认权限。保留完整授权审计，不恢复整库覆盖期间新业务数据。本轮未迁移数据库，不需要数据库回退。gate.pause只停止新认领，不阻止入队；任何失败先检查gate实际状态后恢复，不能盲目重跑deploy。
