# 海外轻量化发布修复独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 提供的 candidateId：`e9bfebf86a057d50ed4ae562273db061adbdd068e8558d79e6db5a04d3a8e292`；审查开始时 `review-status.currentId` 与其相同，`approved: false`，HEAD 为 `0b9d68b8f402c3cc341909a6f416ffd1a55c2995`，已审业务快照为 `e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9`。受控差异为 `scripts/release/overseas-light-deploy.py`、`overseas-light-frontend.py`、`overseas-light-package.py`、`overseas-light-runtime.py`、`test_overseas_light_installer.py`、`test_overseas_light_release.py`。
- 范围：海外轻量化本次发布修复，检查公共 SVG、路径碰撞预检、共享资源安装、临时文件、部分安装及回退、API 恢复和入口关闭、打包身份及 manifest；业务和 UI 仅映射先前已审的同一业务提交。本次不访问生产、不修改实现、不提交、不部署。
- **Stage 1：FAIL，1 项 HIGH；Stage 2：未执行。** 不得为此 candidate 登记两阶段 PASS。
- **审查期间源码变化：** 发出 HIGH 通知后，主 Agent 开始修复，`review-status.currentId` 先变为 `3cd1f13d0cc017443c2f399ea70773739105d3735c17d65084982da492b4e239`，随后变为 `43b0652c74dec091c7abe207c11b0dec8ce5331426111f77b3c4ebc90ffb800c`，均非送审快照。下文源码行号和实验归属明确限定为审查开始时的 **e9bfebf8… 版本**；工作区当前同名文件已经变化，不得把此报告套用于新版本。新代码须完成后重新 `review-prepare` 并从 Stage 1 独立复审。

## Stage 1：HIGH · 新建目标目录在 mkdir 与 chmod 之间被替换时仍可改动外部权限

`DEV-PLAN.md:7` 要求采用现有保护、备份和回退方式；`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求只处理本次目标，避免修改无关目录，并处理预检后的路径变化。送审版本 `scripts/release/overseas-light-frontend.py:65–73` 在 `current.is_symlink()` 检查后调用 `current.mkdir(mode=0o755)`，随即对同一路径调用 `current.chmod(0o755)`，并未确保 chmod 仍作用于刚创建的目录。`scripts/release/overseas-light-deploy.py:265` 要求以 root 执行。

本次在 WSL Linux 私有临时目录，真实调用送审版本的 `ensure_asset_directory()`。测试将 `Path.mkdir` 包装为：真实创建指定的新资产目录后立即移除该空目录，将其替换为指向临时发布树外 `0700` 目录的真实目录符号链接，再让函数继续执行；以此确定性模拟该时间点的并发替换。**函数正常返回，外部目录权限变为 `0755`。** 这是对目录创建之后、chmod 之前发生替换的故障注入，前提是存在有权限改变该目录项的并发主体；并非声称生产存在此条件或本次测试访问了生产。安装随后即使因其他检查失败，该外部权限变更也已发生，现有前端回退不会恢复它。

该复现与先前未关联旧链接遍历引起的 HIGH 属于同一保护目标：静态树外的目录权限仍可被发布脚本修改。`Path.chmod()` 在 Linux 默认跟随符号链接；Python 官方文档说明其 `follow_symlinks` 默认值及文件描述符形式：[Python `os.chmod`](https://docs.python.org/3/library/os.html#os.chmod)。Linux 的目录文件描述符接口用于规避路径分量在多个操作间改变的竞态：[Linux `openat(2)`](https://man7.org/linux/man-pages/man2/open.2.html)。建议修复时审查完整目标路径上的创建、检查、复制、替换和删除；单独在 chmod 前再做一次路径检查仍有检查到使用之间的窗口。

## Stage 1：逐项核对与旧问题状态

以下业务需求与设计的代码和浏览器证据属于 `docs/reviews/overseas-light-complete-20261107.md:17–27,31–35` 的已审业务快照；本 candidate 的受控差异仅在上述六个发布文件。此处不是重新运行全量业务测试，也不把旧报告批准为本 candidate。

| 条目 | 结论和证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址和权限 | 业务快照已审证据见 `docs/reviews/overseas-light-complete-20261107.md:17`。 |
| `Product-Spec.md:8` 请求发起、幂等、排队、取消和日期 | 业务快照已审证据见上述报告第 18 行。 |
| `Product-Spec.md:9–10` 历史未知、图片、停用人员和保留边界 | 业务快照已审证据见上述报告第 19 行。 |
| `Product-Spec.md:11` 概况、下钻、筛选、分页和详情 | 业务快照已审证据见上述报告第 20 行。 |
| `Product-Spec.md:15–16` 实际归档人、筛选、历史及权限 | 业务快照已审证据见上述报告第 21–22 行。 |
| `Product-Spec.md:20` 真实负责人、改派和范围 | 业务快照已审证据见上述报告第 23 行。 |
| `Product-Spec.md:21` 条件过滤、20 条分页和返回 | 业务快照已审证据见上述报告第 24 行。 |
| `Product-Spec.md:22` 状态分组、历史状态和删除异常 | 业务快照已审证据见上述报告第 25 行。 |
| `Product-Spec.md:23` 分批归档、显式完成及解冻 | 已审源码证据见上述报告第 26 行，未操作生产。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3`、确认预览 | 已审隔离浏览器与邻页对比见上述报告第 27、31–35、42 行；此候选未修改 UI，本次未重开页面。最终新包及生产验收仍未执行。 |
| `DEV-PLAN.md:7`、发布记录第 7 行：公共 SVG 换行 | 送审 `scripts/release/overseas-light-package.py:30–35,64–71` 仅对 `frontend/dist/assets/` 外 `.svg` 调用 `scripts/release/package-delivery.py:39–40` 的换行归一；其他字节原样。`scripts/release/test_overseas_light_release.py:17–24` 对公开 SVG、哈希 SVG 和非 SVG 断言，纳入下述 11 项测试。此前的上一正式包 14 个公开 SVG 和 6 个哈希 SVG 的对照证据见 `docs/reviews/overseas-light-publish-final-20261107.md:58–67`；本次没有生成或验收新包。 |
| 先前 MEDIUM：普通文件祖先、有效/失效符号链接及入口目录 | 送审 `overseas-light-frontend.py:42–62` 检查目标入口、资源路径的祖先类型和链接及同名文件摘要；`overseas-light-deploy.py:98–106,200–205` 在 prepare 和关入口之前调用；`test_overseas_light_release.py:27–92` 验证普通文件碰撞、目录/链接条件及碰撞在关入口前阻断。符号链接分支使用 `Path.is_symlink` 模拟，不能把它说成这次对真实目标链接的实测。预检后目录项竞态另见上方 HIGH。 |
| 先前 HIGH：固定临时文件残留及回退独立恢复 API | 送审 `overseas-light-frontend.py:23–39` 用随机唯一名称、排他创建和 `finally` 清理；`sku-frontend.py:73–90` 的回退调用已绑定该复制函数。送审 `overseas-light-deploy.py:227–250` 捕获前端回退异常后仍尝试旧 API，任一恢复异常写入 `ROLLBACK_ERRORS.json` 且不重开入口。`test_overseas_light_release.py:95–109,200–225` 覆盖旧 `.sku-new`、复制失败清理、前端回退异常后旧 API 的调用顺序和入口未重开；后者用 API/代理桩，不是生产恢复证据。 |
| 先前 HIGH：无关旧目录链接被遍历 chmod | 送审 `overseas-light-frontend.py:95–104` 只按本次资源创建缺失目录，去除旧 `sku-frontend.py:55–57` 遍历所有既有目录的行为；`test_overseas_light_release.py:112–133` 验证不 chmod 无关目录。常态问题得到处理，创建目录时的替换竞态仍为上方 HIGH，不能标记为整体消除。 |
| 部分安装和失败回退 | 送审 `overseas-light-frontend.py:82–94` 先保存入口并写 `COMPLETE.json` 才开始安装，`sku-frontend.py:73–90` 对完整或部分安装状态核验后回退入口；`overseas-light-deploy.py:237–250` 将回退与 API 恢复的错误分别记录并保持入口关闭。旧资源保留；保护边界中的外部目录权限不随此回退恢复。 |
| 源提交、基线和包文件范围 | 送审 `overseas-light-package.py:76–86,90–112` 要求干净已提交源码、已批准快照、基线祖先及打包期间身份不变；`package-delivery.py:70–75` 检查批准状态。`overseas-light-runtime.py:21–27,30–56` 固定旧镜像、基线、helper 白名单及包路径/摘要，新 helper 列入名单。`git merge-base --is-ancestor b8d0b57e3dcfdcefd8bda400af672efac6b18240 HEAD` 本次返回成功，当前 HEAD 的父提交为该基线。最终包尚未构建，本项是源码检查，不证明包或生产基线已验收。 |

