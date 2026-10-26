# Extração dos informes municipais

A etapa posterior de conferência visual e correspondência nominal dos bairros está documentada em [REVISAO-TERRITORIAL.md](REVISAO-TERRITORIAL.md). Ela produz uma base revisada separada, com 360 observações, preservando esta extração automática e suas pendências originais.

O script `extrair_informes.py` lê os PDFs locais de 2022–2026 e produz contagens rastreáveis ao arquivo, SHA-256, URL, página e quadro/gráfico de origem. Não precisa baixar novamente os boletins nem enviar PDFs a serviços externos.

```powershell
& '.venv-datasus/Scripts/python.exe' extrair_informes.py
& '.venv-datasus/Scripts/python.exe' verificar_extracao_informes.py
& '.venv-datasus/Scripts/python.exe' validar_extracao_informes.py
```

O ambiente do projeto já está preparado. Para outro ambiente, instale `requirements-extracao-informes.txt`. É possível selecionar `--anos 2024 2026`, mudar `--entrada` e `--destino` ou desativar OCR com `--sem-ocr`. O validador usa o destino padrão.

## O que é interpretado

- Tabelas com bairro de residência e três colunas explicitamente identificadas como casos notificados, prováveis e confirmados, respeitando a ordem do cabeçalho.
- Gráficos de barras por bairro com valores impressos e rótulos inclinados. Os valores são lidos do texto vetorial do PDF, associados por posição. Não se estimam números a partir da altura das barras.
- As três contagens iniciais dos quadros históricos intitulados “Demonstrativo da situação epidemiológica de dengue”: notificados, confirmados e prováveis, por ano. As taxas e proporções desses quadros não são interpretadas nesta versão.
- Quadros comparativos de dengue/chikungunya com dois anos identificados e quatro colunas de contagens (notificados e confirmados por ano), mantendo o corte “até SE” quando expresso.

Outros quadros, tabelas e gráficos ficam inventariados e preservados como blocos de texto para revisão, **sem serem apresentados como indicadores já interpretados**. Não há extrator universal para qualquer diagrama, mapa, gráfico ou página digitalizada. Uma falha de interpretação gera pendência; um PDF que não pôde ser processado gera código de saída diferente de zero.

A ordem interna dos objetos do PDF pode colocar o corpo de uma tabela depois da legenda de outro gráfico. Por isso os extratores municipais reconhecidos examinam as linhas da página completa; os blocos brutos não representam necessariamente recortes geométricos de tabelas. `texto_pagina_arquivo` aponta para o JSON com o texto integral e a página correspondente.

## Arquivos em `dados/informes_extraidos/`

| Arquivo | Conteúdo |
| --- | --- |
| `bairros.csv` | Contagens territoriais extraídas, inclusive as pendentes de revisão |
| `municipio.csv` | Contagens anuais municipais, mantendo cada edição separada |
| `observacoes.csv` | União dos dois arquivos, uma linha por indicador/território/período/publicação |
| `elementos.csv` | Elementos identificados, situação de extração e erros |
| `elementos_brutos.jsonl` | Texto bruto de cada elemento com a origem |
| `documentos.csv` | Conteúdo único, páginas, ano/pasta, metadados internos e classificação |
| `arquivos_origem.csv` | Todos os arquivos e URLs, inclusive cópias de conteúdo idêntico |
| `cobertura_por_ano.csv` | Disponibilidade encontrada nas pastas de cada ano; não é cobertura de todos os bairros |
| `revisar.csv` | Falhas de extração, páginas com pouco texto e menções territoriais sem tabela/gráfico identificado |
| `bairros_revisar.csv` | Observações territoriais com nome de OCR, período ambíguo ou outro alerta |
| `qualidade.json` | Contagens e limitações mensuradas |
| `manifesto_extracao.json` | Fontes e hashes dos produtos |
| `validacao.json` | Resultado das verificações técnicas |
| `textos_pdfium/` | Texto por página, com cache baseado no SHA-256 |
| `ocr/` | Recortes dos gráficos, nomes rotacionados, saída bruta e resultados do OCR local |

Colunas principais: `bairro`, `agravo`, `indicador`, `valor_original`, `valor`, `ano_referencia`, `se_inicio`, `se_fim`, `natureza_temporal`, `periodo_original`, `arquivo_pdf`, `sha256`, `pagina`, `url_pagina`, `titulo_original`, `metodo`, `status_revisao` e `alertas`. Nos gráficos também há coordenadas de leitura (`bbox_*`, em pontos PDF, origem inferior esquerda). O número da página começa em 1.

