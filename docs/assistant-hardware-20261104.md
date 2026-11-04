# 2026-11-04 升级助手真机验证 / Hardware validation

本次在另一台匹配支持构建的 Zune 30G 上，使用 Windows 打包程序的实际工作进程，
完成了原机备份、恢复接口写回原系统、构建本机镜像、安装 3.3 和重启确认。
这些是界面按钮调用的同一套工作进程；没有据此宣称所有界面点击和窗口布局均已人工验收。

The packaged Windows worker used by the GUI completed a controlled workflow on one
additional supported Zune 30G. This does not establish universal device compatibility
or a complete manual visual review of every GUI interaction.

| 步骤 / Step | 结果 / Observation |
| --- | --- |
| 连接 / Connection | 读到 `01.00.00186.00-02.04`，身份全程一致 / Same device identity throughout |
| 原系统 / Original NK | 10,689,955 bytes；容器校验、BIN 记录和支持摘要检查通过 / Validated against the supported build |
| 原机数据 / Original data | 完整 2 MiB NOR、硬盘前 1 MiB、旧安全数据及关联检查通过 / Full NOR, disk prefix and same-unit vault retained locally |
| 恢复 / Recovery | 人工进入 USB recovery，助手写回本机原 NK；正常接口恢复，用户确认主菜单 / Original NK restored and menu confirmed |
| 构建 / Build | 自备官方 3.3 NK 与本机备份离线生成私有兼容镜像 / Private per-device image built locally |
| 安装 / Install | 正常接口完整回读暂存内容、核对队列、仅提交一次 / Byte-exact staging checks and one commit |
| 启动 / Boot | 程序读到 `03.30.00039.00-00002`，用户确认主菜单 / 3.3 interface and real menu confirmed |
| 官方软件 / Desktop | 用户确认官方 Zune 软件出现设备图标 / Device icon confirmed by user |
| 重启 / Reboot | 用户正常重启后，主菜单和“关于”3.3 均保留；程序随后再次读到 3.3 / User and protocol confirmations after reboot |

## 这轮修复 / Fixes found during the run

1. Windows WPD 的 MTP pass-through 在读取设备信息时也要求读写连接权限。
   原 Alpha 只读打开后收到 Access Denied。修正主机连接权限，同时保留只读操作白名单，
   不允许只读连接上传、删除或提交固件。
2. 设备重启后，官方 Zune 软件可能由 `ZuneLauncher.exe` 自动打开，导致助手回读超时。
   第一轮备份实际上已完成；退出官方软件后，继续同一会话成功取回结果，没有重新提交程序。
3. 新增官方主程序占用检测和明确提示，保留原始提交异常；断线仍不自动重试安装。
4. 新增临时暂停自动启动器：核对同一 Windows 会话和受支持安装路径，只停止
   `ZuneLauncher.exe`，不结束 `Zune.exe`，不修改启动注册项或服务。
   图形界面开始操作时暂停，关闭助手时恢复先前状态。命令行工作进程仅在本任务期间暂停。
   私有记录支持异常退出后的下次恢复，恢复前核对可执行文件摘要。

WPD pass-through now requests the required host access while enforcing the existing
read-only command restrictions. The assistant detects an already running Zune main
application and explains how to release the connection. It preserves commit errors
without retrying an uncertain commit.

The temporary launcher guard was tested on this PC: the known launcher stopped,
the already running main application remained running, and the startup registry
value was unchanged. With the guard held, the user rebooted the device and confirmed
that the official application did not reopen. After release, the launcher process
was restored and the registry value remained byte-for-byte unchanged.

## 仍然保留的限制 / Remaining limits

- 59 项离线回归及打包启动自检通过；真实设备范围仍只限已验证构建和本次机器。
- 完整升级用打包工作进程验收；随后增加的启动器保护单独通过主机生命周期、设备重启
  和最终打包程序读取验证，没有为了这一项再次刷写固件。
- 恢复暂存只有完整传输确认，未声称完整回读；进入恢复模式仍需人工按键。
- 不会强制关闭正在同步或更新的 Zune 主程序。它原本已打开时，须先完成任务并退出。
- 默认安装路径之外的未知启动器不会被终止。启动器恢复失败时保留本地记录并报告。
- 这是基于官方 3.3 的本机 RAM 兼容研究版；不是完全未修改的原版，也不自动加入中文/FLAC。
- 没有写入启动器、SIG、永久安全区或分区。开机 TEST 字样未移除。
- 所有原机备份、身份数据、私有 NK 和原始日志均留在本地，未随本报告发布。

59 offline regressions and packaged startup checks passed. Recovery entry still
requires physical buttons; recovery upload is transfer-acknowledged rather than
fully read back. Existing sync/update tasks are never forcibly terminated. The
generated system remains stock-3.3-derived with per-device RAM compatibility.
No bootloader, SIG, permanent security-region or partition writes were performed.
