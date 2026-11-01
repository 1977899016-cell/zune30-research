# 文件与使用方法 / Files and usage

## 公开文件 / Public files

| 路径 / Path | 用途 / Purpose |
| --- | --- |
| `artifacts/ZCJKBoot.exe` | 原创原生 ARM CE 字体加载器；需完整启动配置，不可在 Windows 上运行 / Native CE loader, not a Windows desktop application |
| `tools/build_font_loader.py` | 在电脑构建加载器 / Host-side loader build |
| `tools/ce_pe.py` | 生成 PE 结构，并从用户自备 coredll 导出表读取导入序号 / PE generation and local export-ordinal lookup |
| `tools/prepare_registry.py` | 离线 FDF 修改和启动依赖校验 / Offline FDF modification and dependency checks |
| `tools/inspect_font.py` | 检查字体族及字符映射 / Font metadata and cmap inspection |
| `tests/` | 离线回归验证 / Offline regression tests |
| `tools/upgrade/check_backups.py` | 已有本地备份校验，不是备份提取器 / Check existing backups, not a backup extractor |
| `tools/upgrade/build_upgrade.py` | AUTH196 私有研究镜像离线重建 / Offline private AUTH196 reconstruction |
| `tools/upgrade/runtime.py`、`rewrap_runtime.asm` | 实际 ARM 兼容逻辑，不含原机身份数据 / Actual native routine, no device identity bytes |
| `tools/upgrade/ce_bin.py`、`ce_lzx.py` | 容器、布局及压缩回读检查 / Container and compression checks |
| `evidence/verified-results.json` | 已验证功能与限制的脱敏摘要 / Sanitized evidence and limitations |
| `SHA256SUMS.txt` | 文件完整性清单 / Integrity manifest |

## 安装 Python 依赖 / Python dependencies

```powershell
python -m pip install -r requirements.txt
```

测试使用 `requirements-test.txt`。工具在 Windows 主机上整理，测试不调用 USB。
Use `requirements-test.txt` for offline tests. No test contacts a device.

## 输入输出位置 / Input and output locations

把自己的固件提取文件放入 `local-inputs/`，生成结果放入 `generated/`。这两个目录被 Git 忽略。
不要把整个原始工程复制到仓库，再试图只靠 `.gitignore` 掩盖秘密文件。

Keep private inputs under `local-inputs/` and generated artifacts under `generated/`.
Both are ignored by Git. The browser upload screen can still upload manually selected files;
ignore rules are not an upload filter or a secret scanner.

## 预编译加载器 / Included loader binary

```text
Name: ZCJKBoot.exe
Architecture: ARM / Windows CE
Bytes: 2048
SHA256: dd2c0bf0fad44cc24a058820395b51b960a39fd662364654992144ef92df982d
Font path: \Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf
Required font bytes: 8206424
```

该二进制与历史成功方案的加载器逐字节一致。它没有设备密钥、USB 操作、系统镜像写入或重启命令。
字体缺失时进行有界重试，最终仍通知 Init 继续启动。

The binary is byte-identical to the original successful loader. It contains no device keys,
USB operations, firmware writes or reboot command. Missing-font retries are bounded; the
loader signals Init even if it cannot load the font.

## 不包含的安装阶段 / Installation stages not included

本版没有 Microsoft NK、默认注册表原件、coredll、合并字库、FLAC 第三方 DLL、
TEST 启动器、永久安全区写入程序或通用 USB 备份/刷写器。

No Microsoft NK, source FDF, coredll, merged font, third-party decoder DLL, TEST bootloader,
persistent credential writer or universal USB backup/flasher is included. The upgrade
folder now includes the actual RAM-only compatibility routine and a version-pinned
offline image builder. Read the full guide before treating an output as device-ready.
