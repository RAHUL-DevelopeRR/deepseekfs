"""
Neuron Launcher — Tiny stub compiled by PyInstaller.
Launches the REAL app using the project's venv pythonw.exe (no torch bundling).

Key design decisions:
  - Uses pythonw.exe (not python.exe) so no console window appears.
  - Uses DETACHED_PROCESS (not CREATE_NO_WINDOW) so the child
    process gets its own desktop/window station and PyQt6 can render.
  - CREATE_NO_WINDOW prevents GUI windows from appearing on many
    Windows configurations — that was the v4.2 bug.
"""
import os
import sys
import subprocess


def main():
    # ── Locate the app directory (where run_desktop.py lives) ──
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    app_dir = None
    for candidate in [
        exe_dir,                                    # Same folder
        os.path.join(exe_dir, 'app'),               # Subfolder
        os.path.dirname(exe_dir),                   # Parent
    ]:
        if os.path.exists(os.path.join(candidate, 'run_desktop.py')):
            app_dir = candidate
            break

    if not app_dir:
        _show_error(
            "Could not find Neuron app files.\n"
            "Place Neuron.exe in the project folder containing run_desktop.py."
        )
        sys.exit(1)

    # ── Find pythonw.exe (GUI Python, no console) ──
    # Prefer pythonw.exe over python.exe — it's a windowless host,
    # so no black console flashes, and the child process can still
    # create GUI windows (unlike CREATE_NO_WINDOW).
    venv_pythonw = os.path.join(app_dir, 'venv', 'Scripts', 'pythonw.exe')
    venv_python  = os.path.join(app_dir, 'venv', 'Scripts', 'python.exe')

    if os.path.exists(venv_pythonw):
        interpreter = venv_pythonw
    elif os.path.exists(venv_python):
        interpreter = venv_python
    else:
        _show_error(
            "Could not find Python interpreter in venv/Scripts/.\n"
            "Reinstall Neuron or ensure the venv directory is intact."
        )
        sys.exit(1)

    script = os.path.join(app_dir, 'run_desktop.py')

    # ── Launch the real app ──
    # DETACHED_PROCESS: child gets its own console group but can
    # still create GUI windows.  This replaces CREATE_NO_WINDOW
    # which was preventing the PyQt6 overlay from rendering.
    DETACHED_PROCESS = 0x00000008

    try:
        subprocess.Popen(
            [interpreter, script],
            cwd=app_dir,
            creationflags=DETACHED_PROCESS,
            close_fds=True,
        )
    except Exception as e:
        _show_error(f"Failed to launch Neuron:\n{e}")
        sys.exit(1)


def _show_error(message: str):
    """Show a native Windows error dialog."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "Neuron", 0x10)
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)


if __name__ == '__main__':
    main()
