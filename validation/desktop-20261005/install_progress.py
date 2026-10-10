from pathlib import Path
p = Path('D:/NeuCockpit-build-archive/2026-10-05/fresh-release/install.log')
print(p.read_text(encoding='utf-8', errors='replace')[-1800:] if p.exists() else 'Installer log not created yet')
model = Path('C:/Users/DELL/AppData/Local/Programs/NeuCockpit/_internal/storage/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf')
print('Model bytes extracted:', model.stat().st_size if model.exists() else 0)
