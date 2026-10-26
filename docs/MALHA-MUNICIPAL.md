# Malha municipal de Goiânia — SIGGO

O script `pipeline/coleta/baixar_malha_municipal.py` baixa a camada pública **Divisas de Bairro** do serviço oficial da Prefeitura/SIGGO, exporta os mapas e confere a compatibilidade espacial com os setores do Censo 2022 já obtidos.

Essa é uma fonte municipal complementar à malha do IBGE, que não contém bairros de Goiânia. A documentação do SIGGO descreve a entidade como **divisas de loteamentos**. Sua equivalência com os bairros usados pela Secretaria de Saúde ainda precisa ser conferida.

## Uso

O ambiente do projeto já contém as dependências de `requirements.txt`.

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_malha_municipal
```

O comando baixa a fonte, gera os mapas, cruza com os setores IBGE e executa a validação. Para reprocessar a última coleta sem acessar a rede:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_malha_municipal --processar-local
```

Outras opções:

- `--somente-baixar`: preserva as respostas da API, sem gerar mapas/cruzamentos.
- `--lote 200`: quantidade de OIDs solicitados por página; aceita de 1 a 500.
- `--saida CAMINHO`: pasta de saída; padrão `dados/malha_municipal`.
- `--setores CAMINHO`: malha de setores de Goiânia; padrão `dados/ibge/goiania/setores_goiania_2022.gpkg`.

Cada execução com rede cria uma nova pasta de coleta, com data/hora UTC e sufixo único, para preservar as versões anteriores. O script usa consultas públicas de leitura; não altera o serviço municipal. Em outro ambiente Python 3.13, instale `requirements.txt` antes de processar.

## Como a coleta funciona

Fonte:

```text
https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/MapServer/2
```

O script consulta metadados, contagem e lista completa de OIDs. Faz consultas em lotes por OID, exigindo que cada resposta contenha exatamente os identificadores pedidos, sem repetição ou indicação de truncamento. Ao terminar, confere novamente a lista de OIDs.

As consultas em lote no formato GeoJSON retornaram erro na inspeção. A coleta usa o **JSON geográfico nativo do ArcGIS, em EPSG:31982**, e faz a conversão local com GDAL/pyogrio. Os campos cartográficos são solicitados explicitamente; o esquema do serviço também contém nomes duplicados e campo calculado. Não são obtidas fotos, anexos ou todas as tabelas relacionadas.

Os campos solicitados incluem OID, identificador municipal, nomes/abreviações, qualificação, município/região/macrozona, indicador de condomínio e data de última edição, quando presentes. Os campos estatísticos `pop_total`, `pop_masc` e `pop_fem` não são utilizados nem solicitados: a referência temporal dessa população não está estabelecida para nosso projeto.

A API não oferece um snapshot transacional nesta rotina. A conferência dos OIDs identifica inclusões/exclusões durante a transferência, mas não garante detectar uma edição geométrica feita no mesmo OID entre consultas. A data de captura é registrada; ela não equivale à vigência legal dos limites nem transforma a malha em uma versão histórica de 2022.

## Arquivos

Em `dados/malha_municipal/`:

- `originais/<coleta>/`: metadados, listas de OIDs, contagem, páginas JSON originais, documentação e arquivo combinado `bairros_siggo.esri.json`.
- `manifesto.json`: aponta para a última coleta completa e registra URLs, parâmetros, horários UTC, cabeçalhos, tamanhos e hashes SHA-256.
- `qualidade_malha.json`: geometrias inválidas, reparos, identificadores repetidos e hashes dos mapas exportados.
- `compatibilidade_ibge.json`: cobertura por área e situação urbana/rural, critérios e contagem dos resultados.
- `validacao.json`: resultado das verificações dos originais, mapas e interseções.

Pastas de tentativas interrompidas podem permanecer em `originais/`. Somente as que possuem manifesto completo representam uma coleta concluída; o manifesto da raiz aponta para a última coleta concluída.

Em `goiania/`:

- `bairros_municipais_siggo.gpkg`, `.geojson` e `.csv`: geometria/atributos da fonte exportados localmente, com indicadores acrescentados. O GeoPackage permanece no CRS nativo; o GeoJSON usa EPSG:4326.
- `bairros_municipais_analise.gpkg`, `.geojson` e `.csv`: cópia para análise, com reparo de geometrias inválidas explicitamente documentado.
- `intersecoes_setores_bairros.csv`: todos os pares setor–feição com interseção superior a 1 m²; contém área e fração do setor.
- `diagnostico_setores_bairros.csv`: uma linha por setor, com cobertura pela união das feições, soma de frações, sobreposição e situação da associação.

