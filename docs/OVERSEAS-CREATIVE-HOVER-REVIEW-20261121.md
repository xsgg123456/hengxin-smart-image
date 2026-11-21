# 海外图片工具封面悬停审查

候选快照 `97ffb9089e66f1198ce20e702631b78349c4ae9ca2b8351a00664f9d3737d6e3`。Stage 1 **PASS**，Stage 2 **PASS**。

范围为 Product-Spec.md:1649、Product-Spec-CHANGELOG.md:1129、DEV-PLAN.md:1886 起的本次增量，以及下列四个生产文件和一个浏览器测试。报告中 CreativeTools.vue、motion/ 均相对 `hengxin-smart-image/frontend/src/views/overseas/creative-tools/`，tests/ 相对 `hengxin-smart-image/frontend/`。未跟踪的 preview-creative-workflow/ 作为已确认预览参照。审查针对隔离环境中的海外前端，生产发布和台账核验由发布阶段执行。

## Stage 1　需求与视觉

|需求|结论与证据|
|---|---|
|六卡封面或文字悬停，上移 3 px|完整实现。CreativeTools.vue:92、95、136、141 将列表项悬停和封面指针事件分开。独立运行 tests/creative-tools.browser.mjs:129，六张实卡逐一测得文字和封面位移均为 −3 px，移回标题后原图复位，离卡后为 0 px。|
|爆款复刻、无痕改字推近且灯光稳定|完整实现。CreativeTools.vue:43、46、100、143 直接缩放原图至 1.05 倍，历时 3 秒。tests/creative-tools.browser.mjs:141 检查两张图片的实际缩放，且灯光绘制层数为零。|
|两处黄色风扇消失，真扇继续转|完整实现。motion/removal-frame.ts:39、45、111、115 以相邻天花板纹理覆盖两处黄色影像，保持原图吊扇动画。tests/creative-tools.browser.mjs:79、109 在两个位置采色并验证完成态不回闪，隔 230 ms 采样真实扇叶仍有变化。独立截图见 review-replicate.png。|
|雪地渐白，人物和雪车固定|完整实现。motion/removal-frame.ts:12、18、30 按人物雪车轮廓扣除遮罩。CreativeTools.vue:142 固定画面比例。tests/creative-tools.browser.mjs:79、106、115 对中间态、完成态的主体原图像素及背景纯白逐一断言。独立截图见 review-edit-text.png。|
|木屋背景逐渐变成连续棋盘格，主体固定|完整实现。motion/removal-frame.ts:73、82、91 将现有棋盘延伸到左侧，保留屋顶、路灯与底座。原比例见 CreativeTools.vue:142。tests/creative-tools.browser.mjs:82、96、106、115 对照右侧棋盘不同方格和主体五处像素。独立截图见 review-recolor.png。|
|背景用时 1.75 秒，悬停保持完成态|完整实现。motion/removal-frame.ts:105、118 的进度在 1750 ms 达到 1。motion/CoverMotion.vue:25、30、39 在雪景和木屋完成时停止申请帧，风扇继续转动。tests/creative-tools.browser.mjs:100、112、117 比较中间态、完成态和持续悬停画面。|
|产品换色原动效与八个平台入口|完整实现。CreativeTools.vue:41、48、93 和 motion/scenes.ts:25、34 沿用平台整卡触发和产品换色绘制。tests/creative-tools.browser.mjs:18、51、122、145 核对顺序、14 张原图资源及持续动画。|
|触屏及减少动态效果|完整实现。CreativeTools.vue:71、75、79、136 分别限制指针输入、媒体偏好和 CSS 位移。tests/creative-tools.browser.mjs:161 验证动态开启期间切换减少动态效果及随后逐卡检查。另查 output/overseas-hover-20261121/capture-local.mjs:20 起的触屏上下文逐卡点击断言及 touch.log:1。|

已确认预览的 CatalogPreview.vue:216 与正式 CreativeTools.vue:136 的悬停参数一致。核对预览与正式 removal-frame.ts:12、39、73，三组遮罩轮廓和贴图坐标一致。正式版将原图绘制集中到 motion/CoverMotion.vue:33。CreativeTools.vue:104 沿用工具名称和说明，本次差异覆盖现有卡片的展示与交互，没有新增页面、业务入口、API、数据库或外部资源。

## Stage 2　质量与验证

- 类型与生命周期。CreativeTools.vue:69 使用异步组件，motion/scenes.ts:7 定义场景集合并按图片弱引用缓存预计算绘制器。motion/CoverMotion.vue:15、19、31、42 分别处理组件销毁、解码失败、限帧及原图兜底。四个生产文件分别为 148、53、37、123 行，浏览器测试为 179 行。对五个文件的密钥、危险 DOM 写入、eval、绝对用户目录和 any 类型断言扫描无命中。motion/removal-frame.ts:18、91 的路径均是代码中的固定绘图坐标。
- 测试真实性。独立从隔离地址 `http://127.0.0.1:4231/overseas/` 执行 tests/creative-tools.browser.mjs:11 起的整份浏览器测试，退出码 0，实际读取 CSS 变换、画布和原始照片像素。故障兜底有代码审查证据，未注入图像解码或 Canvas 初始化故障。六张卡片仅检查本次悬停行为，未将其计作六项业务执行测试。
- 视觉比对。独立打开设计任务中心，再通过侧栏进入创作工具集。两页均显示同一应用外壳；创作工具集的平台区与图片区实际测得列间距均为 16 px、圆角 20 px、标题 17 px，对应 CreativeTools.vue:126、128、135。截图位于 output/overseas-hover-20261121/ 下的 review-neighbor.png、review-catalog.png 和三个 review-场景名.png。逐张检查最终画面，雪车人物轮廓完整，木屋路灯及底座保留，天花板两处黄扇均消失。

### 编译及回归原始输出

下列为交接日志原文节选，浏览器末行另经独立运行复现。证据位置均相对 output/overseas-hover-20261121/。

typecheck.log:2

```text
> hengxin-smart-image-frontend@0.2.79 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

browser-build.log:5、100

```text
✓ 4794 modules transformed.
✓ built in 45.45s
```

test.log:675

```text
ℹ tests 616
ℹ suites 0
ℹ pass 616
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 23732.6914
```

browser.log:1、touch.log:1

```text
PASS official navigation, refresh, 14 original covers, responsive rows, eight platform animations, six image-only hover effects, whole-card lift, exit reset and reduced motion
PASS all six on a touch-only device: no hover layer or lift
```
