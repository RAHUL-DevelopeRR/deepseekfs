from pathlib import Path
p=Path('validation/desktop-20261005/latest/desktop-flows-final.log')
print(p.read_text(encoding='utf-8', errors='replace')[-2200:])
