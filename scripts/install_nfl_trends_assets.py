#!/usr/bin/env python3
from pathlib import Path
path=Path('index.html');text=path.read_text(encoding='utf-8')
if 'href="trends.css"' not in text:
 needle='  <link rel="stylesheet" href="redesign-extra.css">\n'
 if needle not in text:raise SystemExit('Could not find CSS insertion point')
 text=text.replace(needle,needle+'  <link rel="stylesheet" href="trends.css">\n',1)
if 'src="trends.js"' not in text:
 needle='<script src="redesign.js" defer></script>\n'
 if needle not in text:raise SystemExit('Could not find JS insertion point')
 text=text.replace(needle,needle+'<script src="trends.js" defer></script>\n',1)
path.write_text(text,encoding='utf-8');print('NFL trends assets installed')
