# 海外轻量化发布修复独立审查 · 2026-11-07

## 快照和结论

- candidateId：`715cd2380b130add02d766889b04b58238445c770d0cb1457b03f7afd06a04e8`；审查范围为海外轻量化上一候选的业务与 UI 映射、本次三个发布脚本差异、打包身份、资源碰撞预检和回退路径。
- **Stage 1：PASS（下述业务需求及普通文件字节冲突范围）。Stage 2：FAIL（1 项 MEDIUM 失败路径）。** 不得为此候选登记两阶段 PASS；修复后须重新 `review-prepare` 并从 Stage 1 复审。
- 审查期间 `review-status` 的 `currentId` 为本候选、`reviewedId` 为 `e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9`、`approved: false`，差异仅 `scripts/release/overseas-light-deploy.py`、`overseas-light-package.py`、`test_overseas_light_release.py`。HEAD 为 `0b9d68b8f402c3cc341909a6f416ffd1a55c2995`；`git show -s --format='%H %P' 0b9d68b` 显示其父提交为 `b8d0b57e3dcfdcefd8bda400af672efac6b18240`。本报告是 Markdown，不属于代码快照。
- 本次未修改实现、未访问生产、未提交或部署。`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 记载的第一次发布及生产状态是主 Agent 证据，本次没有独立在线核实。

## Stage 1：需求与设计

`review-status` 给出的上一已审快照差异仅限上述三个发布脚本，因此可将此前业务及 UI 的逐条证据映射到本候选；这里没有重新宣称此前未验证的生产行为。

| 条目 | 结论及证据 |
| --- | --- |
| `Product-Spec.md:7` 入口、旧地址、权限 | 匹配；代码和浏览器证据见 `docs/reviews/overseas-light-complete-20261107.md:17`。 |
| `Product-Spec.md:8` 实际发起、幂等、取消/重发和日期 | 匹配已测范围；见此前报告 `:18`。 |
| `Product-Spec.md:9–10` 历史未知、图片、停用人员和保留边界 | 匹配已测范围；见此前报告 `:19`。 |
| `Product-Spec.md:11` 概况、下钻、筛选和详情 | 匹配已测范围；见此前报告 `:20`。 |
| `Product-Spec.md:15–16` 实际归档人、筛选、历史和权限 | 匹配已测范围；见此前报告 `:21–22`。 |
| `Product-Spec.md:20` 实际负责人、改派和范围 | 匹配已测范围；见此前报告 `:23`。 |
| `Product-Spec.md:21` 筛选、20 条分页和返回 | 匹配已测范围；见此前报告 `:24`。 |
| `Product-Spec.md:22` 三类状态、历史状态和删除异常 | 匹配已测范围；见此前报告 `:25`。 |
| `Product-Spec.md:23` 分批归档、显式完成与解冻 | 源码匹配，见此前报告 `:26`；生产未由本次审查操作。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 与确认预览的 UI、窄屏和错误状态 | 继承此前隔离浏览器结果，见此前报告 `:27,31–35`。本次无 UI 源码变化；新包及生产验收尚未执行。 |
| `DEV-PLAN.md:7` 与 `docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 的本次发布修复 | `overseas-light-package.py:30–35,64–71` 只归一 `assets/` 外的 `.svg`，其他资源原样进入包。对上一正式包本地 14 个公共 SVG 逐项验证：归一后等于提交 `0b9d68b` 对应 `frontend/public/` 的归一字节、XML 解析树不变；包中 6 个哈希 SVG 字节均不变。`overseas-light-deploy.py:94–101,104–113,206–218` 分别在 prepare、切换入口前预检同路径普通文件的原始摘要，内容不同则拒绝；实际安装仍有检查 `sku-frontend.py:27–34`。本次临时目录实测普通文件碰撞分别在 prepare 构建和 deploy 关入口前中止。目录和符号链接失败路径另见 Stage 2。 |

**未实现 / 部分实现：** 在上表已测业务和普通文件字节碰撞范围未发现缺项；发布与生产验收未完成。**Spec 漂移：** 本候选相对上一已审快照没有新增业务页面、API 或表；三个改动均属于本次发布修复，不代表全仓漂移审计。

## Stage 2：问题、质量与安全

### MEDIUM · 确定性目标路径冲突未在关入口前拦截

