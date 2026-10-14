# 原生工作台对话发布 · 0.2.32

用户明确授权：按已确认方案实施，测试后提交Git并部署生产。正式交付图片之外的临时图、草稿、试验图、中间文件不得在前端显示；完整公开文字和执行播报必须保留。

## 实施与验收顺序
1. 需求文档先同步：首轮一句协作人设，普通输入原样传递，仅主动选择时提供附件/Skill文件引用；不改Skill包。
2. 后端：海外0015迁移保留旧会话/回复，保存完整公开事件与增量游标，增加开始新对话；失败/取消保留已收到文字。
3. 图片：只验证最终回复明确交付的图片引用，不扫描目录发现图片；逐图失败独立，正文Markdown同样受图片门禁；沿用预览、引用修改和SKU归档。
4. 前端：真实事件近实时显示，终态可折叠，刷新重连补齐且去重；保留历史滚动，隐藏/卸载停止读取；新对话保留历史资料与归档。
5. 隔离测试、类型/构建、浏览器与独立两阶段审查后提交，打包隐私检查，生产实际安装镜像测试；关海外接纳并排空、备份、迁移0015、替换海外服务和共享前端，真实入口验收。

## 生产边界与恢复
- 基线0.2.31，国内0028、海外overseas_0014；目标0.2.32、海外overseas_0015，国内和身份服务不重启。
- 14份安装Skill及181文件保持原不可变版本。无生产收费模型调用、无测试业务数据写入。
- 使用native-studio-deploy.py，不复用无迁移热修切换。迁移前关接纳、双轮DB/broker排空和完整备份；实际安装测试过的同一镜像用于迁移及服务。
- 失败保持海外入口关闭，保存PHASE/FAILURE/schema证据。0015保留历史且只前进；不自动降库、不盲目恢复旧数据库、不重放未知结果的切换命令。

## 验证记录
- 正式交付图片专项：21 passed。覆盖未引用临时文件、代码/裸路径、草稿段落、会话归属、历史文件、坏图混合、Unicode路径和预览下载去重。
- 生产只读预检：0.2.31/0028/overseas_0014，在途任务0、删除0，国内原生进程2825545；未执行切换。
- 发布相关重点回归：73 passed、26 subtests passed，见output/native-studio-release-tests.log。
- 发布目录全回归：242 passed、1 skipped、117 subtests passed，另1个历史断言失败：test_release_native.py:100要求annotation旧overlay排末尾，而HEAD的image-inputs-frontend.py已以materials overlay结尾；本次两文件均未修改，不影响新发布路径。

