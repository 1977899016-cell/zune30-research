# Zune 30 Research / Zune 30 研究项目

**ZZ AUDIO · Zune 30G · Windows CE 5 · 研究记录与工具 / Research notes and tools**

让 Zune 30G 在原生音乐界面显示中文，并研究标准 MTP 传歌和原生 FLAC 播放。
长期方向是 CJK 文字显示与个性化；当前已验证的文字功能是中文歌名显示，菜单仍为英文。

Persistent Chinese text in the native Zune 30G music interface, standard MTP music transfers,
and native FLAC playback. CJK text customization is the longer-term goal; Chinese song text
is verified, while the menus remain English.

## 已实现功能 / Results

| 功能 / Feature | 当前结论 / Status |
| --- | --- |
| 重启后中文歌名 / Chinese song text after reboot | 第一台 30G 已经真机确认 / Confirmed on the first test unit |
| Windows 资源管理器传歌 / Explorer music transfers | 标准 MTP，可见 Storage/Music；不是带盘符的 USB 大容量存储 / Standard MTP, not USB Mass Storage |
| 原生 FLAC 播放 / Native FLAC playback | 第一台已确认播放和重启保留 / Playback and persistence confirmed on the first unit |
| 当前批次 FLAC 专辑封面 / Existing FLAC album artwork | 已修复关联并确认重启保留 / Repaired associations and artwork survived reboot |
| 新导入 FLAC 自动补封面 / Automatic artwork for new imports | 后台方案属于实验功能，完整真机验证未完成 / Experimental; full hardware validation pending |
| 第二台机器适配 / Second-unit adaptation | 系统启动、解码器加载、MTP 导入已读回；重启后中文与实际声音确认待完成 / Boot, decoder load and import read back; final visual/audio check pending |
| 日语 / Japanese | 当前字库有假名映射，原生界面尚未完成验证 / Kana coverage exists; native rendering unverified |
| 韩语 / Korean | 当前验证字库没有韩文音节映射，尚未支持 / Not supported by the current verified font |
| 菜单全中文、通用 WAV、LBA48 / Full UI translation, general WAV support, LBA48 | 本版不宣称实现 / Not claimed by this publication |

> 这是研究资料和离线构建工具，不是适用于所有机器的一键刷机包。
> This publication is research documentation and offline tooling, not a universal one-click installer.

## 从这里开始 / Start here

- [中文显示教程（中文）](docs/zh-CN/chinese-text-guide.md)
- [Chinese text guide (English)](docs/en/chinese-text-guide.md)
- [功能范围与验证边界 / Features and validation](docs/features.md)
- [启动机制与注册表 / Startup and registry architecture](docs/architecture.md)
- [文件清单与使用方法 / Files and tools](docs/files.md)
- [1.0 TEST → 3.3 研究状态 / Upgrade research status](docs/upgrade-status.md)
- [脱敏验证摘要 / Sanitized evidence summary](evidence/verified-results.json)

## 本次公开的文件 / Included files

- `artifacts/ZCJKBoot.exe`：本项目生成的原生 ARM CE 字体加载器，2,048 字节。
- `tools/build_font_loader.py`、`tools/ce_pe.py`：加载器源码与离线构建工具。
- `tools/prepare_registry.py`：对自行提取的未压缩 `default.fdf` 生成中文字体链接及启动依赖配置。
- `tools/inspect_font.py`：检查自行准备的字体、字族名称及字符覆盖范围。
- `tests/`：启动依赖与原生 ARM 加载流程的离线回归验证。
- `SHA256SUMS.txt`：上述公开文件的完整性清单。

The loader contains project-generated code and import metadata, not a Microsoft system DLL
or a device credential vault. Building it requires `coredll.dll` extracted locally from the
user's own firmware; that DLL is not included.

## 中文持久化原理 / How persistence works

1. 在持久文件系统保存字库与原生字体加载器。
2. 在系统镜像的默认注册表中配置 `FontLink\SystemLink`。
3. 开机时由 `Init` 启动加载器，在后续服务启动前调用 `AddFontResourceW`。
4. 加载器完成后调用 `SignalStarted(45)`，允许依赖它的服务继续启动。

The persistent image supplies the font-link and startup configuration on each boot.
A native CE executable loads the font before releasing the dependent services. This avoids
relying on temporary XNA application state or unsupported registry flushing.

## 没有随仓库分发的文件 / Not distributed

微软 NK/启动器/系统 DLL、含微软字体字形的合并字库、原机安全区、设备私钥、整机备份、
以及包含个体设备安全数据的适配镜像均未放入本公开包。

Microsoft firmware/system binaries, the historical merged font, device identity material,
private keys, full-device backups and credential-bearing custom images are excluded.
Use your own lawfully obtained inputs and keep all per-device data local.

## 验证方法 / Verification

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

这些检查不会连接 Zune、写入固件或重启设备。离线通过不能替代真机播放、冷重启和恢复验证。
These checks do not contact a Zune or flash firmware. Offline tests do not replace actual
device playback, reboot and recovery validation.

## 许可证与致谢 / License and credits

本仓库项目原创部分采用 [MIT](LICENSE)。第三方依赖保留各自许可；本项目的 MIT 许可不覆盖
微软固件、微软字体、第三方解码器或其他未包含文件。

Original project material is available under the [MIT license](LICENSE). Third-party dependencies
retain their own licenses. This does not relicense Microsoft firmware/fonts or third-party codecs.

感谢 Zune 社区、OpenZDK/OpenZune、字体工具与 FLAC 社区的公开资料和工具。
See [third-party notices](THIRD_PARTY_NOTICES.md).

**记录日期 / Snapshot date: 2026-11-01.**
