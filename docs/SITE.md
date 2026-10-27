# Site público

Site para a população de Goiânia: situação da dengue na semana, gráficos simples, mapa dos bairros com as unidades de saúde e orientações de prevenção. Fica na raiz do servidor (http://127.0.0.1:4173/). O painel técnico da equipe continua em `/equipe/`.

## Princípios

- **Visual antes de texto:** cada seção abre com um gráfico ou um número grande; o texto se limita a uma ou duas frases.
- **Linguagem do dia a dia:** "casos notificados" com explicação curta, "faixa habitual para a época" em vez de quartis, nomes de bairro por extenso ("Parque Atheneu", não "Prq Atheneu").
- **Nada inventado:** todos os números vêm do pipeline. Quando falta dado, o site diz que falta. Um bairro fora das listas dos boletins aparece como "não apareceu entre os bairros com mais casos", nunca como "zero casos".
- **Honestidade sobre incerteza:** semanas recentes incluem a estimativa de registros atrasados, avisada no cartão de situação. A projeção aparece com faixa que desaparece para cima, e só existe porque passou no teste descrito em [MODELAGEM.md](MODELAGEM.md).

## Seções

| Seção | O que mostra | Dados |
|---|---|---|
| Abertura | Situação da dengue nesta semana (abaixo, habitual, pouco acima, acima ou alerta), casos das últimas 4 semanas e tendência | diagrama de controle, nowcasting |
| Números | Casos de dengue e acidentes com escorpião no ano, unidades de saúde | série anual, base integrada, CNES |
| Dengue | Linha do ano sobre a faixa habitual, projeção e comparação com anos anteriores; barras ano a ano desde 2014 | alerta, previsão, série corrigida |
| Tipo de vírus | Sorotipo predominante nas últimas 12 semanas, barras por mês e aviso sobre reinfecção | dados/regional (amostras tipadas de Goiânia) |
| Mosquito e transmissão | LIRAa por ciclo sobre as faixas do Ministério da Saúde; Rt do InfoDengue nas últimas 12 semanas | dados/liraa, dados/infodengue |
| Chikungunya e zika | Casos por ano em Goiânia | dados/regional |
| Chuva e dengue | Chuva mensal e casos por mês nos últimos 24 meses, alinhados | INMET, base integrada |
| Escorpiões | Acidentes por mês no ano e média dos anos anteriores; o que fazer em caso de picada | base integrada |
| Seu bairro | Mapa com ruas, bairros coloridos pela presença nos boletins, oito territórios, unidades de saúde; busca com as 3 unidades mais próximas | malha SIGGO, boletins revisados, CNES |
| O projeto | Oito territórios, parceiros e ações realizadas (do registro da equipe) | seleção, ações de campo |
| Prevenção | Dicas de dengue e de escorpiões, sinais de alerta, SAMU 192 e Disque Saúde 136 | orientações do Ministério da Saúde |
| Sobre os dados | Fontes, data de atualização e link para o painel da equipe | manifestos |

Unidades de saúde no mapa: só as públicas que a população procura, ou seja, postos (UBS), policlínicas, pronto atendimentos e hospitais gerais. A distância mostrada é em linha reta a partir do centro do bairro.

## Tecnologia

- React 18, TypeScript e Vite em `site/`, com gráficos próprios em SVG (d3-scale e d3-shape) e animações com Motion, que respeitam a preferência por menos movimento.
- Mapa com MapLibre GL. O mapa de ruas vem do OpenFreeMap (dados do OpenStreetMap), sem chave de acesso; sem internet, as camadas do projeto aparecem sobre fundo neutro. O mapa só é baixado quando a pessoa chega à seção.
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

Durante o desenvolvimento, rode antes `python -m pipeline.processamento.preparar_site` para ter os dados em `site/public/dados`. O teste no navegador é `python -m pipeline.verificacao.verificar_site`; capturas e resultado ficam em `dados/verificacao_site/`.
