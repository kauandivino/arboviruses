# Fontes complementares

Quatro fontes acrescentadas em 27/10/2026. Todas entram no pipeline e no site, com as mesmas regras do resto do projeto: origem e hash registrados, nada preenchido nem estimado onde falta dado, e problemas da fonte marcados em vez de corrigidos em silêncio.

## Chikungunya e zika (SINAN)

- **Arquivos:** nacionais `CHIKBR` (2014 em diante) e `ZIKABR` (2015 em diante; não há arquivo de zika de 2014), baixados em `dados/datasus_arboviroses/`.
- **Processamento:** `pipeline/coleta/extrair_regional.py` grava só contagens agregadas por semana de início, para Goiânia, vizinhos e resto de Goiás, com as mesmas regras da dengue.
- **Volume em Goiânia:**
  - chikungunya passou de algumas dezenas por ano até 2021 para 1.420 em 2022 e 913 em 2026 (até outubro);
  - zika teve a epidemia de 2016 (8.765) e hoje soma algumas dezenas por ano.
- **Uso:** descritivo, na seção "Chikungunya e zika" do site. Volume semanal baixo demais para treinar modelos.

## LIRAa (informes da Prefeitura)

- **Conteúdo:** os informes trazem o resultado municipal de cada ciclo do Levantamento Rápido de Índices para *Aedes aegypti*: período, índice de infestação predial (IIP), índice de Breteau, estratos em risco baixo, médio e alto e situação geral.
- **Não há dado por bairro:** a geografia dos 74 estratos não é publicada, por isso o LIRAa não vai para o mapa.
- **Extração:** `pipeline/processamento/extrair_liraa.py` lê o texto já extraído dos PDFs e encontrou **18 ciclos, de outubro de 2021 a maio de 2026**.
  - Ciclos repetidos em vários informes precisam ter valores idênticos; não houve divergência.
  - Em todos os ciclos, os estratos somam 74 e a situação bate com o IIP pelas faixas do Ministério da Saúde.
- **Revisão visual** (`dados/liraa/revisao_visual.json`): três ciclos com problema na própria fonte foram conferidos na imagem da página.
  - Janeiro de 2023: IB publicado menor que o IIP. Mantido como publicado e marcado.
  - Novembro de 2024 e janeiro de 2025: os valores do *aegypti* foram impressos na linha do *albopictus*. Foram atribuídos ao *aegypti* por coerência com a situação geral, e o que ficou ambíguo não recebe valor.
- **Uso:** gráfico "Onde está o mosquito" no site, com as faixas de risco do Ministério da Saúde.

## InfoDengue (Fiocruz/FGV)

- **Coleta:** `pipeline/coleta/baixar_infodengue.py` consulta a API pública toda semana, para dengue e chikungunya (zika não está disponível para Goiânia). Cada resposta bruta tem o hash registrado.
- **Outra alimentação do SINAN:** o InfoDengue usa uma base diferente da dos arquivos públicos do DATASUS e conta de 18% a 44% mais notificações por semana. A diferença aparece em qualquer recorte (residência, local ou data de notificação) e cresceu ao longo dos anos. As duas séries têm correlação de 0,975, ou seja, retratam a mesma epidemia em níveis diferentes.
- **Comparação** (`pipeline/modelagem/infodengue.py`):
  - Por causa da diferença de nível, as estimativas não são combinadas em número absoluto.
  - A partir de 01/11/2026, cada coleta grava as estimativas recentes das duas fontes em `dados/infodengue/registro_estimativas.csv`, um registro que só cresce.
  - Cada estimativa é avaliada contra a contagem da própria fonte 12 semanas depois.
  - Com 26 semanas avaliadas, documenta-se qual nowcasting erra menos. A regra foi registrada antes de qualquer resultado.
- **Rt no site:** o ritmo de transmissão é uma razão entre semanas e não depende do nível absoluto. O site mostra as últimas 12 semanas com a linha do 1, avisa que o último ponto é incompleto e dá o crédito ao InfoDengue.

## Saneamento do Censo 2022

- **Processamento:** `pipeline/processamento/saneamento_bairros.py` calcula, por bairro da malha SIGGO, a porcentagem de domicílios:
  - fora da rede geral de água;
  - com água que não chega encanada dentro de casa;
  - com lixo não coletado;
  - com esgoto inadequado.
- **Método,** sem rateio por área:
  - cada setor censitário vai inteiro para o bairro que contém a maior parte dele;
  - setores com menos de 80% da área nesse bairro ficam de fora;
  - células sob sigilo do IBGE ficam sem valor;
  - o indicador só é publicado com 70% de cobertura dos domicílios e pelo menos 50 domicílios.
- **Resultado:** 455 bairros com algum indicador.
  - Coleta de lixo e água encanada são quase universais.
  - Esgoto inadequado é o indicador que mais varia, com média de 16% e bairros periféricos chegando a 100%.
- **Uso:** contexto na ficha do bairro no mapa. Sem dado por bairro de casos, esses indicadores não entram em modelo nem em ranking.

## Reprodução

Tudo roda em `python -m pipeline`; as coletas entram em `--coletar` e `--semanal`. Os testes estão em `pipeline/verificacao/verificar_novas_fontes.py`.
