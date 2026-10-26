import ftplib
with ftplib.FTP('ftp.datasus.gov.br', timeout=30) as ftp:
    ftp.login()
    for folder in ['/dissemin/publicos/SINAN', '/dissemin/publicos/SINAN/DADOS', '/dissemin/publicos/SINAN/DOCS', '/dissemin/publicos/SINAN/DADOS/FINAIS','/dissemin/publicos/SINAN/DADOS/PRELIM']:
        try:
            ftp.cwd(folder)
            names=ftp.nlst()
            if folder.endswith(('FINAIS','PRELIM')):
                ftp.voidcmd('TYPE I')
                names=[(n,ftp.size(n)) for n in names if n.upper() in {f'{p}{y}.DBC' for p in ['DENGBR','ANIMBR'] for y in range(22,27)}]
            print(folder,names,flush=True)
        except Exception as e: print(folder,str(e),flush=True)
