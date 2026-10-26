# Coleta IBGE — Censo 2022, Goiânia

Scripts para baixar os agregados definitivos do Censo 2022, a malha definitiva dos setores censitários e os respectivos dicionários. Os originais são preservados e os recortes utilizam Goiânia, código IBGE `5208707`.

**Todos os dados têm referência no Censo 2022. Uma revisão publicada em 2026 não transforma a população em uma estimativa de 2026.**

## Executar

O ambiente existente `.venv-datasus` foi preparado também com as bibliotecas do IBGE. Na pasta do projeto:

```powershell
& ./.venv-datasus/Scripts/python.exe baixar_ibge.py
```

O comando executa as duas coletas, os recortes e a validação final. Para executar separadamente:

```powershell
& ./.venv-datasus/Scripts/python.exe baixar_ibge_agregados.py
& ./.venv-datasus/Scripts/python.exe baixar_ibge_malhas.py
& ./.venv-datasus/Scripts/python.exe validar_ibge.py
```

Opções disponíveis nos comandos de coleta:

- `--somente-baixar`: obtém os originais, sem processar os dados.
- `--processar-local`: verifica hashes e processa os originais do último manifesto, sem rede.
- `--atualizar`: força a transferência dos originais.
- `--saida CAMINHO`: usa outra pasta de saída; padrão `dados/ibge`.

Para instalar em outro computador, use Python 3.13:

```powershell
py -3.13 -m venv .venv-ibge
& ./.venv-ibge/Scripts/python.exe -m pip install -r requirements-ibge.txt
& ./.venv-ibge/Scripts/python.exe baixar_ibge.py
```

O modo somente download usa apenas a biblioteca padrão do Python. Processamento e validação requerem as dependências listadas.

## Originais e versões

Os índices oficiais são consultados em cada download. Havendo arquivos datados para a mesma tabela, a versão com data mais recente no nome é selecionada. Correspondências ambíguas interrompem a coleta em vez de escolher silenciosamente.

Na execução de 19/10/2026, foram obtidos oito arquivos, totalizando 265,20 MiB:

| Arquivo | Versão selecionada |
|---|---|
| Agregados básicos por setor — Brasil | `Agregados_por_setores_basico_BR_20260520.zip` |
| Características dos domicílios — Parte 1 | `Agregados_por_setores_caracteristicas_domicilio1_BR.zip` |
| Características dos domicílios — Parte 2 | `Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.zip` |
| Características dos domicílios — Parte 3 | `Agregados_por_setores_caracteristicas_domicilio3_BR_20250417.zip` |
| Dicionário dos agregados | `dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx` |
| Malha definitiva de setores — Goiás | `GO_setores_CD2022.gpkg` |
| Malha de bairros — Goiás | `GO_bairros_CD2022.gpkg` |
| Dicionário da malha | `Dicionario_de_dados_malha_agregados.xlsx` |

Os originais ficam em `dados/ibge/originais/` e os dicionários em `dados/ibge/documentacao/`. Cada arquivo tem um recibo `.json` com URL, data de obtenção em UTC, metadados HTTP e SHA-256. Os manifestos agregam os resultados e eventuais erros de cada coleta.

Na reexecução, ETag/data/tamanho publicados e o hash local são conferidos para evitar download repetido. Downloads interrompidos podem ser retomados quando o servidor admite Range e a identidade remota permanece igual. Se o servidor ignorar Range, a transferência recomeça com segurança. O hash é calculado localmente; não é assinatura do IBGE. O processamento local é executado novamente, sem cache dos resultados derivados.

## Recortes e indicadores

Arquivos em `dados/ibge/goiania/`:

- `basico_setores_2022.csv`: população, domicílios e identificação territorial; 2.310 setores.
- `domicilio1_setores_2022.csv`, `domicilio2_setores_2022.csv`, `domicilio3_setores_2022.csv`: todas as variáveis das três partes para Goiânia; 2.304 setores em cada arquivo.
- `indicadores_prioritarios_setores_2022.csv`: 2.310 setores e 37 medidas selecionadas, além de identificação e ano de referência.
- `dicionario_indicadores_prioritarios.csv`: descrição oficial de cada medida e identificação da tabela de origem.
- `dicionario_variaveis.csv`: descrição das variáveis das tabelas coletadas.
- `setores_goiania_2022.gpkg` e `.geojson`: 2.310 polígonos. O CSV de mesmo nome contém os atributos territoriais sem geometria.
- `bairros_goiania_2022.gpkg`, `.geojson` e `.csv`: **vazios para Goiânia**, porque a fonte estadual do IBGE não contém bairros desse município.
- `correspondencia_setores_bairros_2022.csv`: situação da associação por código e, quando há cobertura, verificação geométrica. Nesta coleta, os 2.310 setores não têm código de bairro na malha.
- `cobertura_agregados_malha_2022.csv`: presença de cada setor nas tabelas e na malha, com população e total de domicílios do básico para inspeção.