本记录为进行中证据，部署结果待最终验证后补充。
- 最新生产只读浏览器检查：旧测试任务5917eff2-07a3-4f10-ab17-4011fcd3a936已不可访问，全部任务加载完成为0条。本次不创建生产测试业务；上线后可验证正式入口与空列表/图需/Skill等页面，有数据工作台及新对话功能由隔离浏览器和同版安装测试覆盖，不能宣称已在现有生产会话现场完成操作验证。
- 后端专项与真实隔离PostgreSQL：66 passed、0 skipped（48.13s），见output/native-studio-backend-pg-20261014.log。覆盖完整长文/半行UTF8、取消失败、图片失败、旧数据迁移与重复迁移、禁止降级、并发新会话/发送竞争和权限。
- 前端全量：356 passed、0 failed，pnpm typecheck exit0，见output/native-studio-frontend-tests.log和native-studio-frontend-typecheck.log。
- 依赖审计：critical0；high70/moderate48/low5为与0.2.31一致的既有告警，见output/native-studio-dependency-audit.json。
- Linux只读整仓、无网络完整后端回归：2038 passed、188 skipped、15 warnings（281.45s），见output/native-studio-backend-full.log。专用环境跳过项不计已验证，实际PG迁移已单独执行。
- 滚动时序修复后前端全量再次356 passed、0 failed；最终类型检查exit0，见output/native-studio-frontend-final-typecheck.log。
- 新增原生工作台隔离浏览器连续两次PASS，既有刷新/Skill浏览器PASS；覆盖真实可达的failed无图保文、succeeded混合交付、断线幂等新会话、正文/执行消息临时图不加载、长文与390px。见output/native-studio-browser.log、native-studio-refresh-browser.log；截图output/playwright/studio-native/已目视核对。
- 正式pnpm build exit0，Vite构建37.70s，见output/native-studio-build.log；最终生成文件无额外噪音。
- R1独立审查发现跨段落草稿/中间文件门禁HIGH，已修复为完整段落范围与父级标题保留、后置非交付说明也拒收。新增9个collector边界与3个真实runner/API用例，44项专项通过；文字仍完整保留，非交付图片不进入DTO。R1 FAIL未批准，等待R2新快照复审。
- R2修复后Linux完整后端回归2047 passed、188 skipped、15 warnings（250.78s），见output/native-studio-backend-full-r2.log；该次收集后新增的3条真实runner/API回归另在44项专项中全部通过。前端及迁移/发布代码自前一轮通过后未变化。
- R2独立审查发现文件名final.png可误解除草稿范围，R2 FAIL未批准。R3将正式范围声明限定为链接/图片/代码之外的可见说明文字，并收紧英文声明；新增8个元数据/代码/裸路径对照及1个真实runner/API用例，最终53项专项通过（6.42s）。最终快照4d7e993e0339f10016bc82230f1ffc75a9598344e7644d0f44bf25d311c6ed87已冻结，R3整库回归和独立两阶段审查进行中。
- R3全量后端2059 passed、188 skipped、15 warnings（266.92s），但独立审查又发现“并非最终交付/不是正式交付/not final images”可误收，因此R3 FAIL未批准。R4新增中英文否定交付规则并优先于肯定关键词；补42个前置/后置/标题作用域反例、1个独立正式交付对照和3个真实runner→API反例，102项专项通过（9.12s），文字均完整保留。新快照9bbf15b0ee82e2efc25e1dcde5935d2f9c371c7d95d0323e94a57fcbc44a62db已送fresh reviewer，完整后端再验进行中。
- R4整库2105 passed、188 skipped、15 warnings（246.19s），独立审查发现加粗分割英文否定词漏判，R4 FAIL未批准。R5统一使用Markdown解析后的可见文字识别否定，保留原始完整回复；增加强调/链接文字/行内代码/软换行的33个反例、1个肯定对照和2个runner→API反例，138项专项通过（9.34s）。ATX标题遇换行结束，因此标题测试将notice换行规范为空格，软换行仍由前置/后置段落测试覆盖，没有跳过或降低图片拒收断言。快照3fde16d6f7ec638ec7138489542d566e2e09b11133104915ad79b48db80fbf12已送fresh reviewer并开始最终整库回归。
- R5整库2141 passed、188 skipped、15 warnings（242.46s），独立审查发现图片alt嵌套token未递归，R5 FAIL未批准。R6递归取可见文字并纳入图片/链接title的否定说明，新增12个alt/嵌套alt/下载包裹/title反例与2个runner→API反例，最终152项专项通过（10.31s），快照fbd870cfae4572f463a05a867c529fe732dd55ab48521a61ee79706867f3e859已送fresh reviewer。此次仅collector和测试变化；完整安装镜像回归在审查提交后、生产切换前执行，不将前一快照整库结果冒称当前全量。
- R6完成大部分Stage 2验证后独立实体反例发现text_special未参与alt递归，R6 FAIL未批准。R7补齐该文本叶节点，否定识别兼容实体、字面转义装饰、全角及不可见格式字符；原始正文不变。新增10个collector对照及1个runner→API反例，163项专项通过（9.58s）。新快照28ed2e274df4bc384e74f57b404a2646c038c7f64ccc50254ced1bcc5c8ebd86已送fresh reviewer。
- R7整库2166 passed、188 skipped、15 warnings（250.38s）；独立75组合矩阵发现11类中英文试验/工作稿/初稿/未完成说明在5位置误收，另嵌套title漏检，R7 FAIL未批准。R8递归全部描述节点和title，补齐已实查说明类别；279项专项通过（10.88s），含“Tests passed / 测试通过”仍正式交付的正向对照。新快照76f87f7587485713c68a1cece35d6785f4e56747af52d824ea8a8b9f96d19a4d已送fresh reviewer。最终完整安装镜像测试仍为生产切换前门禁。
- R8后端已通过独立279专项及75矩阵，但正式dist复现全轮sourcePath映射会使旧过程消息和最终回复中被拒收的草稿段落渲染正式对象字节，违反过程路径只作文字，R8 FAIL未批准。R9先同步Spec/Plan，然后移除Markdown图片映射：正文图片引用和本地路径保持完整文字，正式图片仅由现有卡片显示和操作。最终前端357项通过，pnpm build含类型检查exit0（36.01s），正式dist浏览器通过复用路径0正文图/1正式卡片、全文/播报/新会话/滚动/390px回归。快照91e4e338da03ba37009b74a37450ebbcee4f4a07b901a490b24035b00bb9c7dc已送fresh reviewer；R8报告整理期间开始修复已明确告知reviewer，未把旧快照结论用于新代码。
- R9独立两阶段审查均PASS，见docs/reviews/NATIVE-STUDIO-R9-20261014.md，快照仍一致。reviewer独立后端279+6项、前端357项、发布73项+26子测试、类型检查、新旧浏览器及实际邻居视觉全部通过；无剩余HIGH/MEDIUM阻断。既有发布目录历史断言失败和依赖告警仍如实保留。开始登记凭据、提交和最终安装镜像验证。

## 发布核验修正与前进恢复
安装镜像2174项通过后，0015迁移成功；verify-installed阶段将不存在的studio/sessions作为鉴权探针，返回非401/403而触发失败关闭。计划只修正发布探针为真实任务工作台及transcript端点，新增仅支持此已迁移、未发布前端阶段的前进恢复：校验备份/镜像/源文件/0015/入口关闭及空队列，启动同一已测镜像，重做全部安装核验并发布前端。不得重新迁移、恢复旧库或跳过检查；应用代码和镜像不变。修正需专项测试及独立两阶段审查后执行。
