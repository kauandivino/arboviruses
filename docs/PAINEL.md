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

Na raiz do projeto:

```powershell
& .venv/Scripts/python.exe -m pipeline
```

O pipeline regera a integração e a seleção e roda todos os testes e validações. Só depois disso grava `painel/src/data.json`, preservando o ID do painel e marcando o snapshot como revisado. Em seguida compila o painel e o testa no navegador. Se qualquer etapa falhar, o painel anterior em `painel/dist` permanece.

A compilação é independente: usa o Node.js portátil do projeto (`.tools/node`, versão 22.14.0, baixado de nodejs.org com SHA-256 conferido) e o Vite declarado em `painel/package.json`. Na primeira vez, instale as dependências:

```powershell
$env:PATH = "$PWD/.tools/node/node-v22.14.0-win-x64;$env:PATH"
npm ci --prefix painel
```

Para compilar só o painel: `npm run build --prefix painel`. O resultado é um único `painel/dist/index.html` com os dados embutidos. Não abra o arquivo por `file://`; sirva-o com `abrir_painel.ps1`.

## Verificação

`pipeline/verificacao/verificar_integracao.py` verifica fronteiras temporais, ausência de preenchimento artificial e a integração sem multiplicação. `pipeline/verificacao/verificar_painel_browser.py` usa Playwright e Edge instalados para verificar as quatro abas, mudanças de ano e publicação, alertas, seleção vazia, busca, retorno às 200 unidades e largura de celular. Capturas e resultado em `dados/verificacao_painel/`.
