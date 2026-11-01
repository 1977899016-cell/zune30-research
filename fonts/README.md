# 自备字库 / Bring your own font

本目录不包含字体文件。历史验证字库混合了原生界面字形与中文字形，未在本项目 MIT 许可下重新分发。
No font file is included. The historical merged font is not redistributed under this project's license.

准备有相应使用权的输入字体，并运行：

```powershell
python tools/inspect_font.py local-inputs/MyFont.ttf
```

历史配置需要文件位于 `\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf`，字族为 `Zune UI CJK`。
换字体时要同时核对字族、字号表现、路径、加载器文件大小限制以及原生界面结果。
Different fonts require their own family/path/size and actual-device checks.

韩文需要包含 Hangul 字形的字库；当前历史验证字库的 Hangul 音节映射为 0。
Korean text requires a font with Hangul coverage; the historical verified font has none in
the Hangul syllables range.
