# 开机 TEST 字样 / The boot TEST badge

在 2026-11-04 验证机器的启动器备份中，已定位到开机显示的红底白字 TEST：

- 启动器内嵌的 150 × 40、RLE8 BMP，文件偏移 `0x8650`。
- 绘制分支位于 `0x880673A8`，所用构建类型例程在该构建中返回固定值。
- 这不是 3.3 菜单或歌名字体，也没有找到可直接关闭此图的保存配置项。

这些位置仅适用于启动器 SHA-256：

```text
e5077048e6a67c32bb3e948d27b9b643897c487631e0a860c495dd8ee096db7d
```

离线 RSA 核验确认原启动器的镜像签名有效。两个修改对照——更改这张图，或仅跳过其绘制——
都会使原镜像签名失效；位于认证范围之外的时间戳修改作为负对照仍保留签名有效。
因此不能把“已经找到图片”视为“可以安全刷入去标启动器”。

本次没有输出或写入修改后的启动器。现有 USB 恢复流程依赖当前启动器，不能证明启动器被
更早阶段拒绝时仍可恢复。去标需另行验证可信启动及故障恢复方案，不属于当前助手的刷写范围。

On the analyzed bootloader build, TEST is an embedded 150 × 40 RLE8 bitmap, not
a system-language setting. Offline verification found that either changing the
bitmap or skipping its drawing invalidates the existing bootloader image signature.
A timestamp outside the authenticated ranges provided a successful negative control.
No modified bootloader was emitted or flashed. The tested USB recovery path depends
on this bootloader, so recovery from rejection of a patched bootloader is unproven.
The upgrade assistant deliberately does not write bootloaders.
