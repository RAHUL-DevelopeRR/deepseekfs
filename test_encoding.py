import re

cp1252_special = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
pattern = re.compile(r'[\x80-\xff' + re.escape(cp1252_special) + r']+')

def repair_text_regex(text):
    changes = 0
    def replace(match):
        nonlocal changes
        m = match.group(0)
        try:
            encoded = m.encode('cp1252')
            decoded = encoded.decode('utf-8')
            if decoded != m:
                changes += 1
                return decoded
        except Exception:
            pass
        return m

    repaired = pattern.sub(replace, text)
    return repaired, changes

with open("ui/spotlight_components.py", "rb") as f:
    raw = f.read()

content = raw.decode('utf-8', errors='replace').lstrip('\ufeff')
repaired_content, changes = repair_text_regex(content)
print("Regex repair changes in components:", changes)

repaired_lines = repaired_content.splitlines()
for i, line in enumerate(repaired_lines, 1):
    if "setText" in line and any(ord(c) > 127 for c in line):
        print(f"Line {i}: {ascii(line)}")
