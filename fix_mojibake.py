"""
Fix mojibake in Python source files.

Root cause: UTF-8 files were read as CP1252 and re-saved as UTF-8.
Fix: find runs of non-ASCII characters, encode them back to CP1252 bytes,
     then decode those bytes as UTF-8 to recover the original characters.
"""
import re
import os
import sys

# Regex matches runs of characters in the CP1252 high-byte range (0x80-0xFF)
# plus the CP1252-specific characters that map to 0x80-0x9F range
# (these are: €‚ƒ„…†‡ˆ‰Š‹ŒŽ''""•–—˜™š›œžŸ and Latin chars like ð, Ã, etc.)
_MOJIBAKE_RUN = re.compile(
    r'[\x80-\xff\u0152\u0153\u0160\u0161\u0178\u017d\u017e'
    r'\u0192\u02c6\u02dc\u2013\u2014\u2018\u2019\u201a\u201c'
    r'\u201d\u201e\u2020\u2021\u2022\u2026\u2030\u2039\u203a'
    r'\u20ac\u2122]+'
)


def repair_mojibake(text: str) -> tuple[str, int]:
    """Return (repaired_text, change_count)."""
    changes = 0

    def _replace(m: re.Match) -> str:
        nonlocal changes
        frag = m.group(0)
        try:
            restored = frag.encode('cp1252').decode('utf-8')
            if restored != frag:
                changes += 1
                return restored
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return frag

    return _MOJIBAKE_RUN.sub(_replace, text), changes


def fix_file(path: str) -> bool:
    """Fix one file in-place. Returns True if changes were made."""
    with open(path, 'rb') as f:
        raw = f.read()

    has_bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8', errors='replace')
    if has_bom:
        text = text.lstrip('\ufeff')

    repaired, n = repair_mojibake(text)
    if n == 0:
        return False

    enc = 'utf-8-sig' if has_bom else 'utf-8'
    with open(path, 'w', encoding=enc, newline='') as f:
        f.write(repaired)

    print(f"  FIXED  {path}  ({n} mojibake sequences repaired)")
    return True


def main():
    dirs = ['ui', 'core', 'services', 'app', 'scripts']
    fixed = 0
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fn in sorted(files):
                if fn.endswith('.py'):
                    if fix_file(os.path.join(root, fn)):
                        fixed += 1

    print(f"\nDone — {fixed} file(s) repaired.")


if __name__ == '__main__':
    main()
