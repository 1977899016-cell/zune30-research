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

## Optional CE decompression module for the upgrade builder

The offline upgrade builder calls a separately supplied
[KodaSec/wince-decompr](https://github.com/KodaSec/wince-decompr) `wincedecompr.py`
to independently verify CE LZX output. This module is not vendored. Obtain and retain
its upstream license with your local copy. The tested upstream file SHA-256 is
`42693ba5e756f664d2405bdaa2f6f9bc5671b5956439aeed581c8e7e89f2e72d`.
Windows MakeCAB is used as a locally installed tool and is not redistributed.

## FLAC and community research

FLAC functionality in the private research build uses separately obtained Xiph/DirectShow
components and project-specific integration. No decoder binary or its source is bundled in
this initial font-tool publication. Relevant upstream terms remain separate.

Community references:

- [OpenZDK quick-start kit](https://github.com/ZuneRedux/openZDK-quick-start-kit)
- [Zune community archive](https://ephemera.zunes.me/archive)
- [Zune 30G iFixit documentation](https://www.ifixit.com/Device/Microsoft_Zune_30_GB)

Reference links are acknowledgments, not claims that upstream authors endorse this project.
