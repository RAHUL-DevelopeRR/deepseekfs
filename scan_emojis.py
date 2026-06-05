"""Scan UI files for all emoji usage and map them to Lucide icon names."""
import re

# Match any character outside the Basic Multilingual Plane or common emoji ranges
EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF'  # Misc Symbols, Emoticons, etc.
    r'\U00002600-\U000027BF'    # Misc symbols, Dingbats
    r'\U0000FE00-\U0000FEFF'    # Variation selectors
    r'\U0001FA00-\U0001FA6F'    # Chess, extended-A
    r'\U0001FA70-\U0001FAFF'    # Extended-A continued
    r'\u2699\u2696\u2694\u2692' # Individual symbols
    r'\u2728\u2764\u2B50'       # Sparkles, heart, star
    r']+',
    re.UNICODE
)

def scan_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            for m in EMOJI_RE.finditer(line):
                emoji = m.group(0)
                # Get context
                start = max(0, m.start() - 20)
                end = min(len(line), m.end() + 30)
                ctx = line[start:end].strip()
                print(f"  Line {i:4d}: {ascii(emoji):30s}  context: {ascii(ctx)}")

for f in [
    "ui/spotlight_components.py",
    "ui/spotlight_panel.py",
    "ui/activity_panel.py",
    "ui/memory_lane_panel.py",
    "ui/memoryos_panel.py",
    "ui/research_overlay.py",
]:
    try:
        print(f"\n{'='*60}\n{f}\n{'='*60}")
        scan_file(f)
    except FileNotFoundError:
        print(f"  (not found)")
