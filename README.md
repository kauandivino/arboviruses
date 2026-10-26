# Saúde no Território · Goiânia

Monitoramento integrado de dengue e acidentes com escorpiões em Goiânia, a partir de dados públicos oficiais, para planejar ações educativas em oito territórios piloto. Projeto 308-P01 do programa Embaixadores da Cidadania 2026 (pré-projeto em [docs/projeto.pdf](docs/projeto.pdf)).

Tudo aqui usa dados reais coletados das fontes oficiais. Nada é simulado nem estimado para preencher lacunas: meses ou bairros sem dado ficam ausentes, não viram zero. As regras de interpretação estão em [docs/BASE-INTEGRADA.md](docs/BASE-INTEGRADA.md).

## Fontes

| Fonte | Conteúdo | Documentação |
|---|---|---|
| Prefeitura de Goiânia | Informes semanais em PDF (bairros citados), 2022–2026 | [INFORMES](docs/INFORMES.md), [EXTRACAO-INFORMES](docs/EXTRACAO-INFORMES.md), [REVISAO-TERRITORIAL](docs/REVISAO-TERRITORIAL.md) |
| SINAN/DATASUS | Microdados de dengue e de acidentes por animais peçonhentos (2022–2026); dengue 2014–2021 para treinar os modelos | [DATASUS](docs/DATASUS.md), [MODELAGEM](docs/MODELAGEM.md) |
| IBGE, Censo 2022 | Agregados por setor censitário e malhas de setores e bairros | [IBGE](docs/IBGE.md) |
| SIGGO (Prefeitura) | Divisas de bairro e loteamentos | [MALHA-MUNICIPAL](docs/MALHA-MUNICIPAL.md) |
| CNES | Estabelecimentos de saúde com endereço e coordenadas | [CNES](docs/CNES.md) |
| INMET | Estação automática A002: chuva, temperatura, umidade (2014–2026) | [INMET](docs/INMET.md) |

Resultados: [site público para a população](docs/SITE.md), [painel da equipe e registro das ações de campo](docs/PAINEL.md), [modelos de dengue: nowcasting, previsão e alerta](docs/MODELAGEM.md), [base integrada](docs/BASE-INTEGRADA.md), [seleção dos oito territórios](docs/SELECAO-TERRITORIOS.md) e [ofício de solicitação de dados à Secretaria](docs/SOLICITACAO-DADOS-SAUDE.md).

## Estrutura

```
pipeline/
  coleta/          download das fontes oficiais (baixar_*)
  processamento/   extração, revisão territorial, integração, seleção, snapshot do painel
  modelagem/       nowcasting, previsão de 1 a 8 semanas e diagrama de controle
  verificacao/     testes de regras (verificar_*) e validações dos dados reais (validar_*)
  comum/           utilitários compartilhados (hash, manifestos, leitura de PDF, OCR)
  exploracao/      sondagens usadas durante o levantamento das fontes; fora do pipeline
site/             site público para a população (React + TypeScript + Vite, MapLibre)
painel/            painel técnico da equipe, em /equipe/ (React + Vite + Recharts)
dados/             originais, produtos, manifestos com SHA-256 e relatórios de validação
docs/              documentação por fonte e por etapa
```

## Instalação

O projeto inclui Python 3.13 e Node.js 22.14 portáteis em `.tools/` (fora do git). Em um computador novo, instale o [uv](https://docs.astral.sh/uv/) e o Python 3.13, e use o Microsoft Edge já instalado no Windows. Depois, na raiz:

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements.txt
$env:PATH = "$PWD/.tools/node/node-v22.14.0-win-x64;$env:PATH"
npm ci --prefix painel
npm ci --prefix site
```

Use Python 3.13: o conversor `.dbc` do SINAN não tem wheels para 3.14 no Windows.

## Uso

Tudo roda a partir da raiz:

```powershell
& .venv/Scripts/python.exe -m pipeline                # integração, testes, validações e painel (sem rede)
& .venv/Scripts/python.exe -m pipeline --reprocessar  # refaz antes o processamento dos originais locais
& .venv/Scripts/python.exe -m pipeline --coletar      # baixa antes as versões atuais das fontes oficiais
& .venv/Scripts/python.exe -m pipeline --semanal      # baixa só SINAN e INMET (o mesmo da tarefa agendada)
& .venv/Scripts/python.exe -m pipeline --listar       # mostra as etapas sem executar
.\abrir_painel.ps1                                    # site em http://127.0.0.1:4173/ e painel da equipe em /equipe/
```

### Atualização automática semanal

```powershell
.\agendar_atualizacao.ps1                         # agenda toda segunda-feira às 07:00
.\agendar_atualizacao.ps1 -Dia Friday -Hora 20:30 # outro dia e horário
.\agendar_atualizacao.ps1 -Remover                # cancela o agendamento
.\atualizar_semanal.ps1                           # roda a atualização agora
```

A tarefa roda no Agendador de Tarefas do Windows com o usuário atual: baixa o que mudou no SINAN e no INMET, reprocessa, recalcula os modelos, roda todos os testes e recompila o painel. Se o computador estiver desligado no horário, roda assim que ligar e houver internet. Logs das últimas 20 execuções ficam em `logs/` e o resumo em `dados/pipeline_ultima_execucao.json`. Se algo falhar, o painel anterior permanece. Novos dados não são enviados ao git automaticamente: revise e faça commit quando quiser registrar.

Ficam fora da atualização automática, de propósito: CNES e malhas, que mudariam a seleção dos oito territórios (decisão da equipe), e os informes em PDF, que exigem conferência visual. Para eles, use `--coletar` e siga as instruções de cada documento.

O pipeline para na primeira etapa que falhar. O painel só é atualizado depois que todos os testes e validações passam, e o registro de cada execução fica em `dados/pipeline_ultima_execucao.json`. Cada etapa também pode rodar sozinha, por exemplo `python -m pipeline.coleta.baixar_cnes`. Veja as opções na documentação de cada fonte.

Quando os informes mudam, a revisão territorial exige uma nova conferência visual humana: o script recusa PDFs cujo hash não confere com as transcrições revisadas. Veja [docs/REVISAO-TERRITORIAL.md](docs/REVISAO-TERRITORIAL.md).

## Versionamento dos dados

O git guarda o código, a documentação, os manifestos com hash e os produtos derivados. Ficam fora do git os originais grandes (ZIP, DBC, PDF), que o pipeline baixa de novo com `--coletar`, e os CSVs de microdados do SINAN por notificação (`dados/datasus/goiania/*.csv`), que também são regenerados.
