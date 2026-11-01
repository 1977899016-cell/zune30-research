# 1.0 TEST → 3.3 研究状态 / Upgrade research status

本仓库第一批公开内容聚焦中文显示教程和工具。升级研究与中文显示属于相关但不同的工作。
This initial publication focuses on Chinese text documentation and tooling. Upgrade recovery
and font persistence are related but separate work.

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
