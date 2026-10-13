# 海外 Skill 盘点与安装、展示方案

状态：需求对齐与只读核查完成；尚未安装、开发或部署。用户本轮要求先理解两项需求；此前任务删除方案保持待开发，不在本轮实施。

## 盘点依据

仅扫描用户指定的七个目录，根目录为 `C:/Users/82358/Documents/Codex/2026-10-13/bang-w/outputs/SKILLS合集_独立提取/`。以包含 `SKILL.md` 的目录计为一份 Skill，外围安装说明、触发词TXT和参考图片不另计。

共 **14份 Skill 包**、**11个不同的原始name**。14份SKILL.md内容哈希均不同，不能按同名去重成11份。各Skill根目录内共181个文件、111,321,820字节（约106.16 MiB），统计不含外层说明文件。安装需携带Skill目录内的全部配套文件。

| 用户目录 | 数量 | 实际内容 |
| --- | ---: | --- |
| 亚马逊更换产品（颜色）SKILLS | 3 | 主图1600×1600替换、主图1250×1600替换、A+产品替换 |
| Wayfair新品（灯具家居）套图测试SKILLS | 2 | OUTON主图、OUTON主图与A+ |
| 多平台替换产品SKILLS | 1 | 海外多平台图片产品替换 |
| 沃尔玛新品（灯具家居）套图测试SKILLS | 2 | 原版主图、9.27修改版主图 |
| 亚马逊（户外）新品套图SKILLS | 2 | BELEEV主图、BELEEV A+ |
| 亚马逊（家居）新品套图SKILLS | 2 | OUTONLIFE主图、OUTONLIFE A+ |
| 亚马逊灯具品牌套图SKILLS | 2 | OUTON主图、OUTON A+电脑/手机端 |

## 全量清单与建议名称

同名变体分别安装，唯一标识用于CLI，中文名称用于页面及工作台；保留用户源文件，仅在安装副本中同步必要的name及自引用，保持设计规则、尺寸和配套资源不变。下表为待安装映射，不代表已安装。

| 中文显示名 | 源目录（相对上述根目录） | 建议安装标识 |
| --- | --- | --- |
| 亚马逊主图产品替换 · 1600×1600 | 亚马逊更换产品（颜色）SKILLS/主图1600 SKILLS/amazon-main-image-product-swap | amazon-main-image-product-swap-1600 |
| 亚马逊主图产品替换 · 1250×1600 | 亚马逊更换产品（颜色）SKILLS/主图1250 SKILLS/amazon-main-image-product-swap | amazon-main-image-product-swap-1250 |
| 亚马逊 A+ 产品替换 | 亚马逊更换产品（颜色）SKILLS/A+ SKILLS/amazon-aplus-product-swap | amazon-aplus-product-swap |
| OUTON Wayfair 新品主图 | Wayfair新品（灯具家居）套图测试SKILLS/单主图的SKILLS/wayfair-new-product-image-set | wayfair-new-product-image-set-main |
| OUTON Wayfair 新品主图与 A+ | Wayfair新品（灯具家居）套图测试SKILLS/全套图含A+SKILLS/wayfair-new-product-image-set | wayfair-new-product-image-set-main-aplus |
| 海外多平台图片产品替换 | 多平台替换产品SKILLS/overseas-product-image-swap | overseas-product-image-swap |
| 沃尔玛新品主图 · 原版 | 沃尔玛新品（灯具家居）套图测试SKILLS/主图SKILLS/walmart-new-product-image-set | walmart-new-product-image-set-original |
| 沃尔玛新品主图 · 新版（9.27） | 沃尔玛新品（灯具家居）套图测试SKILLS/新版修改过后9.27/walmart-new-product-image-set | walmart-new-product-image-set-revised-0927 |
| BELEEV 亚马逊户外新品主图 | 亚马逊（户外）新品套图SKILLS/主图SKILLS/beleev-amazon-image-set | beleev-amazon-image-set |
| BELEEV 亚马逊户外新品 A+ | 亚马逊（户外）新品套图SKILLS/A+SKILLS/beleev-amazon-aplus | beleev-amazon-aplus |
| OUTONLIFE 亚马逊家居新品主图 | 亚马逊（家居）新品套图SKILLS/主图SKILLS/outonlife-amazon-image-set | outonlife-amazon-image-set |
| OUTONLIFE 亚马逊家居新品 A+ | 亚马逊（家居）新品套图SKILLS/A+SKILLS/amazon-outonlife-new-product-aplus | amazon-outonlife-new-product-aplus |
| OUTON 亚马逊灯具新品主图 | 亚马逊灯具品牌套图SKILLS/主图SKILLS/amazon-new-product-image-set | amazon-new-product-image-set |
| OUTON 亚马逊灯具新品 A+ | 亚马逊灯具品牌套图SKILLS/A+电脑+手机SKILLS/amazon-new-product-aplus | amazon-new-product-aplus |

