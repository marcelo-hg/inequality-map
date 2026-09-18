# Equal-Earth — bases de dados

Base analítica local com **WID + Banco Mundial**, em DuckDB e Parquet. Esta implementação cobre a ingestão e a validação das fontes; não calcula cenários de redistribuição.

A carga verificada em 10/09/2026 contém **6.324.759 observações** e dados para **232 países e territórios**. Consulte o [relatório de cobertura](outputs/reports/data_coverage.md) e a [verificação de reprodutibilidade](outputs/reports/data_validation.json). Os sete países de referência foram reconstruídos offline, sem diferenças nos registros e valores PPP comparados.

## Instalação

Requer Python 3.12 ou superior. Na raiz do projeto, no PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

Alternativa para desenvolvimento: `python -m pip install -e ".[test]"`. As dependências diretas estão fixadas no `pyproject.toml`; o arquivo lock também fixa as transitivas. A implementação foi verificada em Windows/Python 3.14.

## Atualizar os dados

```powershell
.\.venv\Scripts\python.exe -m inequality_map download
```

O comando imprime o caminho da nova pasta em `data/raw/`. O padrão importa todas as áreas nacionais disponíveis, de 2000 até o ano corrente, conforme `config/sources.yml`. Os arquivos WID brutos são exportações completas por país; apenas as variáveis e os anos selecionados entram nas tabelas analíticas, além dos insumos necessários para identificar a base de preços.

Use o caminho impresso no download:

```powershell
.\.venv\Scripts\python.exe -m inequality_map build --snapshot data/raw/IDENTIFICADOR
.\.venv\Scripts\python.exe -m inequality_map validate
.\.venv\Scripts\python.exe -m inequality_map current
```

`build` funciona sem internet. O último comando mostra o arquivo DuckDB atual. O arquivo `database/current.json` aponta para uma pasta que reúne banco, Parquet, relatório e manifesto da mesma construção. O ponteiro só muda após a validação estrutural e a exportação completa; versões anteriores permanecem disponíveis.

## Filtros e retomada

```powershell
python -m inequality_map download --sources wid world_bank --countries BRA USA FRA CHN NOR IND NGA --start-year 2000 --end-year 2025
python -m inequality_map download --snapshot data/raw/IDENTIFICADOR
python -m inequality_map build --snapshot data/raw/IDENTIFICADOR --countries BRA --start-year 2020 --end-year 2024
```

A retomada usa a configuração congelada no manifesto e verifica os arquivos concluídos, sem sobrescrevê-los. Para alterar filtros ou atualizar as fontes, inicie outra carga. Os filtros de construção podem restringir a carga original, mas não ampliar seu período ou cobertura. `--sources world_bank` ainda baixa os dois catálogos de países para manter a correspondência geográfica.

Downloads usam até três tentativas por arquivo e quatro trabalhadores por padrão (`--workers 1` a `8`). Falhas ficam no manifesto e o comando retorna código 2. A construção recusa cargas incompletas, salvo opção explícita `--allow-incomplete`, que mantém esse estado visível nos resultados.

Ao executar fora da raiz, use `python -m inequality_map --root "CAMINHO_DO_PROJETO" ...`. Os scripts de compatibilidade `scripts/download_data.py`, `scripts/build_database.py` e `scripts/validate_data.py` também estão disponíveis.

## Consultar

```python
from pathlib import Path
import duckdb
from inequality_map.build import current_database

path = current_database(Path.cwd())
with duckdb.connect(str(path), read_only=True) as db:
    print(db.sql("""
        SELECT iso3, year, percentile, income_ppp, price_year, input_status
        FROM income_ppp
        WHERE iso3 = 'BRA' AND indicator_code = 'aptinc992j'
          AND percentile = 'p0p100' AND is_requested
        ORDER BY year
    """).fetchall())
```

Cada observação liga-se à série, ao arquivo bruto e à linha original. A consulta `income_ppp` inclui também os identificadores do fator PPP e do índice de preços usados na conversão. Nunca some grupos percentuais sobrepostos ou países com bases monetárias incompatíveis.

## Executar cenários e mapas

As distribuições de 100 percentis publicadas pela WID que passam a validação alimentam os cenários. O ano pode ser informado com `--year`; sem ele, o comando escolhe o último ano validado e o registra nos metadados.

```powershell
.\.venv\Scripts\python.exe -m inequality_map experiment hard_equality
.\.venv\Scripts\python.exe -m inequality_map experiment relaxed_06_30
.\.venv\Scripts\python.exe -m inequality_map experiment hard_equality_full_population
.\.venv\Scripts\python.exe -m inequality_map experiment relaxed_06_30_full_population
.\.venv\Scripts\python.exe -m inequality_map experiment global_median_target --year 2024
.\.venv\Scripts\python.exe -m inequality_map experiment national_mean_equalization --year 2024
.\.venv\Scripts\python.exe -m inequality_map maps --experiment outputs/experiments/hard_equality_2024_v001
```

`hard_equality` calcula o valor de referência E a partir das distribuições utilizadas. `relaxed_06_30` é uma aplicação diagnóstica do piso 0,6E e teto 3E: o resultado sempre informa se o piso e teto conservam o orçamento. Os mapas são SVG determinísticos com os mesmos intervalos de cor 0–10, 10–30, 30–50, 50–70, 70–90 e 90–100%; países sem resultado aparecem em cinza.

Consulte `docs/scenarios.md` para as fórmulas e arquivos de saída.

## Entregas de cada construção

- `inequality.duckdb`: tabelas normalizadas e consultas derivadas.
- `*.parquet`: tabelas e consultas exportadas, incluindo `coverage`, `distribution_checks` e `issues`.
- `coverage_report.md`: resumo legível da cobertura e alertas.
- `coverage_summary.json`: detalhes dos sete países de referência e contagens.
- `build_manifest.json`: entradas, filtros, versão do código, estado e hashes dos artefatos.

Os arquivos volumosos ficam fora do Git. Os arquivos brutos são comprimidos sem perda em gzip; o manifesto guarda SHA-256 tanto do arquivo armazenado quanto do conteúdo HTTP descomprimido.

## Testes e metodologia

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam dados artificiais identificados como fixtures e não dependem das APIs. Validam paginação, falhas, corrupção, duplicação, integridade, intervalos, conversão PPP, filtros e reconstrução offline. Os dados reais são validados durante cada construção. O comando `validate` também verifica os hashes do banco, Parquet e relatórios publicados.

Consulte `docs/data_sources.md`, `docs/methodology.md`, `docs/limitations.md` e `database/README.md` para conceitos e esquema. O plano completo permanece em `PLAN.md`.
