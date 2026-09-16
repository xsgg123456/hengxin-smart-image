# Skill 分组展示独立审查

- candidateId：`d72977c9af60222a295907a95c130640873f2c54e7166263f60c1ab6a2c1b378`
- 前次批准：`932b3519523b274da34fcf121f47a27eac0e69b5610a89608a3df553d6a40277`
- Stage 1：**PASS**；Stage 2：**PASS**。
- 范围：仅 Skill 分组展示，三个文件：
  - `hengxin-smart-image/frontend/src/views/hengxin/admin/skills.vue`
  - `hengxin-smart-image/frontend/src/views/hengxin/admin/skill-groups.ts`
  - `hengxin-smart-image/frontend/tests/skill-groups.test.ts`
- 依据：AGENTS.md、code-review SKILL、Product-Spec.md:447–453、Design-Brief.md:11–15、53、57，以及主 Agent 本次交接约束。
- 顺序：固定快照核对 → Stage 1 逐项需求核对 → Stage 2 质量、测试、只读视觉 → 快照复核。
- 审查开始和测试后两次 review-status 均返回该 candidateId，较前次批准仅上述三个文件改变。未发现 components.d.ts 漂移。未修改实现、批准凭据或 .needs-review；未启动服务、上传、安装、启停、保存绑定、spawn 或 commit。

## Stage 1：Spec Compliance — PASS

以下路径中 S = `hengxin-smart-image/frontend/src/views/hengxin/admin/skills.vue`，G = 同目录 `skill-groups.ts`，T = `hengxin-smart-image/frontend/tests/skill-groups.test.ts`。

| Spec 条目（Product-Spec.md:451） | 结论与证据 |
|---|---|
| 名称与处理类型分组，同 Skill 一行 | 完整实现。G:14–26 使用 mode/name 二元 JSON key 和 Map；S:5、19 渲染组。T:12、24 覆盖合并及跨 mode 分离。独立 CUA 实见 5 个版本归为 4 行。 |
| 版本数量、最近上传版本 | 完整实现。S:19–20；G:16–23 保留输入顺序，以组内首条作为 recent，无 updatedAt 或语义版本排序。后端既有顺序证据：hengxin-smart-image/backend/app/modules/skills/router.py:32、37 的 created_at.desc()，仅只读核对契约。T:13–19 的旧版本 updatedAt 更晚仍不变 recent。 |
| 默认单独显示，无默认不推断 | 完整实现。G:24 仅认 isDefault；S:21 无默认显示“未设为模块默认”。T:18、29 覆盖旧默认及无默认。CUA 壁纸业务 Skill 可用但无默认，三个 local-test 组分别显示 0.0.1 默认。 |
| 展开全部版本，保留原对象与顺序 | 完整实现。G:20、23 直接保留对象；S:10 用 group.versions、row-key=id。T:17–21 验证对象身份、顺序与引用。CUA 展开 ecommerce-wallpaper-swap 实见 1.0.1、1.0.0。 |
| 各版本安装状态、引用、校验记录 | 完整实现。S:11–13、35；CUA 两版本均显示“已被模板或任务引用”、可用及“校验与安装记录”。记录弹窗保留 checksum、node、installedAt、updatedAt、error。 |
| 安装、失败重试、可用、停用操作 | 完整保留。S:14 对 uploaded/failed/disabled/available/installing 分支保留，S:65–69 仍传原版本 id 给既有处理器；CUA 可用两行均有停用入口。本次只读，未触发写操作，不声明重新验证后端安装。 |
| 刷新保留展开 | 完整实现。S:5–6 原生 ElTableColumn expand 与 expand-row-keys；S:52–54 保留独立 expanded，G:17 保证 key 稳定。独立 CUA 点击“刷新版本”，等待按钮恢复可用，仍见“收起版本”、两版本及操作。这里指页面数据刷新，不扩张为整页重载持久化。 |
| 主行更新入口、复用上传、预填类型、所选名称版本与同名提示 | 完整保留。S:22 传 row.recent，S:26–30 展示当前所选版本及包名规则，S:57–61 复用 openUpload；没有另建接口。 |
| 管理员填写新版本，不猜测；每次清空文件、版本及错误 | 完整保留。S:30、59–60：版本清空、file=undefined、递增 fileKey、清空 uploadError；通用入口 S:3 同样调用 openUpload。 |
| 同名包归组，上传后需安装，不改默认/模板/历史引用 | 完整保留。S:28–29 如实说明同名同类型分组、不同名另组、后续安装和手动切换；S:64 只调用既有 uploadSkill。S:25 原样传完整版本数组给 SkillDefaults。G:14–26 无副作用写入。 |
| UI 一致性与引导真实性 | 匹配。S:2–10 复用 hx-page、hx-heading、ElCard、ArtTable；S:23 明确最近上传不代表安装或默认；S:28–29 没有自动迁移或自动猜版本的虚假承诺。Design-Brief.md:13、53。 |

部分实现：无。未实现：无。HIGH：0。Spec 漂移：无；快照差异只有三个展示/测试文件，没有新增数据库、后端、接口或绑定变更。旧 CLI、观测及上传后端不在本报告范围。

## Stage 2：Code Quality — PASS

