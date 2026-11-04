# ZZ AUDIO Zune 30 Upgrade Assistant

**0.1.0-alpha.2, Windows x64. A controlled packaged-worker workflow passed on one additional supported unit.**
See [the hardware report](../docs/assistant-hardware-20261104.md).

Starting an action temporarily pauses the known ZuneLauncher process; closing the GUI
restores its prior state. No startup registry or service is changed. An already running
Zune main application must finish any sync/update and be closed by the user.

[中文使用说明](../docs/zh-CN/assistant.md) · [English](../docs/en/assistant.md)

```powershell
python -m pip install -r app/requirements.txt
python app/main.py
```

Normal startup opens the GUI without USB operations. `--self-test` checks startup,
asset hashes and local COM value objects without enumerating/opening a device.
`--demo` disables all device actions for visual preview.

## Modules

- `zzune/gui.py`: simple action UI and a separate serialized worker process.
- `zzune/engine.py`: inspect, staged backup, prepare, upgrade and restore interface.
- `zzune/wpd.py`: Windows inbox WPD operations; no connection on import.
- `zzune/transfer.py`: same-unit checks, queue/readback checks and durable single-commit intent.
- `zzune/storage.py`: private atomic session and backup journal.
- `native/`: original ARM CE source for NK/raw backup templates.
- `assets/`: generated original helpers, import ordinal metadata and integrity hashes.
- `vendor/`: MIT-licensed CE decoder source.

## Build the Windows executable

```powershell
python -m pip install -r app/requirements-build.txt
python app/build_windows.py --output-dir generated/dist --work-dir generated/packaging
```

The packaged executable includes dependencies and keeps local user data under
`%LOCALAPPDATA%\ZZAudio\ZuneAssistant`. It contains no Microsoft device firmware,
device vault or private identity. See [bundle licensing](LICENSE-BUNDLE.md).

## Rebuild native helper templates

The shipped templates are original project binaries. Their C sources and compiler
script are provided. The compiler is Zig 0.13.0.post1 with ARM1136 settings. Export
ordinals are public metadata retained in `assets/helpers.json`; no DLL code is copied.
Rebuild from published import metadata without a Microsoft DLL:

```powershell
python app/native/build_helpers.py --zig local-inputs/zig.exe --work-dir generated/native-build --output-dir generated/native-assets
```

Optionally regenerate ordinals from your own original 1.0 coredll:

```powershell
python app/native/build_helpers.py --coredll local-inputs/coredll-1.0.dll --zig local-inputs/zig.exe --work-dir generated/native-build --output-dir generated/native-assets
```

Native code is not a desktop program. The host binds its entire volatile carrier
header after creating and verifying the owned MTP object. Tests execute the actual
patched ARM binary with a different synthetic object ID/token; this catches compiler
constant folding that would otherwise break rebinding.

## Tests

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python app/main.py --self-test
```

No test contacts a Zune. Simulated CE/hardware calls do not establish real-device
compatibility. All physical acceptance claims belong in a separate hardware report.
