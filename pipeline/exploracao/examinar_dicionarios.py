import zipfile
from pathlib import Path

path=Path('dados/datasus/documentacao/Docs_TAB_SINAN.zip')
with zipfile.ZipFile(path) as z:
    for name in z.namelist():
        if any(x in name.lower() for x in ['anim', 'deng', 'pecon', 'peç']):
            print(name)
            if name.lower().endswith(('.cnv','.def','.txt','.csv')):
                text=z.read(name).decode('cp1252',errors='replace')
                if any(x in text.upper() for x in ['ESCORP','ANT_DT_ACI','ANT_MUNIC_']):
                    print(text[:8000])
            elif name.lower().endswith('.pdf'):
                target=Path('dados/datasus/documentacao/dicionarios')/Path(name).name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(name))
