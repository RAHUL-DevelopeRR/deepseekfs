import concurrent.futures
import json
import re
import urllib.request

page = 'https://neuron.zero-x.live/'
# These six URLs were read from the live browser's download controls.
names = ['NeuCockpitSetup_v1.0_windows_x64.exe', 'NeuCockpitSetup_v1.0_windows_arm64.exe', 'NeuCockpit-v1.0-linux-x64.run', 'NeuCockpit-v1.0-linux-arm64.run', 'NeuCockpit-v1.0-macos-arm64.dmg', 'NeuCockpit-v1.0-macos-intel.dmg']
links = ['https://github.com/RAHUL-DevelopeRR/deepseekfs/releases/latest/download/' + name for name in names]
def check(url):
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=40) as response:
        return {'asset': url.rsplit('/', 1)[-1], 'status': response.status, 'bytes': response.headers.get('Content-Length')}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
    results = list(executor.map(check, links))
print(json.dumps({'page': page, 'downloads': results}, indent=2))
assert len(results) >= 6
