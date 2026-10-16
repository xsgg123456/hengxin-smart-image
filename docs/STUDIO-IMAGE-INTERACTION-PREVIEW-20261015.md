# 工作台图片交互预览

仅预览授权。基于用户四张截图和正式前端，复用 OverseasShell、正式 studio.css、AnnotationEditor/AnnotationCanvas；独立 preview-studio-images 入口、端口3020、无API代理，浏览器内示例状态，生产代码只读。

1. 页面还原：沿用侧栏、顶栏、任务标题、步骤、工作台、素材栏、输入框及展开方式。完成标准：桌面与展开视图无裁切，示例数据明确。
2. 图片预览：待发/已发/素材/生成组显示完整缩略图；各组独立切换，原图查看器含计数、缩放、关闭。文档继续文件卡。完成标准：混合文档过滤、起始索引正确、关闭不丢草稿。
3. 修改回填：框选与画笔混用、编号意见、撤销删除清空、缩放平移；确认后回填原图/可选标注图和意见，保留已有输入，允许补充/移除/再编辑，发送仅模拟且不出图。完成标准：取消不回填，确认不发送，主动发送后附件在消息区可预览。
4. 验证：独立类型检查与构建、Playwright真实交互和截图；文件上传/拖放/粘贴、分组切换、画布两工具、回填发送、取消、纯文字、移除、窄屏，观察无业务API。独立两阶段审查后交用户试看，不提交部署。

图片采用已有本地灯具示例原文件，不把截图中的低分辨率缩略图冒充原图；本轮样图不代表实际生成结果。

## 本轮验证记录（2026-10-15）
- 独立类型检查：node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-studio-images/tsconfig.json，exit 0。
- 最终独立构建：node node_modules/vite/bin/vite.js build --config preview-studio-images/vite.config.ts --mode demo，4531 modules，built in 20.86s，exit 0；日志 output/studio-image-preview/build.log。
- CUA真实浏览器交互：待发2图、消息3图、素材4图各自切换、初始索引与Esc；原尺寸1250×1600；矩形+画笔2处及编号意见；确认回填保留原文和2附件且不发消息；重开保留2处；取消；补充后主动发送包含4图和全部文字；发送后的标注图可打开4/4预览。
- 本地JPG+TXT混合选择上传及移除；纯文字修改取消不回填、确认仅带原图无标注图；空白意见阻止确认；撤销1→0、删除选中1→0；清空弹出确认，最终确认因浏览器工具超时未作为已验证。
- 窄屏390×844，主Agent IAB实际innerHeight703时确认按钮bottom675.34；reviewer独立实测innerHeight844时bottom816，均完整可见，无水平溢出。最终新增回填区滚到底部由代码复核，尚无新截图断言。
- 浏览器error日志为空。未截获全量网络；无业务API结论限定为隔离配置及源码证据。文件拖放/剪贴板粘贴、大文件边界未做本轮实测，不宣称已验收；仅演示，不代表正式集成质量。
- 截图：output/studio-image-preview/desktop-review.jpg、canvas.png、draft.png、mobile-canvas.png。前三张IAB截图存在设备缩放模糊，desktop-review.jpg为Chrome清晰截图。
- 正式业务src与依赖配置未改，未提交、未部署，正式开发仍待用户看预览后授权。

## 预览追加调整
删除“上传已有标注图”及其点击/拖入/粘贴入口，不保留无意义的直接/上传模式切换。预览专属编辑器仍复用正式AnnotationCanvas、编号意见和原图尺寸导出。验收：入口与上传处理均移除、框选与文字回填不变；不修改国内正式组件。

删除上传模块后的最终验证：vue-tsc exit0；独立构建4534 modules、21.72s、exit0。reviewer独立Chrome验证上传模块/模式切换消失，框选+画笔2处确认回填原图和标注图，另选02纯文字只回填原图，两次均未自动发送且原2附件保留。截图 output/studio-image-preview/desktop-canvas-direct.jpg。

## 画布仅保留标注描述
用户确认删除画布整体补充框，整体要求仅在工作台输入区填写。预览清除旧general并在序列化时强制忽略；无标注允许回填原图，但未提供任何修改意见时不可发送。已有标注仍逐处校验。验证：无整体框/上传框、编号描述正常回填、工作台补充保留、旧general不进入文本、无标注回填不自动发送。

本次仅标注描述调整：vue-tsc --noEmit -p preview-studio-images/tsconfig.json exit0；vite build --config preview-studio-images/vite.config.ts --mode demo exit0（built in42.84s）。独立浏览器已验证无整体框/上传框，无标注仅回填原图并保留原2附件，未填工作台意见时发送禁用、填后启用；空标注描述提示逐处填写。最终完整证据见 docs/STUDIO-IMAGE-NOTES-ONLY-REVIEW-20261015.md。

## 紧凑布局实施计划
1. 缩略图和素材行：消息72px、成品110px、素材48px，保留原图分组查看和素材勾选。
2. 输入区：附件56px，超过3项用查看全部弹窗；标注压成带双缩略图的摘要行，描述弹窗查看，确认后不自动发送。
3. 验收：桌面布局与实际尺寸、附件溢出管理、原图切换、标注回填/描述/再编辑、窄屏无横向溢出；类型检查、独立构建和独立审查。只修改独立预览，未提交部署。

紧凑版实测：vue-tsc 独立检查 exit0；最终 vite 独立构建 exit0，built in21.45s，日志 output/studio-image-preview/build-compact.log。Chrome 桌面原始1920×911实测消息72×72、成品110×110、附件56×56、素材行68px、上传条32px，输入区235.5px。实际操作全选引用5素材→默认3项与查看全部、全部附件弹窗、框选并填写意见、确认回填原图/标注图、查看完整描述、继续在主输入区补充；确认未自动发送。截图 output/studio-image-preview/compact-preview.png。更多附件和标注摘要在宽屏共用一行，待发缩略图文件名移到原图查看器/全部附件弹窗，常态不占第二行。窄屏/独立审核结论另见本轮审查报告。
