# 恒鑫智图 · 品牌资源包

2026-09-14：用户确认采用。公司为前海恒鑫，产品名为恒鑫智图，用途副标题为京东业务生图。

[打开资源预览](preview.html) · [完整横版 SVG](logo-horizontal.svg) · [透明横版 PNG](logo-horizontal.png) · [独立图标 SVG](mark.svg) · [应用图标 PNG](app-icon.png)

`approved-concept.png` 是用户认可的原始概念稿。当前资源按其轮廓重新绘制矢量，以均匀实色取代生成稿里的细微渐变，字标减轻字重；SVG 内的中文已转为路径，接收方无需安装字体。它们不是把 PNG 包进 SVG。

| 文件 | 用途 |
| --- | --- |
| logo-horizontal.svg / .png | 完整横版，含“京东业务生图”，用于登录页和介绍资料 |
| logo-horizontal-white.svg / .png | 深色背景的完整横版 |
| logo-compact.svg / .png | 紧凑横版，仅图形和名称 |
| logo-compact-white.svg | 深色背景的紧凑横版 |
| mark.svg / .png | 彩色独立标识 |
| mark-small.svg | 24px 及以下的同轮廓简化版，去除折面 |
| mark-white.svg / .png | 纯白独立标识，用于深色背景 |
| app-icon.svg / .png、app-icon-dark.svg / .png | 512 单位画布、1024px PNG，用于应用入口 |
| favicon.svg / .ico | 浏览器图标；ICO 内含 16/32/48/256px |
| icon-16.png 至 icon-64.png | 常见小尺寸透明图标（含 24/32/48） |

## 使用规范

- 品牌红 `#F1362F`，折面深红 `#D92D27`，像素橙 `#FF9A16`，深色字标 `#20242D`。
- 独立图形四周至少留出图形宽度的 1/8；交付画布自带少量留白，排版时再留安全间距。
- 完整横版建议宽度不低于 240px；再小改用紧凑横版，侧栏折叠和浏览器入口使用独立图标。按等比例缩放，不拉伸、旋转或重新着色。
- 白色/浅色底使用彩色版，深色底使用反白版。应用图标自带底色；其他标识 PNG 为透明背景。
- 正式前端使用共享 ArtLogo、既有系统名称和登录布局。红橙色只属于品牌标识，业务按钮继续沿用蓝色主题。

## 字体与再生成

字形源自 Adobe [Source Han Sans（思源黑体）](https://github.com/adobe-fonts/source-han-sans)，简体中文 Medium，原始字体采用 SIL Open Font License 1.1，许可副本见 `source/FONT-LICENSE.txt`。未在资源包中分发完整字体，SVG 仅包含标识所需字形路径。

需要重建时，从官方仓库 release 分支的 `SubsetOTF/CN/SourceHanSansCN-Medium.otf` 获取原字体，安装 fontTools 和 sharp 后执行：

```text
python source/build_vectors.py /path/to/SourceHanSansCN-Medium.otf
node source/export-assets.cjs /path/to/sharp
```

矢量定义在 `source/build_vectors.py`，位图导出使用 [sharp 的 SVG 输入与缩放](https://sharp.pixelplumbing.com/api-constructor/)。这些工具只用于素材制作，不是前端运行依赖。导出脚本会同步覆盖本资源包及正式前端的对应品牌资产；修改前应保留上一版。
