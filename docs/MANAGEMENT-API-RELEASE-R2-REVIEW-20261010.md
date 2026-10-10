# 管理中心 API 统计发布增量 R2 独立审查

日期：2026-10-10。candidateId：`b31d45e364ac443088cf9b16afdcd208329bfef1459621fd5b36e4aab71224b2`。

结论：**Stage 1 PASS；Stage 2 PASS。首轮 HIGH R1 已关闭，无阻断问题。** 这是发布工具的代码审查通过，不是生产发布验收通过。

范围：`scripts/release/{package-management,management-runtime,management-deploy,management-verify}.py` 及对应四个测试文件、`hengxin-smart-image/frontend/package.json:3`；合同为 `docs/MANAGEMENT-API-RELEASE-20261010.md:3`。产品基线读取 `Product-Spec.md:920`、`:933`，功能提交 bccf95e 沿用既有独立审查，本轮没有重新认证其全部业务功能。预存 `.agents/skills/dev-builder/SKILL.md` 改动不在范围内。未修改代码、未访问或写入生产、未提交、未登记审批。

## Stage 1：需求符合性

| 合同条目 | 结论与证据 |
|---|---|
| 发布已审、已提交代码，前端 0.2.20 | 完整实现。`package-management.py:74`、`:81` 要求受控变更提交、批准快照匹配，读取 HEAD 字节并复核本地文件；`:110` 固定版本/迁移清单；前端 `package.json:3` 唯一变更是版本号。 |
| 白名单、包哈希、隐私扫描 | 完整实现。`package-management.py:15`、`:26` 限定源码、测试、三个提示词和发布脚本；`:55` 拒绝敏感文件名、未知资源类型，递归扫描 gzip 内容；`:86` 拒绝链接；`:37` 归档后回读逐字节匹配；`:124` 输出归档 SHA256。`test_package_management.py:14`、`:38`、`:59` 覆盖 gzip 秘钥、二进制负例、路径越界、必需文件缺失。实际待打包产物仍须取得扫描证据。 |
| 正式构建及依赖审计 | 构建证据已读取，末行见下。依赖没有修改；主 Agent 提供 critical 0/high 36/moderate 34/low 1 既有基线，未独立重跑审计，不声称零漏洞。 |
| 最终后端镜像断网安装测试 | 完整实现调用机制。`management-deploy.py:57` 使用最终镜像、`--network none`、测试环境；`:63` 保存实测 image ID，`:66` 部署前校验同一 ID。`:13`、`:19` 仅排除六个依赖仓库 infra 的工具模块及一个依赖前端源码的接口字段测试，保留业务测试。`test_management_deploy.py:20` 检查该范围。实际镜像测试日志待构建时取得，断网 PG 用例可能跳过，不能将其认作真实 PG 验证。 |
| 排空后关闭接纳/派发，未知在途不强停 | 完整实现。`management-deploy.py:29` 覆盖旧任务、API 任务/图片、queued/running/cancelling CLI 轮次；`:67` 首次核查，`:73` 停 web/API/outbox、暂停通道并 drain；`:79` 停原生执行器前后二次核查；`:122` 未确认排空时保持关闭、不重启执行器。`test_management_deploy.py:154`、`:201` 故障路径通过。candidate/waiting_user 不是在途执行，不误计为 busy。 |
| 数据库、原生代码、前端入口与配置备份 | 完整实现。`management-runtime.py:85` 创建私有备份目录，pg_dump 后用 pg_restore --list 验证，备份 native、入口、版本标记、nginx、全部 compose；`:105` 最后写 COMPLETE。`management-deploy.py:84` 备份先于迁移；测试 `test_management_deploy.py:180` 验证备份失败不迁移。 |
| 0024/0025/0026 迁移、幂等回填 | 完整实现调用链。`package-management.py:133` 要求三项迁移，`management-deploy.py:86` 执行 migrate、确认 0026、调用既有 backfill。`test_management_deploy.py:162`、`:227` 验证回填失败保留兼容 schema 与迁移/回填/安装顺序。回填业务语义沿用 bccf95e 审查。 |
| 更新五服务/native/前端，保留业务配置与并发 | 完整实现。`management-runtime.py:57` 读取实际全部 compose 路径，仅覆盖 image/build；`:48` 要求原生并发 5、超时 7200、清理关闭；`:108` 安装 Python 和三份必需提示词、保留属主并设置权限；`:124` 发布前端和活动标记。`management-verify.py:106` 逐服务验证实际 image ID、环境、命令和文件；`:116` 校验 native/前端/nginx 哈希。`test_management_runtime.py:17`、`:28`、`:65`、`:93` 验证配置漂移拒绝、覆盖层保留、资源与标记。 |
| 清理保留关闭 | 完整实现。`management-runtime.py:52`、`:68` 拒绝启用清理的配置；`management-verify.py:35` 检查实际 retention disabled 及 1/7 天参数；deploy 不启动 retention 调度服务。 |
| 安装校验、心跳、真实统计后开放 | 完整实现，R1 前半段已修。`management-deploy.py:103` 在发布文件后、开放前调用 installed-only；`management-verify.py:93` 至 `:143` 执行标记、镜像、代码/资源哈希、schema、真实契约、进程和本地 readiness 校验；`:139` 要求 paused=true，`:144` 提前返回且不请求公网。`:25` 使用只读事务、真实非 development 管理员读取实际配置/两通道 heartbeat/统计。`test_management_verify.py:153`、`:160`、`:164` 证明模式与本地损坏拒绝；`test_management_deploy.py:213` 证明失败不开放新 web。 |
| 公网页面/资源/鉴权验证与失败关闭 | 完整实现，R1 后半段已修。`management-deploy.py:105` 先设置 opening 再解除暂停，`:110` 在同一 try 中运行 full verify，成功后才输出完成；`management-verify.py:150`、`:155` 比对公网入口/JS/CSS SHA256，`:159` 要求匿名 auth/me=401。`management-deploy.py:114` 开放后失败停接纳/派发、重新暂停并保留新执行器。`test_management_deploy.py:218` 通过真实 verifier 主函数配合模拟 IO 注入公网哈希/鉴权错误，证明失败进入此分支。 |
| 图片/任务/统计业务基线 | 核查入口完整，生产比对待执行。`management-verify.py:43` 输出 facts、eventCount、inventory；`:141` 输出旧任务/API 图片状态计数。工具没有自动断言发布前后业务总量相等；合同的基线核对仍需主 Agent 使用切换前只读快照与部署后结果人工比较。本报告不声称此生产验收已完成。 |
| 不收费冒烟 | 完整实现。`management-verify.py:25` 只读事务，`:150` 起仅静态资源、健康与匿名鉴权请求；无付费生成调用。 |
| 回退不覆盖数据库、开放后不切旧执行器 | 完整实现。`management-deploy.py:131` 起仅恢复代码/配置/前端及服务，未调用数据库恢复；`:114` 开放后保持新执行器。`management-runtime.py:90` 的 pg_restore 仅 --list。`test_management_deploy.py:162`、`:188`、`:194`、`:207`、`:218` 验证保留 schema、回退失败关闭和开放后保留新代码。 |
| UI、引导真实性、Spec 漂移 | 本增量无页面/组件/文案变化，UI 与邻居页面视觉对比不适用；前端 diff 仅 `package.json:3`。发布脚本符合合同，未新增产品 API/表/页面。不能以本报告替代功能基线的 UI 验收。 |

