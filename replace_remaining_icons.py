"""Replace all emoji in the remaining 4 UI files."""
import re
import py_compile

EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FEFF'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]'
)

def fix_file(fpath, specific_replacements=None):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes = 0
    
    # Add import if not present
    if 'from ui.icons import' not in content:
        # Try to add after the last import line
        lines = content.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('from ') or line.strip().startswith('import '):
                last_import = i
        lines.insert(last_import + 1, 'from ui.icons import icon_pixmap, icon_label')
        content = '\n'.join(lines)
        changes += 1
    
    # Apply specific replacements
    if specific_replacements:
        for old, new in specific_replacements.items():
            if old in content:
                count = content.count(old)
                content = content.replace(old, new)
                changes += count
    
    # Remove all remaining emoji characters
    remaining = list(EMOJI_RE.finditer(content))
    if remaining:
        content = EMOJI_RE.sub('', content)
        changes += len(remaining)
    
    with open(fpath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    
    try:
        py_compile.compile(fpath, doraise=True)
        status = "PASSED"
    except py_compile.PyCompileError as e:
        status = f"FAILED - {e}"
    
    print(f"  {fpath}: {changes} changes, syntax: {status}")
    return changes

base = r"c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs_recovered\ui"

# ── activity_panel.py ──
# Replace the _TYPE_ICONS dict emoji values with icon names
activity_replacements = {
    '"tool_call":       "\U0001f527"': '"tool_call":       "wrench"',
    '"tool_result":     "\U0001f4cb"': '"tool_result":     "clipboard"',
    '"llm_inference":   "\U0001f9e0"': '"llm_inference":   "cpu"',
    '"search":          "\U0001f50d"': '"search":          "search"',
    '"task_created":    "\U0001f4dd"': '"task_created":    "edit-3"',
    '"task_step":       "\u25b6\ufe0f"': '"task_step":       "play"',
    '"task_completed":  "\u2705"': '"task_completed":  "check-circle"',
    '"task_failed":     "\u274c"': '"task_failed":     "x-circle"',
    '"plan_generated":  "\U0001f4ca"': '"plan_generated":  "bar-chart-2"',
    '"watcher_trigger": "\U0001f441\ufe0f"': '"watcher_trigger": "eye"',
    '"plugin_loaded":   "\U0001f50c"': '"plugin_loaded":   "plug"',
    '"user_input":      "\U0001f4ac"': '"user_input":      "message-circle"',
    '"error":           "\u26a0\ufe0f"': '"error":           "alert-triangle"',
    # Filter combobox items
    '\U0001f527 Tool Calls': 'Tool Calls',
    '\U0001f9e0 LLM Inference': 'LLM Inference',
    '\U0001f50d Searches': 'Searches',
    '\U0001f4dd Tasks': 'Tasks',
    '\u26a0\ufe0f Errors': 'Errors',
}
fix_file(f"{base}\\activity_panel.py", activity_replacements)

# ── memory_lane_panel.py ──
memory_replacements = {
    'QPushButton("\u2715")': 'QPushButton("X")',
    '"\U0001f4c1"': '"folder"',
    '"\U0001f50d"': '"search"',
    '"\U0001f4ca"': '"bar-chart-2"',
    'QLabel("\U0001f50d")': 'icon_label("search", 16)',
    'QLabel("\U0001f4c4")': 'icon_label("file", 16)',
}
fix_file(f"{base}\\memory_lane_panel.py", memory_replacements)

# ── memoryos_panel.py ──
memoryos_replacements = {
    'QPushButton("\U0001f44d")': 'QPushButton("+")',
    'QPushButton("\U0001f44e")': 'QPushButton("-")',
    '"\U0001f44d"': '"+"',
    '"\U0001f44e"': '"-"',
}
fix_file(f"{base}\\memoryos_panel.py", memoryos_replacements)

# ── research_overlay.py ──
research_replacements = {
    '\U0001f399 Neuron Research': 'Neuron Research',
    '\U0001f441 Stealth': 'Stealth',
    '\u26a0 For research purposes only': 'For research purposes only',
    '\U0001f6e1 Stealth ON': 'Stealth ON',
    '\U0001f441 Stealth': 'Stealth',
    '\U0001f399 Listening...': 'Listening...',
}
fix_file(f"{base}\\research_overlay.py", research_replacements)

# Also fix the repaired copy if it exists
import os
repaired = f"{base}\\spotlight_panel_repaired.py"
if os.path.exists(repaired):
    fix_file(repaired)

print("\nAll files processed!")
