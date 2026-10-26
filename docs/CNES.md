# Estabelecimentos de saúde de Goiânia — CNES

O script coleta a base mensal pública oficial do DATASUS (`ftp.datasus.gov.br/cnes/BASE_DE_DADOS_CNES_AAAAMM.ZIP`) e o dicionário de dados. Descobre as competências publicadas e usa a maior por padrão. O recorte de Goiânia usa o prefixo municipal 520870 da chave `CO_UNIDADE`, confirmado por `CO_MUNICIPIO_GESTOR`; o código IBGE completo acrescentado é 5208707.

A [documentação do portal](https://wiki.saude.gov.br/cnes/index.php/Portal_CNES#Extra.C3.A7.C3.A3o) também descreve uma exportação de identificação, endereço e coordenadas por município. Na inspeção de 19/10/2026, o serviço de competências respondeu, mas o servidor de entrega `cnesdownload.datasus.gov.br` retornou timeout/503. Por isso esta implementação usa o FTP oficial, sem depender daquele servidor e sem consultar fichas uma a uma.

## Executar

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_cnes
```

Escolher competência:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_cnes --competencia 202609
```

Reprocessar sem rede:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_cnes --competencia 202609 --somente-processar
```

O ambiente existente já contém as dependências de `requirements.txt`. Para um ambiente novo, instale esse arquivo. O ZIP nacional de setembro/2026 tem aproximadamente 710 MiB; a extração é feita em blocos, sem carregar todas as tabelas nacionais em memória. A transferência tem retomada, tamanho e modificação remota registrados, CRC do ZIP e SHA-256. Reexecuções conferem identidade e hash antes de reutilizar arquivos. Falhas geram saída diferente de zero.

## Resultados

Em `dados/cnes/originais/`: base nacional intacta, dicionário e recibos. `competencias.json` registra as opções publicadas e `manifesto_AAAAMM.json` documenta a origem da competência coletada.

Em `dados/cnes/goiania/AAAAMM/`:

- `estabelecimentos.csv`: todos os registros municipais, inclusive sem coordenadas e com motivo de desativação.
- `estabelecimentos.geojson` e `.gpkg`: pontos com coordenadas numéricas dentro do domínio mundial. Incluem pontos fora de Goiânia, sinalizados, para que não desapareçam silenciosamente.
- `revisar_localizacao.csv`: coordenadas ausentes, não numéricas, fora do domínio, zeradas ou fora da malha municipal de referência.
- `qualidade.json`: contagens, referência geográfica e hashes das tabelas de domínio.
- `resumo_tipos.csv`: quantidade por tipo, com contagens de natureza pública e motivo de desativação preenchido.
- Tabelas oficiais de tipo de unidade, tipo de estabelecimento, natureza jurídica e motivo de desativação usadas para acrescentar as descrições.

Campos prioritários: CNES, nome fantasia, razão social, endereço completo, bairro cadastrado, CEP, telefone/e-mail cadastrais, tipo, natureza jurídica, gestão, motivo de desativação, coordenadas originais e numéricas e datas cadastrais. CNES/CEP permanecem texto. Os derivados não incluem CPF nem identificadores de usuários que fizeram atualizações; o ZIP oficial permanece intacto.

## Interpretação

A competência é uma fotografia cadastral; não prova que o estabelecimento esteja aberto, disponível para parceria ou atendendo ao SUS. O script mantém todos os motivos de desativação para inspeção, sem decidir atividade apenas pela presença na base. Gestão municipal/estadual não equivale à propriedade pública; a coluna `natureza_administracao_publica` usa exclusivamente o grupo 1 da natureza jurídica e não constitui seleção final de parceiros.

`TP_UNIDADE` e `CO_TIPO_ESTABELECIMENTO` são classificações distintas e recebem descrições separadas. `CO_TIPO_UNIDADE` é preservado sem substituir uma pela outra. Códigos não encontrados nas tabelas conservam o valor original e ficam sem descrição.

As coordenadas não são invertidas, corrigidas ou completadas por geocodificação. A exportação geográfica interpreta latitude/longitude decimais em EPSG:4326 para visualização; o referencial de precisão do levantamento cadastral não foi auditado. Quando disponível, a união dos setores do Censo 2022 de Goiânia é usada como conferência espacial, com fonte e hash registrados. Estar dentro do município não comprova a posição exata da unidade. Pontos compartilhados são sinalizados, sem deduplicação, pois várias unidades podem ocupar o mesmo endereço.

O bairro informado no endereço é preservado; não é vinculado automaticamente à camada de loteamentos SIGGO nem aos setores do IBGE. Nenhum endereço é usado como localização substituta para coordenadas ausentes. Antes de planejar visitas, conferir os registros selecionados e seus contatos.

## Verificação

```powershell
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_cnes
& .venv/Scripts/python.exe -m pipeline.verificacao.validar_cnes --competencia 202609
```

Os testes cobrem ausências, vírgula decimal, limites e coordenadas zeradas. A validação confere hashes, chaves únicas, município, competência e conservação dos registros nos arquivos tabulares e geográficos. Não atesta a precisão dos dados cadastrais.

## Coleta realizada em 19/10/2026

Competência **09/2026**, com **5.184 estabelecimentos** de Goiânia extraídos de 640.122 registros nacionais. A base inclui consultórios e estabelecimentos privados; não é uma lista restrita às unidades públicas.

| Conferência de localização | Registros |
| --- | ---: |
| Coordenadas dentro da malha municipal de 2022 | 4.902 |
| Sem coordenadas | 155 |
| Coordenadas numéricas fora da malha de 2022 | 127 |

Os 282 registros dos dois últimos grupos estão em `revisar_localizacao.csv`. Há 711 registros com motivo de desativação preenchido, 260 com natureza jurídica do grupo administração pública e 177 com coordenadas compartilhadas. Esses conjuntos podem se sobrepor.

Todos os códigos preenchidos de tipo de unidade, tipo de estabelecimento, natureza jurídica e motivo de desativação foram encontrados nos respectivos domínios oficiais. Foram identificados 107 cadastros do tipo centro de saúde/unidade básica, dos quais 19 têm motivo de desativação preenchido; isso não comprova a situação operacional dos demais.
