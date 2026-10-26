import json
import re
from pathlib import Path

s = Path('dados/datasus/inspecao/dengue_pagina.txt').read_text(encoding='utf-8')
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', s)
if m:
    obj = json.loads(m[1])
    Path('dados/datasus/inspecao/catalogo.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    print('NEXT keys', obj.keys())
else:
    print(s[-1500:])
schema = json.loads(Path('dados/datasus/inspecao/api_schema.txt').read_text(encoding='utf-8'))
print('API server', schema.get('servers'), schema.get('host'), schema.get('basePath'))
for path, info in schema.get('paths', {}).items():
    if any(x in path.lower() for x in ['dengue', 'pecon', 'animais']):
        print(path, json.dumps(info, ensure_ascii=False)[:16000])
