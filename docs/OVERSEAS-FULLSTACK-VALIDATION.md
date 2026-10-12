# 海外二期全流程验收

Phase25交付证据入口，进度以根目录DEV-PLAN.md为准。本文将已完成的Phase16–24证据与最终隔离/恢复验收合并，不以文档代替测试。

## 行为与证据映射

|范围|实际验证入口|所证明行为|
|---|---|---|
|统一身份及双业务|infra/identity-test/checks.py、phase18_checks.py|海外单独身份、五角色/兼任、国内Cookie不互认、停用撤权、身份服务失效关闭|
|任务与资料|phase19_checks.py、phase20_checks.py|必选设计、多SKU、原文解析及私有字节、幂等提交、SQL权限分页、改派旧设计撤权|
|执行调度|phase21_checks.py、backend/tests/test_overseas_concurrency.py|真实Redis/outbox、游标、取消、12线程竞争6作业仅5领取、租约失效占槽且不重放|
|方案与生图|phase22_checks.py、phase23_checks.py|真实离线进程输出协议、完整SKU方案、修改重分析、确认一次、多SKU部分失败恢复、原图验证、历史版本、全通过后冻结ZIP|
|管理|phase24_checks.py、test_overseas_management*.py|当前权限统计、实际usage采集、不可变Skill版本、配置审计/并发、暂停和冻结、生图重试继承原快照、人工返工使用当前绑定|
|浏览器|frontend/tests/overseas-*-real.browser.mjs及既有故障浏览器|正式API图片/历史/归档下载、五角色管理、配置409保留草稿、Skill版本和启停、窄屏；mock用来注入断网/500/撤权等故障|
|资源凭据|infra/overseas/verify_resources.py|两套真实PG/Redis/MinIO凭据双向互访拒绝、DML允许DDL拒绝、应用不持root秘密、私有桶、资源故障ready503/live200和恢复|

## 最终本地运行

Phase24已提交`e0c2acc`。本阶段新增`infra/identity-test/phase25_checks.py`、`object_restore.py`、`database_restore.py`及`--phase25`入口，复用完整Phase17–24流程后继续验证派生资源撤权、会话失效和备份恢复。没有另造业务流程。

已建最新后端镜像`hengxin-smart-image-backend:phase25`，`output/phase25-image-build.log`记录镜像构建；镜像manifest list为`sha256:c75b5a05aee5d3101226c646f850ba8a7a7ec73c38c380de61695f4f5f1f05d9`。该镜像已通过独立Compose资源隔离检查，`output/phase25-resource-isolation.log`全部PASS且仅清理本次资源。

真实Phase17–25 HTTP通过：已归档任务改派后，旧设计的任务、资料原件/解析、方案、图片当前与历史、jobs/events、归档ZIP直接请求403，任务/归档/监控列表及统计不泄漏；新设计、原运营、双主管和管理员可读且图片/归档内文件哈希相同。改派不增加5个既有作业或executionCount。禁用新设计并重新启用后旧cookie仍拒绝，重新登录恢复；finally还原派单和成员，国内全部业务表及对象etag不变。

对象恢复演练已通过：从测试源桶备份12个对象、937字节到新私有备份桶，再从备份恢复至另一空桶；全部key、size、SHA256和content-type一致，匿名访问两桶均AccessDenied，源字节和etag不变。只清理本次两个随机桶。对象与数据库恢复均在所有API退出后执行，不在活跃写入时比较快照。

最终回归结果：后端`2038 passed, 17 skipped, 15 warnings in 350.51s`（`output/phase25-backend.log`）；前端282项通过、0跳过，类型及生产构建通过（36.33s），`output/phase25-frontend-{tests,build}.log`。17项既有跳过为Linux root/nobody/Bubblewrap显式开关用例16项，以及既有非root WSL运行时1项；它们未在此通用容器完成，不能计为通过。

