# 海外管理与搜索实施计划

1. 核对生产与代码权限、成员/作业数量；标准为真实证据区分无数据与个人过滤。
2. 管理统计及监控默认全员提示、操作者筛选；标准为管理员可见其他用户作业，普通角色不可越权，汇总与列表同范围。
3. 删除海外Token/费用接口与展示、专用存储与写入；标准为迁移存量成功且国内和原始CLI日志不变。
4. 成品统一搜索；标准为三个业务字段均可检索、重置与分页及窄屏正确。
5. 更新发布迁移步骤，回归、正式构建、浏览器和独立快照审查；提交后重新打包，在备份排空后部署验证。

既有DEV-PLAN的海外管理和发布验收受影响；本次按以上专项计划执行，既有工作台修复保留。目标版本仍为尚未发布的0.2.35。

## 只读核查

- 2026-10-15生产海外数据库只读事务：成员2（超级管理员1、设计主管1）、任务1、作业1（studio/failed）。页面一条作业符合全库数量，不是个人过滤。
- permissions.scopes 对管理员/主管 stats.read 已返回 all；facts.scoped 在分页/汇总之前一致使用该范围。此次保留权限，改善范围提示及操作者筛选并多用户回归。
- 当前工作台真实操作者来源 Turn.actor_id；旧分析/生成作业没有可靠操作者，不拿任务创建人或指派设计师冒充，显示未记录且默认全员仍可见。
- 成品后端 search 已按品名、品牌、SKU 做 OR 匹配，前端移除重复字段即可。
- Job.usage 仅用于海外统计及写入，计划海外0016迁移移除；国内0028不变。首次两项修复的6022d1a旧包未部署，最终重新打包。

## 验证记录

- 后端Linux定向57项通过；真实PG历史数据迁移通过，完整后端回归进行中。
- 前端单测364项通过，正式构建与浏览器在最终搜索加载态修复后重新验证。
- 发布专项112项及48子测试通过；全发布Windows测试395通过/1跳过/1失败（旧test_release_native期待annotation为最后overlay，但既有代码为materials）。Linux394通过/1跳过/2失败：同一旧断言及测试镜像缺git导致旧package_delivery测试失败。本次发布专项未失败，未更改无关断言。
- 排障通用规则由用户明确采纳，已补入bug-fixer技能：先枚举实际支持输入与分支，再定修复和回归范围。

- 最终全量Linux后端2348 passed、188 skipped、15 warnings（290.31秒），日志output/admin-backend-linux.log；真实PG迁移专项15 passed（43.58秒），见output/admin-backend-pg.log。
- 最终前端364 passed、0 failed；正式构建40.34秒通过（含vue-tsc），日志output/frontend-admin-test.log、output/frontend-admin-build.log。
- 正式dist隔离浏览器overseas-admin-simplify.browser.mjs通过：主管无members.manage仍可按真实操作者筛选，两接口同步、清空恢复全员与分页重置、普通范围、选项失败重试、三字段搜索、重置分页、空态错误及390px裁切。截图在output/playwright/admin-simplify，主Agent已目视。
- 第一轮审查提出发布脚本长度问题，已把资源一致性检查完整移至已有resources模块，主脚本299行；最后发布专项91 passed、48 subtests，见output/admin-release-final.log。新快照b180b482bd6cc678b70fd25dc98af277dfcc9c5d93ecee30896e60d42def5d94待独立复审。

- 独立R2两阶段PASS，报告docs/reviews/OVERSEAS-ADMIN-20261015-R2.md；同一快照已登记批准。reviewer独立发布65 passed/24 subtests，管理/操作者/迁移8 passed；结束时快照一致。生产再检0015、活动作业0、删除0。

## 生产发布完成

- 源码提交adf861b（包含此前6022d1a），发布overseas-20261015-adf861b，前端0.2.35。包1293文件/5598233字节，SHA256 4c4fe8840385418dfe7330071dbcd9213490bdd74b25a126085846bdfb8699b0；隐私及归档校验PASS。
- 首次构建源文件哈希检查拦截db.py和test_overseas_database.py不一致；核对服务器包内586文件与manifest一致后，仅刷新mtime重新构建，未修改字节或绕过检查。最终586文件全部PASS。
- 最终镜像sha256:24aa9f4389b6bf7e5c10a799f765257b09f5562b08326bfd0af62615f4138b25；安装测试2240 passed、187 skipped、1 deselected、15 warnings（435.08秒），上传容量测试4 passed（8.41秒）。
- prepare/deploy均exit0；PHASE=complete；备份/opt/hengxin-backups/overseas-20261015-adf861b/COMPLETE存在；海外0016且usage列数量0；国内0028、国内/identity实例及原生进程不变、技能校验通过；活动作业0。代理重载期间503由既有有界轮询等待恢复，最终验证通过。
- 正式Chrome登录态目视成品库单搜索框、统计全员提示/三业务卡/无Token费用、人员下拉与筛选、监控成功1失败0；生产目前只有1作业，多人员覆盖由隔离真实后端测试验证，未插入生产测试数据。
- 历史误报记录先dry-run eligible，再apply succeeded；事件SHA256及4条公开消息匹配，完成时间2026-10-15 01:08:24.416711 UTC、执行次数1保持；再次dry-run already_recovered。正式任务页面显示Codex已回复、完整原文与无终态错误。未重跑CLI或触发收费生成。
