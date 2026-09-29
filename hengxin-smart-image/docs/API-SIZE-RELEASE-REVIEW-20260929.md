# API 尺寸发布增量独立审查

- candidateId：`2f4d2aba7f628759509374272a2bc58f3bd20cb8b12239ac099055db6ebd9bb2`
- 结论：Stage 1 **PASS**；Stage 2 **PASS**。此结论批准发布工具代码，不代表实际安装或生产部署已经验收。
- 范围：`scripts/release/{package-api-size,api-size-deploy,api-size-runtime,api-size-verify}.py`、三份对应测试、`frontend/package.json` 版本，以及 DEV-PLAN、发布记录、CHANGELOG 的发布授权增量。路径未写项目子目录时均相对仓库根目录。
- 业务基线：已提交的 `c60a0de`；本次不重新替代该业务审查。读取 Product-Spec 文首尺寸需求及迁移文件，确认工具所发布的版本与该功能相容。用户后续发布授权以 DEV-PLAN.md:3、Product-Spec-CHANGELOG.md:534 和发布记录为本轮边界。
- 独立执行：读取代码、故障分支及既有 text 发布脚本差异，重新运行 14 项测试和 Python 编译；未连接生产、未修复代码、未提交。review-status 返回的 currentId 与上述 candidate 一致，审查期间未发现受控文件变化。

## Stage 1：Spec Compliance — PASS

| 发布要求 | 实现与证据 | 判定 |
|---|---|---|
| 固定 0.2.13 / 0021、旧基线 0020 | `hengxin-smart-image/frontend/package.json:3`；`scripts/release/package-api-size.py:100`、`:117`；`scripts/release/api-size-deploy.py:41`、`:67`、`:84`；迁移 `hengxin-smart-image/backend/migrations/versions/0021_api_image_dimensions.py:5` 声明 0020 父版本 | 完整实现 |
| 复用生产完整 Compose 配置及五容器 | `scripts/release/api-size-runtime.py:43` 从运行 API label 读取全部路径，逐容器核对固定旧镜像、环境和 command；`:59` 仅追加 image/build；`scripts/release/test_api_size_runtime.py:16` 验证所有基线层保留。只读基线文件 `output/api-size-production-before.json` 给出 12 层实际路径与旧镜像 | 完整实现 |
| 已审且已提交源码、封闭白名单包、哈希及隐私 | `scripts/release/package-api-size.py:22`、`:51`、`:70`、`:98`；共同门禁 `scripts/release/package-delivery.py:65` 校验 approved；包逐文件读取 Git，末尾重查快照和 HEAD；归档回读逐字节对比；测试 `scripts/release/test_package_api_size.py:13`、`:24`、`:30`、`:36`、`:47` 全通过 | 完整实现 |
| 先实际镜像断网测试再部署 | `scripts/release/api-size-deploy.py:57` 使用 --network none、--init 执行安装测试并记录镜像 ID；`:66` 部署核对同一 ID。测试排除仅仓库工具及一个依赖前端源码的契约用例，`:19` 保留其余契约测试 | 完整实现；实际安装待主 Agent 执行 |
| 暂停接纳、排空后备份 | `scripts/release/api-size-deploy.py:73` 停入口/API/派发器，暂停渠道，排空 API 和原生 Worker，再复查 pending；`:80` 停派生图服务后备份；`scripts/release/image-inputs-worker.py:31` 核验 active/reserved/scheduled 与数据库；测试 `scripts/release/test_api_size_deploy.py:116`、`:128` 通过 | 完整实现 |
| 数据库、源码、静态入口、配置备份 | `scripts/release/api-size-runtime.py:69` 导出 custom dump 并 pg_restore --list 验证，备份 native-app、入口、包版本、发布元数据及每一 Compose 文件，最后写 COMPLETE | 完整实现 |
| 迁移、原生和容器同步、静态入口切换 | `scripts/release/api-size-deploy.py:83` 顺序迁移、安装原生、验证依赖/Worker、启动五容器、健康检查、发布前端后恢复接纳；`scripts/release/api-size-runtime.py:101` 保留旧哈希资源，以 os.replace 切换入口 | 完整实现 |
| 失败恢复不覆盖业务库 | `scripts/release/api-size-deploy.py:104` 区分入口已开放、排空不明和已排空；`:123` 恢复旧源码/元数据/入口/Compose，保留 schema；`:151` 回退失败关闭接纳。`scripts/release/test_api_size_deploy.py:95`、`:103`、`:109`、`:116`、`:122` 均实际调用控制器并注入失败，断言最终代码与 paused/schema 状态 | 完整实现 |
| 线上版本、哈希、schema、健康和鉴权验证 | `scripts/release/api-size-verify.py:23` 核对五容器实际镜像 ID、环境、command、包内 backend 哈希；`:36` 核验原生/前端；`:47` 核验四 nullable 列；`:56` 起健康、公网入口/资源哈希及匿名 401 | 完整实现；线上执行待部署后 |
| 不新增收费生成、不扩产品范围 | 上述工具仅打包/部署/验证，未增加模型调用、页面、API 或表；迁移只增加四个 nullable 证据字段（迁移文件:12），不改历史数据 | 无 Spec 漂移 |

