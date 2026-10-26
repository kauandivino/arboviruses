# Coleta automatizada SINAN / DATASUS

Coleta dengue e acidentes por animais peçonhentos entre 2022 e 2026 e produz recortes de Goiânia. O índice FTP é consultado em cada execução, sem presumir que um ano ainda não publicado esteja disponível.

## Executar

Usa o ambiente único do projeto, `.venv` (Python 3.13, com o conversor nativo `.dbc`; instalação no README da raiz). Na pasta do projeto:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_datasus
```

O ambiente precisa ser Python 3.10–3.13: o conversor não tem wheel Windows para 3.14. Para escolher anos:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_datasus --anos 2022 2023 2024 2025 2026
```

Somente download (não requer bibliotecas adicionais):

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_datasus --somente-baixar
```

Reprocessar arquivos locais sem conexão:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_datasus --processar-local
```

Também aceita `--anos`, `--agravos dengue animais`, `--saida`, `--atualizar` e `--manter-dbf`. O recorte padrão é exclusivamente Goiânia, código SINAN `520870` (IBGE `5208707`). Se usar `--municipio` para outro município, indique também outra pasta `--saida`, pois a pasta padrão se chama `goiania`.

## Arquivos produzidos

- `dados/datasus/originais/dengue/DENGBR*.dbc`: arquivos nacionais de dengue, sem alteração.
- `dados/datasus/originais/animais/ANIMBR*.dbc`: arquivos nacionais de acidentes por todos os animais peçonhentos.
- Cada original tem um recibo `.json` com origem, tamanho, data do servidor e SHA-256.
- `documentacao/`: pacote oficial de dicionários `Docs_TAB_SINAN.zip` e procedimentos de acesso/conversão.
- `goiania/dengue_<ano>.csv`: registros com residência **ou** notificação em Goiânia (e ocorrência se o campo existir).
- `goiania/animais_<ano>.csv`: todos os tipos de animais, com a mesma regra territorial, incluindo município de ocorrência quando disponível.
- `goiania/escorpioes_<ano>.csv`: subconjunto de `animais`, `TP_ACIDENT = 3`, confirmado no campo 45 de `ANIMPN_DIC_DADOS.pdf` (2 corresponde a aranhas). Não inclui avistamentos ou capturas sem acidente notificado.
- `resumos/*_mensal.csv`: contagens de registros por mês, referência geográfica, campo de data e códigos de classificação, critério e evolução. Nos resumos de animais entram apenas escorpiões.
- `qualidade/*.json`: campos originais, contagens de entrada/saída, registros marcados como excluídos no DBF, datas ausentes/inválidas e hashes dos CSVs.
- `inventario.json`, `manifesto.json`, `ultima_execucao.json`: disponibilidade consultada, resultado dos downloads e falhas da execução mais recente. As mensagens de terminal indicam o progresso.

Os CSVs usam vírgula como separador e UTF-8 com BOM. Datas DBF são convertidas para `AAAA-MM-DD`. Os demais códigos permanecem como texto original, incluindo desconhecidos e não preenchidos. Não são transformados em números para evitar perder zeros ou misturar códigos com medidas.

## Como usar os recortes corretamente

As colunas acrescentadas `GOIANIA_RESIDENCIA`, `GOIANIA_NOTIFICACAO` e `GOIANIA_OCORRENCIA` indicam a relação do registro com a cidade. Não são três pessoas ou três acidentes distintos.

- Para estudar moradores: filtre `GOIANIA_RESIDENCIA = 1`.
- Para estudar notificações feitas na cidade: filtre `GOIANIA_NOTIFICACAO = 1`.
- Para estudar acidentes ocorridos na cidade: filtre `GOIANIA_OCORRENCIA = 1`, quando o campo existir.

Nas bases ANIMBR verificadas, o município do acidente é `ANT_MUNIC_` e a data do acidente é `ANT_DT_ACI`. O script identifica esses campos e registra o mapeamento em `qualidade/*.json`; também reconhece os aliases `ID_MUN_OCOR` e `DT_ACID` se surgirem em outra versão. A ausência dos campos essenciais interrompe o processamento do arquivo.

