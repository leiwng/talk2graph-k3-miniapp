# 话图 T2G 小程序头像 — 三工具专属 Prompt 集

> 背景：话图 T2G = 「用自然语言画数学图形」的 K12 教育小程序
> 定位：初中平面几何 / 立体几何 / 统计图表；教育蓝 UI；用户是老师和学生
> 微信头像规格：1:1 方形、建议 144×144 及以上、≤2MB（jpg/png/gif/webp）、小尺寸下主体清晰
> 已用通义万相生成 4 张候选（见同目录 t2g_*.png），下面三套是各工具针对性强项设计的差异化方向

---

## 1. 即梦 AI（字节 · Seedream 5）— 国风教育插画风

即梦的强项：中文语义理解、国风/二次元/插画、中文文字渲染。
方向：**中式教育 + 几何国风**，和通义万相那批做出差异化。

### Prompt A（插画风，带「话图」二字，测试即梦中文渲染）

```
微信小程序头像，1:1 方形，中国风扁平插画，宣纸米白背景，中央一个用毛笔笔触画的几何图形组合：
圆规、三角板、函数抛物线，点缀朱砂红印章式的小圆点，画面左下角竖排小字「话图」二字（书法体），
教育蓝与朱砂红配色，简洁留白，线条圆润可爱，适合小尺寸显示，高清
```

### Prompt B（二次元萌系，无文字纯图形）

```
微信小程序头像，1:1 方形，Q版二次元风格，一个可爱的几何精灵：圆圆的蓝色三角形身体、
戴着小圆眼镜、头顶一支铅笔天线，周围漂浮着圆形、正方体、函数曲线等数学元素，
明亮的糖果色系（教育蓝为主），白色背景，圆润萌系，中心构图，无文字，高清
```

即梦操作：打开即梦 App/网页 → 智能画布 → 粘贴 prompt → 选 1:1 → 生成 4 张挑。

---

## 2. Midjourney V8.1 — 艺术感/质感流

MJ 的强项：艺术审美天花板、painterly 质感、光影氛围。无文字渲染优势，**全部走纯图形**。

### Prompt A（纸雕/丝网印刷质感，辨识度最高）

```
wechat mini-program avatar, 1:1, layered paper-cut style, deep education blue background,
white geometric compositions -- a compass, set square and a rising sine curve forming a
playful face, high contrast, bold clean shapes, tactile paper shadow layers, minimal,
centered, no text --style raw --ar 1:1 --v 8.1
```

### Prompt B（3D 玻璃质感，现代科技感）

```
wechat mini-program avatar, 1:1, glossy 3d glass render, translucent frosted-glass geometric
shapes -- sphere, cube and cylinder floating in soft arrangement, education blue and ice
white palette, soft studio lighting, gentle depth of field, clean gradient background,
centered composition, no text --style raw --ar 1:1 --v 8.1
```

MJ 操作：Discord `/imagine` 粘贴 → `--ar 1:1`（已在 prompt 内）→ 出 4 张，U 放大选中的。

---

## 3. GPT-Image-2（OpenAI）— 文字+图形全能

GPT-Image-2 的强项：**中英文文字渲染精准**、图标式构图。方向：**图标式头像，直接嵌「话图」两个字**，和纯图形方案拉开差距。

### Prompt A（图标式：对话框+画笔+几何，嵌中文品牌字）

```
Square app icon / avatar for a WeChat mini-program called 话图 (means "talk to image"),
a friendly education app that draws math diagrams from natural language.
Design: rounded-square icon, education blue gradient background, centered emblem of a
speech bubble whose tail becomes a pencil, inside the bubble a small triangle and a
rising curve, the two Chinese characters 「话图」 in bold clean white sans-serif at the
bottom, flat modern vector style, generous padding, high contrast, crisp at small sizes,
no other text
```

### Prompt B（单主体：会画画的三角形老师，无字备用）

```
Square app icon, a cute cartoon character: a bright blue triangle with tiny round glasses
holding a pencil, drawing a sine wave behind itself, flat vector illustration, education
theme, white background, bold outlines, minimal, centered, no text, crisp at 144px
```

GPT-Image 操作：ChatGPT 里直接粘贴（GPT-Image-2 支持中文）；或 API `gpt-image-2-medium`。
注意：中文「话图」如出现错字，让它「只保留两个字，重新渲染」，或手动用设计工具叠加文字。

---

## 选型建议

| 方案 | 风格 | 适用场景 |
|---|---|---|
| 通义万相 t2g_badge | 扁平徽章 | 保守稳妥，教育感强 |
| 通义万相 t2g_mascot | 卡通吉祥物 | 萌系吸睛，学生群体友好 |
| 通义万相 t2g_minimal | 极简线条 | 高端简洁 |
| 通义万相 t2g_3d | 3D 玻璃 | 科技感 |
| 即梦 A/B | 国风插画 / Q版 | 差异化国风 |
| MJ A/B | 纸雕 / 玻璃 3D | 质感天花板 |
| GPT-Image A | 图标+中文「话图」 | 品牌字直接进头像 |

微信审核注意：头像不要放二维码/联系方式；最终上传前压到 144×144（本目录已有 1024 原图，用 sips 或微信后台自动压缩均可）。
