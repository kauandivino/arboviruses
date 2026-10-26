# Modelagem da dengue

Três modelos treinados e avaliados com os microdados reais do SINAN, todos em `pipeline/modelagem/`:

- **Nowcasting:** estima quantas notificações das semanas recentes ainda vão ser digitadas.
- **Previsão de 1 a 8 semanas:** só é exibida se, num período de teste nunca usado na escolha do modelo, superar referências simples.
- **Diagrama de controle com alerta:** compara cada semana com o padrão dos cinco anos anteriores.

Em todos, o passado é reconstruído com o que estava digitado em cada data. Nenhum modelo usa informação que ainda não existia no momento avaliado.

## Dados

- **Microdados SINAN de dengue de 2014 a 2026,** só de residentes em Goiânia, de todas as classificações. Contam notificações, não casos confirmados nem pessoas únicas.
  - 2022 a 2026: `dados/datasus/goiania/`.
  - 2014 a 2021: `dados/datasus_historico/goiania/`, coleta separada usada só para treinar e avaliar modelos. A série mensal do painel continua começando em 2022.
- **Clima da estação A002 do INMET de 2014 a 2026:**
  - 2014 a 2021: `dados/inmet_historico/`.
  - 2022 a 2026: `dados/inmet/`.
  - De 91% a 100% das horas medidas, conforme o ano e a variável.
- **Semanas:** a semana é a epidemiológica (domingo a sábado) do início dos sintomas. O cálculo confere com o campo `SEM_PRI` da fonte em todas as semanas. O atraso é medido até a semana de digitação (`DT_DIGITA`).
- **Exclusões, auditadas no manifesto de cada modelo:**
  - notificações sem data de digitação ou com início dos sintomas inválido;
  - notificações fora da janela do arquivo anual (ver a regra dos arquivos abaixo).
- **Ritmo de digitação:** de 2015 a 2018, a mediana do atraso de digitação foi de 11 a 21 semanas; a partir de 2019, de 1 a 4 semanas. Isso orienta os períodos de avaliação abaixo.

## Nowcasting

Chain-ladder em tempo reverso:

1. Monta-se o triângulo de contagens por semana de início e semanas de atraso, só com o que estava digitado na data de corte. Células ainda não observáveis ficam ausentes, nunca zero.
2. Para cada atraso k, o fator de desenvolvimento é a razão entre as contagens acumuladas em k+1 e em k nas 20 coortes mais recentes que já atingiram k+1.
3. A estimativa de uma semana é o observado multiplicado pelos fatores ainda não atingidos, até 52 semanas.

Parâmetros fixos: 52 semanas de maturação, janela de 20 coortes, 12 semanas estimadas e faixa pelos quantis de 2,5% e 97,5% dos erros anteriores.

### Avaliação

Foram 301 semanas de corte, de janeiro de 2020 a outubro de 2025, já com a digitação no ritmo atual. A faixa de cada corte usa só erros cuja verdade já era conhecida naquela data.

| Semanas desde o início | Erro mediano sem modelo | Erro mediano com estimativa | Acerto da faixa |
|---|---|---|---|
| 0 | 90% | 31% | 91% |
| 1 | 65% | 19% | 91% |
| 2 | 47% | 15% | 94% |
| 4 | 30% | 10% | 96% |
| 8 | 14% | 7% | 96% |
| 11 | 8% | 5% | 97% |

A estimativa erra menos que o número bruto em todas as 12 semanas, e a faixa ficou perto dos 95% nominais. O painel só exibe a estimativa se ela superar o número bruto em todas as semanas avaliadas.

### Proteção contra condições não testadas

Na virada de 2025 para 2026, a digitação quase parou: de 4 a 35 notificações por semana na primeira semana após os sintomas, contra centenas no normal. Quando a rotina voltou, em fevereiro, os fatores aprendidos nas semanas lentas multiplicaram a primeira semana normal por cerca de 30, e a estimativa em tempo real superestimou cerca de 8 vezes. Nos cortes avaliados (2020 a 2025), o pior caso tinha sido 6,3 vezes.

Para isso não se repetir no painel, existe uma proteção. Se o fator de correção de uma semana passar do maior fator visto na avaliação para aquele atraso, a estimativa fica **suspensa** e a semana mostra só o observado. Os limites ficam em `limite_fator_por_defasagem`, no manifesto. A regra foi criada depois de identificado o problema; ela não altera as métricas acima, só impede a exibição fora do alcance validado.

## Previsão de 1 a 8 semanas

### Regra, definida antes de rodar a avaliação

- **Candidatos,** um ajuste por horizonte no logaritmo das contagens:
  - ridge sem clima: nível e tendência das últimas semanas e sazonalidade;
  - ridge com clima: o mesmo, mais chuva, temperatura e umidade médias por hora válida das semanas A-9 a A-2. Janelas com menos de 60% das horas medidas ficam sem valor; nenhuma hora é preenchida;
  - gradient boosting com clima, com os mesmos atributos.
- **Referências:** repetir a média das últimas 4 semanas (corrigidas pelo nowcasting) e repetir a mesma semana do ano anterior.
- **Escolha:** o candidato de menor erro absoluto médio nas origens de **validação**, de 2016 a 2020.
- **Exibição:** só se, nas origens de **teste** (2021 a 2025, nunca usadas na escolha), o escolhido tiver erro menor que a melhor referência em todos os horizontes.

Em cada origem, os modelos usam só a série digitada até ali, corrigida pelo nowcasting daquele momento, e o clima até duas semanas antes.

### Resultado

O escolhido na validação foi o **gradient boosting com clima**. Erro absoluto médio no teste, em notificações por semana:

