# Oito territórios propostos para atuação

Seleção operacional condicionada às verificações locais. A ordem abaixo organiza os contatos; não é ranking de risco nem cronograma confirmado.

## Critérios e recorte

Dengue: seis listas de notificações dos informes de 2026, edições SE16, 20, 24, 28, 32 e 36. Cada lista descreve quatro semanas; as janelas vão de SE13 a SE36 e não se sobrepõem. Contamos em quantas listas o território aparece, sem somar seus casos. A última edição utilizável é SE36: SE37/38 repetem valores com rótulos diferentes e SE35 tem legenda temporal divergente. O ano de 2024 não entra nesta seleção porque o período das tabelas não está esclarecido.

Só entram correspondências nominais únicas, ainda sem homologação de limites. Entre os territórios com parceiros candidatos até 3 km do polígono, priorizamos maior presença nas seis listas; a última edição citada e o OID desempatam. O limite de 3 km e a tolerância cadastral de 250 m são escolhas operacionais exploratórias, sem comprovar acessibilidade ou distância entre moradores e unidades.

As janelas alternativas terminam em SE14, 18, 22, 26, 30 e 34. Os mesmos oito territórios foram selecionados: True. Essa verificação não elimina o viés das listas publicadas.

Para os parceiros, usamos centros/unidades básicas e policlínicas públicas, sem motivo cadastral de desativação e dentro da malha municipal. Distritos sanitários classificados como unidade básica são excluídos pelo nome. A posição é confrontada com o bairro cadastrado; divergências ou nomes sem correspondência única não são usados como prova de proximidade. Correspondências sem o tipo territorial ficam identificadas como exploratórias.

## Territórios, evidências e parceiros

| Ordem de contato | Território SIGGO candidato | Listas principal / alternativa | Parceiro candidato | Distância mínima ao polígono |
|---|---|---|---|---|
| 1 | Prq Atheneu | 5/6 · 6/6 | USF PARQUE ATHENEU (CNES 2665239) | 24 m |
| 2 | S Leste Vila Nova | 5/6 · 5/6 | USF LESTE UNIVERSITARIO (CNES 3402177) | 120 m |
| 3 | Jd Novo Mundo | 4/6 · 5/6 | CS JARDIM NOVO MUNDO (CNES 4313593) | 0 m |
| 4 | S Parque Tremendão | 4/6 · 4/6 | USF NOVO PLANALTO (CNES 2506742) | 180 m |
| 5 | Vl Finsocial | 3/6 · 5/6 | CS FINSOCIAL (CNES 4314204) | 0 m |
| 6 | S Pedro Ludovico | 5/6 · 5/6 | CS HORTENCIA MENDONCA VILA REDENCAO (CNES 2339544) | 317 m |
| 7 | S Urias Magalhães | 5/6 · 5/6 | CS FAMA (CNES 2338521) | 1345 m |
| 8 | Jd Nova Esperança | 4/6 · 5/6 | CS FINSOCIAL (CNES 4314204) | 1299 m |

Os nomes acima seguem a malha SIGGO candidata. As grafias literais dos informes e os links de página estão na aba evidencias_janelas. Distância zero significa ponto cadastral dentro do polígono; não significa deslocamento zero. Não pressupomos que a unidade atenda aquele território.

## Execução proposta

Começar pela primeira rodada de articulação, com os parceiros situados dentro ou até 250 m do polígono, e realizar uma atividade por vez. Após a primeira atividade, revisar esforço, participação e materiais antes de ampliar. A segunda rodada depende especialmente da confirmação do deslocamento e da abrangência das unidades externas ao território.

A atividade inicial proposta é um encontro educativo e de escuta, seguido, se houver condições e acordo local, de observação ambiental no espaço definido. Não estão previstos manejo de animais, aplicação de produtos ou coleta de dados clínicos. Materiais de prevenção devem passar pela revisão técnica do parceiro. O endereço e telefone cadastrais estão na planilha para conferência; nenhum contato foi enviado.

CS Finsocial aparece como parceira candidata de Vila Finsocial e Jardim Nova Esperança. Registrar disponibilidade por ação e manter alternativas; não reservar capacidade nem duplicar público atendido entre atividades. A data, o orçamento, os percursos e os responsáveis não foram inventados e permanecem em branco.

Se houver recusa ou inviabilidade, consultar outro parceiro da aba parceiros_candidatos; se o território continuar inviável, usar a ordem de reserva da aba candidatos_e_reservas. A ausência de um bairro nas seis listas não demonstra ausência de casos. Jardim Curitiba I permanece fora por identificação territorial ambígua, embora apareça nas listas.

## Ajuste necessário na justificativa do projeto

Substituir “8 bairros mais urgentes” por “oito territórios priorizados para um piloto, com base na presença recorrente nas listas públicas de dengue, na identificação territorial disponível e em parceiros candidatos para articulação local”. Não há evidência territorial suficiente para dizer que esses oito têm maior risco de acidentes com escorpiões. O tema pode integrar as atividades educativas, sem afirmar priorização epidemiológica por bairro.

A população do Censo 2022 e as variáveis climáticas da estação municipal não foram usadas para ordenar bairros. Não permitem inferir vulnerabilidade, saneamento ou microclima destes territórios sem outra metodologia.

## Reprodução e fontes

Executar na raiz: .venv/Scripts/python.exe -m pipeline.processamento.selecionar_territorios. Insumos, hashes e parâmetros estão em dados/selecao_territorios/manifesto.json. Fontes: dados/base_integrada/bairros_publicados.csv; parceiros_candidatos.csv; malha municipal SIGGO de análise; CNES competência 202609. Não houve nova coleta nem contato externo.
