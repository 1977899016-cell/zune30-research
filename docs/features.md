# 功能与验证范围 / Features and validation

本页只陈述已有证据的结果。版本号、USB 枚举成功和离线模拟通过都不能替代实际功能验证。
This page separates observed results from intended capabilities. A version string, successful
USB enumeration or an emulator pass is not a substitute for real use.

| 功能 / Feature | 已验证 / Verified | 尚未证明 / Not established |
| --- | --- | --- |
| 中文显示 / Chinese text | 第一台原生音乐中文歌名，真实重启后保留 / Native song text survived reboot on unit A | 全部菜单翻译 / Full menu translation |
| 日语 / Japanese | 历史字库有汉字及假名 cmap 映射 / Han and kana cmap entries exist | 原生 UI 完整日语支持 / Complete native Japanese support |
| 韩语 / Korean | 当前字库检查结果明确 / Font coverage inspected | 韩文音节为 0，不能宣称已支持 / Zero mapped Hangul syllables; not supported |
| 文件传输 / Transfer | Windows 自带 MTP 驱动、Storage/Music、普通复制和完整文件回读 / Inbox MTP driver, Explorer copy and byte-exact readback | 真正 U 盘盘符、另一台全新 Windows 的零安装试验 / USB Mass Storage; a separate clean-PC test |
| FLAC | 第一台原生播放及重启保留；第二台解码器加载与导入回读 / Unit A playback and reboot; unit B decoder load and import readback | 所有文件、位深、采样率及复制工具均兼容 / Universal FLAC or transfer-tool compatibility |
| 24 位 FLAC / 24-bit FLAC | 当前实验解码器使用 16 位 PCM 输出，源文件不因此转换 / Current path outputs 16-bit PCM without converting the stored source | 24 位原样 DAC 输出 / Bit-perfect 24-bit output |
| 封面 / Artwork | 第一台已修复的专辑关联与封面在重启后保留 / Repaired artwork persisted on unit A | 自动后台方案的完整真机验收 / Complete hardware validation of the background auto-art worker |
| 1.0 TEST → 3.3 | 个别真机已启动到 3.3，并恢复桌面软件识别 / Device-specific boot and desktop recognition observed | 所有 TEST 设备均可无条件升级；通用原版一键恢复包 / Universal unmodified one-click recovery |
| WAV、LBA48 / WAV, LBA48 | 不属于本次已验证成果 / Outside the verified scope | 通用 WAV 支持、超过原有容量限制的完整读写 / General WAV and full larger-capacity support |

## 两台测试机 / Two test units

- **A：主要中文与 FLAC 测试机。** 用户确认中文歌名、FLAC 播放及已修复封面在重启后仍正常。
- **B：原 1.0 TEST 测试机。** 已完成特定兼容修复及后续中文/FLAC 适配安装。新适配版的
  启动、解码器加载、Windows Shell 复制、完整回读和 3 秒库时长已确认；最后一次重启后的
  原生中文和声音确认尚未收到。

Unit A establishes the earlier native UI/audio/reboot results. Unit B has a distinct boot and
credential history. Results on A do not certify B or every other Zune 30G.

## 历史验证来源 / Evidence sources

公开的 [验证摘要](../evidence/verified-results.json) 来自本地保留的设备读回报告和用户观察。
原始日志包含本机路径、设备标识和媒体信息，没有整包公开。
The public summary is derived from retained physical readback reports and user observations.
Raw logs, local paths, device identifiers and personal media inventories are not published.