- 类型与结构：G:3–10 显式 SkillGroup / ManagedSkill 类型，G:14–26 单次遍历 O(n) 分组，不排序、不复制或改写版本对象；S:51–54 将纯分组与展开状态分离。三个文件分别 71、27、32 行，均小于 300 行。新增代码未引入 any。
- 安全：检查三个文件全文并搜索 eval、innerHTML、dangerouslySetInnerHTML、暴露 VITE KEY/SECRET/TOKEN 和常见密钥前缀，无命中。S:19–23、27–29 用 Vue 文本插值，G:17 用 JSON.stringify 生成结构 key；无新执行入口、SQL 拼接或硬编码密钥。该结论仅覆盖本次三个文件。
- 组件契约：S:5–6、10 使用原 ArtTable 默认 slot 与原生展开列；hengxin-smart-image/frontend/src/components/core/tables/art-table/index.vue:7、47 透传 ElTable 属性与默认 slot，无修改组件底座。
- 测试真实性：T:12–22 输入包含“最近上传失败、旧版可用且默认、旧版更新时间更晚”，可证明不按更新时间或可用状态选 recent；T:24–32 覆盖跨 mode、稳定 key、无默认和空数据。71/71 独立复跑成功，原始输出见下。
- 非阻塞测试盲区：T:13 使用 1.0.1/1.0.0，未单独以逆语义版本号输入证明“绝不按 semver”；代码 G:16–23 直接顺序遍历提供静态证据。刷新及展开没有自动化组件测试，本次以独立真实 CUA 操作补验；不把纯函数测试描述成端到端写操作验证。
- 视觉：独立临时 tab 实际打开 localhost:3008/#/management/skills 与邻居 /management/users，对两页 1280×720 渲染截图进行了观察。卡片左边界约 x259、顶边约 y250、白底圆角、标题基线、浅色表头分隔线、蓝色刷新/文本操作匹配。S:3–10 对应邻居 hengxin-smart-image/frontend/src/views/hengxin/admin/users.vue:3–7。分组展开内仍为同样表格和状态标签，无额外样式覆盖。邻居当前呈接口未接入的空表错误态，只用于框架、卡片、表头和按钮视觉基准，未将其当作新缺陷。
- 编译：主 Agent 最终 pnpm build exit 0；独立读取 output/skill-group-build.log，确认 vue-tsc --noEmit && vite build、3312 modules、built in 1m 44s。未重新构建，完整原始日志附后。
- 测试环境说明：reviewer 初次 pnpm exec 因当前工具环境 pnpm 11.19.0 / Node v24.19.0 与 package.json:6–7 指定 10.33.4 / 24.18.1 不符，在执行测试前被引擎检查拒绝；随后直接运行现有 node_modules/tsx/dist/cli.mjs 完成测试，无安装或配置修改。编译结论以主侧最终日志为证，不把这一工具环境差异当产品缺陷。

## 独立测试原始输出

命令：`node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`；exit code：0。

```text
✔ lost archive response replays original snapshot and key, including after auth recovery (2.9434ms)
✔ identity changes isolate snapshots and definitive rejection permits fresh action (0.6212ms)
✔ 预览身份默认运营，四角色拥有稳定独立标识，未知角色不提权 (1.3506ms)
✔ 登录回跳仅允许业务站内路径，拒绝外域、反斜杠、登录循环与非业务地址 (0.5551ms)
✔ 模板分页/筛选/排序，页界互斥且查询不污染存量 (297.6746ms)
✔ 草稿不可生成，类型匹配 Skill、版本冲突及历史快照不被编辑删除覆盖 (261.689ms)
✔ 无 Skill 场景允许草稿但阻止文字默认与模板执行 (45.3527ms)
✔ 上传 MIME/大小/空文件、文件引用及20张边界，文字输出数等于输入 (138.9622ms)
✔ 模拟失败可重试，失败操作没有写入副作用 (235.3658ms)
✔ HTTP 模板查询、创建POST/编辑PUT、Skill目录、文件multipart契约及坏响应 (21.3837ms)
✔ 下载命名去路径与非法字符，替换旧后缀 (1.7646ms)
✔ MIME 与字节匹配，HTML/JSON/空文件不能伪装图片 (1.0039ms)
✔ ZIP 目录、UTF8、存储内容及标准 CRC 正确 (1.6605ms)
✔ 下载保留 bytes、凭据限定同源，错误/超时/整套任一失败拒绝 (38.4723ms)
✔ 仓库示例 SVG 均可下载，整套成功保留实际格式 (14.237ms)
✔ 合法 JPEG 结束标记后的附加字节下载时完整保留 (4.203ms)
✔ 真实下载携带授权、走文件ID和服务端ZIP且保留顺序 (4.0251ms)
✔ 真实下载拒绝授权错误、伪ZIP及数量不完整的套图 (3.0257ms)
✔ current sentinel resolves actual round and historical selection remains isolated (2.7102ms)
✔ DTO validates nested failure, ISO times and numeric fields without coercion (1.0342ms)
✔ historical unavailable executor passes HTTP guard and retains failure without polling (31.9147ms)
✔ authorized HTTP client rejects malformed execution payloads (1.7982ms)
✔ time math handles null, future clock, inactivity threshold and frozen terminal duration (0.5251ms)
✔ all active statuses schedule correctly, all terminal statuses stop in real controller (0.8827ms)
✔ task, round and identity changes invalidate actual pending responses (0.4655ms)
✔ close, logout, mock and dispose clear data, cancel timers and ignore late success/error (0.3977ms)
✔ initial mock mode never fetches; error retry and mismatch are safe (0.3974ms)
✔ 管理权限每次重新判断：主管无维护权限，个人不能读取他人统计，停用立即拒绝 (6.733ms)
✔ 统计跨日、操作者、去重、已结束分母和缺失 usage 保真 (0.5916ms)
✔ Skill 异步安装失败保留旧版，成功才可发布，设置切换同源版本 (16.6412ms)
✔ 空、未知、空闲与请求失败可复现，HTTP 拒绝畸形管理响应 (29.2127ms)
✔ 角色修改通知共享会话；非法日期和安装包拒绝且没有副作用 (0.9502ms)
✔ 配置遵守并发10、超时60秒和图片10MiB边界 (0.5971ms)
✔ 安装故障首次失败后可重试；统计使用实时 attempt getter (2.4961ms)
✔ 返工 HTTP 带稳定幂等键及失败来源，不把请求改成首次生成 (21.411ms)
✔ 双击与关闭重开共享待处理提交，切换任务身份后迟到回执不污染 (3.19ms)
✔ 401重新登录恢复请求；未知期间编辑保留且只能重放原快照 (5.4254ms)
✔ 冲突保留意见；受理后GET失败不再POST，看到结束轮次后显式开启下一轮 (0.5646ms)
✔ 网络丢响应后目标切换不换键，重试来源轮次也被冻结 (0.4807ms)
✔ 四角色可操作他人业务资源，返工统计及删除审计归实际操作者 (916.7132ms)
✔ 配置上传上限影响后续上传，监控使用本轮实际操作者 (136.0417ms)
✔ 配置按返工轮次冻结，新并发设置用于后续执行 (186.6072ms)
✔ 合法60秒超时配置到期停止轮次，保留旧图并计入超时统计 (45.8854ms)
✔ 模拟服务隔离快照与实例，空工作区无种子污染 (24.4227ms)
✔ 提交异步受理保留输入，不匹配模板拒绝；不同任务有独立受理标识 (61.3965ms)
✔ 返工串行、单图版本隔离、归档快照和重复归档幂等 (157.7719ms)
✔ HTTP 真实模式网络断连直接报错，不返回模拟数据 (0.8714ms)
✔ HTTP 拒绝 HTML fallback、无效 JSON、未授权响应 (19.8693ms)
✔ HTTP 写操作正确传输 Cookie、请求体和 202 受理；204 不解析 JSON (0.6371ms)
✔ 合法 JSON 的错误结构被拒绝，不能误受理或导致页面崩溃 (4.091ms)
✔ 同名同类型合并，保留各版本身份与引用，默认可以是旧版本 (1.7141ms)
✔ 同名不同类型分开，组key刷新稳定，无默认不从可用版本推断 (0.3026ms)
✔ 首次401卸载后同用户重新挂载恢复草稿，编辑不能替换待确认原键和原快照 (8.5216ms)
✔ 已受理详情读取失败后重建保留回执；显式另建才发新POST (1.0599ms)
✔ 换用户和入口隔离草稿与请求，旧组件不能重放别人尝试 (1.1204ms)
✔ 未完成请求跨卸载仍互斥，迟到回执只写原用户状态 (1.0022ms)
✔ 响应丢失后重放同键原快照，变更输入保留且不能静默创建第二任务 (26.6787ms)
✔ 202 后详情读取失败仍保留原任务 ID，不再次 POST；重复点击不并行受理 (16.9903ms)
✔ 明确校验拒绝后编辑采用新键；503 不伪成功且不清空表单 (1.0997ms)
✔ 不确定请求重放被401拒绝仍须保留原键，不能因重新认证静默重复创建 (0.4812ms)
✔ 操作资格坏 DTO 拒绝；失败状态不能覆盖服务端禁用，fixture 与轮询来源准确 (17.0347ms)
✔ 模拟同键重放只创建一个任务，同键异内容拒绝且保留返工资格 (57.2383ms)
✔ 首次受理仅有结果槽，完成后才展示可用结果和完整轮次 (102.5378ms)
✔ 单图返工失败保持旧版本、重试恢复原目标，其余槽完全不变 (217.5208ms)
✔ 部分失败保留成功图片但不可归档，首次全失败无虚构结果，重试恢复 (413.495ms)
✔ 归档按版本幂等、后续整套返工不覆盖归档、删除任务保留成品与操作者记录 (307.7144ms)
✔ 删除运行任务不复活；分页/搜索SKU/异常筛选与归档写失败重试 (204.3963ms)
✔ 任务HTTP新接口结构守卫、路径编码及成功读回 (36.4099ms)
✔ 默认绑定在保存时冻结；清除默认不改旧版本，重新保存变草稿并保留图片顺序历史 (80.6088ms)
✔ 专用绑定优先于默认，默认管理拒绝越权和跨类型 (90.3007ms)
✔ 历史与默认HTTP契约编码路径、校验返回数据，错误不能伪装成功 (23.1322ms)
ℹ tests 71
ℹ suites 0
ℹ pass 71
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3176.7744

```

