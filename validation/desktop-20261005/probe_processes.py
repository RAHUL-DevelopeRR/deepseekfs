import datetime
import psutil
for p in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'memory_info', 'create_time']):
    try:
        info = p.info
        command = ' '.join(info['cmdline'] or [])
        if any(x in command for x in ['run_llm_worker.py', 'neufs.py', 'NeuronLLMWorker.exe', 'verify_release_ai.py']):
            print(info['pid'], info['ppid'], info['name'], round(info['memory_info'].rss / 1024**2), datetime.datetime.fromtimestamp(info['create_time'], datetime.timezone.utc).isoformat(), 'parent_exists', psutil.pid_exists(info['ppid']))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