## Períodos e duplicidades

Uma legenda com “últimas 4 semanas (SE 35 a 38)” é uma **janela móvel**, não um total anual nem quatro observações semanais separadas. Janelas consecutivas se sobrepõem e não devem ser somadas. O script não calcula diferenças entre edições, pois revisões e mudanças no conjunto de bairros impedem interpretar essas diferenças automaticamente como novos casos.

Um título que informa apenas “Goiânia, 2024” fica com natureza temporal não explícita. O número da edição ou a semana exibida no cabeçalho não é usado para preencher automaticamente o período daquela tabela. Os quadros por ano são classificados como acumulados anuais com corte não explícito; não são ocorrências da semana de publicação. Não há conversão de semanas epidemiológicas para datas civis nesta etapa.

Inconsistências são preservadas: por exemplo, “últimas 4 semanas (SE 32 a 36)” mantém 32–36 e recebe um alerta. Não se corrige a fonte silenciosamente. Símbolos de ausência/supressão não viram zero. O ano da pasta pode diferir do ano interno do documento.

Somente cópias binárias idênticas (mesmo SHA-256) são processadas uma vez; seus caminhos e URLs ficam registrados. Edições com revisões, mesmo que repitam valores, permanecem separadas. `grupo_observacao` ajuda a localizar observações potencialmente relacionadas, mas não comprova equivalência temporal quando o corte é desconhecido. Todos os registros têm `pode_somar_entre_boletins=False`.

## OCR e uso territorial

Alguns nomes estão desenhados como contornos e não têm texto extraível. Nesses casos, o gráfico é renderizado localmente, os nomes são rotacionados e lidos com RapidOCR. Os números continuam vindo do texto vetorial. Recortes e saída bruta são salvos; os nomes não são corrigidos automaticamente por aproximação com outro cadastro. Confiança do modelo não equivale a probabilidade de acerto. Todos os registros com nomes de OCR ficam pendentes de conferência visual.

`checagens_automaticas_aprovadas` significa aprovação das regras de leitura e do período, não homologação epidemiológica. `pendente` conserva os dados, mas exige conferir os motivos em `alertas`. A validação técnica não elimina essas pendências e não certifica os nomes reconhecidos por OCR.

As listas publicadas por bairro não comprovam exaustividade. Um bairro ausente não tem valor zero; a soma dos bairros exibidos não equivale ao total municipal. As grafias originais são mantidas e não são automaticamente vinculadas ao SIGGO ou aos setores do IBGE. A coleta, por si só, não permite construir um ranking comparável de todos os bairros ou selecionar definitivamente os oito prioritários.

O diagnóstico de disponibilidade e das bases municipais ainda necessárias é produzido em `diagnostico_cobertura.md`. Os anos da tabela de cobertura são os das pastas de coleta; consulte `ano_boletim` e `ano_referencia` antes de interpretar o período dos dados.

## Execução de 19/10/2026

Foram lidos 238 arquivos locais, com 237 conteúdos distintos. A execução gerou 4.265 observações de indicadores: 3.957 municipais e 308 por bairro. São observações de publicações, com repetições/revisões, e não pessoas ou casos únicos.

As observações por bairro vêm de quatro tabelas em dois PDFs da pasta 2024 (120 observações de dengue/chikungunya) e de 19 gráficos da pasta 2026 (188 observações de dengue). Outros cinco gráficos de 2026 ficaram sem extração estruturada por falta de associação unívoca de nome/número; seus recortes e erros foram preservados para revisão. Portanto, os totais de extração não equivalem a tudo que está disponível visualmente nos PDFs.

Nos gráficos interpretados, 170 nomes foram obtidos por OCR e 18 por texto vetorial. Todas as 120 observações territoriais de 2024 têm corte temporal não explícito. As 18 observações vetoriais de 2026 passaram pelas checagens automáticas; as outras 290 observações territoriais permanecem pendentes por OCR/período. Os quadros municipais também mantêm suas pendências de corte temporal.

Os nove testes passaram. A validação real conferiu hashes, páginas, chaves, conservação dos arquivos derivados, linhas de origem e os 188 números dos gráficos novamente nas coordenadas dos PDFs. O resultado é aprovação técnica com pendências semânticas explícitas, e não liberação de todas as observações para comparação epidemiológica.
