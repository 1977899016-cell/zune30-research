# Zune 30G: understanding the 1.0 TEST to 3.3 upgrade

[中文详细教程](../zh-CN/upgrade-1.0-test-to-3.3.md) · [Technical explanation](../upgrade-internals.md) · [Home](../../README.md)

## What was actually achieved?

One former `1.0 (186) TEST` Zune 30G booted into a working 3.3 menu. The user
confirmed the version in About and, in that phase, another successful reboot.
Later compatibility work restored the device icon in the official PC Zune software.
Chinese/FLAC adaptation continued on that same unit afterward.

**The AUTH196 image that restored desktop recognition is a customized research
image derived from official 3.3. It is not an entirely unmodified stock image.**
It adapts this device's old credential data during boot in RAM. A complete permanent
migration of all credential fields has not been finalized. The earlier reboot check
and the later desktop-recognition check belong to different experimental stages.

This publication contains the actual ARM compatibility routine, an offline image
builder, a local backup checker and regression tests. With the maintainer's exact
private inputs and journal token, the public builder reproduced the historical
AUTH196 image byte for byte. No credential-bearing image is distributed.

**There is no universal USB backup, flashing or recovery application in this release.**
Generating a file does not install it. Another device's image must not be reused.

## 1. Terms and prerequisites

| Term | Meaning |
| --- | --- |
| NK / system image | The CE container holding OS programs, drivers and default registry. |
| EBoot / bootloader | Runs before NK and controls boot sources and image acceptance. |
| NOR | Flash containing boot code, configuration and security-related regions. |
| Vault | Device identity, certificate and encrypted credential data; use your own unit's backup. |
| RAM adaptation | Converts data for the current boot; repeated automatically by the customized image. |
| SHA-256 | A file-integrity fingerprint, not proof that a file belongs to your device. |
| MTP | Explorer portable-device folders; not a USB Mass Storage drive letter. |

This workflow targets the first-generation 30G and the analyzed TEST configuration.
It does not cover HD, 80G, 120G or flash models. TEST text alone does not identify
the exact firmware, boot policy or credential state.

Prepare Windows, a reliable cable, sufficient device power, Python and this repository.
Obtain your own supported 3.30.39 source NK and **your own device backups**. Confirm
the recovery entry, host connection and actual writeback of a known working image
before attempting an installation. Seeing a recovery screen alone is insufficient.

## 2. Check existing backups

The research backup set includes:

```text
local-inputs/
  nk.original.bin          previously working system
  nor.original.bin         complete 2 MiB original NOR for this layout
  disk-prefix.original.bin at least 1 MiB, aligned to 512-byte sectors
  vault.legacy.bin         original NOR bytes 0x70000 through 0x7FFFF
```

These files must already have been read from the device. The following tool checks
local files; it does not create backups. Explorer's Music folder does not expose
these raw regions. Keep a second private copy on another disk.

Open the extracted folder containing `README.md` and `tools`. Type `powershell`
in Explorer's address bar and press Enter to open a terminal in that folder. Run:

```powershell
python tools/upgrade/check_backups.py --original-nk "local-inputs/nk.original.bin" --nor "local-inputs/nor.original.bin" --disk-prefix "local-inputs/disk-prefix.original.bin" --legacy-vault "local-inputs/vault.legacy.bin" --output "generated/backup-inventory.PRIVATE.json"
```

Success includes `nk_record_checksums_valid: true` and
`vault_matches_original_nor_region: true`. It also correctly reports that it has
not created the backup or tested physical recovery. Independently establish which
unit the files came from; byte agreement cannot establish that provenance.

## 3. Why a direct upgrade failed

Boot-time vault integrity and post-boot credential use were separate problems.
Adapting only the 32-byte header can satisfy the outer integrity check while the
encrypted body still fails under the new decoding path. Consequently, a working
3.3 menu does not establish working PC authentication.

The working research adaptation reads the owner's pinned legacy encrypted data
from a private ROM file, preserves the incoming RAM buffer, converts 38 analyzed
fields using the old and new paths, verifies each roundtrip, rebuilds the header
integrity data and calls the existing 3.3 validator. Handled failures restore the
incoming RAM buffer. Persistent vault writes are disabled in this diagnostic image.

See [the code explanation](../upgrade-internals.md) for the field map, image changes
and distinctions between software models and physical observations.

## 4. Build locally

