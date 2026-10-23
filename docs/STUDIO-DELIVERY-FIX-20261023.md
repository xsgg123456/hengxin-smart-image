# 海外图片交付修复与发布计划

1. 固定事故证据：首轮原生图生成并公开输出，CLI JSON仅文字导致漏收；次轮引用被历史baseline拒绝。以真实脱敏结构回放，校验原PNG哈希。
2. 原生证据采集：安全读取同会话rollout启动后尾部，识别同成功轮generation与公开image输出匹配；最终显式链接优先，草稿不显示；解析失败明确告知。完成标准为首轮无Markdown仍产生有效图片，跨会话/失败/草稿/损坏均不收。
3. 正常补交：明确引用历史native路径时核验原成功公开展示与字节一致；已入库图片不重复创建。保留普通work与国内协议门禁。完成标准为多轮和存储失败重试回归通过。
4. 历史恢复：仅受限维护入口核验指定成功轮、原事件哈希和文件，排空、台账、锁内幂等发布、审计。原执行时间/次数保持，重复执行无新增。
5. 测试与审查：Windows专项、实际Linux安装包专项与海外相关全回归，类型检查；固定candidateId，独立两阶段审查并登记。
6. 发布：只增量更新实际海外原生worker代码，当前API/前端无逻辑变更则不重启；完整备份源代码、服务配置、数据库与目标原图，暂停认领并排空，创建新目录/安装测试，再切换服务。保持国内、权限、Skill状态、旧文件和模型参数。失败恢复原服务配置并核实再开放。
7. 补回指定原图：任务7895150e-3164-4ffb-9648-579fff452861，会话087137a7-e53f-45f3-b81f-fb20e9f0bb29，补交轮d1853186-95ba-4ea7-a87c-924ed1e45328。PNG SHA256 20c312e85f98c39511dcb9eacc8ad411687e81ad35a67f43b08811087fa30666。正式浏览器预览/下载，归档可选但不代用户归档，二次维护调用证明幂等。恢复接纳后核验Worker实际加载版本与健康。

本次是既有Phase的缺陷修复，无新增页面或数据库设计。DEV-PLAN原阶段不重排；本计划补充该交付链的验证及发布记录。

## 验证与边界

原生双证据要求用于没有Markdown引用的原生图片展示通道，以及历史native图片补交；既有本轮Markdown明确交付继续执行文件/归属/新增门禁（包括work导出的图片）。若取得原生证据，则额外校验与该证据的内容哈希一致。它不改变国内收图协议。

Windows工作台全回归605通过、28项平台/环境跳过；前端vue-tsc和Python编译通过。独立初审发现历史补交未按原最终清单筛选，已修复并补清单内外/草稿正式混合分区测试。最终原生与桥接51通过1跳过，双不同PNG及部分存储失败后补交去重覆盖。原认证测试的会话保护断言已适配合法rollout fixture，18项通过。

Linux安装验证初次挂载整个backend遮住镜像依赖目录，改为仅挂实际安装app代码和独立tests；私有测试bundle权限调整为容器可读但其父目录仍root私有。完整实装代码首次回归1223通过79跳过11失败：其中9项完整成员授权属于今天仅部署于API的代码，原生worker保持既有基线；另外2项是认证测试旧fixture字面断言，已修正原始字节保护断言。正在分别复核原生原基线9项并重跑本次适用回归，不把这些失败冒充通过。

## 发布前证据

