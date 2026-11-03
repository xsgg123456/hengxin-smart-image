# 海外 Skill 文件夹管理验证

实施合同：SKILL-FOLDERS-IMPLEMENTATION-20261103.md。目标版本0.2.63；此文件记录验证，生产发布状态另记。

## 自动化及真实运行

- 前端 `corepack pnpm test`：514/514通过，日志 `output/skill-folders-frontend-all-final.log`。
- 前端 `corepack pnpm build`（含vue-tsc）：通过，34.36秒；`output/skill-folders-frontend-build.log`。
- Windows后端上传/故障/标题回归：40通过；`output/skill-folders-backend-final.log`。
- Linux最终镜像 `hengxin-skill-folders-test:9f179268423d729c`：51通过，无跳过；上传/故障/installed/catalog/title/freeze，`output/skill-folders-release/linux-final.log`。
- root发布服务与独立UID10001只读API实测：socket 0:10001/0660，API可连接且不能写catalog，UID65534被拒；`output/skill-folders-release/linux-permissions-final.log`。
- 最新reader以UID10001、无网络、只读挂载读取现有生产17包成功；`output/skill-folders-release/real-catalog-readonly.log`。
- 发布范围及恢复委托边界9项通过：API固定10模块，native仅installed_catalog/installed_tree两个reader，不迁移数据库。生产基线真实重采、既有字段与源码无漂移。
- 依赖审计critical=0；历史high=73、moderate=54、low=11，并未宣称全部清零。新增固定yaml2.9.1，余依赖版本保持。

## 真实浏览器

`tests/skill-folders.browser.mjs` 使用最终构建，隔离真实API、Unix socket publisher和临时数据库。原生目录拖拽读取108文件、3目录，含105个同级文本、中文文件名、二进制、空目录；服务端清单和原目录完全一致。

六项全部通过且无pageerror：完整拖入；完整目录写入及逐文件读回SHA256核验；同名目标拒绝覆盖；同内容幂等与删除取消；不同内容显式更新和旧版本保持；删除最后一项后的空目录及旧冻结文件读取。

结果 `output/playwright/skill-folders/result.json`，扫描/保存/删除/差异/窄屏/空目录六张截图在同目录。保存使用Chrome真实OPFS目录句柄，仅系统选择器由测试替换；不把此项称为已验证Windows原生选择窗口。浏览器后端镜像358116fe29283ef2；后续CommonMark reader修复由最终Linux51项及生产17包只读回归覆盖。

## 审查整改及边界

前两轮Stage1拒绝已记录，不作为批准：正则元数据误拒改为真实YAML/CommonMark解析；首次及重试写入增加会话归属/句柄/哈希保护；所有明确新包引用校验；历史reader跳过代码示例且接受真实空目录链接。

完整性指目录与文件字节一致，不保证外部依赖可运行、文件ACL或创建时间。浏览器目录API没有原子exclusive-create/CAS，已在创建、下载等待、writer创建及重试前检查冲突；不能绝对消除用户外部进程在最终检查与提交间的极短并发修改。

生产部署不对真实Skill做删除/更新测试，不发起付费生图。

