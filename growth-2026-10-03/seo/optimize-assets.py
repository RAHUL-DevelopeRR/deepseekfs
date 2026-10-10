from pathlib import Path
from PIL import Image
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

root = Path('C:/Users/DELL/zero-x.live')
assets = root / 'Assets'
variants = {
    'Zero-xBnW.png': ('zerox-wordmark.webp', (256, 112)),
    'NeuronBnW.png': ('neucockpit-mark.webp', (112, 112)),
    'neuron_circular.png': ('neucockpit-circle.webp', (64, 64)),
    'neucockpit-wheres-that-file.jpg': ('neucockpit-film-poster.webp', (360, 640)),
}
for source, (target, size) in variants.items():
    im = Image.open(assets / source)
    im.thumbnail(size, Image.Resampling.LANCZOS)
    im.save(assets / target, 'WEBP', quality=88, method=6)
    print(target, im.size, (assets / target).stat().st_size)

pages = [root / 'index.html', root / 'neuron.html']
all_html = '\n'.join(p.read_text(encoding='utf-8') for p in pages)
names = sorted(set(re.findall(r'<span[^>]*class="[^"]*material-symbols-outlined[^\"]*"[^>]*>\s*([a-z_0-9]+)\s*</span>', all_html)))
urls = [
    'https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@800,700,500,400&display=swap',
    'https://api.fontshare.com/v2/css?f[]=satoshi@700,500,400&display=swap',
    'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap',
    'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&icon_names=' + ','.join(names) + '&display=block',
]
def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36'})
    return urllib.request.urlopen(request, timeout=45).read().decode()
with ThreadPoolExecutor(max_workers=4) as pool:
    css_parts = list(pool.map(fetch, urls))
# Retain the vendor font URLs and font-display rules; remove the external CSS round trip.
font_css = '\n'.join(css_parts).replace("url('//", "url('https://")
(root / 'site-fonts.css').write_text(font_css, encoding='utf-8')
print('Subset icons:', ','.join(names))
for p in pages:
    html = p.read_text(encoding='utf-8')
    html = re.sub(r'  <link href="https://(?:api.fontshare.com|fonts.googleapis.com)[^\n]+\n', '', html)
    html = html.replace('  <!-- ═══ Fonts ═══ -->', '  <!-- ═══ Fonts ═══ -->\n  <link rel="preconnect" href="https://cdn.fontshare.com" crossorigin/>\n  <link rel="stylesheet" href="./site-fonts.css"/>')
    # Product currently has no Fonts comment; anchor before existing preconnect instead.
    if 'href="./site-fonts.css"' not in html:
        html = html.replace('  <link rel="preconnect" href="https://fonts.googleapis.com"/>', '  <link rel="preconnect" href="https://cdn.fontshare.com" crossorigin/>\n  <link rel="stylesheet" href="./site-fonts.css"/>\n  <link rel="preconnect" href="https://fonts.googleapis.com"/>')
    for source, (target, _) in variants.items():
        html = html.replace('src="./Assets/' + source + '"', 'src="./Assets/' + target + '"')
        html = html.replace('poster="./Assets/' + source + '"', 'poster="./Assets/' + target + '"')
    def dimensions(match):
        tag = match.group()
        src = re.search(r'src="\./Assets/([^\"]+)"', tag)
        if src and 'width=' not in tag:
            im = Image.open(assets / src[1])
            tag = tag.replace('<img', f'<img width="{im.width}" height="{im.height}"', 1)
        return tag
    html = re.sub(r'<img\b[^>]*>', dimensions, html, flags=re.S)
    html = html.replace('<p class="mt-6 text-[14px] text-zx-muted">', '<p class="max-w-[1100px] mx-auto mt-6 text-[14px] text-zx-muted">')
    html = html.replace('text-zx-faint/60', 'text-zx-faint')
    # The modal is outside main; page content starts immediately after its closing tag.
    html = html.replace('</dialog>', '</dialog>\n<main id="main-content">', 1)
    html = html.replace('<footer ', '</main>\n<footer ', 1)
    if p.name == 'index.html':
        html = html.replace('preload="metadata"', 'preload="none"')
        html = html.replace('  <link rel="stylesheet" href="./site-fonts.css"/>', '  <link rel="stylesheet" href="./site-fonts.css"/>\n  <link rel="preload" as="image" href="./Assets/neucockpit-film-poster.webp" fetchpriority="high"/>')
        html = html.replace('max-w-[1120px] mx-auto reveal py-4', 'max-w-[1120px] mx-auto py-4')
    p.write_text(html, encoding='utf-8', newline='\n')
