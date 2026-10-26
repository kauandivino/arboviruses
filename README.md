# Saúde no Território · Goiânia

Monitoramento integrado de dengue e acidentes com escorpiões em Goiânia, a partir de dados públicos oficiais, para planejar ações educativas em oito territórios piloto. Projeto 308-P01 do programa Embaixadores da Cidadania 2026 (pré-projeto em [docs/projeto.pdf](docs/projeto.pdf)).

Tudo aqui usa dados reais coletados das fontes oficiais. Nada é simulado nem estimado para preencher lacunas: meses ou bairros sem dado ficam ausentes, não viram zero. As regras de interpretação estão em [docs/BASE-INTEGRADA.md](docs/BASE-INTEGRADA.md).

## Fontes

| Fonte | Conteúdo | Documentação |
|---|---|---|
| Prefeitura de Goiânia | Informes semanais em PDF (bairros citados), 2022–2026 | [INFORMES](docs/INFORMES.md), [EXTRACAO-INFORMES](docs/EXTRACAO-INFORMES.md), [REVISAO-TERRITORIAL](docs/REVISAO-TERRITORIAL.md) |
| SINAN/DATASUS | Microdados de dengue e de acidentes por animais peçonhentos | [DATASUS](docs/DATASUS.md) |
| IBGE, Censo 2022 | Agregados por setor censitário e malhas de setores e bairros | [IBGE](docs/IBGE.md) |
| SIGGO (Prefeitura) | Divisas de bairro e loteamentos | [MALHA-MUNICIPAL](docs/MALHA-MUNICIPAL.md) |
| CNES | Estabelecimentos de saúde com endereço e coordenadas | [CNES](docs/CNES.md) |
| INMET | Estação automática A002: chuva, temperatura, umidade | [INMET](docs/INMET.md) |

Resultados: [painel, mapa e registro das ações de campo](docs/PAINEL.md), [base integrada](docs/BASE-INTEGRADA.md), [seleção dos oito territórios](docs/SELECAO-TERRITORIOS.md) e [ofício de solicitação de dados à Secretaria](docs/SOLICITACAO-DADOS-SAUDE.md).

## Estrutura

```
pipeline/
  coleta/          download das fontes oficiais (baixar_*)
  processamento/   extração, revisão territorial, integração, seleção, snapshot do painel
  verificacao/     testes de regras (verificar_*) e validações dos dados reais (validar_*)
  comum/           utilitários compartilhados (hash, manifestos, leitura de PDF, OCR)
  exploracao/      sondagens usadas durante o levantamento das fontes; fora do pipeline
painel/            painel web (React + Vite + Recharts)
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
```

Use Python 3.13: o conversor `.dbc` do SINAN não tem wheels para 3.14 no Windows.

## Uso

Tudo roda a partir da raiz:

```powershell
& .venv/Scripts/python.exe -m pipeline                # integração, testes, validações e painel (sem rede)
& .venv/Scripts/python.exe -m pipeline --reprocessar  # refaz antes o processamento dos originais locais
& .venv/Scripts/python.exe -m pipeline --coletar      # baixa antes as versões atuais das fontes oficiais
& .venv/Scripts/python.exe -m pipeline --listar       # mostra as etapas sem executar
.\abrir_painel.ps1                                    # painel e registro de ações em http://127.0.0.1:4173/
```

O pipeline para na primeira etapa que falhar. O painel só é atualizado depois que todos os testes e validações passam, e o registro de cada execução fica em `dados/pipeline_ultima_execucao.json`. Cada etapa também pode rodar sozinha, por exemplo `python -m pipeline.coleta.baixar_cnes`. Veja as opções na documentação de cada fonte.

Quando os informes mudam, a revisão territorial exige uma nova conferência visual humana: o script recusa PDFs cujo hash não confere com as transcrições revisadas. Veja [docs/REVISAO-TERRITORIAL.md](docs/REVISAO-TERRITORIAL.md).

## Versionamento dos dados

O git guarda o código, a documentação, os manifestos com hash e os produtos derivados. Ficam fora do git os originais grandes (ZIP, DBC, PDF), que o pipeline baixa de novo com `--coletar`, e os CSVs de microdados do SINAN por notificação (`dados/datasus/goiania/*.csv`), que também são regenerados.