`scripts/release/overseas-light-deploy.py:94–101` 只对完整目标路径调用 `exists()`；其父路径存在且为普通文件时，完整路径不存在而通过预检。`sku-frontend.py:48–54` 随后会创建该父目录并抛错；它在 `overseas-light-deploy.py:218–227` 关闭入口、停止旧 API 和切换候选 API 之后执行。临时目录用真实 `deploy()` 与真实前端安装/回退函数复现：源 `samples/icon.svg`、目标 `samples` 为普通文件，先关入口、停 API、切换候选，才发生 `FileExistsError` 并回退。实测旧 index 和 package 恢复；这不能证明真实生产回退已验证。

本地 Linux 临时目录另证实目标文件是失效符号链接时，同一预检放行，`sku-frontend.py:18–24` 的实际 `atomic_copy` 才报 `Linked static destination`；同内容的有效目标符号链接也被预检接受。当前生产是否存在这类路径，本审查没有访问生产，不能推断。新增测试 `test_overseas_light_release.py:27–36` 只覆盖普通同路径文件相等和字节不等，未覆盖目录层级或符号链接，也未通过 prepare/deploy 验证碰撞发生在入口关闭之前。建议预检目标及各级祖先的类型与符号链接，并对 prepare/deploy 与真实前端安装错误路径增加回归。

### 其他检查

- **绑定已审提交：** `overseas-light-package.py:76–86,90–112` 要求工作区提交干净、审查快照通过、HEAD 包含固定基线，后端从提交读取并复核，前端从相同提交 Git archive 构建（`:38–61`），manifest 记录 commit 和 candidateId 并再次检查。`overseas-light-runtime.py:21–22` 固定旧 API 镜像和 `b8d0b57`；本地 `git merge-base --is-ancestor ... HEAD` 输出 `BASE_ANCESTOR_OK`。后续补丁提交仍须保留该祖先，最终包必须从重新审查并提交的版本构建；运行依赖 `node_modules` 不在快照内。
- **在途与回退：** `skill-reuse-gate.py:68–94` 关闭代理并等待旧 worker 排空；`overseas-light-deploy.py:219–225,233–252` 等待 API 正常停止，失败时恢复旧镜像，未确认停机不重开入口。`test_overseas_light_release.py:74–116` 模拟前端失败和未确认停机；本次亦在临时目录执行真实前端回退。上述不能替代生产在途任务和真实回退验收。
- **质量和安全扫描：** 本次三个文件分别为 123、276、116 行。对它们扫描 `eval(`、`dangerouslySetInnerHTML`、`innerHTML`、`shell=True`、前端密钥变量、常见密钥前缀及 `/Users/`，无匹配；这是限定范围静态扫描，不是全面渗透测试。符号链接路径问题见上文。
- **视觉：** 没有新的 UI 变更；邻页和确认预览此前在同业务快照实际打开的结果见 `docs/reviews/overseas-light-complete-20261107.md:31–35,42`，本次没有重新打开页面。

## 本次验证原始输出

1. `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py`，exit 0：

```text
.....                                                                    [100%]
5 passed in 0.86s
```

2. `hengxin-smart-image/backend/.venv/Scripts/python.exe -m py_compile scripts/release/overseas-light-package.py scripts/release/overseas-light-deploy.py scripts/release/test_overseas_light_release.py`，exit 0，原始 stdout/stderr 均为空。

3. 本地上一正式包内容及独立调用验证，exit 0：

```text
selected_svg_count: 14
converted_matches_committed_and_xml_equivalent: 14
hashed_svg_byte_identical: 6
deploy_conflict_before_gate_and_marker: PASS
prepare_conflict_before_build: PASS
equal_and_new_assets_accepted: PASS
non_directory_ancestor_preflight: MISSED
```

4. 模拟 API / 入口，但真实调用当前 `deploy()` 与前端安装和回退，exit 0：

```text
ROLLBACK_COMPLETE_WORKERS_AND_DATABASE_RETAINED
deterministic_parent_file_failure_after_switch: ['closed', 'stop', 'api-overlay.json', 'closed', 'old-overlay.json', 'opened']
rollback_restored_old_entries: PASS
```

5. 本地 Linux 临时目录符号链接复现，exit 0，以下为测试程序原始输出；WSL 启动还输出了本地网络提示：

```text
broken_symlink_preflight: MISSED
installation_atomic_copy: Linked static destination
existing_same_bytes_symlink_preflight: ALLOWED
```

## 后续门禁与边界

修复失败路径、运行相关回归后重新固定候选并独立审查，不能用本报告登记通过。新提交的最终包、完整资源检查、隔离安装测试、真实切换及正式入口只读验收均尚未由本次审查执行。审查快照、包身份和实际生产基线须在后续各门禁重新核对；本报告不证明生产现状或正式交付完成。
