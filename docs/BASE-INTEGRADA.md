# Saúde no Território — versão com bases disponíveis

O projeto passa a funcionar com os arquivos públicos já coletados. Nenhuma etapa de análise, planejamento ou entrega fica condicionada a resposta da Secretaria. Novos dados serão uma ampliação versionada, preservando os resultados reproduzíveis desta versão.

## Entrega executada

`dados/base_integrada/base_integrada.xlsx` reúne sete abas, também disponíveis como CSV:

- `municipal_mensal_clima`: registros SINAN por agravo e mês, com contexto da estação A002. Dengue: residência em Goiânia e data da notificação. Escorpiões: ocorrência em Goiânia e data do acidente. Os números representam registros de todas as classificações, sem afirmar casos confirmados ou pessoas únicas.
- `bairros_publicados`: observações territoriais revisadas, preservando edição, janela, indicador, página e pendências. Cada edição permanece separada.
- `clima_mensal`: 57 meses da A002 com cobertura, valores observados e completos; calendário UTC.
- `parceiros_candidatos`: 200 cadastros públicos, sem motivo registrado de desativação e com coordenadas dentro da malha municipal. Funcionamento e interesse em parceria precisam de verificação em campo.
- `contexto_censo_2022`: população municipal e quantidade de setores, com referência explícita a 2022.
- `exclusoes_temporais`: contagens excluídas da série por data ausente ou externa ao ano do arquivo.
- `definicoes`: regras de interpretação e integração futura.

O manifesto registra hashes dos insumos e verificações executadas. Não houve novos downloads nesta integração.

## Regras que definem esta versão

O SINAN é a referência para evolução municipal; os informes descrevem os bairros citados em cada publicação. As duas fontes não são somadas. Não preenchemos meses ou bairros ausentes com zero. A existência de registros no mês não comprova que ele esteja completo. Arquivos preliminares continuam identificados e 2026 permanece um ano parcial.

Cada arquivo anual contribui com as notificações cuja data está dentro do ano civil ou do ano epidemiológico que ele cobre (os de dengue seguem o ano epidemiológico), e a integração verifica que nenhuma notificação aparece em dois arquivos. A regra anterior, só pelo ano civil, perdia notificações nas viradas de ano e foi corrigida em 26/10/2026; detalhes em [MODELAGEM.md](MODELAGEM.md#regra-dos-arquivos-anuais-correção-de-26102026). A série continua sendo um recorte operacional dos arquivos disponíveis. Datas excluídas ficam auditáveis. A data da notificação da dengue não é a data de início dos sintomas; a comparação temporal com clima é contextual.

Os informes oferecem listas selecionadas e janelas que se sobrepõem. A seleção de oito territórios será uma escolha operacional documentada, não uma afirmação de que são os oito bairros de maior risco. Não haverá taxas por bairro, população atribuída por área, diferença de acumulados apresentada como incidência, nem estimativa de dados ausentes. Correspondência nominal com SIGGO não comprova limites usados pela vigilância.

## Organização das próximas entregas

1. Painel municipal: séries separadas de dengue e acidentes por escorpiões, com situação da fonte e cobertura climática. Comparações devem usar meses equivalentes e explicitar períodos parciais.
2. Consulta territorial: selecionar uma publicação, agravo e indicador de cada vez; mostrar os bairros citados, sua página de origem e a situação da correspondência. Listas com período inconsistente continuam identificadas.
3. Planejamento de campo: registrar oito territórios escolhidos, justificativa baseada na publicação consultada, viabilidade de acesso, parceiro candidato e decisão da equipe. Maior frequência de aparição nas listas pode orientar exploração, mas não mede maior risco.
4. Avaliação das ações: registrar data, local, atividade, participantes e materiais utilizados a partir da execução real. Esses dados ainda não existem e não serão simulados. A avaliação inicial será de execução e alcance; atribuir redução de casos às atividades exigiria outro desenho de estudo.

O painel interativo local foi criado na etapa seguinte, com Node.js portátil no projeto. Consulte PAINEL.md para abrir, atualizar e verificar. A planilha e os CSVs continuam disponíveis de forma independente.

## Reprodução

Na raiz do projeto, em PowerShell:

```powershell
& .venv/Scripts/python.exe -m pipeline.processamento.integrar_bases
& .venv/Scripts/python.exe -m pipeline.verificacao.verificar_integracao
```

Novos dados devem entrar em uma camada própria com fonte, versão, período, definição, granularidade e chaves. Só depois da comparação metodológica poderão substituir ou complementar indicadores existentes. Os arquivos públicos originais e as pendências permanecem preservados.
