# Painel da equipe

Painel técnico do projeto, para a equipe: séries, auditoria, avaliação dos modelos e registro das ações de campo. Fica em http://127.0.0.1:4173/equipe/. Para a população existe o [site público](SITE.md), na raiz do mesmo servidor.

Primeira versão local baseada exclusivamente nos arquivos públicos coletados. Não depende de resposta da Secretaria. Nenhum dado foi publicado na internet.

## Abrir

Com o servidor iniciado, acesse http://127.0.0.1:4173/equipe/ no navegador. Para iniciar novamente, na raiz do projeto:

```powershell
.\abrir_painel.ps1
```

O script inicia `pipeline/servidor.py`, que serve o painel e a API local das ações de campo. O terminal precisa permanecer aberto. Use `-Porta 4174` caso a porta já esteja ocupada e acesse a nova porta. O servidor atende apenas no próprio computador e só aceita gravações vindas da própria página do painel.

## Consultas disponíveis

- Nowcasting (aba Evolução municipal): notificações de dengue por semana de início dos sintomas nas últimas 52 semanas, com a estimativa das digitações ainda esperadas nas 12 mais recentes, faixa de incerteza e avaliação retrospectiva. Método em [MODELAGEM.md](MODELAGEM.md).
- Previsão e alerta (aba Evolução municipal): previsão das próximas 8 semanas, exibida porque superou referências simples no teste de 2021–2025, com as ressalvas por temporada; diagrama de controle do ano atual com as zonas dos cinco anos anteriores, a linha como era vista em cada semana e a avaliação do alerta nas temporadas 2019–2025.
- Evolução municipal: dengue por residência e mês de notificação; escorpiões por ocorrência e mês do acidente. Filtro de ano, histórico completo, situação da fonte e população municipal do Censo 2022.
- Bairros nos informes: publicação, agravo e indicador, valores da lista publicada, correspondência nominal e link para a página do PDF. Combinações inexistentes mostram ausência de observações. Seleções de múltiplas publicações não geram um gráfico agregado.
- Clima: chuva observada, cobertura horária, temperatura e umidade da A002; calendário UTC e tabela de cobertura por variável.
- Unidades de saúde: busca e paginação dos 200 cadastros públicos candidatos a contato. Não comprova funcionamento ou disponibilidade para parceria.
- Mapa: limite municipal (setores IBGE 2022 dissolvidos), 1.208 bairros SIGGO, os 15 territórios elegíveis coloridos pelo número de listas de dengue de 2026 que os citam, os oito selecionados com a ordem de contato e as 200 unidades CNES candidatas, com os parceiros destacados. Zoom pela roda do mouse, por botões ou por pinça; arraste para mover; "Ir para" enquadra um território; clique ou Enter mostra os dados de origem. Geometria real em EPSG:31982 com escala gráfica; contornos simplificados em 8 m (bairros) e 15 m (limite) apenas para exibição. Preparado por `pipeline/processamento/preparar_mapa.py`, testado por `pipeline/verificacao/verificar_mapa.py`; fontes e hashes em `dados/mapa/manifesto.json`. A feição SIGGO 5158 ("Gleba") tem área zero na fonte e fica sem contorno.
- Plano de atuação: oito territórios propostos, presença nas listas em duas configurações de janelas, parceiros candidatos e condições antes de agendar. Justificativa detalhada em SELECAO-TERRITORIOS.md; planilha em dados/selecao_territorios/selecao_e_plano.xlsx.
- Ações de campo: formulário para registrar ações planejadas, realizadas ou canceladas, com data, atividade, território (malha SIGGO), local, unidade parceira (CNES), contagem de participantes, materiais, responsável e observações. Indicadores de execução calculados somente a partir dos registros: ações realizadas, participantes, territórios com ação e materiais distribuídos (só das ações que informaram quantidade). Editar exige motivo e cria uma nova versão. Sem o servidor local, a aba mostra os registros da última compilação, só para leitura.

### Onde ficam os registros

- `dados/acoes_campo/registros.jsonl`: histórico com todas as versões, uma linha por gravação, nunca reescrito. É a fonte oficial e fica versionado no git.
- `dados/acoes_campo/acoes.csv`: estado atual, regenerado a cada gravação, para abrir em planilha.

As regras de validação ficam em `pipeline/acoes_campo.py`: o território precisa existir na malha, a unidade precisa estar entre as candidatas do CNES, uma ação realizada não pode ter data futura e precisa da contagem de participantes, e ações planejadas ou canceladas não aceitam contagens. Não registre nomes de participantes. Faça commit dos registros periodicamente para ter cópia do histórico.

Menus dos componentes permitem consultar fontes e dados da seleção. A interface compartilhada possui alguns controles em inglês. O painel não faz atualizações de fontes sozinho. A data de geração do snapshot não significa que todos os dados tenham essa data de referência.

Não foram criados taxas por bairro, rankings completos, previsões ou atribuição causal. Os limites e a metodologia estão em BASE-INTEGRADA.md. A escolha dos oito territórios continua sendo uma decisão operacional documentada da equipe.

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

`pipeline/verificacao/verificar_integracao.py` verifica fronteiras temporais, ausência de preenchimento artificial e a integração sem multiplicação. `pipeline/verificacao/verificar_painel_browser.py` usa Playwright e Edge instalados para verificar as seis abas, incluindo foco, detalhe e camadas do mapa, mudanças de ano e publicação, alertas, seleção vazia, busca, retorno às 200 unidades e largura de celular. Capturas e resultado em `dados/verificacao_painel/`.