`OID_SIGGO` identifica uma feição da captura e é usado no cruzamento. `ID_SIGGO` preserva o código municipal, sem tratá-lo como código IBGE. Identificadores municipais repetidos não são eliminados. `NOME_SIGGO` usa o nome `nm`, quando preenchido, ou tipo + nome (`tp_bai` + `nm_bai`) como alternativa; os campos de origem permanecem disponíveis.

## O que o cruzamento significa

As áreas são calculadas em EPSG:31982. O script não distribui pessoas por área nem agrega indicadores censitários por bairro.

| Situação | Interpretação |
|---|---|
| `candidato_um_poligono_99pct` | Uma feição cobre pelo menos 99% do setor, com cobertura conjunta de pelo menos 99% e sobreposição entre feições de no máximo 1%. É candidato para revisão. |
| `setor_cruza_poligonos` | O setor coberto atravessa divisas; não recebeu candidato único. |
| `cobertura_parcial` | A união das feições cobre menos de 99% da área do setor. |
| `sem_intersecao_acima_tolerancia` | Nenhum par supera o limiar de 1 m². |
| `sobreposicao_entre_poligonos` | A soma das interseções excede a cobertura pela união em mais de 1% da área do setor. |

A cobertura parcial tem precedência sobre o alerta de sobreposição no rótulo principal; os valores numéricos de ambas ficam registrados. A tabela de interseções pode conter vários bairros/loteamentos para o mesmo setor. Somar população depois de um join direto com essa tabela duplicaria pessoas.

Não houve atribuição por centroide, escolha obrigatória do maior polígono, rateio de população ou equivalência automática com bairros de notificações de saúde. Mesmo um candidato com 99% da área precisa ser tratado como correspondência geométrica aproximada: população não se distribui uniformemente no território, e os limites municipais atuais podem diferir dos de 2022.

## Resultado da execução de 19/10/2026

Foram recebidas **1.208 de 1.208 feições** anunciadas pela API e analisados os **2.310 setores de Goiânia**. Os três testes locais passaram, e a validação real foi aprovada com limitações.

| Resultado | Quantidade |
|---|---:|
| Pares de interseção acima de 1 m² | 6.462 |
| Setores com candidato geométrico de 99% | 1.305 |
| Setores que cruzam divisas | 783 |
| Setores com cobertura parcial | 219 |
| Setores sem interseção acima da tolerância | 3 |

Cobertura por área, utilizando a união das feições para não contar sobreposições duas vezes:

- **92,75% da área dos 2.291 setores urbanos** do IBGE.
- **10,25% da área dos 19 setores rurais**.
- **60,07% da área total do município**, conforme a união dos setores do IBGE.

Esses percentuais são de **área**, não de moradores, domicílios ou casos de doença. A fonte cobre boa parte da área urbana, mas não é uma partição completa do município. Também foram medidos aproximadamente 0,073 km² de polígonos fora do limite formado pelos setores IBGE, preservados e registrados como diferença entre as fontes.

Havia uma geometria inválida na origem, OID 1112. Ela foi preservada no original e reparada com `make_valid` somente na cópia de análise; componentes não poligonais são descartados nessa preparação. Nenhuma feição precisou ser excluída. Um identificador municipal repetido foi mantido e listado para revisão em `qualidade_malha.json`.

Foram validados hashes, OIDs e contagens, mapas exportados, validade das geometrias de análise, códigos de todos os setores e áreas dos 6.462 pares, recalculadas a partir das geometrias. A aprovação técnica não resolve as limitações de cobertura ou de equivalência com a divisão territorial da Saúde.

Para repetir:

```powershell
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_malha_municipal
& .venv/Scripts/python.exe -m pipeline.verificacao.validar_malha_municipal
```

## Fontes oficiais

- [Camada Divisas de Bairro](https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/MapServer/2).
- [Metadados da camada em JSON](https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/MapServer/2?f=pjson).
- [Documentação SIGGO da entidade Divisas de Bairro](https://portalmapa.goiania.go.gov.br/helpsiggo/HelpSIGGO/bai.htm).

Os setores e as estatísticas do Censo permanecem separados em `dados/ibge/`; sua coleta está documentada em `IBGE.md`.
