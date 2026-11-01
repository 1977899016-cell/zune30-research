# Executable distribution / 可执行包许可

Original ZZ AUDIO source files retain the repository's MIT license.
The packaged Windows executable includes Keystone Engine, distributed here under
GNU GPL version 2. Distribution of this combined executable is under GPL-2.0;
the MIT source remains available under its original permissive terms as well.
The GPL-2.0 text is provided in `licenses/KEYSTONE-GPL2.txt`.

对应的项目源码、构建脚本和原生备份程序源码位于本仓库的 `app/` 与 `tools/upgrade/`。
可重新构建本机程序；原生模板的重新构建另需用户自备的 1.0 coredll 导出信息和 Zig。
生成的设备备份和私有 NK 不属于分发包。

Corresponding project source and build scripts are in `app/` and `tools/upgrade/`.
Native template source is in `app/native/`; rebuilding those templates can use
the published import-ordinal metadata and Zig. No device credential
or Microsoft device firmware is distributed.

Third-party components retain their individual notices:

- Keystone Engine: package license and GPL-2.0, plus upstream notices included with it.
- Python: Python Software Foundation license and included third-party terms.
- Tcl/Tk: upstream license terms.
- comtypes: MIT.
- pefile: upstream MIT-style license.
- KodaSec wince-decompr: MIT; its source and license are included.
- PyInstaller bootloader: GPL with its special distribution exception.

See `app/licenses/` and the repository's `THIRD_PARTY_NOTICES.md`. This does not
relicense Microsoft firmware, device data, fonts or system DLLs.
