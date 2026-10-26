# Nowcasting de dengue

As notificações de dengue chegam ao SINAN com atraso: a mediana entre o início dos sintomas e a digitação é de 15 dias, e 10% levam mais de 93 dias. Por isso as semanas recentes sempre parecem menores do que serão. O nowcasting estima quantas notificações de cada semana ainda vão ser digitadas.

Não é previsão de semanas futuras. Estima o total das semanas que já passaram, a partir do que já foi digitado e do histórico de atrasos.

## Dados

- Microdados SINAN de dengue de 2022 a 2026 (`dados/datasus/goiania/dengue_<ano>.csv`), só de residentes em Goiânia, de todas as classificações. Contam notificações, não casos confirmados nem pessoas únicas.
- A semana é a epidemiológica (domingo a sábado) do início dos sintomas. O atraso é medido até a semana de digitação (`DT_DIGITA`).
- A data de corte é a última semana de digitação completa da base.
- Regra dos arquivos: a mesma da base integrada (ver abaixo). Notificações excluídas pela regra aparecem por semana na coluna `excluidas_fora_janela` e no balão do gráfico.

## Método

Chain-ladder em tempo reverso, sem parâmetros ajustados aos resultados:

1. Monta-se o triângulo de contagens por semana de início e semanas de atraso, só com o que estava digitado na data de corte. Células ainda não observáveis ficam ausentes, nunca zero.
2. Para cada atraso k, o fator de desenvolvimento é a razão entre as contagens acumuladas em k+1 e em k nas 20 coortes mais recentes que já atingiram k+1.
3. A estimativa de uma semana é o observado multiplicado pelos fatores ainda não atingidos, até 52 semanas, quando a coorte é tratada como completa.

Parâmetros fixos em `pipeline/modelagem/nowcast.py`: 52 semanas de maturação, janela de 20 coortes, 12 semanas estimadas e faixa pelos quantis de 2,5% e 97,5%.

## Avaliação retrospectiva

Para cada uma das 145 semanas de corte entre janeiro de 2023 e outubro de 2025, reconstrói-se o que estava digitado naquele momento pela data de digitação, estima-se e compara-se com o total que chegou depois. A faixa de cada avaliação usa só erros cuja verdade já era conhecida naquela data, sem olhar o futuro.

| Semanas desde o início | Erro mediano sem modelo | Erro mediano com estimativa | Acerto da faixa |
|---|---|---|---|
| 0 | 90% | 29% | 82% |
| 1 | 65% | 20% | 87% |
| 2 | 46% | 15% | 87% |
| 4 | 31% | 10% | 92% |
| 8 | 15% | 6% | 84% |
| 11 | 9% | 4% | 71% |

A estimativa erra menos que o número bruto em todas as 12 semanas. A faixa é nominalmente de 95%, mas conteve o total final de 71% a 92% das vezes, conforme a semana. O painel mostra a taxa medida, não a nominal. Os números completos estão em `dados/modelagem/nowcast_dengue_avaliacao.csv`, e cada avaliação individual em `nowcast_dengue_retrospectiva.csv`.

O painel só exibe a estimativa se ela superar o número bruto em todas as semanas avaliadas. Se uma atualização dos dados mudar isso, o gráfico volta a mostrar só o observado e explica o motivo.

## Limitações

- A reconstrução do passado usa a base atual: notificações removidas depois, como duplicidades, não aparecem nos cortes antigos.
- Uma mudança brusca na rotina de digitação, como uma força-tarefa ou um sistema fora do ar, pode deixar a faixa estreita demais.
- Na semana mais recente quase tudo ainda vai chegar; a faixa é larga e deve ser lida assim.

## Previsão de 1 a 8 semanas

`pipeline/modelagem/previsao.py` tenta prever as notificações das próximas 8 semanas. A regra foi definida antes de ver o resultado: o modelo só é exibido se tiver erro absoluto médio menor que o da melhor referência simples em todos os horizontes.

- **Referências:** repetir a média das últimas 4 semanas (corrigidas pelo nowcasting) e repetir a mesma semana do ano anterior.
- **Modelo:** regressão ridge no logaritmo das contagens, uma por horizonte, com nível e tendência recentes, sazonalidade e clima da estação A002. O clima entra como chuva, temperatura e umidade médias por hora válida das semanas A-9 a A-2. Janelas com menos de 60% das horas medidas ficam sem valor; nenhuma hora é preenchida.
- **Avaliação:** 111 origens semanais de julho de 2023 a outubro de 2025. Em cada origem, o modelo usa só o que estava digitado naquela data, corrigido pelo nowcasting daquele momento, e o clima até duas semanas antes.

Resultado em 26/10/2026 (erro absoluto médio, em notificações por semana):

| Semanas à frente | Últimas 4 semanas | Modelo sem clima | Modelo com clima |
|---|---|---|---|
| 1 | 241 | 244 | 288 |
| 4 | 329 | 337 | 401 |
| 8 | 459 | 387 | 435 |

O modelo com clima não superou a referência em 7 dos 8 horizontes; na epidemia de 2024 errou bem mais (693 contra 507 no horizonte de 4 semanas). Por isso **a previsão não é exibida**. O modelo sem clima ganhou só de 5 a 8 semanas à frente e não foi adotado depois de ver o resultado, para não ajustar o critério à resposta.

Com quatro temporadas e uma única estação meteorológica, os dados não sustentam uma previsão melhor do que repetir o nível recente. O painel mostra essa avaliação, e o pipeline a refaz a cada atualização: se um dia o modelo passar na regra, a previsão aparece automaticamente com a faixa de incerteza.

## Regra dos arquivos anuais (correção de 26/10/2026)

Os arquivos de dengue do SINAN seguem o ano epidemiológico da notificação; os de animais peçonhentos, o ano civil. A regra anterior ("cada arquivo contribui só com datas do próprio ano civil") descartava notificações legítimas nas viradas de ano, como as de 1º a 3 de janeiro de 2026, que pertencem ao ano epidemiológico de 2025 e só existem nesse arquivo.

A regra atual (`pipeline/comum/epidemiologia.py`) aceita, de cada arquivo, as notificações com data dentro do ano civil ou do ano epidemiológico correspondente, e a integração verifica que nenhuma notificação aparece em dois arquivos. Com isso, a série mensal ganhou 247 notificações de dengue e 7 de escorpiões. Continuam excluídas, e auditadas em `exclusoes_temporais`, 425 notificações do arquivo de 2025 feitas depois de 03/01/2026: elas não aparecem no arquivo de 2026, mas podem passar a aparecer quando ele for atualizado, e seriam contadas duas vezes.

## Reprodução

```powershell
& .venv/Scripts/python.exe -m pipeline.modelagem.nowcast
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_nowcast
```

Ambos rodam dentro de `python -m pipeline`. Fontes, parâmetros, exclusões e hashes ficam em `dados/modelagem/nowcast_dengue_manifesto.json`.
