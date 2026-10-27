# Solicitação de dados agregados — projeto Saúde no Território

À Secretaria Municipal de Saúde de Goiânia

Assunto: dados agregados por bairro e referência territorial para ações de prevenção de dengue e acidentes com escorpiões.

O projeto **Saúde no Território: Monitoramento Integrado de Riscos à Saúde e Mobilização Comunitária** pretende apoiar a identificação de áreas prioritárias e o planejamento de atividades educativas e parcerias em Goiânia. Para isso, solicitamos os conjuntos agregados abaixo, de janeiro de 2022 até o último período disponível de 2026, indicando a data de atualização e quais períodos são preliminares.

1. **Dengue por bairro de residência e período:** contagens de notificações, casos prováveis e casos confirmados, em colunas ou indicadores separados. Preferimos semana epidemiológica; se não estiver disponível, mês. Solicitamos informar qual data define o período — início dos sintomas, notificação ou outra — e as definições/filtros dos indicadores. Quando disponíveis, incluir casos graves e óbitos em campos separados.

2. **Acidentes com escorpiões por bairro e período:** contagem específica de acidentes por escorpiões, distinguindo o local do acidente da residência do paciente e do local de notificação. Solicitamos indicar qual referência está disponível e qual data define o período. Avistamentos, capturas ou reclamações, caso disponíveis, podem ser fornecidos em tabela separada, sem misturar esses eventos com acidentes notificados.

3. **Cadastro e limites territoriais usados pela Saúde:** código, nome completo, aliases/abreviações, distrito sanitário e vigência de cada unidade territorial. Solicitamos a malha correspondente, preferencialmente GeoPackage, GeoJSON ou Shapefile, com o sistema de referência. Se houver relação com bairros/loteamentos SIGGO ou setores censitários do IBGE, solicitamos a tabela de correspondência e a indicação de relações parciais ou múltiplas. Esclarecer mudanças de limites, etapas e áreas não abrangidas.

4. **Séries completas e documentação:** contemplar todos os bairros/territórios da cobertura informada, distinguindo zero confirmado de dado ausente, ignorado, não publicado ou suprimido. Solicitamos dicionário de campos e códigos, regras de atualização/revisão, período de fechamento, município de referência e metodologia para evitar duplicidades de notificações. Não é necessário disponibilizar nomes, CPF, endereços individuais ou identificadores pessoais.

5. **Esclarecimentos dos informes já publicados:**
   - Informes SE 09 e 10/2024, quadros 5 e 8, páginas 5 e 7: esclarecer o início/fim do período de cada tabela por bairro e se são acumulados do ano, ocorrências da semana ou outra janela.
   - Informe SE 10/2024, quadro 8, página 7: confirmar definições e ordem das colunas. Em sete bairros, os valores da coluna “Casos confirmados” superam os da coluna “Casos Prováveis”. Preservamos os valores publicados e não invertemos as colunas. Os bairros são Setor Sudoeste, Bairro Capuava, Jardim Novo Mundo, Jardim Balneário Meia Ponte, Bairro Cidade Jardim, Setor Oeste e Setor Novo Horizonte.
   - Informe SE 35/2026, gráfico 4, página 3: a legenda informa “últimas 4 semanas (SE 32 a 36)”, um intervalo de cinco semanas e com término posterior ao número da edição. Solicitamos confirmar o intervalo correto e os valores correspondentes.
   - Informe SE 26/2026, gráfico 4, página 3: informar o nome completo de “SET URIAS MAGAL...”. Informe SE 32/2026, gráfico 4, página 3: informar os nomes completos de “SET DOS...” e “SET LESTE...”.
   - Confirmar o território de **Jardim Curitiba I**, pois a captura SIGGO disponível contém “Jd Curitiba” sem o indicador de etapa; **Vila São José**, pois encontramos complemento/extensão; **Sítio Rec. Morada do Sol**, pois o candidato nominal tem tipo “Setor”; e **Parque Amazonas**, enquanto a camada municipal usa “Prq Amazônia”. A tabela anexa inclui as demais pendências, inclusive abreviações das edições 16 e 19/2026.
   - Se possível, esclarecer o critério/versão das contagens das edições 18–20/2026: por exemplo, o rótulo Jardim Curitiba I aparece com 260, 787 e 204 notificações, respectivamente, em legendas de quatro semanas. Não estamos afirmando que os valores estejam errados; precisamos confirmar sua comparabilidade e eventuais revisões.
   - Se possível, confirmar as extrações dos gráficos das edições 37 e 38/2026: a sequência dos dez valores é idêntica, mas os bairros associados mudam. Precisamos preservar corretamente as versões e referências temporais.

6. **Denominadores, caso disponíveis:** população por bairro com ano de referência, metodologia e limites territoriais usados. Já possuímos o Censo 2022 por setor; não o apresentaremos como população observada em 2026 nem faremos rateio automático sem validar a correspondência territorial.

O formato exato que o projeto consegue receber e validar automaticamente está em [DADOS-SECRETARIA.md](DADOS-SECRETARIA.md): uma tabela de contagens por território e semana e um cadastro dos territórios com a correspondência à malha SIGGO. Se não for possível seguir esse formato, aceitamos **CSV ou XLSX** com dicionário e metadados. Uma estrutura útil contém município, código/nome do bairro, agravo, indicador, período inicial/final ou ano/semana epidemiológica, referência geográfica, quantidade, situação do dado, data de atualização e versão. Caso o nível solicitado não esteja disponível, pedimos informar a menor unidade territorial e periodicidade disponibilizáveis.

Anexos sugeridos, disponíveis em `dados/revisao_territorial/`:

- `lista_lacunas_para_sms.csv`: itens solicitados e evidências.
- `pendencias_territoriais.csv` e `candidatos_siggo.csv`: rótulos, publicações e alternativas nominais.
- `inconsistencias_fonte.csv`: ocorrências para esclarecimento.
- `revisao_territorial.xlsx`: base revisada e tabelas auxiliares.

Responsável: [preencher nome e contato]

Data do levantamento que fundamenta este pedido: 19/10/2026.
