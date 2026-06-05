"""Replace all emoji usage in spotlight_panel.py with Lucide icon system calls."""
import re

fpath = r"c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs_recovered\ui\spotlight_panel.py"

with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ── Add import if not present ──
if 'from ui.icons import' not in content:
    content = content.replace(
        'from ui.spotlight_components import',
        'from ui.icons import icon_pixmap, icon_label\nfrom ui.spotlight_components import',
        1
    )
    changes += 1
    print("Added ui.icons import")

# ── Emoji replacements (text labels, remove emoji prefix) ──
# Map of emoji -> replacement text
emoji_text_replacements = {
    '\U0001f9e0 Encyl Answer': 'Encyl Answer',
    '\U0001f9e0 Encyl Summary': 'Encyl Summary',
    '\U0001f9e0 Encyl is searching your files': 'Encyl is searching your files',
    '\U0001f9e0 AI enhancing': 'AI enhancing',
    '\U0001f9e0 Encyl is reading your files': 'Encyl is reading your files',
    '\U0001f9e0 Encyl is thinking': 'Encyl is thinking',
    '\U0001f9e0 Encyl is summarizing': 'Encyl is summarizing',
    '\U0001f9e0 Reading': 'Reading',
    '\U0001f9e0 Encyl answered': 'Encyl answered',
    '\U0001f9e0 Encyl summarized': 'Encyl summarized',
    '\U0001f9e0 Encyl': 'Encyl',
    '\U0001f9e0 \u2717': 'Encyl \u2717',  # brain + x-mark
    '\u2728 AI-enhanced': 'AI-enhanced',
    '\u26a0 Encyl offline': 'Encyl offline',
    '\u26a0 Encyl error': 'Encyl error',
    '\U0001f525 ': '',  # flame before streak numbers
    '\U0001f4c2': '',  # folder emoji
    ' \U0001f525': '',  # flame after streak text
}

for old, new in emoji_text_replacements.items():
    if old in content:
        count = content.count(old)
        content = content.replace(old, new)
        changes += count
        print(f"  Replaced {repr(old)[:40]} -> '{new}' ({count}x)")

# ── Replace close button emoji ──
# QLabel("✕") or QLabel("✖") or QLabel("✗")  
content = content.replace('QLabel("\u2715")', 'QLabel("X")')
content = content.replace('QLabel("\u2717")', 'QLabel("X")')
content = content.replace('QLabel("\u2716")', 'QLabel("X")')

# ── Replace action card emojis that may be passed as args ──
# ActionCard("\U0001f504", ...) -> ActionCard("refresh-cw", ...)
content = content.replace('ActionCard("\U0001f504"', 'ActionCard("refresh-cw"')
content = content.replace('ActionCard("\U0001f4c2"', 'ActionCard("folder-plus"')
content = content.replace('ActionCard("\u2699\ufe0f"', 'ActionCard("settings"')
content = content.replace('ActionCard("\u2699"', 'ActionCard("settings"')

# ── Replace activity emoji map references ──
# type_emoji dict
type_emoji_replacements = {
    '"open": "\U0001f4c2"': '"open": "folder"',
    '"search": "\U0001f50d"': '"search": "search"',
    '"summarize": "\U0001f9e0"': '"summarize": "cpu"',
    '"index": "\U0001f4c4"': '"index": "hard-drive"',
    '"access": "\U0001f4c4"': '"access": "file"',
}
for old, new in type_emoji_replacements.items():
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print(f"  Replaced type_emoji: {new}")

# ── Generic emoji removal (any remaining emojis as prefixes) ──
# Remove any standalone emoji characters left  
EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FEFF'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]'
)

remaining = [(m.start(), m.group(), content[max(0,m.start()-20):m.end()+20]) 
             for m in EMOJI_RE.finditer(content)
             if not content[max(0,m.start()-10):m.start()].rstrip().endswith('#')]  # skip comments

if remaining:
    print(f"\n  Remaining emoji occurrences ({len(remaining)}):")
    for pos, emoji, ctx in remaining[:10]:
        print(f"    pos {pos}: {ascii(emoji)} ctx: {ascii(ctx.strip())}")
    # Remove them
    content = EMOJI_RE.sub('', content)
    changes += len(remaining)
    print(f"  Removed {len(remaining)} remaining emoji characters")

with open(fpath, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print(f"\nDone! {changes} total changes in spotlight_panel.py")

# Verify
import py_compile
try:
    py_compile.compile(fpath, doraise=True)
    print("Syntax check: PASSED")
except py_compile.PyCompileError as e:
    print(f"Syntax check: FAILED - {e}")