**未实现/部分实现：** 目标路径替换下的目录保护不符合上述发布要求，故 Stage 1 失败；其他条目仅在表中明确限定的范围内核对。**Spec 漂移：** 送审快照相对已审业务快照的六个受控差异均是发布脚本和测试，未发现新增业务页面、API 或表；非全仓漂移审计。

## 验证原始输出

1. 送审快照执行 `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py scripts/release/test_overseas_light_installer.py`，exit 0：

```text
...........                                                              [100%]
11 passed in 1.03s
```

2. WSL Linux 临时目录真实调用送审版 `ensure_asset_directory`，在目标 `mkdir` 后确定性将目录替换为真实符号链接，exit 0。以下为测试程序原始标准输出，WSL 启动另产生本机网络提示：

```text
outside_mode_before: 0o700
path_swapped_to_directory_symlink_after_mkdir: True
ensure_result: RETURNED_SUCCESS
outside_mode_after: 0o755
```

3. 编译检查对六个路径调用 Python `compile(..., 'exec')`，exit 0，原始标准输出如下；该命令在主 Agent 开始修改后执行，**不能绑定为送审快照的编译证据**：

```text
COMPILE_OK 6
```

4. `git merge-base --is-ancestor b8d0b57e3dcfdcefd8bda400af672efac6b18240 HEAD` 成功，`git show -s --format='%H %P' HEAD` 和 `git diff --check` 的输出为：

```text
BASE_ANCESTOR_OK
0b9d68b8f402c3cc341909a6f416ffd1a55c2995 b8d0b57e3dcfdcefd8bda400af672efac6b18240
```

`git diff --check` 原始标准输出和标准错误为空。

## 未执行及交接

由于 Stage 1 有 HIGH，Stage 2 的代码质量、测试真实性全面审查、安全扫描及新邻页视觉对比均未执行。新版本已在审查期间变化，必须重新固定快照、对差异从 Stage 1 重审，不能登记本报告为 PASS。新发布包、生产隔离安装、生产实际流量切换与线上验收尚未执行；首次生产发布及回退情况仅为 `docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 的主 Agent 记录，本审查未在线核验。
