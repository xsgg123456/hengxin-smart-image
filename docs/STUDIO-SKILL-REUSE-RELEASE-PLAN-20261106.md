# 同会话 Skill 复用：原生服务发布计划

用户已授权开发、中文提交和部署；发布准备子 Agent 只编写工具、自测及只读实查，不执行生产变更。主 Agent 控制审查、提交和生产操作。

## 范围与实查

2026-11-06 通过明确入口 `root@107.172.161.139`、密钥 `C:/Users/82358/.ssh/codex_vps_20260908_ed25519`、BatchMode 和 StrictHostKeyChecking 只读实查：

- worker/outbox 为 active，PID 735950/735948，共用 `/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend`。
- API 镜像 `sha256:30681c68650019ee8b4f5e6c3c30fe810a47f4a7de540273f03cae02eb90c943`，启动时间 `2026-11-05T06:46:34.677895031Z`。
- 边缘 `/opt/1panel/www/conf.d/zhitu.qhhengxin.top.conf` 和内层 `/opt/hengxin-smart-image/infra/nginx.vps.conf` 都有唯一 `location ^~ /api/overseas/v1/`。发布只临时将该段改为503，恢复原字节；保留 bind mount inode。
- 最近部署依据为 `STUDIO-BATCH-DEPLOYED-20261105.md`。本次不套用旧版本/镜像常量，打包前重新捕获基线。

只安装 `app/overseas/execution/{materials,skill_cache,skill_content}.py`。不替换或重启API、不改前端/数据库结构/模型/生产环境/本地Skill内容，不删除任何真实会话文件。新增模块回退时移到原源码根的归档文件，原有模块从备份原子恢复。

## 顺序与验收

1. 本地回归与编译、两阶段独立review、中文提交。完成标准：当前提交匹配已批准快照，工作区干净。Linux真实身份/Bubblewrap隔离回归在步骤4从固定提交安装后完成，未通过不得进入步骤5。
2. `skill-reuse-baseline.py` 从真实环境读取API ID/image/StartedAt、schema、两个unit实际cwd、三个源码基线hash（新增允许absent）、既有context_fs依赖hash。输出只有代码hash与基础设施身份，不输出环境或业务内容。
3. `skill-reuse-package.py` 从固定Git提交只提取白名单源码、递归纯Python测试依赖、明确的发布helper；隐私扫描并记录全部SHA256。正式包必须已批准review。candidate包仅允许prepare/test。
4. `prepare` 验包并固定真实服务/源码/Compose/环境hash、Skill树、前端入口hash、两代理原文和执行根路径；不修改生产服务。`test` 在 `/opt/hengxin-skill-reuse-test-<manifest16>` 复制纯app源码并叠加三个候选模块。使用原生venv解释器，pytest六个纯Python包和py.py兼容模块从原API镜像导出到独立vendor，不写生产venv。`unshare --net`、清空环境、真实服务UID执行全部纯文件测试；root另跑Linux bwrap测试。必须有passed且无failed/skipped/xfail。断言应用模块来自指定安装根、pytest来自vendor、运行UID正确。
5. `gate` 复用host级release.lock，并持久化跨CLI阶段的独占owner。关闭双代理海外入口，统一360秒内验证503并等待reload前全部nginx worker退出，避免已有上传请求晚入队。再在180秒内检查任务/导入/删除排空、pause已识别consumer，复用sku-native禁SIGKILL保护、统一60秒停止两单元。停稳后记录整个执行根所有条目的相对路径/类型/size/mtime/inode/uid/gid/mode，以及Studio/会话表记录数与内容hash；不读取会话文件内容、不hash全30GB。
6. `install` 在已关闭入口且两单元停止时备份旧源码和absent清单。app树外同文件系统暂存、hash核对、保留权限、fsync、原子替换。真实UID从最终安装路径跑完整纯文件套件，root再跑bwrap；严格核对会话元数据/表摘要，再启动两个原生服务、验证PID、UID、cwd和环境hash。
7. 主Agent用 `skill-reuse-catalog-probe.py` 在隔离工作区、真实服务身份、无网环境读取实际已安装Skill，验证A/A同路径与内容/mtime复用；不加载生产凭据、不调用模型。candidate和正式安装路径都执行，证据独立保存。
8. `verify` 核对原生新hash、安装测试、会话保留、国内/海外本机ready、API ID/image/StartedAt原样、Skill/前端/Compose/其他资源原样。`resume` 先再验证，然后恢复两代理、核对正式海外ready，写RESUMED并释放owner。不得在开放入口后用旧静态会话快照判定正常用户写入是损坏。

## 命令

先将只读baseline脚本内容通过SSH stdin送入 `python3 -B -`，在本地保存JSON到Git忽略的 `output/release/skill-reuse-baseline-20261106.json`。不要用会输出服务器环境变量的命令。

```powershell
python -m unittest discover -s scripts/release -p 'test_skill_reuse*.py' -v
python .codex/hooks/harness.py review-status
python scripts/release/skill-reuse-package.py --baseline output/release/skill-reuse-baseline-20261106.json
```

包为 `output/release/skill-reuse-20261106-<commit7>/release.tar.gz`。本地与远程SHA256必须一致。上传沿用上述明确IP/密钥和两项SSH选项。source/work必须为新目录：父目录及source逐层0755供真实服务身份读取，work0700。source解包文件0644、目录0755，不允许链接或额外文件。

```sh
source_dir=/opt/hengxin-skill-reuse-<commit7>/source
work=/opt/hengxin-skill-reuse-<commit7>/work
runner=$source_dir/scripts/release/skill-reuse-deploy.py
python3 -B "$runner" prepare --source "$source_dir" --work "$work"
python3 -B "$runner" test --work "$work"
# 执行candidate真实catalog探针，保存证据。
python3 -B "$runner" gate --work "$work"
python3 -B "$runner" install --work "$work"
# 执行最终安装路径真实catalog探针，保存证据。
python3 -B "$runner" verify --work "$work"
python3 -B "$runner" resume --work "$work"
```

逐条执行，失败停止；不修改包/manifest绕过hash。真实catalog命令以主Agent提交的probe CLI说明为准。

## 恢复

`python3 -B "$runner" recover --work "$work"` 保持双代理关闭，拒绝pending systemd stop job，恢复原生源码/consumer后才恢复代理；API从未停止，不运行docker restart/up/stop。恢复不回灌数据库、不回滚会话。部分新增文件恢复支持absent，源码新版本留在app树外归档。恢复前若已开放并产生新会话写入，停止原生后另存recovery-preserve基线，以保留新产生的合法上下文。

停机超时保留运行时no-SIGKILL保护和host owner，等待真实inactive后再recover；不能强杀或手动删除owner。暂存中断字节留app树外并归档，重复install不会覆盖原始备份。API/配置/无关源码/PID漂移会拒绝继续，需实查差异。

## 准备期验证

10项本地unittest通过：代理作用域/重复匹配拒绝、旧nginx worker识别与期限、原始/absent备份、备份缺项与篡改、恢复absent/异常PID/无关源码拒绝、元数据保留不读私密字节、API同容器重启检测、pending stop拒绝重新开放、测试/helper白名单。所有新增helper编译通过。

这些是发布工具本地自测；不代表已经运行Linux安装套件或完成生产部署。正式Linux、真实catalog、部署证据由主Agent另行补充。
