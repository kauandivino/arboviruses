# Painel Saúde no Território

Primeira versão local baseada exclusivamente nos arquivos públicos coletados. Não depende de resposta da Secretaria. Nenhum dado foi publicado na internet.

## Abrir

Com o servidor iniciado, acesse http://127.0.0.1:4173/ no navegador. Para iniciar novamente, na raiz do projeto:

```powershell
.\abrir_painel.ps1
```

O terminal precisa permanecer aberto. Use `-Porta 4174` caso a porta já esteja ocupada e acesse a nova porta. O servidor atende apenas no próprio computador.

## Consultas disponíveis

- Evolução municipal: dengue por residência e mês de notificação; escorpiões por ocorrência e mês do acidente. Filtro de ano, histórico completo, situação da fonte e população municipal do Censo 2022.
- Bairros nos informes: publicação, agravo e indicador, valores da lista publicada, correspondência nominal e link para a página do PDF. Combinações inexistentes mostram ausência de observações. Seleções de múltiplas publicações não geram um gráfico agregado.
- Clima: chuva observada, cobertura horária, temperatura e umidade da A002; calendário UTC e tabela de cobertura por variável.
- Unidades de saúde: busca e paginação dos 200 cadastros públicos candidatos a contato. Não comprova funcionamento ou disponibilidade para parceria.
- Plano de atuação: oito territórios propostos, presença nas listas em duas configurações de janelas, parceiros candidatos e condições antes de agendar. Justificativa detalhada em SELECAO-TERRITORIOS.md; planilha em dados/selecao_territorios/selecao_e_plano.xlsx.

Menus dos componentes permitem consultar fontes e dados da seleção. A interface compartilhada possui alguns controles em inglês. O painel não faz atualizações de fontes sozinho. A data de geração do snapshot não significa que todos os dados tenham essa data de referência.

Não foram criados mapas, taxas por bairro, rankings completos, previsões ou atribuição causal. Os limites e a metodologia estão em BASE-INTEGRADA.md. A escolha dos oito territórios continua sendo uma decisão operacional documentada da equipe.

## Atualizar e recompilar

```powershell
& '.venv-datasus/Scripts/python.exe' integrar_bases.py
& '.venv-datasus/Scripts/python.exe' verificar_integracao.py
& '.venv-datasus/Scripts/python.exe' preparar_painel.py
```

O preparador atualiza `painel/src/data.json`, preservando o ID do painel e marcando atualização em andamento. Após a revisão, definir `buildStatus` como `complete` nesse arquivo e compilar:

```powershell
& '.tools/node/node-v22.14.0-win-x64/node.exe' 'C:/Users/user/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11/scripts/data-app.mjs' build --project-dir "$PSScriptRoot/painel" --separate-data
```

Em terminal interativo, substitua `$PSScriptRoot/painel` pelo caminho absoluto `D:/Desktop/cidadania/painel`. O compilador pertence ao plugin Data instalado. O Node.js portátil foi baixado de nodejs.org, versão 22.14.0, com SHA-256 conferido contra SHASUMS256.txt oficial. Não há instalação global nem necessidade de npm.

Sirva a pasta `painel/dist` inteira: o HTML depende do snapshot JSON verificado ao lado. Não abra o HTML por `file://`.

## Verificação

`verificar_integracao.py` verifica fronteiras temporais, ausência de preenchimento artificial e a integração sem multiplicação. `verificar_painel_browser.py` usa Playwright e Edge instalados para verificar as quatro abas, mudanças de ano e publicação, alertas, seleção vazia, busca, retorno às 200 unidades e largura de celular. Capturas e resultado em `dados/verificacao_painel/`.