As 37 medidas prioritárias cobrem população, totais de domicílios, domicílios particulares permanentes ocupados (DPPO), moradores dos DPPO, formas de abastecimento de água, água encanada, destinação do esgoto e destinação do lixo.

Os códigos permanecem os do IBGE: por exemplo, `V0001` no básico e `V00001` nas características domiciliares são variáveis distintas. As colunas do arquivo prioritário recebem o prefixo da tabela para impedir essa confusão. A descrição oficial completa acompanha cada medida. Não foram calculadas taxas ou percentuais adicionais: os denominadores devem corresponder ao universo de cada variável, sobretudo DPPO versus total de domicílios.

Os recortes normalizam os cabeçalhos para maiúsculas e o identificador `setor`/`CD_setor` para `CD_SETOR`. A correspondência da variável e o conteúdo das células são preservados. Os CSVs derivados usam vírgula como separador e UTF-8 com BOM; números com vírgula decimal permanecem como texto original. `X`, ponto, hífen e vazio não são substituídos por zero. Códigos territoriais são lidos como texto, sem notação científica.

Os atributos estatísticos eventualmente embutidos na malha são excluídos do recorte geográfico: as estatísticas devem vir dos agregados revisados, evitando misturar versões. O GeoPackage preserva o CRS da fonte, EPSG:4674; o GeoJSON é exportado em EPSG:4326.

## Cobertura e limites identificados

**A malha de bairros do IBGE para Goiás contém somente Pires do Rio e Posse nesta versão. Ela não fornece os bairros de Goiânia.** O arquivo de setores de Goiânia também não possui códigos de bairro preenchidos. Isso não significa que Goiânia não tenha bairros: para essa associação será necessária uma malha municipal compatível, obtida na Prefeitura/SIGGO, e sua correspondência com os territórios usados pela Saúde.

Foi adicionada uma coleta complementar da camada municipal do SIGGO, em pasta separada, sem substituir arquivos do IBGE. Consulte [MALHA-MUNICIPAL.md](MALHA-MUNICIPAL.md) para os mapas, a cobertura e os casos que exigem revisão. A camada municipal obtida tem cobertura parcial e não autoriza uma agregação direta de toda a população por bairro.

Não foi feita agregação por bairro, atribuição por centroide, rateio por área nem preenchimento de bairros sem fonte. A rotina de correspondência, quando houver bairros, confere códigos e a fração de área do setor contida no bairro declarado; divergências ficam registradas. Compatibilidade com bairros do IBGE não assegura equivalência com outra divisão territorial.

Os seis setores sem linha nas tabelas de características domiciliares são:

```text
520870705080044
520870705110010
520870705310053
520870705570036
520870705630078
520870705630084
```

No agregado básico, todos têm zero pessoas e zero domicílios. Eles foram preservados no arquivo básico, nos indicadores e na malha. As células de características domiciliares ausentes continuam vazias, sem inferência de valores.

## Validação realizada

Em 19/10/2026, os quatro testes locais passaram. A execução com os dados reais foi aprovada com as limitações de cobertura acima:

- Oito originais conferidos por hash, tamanho, CRC dos ZIPs/XLSX e integridade SQLite dos GeoPackages.
- 2.310 chaves do básico correspondem exatamente às 2.310 chaves da malha definitiva de Goiânia.
- Nenhuma geometria de setor nula, vazia ou inválida.
- CRS, município e ausência de códigos duplicados verificados.
- 37 medidas prioritárias reconciliadas célula a célula com os recortes, inclusive marcadores e ausências.
- Reexecução do comando único de download reutilizou os oito arquivos sem transferi-los novamente.

Resultados em `dados/ibge/validacao.json`, `qualidade_agregados.json` e `qualidade_malhas.json`.

Para repetir os testes:

```powershell
& ./.venv-datasus/Scripts/python.exe verificar_ibge.py
```

## Fontes oficiais

- [Agregados por setores censitários](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/).
- [Malhas definitivas do Censo 2022](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/).
- [Página das malhas de setores censitários](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/26565-malhas-).
