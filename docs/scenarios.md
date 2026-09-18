# Cenários Equal-Earth

Os cenários em `config/scenarios.yml` só usam distribuições WID com 100 bins percentuais publicados e `distribution_checks.status = passed`. Não há interpolação, ajuste de distribuição ou preenchimento de país ausente.

`hard_equality` calcula primeiro `E`: a média de renda PPP ponderada pela população adulta dos países incluídos no ano resolvido. Em seguida atribui `E` a cada bin. Como o mesmo conjunto de bins define `E` e o cenário, o total antes e depois deve ser igual, dentro da tolerância numérica registrada no resultado.

`relaxed_06_30` aplica o diagnóstico `clip(renda, 0.6E, 3E)`. Seus ganhos exigidos, perdas arrecadadas e diferença orçamentária são sempre publicados. O cenário não redistribui a diferença remanescente: `budget_balanced: false` significa que o teto proposto não financiou exatamente o piso proposto.

## Mediana global e média nacional

`global_median_target` atribui a cada adulto a mediana global ponderada pela população dos bins elegíveis. `global_median_target_full_population` aplica a mesma regra à distribuição estimada de todas as idades. O cálculo ordena as rendas médias dos bins e escolhe a primeira renda cuja população acumulada atinge 50% da população incluída. É a mediana inferior da distribuição discreta de **médias de bins**, não a mediana exata dos indivíduos. Em um empate ou bin que atravesse 50%, a parcela de vencedores pode ser menor que 50%. A mediana é recalculada depois da transformação para população total.

`national_mean_equalization` atribui a cada adulto a média ponderada de seu próprio país. `national_mean_equalization_full_population` usa a média per capita estimada do país. Esses cenários preservam a renda de cada país e não fazem transferências líquidas internacionais. A fração de vencedores pode mudar entre as duas bases porque cada país recebe um fator de escala diferente, mas dentro de cada país ela permanece igual quando a cobertura é idêntica.

Os quatro cenários usam as mesmas distribuições validadas dos cenários antigos. `reference.scope` pode ser `global` ou `national`; `reference.statistic` pode ser `mean` ou `median` nas combinações implementadas. Sem `reference`, a regra antiga de média global continua válida. O resultado nacional registra um alvo por país, não um único valor global. `country_results.json` registra `target_income_ppp`, saldo orçamentário e indicadores de conservação por país; `global_results.json` registra o saldo global. Superávit não distribuído e financiamento exigido são zero quando o saldo está dentro da tolerância numérica de conservação. A mediana global normalmente deixa um superávit; o motor o informa, sem redistribuí-lo automaticamente.

Para executar o conjunto inicial com renda de 2024 em dólares PPP de 2025:

```powershell
foreach ($scenario in @('global_median_target','global_median_target_full_population','national_mean_equalization','national_mean_equalization_full_population')) {
    .\.venv\Scripts\python.exe scripts/run_experiment.py $scenario --year 2024
}
```

`scripts/generate_experiment_comparison.py` gera `outputs/reference_tables/experiment_comparison.md` e `.json` para os sete países de referência. Ele só compara cenários com mesmo ano, base populacional, hash do banco e países incluídos. O alvo, as frações de ganhadores e perdedores, os ganhos e perdas médios e os saldos ficam explícitos.

Cada execução grava `config.json`, `country_results.json`, `reference_country_results.json`, `country_results.parquet`, `global_results.json` e `metadata.json` em `outputs/experiments/{scenario}_{ano}_{fingerprint}/`. Os JSON são a fronteira estável para o frontend; `metadata.json` contém os parâmetros, hashes, ano, lançamento de dados e método.

## Base populacional completa

Os cenários `*_full_population` usam a distribuição adulta publicada como ponto de partida. Para cada país e ano elegível, multiplicam a renda de cada percentil por `npopul992i / npopul999i` e atribuem a cada percentil 1% de `npopul999i`. A transformação preserva a renda total do país, mas supõe que a proporção de adultos seja igual em todos os percentis. Por isso, o resultado é `estimated`, método `adult_shape_scaled_to_total_population`.

O processo exige populações adulta e total positivas no mesmo ano, com `adultos <= população total`; não usa população do Banco Mundial nem ano vizinho. `metadata.json` lista exclusões e linhagem PPP. `input_lineage.json` registra os identificadores de observação, linhas brutas, arquivo de fonte, conversão PPP e índice de preços usados por país. `basis_comparison.json` compara a base adulta e a base completa no mesmo conjunto de países, e `reference_basis_comparison.json` contém os sete países de referência.

As pastas de resultado incluem um fingerprint dos parâmetros e do banco de entrada. Uma execução nunca sobrescreve uma pasta existente. O clamp continua diagnóstico; um solucionador de piso/teto com orçamento equilibrado é trabalho futuro.
