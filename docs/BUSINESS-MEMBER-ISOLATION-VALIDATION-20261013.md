# 国内与海外成员隔离：本地验收与发布准备

日期：2026-10-13。本轮只在本地独立数据库、Redis与容器中验证；未部署，未读取或清理生产成员。

后续发布阶段已完成生产0.2.29上线及四条用户明确确认的海外空档案清理，生产验收与恢复材料见 [发布记录](BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md)。本文保留本地阶段的验证边界，不代表当前生产仍未整改。

## 实现范围

- 统一钉钉身份保留；业务选择只查询状态，进入某一业务才创建该业务会话。身份票据同时绑定业务和 `access/session/application` 用途。
- 国内旧网页回调、容器登录和双边会话兑换均禁止给普通未加入用户建档；国内明确配置的首位管理员初始化保留独立审计。
- 双业务分别申请、撤回、拒绝、重申、审批；审批在事务内写成员、角色与审计。停用人员不能通过申请恢复权限。
- 默认成员目录仅显示已确认归属的成员。主动申请与历史待核对独立分页计数；历史人员普通编辑不能授权，明确申请审批后可复用原成员ID。
- 国内0028、海外0014新增归属字段及独立申请/事件表；国内增加成员审计表。迁移将旧pending标为legacy，不删除历史成员或业务数据。
- 浏览器用统一身份会话ID校验业务会话，不按姓名复用身份；同身份窗口恢复保留页面。
- 历史核查/校正工具默认只读；执行要求指定业务、审核名单、完整快照和恢复目录，执行前锁定复查引用，保存恢复包后才删除确认的空壳。

实施合同：[整改方案](BUSINESS-MEMBER-ISOLATION-PLAN-20261013.md)。历史工具参数及恢复步骤：[工具说明](../scripts/maintenance/README.md)。

## 验证记录

以下命令在仓库根目录执行；前端命令在 `hengxin-smart-image/frontend` 执行。临时数据源通过专用测试变量注入，未读取生产 `.env`。

| 验证 | 命令/证据 | 结果 |
|---|---|---|
| 后端针对性回归 | `pytest` auth/成员/配置/迁移/PG并发集合；`output/member-backend-targeted.log` | 171 passed |
| 后端最终审计调整回归 | `output/member-backend-final-smoke.log` | 50 passed，包括申请28项、升级/回退/再升级2项 |
| 身份票据最终增量 | `pytest tests/test_identity_service.py tests/test_identity_client.py tests/test_identity_ticket_purposes.py -q`；`output/member-identity-final.log` | 32 passed，真实独立Redis；包含全套之后新增的expectedSessionId竞争窗口3项 |
| 维护工具 | `python -m pytest scripts/maintenance/tests -q --tb=short` | 60 passed / 1不适用分支skip；PG10项全部执行 |
| 后端Linux全套 | `python hengxin-smart-image/infra/overseas/regression.py`；`output/member-linux-pytest.log` | 2151 passed / 17 skipped / 15 warnings，465.24秒，退出0并清理临时容器 |
| 双库真实HTTP | `python hengxin-smart-image/infra/identity-test/run.py --members --serve --origin http://127.0.0.1:3013`；`output/member-final-http.log` | Phase17及成员隔离全部PASS |
| 既有角色/任务HTTP | `python hengxin-smart-image/infra/identity-test/run.py --phase19`；`output/member-phase19-http.log` | Phase17/18/19全部PASS；精确事件/outbox/request计数及国内全表不变通过 |
| 前端全套/类型/构建 | `pnpm test`、`pnpm typecheck`、`pnpm build`、`pnpm build:overseas`；`output/member-frontend-{tests,build,preview-build}.log` | 335 passed / 0 skipped；类型通过；正式构建35.99秒、海外预览35.51秒通过 |
| 浏览器与窄屏 | `node tests/member-isolation-real.browser.mjs`；`output/member-frontend-browser.log` | 两业务完整流程、同名换号及确认后换号竞争窗口全部PASS，退出0；390px祖先裁切检查、表格横滚审批实点通过 |
| 身份真实组合/故障 | `node tests/unified-identity-real.browser.mjs`、`node tests/unified-identity-faults.browser.mjs`；`output/member-unified-identity-{real,faults}.log` | both/domestic/overseas/neither组合、退出、503重试、403与初始化隔离PASS |
| 成员故障交互 | `node tests/overseas-members-faults.browser.mjs`；`output/member-overseas-members-faults.log` | 多角色拒绝、分页、409刷新、禁用确认、空态、窄屏、断网、401/403/撤权PASS |
| 独立并发首次申请 | `output/member-review-concurrency.py`；`output/member-review-concurrency.log` | 两业务分别8次并发首次提交，均同一ID/version=1、1条申请/1条submit事件，0成员/身份/角色/会话；随机PG schema已清理 |
| 独立两阶段审查 | [审查报告](reviews/BUSINESS-MEMBER-ISOLATION-REVIEW-20261013.md)；`harness.py review-prepare` / `review-approve` / `review-status` | Stage 1 PASS / Stage 2 PASS；快照 `a527f5b1b6eef7553b8d6699408ad6ac980c22a580eaa2831d197fbf575e0bd1` 已登记；最终approved=true、changedFiles=[] |

