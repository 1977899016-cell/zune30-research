# Third-party notices / 第三方说明

The root MIT license applies to original project material, not third-party firmware, fonts or codecs.
根目录 MIT 许可只覆盖项目原创部分，不覆盖第三方固件、字体或解码器。

## Locally supplied Microsoft files

Zune, Windows CE, Microsoft firmware, `coredll.dll` and original interface fonts are Microsoft
materials. No such system binary or font is included. Export ordinals are read from the user's
local DLL by the offline build tool. Use the inputs under their applicable terms.

## Python dependencies

Dependencies are installed from their upstream packages, not vendored here:

- [fontTools](https://github.com/fonttools/fonttools): MIT.
- [pefile](https://github.com/erocarrera/pefile): MIT-style upstream license.
- [Keystone Engine](https://github.com/keystone-engine/keystone): upstream GPL-2.0/commercial licensing.
- [Capstone](https://github.com/capstone-engine/capstone): upstream BSD licensing.
- [Unicorn Engine](https://github.com/unicorn-engine/unicorn): GPL-2.0 upstream licensing.

Check the exact package versions and upstream license files before redistributing dependencies.
The repository does not relicense them. The loader generator's output is not a bundled copy
of these engines.

## FLAC and community research

FLAC functionality in the private research build uses separately obtained Xiph/DirectShow
components and project-specific integration. No decoder binary or its source is bundled in
this initial font-tool publication. Relevant upstream terms remain separate.

Community references:

- [OpenZDK quick-start kit](https://github.com/ZuneRedux/openZDK-quick-start-kit)
- [Zune community archive](https://ephemera.zunes.me/archive)
- [Zune 30G iFixit documentation](https://www.ifixit.com/Device/Microsoft_Zune_30_GB)

Reference links are acknowledgments, not claims that upstream authors endorse this project.
