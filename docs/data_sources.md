# Fontes e variáveis

## WID

Origem: [exportações oficiais por país](https://wid.world/bulk_download/), acompanhadas do catálogo, README e metadados individuais. Conceitos: [dicionário WID](https://wid.world/codes-dictionary/).

| Código canônico | Conteúdo |
|---|---|
| aptinc992j | Média de renda nacional antes dos impostos, adultos equal-split |
| sptinc992j | Participação na renda dos mesmos grupos |
| tptinc992j | Limiares de renda dos mesmos grupos |
| npopul992i | População de 20 anos ou mais |
| npopul999i | População de todas as idades |
| anninc992i | Renda nacional líquida média por adulto |
| anninc999i | Renda nacional líquida média por pessoa |
| mnninc999i | Renda nacional líquida total |
| inyixx999i | Índice de preços |
| xlcusp999i | PPP em moeda local por dólar internacional |

A exportação CSV atualmente organiza o código como `aptincj992`; o código canônico é `aptinc992j`. A aplicação valida a correspondência com as colunas `age` e `pop`, sem inferir o conceito a partir do nome traduzido. Ambos os códigos permanecem disponíveis.

O download considera os códigos nacionais de duas letras com região geográfica no catálogo WID, inclusive códigos históricos ou sem ISO atual. Regiões e subdivisões são catalogadas separadamente, sem tratá-las como países. Códigos sem correspondência são preservados como áreas `unmapped` e reportados. Kosovo usa `XKX`, identificado explicitamente como código atribuído, não ISO oficial.

## WIID — avaliação de cobertura

A [World Income Inequality Database (WIID)](https://www.wider.unu.edu/project/world-income-inequality-database) foi avaliada como fonte complementar. A versão pública mais recente contém estatísticas de desigualdade agrupadas — como Gini e participações de renda — e a WIID Companion é publicada para exploração e exportação pelo WIID Explorer. Esses dados não oferecem uma distribuição anual de 100 percentis observados, comparável à exportação por país da WID.

Por isso, esta carga usa a WID como fonte prioritária de `income_percentiles`: somente grupos percentuais publicados diretamente entram na tabela. A WIID não é usada para preencher, interpolar ou substituir lacunas da WID. Quando o mecanismo de reconstrução de distribuições for implementado, a WIID poderá entrar como uma fonte de estatísticas de validação, com sua versão, seleção e transformação registradas separadamente.

## Banco Mundial

[API Indicators V2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392), fonte WDI (`source=2`), respostas JSON paginadas:

| Indicador | Conteúdo |
|---|---|
| SP.POP.TOTL | População total |
| PA.NUS.PPP | Fator PPP do PIB, moeda local por dólar internacional |

O importador também guarda catálogo de países, metadados dos indicadores, notas das observações, data de atualização no envelope bruto e valores ausentes. Agregados retornados pela API permanecem em `areas` como agregados, sem ISO-3 de país e sem entrar nos totais de cobertura nacional.

## Versão e proveniência

Cada carga congela configuração, filtros, URL, horário, cabeçalhos de versão disponíveis e hashes. A versão interna é a captura identificada no manifesto: ela **não** afirma que todos os arquivos pertencem a um release oficial único. A data de publicação e a licença ficam nulas quando não são fornecidas de forma verificável; isso não constitui uma licença presumida. Citações e notas metodológicas específicas são preservadas em `series` e nos arquivos brutos.

As fontes podem revisar séries históricas entre capturas. Uma atualização cria outra pasta; reconstruir uma captura usa exclusivamente os arquivos daquela pasta.
