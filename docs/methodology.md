# Metodologia da camada de dados

## Valores publicados e derivados

`observations.value` preserva o valor numérico publicado; `original_value` guarda sua representação original disponível. `source_reported` significa publicado pela fonte, **não** diretamente medido. A fonte pode incorporar estimativas, imputações e projeções. Notas de método, qualidade e citações são mantidas sem tentar deduzir um grau científico a partir de palavras isoladas.

A classificação `derived` é utilizada explicitamente nas conversões PPP e nas consultas que as aplicam. Nenhuma renda é imputada pelo projeto nesta fase. População total, população adulta, renda líquida nacional e renda distribuída antes dos impostos são séries distintas.

## Moeda e preços

Segundo a [nota oficial de conversão WID](https://wid.world/document/convert-wid-world-series/), a renda padrão é expressa em moeda local a preços constantes. Para exportar renda em PPP a preços dessa mesma base, o projeto divide a renda constante pelo fator `xlcusp999i` **do ano-base**, não pelo fator do ano da observação.

O ano-base é identificado apenas quando existe um único ano com `inyixx999i = 1` (tolerância absoluta `1e-10`). A conversão exige o fator positivo desse ano e a moeda informada nos metadados da renda. Sem esses insumos, a renda local permanece disponível e a ausência de conversão é reportada. O benchmark ICP só é rotulado quando identificado inequivocamente nos metadados do fator; caso contrário permanece não especificado.

Não se usa câmbio de mercado, PPP do Banco Mundial ou ano vizinho como substituto. Para uma seleção de anos anterior à base de preços, os dois insumos exatos de conversão são retidos com `is_requested=false`, distinguindo suporte metodológico da cobertura solicitada.

## Intervalos e distribuições

`percentile_groups` guarda os limites e a fração da população, sem confundir média com limiar. Um código de ponto como `p99` permanece um ponto sem limite superior inferido. Intervalos `p0p50`, `p90p100` e `p99p100` podem coexistir; eles não devem ser somados como partição.

Para validar, a aplicação escolhe os menores intervalos adjacentes publicados começando em zero e terminando em 100. Se essa sequência não existir, a distribuição é incompleta. Não há divisão de bins, ajuste de curvas ou interpolação. A consulta `income_percentiles` seleciona apenas bins inteiros de largura 1 explicitamente publicados; sua presença parcial não garante 100 percentis.

Uma partição completa deve ter pesos positivos somando 1 e médias não decrescentes. Compara-se sua média com `aptinc992j/p0p100` (erro relativo máximo 2%) e suas participações inferior 50%, superior 10% e superior 1% com `sptinc992j` (erro absoluto máximo 0,01). Sem as três comparações e a média de referência, o estado é `unverifiable`, mesmo que a estrutura seja consistente. Um limite de grupo que corta um bin não é interpolado para forçar a comparação.

Rendas e participações negativas são preservadas e sinalizadas. Populações, índices e fatores não positivos são preservados como evidência de origem, sinalizados e impedem conversões que dependam deles.

## Referências dos experimentos

Os cenários calculam a referência usando exclusivamente as distribuições elegíveis transformadas para a base populacional escolhida. A média global divide a soma da renda dos bins pela soma de suas populações. A mediana global é a primeira renda média de bin que atinge pelo menos metade da população acumulada após ordenação por renda; não interpola rendas dentro dos bins. A média nacional usa os mesmos pesos e rendas, restritos a cada país. O `metadata.json` registra escopo, estatística, método, moeda PPP e ano de preços; os resultados nacionais registram o alvo aplicado a cada país. O saldo assinado é `renda_depois - renda_antes`, com conservação avaliada por tolerância numérica relativa ao total inicial.

## Publicação local

Uma construção gera uma pasta nova. Restrições do esquema e verificações de referências impedem publicação de corrupção estrutural. Problemas científicos e lacunas permanecem nas tabelas e nos relatórios, não são removidos para produzir aparência de cobertura completa. O ponteiro `database/current.json` só muda após os artefatos estarem completos.

Resultados de distribuições inválidas não devem alimentar mapas ou experimentos futuros sem tratamento explícito. Essa etapa ainda não produz esses resultados.