没有部分实现或未实现的阻断性工具需求。生产包上传哈希、安装、迁移、备份、真实配置/数据与公网验收是后续执行事项。

## Stage 2：代码质量与安全

- 通过：四个工具按打包/运行支持/部署状态机/验收划分职责，文件分别 147/144/175/165 行；四测试分别 71/117/253/175 行，均低于 300 行。`management-deploy.py:70` 的状态标志与 `:112` 错误分支覆盖安装前、排空未知、开放前、开放后恢复。Python 动态字典沿用工具风格，无 TypeScript any 变更。
- 通过：扫描四工具未发现 eval、shell=True、innerHTML、VITE 密钥、个人用户路径或硬编码 secret。`management-runtime.py:20` 使用参数数组执行命令；`management-deploy.py:36` 与 `management-verify.py:85` 限定 release ID；`:135` 的 SQL 列名来自固定四项常量，未接受用户拼接输入。`management-deploy.py:34` umask 077、`management-runtime.py:86` 目录 0700 保护服务器配置/备份；真实身份/凭据未输出。
- 通过：测试确实走部署主函数与恢复路径。`test_management_deploy.py:79` 调用 verifier 测试夹具中的真实 main；`:218` 注入不同公网错误并断言新代码保留、paused=true、无旧 compose 重启；`:227` 明确断言两次校验相对发布/解除暂停的顺序，原先“仅测试顺畅路径”的缺口已消除。
- 测试边界：`test_management_verify.py:99` 模拟容器内哈希命令，`:134` 模拟真实契约返回，因此单测不是五个真实容器/真实 PG 统计契约验收；生产 full/installed-only 都仍执行真正的容器哈希及 CONTRACT_CHECK（`management-verify.py:105`、`:130`）。本次未以模拟证据冒充生产成功。
- LOW 文档证据滞后：`docs/MANAGEMENT-API-RELEASE-20261010.md:23` 仍写 31 项专项测试，本轮独立执行为 37 项；建议主 Agent 更新发布记录，代码不受影响。

## 独立测试与编译原始输出

命令：`python -m unittest discover -s scripts/release -p 'test_management*.py' -v`

```text
----------------------------------------------------------------------
Ran 31 tests in 0.963s

OK
```

命令：`python -m unittest discover -s scripts/release -p 'test_package_management.py' -v`

```text
----------------------------------------------------------------------
Ran 6 tests in 0.007s

OK
```

八个文件独立调用 Python 内置 compile（不执行服务器入口），原始输出：

```text
management-deploy.py 175 lines
management-runtime.py 144 lines
management-verify.py 165 lines
package-management.py 147 lines
test_management_deploy.py 253 lines
test_management_runtime.py 117 lines
test_management_verify.py 175 lines
test_package_management.py 71 lines
Python syntax compilation: 8 files PASS
```

主 Agent 正式前端构建日志 `output/release/management-prep/build.log`，独立读取的末行（未重复构建）：

```text
✓ built in 43.92s
```

审查前后使用 review-status 核对 candidate，受控范围始终为版本文件与八个 Python 文件，未发现审查中代码变化。报告为 Markdown，不改变候选快照。由主 Agent 使用同一 candidateId 登记两个阶段 PASS；不得写 clean，后续代码变更必须另行固定快照复核。
