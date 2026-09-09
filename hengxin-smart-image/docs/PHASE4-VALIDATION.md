# Phase 4 前端验证记录

日期：2026-09-09。基线 df13884。范围：调用统计、执行监控、用户角色、Skill 管理、系统配置、钉钉登录状态与四角色导航。Product-Spec v0.14 明确四角色均可编辑、返工及归档全员业务资源。当前为前端模拟及 HTTP 契约验收，不是实际钉钉/CLI/后台授权验收。

| 检查 | 当场结果 |
|---|---|
| 独立审查 | 最终 Stage 1 / Stage 2 PASS，无遗留 HIGH/MEDIUM；详见 PHASE4-REVIEW.md |
| 单测及服务集成 | `npx --yes pnpm@10.33.4 test`：37 tests / 37 pass / 0 fail，1684.8425 ms；最终审查独立复跑 37/37，1740.1108 ms |
| 严格类型与生产构建 | `npx --yes pnpm@10.33.4 build` → `vue-tsc --noEmit && vite build`，built in 29.17s，exit 0 |
| auth-flow.js | 7 种登录异常、重试恢复、容器入口、安全回跳、四角色菜单、身份变更重建路由、真实 401/503 分流、业务 401 立即锁定、真实模式无角色工具，PASS |
| management-flow.js | 统计汇总/明细/空数据/读取失败重试；监控 idle/unknown/存储异常及主管详情隔离；成员角色必填、保存失败保留与重试、启停；配置失败保留、版本递增和审计、HTTP 域名拒绝；ZIP 接收、安装失败保留旧版、重试/停用/启用，PASS |
| api-flow.js | HTTP 25 成员分页、搜索重置与迟到响应、503 保留旧列表及重试、403 清除受限数据、保存失败保留输入与双击只提交一次，PASS |
| visual-flow.js | 五管理页 1280px 无横向溢出；与任务页邻居实际截图对照；Worker 失联/认证拒绝/限流/超时分别表达，PASS |
| Phase 3 create-flow.js | 壁纸/商品 8 张、文字 2 张、SKU 检索、整套返工 8 位置全部更新，PASS，pageerror=0 |
| Phase 3 version-flow.js | 单图失败保留旧图、重试原范围、其余 7 槽不变、历史下载、实际 ZIP、当前版本幂等归档、删任务旧新成品仍在，PASS，pageerror=0 |
| Phase 2 template-flow.js | 模板必填、排序持久、保存失败保留、版本递增、使用深链接、删除取消/确认、草稿不可生成、无 Skill 文字阻断与列表重试，PASS |

浏览器使用独立内存会话 hx-phase4（登录子任务先用 hx-phase4-auth），访问本地 3008 和临时 3018。命令、测试文件准备及复跑顺序见仓库 scripts/phase4/README.md。所有请求拦截仅存在于测试浏览器，不连接生产系统。

## 修复闭环

- 历史统计改为独立账本，删除业务任务后新建数和已发生执行量不减少。集成测试实际比对删除前后 summary。
- 跨创建人返工、归档与删除按实际操作者记录，监控从本轮 attempt 取操作者；四角色测试均使用与 fixture owner 不同的身份。
- 配置上传上限应用于后续文件接收；并发/超时按轮次冻结，更新不追溯旧轮次。合法 60 秒超时配置通过受控时钟前移实际触发停止分支，旧版本保留。
- 监控独立表达空闲、未知、失联、依赖不可达、认证拒绝、限流和超时；最近结果取最近已结束 attempt，不把历史成功冒充当前健康。
- 配置表单响应式对象通过 JSON 边界复制；保存仅传可编辑字段，避免 dingtalk.state 造成虚假审计。安装受理后先更新返回状态，再读回列表，读取失败不把旧上传状态误当可重新安装。
- 旧单测固定等待 45ms 改成有界状态轮询，保留所有版本和归档断言，避免机器负载导致计时误报。

## 视觉与边界

本机 output/playwright 中保留 phase4-usage-1280.png、phase4-monitor-1280.png、phase4-users-1280.png、phase4-skills-1280.png、phase4-settings-1280.png、phase4-neighbor-tasks.png、phase4-monitor-timeout.png、phase4-login-container.png、phase4-login-expired-real.png。管理页复用 Art 标题、卡片、表格和按钮，未修改原 prototype/source。

没有新增运行时依赖。真实模式不会使用 URL 角色或故障参数获得模拟身份；只展示登录入口与接口状态，实际 SDK、企业账号映射、Cookie/state 验证、双端兼容在 Phase 12/14 进行。模拟 ZIP 只验证上传与生命周期，不执行包，不能当作真实 Skill 安装验证。

前端技术验收后才进入 Phase 5；真实服务、数据库、存储、持久队列与 CLI 尚未接入。本机原有 .idea 和自动生成组件声明不属于本轮业务提交。
