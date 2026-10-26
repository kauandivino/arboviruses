# Clima de Goiânia — INMET

Coleta pública dos [arquivos históricos anuais de estações automáticas](https://portal.inmet.gov.br/dadoshistoricos), com extração exclusiva da estação A002 (GOIANIA). O script consulta os links da página, confirma a estação no catálogo oficial, baixa os ZIPs nacionais e extrai um CSV por ano. Não exige login nem navegador.

## Executar

No ambiente já preparado neste projeto:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_inmet
```

O padrão é 2022 a 2026. Para escolher anos, acrescente `--anos 2024 2025 2026`. Para reprocessar sem rede, use `--somente-processar`, com os mesmos anos da coleta. Para outro ambiente, instale `requirements.txt`.

O ZIP de 2026 contém duas versões acumuladas da A002, até agosto e até setembro. O script escolhe a maior data final entre arquivos que começam em 1 de janeiro e registra todos os candidatos; não concatena versões sobrepostas. Empates ou nomes inesperados geram erro.

Downloads usam dois processos de transferência simultâneos, blocos com retomada, identificação por ETag/Last-Modified, tamanho esperado e verificação CRC do ZIP. Os recibos incluem URL, rótulo do link, data da coleta e SHA-256. Uma nova execução consulta o servidor e baixa novamente arquivos atualizados, incluindo 2026. Falhas interrompem a execução com código diferente de zero; arquivos parciais ficam disponíveis para retomada.

## Arquivos em `dados/inmet`

- `originais/`: ZIPs nacionais intactos e recibos de cada ano.
- `estacao_originais/`: CSVs A002 extraídos sem alteração.
- `pagina.html`, `catalogo_estacoes.json`, `estacao.json`: documentação da descoberta e localização.
- `manifesto.json`, `fontes_estacao.json`: procedência e hashes.
- `goiania/horario.csv`: precipitação horária em mm, temperatura do ar (bulbo seco) em °C e umidade relativa em %, valores originais e motivos de ausência.
- `goiania/dia_utc.csv` e `mes_utc.csv`: somas de chuva e médias aritméticas das observações horárias de temperatura/umidade, acompanhadas de cobertura.
- `goiania/qualidade.json`: contagem de falhas e metadados por ano, incluindo as coordenadas informadas em cada CSV.

Os resumos usam dias civis e meses **UTC**. A série horária também informa o horário de Brasília; converter o fuso pode mudar a data. Não são médias compensadas nem totais do dia meteorológico convencional. A precipitação registrada em uma hora corresponde à medição horária do INMET; o script não desloca seu intervalo de referência.

Cada variável tem seu próprio número de horas válidas. `_observado` é soma/média apenas dos valores disponíveis. `_completo_valor` só é preenchido quando todas as horas do período têm valores válidos; caso contrário fica vazio. Zero de chuva é mantido como zero. Campos vazios, Null, NaN e sentinelas ±9999 são ausências; chuva negativa e umidade fora de 0–100 são marcadas como fora do domínio. Não há preenchimento nem interpolação. Temperaturas extremas não são removidas por um limite arbitrário.

Nos anos encerrados, a grade inclui o ano inteiro; no ano corrente termina no último dia encontrado no CSV da estação. Meses parcialmente publicados são identificados pela cobertura. O limite da estação pode ser anterior ao rótulo geral do arquivo nacional. Datas futuras não são preenchidas com zero. Na consulta de 19/10/2026, a página anunciava 2026 até 30/09/2026.

## Validação e uso

```powershell
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_inmet
& .venv/Scripts/python.exe -m pipeline.verificacao.validar_inmet
```

O primeiro comando testa as regras; o segundo verifica hashes, unicidade temporal, domínio da cobertura e reconstituição dos resumos salvos. Dados automáticos brutos não equivalem a uma série já consistida pelo INMET. A validação técnica não atesta precisão dos sensores.

Uma estação fornece contexto temporal para Goiânia; não mede diferenças entre bairros. Não distribuir estes valores como se fossem observações independentes de cada bairro. Não há cálculo de relação causal entre clima e dengue nesta etapa. Para relacionar com os boletins, é necessário definir o calendário epidemiológico e as defasagens, a partir da série horária, sem tratar estes dias UTC como semanas epidemiológicas.

## Coleta executada em 19/10/2026

Baixados cinco ZIPs (528.014.118 bytes), com 41.616 horários da A002 entre 01/01/2022 e 30/09/2026, 1.734 dias e 57 meses. Os três testes de regras e a validação real dos hashes e resumos passaram.

| Ano | Horas na grade | Horas válidas de chuva | Temperatura | Umidade |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 8.760 | 6.996 | 8.760 | 8.760 |
| 2023 | 8.760 | 8.758 | 8.758 | 8.758 |
| 2024 | 8.784 | 8.725 | 8.726 | 8.702 |
| 2025 | 8.760 | 6.063 | 6.066 | 6.066 |
| 2026, até setembro | 6.552 | 6.395 | 6.398 | 6.398 |

Em 2025 faltam aproximadamente 31% das medições em cada variável; em 2022 faltam aproximadamente 20% das medições de chuva. Isso limita comparações de totais anuais. A extração não atribui uma causa a essas ausências.