- 最终批准快照：`ad0ae03ab93121c235ac5cd119b0e792a338a799ba8b6217ea0fa09b4afaab8c`；独立复审见 `STUDIO-DELIVERY-FINAL-REVIEW-20261023.md`，Stage 1/2 均 PASS，review-status 内容匹配。
- 实装补丁清单 SHA256：`a89ccebf7205aa5f880d996e2cc5c0233bff5d12dccc90bf7f5e046717aea223`。实装目录 `/opt/hengxin-overseas-releases/studio-delivery-20261023/backend`；私有发布证据目录 `/opt/hengxin-releases/studio-delivery-20261023`。
- 原生旧 worker 基线复跑完整成员授权专项同样 9 项失败，确认这部分是 API 单独发布能力，不混入本次 worker 补丁；当前 API 保持独立部署版本。
- 最终测试包已核对服务器文件哈希：认证测试 `040ea41df3eef17272d44dddece938947c20268a8e1fc4f708e7acc6edf07ccc`，桥接测试 `e49651d099d6ded4cabeb78c06515ef71c0cbb8e2619d8bc26222a5572848a4e`。先前上传断线使旧测试仍被执行的那次结果为 1223 通过、79 跳过、2 个旧断言失败，不计为最终通过。
- Linux 发布专项 36 项通过（包含 Windows 跳过的符号链接项）；从目标安装目录对真实事故 rollout 和原 PNG 重放，首轮无 Markdown 收集 1 张、次轮历史补交收集 1 张、已入库重试新增 0 张，均无警告，SHA256 与原图一致。证据 `REAL-REPLAY.json`。
- 正式补收前只读核验：原操作人张帅为 active super_admin，目标任务无待执行作业；补交轮 events.jsonl SHA256 为 `0e3441313f5c9b3707f679f4a916dbacc38daf9be1d7eb4bbf5bd9f52aa326b0`。执行次数 1，原完成时间 `2026-10-23T10:23:16.757534+00:00`。证据 `recovery-preflight.json`。
- 原 PNG 已额外备份为私有发布目录 `original-image.png`，1,707,945 字节，原像素 1108×1419；这是实际模型原图，未按提示中的目标尺寸重采样或重新生成。
- 正式切换首次在暂停前被配置顺序门禁拦截，`phase=prepared`，未修改运行服务。现场存在 `zzzzzzzz-any-file-20261022.conf`（8 个 z），本次覆盖文件改为 `zzzzzzzzz-studio-delivery-20261023.conf`（9 个 z），保留所有原配置；补真实配置名顺序回归后重新固定快照复审。
- 最终 Linux 实装后端适用回归 **1226 passed、79 skipped**，343.44 秒，退出码 0；无失败。运行期两条已有依赖弃用警告保留在 `installed-tests.log`，结果及补丁绑定在 `installed-tests-result.json`。上述 API 独立授权模块的 9 项不计入此范围；本次未更改其运行容器。
- 配置顺序修正后的发布专项：Windows 36 passed、1 skipped；Linux 37 passed，0 skipped。后端六个补丁文件及清单哈希未变化，测试许可仍绑定同一实装补丁。
- 切换已到 `started`，新 worker PID 3128252，实际目录/命令均为目标版本，gate paused=true、active=0。后验检查发现 `systemctl cat` 在 daemon-reload 前使用缓存覆盖列表，保存的 unit-installed 少本次新覆盖段。只读 diff 确认唯一变化就是本次 9z 覆盖文件的六行新增，无其他配置漂移。将配置凭据采集移到 daemon-reload 后，补缓存语义回归；现场只允许在“原凭据=unit-before、新凭据=原内容+本次固定覆盖段”完全匹配时补记凭据，再运行完整 verify，不重启或重做 switch。

## 上线与生产验收完成

