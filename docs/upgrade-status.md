# 1.0 TEST → 3.3 研究状态 / Upgrade research status

升级研究现已补充详细双语教程、失败原因解析和实际离线构建代码：

- [Windows 图形升级助手（实验 Alpha）](zh-CN/assistant.md) / [English](en/assistant.md)
- [中文新手教程：准备、备份、构建、验收和恢复](zh-CN/upgrade-1.0-test-to-3.3.md)
- [English beginner guide](en/upgrade-1.0-test-to-3.3.md)
- [源码与失败原因解析 / Internals and source map](upgrade-internals.md)
- [脱敏重建验证 / Sanitized reconstruction proof](../evidence/upgrade-reproduction.json)

The public source includes the real ARM RAM-compatibility routine, a local backup
checker and an offline AUTH196 image builder. It reproduces the historical private
image with the same private inputs; it does not contact USB or install firmware.
The separate experimental GUI in `app/` implements restricted USB operations with
same-unit and recovery gates. Its packaged worker passed a controlled workflow on
one additional supported unit; see [the hardware report](assistant-hardware-20261104.md).

## 实际结果 / Observed results

在一台原 1.0 TEST 机器上，曾经直接安装 1.4/3.3 后出现进度条后黑屏或反复重启。
保留原机备份并验证恢复后，研究定位到本机安全数据与不同版本实现之间的兼容问题。
后续已观察到 3.3 正常主菜单、关于中的 3.3 版本、重启后的 3.3 启动，以及桌面 Zune 软件识别。

One former 1.0 TEST unit failed to boot direct 1.4/3.3 images. After backup and recovery work,
the investigation found device-specific credential-format compatibility issues. Later tests
observed a working 3.3 menu, About version, reboot and desktop recognition.

## 必须保留的边界 / Important boundary

当前可工作的研究适配包含本机专属的运行时兼容处理。
不能因此宣称已经发布了适用于所有机器、无需任何修改的微软原版通用升级包。
不修改原版程序且永久完成本机安全数据迁移的最终方案，与这些实验结果不是同一结论。

The working research adaptation includes per-device runtime compatibility handling.
These results are not a released universal, entirely unmodified Microsoft upgrade package.
Finalizing durable credential compatibility with an unmodified image remains a distinct task.

本次不公开个体设备安全区、身份私钥和嵌入这些材料的适配 NK。
Device security areas, private identity keys and credential-bearing images are not part of
this publication. A future generic workflow must use each owner's own local backups.