Nos resumos, escolha **uma** referência geográfica e **um** campo de data antes de somar. O mesmo registro pode aparecer em várias referências e campos de data. `SEM_DATA_VALIDA` preserva registros sem data utilizável; ausência de uma linha mensal não é automaticamente zero.

As contagens de dengue são de registros de notificação, separados pelos códigos originais. Não representam automaticamente casos confirmados, pessoas únicas ou incidência. Classificação/critério/evolução precisam ser interpretados conforme o dicionário. Não houve deduplicação epidemiológica de notificações nem cálculo de taxas. A extração preserva os marcadores de duplicidade que existirem na fonte.

O ano do arquivo é o agrupamento de publicação do SINAN, não um filtro adicional sobre todas as datas. Os CSVs preservam as datas e o ano informado em cada registro. Comparações com boletins municipais podem divergir por versão, data de fechamento, critérios e referência territorial.

## Atualização e validação

Downloads usam duas conexões FTP anônimas e até três tentativas. O tamanho e a data do arquivo remoto são conferidos antes/depois da transferência; SHA-256 verifica a integridade local nas execuções seguintes. Arquivos parciais podem ser retomados se a identidade remota não mudou. Fontes com data/tamanho alterados são baixadas novamente, e o processamento é invalidado pelo hash da fonte. O hash é calculado localmente; não é uma assinatura fornecida pelo Ministério.

O conversor expande um arquivo por vez e a leitura DBF filtra por município antes de decodificar todas as colunas. Somente o DBF temporário produzido é removido ao terminar; DBCs originais e CSVs são preservados. O DBF nacional de dengue de 2024 é grande: é necessário espaço temporário além dos aproximadamente 540 MB de download. O script estima o tamanho antes da expansão.

O script rejeita cabeçalhos inconsistentes, DBFs truncados e ausência de campos essenciais. Não promete dados por bairro: o recorte público municipal não substitui os dados locais necessários para escolher oito bairros prioritários. Dados em `PRELIM` e o ano corrente são parciais e sujeitos a revisão; `FINAIS` é o nome do diretório de publicação, não garantia de ausência de revisões futuras.

Testes locais:

```powershell
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_datasus
```

Conferência completa dos arquivos e reconciliação dos resultados de 2022–2026:

```powershell
& .venv/Scripts/python.exe -m pipeline.verificacao.validar_coleta_datasus
```

### Execução verificada em 19/10/2026

Foram baixadas e processadas as dez bases esperadas (cinco anos de cada agravo), somando 540,14 MB de DBCs nacionais, além da documentação. Foram gerados 15 CSVs locais (70,04 MB), dez resumos mensais e dez registros de qualidade. A validação de hashes, integridade do ZIP, filtros territoriais, seleção de escorpiões e reconciliação das contagens foi aprovada; resultado em `dados/datasus/validacao.json`. Nenhum DBF temporário permaneceu após o processamento.

No inventário consultado: dengue 2022–2025 e animais 2022 estavam em `FINAIS`; dengue 2026 e animais 2023–2026 estavam em `PRELIM`. Os recortes incluem registros relacionados ao município por qualquer referência identificada, e não somente moradores; filtre os indicadores descritos acima para cada análise.

## Fontes

- Índices oficiais: `ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/` e `.../PRELIM/`.
- Documentação: `ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DOCS/`.
- [Transferência de arquivos DATASUS](https://datasus.saude.gov.br/transferencia-de-arquivos/).
- [Orientação oficial sobre microdados e desagregação municipal](https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/svsa/agravos-de-notificacoes/agravos-de-notificacoes).
- [Catálogo oficial de dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue).

A API de dengue foi inspecionada, mas não é usada na coleta principal: seu parâmetro `id_municip` filtra município notificador, o que não garante captar todos os residentes de Goiânia. Os arquivos nacionais permitem aplicar os critérios geográficos separadamente.