Windows完整回归中安全文件打开和符号链接测试受操作系统限制，最终以相同工作区代码在Linux隔离容器的完整结果为准，不删除相关断言。既有Phase18/19脚本仍保留早期“多角色、管理员无提交/设计能力”的断言，本轮同步到已经存在的单角色及超级管理员能力合同；不改变生产任务权限。

Linux全套17项跳过为现有root/Bubblewrap技能权限专用环境及非root WSL运行条件；当前新成员/申请/身份测试均执行。构建期间曾有Windows自动导入缓存并发写入失败，停止本轮开发服务后串行构建成功；已恢复无关自动生成声明，不作为产品代码改动。

真实HTTP对两库成员、身份、角色、会话、申请、事件及成员审计行做完整快照比较，验证重复access零业务写入、仅所选业务创建会话、申请审批不改变另一库；包含并发审批200/409、停用拒绝、自助申请拒绝、历史ID复用、跨业务管理拒绝及错用途票据。

最终身份增量修复：在前端确认与签发票据之间发生跨标签换号时，`expectedSessionId`必须匹配签发时的cookie身份，否则401且Redis无新增票据；原会话已签发票据在换号后也兑换失败。这3项分别对access/session/application执行，不把同名当同身份。

浏览器使用已安装Playwright包通过 `PLAYWRIGHT_MODULE` 指定路径，仅访问独立本地 `IDENTITY_UI_URL=http://127.0.0.1:3013`。业务申请/审批主流程不拦截接口；换号竞争窗口测试仅延迟/转发真实身份me响应，在其间真实更换cookie身份，实际票据接口返回401，业务申请/会话接口零调用。

稳定截图位于 `output/playwright/member-isolation/`：两业务 `applications.png` 桌面申请目录、`mobile.png` 390px目录、`approval-mobile.png`审批表单、`entry-mobile.png`申请入口。已与既有成员页比对，继承Shell、hx卡片、Element控件；移动菜单关闭，弹窗关闭动画结束后截图，按钮/提示相对裁切祖先可见。表格在窄屏允许组件内部横滚，审批按钮通过横滚后实际点击验证。

收尾：本轮创建的PG、Redis、HTTP拓扑及Vite3013均已关闭清理；既有其它服务保持原状。测试日志与具名稳定截图保留供复核。114个新增/修改代码文件均不超过300行，最大297行；无关自动生成声明已恢复，`compileall`和`git diff --check`通过。未执行Git提交、推送或部署。

## 发布与回退顺序

1. 获得本轮发布授权后，备份国内/海外数据库并确认可恢复；先分别运行只读历史核查导出，保存名单和角色/资源引用摘要。
2. 在预发布备份副本验证国内0027→0028、海外0013→0014，核对原启用/停用成员、角色和业务引用保留，旧pending仅改归属标记。旧待授权记录不自动转换为主动申请。
3. 身份服务、国内后端、海外后端与前端作为同一发布单元。滚动切换期间旧无用途票据会拒绝，前端需刷新重试；不得恢复隐式建档来兼容旧页面。
4. 检查既有管理员可用、两边成员/申请/待核对数量、只读选择、双向独立申请审批、撤回拒绝、同名换号及最后管理员保护。真实企业钉钉登录需在实际部署后单独记录证据。
5. 历史清理独立审核与执行。默认只读报告和模拟；没有确认名单不删除。不得将“海外pending且国内有同名人员”当删除依据。
6. 回退不恢复旧自动双边建档代码。优先回滚到保留隔离的兼容版本，必要时临时关闭新申请入口并保留既有合法会话；审计/申请表有新数据时禁止直接降级删除新表。
7. 必须整体数据库恢复时，按备份时间点评估新业务数据并在维护窗口执行；核查工具的逐条恢复仅用于该工具删除的legacy空壳，不能替代整库备份。

本地迁移回退测试证明结构可升级/降级/再升级，不构成生产恢复授权。历史名单尚未核对，不声称截图中的具体人员已完成归属纠正。
