# Windows graphical upgrade assistant

**0.1.0-alpha.2: 59 offline tests and packaged startup checks passed.** A controlled
packaged-worker backup/recovery/upgrade/reboot workflow passed on one additional
supported unit. See [the hardware report](../assistant-hardware-20261104.md).
It remains an experimental, build-restricted tool.

[Windows x64 download](https://github.com/1977899016-cell/zune30-research/raw/refs/heads/main/downloads/ZZAudio-Zune30-Assistant-v0.1.0-alpha.2-win64.zip) · [中文](../zh-CN/assistant.md)

## Quick start

1. Extract the ZIP and open `ZZAudio-Zune30-Assistant.exe`. Python is not required.
2. Connect only one Zune. Finish any official Zune update/sync, then close that application.
3. Click **检查连接** (Check connection). This is read-only.
4. Review the Alpha acknowledgment to enable eligible write actions.
5. Click **开始 / 继续备份** (Start/resume backup), then follow the prompts.
6. Before the first upgrade, use **恢复原系统 / 首次恢复验证** to enter recovery manually,
   restore the original NK and demonstrate a return to the normal 1.0 interface.
7. Click **选择固件 / 升级**, select your existing supported 3.3 NK/CAB, let the tool
   prepare a private image, then separately confirm installation.

The host needs the existing driver for the old Zune interface. Firmware is not
bundled or downloaded automatically. This tool is limited to the analyzed first-
generation 30G 1.0 (186) TEST build; it does not infer compatibility from TEST text.
It verifies the retrieved NK hash and bootloader code hash before enabling upgrade.

## What backup changes

USB backup temporarily installs an original native helper through `qtk.exe` and
reboots in two stages. **The previous qtk.exe cannot itself be backed up through
this interface before replacement.** The confirmation explains this limitation.

Starting an action temporarily pauses the known, default-installation `ZuneLauncher.exe`
process so device reboots do not automatically open the official application. Closing
the GUI restores its previous state. No startup registry value or service is changed.
**If the Zune main application is already open, finish any sync/update and close it first.**
The assistant never forcibly terminates the main app; follow its busy-connection prompt.

Starting an action temporarily pauses the known, default-installation `ZuneLauncher.exe`
process so device reboots do not automatically open the official application. Closing
the GUI restores its previous state. No startup registry value or service is changed.
**If the Zune main application is already open, finish any sync/update and close it first.**
The assistant never forcibly terminates the main app; follow its busy-connection prompt.
The helper reads source NK/NOR/disk regions and writes only its token-bound owned
carrier. Incomplete or inconsistent backup results block upgrade.

Private files are stored under `%LOCALAPPDATA%\ZZAudio\ZuneAssistant\Backups`.
Use **打开私有备份** to open the folder and make a second private copy elsewhere.
Keep the initial carriers, original NK, NOR, disk prefix, vault and journals.
Never upload that directory or its generated private image.

## Recovery

Keep USB connected and HOLD unlocked. Hold Back, briefly press/release Play and
continue holding Back for about 20 seconds. Release everything at yellow Pyxis
maintenance, then briefly press Back once for USB recovery. Do not choose factory
defaults, format or initialize disk, and do not change SIG.

After reaching the recovery screen, confirm the assistant's recovery dialog. It
restores only this unit's original NK. Recovery staging supports transfer acknowledgment,
not full readback; the journal distinguishes those claims. Observe the real menu too.

If an upgrade black-screens, the same guided recovery is available. Manual button
input is usually still required. The assistant does not promise unattended recovery
from every failure. An uncertain commit cannot be silently repeated.

## Scope

The generated image is stock-3.3-derived with same-unit RAM credential compatibility,
not completely unmodified stock firmware. The tool does not install Chinese/FLAC
adaptations, replace EBoot/Recovery, change SIG, format disks or write a permanent
credential migration. It does not authenticate using a shared device identity.

59 offline tests cover the real state machine and distributed ARM helper execution
against synthetic CE APIs, including owner checks, source instability, corruption,
backup changes, unknown firmware queues and disconnect/no-repeat behavior. Packaged
GUI/assets/COM startup checks passed without opening a device. A controlled physical
worker workflow passed on one supported unit; the launcher guard separately passed
host lifecycle and device-reboot tests. Visual screenshot acceptance remains unverified
and this is not proof of compatibility with every Zune.

See [source](../../app), [research guide](upgrade-1.0-test-to-3.3.md) and the
[evidence summary](../../evidence/assistant-validation.json).
