"""Package a Windows x64 experimental GUI. Does not access a connected device."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'PyInstaller', '--onefile', '--windowed', '--noupx',
        '--name', 'ZZAudio-Zune30-Assistant', '--distpath', str(args.output_dir.resolve()),
        '--workpath', str((args.work_dir/'build').resolve()), '--specpath', str(args.work_dir.resolve()),
        '--paths', str(root/'app'),
        '--collect-all', 'keystone', '--exclude-module', 'comtypes.test',
        '--exclude-module', 'numpy', '--exclude-module', 'psutil',
        '--add-data', str(root/'app/assets') + ':app/assets',
        '--add-data', str(root/'app/vendor') + ':app/vendor',
        '--add-data', str(root/'app/licenses') + ':app/licenses',
        '--add-data', str(root/'tools/upgrade') + ':tools/upgrade', str(root/'app/main.py')]
    from PyInstaller.utils.hooks import collect_submodules
    modules = collect_submodules('comtypes', filter=lambda name: not name.startswith(('comtypes.test', 'comtypes.server')))
    for module in modules:
        command[3:3] = ['--hidden-import', module]
    subprocess.run(command, cwd=root, check=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

if __name__ == '__main__': main()
