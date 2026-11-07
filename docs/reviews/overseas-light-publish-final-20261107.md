# 海外轻量化发布修复独立审查 · 2026-11-07

## 快照、范围和结论

- candidateId：`a38d40445265fed7baaf1be3a99702c24e7cd6418b8e082ffdfd55f7e9d59838`；HEAD `0b9d68b8f402c3cc341909a6f416ffd1a55c2995`。
- 范围：本次海外轻量化发布脚本差异、静态资源打包、发布前冲突预检和安装失败回退；业务与 UI 依据同一已审业务提交的独立报告复核映射。审查开始及报告编写前 `review-status` 均为本 candidateId，受控差异仅 `scripts/release/overseas-light-deploy.py`、`scripts/release/overseas-light-package.py`、`scripts/release/test_overseas_light_release.py`，`approved: false`。
- **Stage 1：FAIL，2 项 HIGH。Stage 2：未执行。** 不得以此报告或此前业务报告批准本候选。修复后重新 `review-prepare`，对新快照从 Stage 1 起复审。
- 本次未修改实现、提交、访问生产或部署。`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 的首次发布及回退状态为主 Agent 的记录，本次没有独立在线核实。

## Stage 1：HIGH · 临时文件残留会导致发布失败且回退无法恢复入口

`DEV-PLAN.md:7` 要求按现有保护、备份与回退方式发布并保护在途任务。`scripts/release/overseas-light-deploy.py:94–114,219–224` 检查目标入口和共享资产，但不检查 `sku-frontend.py:18–24` 的固定临时路径 `<目标>.sku-new`。一次被中断的安装或其他残留若留下 `frontend/dist/index.html.sku-new`，发布预检会放行。

本次在本机隔离临时目录预置普通文件 `index.html.sku-new`，实际调用当前 `deploy()`、真实 `frontend.deploy()` 和真实 `frontend.rollback()`；仅将生产 API、代理开关、服务操作、包校验及状态检查替换为记录事件的本地桩。预检通过后，脚本关入口、停止旧 API、切换候选；`sku-frontend.py:58–61` 写入新 index 时因 `open('xb')` 抛 `FileExistsError`。回退在 `sku-frontend.py:73–87` 恢复旧 index 时使用同一临时路径，再次抛错。`overseas-light-deploy.py:254–264` 因前端回退异常跳过旧 API 恢复和重新开放入口，留下 `ROLLBACK_REQUIRES_INSPECTION`。该结果表明此确定性冲突可引发服务中断和自动回退不完整；**不代表生产当前存在该文件，也不代表本次访问或测试了生产**。

修复需覆盖安装和回退可能写到的临时文件，并验证前端回退发生异常时 API 恢复、入口处理和故障上报的安全行为；不能只通过模拟 `frontend.rollback` 恒成功的测试代替。当前 `scripts/release/test_overseas_light_release.py:130–156` 的回退测试将前端安装与回退都替换为桩，故七项测试通过不能排除此故障。

## Stage 1：HIGH · 已有目录符号链接可令安装修改发布目录外权限

`overseas-light-deploy.py:103–114` 只检查候选资产对应的目标及其祖先，不检查静态目录中与本次候选无关的已有目录链接。`sku-frontend.py:55–57` 随后遍历全部既有静态目录，对 `is_dir()` 为真的路径执行 `chmod(0o755)`；这两个调用会跟随目录符号链接。`overseas-light-deploy.py:274` 要求以 root 执行，因此一个这样的链接可使发布操作修改静态目录以外的目录权限。

本次在本机 Linux 临时目录将 `frontend/dist/legacy` 指向静态目录外的 `0700` 目录，候选包不包含 `legacy`。真实预检通过、真实 `frontend.deploy()` 返回安装成功，但外部目录权限变为 `0755`，见下方原始输出；无任何生产操作。主 Agent 另行告知线上只读核查 7 个子目录均为 `0755`、符号链接为 0；本次未在线复核，且该事实不能证明代码对其他或发生变化的目录安全。修复需同时考虑实际安装步骤对符号链接和已有目录权限的处理，以及预检后路径变化。

## Stage 1：逐项证据与边界

此前业务审查快照 `e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9` 两阶段通过；`review-status` 的差异范围及本次 `git diff` 证明本候选只改变三个发布相关文件。以下业务、权限与 UI 为原报告已测范围的映射，并非本次重新运行生产业务测试。

| 需求 | 状态与证据 |
| --- | --- |
| `Product-Spec.md:7` 入口、旧地址与权限 | 已审业务快照对应实现和浏览器证据见 `docs/reviews/overseas-light-complete-20261107.md:17`。 |
| `Product-Spec.md:8` 实际发起、幂等、排队、取消与日期 | 已审业务快照证据见 `docs/reviews/overseas-light-complete-20261107.md:18`。 |
| `Product-Spec.md:9–10` 历史身份、留存、图片和停用人员 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:19`。 |
| `Product-Spec.md:11` 概况、下钻、筛选、分页和详情 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:20`。 |
| `Product-Spec.md:15–16` 真实归档人、历史及权限 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:21–22`。 |
| `Product-Spec.md:20` 实际负责人、改派和范围 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:23`。 |
| `Product-Spec.md:21` 条件过滤、20 条分页和返回 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:24`。 |
| `Product-Spec.md:22` 状态分组、历史状态和删除异常 | 已审范围证据见 `docs/reviews/overseas-light-complete-20261107.md:25`。 |
| `Product-Spec.md:23` 分批归档、显式完成与解冻 | 已审源码证据见 `docs/reviews/overseas-light-complete-20261107.md:26`；未操作生产。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 确认预览、窄屏、错误态 | 已审隔离浏览器和设计对照见 `docs/reviews/overseas-light-complete-20261107.md:27,31–35`。本次未重开页面；新包及生产验收未完成。 |
| `DEV-PLAN.md:7`、`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 公开 SVG 换行 | `scripts/release/overseas-light-package.py:30–35,64–71` 对 `assets/` 外的 `.svg` 调用 `package-delivery.py:39–40` 的 CRLF/CR 到 LF 替换，其余字节原样。独立读取上一正式包及 Git 提交，14/14 公共 SVG 归一后与对应 Git 原件的归一字节相同，6/6 哈希 SVG 未改变；含真实内容差异的样例归一后仍不同。 |
| 发布前预检与回退 | `overseas-light-deploy.py:117–126,219–231` 在准备和关入口之前检查目标；旧报告 `docs/reviews/overseas-light-publish-fix-20261107.md:32–36` 的普通文件祖先、有效及失效符号链接问题已由 `overseas-light-deploy.py:96–114` 检出，临时目录及真实 Linux 符号链接结果见下文。**上述两项 HIGH 仍阻断整个发布修复。** |

**Spec 漂移：** 本次相对上一已审业务快照的三个差异均在发布脚本及其测试，未发现新增业务页面、API 或表；不构成全仓漂移审计。

## 本次验证原始输出

1. `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py`，exit 0：

```text
.......                                                                  [100%]
7 passed in 0.75s
```

2. 使用同一虚拟环境 Python 对上述三个文件的原始字节分别执行内置 `compile(..., 'exec')`，exit 0，原始 stdout/stderr 均为空；未生成或修改代码文件。

3. 对上一正式包的公开 SVG、哈希 SVG 及内容差异样例独立调用当前 `asset_bytes`，exit 0：

```text
public_svg_normalized_matches_git: 14 / 14
hashed_svg_unchanged: 6 / 6
actual_content_difference_preserved: True
non_svg_unchanged: True
```

4. 独立临时目录验证普通文件祖先，及本地 Linux 临时目录使用真实符号链接验证先前 MEDIUM；均 exit 0。WSL 启动另外输出本地网络提示：

```text
non_directory_ancestor: Unsafe shared asset directory: samples
broken_symlink: Linked shared asset: samples/icon.svg
same_bytes_symlink: Linked shared asset: samples/icon.svg
linked_ancestor: Unsafe shared asset directory: samples
entry_directory: Unsafe frontend entry: frontend/dist/index.html
```

5. 本机隔离目录、真实前端安装与回退的 `index.html.sku-new` 故障注入，exit 0；事件是测试替代的代理/API 操作，不是生产操作：

```text
preflight: PASSED WITH STALE INDEX TEMP
ROLLBACK_REQUIRES_INSPECTION: C:\Users\82358\AppData\Local\Temp\release-review-3horhc2t\work
deploy_exception: FileExistsError index.html.sku-new
events: ['gate_closed', 'stop', 'api-overlay.json', 'gate_closed']
switch_started: True
backup_complete: True
old_index_unchanged: True
old_api_restored: False
traffic_reopened: False
```

6. 本机 Linux 临时目录、真实前端安装，模拟未关联候选资产的已有目录符号链接；只模拟包验证，exit 0。WSL 启动另有本地网络提示：

```text
outside_mode_before: 0o700
preflight: PASS
frontend_deploy: FRONTEND_0.2.67_INSTALLED
outside_mode_after: 0o755
```

7. `git diff --check`，exit 0，原始 stdout/stderr 均为空。

## 未验证与后续门禁

本候选因 Stage 1 的 HIGH 停止审查，Stage 2 的代码质量、全面安全扫描、测试真实性及邻页视觉未在本次执行。新包、动态资源完整性、隔离安装、实际生产路径、真实流量切换和线上验收均未由本次审查验证，不能宣称已部署。修复后必须重新固定快照并独立两阶段审查，再根据真实部署基线完成后续门禁。