Install the pinned Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Windows `makecab.exe` encodes independent LZX blocks. An external
[`wincedecompr.py`](https://github.com/KodaSec/wince-decompr) checks decompression.
Download that repository using **Code → Download ZIP**, extract it and place its
`wincedecompr.py` in `local-inputs/ce-decoder/`. Keep its upstream license with your
local copy. The verified script SHA-256 is
`42693ba5e756f664d2405bdaa2f6f9bc5671b5956439aeed581c8e7e89f2e72d`.
The loader also accepts a parent directory containing `wince_decompr/wincedecompr.py`.

Place your stock source as `local-inputs/nk.stock33.bin`. Its required SHA-256 is:

```text
81951eaf10feb868e2f2818aea64d15f0b2b6484458454c2655efd0668c13a11
```

Check both inputs:

```powershell
Get-FileHash -Algorithm SHA256 "local-inputs/nk.stock33.bin"
Get-FileHash -Algorithm SHA256 "local-inputs/vault.legacy.bin"
```

The stock hash must match the fixed supported version. The vault hash must match
your own original inventory. Replace `YOUR_OWN_VAULT_SHA256` with that 64-digit hash:

```powershell
python tools/upgrade/build_upgrade.py --stock-nk "local-inputs/nk.stock33.bin" --legacy-vault "local-inputs/vault.legacy.bin" --vault-sha256 "YOUR_OWN_VAULT_SHA256" --decompressor-dir "local-inputs/ce-decoder" --output-dir "generated/auth196-local"
```

The output folder must not already exist. Output files are:

- `nk.AUTH196.PRIVATE.bin`: per-device research NK containing encrypted identity material.
- `runtime.PRIVATE.bin`: assembled ARM compatibility routine.
- `build.PRIVATE.json`: local build checks and hashes.

Expected report fields include `rom_legacy_file_roundtrip_verified: true`,
`runtime_module_overlap: false`, `persistent_security_write_implemented: false`,
`device_operations_performed: false` and `new_device_hardware_boot_verified: false`.
The last two mean exactly that: no installation or new-unit boot test took place.
Random journal tokens normally cause different output hashes between builds.

| Error | Action |
| --- | --- |
| Stock hash mismatch | Obtain the supported input; do not change the hardcoded hash to force a build. |
| Vault size/hash mismatch | Check your paths and original backup inventory. |
| Missing decoder | Point the option at the directory containing the actual Python module. |
| MakeCAB failure | Check its path, the temporary folder and disk space. |
| Existing output directory | Select a fresh output folder. |
| Unexpected layout or overlap | Investigate offline; do not install the result. |

## 5. Installation boundary and historical procedure

There is currently no general Windows USB transport backend/installer here.
If you do not have a unit-reviewed installer and tested recovery, stop after
offline preparation. Do not drag an NK into Music, rename an intermediate file,
or assume Zune software will accept the private image as an official update.

The historical installer checked the same-unit identity, original backups and
empty firmware queue; staged `nk.bin` using special format `0xB802`; performed
complete partial-object readback on the normal 1.0 interface; checked the hash
and exact queue; then sent **one** commit and observed reboot. Recovery-mode
staging offered different verification capabilities and did not provide full
readback. An acknowledged upload is not a byte-exact readback claim.

The [USB state-machine notes](../upgrade-internals.md#usb-transfer-and-commit)
document this sequence for implementers. None of this publication's tools contact
USB, install firmware or restart a device.

## 6. Verify actual results

Record the exact image used for each test. Verify the normal menu, About version,
another physical reboot, official PC device icon, and the required content/sync
functions separately. A firmware string, protocol challenge or menu alone does not
prove every other function or long-term stability.

The public test certificate previously returned `0x2020`; same-unit identity later
passed the real challenge. A refusal alone cannot localize the fault to damaged
RSA data or failed boot. Avoid simultaneously owning USB from an installer and
the official desktop application.

## 7. Recovery and troubleshooting

The following worked with the TEST bootloader used in this project; it is not a
guarantee for every unit. Keep power connected and HOLD unlocked:

1. Hold Back, briefly press and release Play, and keep Back held for about 20 seconds.
2. Release all buttons when yellow **Pyxis maintenance** appears.
3. Press Back briefly once to enter the PC/firmware recovery screen.
4. Use the already-reviewed recovery program to restore this unit's own working NK.
5. Confirm the normal menu and the restored identity/version/hash before another trial.

Back+Up reset, followed by releasing Up while retaining Back, was another working
entry on the tested unit. If neither route works, stop changing settings blindly.
Do not select factory defaults, format data partition or initialize disk: they are
different operations. Saving SIG Disabled also caused failures during this research;
the published build does not require changing EBoot, SIG or partitions.

Wait for any active desktop update/sync to finish before closing the application
to release USB. This project used local-image recovery; a recovery picture does
not itself prove an online server is required. A universal recovery writer is not
included in this release.

## 8. Sharing and remaining work

Share source, docs and sanitized evidence. Keep backups, credentials, generated
images and private reports local. Encrypted embedded credentials still make an NK
device-specific. Browser uploads can bypass `.gitignore`.

Remaining work includes a complete durable migration compatible with an unmodified
stock image, a general same-unit backup/installer/recovery tool, and broader physical
validation. The published builder reproduces the actual research path; it does not
claim those unfinished stages are already solved.