## 生产只读核查与现有实现

2026-10-13通过已配置SSH连接，只读检查正在运行的海外API容器和海外专属数据库，未写生产数据或调用生成。

- `HX_BUSINESS_CONTEXT`为overseas；`overseas_skills`当前0条。
- 海外配置目录 `/var/lib/hengxin-overseas/skills` 与 `/var/lib/hengxin-overseas/local-skills` 均存在，扫描均无SKILL.md；对应海外独立Docker卷。
- 海外原生worker/outbox服务均active；只读检查未重启或停止服务。
- 现有管理页 `OverseasLiveSkills.vue` 包含添加、ZIP上传、发布版本、历史版本、启停及阶段筛选；这与本次只读目录需求不同。
- 现有工作台从数据库Skill记录获取选项，执行层 `overseas/execution/materials.py` 将每轮冻结的文字及资源写入本轮Skill目录，再由隔离CLI读取。因此，单独把文件复制到服务器某个用户的全局Skill目录，不能证明工作台能够选择和使用。

## 确定的产品范围与实施方向

1. 安装目标是海外生产生图CLI环境，14份全部保留；国内环境、本机Codex个人技能目录及其他服务不属于目标。完整安装SKILL.md、agents、references、assets和scripts等随附内容。
2. 海外专用安装目录是可用Skill的事实来源；数据库可复用为目录索引和历史快照，但不能把仅登记、缺文件或挂载不可读的条目展示为已挂载。目录读取失败与空目录明确区分。
3. 管理页展示中文名称和描述两列；保留轻量搜索、刷新即可。移除添加、上传、编辑、发布、启停、历史版本等写操作与面板，移除工作流阶段、版本、状态和操作列。描述来源于实际Skill元数据，必要时整理为忠实的中文用途说明。
4. AI工作台的Skill选择与管理页复用同一套可用目录。每轮选择后，CLI能读取相应完整Skill及资源；继续保持任务隔离与轮次内容固定，避免安装更新改变正在执行的任务。不要用前端写死名称制造已安装假象。
5. 后续新增或更新由部署维护完成，页面只负责展示。接口相应提供轻量只读元数据，实际安装与校验成功后再同步目录；不向浏览器下发整套指令、私有路径或全部历史文件来展示两列信息。

## 安装前需要处理的实际差异

- 三组重名分别是amazon-main-image-product-swap、wayfair-new-product-image-set、walmart-new-product-image-set；按上表保留所有变体，不用新版覆盖原版。
- 用户已明确沃尔玛两份的区分方式：管理页及工作台选择中分别显示“沃尔玛新品主图 · 原版”和“沃尔玛新品主图 · 新版（9.27）”。新版标识对应源目录“新版修改过后9.27”，两份同时保留，不合并、不覆盖，技能指令内容保持各自版本；本次只记录标识方案，尚未安装或修改界面。
- OUTON亚马逊主图目录含76个文件、约47.01 MiB。旧网页ZIP入口限制20 MiB，不能依赖原网页上传流程承接本次完整部署，也不能通过删参考图来缩小包。
- 沃尔玛9.27修改版只有SKILL.md，没有agents/openai.yaml；可从其name/description和已核实用途生成显示元数据，不因此漏装或套用原版规则。
- 14份目录均未附带字体文件；部署前核对CLI实际运行环境的字体、文档读取和图片校验依赖，缺项明确记录，不能把“文件已安装”当成“品牌字体与真实生成效果已验收”。当前仅做文件与加载路径核查，尚未验收这些能力。

## 后续验收标准

- 14份安装标识唯一、数量与目录逐一对应，资源与源文件清单核对；仅必要命名适配有差异记录，用户源目录不变。
- 管理页只显示实际可用Skill名称和描述；空目录、加载错误有真实反馈；无添加或发布入口。
- 管理页和工作台选项一致，CLI实际隔离环境可读取所选SKILL.md及配套资源；不能只验证宿主机文件存在。
- 旧任务与正在执行任务保持冻结内容；国内数据和Skill不受影响。任务删除只清任务内副本，不清共享安装目录。
- 未执行真实生图时，只报告安装、挂载与选择验证，不宣称成图质量已验证。
