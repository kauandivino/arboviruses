# Formato dos dados por bairro da Secretaria

Formato que o projeto espera receber da Secretaria Municipal de Saúde para analisar e prever por bairro. Ele acompanha o [ofício de solicitação](SOLICITACAO-DADOS-SAUDE.md). O pipeline já está pronto para receber os arquivos: basta colocá-los em `dados/secretaria/recebidos/` e rodar

```powershell
.venv\Scripts\python.exe -m pipeline.coleta.receber_secretaria
```

O validador confere cada regra abaixo e grava o relatório em `dados/secretaria/validacao.json`. Arquivo com erro não entra no pipeline, e o relatório diz o que corrigir. Enquanto nenhum arquivo for recebido, nada é feito e nenhum número é exibido.

## 1. Contagens: `contagens_bairro_semana.csv`

Uma linha por bairro, semana, agravo e indicador. UTF-8, separador vírgula.

| Coluna | Conteúdo | Exemplo |
|---|---|---|
| `codigo_territorio` | Código do bairro ou território usado pela Saúde | `0123` |
| `nome_territorio` | Nome completo | `Parque Atheneu` |
| `distrito_sanitario` | Distrito sanitário | `Leste` |
| `ano_epidemiologico` | Ano da semana epidemiológica | `2026` |
| `semana_epidemiologica` | 1 a 53 | `14` |
| `agravo` | `dengue`, `chikungunya`, `zika` ou `escorpiao` | `dengue` |
| `indicador` | `notificacoes`, `casos_provaveis`, `casos_confirmados`, `internacoes` ou `obitos` | `notificacoes` |
| `referencia_data` | Data que define a semana: `inicio_sintomas`, `notificacao` ou `acidente` | `inicio_sintomas` |
| `referencia_local` | `residencia`, `ocorrencia` ou `notificacao` | `residencia` |
| `valor` | Contagem inteira, maior ou igual a zero, ou vazio | `7` |
| `situacao_valor` | `observado`, `zero_confirmado`, `suprimido` ou `ignorado` | `observado` |
| `data_extracao` | Data em que a base foi extraída (AAAA-MM-DD) | `2026-11-10` |

Regras conferidas pelo validador:

- Colunas obrigatórias presentes, sem colunas com nome diferente.
- Valores das listas acima, semana entre 1 e 53, ano entre 2014 e o ano corrente.
- `valor` inteiro ≥ 0 quando `situacao_valor` é `observado`; `0` quando `zero_confirmado`; vazio quando `suprimido` ou `ignorado`. **Zero e ausência são diferentes** e não são convertidos um no outro.
- Nenhuma linha repetida para a mesma combinação de território, semana, agravo, indicador e referências.
- Todo `codigo_territorio` presente no cadastro (item 2).

## 2. Cadastro dos territórios: `territorios.csv`

| Coluna | Conteúdo |
|---|---|
| `codigo_territorio` | Mesmo código das contagens |
| `nome_territorio` | Nome completo |
| `apelidos` | Outros nomes ou abreviações, separados por `;` |
| `distrito_sanitario` | Distrito sanitário |
| `oid_siggo` | OID do bairro na malha SIGGO, quando houver; vários separados por `;` |
| `relacao_siggo` | `igual`, `parte_de`, `contem`, `parcial` ou `sem_correspondencia` |
| `vigencia_inicio`, `vigencia_fim` | Período em que o território vale (AAAA-MM-DD; fim vazio se vigente) |

Se houver malha própria da Saúde, o projeto pede GeoPackage, GeoJSON ou Shapefile com o sistema de referência; ela é guardada em `dados/secretaria/recebidos/` e usada no lugar da correspondência nominal.

## Depois de validado

Os dados entram numa camada própria, sem substituir as fontes públicas, e servem para:

1. **Mapa por bairro real**, com casos por semana em vez de presença nas listas dos boletins.
2. **Taxas por bairro**, se vierem com população ou se a malha permitir agregar o Censo 2022 com a metodologia documentada.
3. **Previsão por bairro**, avaliada como os modelos municipais: regra registrada antes, validação e teste separados no tempo e exibição só se superar as referências simples.