部分实现、未实现：本次发布工具范围内无。实际归档、镜像安装、线上尺寸 DTO 和页面验证属于后续发布执行，不以本报告替代。

UI 一致性及引导真实性：本增量唯一前端变化为 `hengxin-smart-image/frontend/package.json:3` 版本号；无页面、文案或样式变更，邻居页面视觉对比不适用。业务视觉验收沿用此前业务审查，本报告没有声称重新打开页面。

## Stage 2：Code Quality — PASS

- 代码结构：7 个新增 Python 文件均小于 300 行（163/118/70/125/140/48/58），打包、运行支持、部署控制、线上核验职责分开。与 text 发布脚本逐行对比确认主要为固定版本、迁移、旧镜像及元数据名称更新；安装测试增加 --init（`api-size-deploy.py:60`）。版本化发布脚本的重复为可追溯旧版本所用，本轮不重构历史发布物。
- 错误处理：关闭接纳标志提前设置，原生/前端变更标志先于变更设置（`api-size-deploy.py:70`、`:86`、`:96`），能够覆盖部分写入失败；恢复失败继续暂停渠道（`:151`）。未发现本次新增的阻断缺陷。
- 测试真实性：14 项由 reviewer 独立执行全部通过。控制器测试执行真实 main 和文件恢复操作，通过替身隔离 Docker/SQL/systemd；它们证明分支及顺序，不证明真实 Compose 合并、Linux 权限和数据库迁移运行。因此实际镜像安装、上线后核验仍是发布硬性步骤，当前尚未完成；该边界在 DEV-PLAN.md:6 与部署脚本:57、:66 明确。
- 安全扫描：对新增运行脚本搜索 eval、shell=True、innerHTML、前端 secret/token/key 前缀及 password 赋值，无命中。命令以参数列表调用（`api-size-runtime.py:15`），SQL 为固定语句，线上 verifier 的列名来自固定 tuple（`api-size-verify.py:47`）。`/opt` 路径为明确部署目标，不属于用户隐私泄露。
- 隐私：`package-api-size.py:22` 排除 env、运行库、源前端及非白名单脚本；`:51` 拒绝敏感资产名、不支持扩展名和 sourcemap，并递归扫描 gzip。`api-size-deploy.py:34` 设置 umask 077，`api-size-runtime.py:70` 备份目录 0700；完整 Compose 私有配置仅写服务器工作/备份目录，不打印到输出。源码扫描使用 `package-delivery.py:21` 的固定规则及精确合成负例豁免。实际发布包隐私审计结果仍须生成保存。
- 已有依赖风险：`output/api-size-release-audit.json` 原始统计 critical=0、high=33、moderate=30、low=1。`frontend/package.json:3` 本轮只改版本，锁文件未改；本报告不将既有高风险依赖宣称为零漏洞，也不扩大本次发布工具审查为依赖升级。

## 编译与测试原始输出

reviewer 执行 `python -m unittest discover -s scripts/release -p test_api_size*.py -v`：

```text
Ran 9 tests in 0.093s

OK
```

reviewer 执行 `python -m unittest discover -s scripts/release -p test_package_api_size.py -v`：

```text
Ran 5 tests in 0.005s

OK
```

reviewer 对全部 7 个新增 Python 文件执行内置 compile（不写 pyc）：

```text
Python compile PASS: 7 files
```

已读取主 Agent 保存的 `output/api-size-release-build.log`，以下为原始摘录；reviewer 未重复运行前端构建：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.13 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

vite v7.1.7 building for production...
✓ 4483 modules transformed.
✓ built in 31.18s
```

本报告仅绑定上述 candidate；由主 Agent 使用 review-approve 登记两阶段 PASS，再执行提交、打包、安装与发布验收。不写 `.needs-review`。

## 上传执行脚本补充核对

应主 Agent 补充要求，只读核对 ignored `output/api-size-upload.py`，SHA256 为 `f1a71bc305dd0b0b6cf24a7ca381a8c35aa6f7b872a2a5800edca1d43bf067c2`；该文件不在 candidate 或发布包内，此结论仅针对所列文件哈希。第 5 行严格限制 release 标识，8–11 行使用固定 SSH 主机及 StrictHostKeyChecking，第 17 行校验远端归档 SHA，第 20–24 行拒绝重复、非普通文件、绝对路径和父目录逃逸并检查成员集合，26–32 行在新目录逐文件校验 SHA 和解析路径范围后写入。未发现阻断问题；未执行上传。脚本含本机密钥文件路径，属于本机执行上下文，不能加入发布产物。
