# 国内每轮显式 Skill · 部署验收 2026-11-13

正式入口：`http://192.168.1.245:8080/domestic/`，主机 `hengxin-ai-245`。

## 交付与版本

- 功能提交 `9a884b7cee60b1a0965b49cfc97c0940c1811790`，国内前后端实际版本一致；前端 0.2.71。
- 五工作台在上传附件左侧显示已绑定 Skill 的勾选项，默认不选；仅本轮明确勾选才使用，发送成功后清空选择。未选可继续会话和修改上一张图；不挂载 Skill 文件、不注入 Skill 调用。未知结果重试保留原请求，明确失败保留可编辑草稿。
- 绑定改为提供可选 Skill；未绑定允许普通发送。无新依赖、迁移或数据库结构变更。
- 海外/共享前后端仍为 `2bc8acc7ecf412626a6a635a9413b1644b55417e`。14 个非国内进程/容器的身份及启动时间与发布前相同；这不表示下面维护标记问题期间业务入口未受影响。
- 当前工具 `/opt/hengxin-intranet-tools/releases/27edb514d44614af`；对应修复提交 `5d30448`、`db89712`，仅在旧工具清单上增加本次已审配置保留、测试隔离和入口恢复改动，没有重跑联合迁移。

## 发布凭据

- 包由已提交源码通过 `package_release.py --scope domestic` 构建，5,868,929 字节。
- SHA256：`0038fc916059e397f12d56865f09c04b84aa1353918b356000c61f528c4bfb0b`。
- 正式发布目录 `/opt/hengxin-unified-releases/lan-domestic-20261113-skill-9a884b7`。
- 成功事务 `/var/lib/hengxin-release/intranet-transactions/lan-domestic-20261113-skill-9a884b7-1794553681277974497`。
- 使用服务器 current 工具执行 stage、prepare、deploy、verify。最终 pending=null，国内 previous 保留上一成功版本。
- 自动清理成功：保留全部受引用源码与镜像；删除已恢复失败事务及附带备份。工具同口径统计 3,833,801,877→3,833,302,165 字节，净释放 499,712 字节；未删除业务数据。

## 验证

- 功能独立两阶段审查通过：[功能审查](reviews/DOMESTIC-EXPLICIT-SKILL-20261113.md)。
- 前端 567 项测试、类型检查、生产构建通过；本地真实 Vue 页面隔离浏览器覆盖五入口、勾选→提交清空→下一轮空 Skill、草稿、重试及桌面/窄屏，共15次拦截请求；独立 reviewer 重跑通过。
- 后端隔离 PostgreSQL/Bubblewrap 合计176项通过、19项环境条件跳过；其中真实沙箱验证选 Skill 后下一轮无 Skill 文件并继续 session。初次2项子进程环境失败在补齐 PYTHONPATH 后补验通过。
- 发布工具最新本地全套396项、15子测试通过，5项跳过。入口恢复独立复跑36项及5文件编译通过。服务器最终安装路径在只读宿主根、独立 /tmp、无网络 Bubblewrap 内执行394项、15子测试通过，5项跳过；工具基线测试清单与本地退役后清单有2项差异。
- 正式 `verify` 与恢复入口时的完整 runtime capture 都通过：实际源码、配置、数据身份、镜像、schema、健康和台账一致。
- 正式 Chrome 重新连接后打开“只换产品”：页面准备就绪，`国内通用型产品替换` 显示在上传附件左侧，checkbox=0，发送可用；原8个附件草稿仍在。没有代用户发送真实模型任务。

## 发布中故障及恢复

首次国内发布发现旧工具生成原生配置时只保留 WorkingDirectory，覆盖联合升级写入的门禁和工作台环境，运行核验拒绝。先执行官方 `recover --scope domestic` 恢复原版本并验证；工具改为仅替换目录、保留原配置，异常结构拒绝，独立审查通过后重新发布成功。见 [配置修复审查](reviews/INTRANET-NATIVE-CONFIG-PRESERVE-20261113.md)。

随后页面验收发现503：安装时以root运行旧工具测试，原生迁移失败测试缺少门禁隔离，15:07:15误把真实HTTP标记设为closed，影响业务入口；后台标记保持open。这是本次执行造成的问题，健康接口正常不能代替业务入口验收。

修复测试内存门禁并限制假写入只能落到临时目录；安装测试进一步置于宿主文件系统只读的沙箱。新增已审 `release.py restore-ingress`，沿全局锁，要求联合升级complete、无pending、后台已开放，完整核对当前台账和运行状态后再次核查无漂移，才开放HTTP入口，未手工写open、未跳过核验、未回退数据库。见 [恢复审查](reviews/INTRANET-INGRESS-RESTORE-20261113.md)。

最终两标记实查均为open，`ingress-restore-last.json` 为 phase=opened，核验状态摘要 `69942482d446a8fe6882e3abed060832c2037c86a0fed6e19934ccfed8e32066`；正式浏览器会话已恢复。没有遗留发布pending。

原始证据位于 Git 忽略的 `output/explicit-skill-*`、`output/domestic-explicit-backend-*` 与 `output/playwright/domestic-explicit-skill*`。跳过项及拦截浏览器测试不算真实付费模型生图验收。
