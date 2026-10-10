import json
import psutil

memory = psutil.virtual_memory()
processes = []
for process in psutil.process_iter(['pid','name','memory_info']):
    try:
        info = process.info
        if info['memory_info']:
            processes.append({'pid':info['pid'],'name':info['name'],'rss_mb':round(info['memory_info'].rss / 1048576)})
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
print(json.dumps({'total_ram_mb':round(memory.total / 1048576),'available_ram_mb':round(memory.available / 1048576),'used_percent':memory.percent,'largest_processes':sorted(processes,key=lambda p:p['rss_mb'],reverse=True)[:8]},indent=2))
