"""Read-only host process detection; never closes applications or resets USB."""
import csv
import os
from pathlib import Path
import subprocess


class OfficialZuneBusy(RuntimeError):
    pass


def official_zune_running():
    if os.name != 'nt': return False
    tasklist = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/tasklist.exe'
    result = subprocess.run([str(tasklist), '/FI', 'IMAGENAME eq Zune.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                            timeout=10, check=True)
    # Only compare the ASCII executable name. Localized messages are not parsed.
    return any(row and row[0].lower() == 'zune.exe'
               for row in csv.reader(result.stdout.decode('ascii', errors='replace').splitlines()))