| Semanas à frente | Melhor referência | Gradient boosting com clima | Ridge sem clima |
|---|---|---|---|
| 1 | 202 | 197 | 198 |
| 2 | 234 | 228 | 210 |
| 4 | 293 | 280 | 234 |
| 6 | 352 | 302 | 256 |
| 8 | 420 | 306 | 279 |

O escolhido superou a referência nos 8 horizontes, então a previsão é exibida. Ressalvas, também mostradas no painel:

- **Vantagem pequena no curto prazo:** 2% a 4% de 1 a 4 semanas à frente; maior de 6 a 8 semanas.
- **Ganho concentrado na epidemia de 2022.** No horizonte de 4 semanas, o erro de 2022 foi 189 contra 448 da referência. Em 2021, 2023 e 2025 o modelo errou mais que a referência. O painel calcula essa comparação por temporada a partir dos dados.
- **Faixa larga:** acerta de 91% a 100% das vezes, mas vai de cerca de um quarto a quase três vezes o valor previsto.
- **O ridge sem clima foi melhor no teste,** mas não foi adotado: trocar de modelo depois de ver o teste anularia o teste.
- **Validação em outro regime:** a validação de 2016 a 2020 inclui o período de digitação lenta. Isso pode ter favorecido o gradient boosting na escolha.

A avaliação completa leva cerca de 25 minutos. Ela é refeita só quando os dados, os parâmetros ou o código mudam (`chave_avaliacao` no manifesto); caso contrário, o pipeline reaproveita a avaliação e recalcula apenas a previsão atual.

## Diagrama de controle e alerta

Segue o método dos quartis, usado em vigilância epidemiológica:

- **Referência:** para cada semana epidemiológica do ano, as contagens da mesma semana e das vizinhas (±1) nos cinco anos anteriores, como eram conhecidas no início do ano, somando 15 valores.
- **Zonas:** abaixo do 1º quartil, até a mediana, até o 3º quartil e acima do 3º quartil (epidêmica).
- **Alerta:** duas semanas seguidas na zona epidêmica, com o valor de cada semana como era visto naquela data (digitado e corrigido pelo nowcasting).
- **Semanas indeterminadas:** quando o fator de correção daquele momento passa do limite da proteção, a semana fica indeterminada e não conta para o alerta.

A simulação semana a semana das temporadas 2019 a 2025 fica em `dados/modelagem/alerta_dengue_avaliacao.csv`:

| Temporada | Notificações | Primeiro alerta em relação ao pico | Alertas confirmados |
|---|---|---|---|
| 2022 | 54 mil | 7 semanas antes | 100% |
| 2024 | 57 mil | 11 semanas antes | 96% |
| 2025 | 32 mil | 16 semanas antes | 60% |
| 2021 | 12 mil | 2 semanas antes | 100% |
| 2023 | 20 mil | 22 semanas depois | 71% |
| 2019 | 33 mil | 1 semana depois (17 semanas indeterminadas) | 17% |

"Alertas confirmados" é a fração das semanas em alerta que, com os dados finais, estavam de fato na zona epidêmica.

Nas duas grandes epidemias, o alerta antecedeu o pico em 7 e 11 semanas, quase sem alarmes falsos. Em temporadas menores, a confirmação é mais baixa. Em 2019, a digitação ainda lenta deixou a maior parte do início da temporada indeterminada. As contagens não são convertidas em incidência porque não há estimativa oficial semanal de população.

## Regra dos arquivos anuais (correção de 26/10/2026)

Os arquivos de dengue do SINAN seguem o ano epidemiológico da notificação; os de animais peçonhentos, o ano civil. A regra anterior ("cada arquivo contribui só com datas do próprio ano civil") descartava notificações legítimas nas viradas de ano, como as de 1º a 3 de janeiro de 2026, que pertencem ao ano epidemiológico de 2025 e só existem nesse arquivo.

A regra atual (`pipeline/comum/epidemiologia.py`) aceita, de cada arquivo, as notificações com data dentro do ano civil ou do ano epidemiológico correspondente. A integração verifica que nenhuma notificação aparece em dois arquivos. Com isso, a série mensal ganhou 247 notificações de dengue e 7 de escorpiões.

Continuam excluídas, e auditadas em `exclusoes_temporais`, 425 notificações do arquivo de 2025 feitas depois de 03/01/2026. Elas não aparecem no arquivo de 2026, mas podem passar a aparecer quando ele for atualizado, e seriam contadas duas vezes.

## Limitações comuns

- A reconstrução do passado usa a base atual: notificações removidas depois, como duplicidades, não aparecem nos cortes antigos.
- Uma única estação meteorológica representa a cidade inteira; nada aqui descreve diferenças entre bairros.
- Associação estatística com o clima não demonstra causa.

## Reprodução

Tudo roda em `python -m pipeline`. Para rodar só a modelagem e os testes:

```powershell
& .venv/Scripts/python.exe -m pipeline.modelagem.nowcast
& .venv/Scripts/python.exe -m pipeline.modelagem.previsao
& .venv/Scripts/python.exe -m pipeline.modelagem.alerta
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_nowcast
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_previsao
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_alerta
```

Para coletar de novo o histórico:

```powershell
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_datasus --anos 2014 2015 2016 2017 2018 2019 2020 2021 --agravos dengue --saida dados/datasus_historico
& .venv/Scripts/python.exe -m pipeline.coleta.baixar_inmet --anos 2014 2015 2016 2017 2018 2019 2020 2021 --destino dados/inmet_historico
```

Fontes, parâmetros, exclusões e hashes ficam nos manifestos de `dados/modelagem/`.
