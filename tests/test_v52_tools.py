"""Test script for Neuron v5.2 tool execution."""
import sys, os, tempfile
sys.path.insert(0, r'c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from services.tools import execute_tool

passed = 0
failed = 0

def check(name, result, expect_success=True):
    global passed, failed
    ok = result.success == expect_success
    status = "PASS" if ok else "FAIL"
    if not ok:
        failed += 1
    else:
        passed += 1
    # Avoid emoji for cp1252 console
    out = result.output[:100].encode('ascii', 'replace').decode()
    print(f"  [{status}] {name}: success={result.success} | {out}")

print("=" * 60)
print("Neuron v5.2 — Tool Execution Tests")
print("=" * 60)

# Setup
test_dir = os.path.join(tempfile.gettempdir(), 'neuron_test')
os.makedirs(test_dir, exist_ok=True)
test_file = os.path.join(test_dir, 'hello.py')

# 1. file_write
r = execute_tool('file_write', path=test_file, content='print("Hello from MemoryOS!")\n')
check("file_write", r)

# 2. file_read
r = execute_tool('file_read', path=test_file)
check("file_read", r)

# 3. file_edit
r = execute_tool('file_edit', path=test_file, find='Hello', replace='Greetings')
check("file_edit", r)

# 4. file_read (verify edit)
r = execute_tool('file_read', path=test_file)
assert 'Greetings' in r.output, f"Edit not applied: {r.output}"
check("file_read (post-edit)", r)

# 5. folder_create
sub = os.path.join(test_dir, 'subdir', 'nested')
r = execute_tool('folder_create', path=sub)
check("folder_create", r)

# 6. folder_list
r = execute_tool('folder_list', path=test_dir, max_depth=2)
check("folder_list", r)

# 7. glob
r = execute_tool('glob', pattern='*.py', path=test_dir)
check("glob", r)

# 8. shell (safe command)
r = execute_tool('shell', command='echo MemoryOS-ShellTest')
check("shell (safe)", r)

# 9. shell (dangerous - should be blocked)
r = execute_tool('shell', command='format C:')
check("shell (blocked)", r, expect_success=False)

# 10. python_exec
r = execute_tool('python_exec', code='print(2+2)\nprint("Python exec works!")')
check("python_exec", r)

# 11. summarize (folder)
r = execute_tool('summarize', path=test_dir)
check("summarize (folder)", r)

# 12. file_delete (dangerous - needs override)  
r = execute_tool('file_delete', path=test_file)
check("file_delete", r)

# 13. folder_search
r = execute_tool('folder_search', query='neuron_test', search_path=tempfile.gettempdir())
check("folder_search", r)

# Cleanup
import shutil
shutil.rmtree(test_dir, ignore_errors=True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
print("=" * 60)

if failed > 0:
    sys.exit(1)
