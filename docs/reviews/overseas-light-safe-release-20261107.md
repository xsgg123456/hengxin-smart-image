# 海外轻量化安全发布修复独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 提供的 candidateId：`5f90e34a82879c909ea1cdf9f772041757247dd74258473fe07d1b0e62a416fb`。审查开始、报告写入前及写入后 `review-status.currentId` 均为该编号，`approved: false`；HEAD 为 `0b9d68b8f402c3cc341909a6f416ffd1a55c2995`，此前已审业务快照为 `e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9`。审查期间受控源码未变化。
- 相对已审业务快照的受控差异为 `scripts/release/overseas-light-deploy.py`、`overseas-light-frontend.py`、`overseas-light-package.py`、`overseas-light-runtime.py`、`test_overseas_light_installer.py`、`test_overseas_light_release.py`。范围为本次发布修复、旧问题及目录和资源竞态；业务与 UI 只映射同一业务提交的既有独立审查，不重跑无关业务测试或修改实现。
- **Stage 1：FAIL，2 项 HIGH。Stage 2：未执行，不是 PASS。** 不得为本候选登记两阶段 PASS。两项 HIGH 已分别通知主 Agent；修复后重新 `review-prepare`，从 Stage 1 复审新快照。
- 本次未访问生产、部署、提交或修改实现。`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 的首次发布、回退和生产状态是主 Agent 的记录，本次未在线核实。

## Stage 1：HIGH · 并发出现的共享资源被覆盖且回退不恢复

`DEV-PLAN.md:7` 要求采用保护、备份及回退方式发布；`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求检查同名资源冲突、实际安装保留逐文件检查。`scripts/release/overseas-light-frontend.py:201–207` 判断目标不存在后才复制，但该检查与后续写入不是原子操作。`overseas-light-frontend.py:83–93` 的复制函数即使发现目标已是普通文件仍执行 `os.replace`，没有比较其内容。Linux 的 `rename` 会原子替换已存在的目标，见 [Linux rename(2)](https://man7.org/linux/man-pages/man2/renameat.2.html)。

本次在本机 `python:3.12.10-slim-bookworm` 只读、无网络容器的私有临时目录中真实调用安装和回退；仅替换包验证为本地 manifest 桩。在目标不存在的检查后、`os.replace` **之前**确定性创建不同内容的共享文件，安装正常返回并将该文件覆盖；回退只恢复入口文件，未恢复被覆盖的共享资源。注入的是并发文件出现在检查后的时序，前提是存在可写目标静态目录的并发主体；本实验不表示生产存在此并发条件。`overseas-light-frontend.py:224–241` 的回退范围仅 `frontend.ENTRIES`；`sku-frontend.py:14` 定义该范围不含共享资产。现有 `test_overseas_light_release.py:27–36,68–94` 只测预先存在的碰撞，不能排除此竞态。修复应保证目标出现时不会覆盖它，并对关键时序和回退保留增加真实安装测试。

## Stage 1：HIGH · 普通目录替换仍可改变原无关目录的权限和内容

`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求安装只处理本次目标且不修改无关目录。`overseas-light-frontend.py:150–161` 在 `mkdir` 成功后设置 `created=True`，随后以 `O_NOFOLLOW` 打开当前名称并 `fchmod`；它没有证明打开的目录还是刚创建的 inode。`O_NOFOLLOW` 拒绝符号链接，并不阻止同文件系统中的真实目录被重命名到该名称；`fchmod` 改变当前打开描述符所指对象，见 [Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html) 和 [Linux fchmod(2)](https://man7.org/linux/man-pages/man2/fchmod.2.html)。生产入口要求 root，见 `overseas-light-deploy.py:265`。

本次在上述 Linux 容器的私有临时目录真实调用 `ensure_asset_directory`：注入刚创建子目录后，将其移走，再把原位于目标树外、权限为 `0700` 的真实目录重命名到该名称。函数正常返回，原目录的 inode 未变但权限变为 `0755`。此复现前提是同文件系统且并发主体有两个父目录的重命名权限；目录先被并发主体移到目标树中，不能说原外部路径仍存在，更不能推断生产存在此条件。现有 `test_overseas_light_installer.py:63–89` 注入的是符号链接替换，不能覆盖普通目录替换；目录保护目标因此尚未完整满足。

进一步用真实 `install_frontend` 实验：即使目标 `assets` 父目录原已存在，在 `overseas-light-frontend.py:202` 的目录确认返回后、复制前将它移走，再将原本在目标树外的 `0700` 真正目录移入，安装会在该原目录 inode 新增文件并成功，回退不删除该文件。输出见第 5 项；前提及目录已被移入目标树的边界同上。这表明单纯要求父目录预先存在，不足以证明后续对目标 inode 的操作符合预检时的目录身份。

## Stage 1：需求、旧问题和发布边界

以下业务条目仅映射 `docs/reviews/overseas-light-complete-20261107.md` 对同一业务提交的已测证据；本候选六项受控差异都在发布脚本和测试，未重新验证生产或将旧报告批准为本候选。

| 条目 | 结论和证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址与权限 | 已审证据见 `docs/reviews/overseas-light-complete-20261107.md:17`。 |
| `Product-Spec.md:8` 实际发起、幂等、排队、取消、重发与日期 | 已审证据见该报告第 18 行。 |
| `Product-Spec.md:9–10` 历史未知、图片、停用人员和保留边界 | 已审证据见该报告第 19 行。 |
| `Product-Spec.md:11` 概况、下钻、筛选、分页和详情 | 已审证据见该报告第 20 行。 |
| `Product-Spec.md:15–16` 真实归档人、筛选、历史和权限 | 已审证据见该报告第 21–22 行。 |
| `Product-Spec.md:20` 实际负责人、改派和范围 | 已审证据见该报告第 23 行。 |
| `Product-Spec.md:21` 过滤、20 条分页和返回 | 已审证据见该报告第 24 行。 |
| `Product-Spec.md:22` 状态分组、历史状态和删除异常 | 已审证据见该报告第 25 行。 |
| `Product-Spec.md:23` 分批归档、显式完成和解冻 | 已审源码证据见该报告第 26 行，未操作生产。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 确认预览、窄屏和错误态 | 业务快照的隔离浏览器和设计对照见该报告第 27、31–35 行；本次未重开页面，新包和生产验收未完成。 |
| `DEV-PLAN.md:7` 与发布记录第 7 行：公开 SVG | `overseas-light-package.py:30–35,64–71` 对 `frontend/dist/assets/` 外的 `.svg` 使用 `package-delivery.py:39–40` 的换行归一，其他资源字节不改；`test_overseas_light_release.py:17–24` 覆盖示例。上一包 14 个公共 SVG 与 6 个哈希 SVG 的独立对照见 `docs/reviews/overseas-light-publish-final-20261107.md:58–67`；本次未生成新包。 |
| 旧 MEDIUM：预先存在的普通文件祖先、链接和入口目录 | `overseas-light-deploy.py:98–106,200–205` 在 prepare 和关入口前调用 `overseas-light-frontend.py:117–137` 预检；`test_overseas_light_release.py:27–94` 验证已存在碰撞先于流量更改及路径类型检查。此结论不覆盖上方安装时并发文件覆盖。 |
| 旧 HIGH：固定临时文件残留与前端回退异常 | `overseas-light-frontend.py:75–98,224–241` 使用唯一临时文件并清理；`test_overseas_light_installer.py:9–60` 在 Linux 真实安装/回退并保留旧 `.sku-new`，也注入替换失败检查临时文件清理。`overseas-light-deploy.py:237–250` 捕获前端回退异常后仍尝试恢复旧 API，异常时记录且不重开入口；`test_overseas_light_release.py:202–227` 用服务桩验证调用顺序和错误记录，不能证明真实生产回退。 |
| 旧 HIGH：无关旧目录符号链接和创建后链接替换 | `overseas-light-frontend.py:140–168,198–207` 仅创建目标资源目录、POSIX 按目录描述符逐级 `O_NOFOLLOW` 打开；`test_overseas_light_installer.py:24–43,63–89,92–131` 在 Linux 真实链接上验证无关目录权限保留，以及创建后和写入/删除前的链接替换被拒绝。但普通目录替换仍有上方 HIGH，不能宣称目录保护整体通过。 |
| 提交和包范围 | `overseas-light-package.py:76–86,90–112` 要求提交和已审身份，构建读取固定 commit，manifest 写入 commit 与 candidateId；`overseas-light-runtime.py:21–27,30–56` 固定基线并将新 helper 纳入白名单和哈希校验。本机确认 HEAD 的父提交是指定基线；新正式包未构建，不能把源码检查当作包或生产安装证明。 |

**部分实现：** 两项并发路径不满足共享资源及无关目录保护；正常路径和链接替换仅在表述范围内成立。**未实现：** 本次发布和生产验收尚未完成。**Spec 漂移：** 六项受控差异均是发布代码或测试，未发现新增业务页面、API 或表；这不是全仓漂移审计。

## 本候选独立验证原始输出

1. Windows 使用 `hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py scripts/release/test_overseas_light_installer.py`，exit 0：

```text
.............                                                            [100%]
13 passed in 0.94s
```

Windows 上 `test_overseas_light_installer.py:63–64,92–94` 的两个 POSIX 专用测试直接返回；因此这 13 项不能代表已实测 Linux 链接竞态。

2. `python:3.12.10-slim-bookworm`、无网络、容器根文件系统和源码挂载只读、临时文件在容器 `/tmp`，运行真实 `python -B /review/test_overseas_light_installer.py`，exit 0：

```text
ISOLATED_INSTALL_AND_ROLLBACK_PASS
```

3. 同一容器真实安装、回退，注入共享资源在内部目标 `stat` 后、`os.replace` 前出现，exit 0：

```text
created_after_internal_target_stat: True
injection_reached: True
install_returned_success: True
after_install_target: release asset
after_rollback_target: release asset
```

4. 同一容器真实 `ensure_asset_directory`，注入普通目录替换，exit 0：

```text
outside_mode_before: 0o700
post_mkdir_swapped_to_ordinary_directory: True
ensure_returned_success: True
same_directory_inode: True
moved_directory_mode_after: 0o755
```

5. 同一容器真实安装和回退，在确认已存在父目录后注入普通目录替换，exit 0：

```text
preexisting_parent_replaced_with_originally_outside_directory: True
install_returned_success: True
same_directory_inode: True
directory_mode: 0o700
added_asset: release asset
added_asset_after_rollback: release asset
```

6. 对六个受控发布 Python 文件执行 `compile(path.read_bytes(), ..., 'exec')`，exit 0，原始输出：

```text
COMPILE_OK 6
```

7. `git diff --check`，exit 0，原始 stdout/stderr 均为空。`git merge-base --is-ancestor b8d0b57e3dcfdcefd8bda400af672efac6b18240 HEAD` 和 `git show -s --format='%H %P' HEAD`，exit 0：

```text
BASE_ANCESTOR_OK
0b9d68b8f402c3cc341909a6f416ffd1a55c2995 b8d0b57e3dcfdcefd8bda400af672efac6b18240
```

## 未执行和后续门禁

因 Stage 1 存在 HIGH，Stage 2 的完整代码质量、安全扫描、测试真实性审查和邻页视觉复核未执行。新正式包、包内完整动态资源、生产隔离安装、实际流量切换及线上验收均未由本次审查完成。修复后必须固定新 candidate、对差异从 Stage 1 复审；通过两阶段后由主 Agent 按 `docs/HARNESS-REVIEW.md` 登记同一快照，不得以写 `.needs-review` 为 clean 代替。
