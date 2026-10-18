#!/usr/bin/env python3
from pathlib import Path

path = Path('index.html')
text = path.read_text(encoding='utf-8')
css = '  <link rel="stylesheet" href="trends.css">\n'
js = '<script src="trends.js" defer></script>\n'
if 'href="trends.css"' not in text:
    needle = '  <link rel="stylesheet" href="redesign-extra.css">\n'
    if needle not in text:
        raise SystemExit('Could not find CSS insertion point in index.html')
    text = text.replace(needle, needle + css, 1)
if 'src="trends.js"' not in text:
    needle = '<script src="redesign.js" defer></script>\n'
    if needle not in text:
        raise SystemExit('Could not find JS insertion point in index.html')
    text = text.replace(needle, needle + js, 1)
path.write_text(text, encoding='utf-8')
print('NFL trends assets installed in index.html')
