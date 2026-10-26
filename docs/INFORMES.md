# Download dos informes de Goiânia

Visão geral do projeto e comando único: [README da raiz](../README.md).

Para a conferência visual dos informes, a base territorial revisada e os candidatos de correspondência dos bairros ao SIGGO, consulte [REVISAO-TERRITORIAL.md](REVISAO-TERRITORIAL.md). A minuta do pedido de dados agregados está em [SOLICITACAO-DADOS-SAUDE.md](SOLICITACAO-DADOS-SAUDE.md).

Para extrair contagens dos PDFs já baixados, consulte [EXTRACAO-INFORMES.md](EXTRACAO-INFORMES.md). O script `pipeline/processamento/extrair_informes.py` registra bairro, período, indicador, valor e página de origem, com pendências explícitas para OCR e períodos ambíguos.

Para localização e endereço dos estabelecimentos de saúde de Goiânia, consulte [CNES.md](CNES.md). O script `pipeline/coleta/baixar_cnes.py` descobre a competência mais recente da base oficial e gera CSV, GeoJSON e GeoPackage com indicadores de qualidade.

Para chuva, temperatura e umidade da estação automática de Goiânia (INMET A002), consulte [INMET.md](INMET.md). O script `pipeline/coleta/baixar_inmet.py` coleta 2022–2026 e gera séries horárias e resumos com indicadores de cobertura.

Para a coleta estruturada de dengue e acidentes por escorpiões do SINAN/DATASUS, consulte [DATASUS.md](DATASUS.md). O script correspondente é `pipeline/coleta/baixar_datasus.py` e usa um ambiente separado, `.venv`.

Para população, domicílios, saneamento e malhas do Censo 2022, consulte [IBGE.md](IBGE.md). O comando único é `pipeline/coleta/baixar_ibge.py`, com scripts separados para agregados e malhas.

Para a camada municipal de bairros/loteamentos do SIGGO e o diagnóstico de cobertura dos setores do IBGE, consulte [MALHA-MUNICIPAL.md](MALHA-MUNICIPAL.md). O script é `pipeline/coleta/baixar_malha_municipal.py`.

O script consulta as páginas oficiais, executa o JavaScript da lista de 2026 e baixa os links de PDF encontrados. Por padrão, descobre os anos publicados no índice oficial, incluindo a página conjunta de 2012–2013. A organização acompanha o ano da página, que pode diferir do ano indicado no PDF.

## Instalação

Usa o ambiente único do projeto, `.venv` (instalação no README da raiz), e o Microsoft Edge instalado.

Se preferir Chromium, instale-o com `.venv/Scripts/python.exe -m playwright install chromium` e acrescente `--canal chromium` aos comandos abaixo.

## Uso

Descobrir links de dois anos sem baixar PDFs:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_informes --anos 2026 2025 --listar
```

Baixar todos os anos encontrados no índice oficial:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_informes
```

Baixar apenas anos selecionados:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_informes --anos 2026 2025 2024 2023
```

Testar um único arquivo:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_informes --anos 2026 --limite 1
```

## Resultado e limites

- PDFs em `dados/informes/<ano>/`.
- `manifesto.csv` registra origem, arquivo, tamanho, hash, horário UTC e erros. É atualizado após cada arquivo para permitir retomada.
- `links_<ano>.json` e `pagina_<ano>.html` permitem conferir os links descobertos.
- URLs repetidas são deduplicadas. Arquivos existentes válidos são preservados; novas execuções procuram novos links. Revisões publicadas no mesmo endereço não são baixadas novamente automaticamente.
- O script verifica o início `%PDF-`; isso evita salvar páginas de erro como PDF, mas não substitui uma validação completa do documento.
- Falhas geram código de saída diferente de zero. Uma página sem links é tratada como erro, nunca como download completo.
- O alcance é a lista de PDFs exposta por cada página: não garante semanas ausentes no próprio site. A lista dinâmica pode exigir `--carregamento 60` em conexões lentas.
- Não extrai tabelas nem soma os indicadores dos boletins. Os valores podem ser acumulados e revisados entre edições.
- Erros 403, indisponibilidade do servidor e mudanças no site podem impedir a coleta. `--visivel` abre uma janela para diagnóstico.

Fonte: https://saude.goiania.go.gov.br/informe-dengue-chikungunya-zika-e-microcefalia/

## Verificação realizada

Em 19/10/2026: descoberta de 34 URLs únicas na página de 2026 e 53 na de 2025; download real de um PDF de 2026 com validação do cabeçalho; reexecução preservando o arquivo existente; verificações locais de extração HTML/JavaScript, normalização de URLs e gravação do manifesto. A coleta completa de todos os anos não foi executada. A quantidade representa links encontrados, não semanas ou conteúdo único validado.
