# 海外完整 Skill 运维入口

本文件说明离线安装和校验。2026-10-13生产14包安装及API/native/真实worker沙箱验证已完成，证据见 `OVERSEAS-DELETE-SKILLS-PRODUCTION-20261013.md`。安装不注册虚构业务用户，不写国内或海外业务表，不执行包内脚本，不调用生图。

## 目录与冻结

- 唯一当前来源：海外 `OVERSEAS_LOCAL_SKILL_ROOT/current.json` 指向 `releases/<sha256>`。
- 每个发布目录包含 `manifest.json` 与完整的 `<Skill标识>/SKILL.md`、agents、references、assets、scripts 等原包内容。源目录保持不变；必要名称与自引用改动逐文件列在 manifest 的 `adaptedFiles`，源/目标目录及文件校验在 `sourceEntries`/`entries`。
- 安装先完整预检和复制，再以原子替换发布 current.json。再次安装相同包复用同一发布目录；失败不会把新包标成可用。保留历史发布目录，禁止删除仍被排队/运行/历史重试引用的版本。本入口不提供发布清理命令。
- 管理目录与工作台共用真实目录校验，页面只收到 id/name/displayName/description。空目录返回空列表；读取、权限或完整性失败返回503。未安装的数据库条目不会显示。旧默认编号只在同名完整包存在时映射；否则422明确拒绝。
- 新轮次冻结发布SHA及包SHA。执行前再次完整验证、复制所有文件至本轮私有目录，沿用原生CLI只读挂载。旧轮次的files/assets快照仍受支持。
- 目录读取按发布SHA及全树stat指纹缓存哈希结果。文件新增、删除、内容/权限/链接状态改变会重新验证；执行前完整验证不使用目录缓存。

## 本地预检与打包

在 `hengxin-smart-image/backend` 执行；source/output需为绝对路径。默认14包映射已版本化在 `app/overseas/management/skill_inventory_20261013.json`。

```powershell
./.venv/Scripts/python.exe -m app.overseas.management.skill_install preflight --source 'C:/Users/82358/Documents/Codex/2026-10-13/bang-w/outputs/SKILLS合集_独立提取'
./.venv/Scripts/python.exe -m app.overseas.management.skill_install bundle --source 'C:/Users/82358/Documents/Codex/2026-10-13/bang-w/outputs/SKILLS合集_独立提取' --output 'D:/Work_Project/hengxin-smart-image/output/overseas-skills-20261013'
```

本次源：14包，181文件，111,321,820字节。安装副本：181文件，111,321,938字节；118字节差额仅来自唯一名称及自引用适配。

发布SHA：`7f409fdc92401c25f559899e3529720480b482cee0bfbbbca8daaecb0c0c2bbc`。

打包目录可整体传输，不能仅传SKILL.md或删参考图。OUTON主图约47MiB由目录安装承接，不经过20MiB网页ZIP入口。

## 生产安装与检查

先部署与该协议匹配的海外API/原生worker代码。加载已配置的海外环境，确认 `HX_BUSINESS_CONTEXT=overseas`、`OVERSEAS_APP_ENV=production`，操作员以root运行安装。安装目录必须已经存在，root所有且组/其他用户不可写；发布内容由安装程序设置目录755、文件644、脚本755。API和worker使用同一个海外卷；API侧建议只读挂载。

生产白名单仅：

- API卷内 `/var/lib/hengxin-overseas/local-skills`
- 原生worker卷路径 `/var/lib/docker/volumes/hengxin-overseas_overseas_local_skills/_data`

2026-10-13主Agent只读实查发现，现有native `/var/lib/hengxin-overseas/local-skills` 与旧API named volume实际是两个不同inode的空目录。发布必须先归一：以native路径为唯一目录，设置root:root/755；新Compose overlay把API与migrate的同目标local-skills挂载替换成此宿主目录的只读bind。保持worker既有环境路径，保留旧空named volume不做删除。不允许两边各安装一份后宣称同源。

在已加载海外环境的backend目录执行，bundle路径替换为上传后完整包的位置：

```sh
python -m app.overseas.management.skill_install install --bundle /已上传目录/7f409fdc92401c25f559899e3529720480b482cee0bfbbbca8daaecb0c0c2bbc
```

然后切换为海外原生worker用户，加载其环境执行：

```sh
python -m app.overseas.management.skill_install verify
python -m app.overseas.management.skill_probe
```

`verify`检查实际生产目录，`skill_probe`复用真实Bubblewrap及CLI二进制所在目录，逐包在同样的Linux沙箱里读取两处挂载的全部文件、核对SHA、验证只发现本轮所选Skill并拒绝写入。只运行本地Python校验，未启动Codex生图、未读认证文件、未接生产任务。临时探测目录创建在海外执行根并在结束时清理。

API容器与native分别运行verify，比较输出的`directoryIdentity.device/inode`一致，证明实际共享同一目录。native probe必须以真实海外worker用户执行，输出uid须为该用户；不得仅以root探测代替。发布drain及重启由主Agent按既有运维流程处理。

预期probe结果：packages=14、files=181，每条readOnly=true。还需使用有效海外身份确认管理页与工作台名称一致、两份沃尔玛同时存在。

首次生产切换实测：发布进程的 umask 077 将新建 releases 父目录限制为700，真实worker探针拒绝放行。已核实该目录为海外专用、root所有、无链接后改为755，重新执行API/native/sandbox全量校验通过并恢复入口。发布运维脚本需在调用安装器前显式确保 ROOT/releases 为root所有的755目录，不能只依赖mkdir的mode参数；已有非目录或链接必须拒绝。该修正仅作用于公共Skill发布目录，备份、凭据及任务私有目录继续保持原有保护。

此验证证明目录、选择及隔离加载；不证明字体已齐全或真实成图质量合格。原14包未带字体，生产字体、文档/图片工具仍须单独核查并记录。

## 本轮本地证据

`pytest tests/test_overseas_installed_skills.py tests/test_overseas_management.py tests/test_overseas_skill_packages.py tests/test_overseas_studio.py -q` 已通过25项、1项Linux权限检查在Windows跳过，覆盖真实完整包选择/冻结、更新不影响旧快照、同名变体共存、损坏/缺文件/目录权限拒绝、未安装索引隐藏、旧快照资源读取、21MiB单资源、发布失败与原子指针、缓存失效与执行重新验证、网页写入口关闭。相关代码compileall通过。

真实14包预检与bundle生成已执行并得到上述数量、字节和SHA。另在独立TemporaryDirectory内实际安装两次、校验幂等，并把14份选择逐一经materials.prepare冻结复制到私有轮次；对181文件逐字节与发布包比较全部一致，111,321,938字节。两份沃尔玛中文名同时验证。Windows样本首次完整目录校验3806ms，stat缓存读取150ms。

Windows没有生产Bubblewrap环境，沙箱probe及生产安装结果由主Agent在Linux独立记录。Windows海外整组一度为325通过/62跳过/10失败，其中2项是并行开发中的路由/权限断言待同步，8项因现有Linux安全读取或symlink权限条件失败；不能把专项通过当作整组通过。Linux全套及PG结果由主Agent最终验收记录。
