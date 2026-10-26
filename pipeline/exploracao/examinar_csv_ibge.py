from pathlib import Path
import zipfile
for p in Path('dados/ibge/originais').glob('*.zip'):
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            if name.lower().endswith('.csv'):
                with z.open(name) as f:
                    raw=f.read(1500)
                print(p.name,repr(raw[:900]),flush=True)
