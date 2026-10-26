"""Launch the packaged Windows EXE, verify its visible GUI, and close it."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

exe = Path(__file__).resolve().parents[1] / 'dist' / 'Lotto Generator.exe'
process = subprocess.Popen([str(exe)])
deadline = time.monotonic() + 45
windows = []


@callback_type
def visit(hwnd, _):
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, len(title))
    if title.value == '로또 6/45 · 베이지안 번호 추천' and user32.IsWindowVisible(hwnd):
        windows.append(hwnd)
    return True


try:
    while time.monotonic() < deadline and process.poll() is None:
        user32.EnumWindows(visit, 0)
        if windows:
            break
        time.sleep(0.25)
    if not windows:
        raise RuntimeError(f'Packaged EXE did not show the expected window. Exit code: {process.poll()}')
    user32.PostMessageW(windows[0], 0x0010, 0, 0)  # WM_CLOSE
    code = process.wait(timeout=15)
    if code != 0:
        raise RuntimeError(f'EXE exited with code {code}')
    print('EXE_SMOKE_OK: packaged EXE showed the Korean GUI and closed successfully')
finally:
    if process.poll() is None:
        process.kill()
