"""
Neuron Launcher — Tiny stub compiled by PyInstaller.
Launches the REAL app using the project's venv Python (no torch bundling).
"""
import os
import sys
import subprocess

def main():
    # Find the app directory (where this exe lives or parent)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    # Look for the app in expected locations
    app_dir = None
    for candidate in [
        exe_dir,                                    # Same folder
        os.path.join(exe_dir, 'app'),               # Subfolder
        os.path.dirname(exe_dir),                   # Parent
        r'c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs',  # Hardcoded fallback
    ]:
        if os.path.exists(os.path.join(candidate, 'run_desktop.py')):
            app_dir = candidate
            break

    if not app_dir:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "Could not find Neuron app files.\nPlace Neuron.exe in the project folder.", "Neuron", 0x10
        )
        sys.exit(1)

    # Find python interpreter
    venv_python = os.path.join(app_dir, 'venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = sys.executable  # fallback to system python

    script = os.path.join(app_dir, 'run_desktop.py')

    # Launch the real app (detached, no console window)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE

    subprocess.Popen(
        [venv_python, script],
        cwd=app_dir,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

if __name__ == '__main__':
    main()