## 最终构建原始输出

来源：`output/skill-group-build.log`；主 Agent 确认该次进程 exit code 0。以下直接附原文件内容。

```text

> hengxin-smart-image-frontend@0.0.0 build D:\solveproblems\SOP\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3312 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                                                         1.33 kB │ gzip:   0.79 kB
dist/assets/login_icon-C4TVlUS8.svg                                                     4.23 kB │ gzip:   1.48 kB
dist/assets/favicon-C1KazUkF.ico                                                        4.29 kB
dist/assets/403-BdWuHcJA.svg                                                            4.61 kB │ gzip:   1.55 kB
dist/assets/yd-BrGqJ6Cs.png                                                             4.63 kB
dist/assets/sd-C0PQtrty.png                                                             4.75 kB
dist/assets/500-C-Ru4KUd.svg                                                            4.93 kB │ gzip:   1.75 kB
dist/assets/404-BzxNMzaO.svg                                                            5.12 kB │ gzip:   1.94 kB
dist/assets/icon4-DoSzj0bv.webp                                                         5.76 kB
dist/assets/icon3-T3qq4dG7.webp                                                         5.87 kB
dist/assets/icon6-WLywVSyq.webp                                                         6.31 kB
dist/assets/icon2-CpZimU24.webp                                                         6.71 kB
dist/assets/img1-D1-edq2V.webp                                                          7.52 kB
dist/assets/icon5-BXFopm_n.webp                                                         7.93 kB
dist/assets/icon7-Bv7tEJJc.webp                                                         8.18 kB
dist/assets/img7-4tHQ8_RR.webp                                                          8.69 kB
dist/assets/img9-C5GNNLTv.webp                                                          9.21 kB
dist/assets/img5-O9OJMad4.webp                                                          9.48 kB
dist/assets/img8-B6h2fA3L.webp                                                          9.58 kB
dist/assets/img4-puXkhAjD.webp                                                          9.83 kB
dist/assets/icon1-DYDLnOGV.webp                                                        10.08 kB
dist/assets/img6-PBedqv72.webp                                                         10.90 kB
dist/assets/draw1-Ce1WF34i.png                                                         11.32 kB
dist/assets/img3-2dukXPv_.webp                                                         12.13 kB
dist/assets/bg-DrCBEYh-.webp                                                           12.35 kB
dist/assets/img2-B4YC9Se8.webp                                                         14.02 kB
dist/assets/lf_icon2-CrdSAdav.webp                                                     25.02 kB
dist/assets/bg_light-WsVMpqKz.webp                                                     67.25 kB
dist/assets/bg_dark-BoZNsetB.webp                                                      70.59 kB
dist/assets/el-tooltip-tn0RQdqM.css                                                     0.00 kB │ gzip:   0.02 kB
dist/assets/tree-wLlS6SDK.css                                                           0.09 kB │ gzip:   0.10 kB
dist/assets/index-DmjyQX8P.css                                                          0.16 kB │ gzip:   0.13 kB
dist/assets/el-space-3oFudasq.css                                                       0.16 kB │ gzip:   0.12 kB
dist/assets/el-overlay-Db7iXMEX.css                                                     0.16 kB │ gzip:   0.14 kB
dist/assets/new-user-1pqc1sqz.css                                                       0.17 kB │ gzip:   0.14 kB
dist/assets/index-Dq1dc_9t.css                                                          0.31 kB │ gzip:   0.17 kB
dist/assets/ExecutionProgress-BYNzuIN8.css                                              0.48 kB │ gzip:   0.25 kB
dist/assets/el-row-C6BJsxyy.css                                                         0.49 kB │ gzip:   0.20 kB
dist/assets/ImageUpload-8OMTgVs_.css                                                    0.65 kB │ gzip:   0.29 kB
dist/assets/index-BGWsF0I2.css                                                          0.74 kB │ gzip:   0.40 kB
dist/assets/index-BSJdEnCC.css                                                          0.74 kB │ gzip:   0.40 kB
dist/assets/index-CpA-Fmic.css                                                          0.81 kB │ gzip:   0.41 kB
dist/assets/index-C0PyNZuq.css                                                          0.82 kB │ gzip:   0.42 kB
dist/assets/el-avatar-BmRr_O8d.css                                                      0.88 kB │ gzip:   0.34 kB
dist/assets/el-text-3XkjT9nK.css                                                        1.05 kB │ gzip:   0.35 kB
dist/assets/index-BF_swEeW.css                                                          1.13 kB │ gzip:   0.41 kB
dist/assets/el-empty-D4ZqTl4F.css                                                       1.20 kB │ gzip:   0.47 kB
dist/assets/index-DSbFsYT8.css                                                          1.26 kB │ gzip:   0.44 kB
dist/assets/el-popover-Cktl5fHm.css                                                     1.35 kB │ gzip:   0.42 kB
dist/assets/index-C7odSoxK.css                                                          1.37 kB │ gzip:   0.43 kB
dist/assets/index-C-X6uWh-.css                                                          1.77 kB │ gzip:   0.64 kB
dist/assets/index-86w9PCiC.css                                                          1.89 kB │ gzip:   0.72 kB
dist/assets/index-B7q-DPlS.css                                                          1.89 kB │ gzip:   0.72 kB
dist/assets/index-CUmp_ij4.css                                                          2.01 kB │ gzip:   0.62 kB
dist/assets/index-DxMe_p9x.css                                                          2.01 kB │ gzip:   0.55 kB
dist/assets/index-CrNpgUmE.css                                                          2.05 kB │ gzip:   0.70 kB
dist/assets/index-DVtb5Tyi.css                                                          2.07 kB │ gzip:   0.63 kB
dist/assets/index-Dc5Ya_H_.css                                                          2.15 kB │ gzip:   0.78 kB
dist/assets/el-progress-Dw9yTa91.css                                                    2.59 kB │ gzip:   0.76 kB
dist/assets/el-timeline-item-BvbJTz1y.css                                               2.60 kB │ gzip:   0.64 kB
dist/assets/el-image-viewer-Dh4MhdCP.css                                                2.62 kB │ gzip:   0.80 kB
dist/assets/index-CDDDnorJ.css                                                          2.65 kB │ gzip:   0.77 kB
dist/assets/index-CFoanJPB.css                                                          3.28 kB │ gzip:   0.88 kB
dist/assets/index-DjllX7qf.css                                                          3.37 kB │ gzip:   1.17 kB
dist/assets/index-CCsB2IfO.css                                                          3.41 kB │ gzip:   0.83 kB
dist/assets/index-o9ObloqJ.css                                                          3.42 kB │ gzip:   0.60 kB
dist/assets/index-DOE9lKFE.css                                                          3.44 kB │ gzip:   1.02 kB
dist/assets/el-drawer-BhCnIJJ3.css                                                      3.51 kB │ gzip:   0.88 kB
dist/assets/el-dialog-DyK7vRzj.css                                                      3.53 kB │ gzip:   0.98 kB
dist/assets/el-switch-B5lTGWdM.css                                                      3.94 kB │ gzip:   0.96 kB
dist/assets/el-input-number-D6iOyBgb.css                                                4.34 kB │ gzip:   0.91 kB
dist/assets/el-collapse-item-D4LG0FJ0.css                                               4.64 kB │ gzip:   0.98 kB
dist/assets/message-CIxGxpAv.css                                                        4.69 kB │ gzip:   1.06 kB
dist/assets/overlay-D80Dkf6C.css                                                        4.89 kB │ gzip:   1.21 kB
dist/assets/el-tree-C2sTlbKd.css                                                        4.91 kB │ gzip:   1.11 kB
dist/assets/el-checkbox-DIj50LEB.css                                                    6.53 kB │ gzip:   1.21 kB
dist/assets/el-pagination-BNQcHhjS.css                                                  6.58 kB │ gzip:   1.17 kB
dist/assets/el-input-tPmZxDKr.css                                                      10.83 kB │ gzip:   1.74 kB
dist/assets/index-BIiiZCBB.css                                                         11.43 kB │ gzip:   2.38 kB
dist/assets/el-upload-q8uObtwj.css                                                     11.46 kB │ gzip:   2.07 kB
dist/assets/index-wywGMzvX.css                                                         14.06 kB │ gzip:   2.53 kB
dist/assets/index-DvSLPTL8.css                                                         15.41 kB │ gzip:   3.54 kB
dist/assets/index-CdYqqRct.css                                                         17.17 kB │ gzip:   2.75 kB
dist/assets/el-table-column-CKoPG0Y8.css                                               18.06 kB │ gzip:   2.87 kB
dist/assets/index-CNLwSxeQ.css                                                         20.10 kB │ gzip:   3.49 kB
dist/assets/button-L2Z7rtlF.css                                                        26.23 kB │ gzip:   3.38 kB
dist/assets/el-date-picker-panel-BhfPqR_w.css                                          28.61 kB │ gzip:   4.15 kB
dist/assets/index-DqbPTe_j.css                                                         30.98 kB │ gzip:   5.09 kB
dist/assets/index-CfPtBhMe.css                                                         36.98 kB │ gzip:   6.70 kB
dist/assets/el-col-DD1Vn-Yu.css                                                        38.68 kB │ gzip:   3.75 kB
dist/assets/tree-select-DiR0CiUQ.css                                                   90.46 kB │ gzip:  12.95 kB
dist/assets/index-CvHOqcf8.css                                                        197.00 kB │ gzip:  32.73 kB
dist/assets/bg_dark-Bvyr6IFB.js                                                         0.06 kB │ gzip:   0.08 kB
dist/assets/emojo-Ben6gd8J.js                                                           0.06 kB │ gzip:   0.08 kB
dist/assets/cloneDeep-BArjK8PO.js                                                       0.09 kB │ gzip:   0.10 kB
dist/assets/validator-CSQLflzg.js                                                       0.09 kB │ gzip:   0.10 kB
dist/assets/AdminPreview-DOH0dp43.js                                                    0.13 kB │ gzip:   0.14 kB
dist/assets/about-project-DdeW2i5X.js                                                   0.13 kB │ gzip:   0.14 kB
dist/assets/dynamic-stats-o_kwtpnm.js                                                   0.13 kB │ gzip:   0.14 kB
dist/assets/WorkspaceStatus-lX_0gbv-.js                                                 0.14 kB │ gzip:   0.14 kB
dist/assets/formEnum-BLgiZVxV.js                                                        0.15 kB │ gzip:   0.15 kB
dist/assets/isArrayLikeObject-COjlxwiT.js                                               0.16 kB │ gzip:   0.15 kB
dist/assets/SkillDefaults-DL7ZvAUO.js                                                   0.16 kB │ gzip:   0.15 kB
dist/assets/img4-C_uoj_3k.js                                                            0.17 kB │ gzip:   0.13 kB
dist/assets/icon4-CA11c3Wn.js                                                           0.17 kB │ gzip:   0.13 kB
dist/assets/todo-list-qPPfAjl5.js                                                       0.19 kB │ gzip:   0.16 kB
dist/assets/transaction-list-Eo-d_y8v.js                                                0.20 kB │ gzip:   0.15 kB
dist/assets/banner-Cr2cpnxz.js                                                          0.22 kB │ gzip:   0.16 kB
dist/assets/index-C8Zxe4C_.js                                                           0.23 kB │ gzip:   0.21 kB
dist/assets/index-C67b_uxx.js                                                           0.23 kB │ gzip:   0.21 kB
dist/assets/index-C_0gl4XU.js                                                           0.23 kB │ gzip:   0.21 kB
dist/assets/index--iLCh3Wy.js                                                           0.23 kB │ gzip:   0.21 kB
dist/assets/recent-transaction-CtxzoK2n.js                                              0.24 kB │ gzip:   0.17 kB
dist/assets/card-list-CQGNPoww.js                                                       0.25 kB │ gzip:   0.18 kB
dist/assets/today-sales-9HdNecXw.js                                                     0.25 kB │ gzip:   0.18 kB
dist/assets/active-user-B2rcIMR-.js                                                     0.26 kB │ gzip:   0.18 kB
dist/assets/total-revenue-FmsjapGF.js                                                   0.26 kB │ gzip:   0.18 kB
dist/assets/hot-commodity-CukdDaYT.js                                                   0.26 kB │ gzip:   0.18 kB
dist/assets/sales-overview-CbfXzq6T.js                                                  0.26 kB │ gzip:   0.18 kB
dist/assets/visitor-insights-T0tlHrAu.js                                                0.26 kB │ gzip:   0.18 kB
dist/assets/target-vs-reality-tKeY1l8o.js                                               0.26 kB │ gzip:   0.18 kB
dist/assets/volume-service-level-9-dUcCKz.js                                            0.27 kB │ gzip:   0.18 kB
dist/assets/customer-satisfaction-5ByT17Gq.js                                           0.27 kB │ gzip:   0.19 kB
dist/assets/clamp-BL5ZBtMQ.js                                                           0.27 kB │ gzip:   0.19 kB
dist/assets/ResultCard-DHbgWUw-.js                                                      0.32 kB │ gzip:   0.21 kB
dist/assets/skills-CrWTpC7H.js                                                          0.34 kB │ gzip:   0.24 kB
dist/assets/useAuth-Ig_5gF2c.js                                                         0.35 kB │ gzip:   0.26 kB
dist/assets/index-1z8Fl4T5.js                                                           0.37 kB │ gzip:   0.29 kB
dist/assets/index-BieujcvK.js                                                           0.42 kB │ gzip:   0.30 kB
dist/assets/cart-conversion-rate-9DknYMpI.js                                            0.43 kB │ gzip:   0.36 kB
dist/assets/role-edit-dialog-WzwtrWq5.js                                                0.44 kB │ gzip:   0.26 kB
dist/assets/role-permission-dialog-fvRVGkAz.js                                          0.44 kB │ gzip:   0.24 kB
dist/assets/user-dialog-DRDuSkoo.js                                                     0.49 kB │ gzip:   0.28 kB
dist/assets/raf-DK6Vs5Ub.js                                                             0.50 kB │ gzip:   0.33 kB
dist/assets/archives-Cwd4sDrm.js                                                        0.55 kB │ gzip:   0.29 kB
dist/assets/top-products-D0Vzh5Uo.js                                                    0.61 kB │ gzip:   0.31 kB
dist/assets/sales-mapping-by-country-CGmirSZm.js                                        0.61 kB │ gzip:   0.46 kB
dist/assets/total-products-DzdP6Lv0.js                                                  0.63 kB │ gzip:   0.45 kB
dist/assets/sales-trend-D6W7IeO7.js                                                     0.64 kB │ gzip:   0.46 kB
dist/assets/hot-products-list-Io_h5pa3.js                                               0.64 kB │ gzip:   0.33 kB
dist/assets/Archive-J0inilKJ.js                                                         0.65 kB │ gzip:   0.32 kB
dist/assets/CreateTask-BiAdsA8b.js                                                      0.66 kB │ gzip:   0.32 kB
dist/assets/role-search-Bfrkk-be.js                                                     0.67 kB │ gzip:   0.34 kB
dist/assets/user-search-B0z6SkPX.js                                                     0.67 kB │ gzip:   0.34 kB
dist/assets/TemplateHistory-C4WhTOin.js                                                 0.68 kB │ gzip:   0.34 kB
dist/assets/useLayoutHeight-CDFuRPOZ.js                                                 0.68 kB │ gzip:   0.43 kB
dist/assets/use-admin-query-ITWrV0vN.js                                                 0.69 kB │ gzip:   0.47 kB
dist/assets/templates-C1oHdEbI.js                                                       0.70 kB │ gzip:   0.30 kB
dist/assets/sales-overview.vue_vue_type_script_setup_true_lang-CFEwjUK3.js              0.71 kB │ gzip:   0.49 kB
dist/assets/total-order-volume-D_74Dfxw.js                                              0.72 kB │ gzip:   0.53 kB
dist/assets/index-BacN1_xA.js                                                           0.73 kB │ gzip:   0.38 kB
dist/assets/total-revenue.vue_vue_type_script_setup_true_lang-B3AEgRhw.js               0.73 kB │ gzip:   0.51 kB
dist/assets/product-sales-BB2ABfnU.js                                                   0.75 kB │ gzip:   0.50 kB
dist/assets/index-vNYOUfNT.js                                                           0.76 kB │ gzip:   0.38 kB
dist/assets/index-CZxTYueA.js                                                           0.76 kB │ gzip:   0.39 kB
dist/assets/sales-growth-Bx0C0QrW.js                                                    0.76 kB │ gzip:   0.51 kB
dist/assets/index-DdAqvMql.js                                                           0.76 kB │ gzip:   0.39 kB
dist/assets/volume-service-level.vue_vue_type_script_setup_true_lang-B1hZcH1K.js        0.76 kB │ gzip:   0.50 kB
dist/assets/customer-satisfaction.vue_vue_type_script_setup_true_lang-BGEbzZVN.js       0.77 kB │ gzip:   0.53 kB
dist/assets/visitor-insights.vue_vue_type_script_setup_true_lang-hCE1ptNk.js            0.78 kB │ gzip:   0.53 kB
dist/assets/TaskDetail-dOcVfBl3.js                                                      0.80 kB │ gzip:   0.37 kB
dist/assets/TemplateEditor-BzJac5Oz.js                                                  0.81 kB │ gzip:   0.36 kB
dist/assets/index-BwickjLI.js                                                           0.81 kB │ gzip:   0.49 kB
dist/assets/index-D7EfpirM.js                                                           0.81 kB │ gzip:   0.49 kB
dist/assets/index-CCVVAu0C.js                                                           0.82 kB │ gzip:   0.49 kB
dist/assets/menu-dialog-CaSyd2Uu.js                                                     0.82 kB │ gzip:   0.39 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-rXWWOQTE.js                       0.87 kB │ gzip:   0.53 kB
dist/assets/recent-transaction.vue_vue_type_script_setup_true_lang-RFxy1dew.js          0.90 kB │ gzip:   0.58 kB
dist/assets/ArtException.vue_vue_type_script_setup_true_lang-DFlxuHre.js                0.91 kB │ gzip:   0.58 kB
dist/assets/transaction-list.vue_vue_type_script_setup_true_lang-DkQ5RWOr.js            1.01 kB │ gzip:   0.60 kB
dist/assets/index-DwKqD8Qo.js                                                           1.02 kB │ gzip:   0.60 kB
dist/assets/Iframe-CXyLA0Pm.js                                                          1.03 kB │ gzip:   0.62 kB
dist/assets/active-user.vue_vue_type_script_setup_true_lang-KHc5CCL_.js                 1.20 kB │ gzip:   0.80 kB
dist/assets/Tasks-_yzTZshX.js                                                           1.25 kB │ gzip:   0.52 kB
dist/assets/annual-sales-BMEZ6T6a.js                                                    1.25 kB │ gzip:   0.68 kB
dist/assets/index-B6y3AxVA.js                                                           1.29 kB │ gzip:   0.60 kB
dist/assets/el-row-Bw4u4pK6.js                                                          1.31 kB │ gzip:   0.73 kB
dist/assets/index-f8vL9ajF.js                                                           1.33 kB │ gzip:   0.58 kB
dist/assets/about-project.vue_vue_type_script_setup_true_lang-DQ3XHSnj.js               1.33 kB │ gzip:   0.92 kB
dist/assets/sales-classification-7NVk0Dc8.js                                            1.34 kB │ gzip:   0.77 kB
dist/assets/Templates-D740LtsD.js                                                       1.35 kB │ gzip:   0.52 kB
dist/assets/index-BA6cNgjq.js                                                           1.36 kB │ gzip:   0.85 kB
dist/assets/todo-list.vue_vue_type_script_setup_true_lang-j1XYli2V.js                   1.37 kB │ gzip:   0.76 kB
dist/assets/index-rpTYdHGs.js                                                           1.40 kB │ gzip:   0.76 kB
dist/assets/banner.vue_vue_type_script_setup_true_lang-e862JvBE.js                      1.42 kB │ gzip:   0.82 kB
dist/assets/index-HiKjhgyK.js                                                           1.43 kB │ gzip:   0.58 kB
dist/assets/index-CpW0rRGy.js                                                           1.43 kB │ gzip:   0.86 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-Cu6C7H7O.js                       1.45 kB │ gzip:   0.75 kB
dist/assets/ArtResultPage.vue_vue_type_script_setup_true_lang-B28N9Obk.js               1.46 kB │ gzip:   0.81 kB
dist/assets/dynamic-stats.vue_vue_type_script_setup_true_lang-DA0QkI6p.js               1.48 kB │ gzip:   0.83 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-Cr-8SN4D.js                       1.53 kB │ gzip:   0.82 kB
dist/assets/target-vs-reality.vue_vue_type_script_setup_true_lang-BFruJMaw.js           1.56 kB │ gzip:   0.86 kB
dist/assets/card-list.vue_vue_type_script_setup_true_lang-BB-nH92I.js                   1.56 kB │ gzip:   0.91 kB
dist/assets/user-search.vue_vue_type_script_setup_true_lang-BcaCziHm.js                 1.61 kB │ gzip:   0.86 kB
dist/assets/hot-commodity.vue_vue_type_script_setup_true_lang-BOFDlbOV.js               1.65 kB │ gzip:   0.89 kB
dist/assets/el-avatar-pcZCxW5y.js                                                       1.66 kB │ gzip:   0.91 kB
dist/assets/top-products.vue_vue_type_script_setup_true_lang-BIp0BoKQ.js                1.69 kB │ gzip:   0.94 kB
dist/assets/index-CqcKC9_d.js                                                           1.74 kB │ gzip:   0.97 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-BmVOstfu.js                       1.75 kB │ gzip:   0.96 kB
dist/assets/index-C1UyU5fL.js                                                           1.77 kB │ gzip:   0.91 kB
dist/assets/role-search.vue_vue_type_script_setup_true_lang-CQEgjE_f.js                 1.78 kB │ gzip:   0.94 kB
dist/assets/el-col-B57KBHu4.js                                                          1.79 kB │ gzip:   0.85 kB
dist/assets/index-BcwJ9yfr.js                                                           1.80 kB │ gzip:   0.99 kB
dist/assets/avatar10-Dom60BwY.js                                                        1.93 kB │ gzip:   1.50 kB
dist/assets/index-D_qj5YQl.js                                                           1.93 kB │ gzip:   1.06 kB
dist/assets/basic-CGfh5koz.js                                                           1.94 kB │ gzip:   1.01 kB
dist/assets/AdminPreview.vue_vue_type_script_setup_true_lang-BMAd2kdd.js                2.04 kB │ gzip:   1.13 kB
dist/assets/index-B-hoez5s.js                                                           2.05 kB │ gzip:   0.75 kB
dist/assets/today-sales.vue_vue_type_script_setup_true_lang-BW8z8n0l.js                 2.13 kB │ gzip:   1.14 kB
dist/assets/index-k2UDgcwr.js                                                           2.19 kB │ gzip:   1.13 kB
dist/assets/el-timeline-item-Cim5hHTr.js                                                2.22 kB │ gzip:   1.00 kB
dist/assets/index-m4FtWELM.js                                                           2.26 kB │ gzip:   1.03 kB
dist/assets/index-DIaSPOpq.js                                                           2.37 kB │ gzip:   0.93 kB
dist/assets/index-Hf4iQ7If.js                                                           2.42 kB │ gzip:   1.32 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-BpGXo0wS.js                       2.43 kB │ gzip:   1.15 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-CIlgo_A_.js                       2.45 kB │ gzip:   1.20 kB
dist/assets/useTableColumns-N-zxb-CN.js                                                 2.46 kB │ gzip:   1.04 kB
dist/assets/el-space-B-zYEaMa.js                                                        2.51 kB │ gzip:   1.18 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-BffmIbeG.js                       2.52 kB │ gzip:   1.25 kB
dist/assets/index-bUSyupCB.js                                                           2.68 kB │ gzip:   0.97 kB
dist/assets/WorkspaceStatus.vue_vue_type_script_setup_true_lang-BnHNAny3.js             2.75 kB │ gzip:   1.38 kB
dist/assets/ResultCard.vue_vue_type_script_setup_true_lang-DUBWNbGJ.js                  2.80 kB │ gzip:   1.50 kB
dist/assets/index-BIxxaZxW.js                                                           2.84 kB │ gzip:   1.30 kB
dist/assets/avatar-pR7-E1hl.js                                                          2.89 kB │ gzip:   2.23 kB
dist/assets/hot-products-list.vue_vue_type_script_setup_true_lang-Br0DTirQ.js           2.92 kB │ gzip:   1.51 kB
dist/assets/SkillDefaults.vue_vue_type_script_setup_true_lang-BZ0aC-Wz.js               2.96 kB │ gzip:   1.51 kB
dist/assets/index-BoH5qAEL.js                                                           3.03 kB │ gzip:   1.57 kB
dist/assets/new-user-DMJQ6oPh.js                                                        3.06 kB │ gzip:   1.50 kB
dist/assets/index.vue_vue_type_script_setup_true_lang--Rum-1o_.js                       3.07 kB │ gzip:   1.31 kB
dist/assets/avatar1-CutlWZf5.js                                                         3.11 kB │ gzip:   2.40 kB
dist/assets/sd-mv97tFD2.js                                                              3.12 kB │ gzip:   2.14 kB
dist/assets/TemplateHistory.vue_vue_type_script_setup_true_lang--5e1OUMh.js             3.13 kB │ gzip:   1.67 kB
dist/assets/role-edit-dialog.vue_vue_type_script_setup_true_lang-DYR-bmN_.js            3.19 kB │ gzip:   1.37 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-C2aia6qq.js                       3.20 kB │ gzip:   1.37 kB
dist/assets/index-Bz9lVeZZ.js                                                           3.22 kB │ gzip:   1.43 kB
dist/assets/index-vtvYJ1Ch.js                                                           3.32 kB │ gzip:   1.58 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-CcntTPrh.js                       3.36 kB │ gzip:   1.58 kB
dist/assets/user-dialog.vue_vue_type_script_setup_true_lang-CK1R66kW.js                 3.39 kB │ gzip:   1.59 kB
dist/assets/el-popover-Bj7IzcDd.js                                                      3.43 kB │ gzip:   1.49 kB
dist/assets/index-B7LX3YKT.js                                                           3.46 kB │ gzip:   1.44 kB
dist/assets/role-permission-dialog.vue_vue_type_script_setup_true_lang-DmMnW8mv.js      3.54 kB │ gzip:   1.72 kB
dist/assets/index-BBDlNWjH.js                                                           3.60 kB │ gzip:   1.19 kB
dist/assets/formData-Cd6BXK-M.js                                                        3.80 kB │ gzip:   1.22 kB
dist/assets/index-Bp_dj5B-.js                                                           4.29 kB │ gzip:   1.84 kB
dist/assets/index-C2uFv4M6.js                                                           4.50 kB │ gzip:   1.52 kB
dist/assets/index-DPp2vI8n.js                                                           4.52 kB │ gzip:   1.82 kB
dist/assets/el-overlay-CbQH9ZzL.js                                                      4.56 kB │ gzip:   1.79 kB
dist/assets/index-BAQaJJxB.js                                                           4.72 kB │ gzip:   2.27 kB
dist/assets/index-Bwl8qeh9.js                                                           4.73 kB │ gzip:   1.98 kB
dist/assets/el-empty-Vn7jcuSf.js                                                        4.78 kB │ gzip:   1.67 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-RP40n1WQ.js                       4.86 kB │ gzip:   1.96 kB
dist/assets/el-collapse-item-Ct4keGoU.js                                                4.87 kB │ gzip:   2.13 kB
dist/assets/index-DT9L8Dqh.js                                                           4.99 kB │ gzip:   1.86 kB
dist/assets/index-DLq-d6cQ.js                                                           4.99 kB │ gzip:   1.98 kB
dist/assets/el-drawer-Bf5E94G1.js                                                       4.99 kB │ gzip:   2.29 kB
dist/assets/monitor-DuVA44JQ.js                                                         5.00 kB │ gzip:   2.32 kB
dist/assets/el-dialog-B2Hb-Qnl.js                                                       5.04 kB │ gzip:   2.19 kB
dist/assets/index-CuGO4UZq.js                                                           5.06 kB │ gzip:   2.46 kB
dist/assets/index-NCxGkpEU.js                                                           5.09 kB │ gzip:   2.61 kB
dist/assets/index-D0OS-AWb.js                                                           5.33 kB │ gzip:   2.49 kB
dist/assets/index-D-f635aO.js                                                           5.33 kB │ gzip:   2.52 kB
dist/assets/download-BCpBmSnK.js                                                        5.39 kB │ gzip:   2.58 kB
dist/assets/tree-CvE2Go6C.js                                                            5.39 kB │ gzip:   2.49 kB
dist/assets/useChart-BbBkzoiO.js                                                        5.97 kB │ gzip:   2.62 kB
dist/assets/index-2E8QDbZx.js                                                           6.17 kB │ gzip:   2.50 kB
dist/assets/index-DtTxxU9O.js                                                           6.18 kB │ gzip:   3.64 kB
dist/assets/index-q9VsByV-.js                                                           6.28 kB │ gzip:   2.61 kB
dist/assets/index-CJeXCSlV.js                                                           6.52 kB │ gzip:   2.94 kB
dist/assets/index-C1Gx8A64.js                                                           6.57 kB │ gzip:   2.81 kB
dist/assets/users-BNiCtFuz.js                                                           6.59 kB │ gzip:   2.96 kB
dist/assets/index.vue_vue_type_script_setup_true_lang-DCVVkjj6.js                       6.68 kB │ gzip:   2.83 kB
dist/assets/Templates.vue_vue_type_script_setup_true_lang-ujG8a5Dp.js                   6.76 kB │ gzip:   3.02 kB
dist/assets/index-ChpsHJTL.js                                                           6.95 kB │ gzip:   2.90 kB
dist/assets/usage-DzyZRcOt.js                                                           6.95 kB │ gzip:   3.04 kB
dist/assets/index-CgDZOtMw.js                                                           6.96 kB │ gzip:   2.82 kB
dist/assets/settings-B0oM9wAf.js                                                        7.02 kB │ gzip:   3.14 kB
dist/assets/index-C801oBuh.js                                                           7.08 kB │ gzip:   2.86 kB
dist/assets/menu-dialog.vue_vue_type_script_setup_true_lang-BilSqDyf.js                 7.27 kB │ gzip:   3.19 kB
dist/assets/index-CQT-sbw1.js                                                           7.34 kB │ gzip:   3.05 kB
dist/assets/TemplateEditor.vue_vue_type_script_setup_true_lang-CYBxUGG4.js              7.37 kB │ gzip:   3.08 kB
dist/assets/index-hUPNTYWy.js                                                           7.43 kB │ gzip:   2.86 kB
dist/assets/index-ja2J0bTd.js                                                           7.57 kB │ gzip:   3.16 kB
dist/assets/Archive.vue_vue_type_script_setup_true_lang-B_wOS0dc.js                     7.83 kB │ gzip:   3.22 kB
dist/assets/index-8mcdscUB.js                                                           7.94 kB │ gzip:   3.27 kB
dist/assets/Tasks.vue_vue_type_script_setup_true_lang-DaEg5fu_.js                       8.04 kB │ gzip:   3.54 kB
dist/assets/avatar6-VNTlcTK9.js                                                         8.15 kB │ gzip:   6.07 kB
dist/assets/ImageUpload-Cl8Rn1nV.js                                                     8.15 kB │ gzip:   3.66 kB
dist/assets/index-BUqv6_h_.js                                                           8.56 kB │ gzip:   3.21 kB
dist/assets/index-2zeBktOK.js                                                           9.17 kB │ gzip:   4.02 kB
dist/assets/index-CNQkK-gD.js                                                           9.82 kB │ gzip:   3.89 kB
dist/assets/index-D_sciAiB.js                                                           9.83 kB │ gzip:   3.42 kB
dist/assets/ExecutionProgress-DEuG5JY5.js                                               9.94 kB │ gzip:   4.41 kB
dist/assets/avatar9-oKrDyQhv.js                                                        11.24 kB │ gzip:   8.45 kB
dist/assets/overlay-CyyiV0zl.js                                                        11.48 kB │ gzip:   4.26 kB
dist/assets/skills-B-lWcMUz.js                                                         11.52 kB │ gzip:   4.49 kB
dist/assets/index-Bqwk2Jyn.js                                                          11.56 kB │ gzip:   4.23 kB
dist/assets/index-Cp2oRs2u.js                                                          11.57 kB │ gzip:   4.47 kB
dist/assets/index-QUyCnjDq.js                                                          11.61 kB │ gzip:   4.43 kB
dist/assets/el-pagination-S0dcxqWN.js                                                  12.02 kB │ gzip:   4.06 kB
dist/assets/search-bar-DtRClSwi.js                                                     12.58 kB │ gzip:   4.66 kB
dist/assets/index-rj9JgQPg.js                                                          12.61 kB │ gzip:   4.95 kB
dist/assets/index-CG8baIwJ.js                                                          13.43 kB │ gzip:   5.17 kB
dist/assets/index-C5eDu2AH.js                                                          13.68 kB │ gzip:   4.92 kB
dist/assets/TaskDetail.vue_vue_type_script_setup_true_lang-LLBbRg96.js                 14.48 kB │ gzip:   5.73 kB
dist/assets/CreateTask.vue_vue_type_script_setup_true_lang-WHEJi_s8.js                 15.05 kB │ gzip:   6.28 kB
dist/assets/index-2NV3AVxG.js                                                          15.48 kB │ gzip:   4.25 kB
dist/assets/index-E5bsQyTE.js                                                          15.53 kB │ gzip:   5.03 kB
dist/assets/useTable-CdiUcVyl.js                                                       16.08 kB │ gzip:   6.95 kB
dist/assets/index-C_XVpnLE.js                                                          16.18 kB │ gzip:   4.73 kB
dist/assets/index-BTvocsvC.js                                                          17.08 kB │ gzip:   5.72 kB
dist/assets/index-oDV7Farv.js                                                          19.53 kB │ gzip:   7.21 kB
dist/assets/index-B1eCC1jM.js                                                          21.37 kB │ gzip:   7.34 kB
dist/assets/index-Dc2g9XSV.js                                                          21.47 kB │ gzip:  12.41 kB
dist/assets/index-BZasWPHm.js                                                          23.93 kB │ gzip:   9.05 kB
dist/assets/index-c8Qa0Trv.js                                                          26.66 kB │ gzip:   9.47 kB
dist/assets/index-Fy0_obXV.js                                                          28.93 kB │ gzip:   9.29 kB
dist/assets/index-BolGTnoW.js                                                          34.40 kB │ gzip:   9.31 kB
dist/assets/vue-draggable-plus-ByXdSFbb.js                                             41.70 kB │ gzip:  14.38 kB
dist/assets/index-BxMync55.js                                                          56.14 kB │ gzip:  19.01 kB
dist/assets/tree-select-vHL9L5Ji.js                                                    70.54 kB │ gzip:  22.92 kB
dist/assets/index-BBpty2Vl.js                                                          74.15 kB │ gzip:  28.66 kB
dist/assets/el-table-column-2VTtIp4j.js                                                74.71 kB │ gzip:  24.82 kB
dist/assets/index-DCCOhQXl.js                                                          96.23 kB │ gzip:  26.85 kB
dist/assets/index-D0VHfiZz.js                                                         284.43 kB │ gzip:  77.35 kB
dist/assets/index-m8tuPCJc.js                                                         420.92 kB │ gzip: 140.91 kB
dist/assets/index-Apms_x2o.js                                                         562.42 kB │ gzip: 191.28 kB
dist/assets/echarts-DSKumXTW.js                                                       748.03 kB │ gzip: 244.46 kB
dist/assets/index.vue_vue_type_style_index_0_lang-7ND_eV4D.js                         813.93 kB │ gzip: 275.57 kB
dist/assets/index-Bm6ngCTf.js                                                       1,609.80 kB │ gzip: 534.26 kB
✓ built in 1m 44s

```
