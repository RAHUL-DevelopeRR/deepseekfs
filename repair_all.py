import os
import sys

def get_cp1252_chars():
    cp1252_chars = set()
    for i in range(256):
        try:
            cp1252_chars.add(bytes([i]).decode('cp1252'))
        except UnicodeDecodeError:
            pass
    return cp1252_chars

def repair_text(text, cp1252_chars):
    # Segment text into runs of CP1252-valid characters vs non-CP1252-valid characters
    chunks = []
    current_run = []
    in_cp1252 = None
    
    for char in text:
        is_cp = char in cp1252_chars
        if in_cp1252 is None:
            in_cp1252 = is_cp
            current_run.append(char)
        elif in_cp1252 == is_cp:
            current_run.append(char)
        else:
            chunks.append((''.join(current_run), in_cp1252))
            current_run = [char]
            in_cp1252 = is_cp
    if current_run:
        chunks.append((''.join(current_run), in_cp1252))
        
    repaired_chunks = []
    changes_count = 0
    for chunk_text, is_cp in chunks:
        if not is_cp:
            repaired_chunks.append(chunk_text)
        else:
            # Check if it has any non-ASCII characters to even consider it for repair
            if all(ord(c) < 128 for c in chunk_text):
                repaired_chunks.append(chunk_text)
            else:
                try:
                    repaired_bytes = chunk_text.encode('cp1252')
                    repaired_text = repaired_bytes.decode('utf-8')
                    if repaired_text != chunk_text:
                        changes_count += 1
                    repaired_chunks.append(repaired_text)
                except UnicodeError:
                    # Keep as is if it fails to decode as UTF-8
                    repaired_chunks.append(chunk_text)
                    
    return ''.join(repaired_chunks), changes_count

def repair_file(file_path, cp1252_chars):
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
            
        # Detect BOM
        has_bom = raw.startswith(b'\xef\xbb\xbf')
        
        # Decode as utf-8
        content = raw.decode('utf-8', errors='replace')
        if has_bom:
            content = content.lstrip('\ufeff')
            
        repaired_content, changes = repair_text(content, cp1252_chars)
        
        if changes > 0:
            print(f"Repairing {file_path} - {changes} mojibake sequences found.")
            # Save back
            with open(file_path, "w", encoding="utf-8-sig" if has_bom else "utf-8") as f:
                f.write(repaired_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    cp1252_chars = get_cp1252_chars()
    target_dirs = ["ui", "core", "services", "app", "scripts"]
    repaired_files = 0
    
    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    if repair_file(path, cp1252_chars):
                        repaired_files += 1
                        
    print(f"\nCompleted! Repaired {repaired_files} files.")

if __name__ == "__main__":
    main()
