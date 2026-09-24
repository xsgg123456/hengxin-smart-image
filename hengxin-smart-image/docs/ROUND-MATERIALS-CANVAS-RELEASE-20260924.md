# 执行材料与画布优化生产发布 · 2026-09-24

用户已明确授权提交Git、打包并部署既有生产站点 https://zhitu.qhhengxin.top/ 。发布目标为前端0.2.6、CLI逐轮执行材料采集和展示、API/CLI公共标注画布优化；无数据库迁移，保持0017。

## 计划与验收

1. 保留功能批准快照，完成版本和部署脚本增量、独立审查后提交；生产构建和白名单产物隐私审计通过。两个原有PERFORMANCE文档不属于本次提交。
2. 按实际完整Compose overlay链匹配生产配置。构建新后端镜像，以无网络、无生产凭据与数据挂载的安装镜像运行材料/标注/排空专项，固定镜像ID。
3. 再次检查在途任务，关闭接纳与派发、排空API/CLI后才切换。备份数据库、前端、manifest、原生CLI本次覆盖和新增文件清单。更新API、两个outbox、API专用worker、原生CLI材料采集代码及前端，不改模型/Skill/凭据/并发/7200秒时限。
4. 安装哈希、0017、服务健康、队列和心跳、公开页面正常后开放。以原生worker身份先只读检查、再回填用户指定历史轮次，验证数据库和鉴权材料展示；不新建收费任务。
5. 核实最终生产状态与产物一致，补写发布结果。回退保留数据库及业务数据，恢复旧镜像、前端、native文件和manifest；本次新增native文件在回退时删除。排空或恢复不明时保持关闭，不强停生图或错误开放。

## 生产预检

发布前只读实查：当前annotation-20260924-6b43b3c、前端0.2.5；schema0017，CLI 37成功/12失败/2取消，API 10成功，无在途任务；通道未暂停，原生CLI active，health/ready全部正常。切换前仍需重新检查。

## 首次发布与真实会话兼容修正

提交e3c60c9、发布materials-20260924-e3c60c9于北京时间18:18:50切换成功，0.2.6、647文件包、151项安装镜像测试通过，完整安装哈希/队列/健康/公开登录页及匿名鉴权通过。CLI51笔、API10笔任务状态保持，未新增付费任务。备份位于同发布编号的 /opt/hengxin-backups 目录。

安装测试首次挂载到/release-tests时有1项迁移路径失败（150通过），随后保持镜像不变、挂载到/app/tests后151项全部通过；测试包装换行也已修正。不是业务用例被跳过。

真实历史回填只读检查发现系统提示词1、生图调用0，尚未写入。实查会话工具事件为custom_tool_call/input，调用后还有store及Object.fromEntries字段过滤展示尾部。采集器仅识别function_call/arguments和简单展示尾部，故保守遗漏。按bug-fixer闭环补足明确事件字段与这一受限语法形态，不放宽任意脚本执行判断；对应增加真实形态与字段错配回归，修正版0.2.7另行送审、安装测试和部署。旧发布保持运行，修正版需叠加当前e3c60c9 overlay。

## 最终发布与历史回填

2026-09-24 18:40:07（北京时间）修正版切换成功，发布 `materials-20260924-2cdb4ff`，代码提交 `2cdb4ff`，前端0.2.7。此前功能提交为e3c60c9。最终两阶段审查见根docs/ROUND-MATERIALS-REAL-LOG-REVIEW-20260924.md；本地106专项及服务器实际安装镜像196专项全部通过，6条既有警告，无跳过；正式构建成功。

发布包647文件、4,848,350字节，SHA256 `19fabbc502ff34f3d2010ce7580d3950a2e8a5bcaf071928af167d9e36c678eb`。镜像ID `sha256:71f7371958c2098e6acbe8568bd6ac2995b9196aab13422a4aa6233ba2b55a76`。前端478文件（含package.json）、四个后端服务各159文件、原生CLI七文件逐文件哈希全部匹配。包位于本地output/materials-20260924-2cdb4ff/release.tar.gz，服务器同编号发布目录；完整备份位于/opt/hengxin-backups/materials-20260924-2cdb4ff。

API healthy、原生CLI active、API Worker池5及专用队列、CLI队列和心跳全部通过；schema0017、并发5、CLI0.156.1、超时7200秒保持。API通道开放，CLI37成功/12失败/2取消、API10成功，无新增付费生成。切换前均排空，没有强停在途生成。

已以原生worker的codex身份先只读确认，再对指定轮次cd103910-f824-4ac6-91f7-64b9fbe6b767回填：成功1、失败0。安装API实际业务查询确认完整系统提示词510字符、生图提示词2160字符，图片引用顺序为/work/current/00.png、/work/inputs/00.png、/work/original/00.jpg；输入基础V1、原始底图4、素材1全部可读且已核实；输出为该轮V2。唯一提示为该轮未提交标注图，符合真实请求。没有重放或重新生成图片。

公网首页哈希匹配，无脚本错误或JS/CSS失败；health/ready 200，匿名auth/me、API任务及新增材料接口均401。线上登录后交互未绕过身份认证测试；画布交互依据同源正式构建的16组矩阵和独立光标测试，历史材料依据安装API实际业务查询验证。

本地证据：output/materials-release-20260924/ 下build-and-tests.log、deploy.log、verification.log、backfill-write.log、materials-verification.log、production-browser.json及生产登录页截图。生产依赖审计critical0/high33/moderate30/low1，均为基线已有，本轮未升级依赖。

后续维护的Compose链须在原三份基础配置后依次叠加three-fixes-20260923、cli-two-hour-20260923、inputs-20260923-b2841c7、annotation-20260924-6b43b3c、materials-20260924-e3c60c9、materials-20260924-2cdb4ff各发布目录下api-override.yaml。旧镜像和备份保留，不恢复数据库dump覆盖业务数据。
