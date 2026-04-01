import os
import sys
import winreg
from pathlib import Path

def set_startup(enable: bool = True):
    """Add or remove Neuron from Windows startup."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "Neuron"
    
    try:
        # Determine path to the executable or script
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            # If running from source, point to run_desktop.py via pythonw
            root_dir = Path(__file__).parent.parent.absolute()
            pythonw = root_dir / "venv" / "Scripts" / "pythonw.exe"
            script = root_dir / "run_desktop.py"
            if pythonw.exists():
                exe_path = f'"{pythonw}" "{script}"'
            else:
                exe_path = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{script}"'
                
        # Open registry key
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, str(exe_path))
            print(f"Added {app_name} to Windows startup: {exe_path}")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                print(f"Removed {app_name} from Windows startup.")
            except FileNotFoundError:
                print(f"{app_name} was not set to run on startup.")
                
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Error configuring startup: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Configure Neuron to run on Windows startup.")
    parser.add_argument("--disable", action="store_true", help="Remove Neuron from Windows startup")
    args = parser.parse_args()
    
    set_startup(not args.disable)
