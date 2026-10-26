from pathlib import Path
import json
from pipeline.coleta.baixar_malha_municipal import get,LAYER,FIELDS

ids=json.loads(Path('dados/malha_municipal/inspecao/bairros_ids.json').read_text())['objectIds']
probes=[
    {'objectIds':','.join(map(str,sorted(ids)[:200])),'outFields':'OBJECTID,id,tp_bai,nm_bai,nm,id_mun','returnGeometry':'true','outSR':'4326','f':'geojson'},
    {'objectIds':str(ids[0]),'outFields':','.join(FIELDS),'returnGeometry':'true','outSR':'4326','f':'geojson'},
    {'objectIds':','.join(map(str,sorted(ids)[:200])),'outFields':'OBJECTID,id,tp_bai,nm_bai,nm,id_mun','returnGeometry':'true','outSR':'31982','f':'json'},
    {'objectIds':','.join(map(str,sorted(ids)[:200])),'outFields':','.join(FIELDS),'returnGeometry':'true','outSR':'31982','f':'json'},
]
for i,params in enumerate(probes):
    raw,receipt=get(LAYER+'/query',params)
    Path(f'dados/malha_municipal/inspecao/query_{i}.json').write_bytes(raw)
    obj=json.loads(raw)
    print(i,list(obj),obj.get('error'),'features',len(obj.get('features',[])),flush=True)
