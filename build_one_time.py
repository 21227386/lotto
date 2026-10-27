"""Build the separate EXE without replacing the regular Lotto Generator."""
import os
from pathlib import Path
import subprocess
import sys

if os.name != 'nt':
    raise SystemExit('Use Windows Python or Windows Python under Wine.')
root = Path(__file__).resolve().parent
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
                '--name', 'One-time Lotto Generator for You',
                '--add-data', str(root / 'assets') + ';assets',
                '--add-data', str(root / 'embedded') + ';embedded',
                '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
                '--specpath', str(root / 'build'), str(root / 'one_time_gui.py')], cwd=root, check=True)
