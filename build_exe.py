"""Developer-only Windows build; end users run the resulting EXE."""
import os
from pathlib import Path
import subprocess
import sys

if os.name != 'nt':
    raise SystemExit('Run this builder with Windows Python (or Windows Python under Wine).')

root = Path(__file__).resolve().parent
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                '--onefile', '--windowed', '--name', 'Lotto Generator',
                '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
                '--specpath', str(root / 'build'), str(root / 'lotto_gui.py')], cwd=root, check=True)
