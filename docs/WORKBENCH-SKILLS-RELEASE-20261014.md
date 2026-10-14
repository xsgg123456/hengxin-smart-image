# 工作台与Skill统一合并发布 · 0.2.31

用户已授权修复自动刷新和Skill名称/描述、管理与工作台同步，测试后连同上传放宽及北京时间修复一起上线。

## 有序交付与验收
1. 需求同步：Product-Spec、DEV-PLAN、变更日志先同步，沿用既有UI布局。
2. 实现：后端读取完整性校验后的SKILL标题，前端静默自适应更新与完整描述展示。保持Skill安装包/标识/历史冻结不变。
3. 验证：前后端全回归、构建、浏览器正常/错误/空闲/执行与可见性、独立两阶段审查。
4. 发布：0.2.31；既有overseas-hotfix-deploy无迁移流程，基线0.2.30，国内0028/海外0014；生产安装镜像测试、备份、关海外接纳、双轮排空、替换海外API/原生执行代码及共享前端，再健康/权限/静态资源/页面验收。
5. 已授权提交已审源码，使用中文提交信息；不推送、不改Skill包、不触发收费模型。

## 恢复原则
沿用发布编排：失败关闭海外入口，保留PHASE、FAILURE和备份，实查后恢复旧应用；绝不以旧数据库覆盖新业务数据。不重启国内和身份服务。

## 合并回归证据
- 前端347 passed/0 failed，typecheck exit0；output/studio-frontend-tests.log、studio-frontend-typecheck.log。
- 生产构建exit0，38.33s；output/workbench-release-build.log。
- Linux只读仓库、无网络全回归：2007 passed、185 skipped、15 warnings，263.39s；output/workbench-release-backend-full.log。环境跳过不计已验证。
- 浏览器隔离接口测试PASS：草稿/附件/Skill/滚动保持，手动与静默刷新、错误恢复、完成停止，390px长描述全文滚动及说明弹窗；output/studio-refresh-browser.log、output/playwright/studio/。可见性/卸载/竞争及权限由真实hook定时器测试覆盖。
- 发布脚本13项、打包25项通过。依赖审计critical=0；既有high70/moderate48/low5，本次未修改依赖。
- 生产只读预检：0.2.30、国内0028/海外0014、在途0、删除0、worker空闲。真实Skill14包181文件，保持不可变安装版本。

## 生产发布结果
- 发布0.2.31成功，2026-10-14北京时间约10:10恢复入口；源码53cf1de，包overseas-20261014-53cf1de。
- 独立两阶段审查PASS，candidate ad0843abf633a7710f2bb13f7c16da45b3fd0595bb9448cf998964c70417db99；见docs/reviews/WORKBENCH-SKILLS-RELEASE-20261014.md。
- 包1454文件/8636575字节，隐私PASS，SHA256 79156dacdc7febe38234fbfa85d2e3bb9f85601b0c8ba382a02f4b26081dfb9b；镜像564个后端源文件哈希一致。
- 生产实际镜像安装回归1899 passed、184 skipped、1 deselected、15 warnings，419.48s；排除外部宿主专用测试与不随包部署的前端源码合同用例，未宣称跳过项通过。
- prepare/deploy均exit0，PHASE complete；备份/opt/hengxin-backups/overseas-20261014-53cf1de。海外两轮排空后切换，国内/身份容器及国内原生进程保持不变，schema不变。
- 生产只读验证14个Skill名称与description逐项匹配实际校验后的SKILL文件，原安装release未修改。
- 正式已登录浏览器验证管理页与工作台实际名称、下拉完整描述和说明弹窗；截图output/workbench-production-management.png、workbench-production-skill.png。
- 正式任务列表中原样例已显示2026-10-14 08:59:59；截图output/workbench-production-time.png。图需提交页两input accept均空，文案不限格式含PPT/PPTX、解析失败不阻止提交；截图output/workbench-production-upload.png。
- 生产页面验收采用现有任务只读导航及本地Skill选择，未新建生产任务/上传测试资料/调用收费模型。上传实际提交与刷新故障/隐藏/并发由发布前隔离浏览器及后端测试覆盖；不把生产只读验收当成收费生成端到端验证。
- 首次SSH构建连接超时、重试成功；切换开放后的首次探测503，经发布器重试恢复并通过正式入口检查，无回退或数据库恢复。
