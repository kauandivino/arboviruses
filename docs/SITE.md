# Site público

Site para a população de Goiânia: situação da dengue na semana, gráficos simples, mapa dos bairros com as unidades de saúde e orientações de prevenção. Fica na raiz do servidor (http://127.0.0.1:4173/). O painel técnico da equipe continua em `/equipe/`.

## Princípios

- **Visual antes de texto:** cada aba abre com um gráfico ou um número grande; o texto se limita a uma ou duas frases, e os textos dos achados são gerados a partir dos dados.
- **Linguagem do dia a dia:** "casos notificados" com explicação curta, "faixa habitual para a época" em vez de quartis, nomes de bairro por extenso ("Parque Atheneu", não "Prq Atheneu").
- **Nada inventado:** todos os números vêm do pipeline. Quando falta dado, o site diz que falta. Um bairro fora das listas dos boletins aparece como "não apareceu entre os bairros com mais casos", nunca como "zero casos".
- **Honestidade sobre incerteza:** semanas recentes incluem a estimativa de registros atrasados, com faixa no gráfico e o número já registrado na dica de cada semana. A projeção aparece com faixa que desaparece para cima (no Painel, cortada no dobro do valor central; a dica mostra a faixa completa), e só existe porque passou no teste descrito em [MODELAGEM.md](MODELAGEM.md).

## Abas

O site é dividido em abas com endereço próprio (`#/dengue`, `#/bairro`...), que podem ser compartilhadas. O Painel junta tudo num só lugar; as outras abas aprofundam cada tema.

| Aba | O que mostra | Dados |
|---|---|---|
| Painel | Seis indicadores (situação da dengue, chikungunya no ano, LIRAa, Rt, chuva do último mês contra a média, escorpiões no último mês contra o habitual), cada um levando à sua aba; dengue do ano com faixa habitual, estimativa das semanas recentes, projeção e chuva semanal no mesmo eixo; quatro achados das correlações com minigráficos; mapa resumido dos bairros e os mais citados nos boletins | todos os produtos abaixo |
| Dengue | Linha do ano sobre a faixa habitual, projeção e comparação com anos anteriores; Goiânia, vizinhas e resto de Goiás na proporção do próprio pico; sorotipos; internações por ano; barras ano a ano desde 2014 | alerta, previsão, nowcasting, dados/regional |
| Chikungunya e Zika | Casos por ano; chikungunya e dengue lado a lado nos últimos 2 anos, com a defasagem entre os picos | dados/regional, correlações |
| Mosquito e Clima | LIRAa por ciclo sobre as faixas do Ministério da Saúde; Rt do InfoDengue; correlação de chuva, umidade e temperatura com a dengue por defasagem, bruta e sem sazonalidade; chuva e dengue mês a mês | dados/liraa, dados/infodengue, INMET, correlações |
| Escorpiões | O que fazer em caso de picada; acidentes por mês desde 2014 (com previsão só se o modelo passar no teste); o ano atual contra a média; época do ano e temperatura | SINAN de animais peçonhentos, modelo de escorpiões, correlações |
| Seu bairro | Mapa com ruas, bairros coloridos pela presença nos boletins, oito territórios, unidades de saúde; busca com as 3 unidades mais próximas; o projeto e as ações realizadas | malha SIGGO, boletins revisados, CNES, ações de campo |
| Prevenção | Dicas de dengue e de escorpiões, sinais de alerta, SAMU 192 e Disque Saúde 136 | orientações do Ministério da Saúde |
| Sobre | Fontes, data de atualização, todos os modelos testados (no site ou não, com o resultado do teste) e link para o painel da equipe | manifestos |

Unidades de saúde no mapa: só as públicas que a população procura, ou seja, postos (UBS), policlínicas, pronto atendimentos e hospitais gerais. A distância mostrada é em linha reta a partir do centro do bairro.

## Tecnologia

- React 18, TypeScript e Vite em `site/`, com gráficos próprios em SVG (d3-scale e d3-shape) e animações com Motion, que respeitam a preferência por menos movimento.
- Mapa com MapLibre GL. O mapa de ruas vem do OpenFreeMap (dados do OpenStreetMap), sem chave de acesso; sem internet, as camadas do projeto aparecem sobre fundo neutro. O mapa de ruas só é baixado quando a pessoa abre a aba Seu bairro; o mapa resumido do Painel é SVG simples.
- Fontes Raleway e Inter e ícones Lucide incluídos no próprio site, sem depender de serviços externos.
- Tema claro, acento verde-azulado, títulos largos em caixa alta e motivo triangular. Funciona do celular (390 px) ao computador.

## Dados

`pipeline/processamento/preparar_site.py` gera `site/public/dados/`:

- `site.json`: situação, séries, territórios e ações;
- `bairros.geojson`: 1.207 bairros simplificados em 6 m, em latitude/longitude;
- `unidades.geojson`: unidades de saúde com endereço e telefone do cadastro;
- `manifesto.json`: fontes e hashes.

O site lê esses arquivos ao abrir. Por isso a atualização semanal recompila tudo e o site mostra os dados novos sem nenhum passo manual.

## Desenvolvimento

```powershell
$env:PATH = "$PWD/.tools/node/node-v22.14.0-win-x64;$env:PATH"
npm ci --prefix site              # primeira vez
npm run dev --prefix site         # servidor de desenvolvimento com recarga
npm run build --prefix site       # verificação de tipos e compilação em site/dist
```

As correlações e o modelo de escorpiões vêm de `dados/modelagem/` (ver [MODELAGEM.md](MODELAGEM.md)).

Durante o desenvolvimento, rode antes `python -m pipeline.processamento.preparar_site` para ter os dados em `site/public/dados`. O teste no navegador é `python -m pipeline.verificacao.verificar_site`; capturas e resultado ficam em `dados/verificacao_site/`.