七组真实API浏览器最终全部通过（`output/phase25-browser.log`），无route模拟。旧Phase17/18/19脚本仍断言正式业务尚未接入，更新为服务端真实capabilities对应菜单；保留无模拟角色切换、无权限直链、Cookie撤销及真实写入审核断言。方案与图片均有SKU页签，旧方案脚本改为精确选方案区域的首个页签，断言内容保持。

浏览器结束后的数据库演练已通过：PG17容器内`pg_dump -Fc`→新空库`pg_restore --exit-on-error`，27张表/序列、459行、110472字节备份，全部表行SHA256与序列位置一致，源库未变；恢复库随后删除，仅清理本次容器。日志`output/phase25-http.log`。最终入口改为API全部停止后再做对象备份恢复，外层接续数据库恢复，保证两者在同一静止写入区间；完整复跑通过`output/phase25-http-final.log`，27表/序列、360行、99700字节，差异来自无浏览器增量。

独立审查要求将达到311行的总入口按职责拆分，已新增16行`shutdown.py`，总入口300行，保持写入静止边界与失败不放行；修后再跑全部真实HTTP/恢复。DEV-PLAN总览中的历史阶段状态也已统一，具体审查与最终日志以同名报告为准。

最终批准快照`5072f0ce8509b03da3c96a7a7efa528f3d4db52fffb7bff580ffec078003f294`，独立[Phase25审查](reviews/OVERSEAS-PHASE25-REVIEW.md) Stage1/Stage2均PASS。最终快照复跑`output/phase25-http-reviewed.log`：对象12/937字节、数据库27表及序列/360行/99683字节均恢复一致，源不变，本次所有临时容器与网络已清理。固定脚本、依赖和数据随机ID不同会使备份字节数略有差异，验收按行/序列和对象哈希对账。

## 可复跑入口

从仓库根目录运行（PowerShell；镜像已按本项目Dockerfile构建）：

```powershell
$env:IDENTITY_TEST_IMAGE='hengxin-smart-image-backend:phase25'
python hengxin-smart-image/infra/identity-test/run.py --phase25
python hengxin-smart-image/infra/overseas/regression.py
$env:OVERSEAS_VERIFY_IMAGE='hengxin-smart-image-backend:phase25'
python hengxin-smart-image/infra/overseas/verify_resources.py
```

真实浏览器使用同一入口加`--serve --origin http://127.0.0.1:3016`，按输出的三个随机LOCAL PORTS设置Vite的`VITE_API_PROXY_URL`、`VITE_OVERSEAS_PROXY_URL`、`VITE_IDENTITY_PROXY_URL`，再启动3016。前端目录设置`IDENTITY_UI_URL=http://127.0.0.1:3016`及`PLAYWRIGHT_MODULE`为本机已安装Playwright模块路径，执行`node tests/overseas-fullstack-real.browser.mjs`串行运行七组真实API浏览器。结束仅停止日志对应的`hx-p25-<随机>-runner`，总入口随即执行数据库恢复并清理自己创建的容器/网络；不批量停止其它进程。

前端目录执行`pnpm test`、`pnpm build`（包含vue-tsc类型检查）。故障注入测试仍使用既有`overseas-*.browser.mjs`及`overseas-management-faults.browser.mjs`，区别于真实API测试。所有CLI为本地离线fixture，无收费执行。

## 验证边界

CLI测试使用明确的离线可执行文件，真实走进程、stdin、输出事件、文件验证和数据库发布；不等于真实收费模型或图片质量通过。真实钉钉企业回调、生产账号额度、Linux目标主机沙箱和资源预算、真实任务容量/延迟、灾备RPO/RTO及生产部署仍未验证。生产应用凭据隔离已在本地固定镜像拓扑证明，生产真实账号与目录仍需按部署清单核查。

用户原有预览和独立改动保留；未自动推送或部署。正式资料、图片版本和归档不自动清理。部署准备见[清单](OVERSEAS-RELEASE-CHECKLIST.md)。
