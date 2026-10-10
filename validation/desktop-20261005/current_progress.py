from pathlib import Path

root = Path('D:/NeuCockpit-build-archive/2026-10-05/accelerated-release')
installer = root / 'NeuCockpitSetup_v1.0_windows_x64.exe'
print('Installer bytes:', installer.stat().st_size, '/ 1295602832')
log = Path(__file__).parent / 'resume-download.log'
if log.exists():
    print(log.read_text(errors='replace').replace('\r', '\n').splitlines()[-1])
install_log = root / 'install.log'
if install_log.exists():
    print('\n'.join(install_log.read_text(errors='replace').splitlines()[-8:]))