- 最终批准代码快照：`ede03b314995060169e2f6ae7a67991e11308983d6476bd2c8b90a03856d6fb4`，两阶段 PASS。相对上次仅调整配置凭据采集时序及专项测试，报告 `STUDIO-DELIVERY-RECEIPT-REVIEW-20261023.md`；Windows 发布专项 37 passed、1 skipped，Linux **38 passed**。最终脚本已同步服务器。
- 现场严格比较原配置与“只追加本次固定覆盖段”完全一致后修正凭据，完整 verify 通过；该过程没有再次重启 worker。审计证据 `unit-receipt-repair.json`，两个中断原因另存 `ATTENTION-before-override-fix.json` / `ATTENTION-before-receipt-fix.json`，未隐藏故障记录。
- 数据库备份 187,348 字节，`pg_restore --list` 验证通过；SHA256 `d6745da5bd67f943012d5abfb9ba2a904b4b9f3b345d8b8bb112283a92326fd1`。保留原 worker 源码、原 unit、依赖与原 PNG 备份，不自动回灌数据库。
- 补收 dry-run 为 eligible，正式执行 succeeded，图片 ID `53404bab-7ee9-51f5-9f0c-5257c08a779b`；第二次执行 already_recovered，图片数仍 1，delivery_error 为 null，执行次数与原完成时间不变。使用原 PNG，无新模型调用。证据 `recovery-dry-run.json` / `recovery-apply.json` / `recovery-idempotence.json`，业务审计 action `studio.image_recovery`。
- Chrome 正式任务页显示该图，完整放大预览通过；点击“下载原图”所得文件 1,707,945 字节，SHA256 与原 PNG 相同。选中后“归档成品（1）”可用，未代用户归档或完成任务。截图：本地 `output/studio-delivery-20261023/production-preview.png` 和 `production-restored.png`；下载文件位于当前用户 Downloads/53404bab-7ee9-51f5-9f0c-5257c08a779b.png。
- 接纳状态已恢复原值，随后完整 verify 再通过，最终 `phase=resumed`、PID 3128252、版本清单 `a89ccebf7205aa5f880d996e2cc5c0233bff5d12dccc90bf7f5e046717aea223`。验证包括实际进程 argv/cwd/解释器、Celery PID 与 5 并发及 overseas.cli 队列、API readiness、安装文件/配置/依赖未漂移，以及其他容器 ID/镜像/启动时间和其他恒鑫服务 PID/cwd 与发布前一致。

验收限于真实事故记录重放、隔离回归及生产图片恢复/读取/下载链路；没有为了验收再次调用模型生成收费图片，也不将平台/环境跳过项表述成通过。

## 第二条历史记录“123”

用户随后报任务 `3082e683-cd4c-45c2-a1bf-ed15f1e7b879` 仍只有文字。只读查明 turn `f149d4be-68a4-4d9a-a248-4a60f2142a05` 于北京时间 19:12:00 完成，早于新 worker 19:52 启动，属于上线前已落库的另一条历史漏收。会话 `c2891728-ada0-4924-b102-7d5f6ee68709` 只有一条业务轮；原生 session `01a16874-7f73-76b1-8f9d-297bbe7e3b1b` 唯一成功轮。实际已上线 collect_delivery 重放收到 1 张、无警告；原 PNG 1,686,221 字节、1108×1419，SHA256 `12df42e3151224f8d81fe7102a16dd357c852025b489ce3b0545acf18b08807b`；events SHA256 `e68bee95ecc5e054631537abc7390555e9376cfc965205f1f402c29d7ac99520`。

维护入口补充无Markdown分支：业务会话必须唯一指定轮，使用空cursor使原生解析必须唯一完成轮且正文一致，再复用正式收图的草稿、哈希、公开呈现与文件门禁。显式链接分支不变，仍两事务台账/审计/幂等。新增10项回归；Windows专项97 passed、1 skipped，Linux实际独立模块安装专项98 passed。维护模块 SHA256 `f75560f9634083a90a2a0cdcc9c523aed8cadbae59d77c58d440e4c3521bc0b3`，独立安装在私有发布目录 maintenance-123/app/overseas/studio/image_recovery.py，不改动运行中 worker 已验证文件清单。

执行顺序：独立复审 → 原图备份与证据预检 → 暂停认领排空 → dry-run/补收/重复幂等验证 → 正式页面预览和下载校验 → 恢复原接纳状态 → 完成原已授权 Git 提交。

本次候选 `6277f3a553dd9f6e4a0b07f8d9020df18b1ab47dc1a735d4a36b368662c54080` 已独立 Stage 1/2 PASS。补收已完成，图片 ID `0cd520c2-90bb-5744-bd47-b1269c939219`，原回复、执行次数 1 和完成时间 `2026-10-23T11:12:00.067679+00:00` 均保留。SSH中途断线后先实查状态再恢复执行；再次调用返回 already_recovered，图片数 1。原 PNG 已备份到 maintenance-123/original.png，恢复及幂等报告同目录。正式 Chrome 预览完整加载，下载文件 1,686,221 字节且 SHA256 与原图一致；选中后归档成品（1）可用，未自动归档。截图 `output/studio-delivery-20261023/production-123-preview.png`、`production-123-restored.png`。接纳状态已恢复 `paused=false, active=0`，维护状态 `phase=resumed`。
