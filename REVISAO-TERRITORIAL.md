# Revisão dos informes e correspondência dos bairros

A revisão conferiu visualmente os **24 gráficos por bairro de 2026** e as **quatro tabelas por bairro das edições 09 e 10/2024** já identificadas na extração. A base resultante contém **360 observações**, ante 308 na extração automática: foram recuperados os cinco gráficos pendentes e duas barras omitidas no gráfico da edição 26/2026. Esses números são observações de indicadores publicados, não pessoas distintas.

A revisão foi feita pelo assistente a partir de recortes renderizados dos PDFs originais. Não representa homologação da Secretaria de Saúde. Cada transcrição registra PDF, URL, SHA-256, página, elemento, posição na tabela/gráfico, legenda e imagem de conferência. Os dados brutos e a extração anterior permanecem separados.

## Arquivos para consultar

Em `dados/revisao_territorial/`:

- `revisao_territorial.xlsx`: base revisada, correspondências, candidatos, pendências e auditoria, em abas separadas.
- `base_territorial_revisada.csv`: 240 observações de gráficos de dengue de 2026 e 120 observações das tabelas de dengue/chikungunya de 2024.
- `correspondencia_bairros.csv`: uma linha por rótulo revisado, com situação nominal, publicações e pergunta para a Saúde.
- `candidatos_siggo.csv`: alternativas de polígonos, em tabela separada para não multiplicar contagens de saúde.
- `pendencias_territoriais.csv`: rótulos que não permitem candidato nominal único por normalização controlada.
- `observacoes_com_pendencias.csv`: observações com pendências nominais, de período ou de coerência da fonte.
- `auditoria_revisao.csv`: comparação por elemento com a extração anterior e registros recuperados.
- `inconsistencias_fonte.csv`: pontos de esclarecimento, incluindo sete linhas de chikungunya e três questões entre edições.
- `lista_lacunas_para_sms.csv`: lista objetiva dos dados e esclarecimentos necessários.
- `conferencia/`: recortes individuais e pranchas usados na leitura visual.
- `qualidade.json`, `manifesto.json`, `validacao.json`: resultados e procedência.

O texto para encaminhamento está em [SOLICITACAO-DADOS-SAUDE.md](SOLICITACAO-DADOS-SAUDE.md).

## Correspondência nominal e limites

Há **53 grafias/rótulos distintos** na revisão. **37** têm um único candidato nominal após normalização de caixa, acentos e abreviações controladas; eles se relacionam a **31 polígonos SIGGO distintos**. As outras **16** grafias permanecem com identificação territorial pendente, incluindo três rótulos truncados no próprio PDF. Grafias não são contagem de bairros oficiais.

A normalização preserva números, etapas, tipos e complementos. Exemplos: “SET” e “S” podem normalizar para “SETOR”; “JD Curitiba I” não é reduzido a “JD Curitiba”; “Bairro São Francisco” não é confundido com “Vila São Francisco”. Hipóteses contextuais e similaridade textual aparecem somente como sugestões, sem preencher o identificador principal do candidato.

**Correspondência nominal não comprova equivalência dos limites usados pela Saúde.** Todos os registros conservam `limites_homologados_pela_saude=False` e `apto_ranking_completo_ou_taxa=False`. Não houve soma entre janelas, deduplicação epidemiológica, rateio de população, atribuição obrigatória de polígono ou criação de taxas. A camada SIGGO descreve loteamentos e não foi validada como divisão sanitária.

## Pendências que a leitura dos PDFs não resolve

- As 120 observações de 2024 têm título anual, sem corte temporal explícito. O número da edição não foi convertido automaticamente em período da tabela.
- Dez observações da edição 35/2026 preservam a divergência entre “últimas 4 semanas” e “SE 32 a 36”.
- Três nomes estão truncados na própria fonte: “SET URIAS MAGAL...”, “SET DOS...” e “SET LESTE...”. Não foram completados por semelhança com outras edições.
- Sete linhas de chikungunya da edição 10/2024 têm confirmados superiores a prováveis conforme o cabeçalho impresso. Os valores e a ordem das colunas foram preservados para esclarecimento.
- As edições 18–20/2026 apresentam grande variação nas contagens e as edições 37 e 38 repetem a sequência dos dez valores com bairros diferentes. Isso não comprova erro, mas justifica confirmar critério e versão antes da comparação.
- As listas publicadas não comprovam cobertura de todos os bairros. Ausência de um bairro não significa zero. Não identificamos uma série de acidentes com escorpiões por bairro nesses informes.

A base tem 194 observações com pelo menos uma dessas pendências de fonte/período ou de identificação nominal. As demais 166 também dependem da validação dos limites e da avaliação de cobertura antes de apoiar taxas ou um ranking completo.

## Reproduzir

```powershell
& '.venv-datasus/Scripts/python.exe' revisar_territorio.py
& '.venv-datasus/Scripts/python.exe' verificar_revisao_territorial.py
& '.venv-datasus/Scripts/python.exe' validar_revisao_territorial.py
```

O script usa `revisoes_visuais_informes.json`, que contém as transcrições e hashes fixados das fontes inspecionadas, e o CSV municipal já coletado. Recusa PDFs ou recortes que mudaram. Para novas versões dos informes, é necessária nova conferência visual e atualização explícita das transcrições; não reaplicar a revisão antiga a um arquivo diferente.

`preparar_revisao_territorial.py` produz os recortes e pranchas de conferência. O ambiente `.venv-datasus` já tem as dependências usadas: pandas, openpyxl, Pillow e pypdfium2. Os seis testes protegem abreviações, etapas, tipos, complementos e sugestões não confirmadas. O validador confere hashes, transcrições, cardinalidade, candidatos, conservação de pendências e equivalência entre CSV e Excel.
