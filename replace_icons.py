"""Replace the _I icon map and other emoji usage in spotlight_components.py programmatically."""
import re

fpath = r"c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs_recovered\ui\spotlight_components.py"

with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace the entire _I = { ... } block with clean icon names
new_I = '''# \u2500\u2500 file icon map \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
_I = {
    ".py":("code","#3B82F6","PY"),        ".ipynb":("notebook","#8B5CF6","NB"),
    ".js":("zap","#EAB308","JS"),         ".ts":("code","#3B82F6","TS"),
    ".jsx":("atom","#22D3EE","JSX"),      ".tsx":("atom","#3B82F6","TSX"),
    ".rs":("code","#E57A44","RS"),         ".go":("code","#00ADD8","GO"),
    ".java":("coffee","#F59E0B","JV"),     ".cpp":("terminal","#60A5FA","C++"),
    ".c":("terminal","#94A3B8","C"),       ".h":("terminal","#94A3B8","H"),
    ".cs":("code","#A78BFA","C#"),         ".rb":("diamond","#EF4444","RB"),
    ".php":("code","#A78BFA","PHP"),       ".swift":("zap","#F97316","SW"),
    ".kt":("code","#A855F6","KT"),         ".html":("globe","#EF4444","HTM"),
    ".css":("palette","#38BDF8","CSS"),    ".md":("file-text","#94A3B8","MD"),
    ".txt":("file-text","#94A3B8","TXT"),  ".log":("clipboard","#94A3B8","LOG"),
    ".pdf":("book-open","#EF4444","PDF"),  ".docx":("file-text","#2563EB","DOC"),
    ".doc":("file-text","#2563EB","DOC"),  ".xlsx":("bar-chart-2","#22C55E","XLS"),
    ".xls":("bar-chart-2","#22C55E","XLS"),".csv":("bar-chart-2","#22C55E","CSV"),
    ".pptx":("file-text","#F97316","PPT"),
    ".json":("{ }","#F5B74A","JSON"),      ".xml":("< >","#F5B74A","XML"),
    ".yaml":("settings","#A78BFA","YML"),  ".yml":("settings","#A78BFA","YML"),
    ".toml":("settings","#A78BFA","TML"),  ".env":("lock","#A78BFA","ENV"),
    ".ini":("settings","#94A3B8","INI"),   ".cfg":("settings","#94A3B8","CFG"),
    ".mp4":("film","#A855F6","MP4"),       ".mkv":("film","#A855F6","MKV"),
    ".avi":("film","#A855F6","AVI"),       ".mov":("film","#A855F6","MOV"),
    ".png":("image","#EC4899","PNG"),      ".jpg":("image","#EC4899","JPG"),
    ".jpeg":("image","#EC4899","JPG"),     ".gif":("image","#EC4899","GIF"),
    ".webp":("image","#EC4899","WBP"),
    ".zip":("package","#FBBF24","ZIP"),    ".exe":("terminal","#A78BFA","EXE"),
}
_D = ("file","#64748B","FILE")'''

# Find and replace the _I block using regex
# Match from "# ── file icon map" through "_D = ..."
pattern = re.compile(
    r'# .+ file icon map .+\n_I = \{.*?\}\n_D = \([^)]+\)',
    re.DOTALL
)
content, n = pattern.subn(new_I, content)
print(f"Replaced _I block: {n} match(es)")

# 2. Replace remaining emoji in folder path labels
content = content.replace('  \U0001f4c2  ', '  ')  # 📂 in watch paths
content = content.replace('\U0001f4c4', '')  # 📄 fallback

# 3. Replace emoji in SuggestionChip fallback
# The setText("📄") for fallback icon
old_chip = 'ic.setText("\U0001f4c4")'
new_chip = 'ic.setPixmap(icon_pixmap("file", 14, "#94A3B8"))'
content = content.replace(old_chip, new_chip)

# 4. Replace remaining close button ✕
# Already handled - keep as text

with open(fpath, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Done! spotlight_components.py updated.")

# Verify it compiles
import py_compile
try:
    py_compile.compile(fpath, doraise=True)
    print("Syntax check: PASSED")
except py_compile.PyCompileError as e:
    print(f"Syntax check: FAILED - {e}")
