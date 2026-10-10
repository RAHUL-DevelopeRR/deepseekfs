from pathlib import Path
for p in [Path('C:/Program Files (x86)/Inno Setup 6/ISCC.exe'), Path('C:/Program Files/Inno Setup 6/ISCC.exe')]:
    print(str(p), p.exists())
for root in ['C:/Users/DELL/AppData/Local/Programs/NeuCockpit', 'D:/NeuCockpit-build-archive/2026-10-05/previous-installed-layout']:
    p = Path(root)
    print(root, p.exists(), len(list(p.rglob('*'))) if p.exists() else 0)
