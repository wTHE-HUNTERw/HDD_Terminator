"""
HDD Terminator Entry Point with Automatic UAC Elevation
"""

import sys
import os
import ctypes

def is_user_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_as_admin():
    """Relaunches the current script with elevated Administrator privileges."""
    if not is_user_admin() and "--no-elevate" not in sys.argv:
        script = os.path.abspath(__file__)
        params = f'"{script}" ' + " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        # ShellExecuteW with 'runas' verb triggers the Windows UAC elevation prompt
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            os.path.dirname(script),
            1 # SW_SHOWNORMAL
        )
        if ret > 32:
            # Elevation request succeeded, exit current unprivileged process
            sys.exit(0)

# Ensure package path is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import HDDTerminatorApp

def main():
    elevate_as_admin()
    app = HDDTerminatorApp()
    app.mainloop()

if __name__ == "__main__":
    main()

