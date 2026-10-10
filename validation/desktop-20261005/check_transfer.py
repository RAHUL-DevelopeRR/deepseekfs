import psutil
for process in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        if (process.info['name'] or '').lower() == 'curl.exe':
            command = ' '.join(process.info['cmdline'] or [])
            if 'accelerated-release' in command:
                print(process.info['pid'], command)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
