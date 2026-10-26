"""Consulta metadados e contagem da camada pública de bairros do SIGGO."""
import json
from pathlib import Path
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT='https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/'
URLS={
    'camada_bairros':ROOT+'Feature_Base/MapServer/2?f=pjson',
    'bairros_contagem':ROOT+'Feature_Base/MapServer/2/query?where=1%3D1&returnCountOnly=true&f=pjson',
    'bairros_ids':ROOT+'Feature_Base/MapServer/2/query?where=1%3D1&returnIdsOnly=true&f=pjson',
    'limites':ROOT+'Mapa_Limites/MapServer?f=pjson',
}

def inspect(item):
    name,url=item
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=45) as r:
            data=r.read()
        p=Path('dados/malha_municipal/inspecao')
        p.mkdir(parents=True,exist_ok=True)
        (p/(name+'.json')).write_bytes(data)
        obj=json.loads(data)
        if name=='camada_bairros':
            print(name,json.dumps({k:obj.get(k) for k in ['name','geometryType','objectIdField','maxRecordCount','extent','fields','advancedQueryCapabilities','editingInfo']},ensure_ascii=False),flush=True)
        elif name=='bairros_ids':
            print(name,'ids',len(obj.get('objectIds') or []),'error',obj.get('error'),flush=True)
        else:
            print(name,json.dumps(obj,ensure_ascii=False)[:6000],flush=True)
    except Exception as exc:
        print(name,str(exc),flush=True)

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(inspect,URLS.items()))
