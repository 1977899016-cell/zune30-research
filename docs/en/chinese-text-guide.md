# Persistent Chinese text on the Zune 30G

## Scope

The goal is readable Chinese song text in native Music after a real reboot. This is not a full
menu translation, and the first-generation CE 5 Zune 30G procedure does not apply to Zune HD.

The first test unit passed native visual, playback and reboot checks. The second custom build
has passed boot, decoder-load and transfer readback checks; its final reboot/visual/audio check
is still pending. See [features](../features.md).

This publication contains documentation, the original native font loader and offline tools.
It does **not** contain a universal NK image, automatic flasher, bootloader package or credential
migration bundle. The intermediate registry output must not be renamed to `nk.bin` and flashed.

## 1. Establish recovery first

Identify the actual model, firmware, bootloader and previous modifications. Privately preserve
the unit's system, boot-related data and unique security data, together with sizes and hashes.
Confirm recovery enumeration and the complete same-unit writeback path before changing the image.
Seeing a recovery screen alone is not proof that a full image can be restored.

Never use another unit's security area, full flash or credential-bearing NK as a universal backup.
This project encountered real black-screen and authentication compatibility failures.

## 2. Prepare a font locally

The historical verified setup used:

```text
Device file: \Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf
Font family: Zune UI CJK
Size: 8206424 bytes
```

That merged font combines original interface glyphs and Chinese glyphs and is not distributed
here. Prepare inputs you are entitled to use, then check their family, size, character coverage
and actual device rendering. Changing the font invalidates the previous font-specific result.

```powershell
python -m pip install -r requirements.txt
python tools/inspect_font.py local-inputs/MyFont.ttf
```

Inspect `families`, `bytes`, `sample_coverage` and `coverage`. The historical font contains
20,909 basic Han mappings and kana mappings, but no Hangul syllable mappings. Cmap coverage alone
does not prove native Music rendering or complete Japanese/Korean support.

## 3. Build or inspect the native loader

`artifacts/ZCJKBoot.exe` is the original 2,048-byte ARM CE loader used by the successful approach.
It checks the fixed file path and size, calls `AddFontResourceW`, then releases dependent startup
services with `SignalStarted(45)`. It does not require launching an XNA game.

The included binary accepts only the historical 8,206,424-byte font. This size check is not a
cryptographic font verification. To use another size, extract `coredll.dll` locally from your
own 3.30 firmware and build on the host:

```powershell
python tools/build_font_loader.py --coredll local-inputs/coredll.dll --font-size 8206424 --output generated/ZCJKBoot.exe
```

Replace the size with your actual font size. The tool only creates host files; it does not deploy
them. Do not commit the input system DLL. Newly generated output requires its own validation.

## 4. Configure font linking and startup

The validated dependency relationship is:

```text
Launch20 = device.exe
Launch30 = gwes.exe          Depend30 = 20
Launch45 = \Hard Disk\Fonts\ZCJKBoot.exe
                             Depend45 = 30
Launch60 = services.exe      Depend60 = 20,45
```

Each of these existing UI font names receives a `REG_SZ` value under
`HKLM\Software\Microsoft\FontLink\SystemLink`:

```text
Zegoe UI
Zegoe UI Light
Zegoe UI Semibold
```

The value is `\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf,Zune UI CJK`.
Use your actual font family on the right-hand side. Do not arbitrarily rename the existing UI
font names. The executable and font must exist at the configured device paths.

Extract and decompress your own `default.fdf`, then prepare an offline intermediate:

```powershell
python tools/prepare_registry.py local-inputs/default.fdf generated/default.CJK.fdf --family "Zune UI CJK"
```

The tool preserves unrelated values, rejects a conflicting `Launch45`, and checks the full Init
dependency graph. Its output is an uncompressed registry file, **not installable firmware**.

A real failed build made 45 depend on60 while60 depended on45. A program cannot break that cycle
by calling `SignalStarted` early, because Init has not allowed the program to run in the first place.

## 5. Firmware packaging is a separate boundary

Persistent startup configuration must be present in the boot image. A one-time RAM change or
an unsupported registry flush is insufficient for this approach.

Actual image integration still requires registry compression roundtrips, ROM file-table/pointer
and allocation checks, CE BIN record validation, and acceptance by the exact device's boot chain.
It also requires correct file routing, a complete acknowledged transfer, post-install checks and
a working same-unit rollback. High runtime privileges or a TEST label do not establish these facts.

The public tools intentionally stop before firmware generation, USB writes and reboot. They do
not silently skip the missing boot-policy and ROM-layout work.

## 6. Verify on hardware

Wait for transfers to finish and return to the normal menu. Perform a real reboot without opening
Games, Connect or a font activator. Open native Music and inspect a previously unreadable Chinese
song title. Repeat after another reboot and record the actual menu/rendering result.

For FLAC, use a short self-created audio sample. Check library duration, actual audible playback
and persistence. A launch acknowledgment, isolated glyph test, or reappearing USB device does not
by itself establish native Chinese or audio success. English menus are expected.

## 7. Standard MTP and FLAC import

The Explorer-visible `Storage/Music` path is standard MTP, not a USB Mass Storage drive letter.
File transfer, native library registration, decoding and artwork are separate stages.

Windows Shell copy supplied a correct three-second duration automatically in our device test.
A lower-level WPD test omitted the duration property and created a zero-second entry. These are
different transfer paths; the result is not a universal on-device duration repair claim.

## 8. Public and private material

This repository includes original code, the generated loader, configuration tools, documentation
and sanitized verification summaries. It excludes device identity secrets, private keys,
credential-bearing images, Microsoft firmware/system binaries and the historical merged font.
Keep each device's recovery data local. Do not upload the complete research or NAS archive.
