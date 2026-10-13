# 海外页面重验与成员字段修复

## 规划与验收

1. 排查focus/visibility重验及路由。证据：IdentityPortal.resume无条件调用load，load清空member，v-if还受busy控制，因此每次切回窗口都会卸载海外页面并显示入口。修复须保持同身份组件及草稿，合并并发重验，真正失败仍关闭旧身份。
2. 海外成员弹窗、表格、搜索提示移除部门；保留协议兼容，避免为界面调整重启后端或迁移生产数据。
3. 用户明确授权张帅全部权限：调用正式patch_member，自身已有super_admin，增加完整五角色，核对八项能力并保留审计。已在生产执行成功。
4. 组件/重验回归、类型、正式构建、CSS入口回归和真实浏览器验证后独立两阶段审查；提交后仅发布前端0.2.24，再验证生产会话与界面。

## 验证

- 张帅生产只读复验`output/overseas-grant-verified.json`：active、完整五角色、完整八能力，update审计时间2026-10-13 03:01:39.387856 UTC，审计角色匹配。仅该账号授权，不改全局角色矩阵。
- 首轮审查Stage1发现根元素inert不能覆盖teleport到body的弹层，FAIL且未执行Stage2。已改为body.inert覆盖页面及弹层，成员禁用确认在组件卸载时关闭；重新固定快照并交新reviewer。
- 最新前端292项测试通过，包括6项重验控制器测试及4项编译真实IdentityPortal.vue、以Vue renderer挂载的生命周期测试：focus+visibility去重、等待时原组件不卸载、body锁定、有效同身份草稿保留、401/403/503清业务、晚返回不恢复旧身份。测试对子页面和IO替身，不冒充真实浏览器焦点事件。
- 正式构建31.42s通过、类型检查通过、6入口CSS回归通过、4发布测试通过。日志`output/overseas-session-hotfix-{build,typecheck,tests}.log`。
- 正式dist浏览器成员列表和弹窗无部门，搜索提示只显示姓名，拥有提交能力的fixture侧栏显示提交图需。截图`output/session-hotfix-members-dialog.jpg`。IAB自动切换标签未观察到可验证的focus请求，因此该动作不作为重验测试证据，重验路径以上述真实组件事件测试为依据。
