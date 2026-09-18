# Esquema e arquivos

O esquema SQL canônico, incluído no pacote instalado, está em `src/inequality_map/schema.sql`. `schema_version` identifica a versão 1. Alterações futuras de esquema exigem reconstrução a partir dos brutos, sem modificar a captura original.

| Tabela/consulta | Finalidade |
|---|---|
| countries | Dimensão ISO-3 e exceções explicitamente identificadas |
| areas / country_codes | Códigos originais, correspondências e agregados separados |
| sources / source_files | Capturas, arquivos, hashes, URLs e datas |
| series | Conceitos, unidades, moeda, ano-base, notas e citações |
| observations | Valores originais, qualidade, período e linha de origem |
| percentile_groups | Limites dos grupos publicados |
| ppp_conversions | Fatores e referências aos insumos da conversão |
| income_ppp | Renda calculada com PPP compatível e linhagem explícita |
| income_percentiles | Bins inteiros de largura 1 publicados pela fonte |
| distribution_checks | Resultado da validação por área e ano |
| coverage | Grade de cobertura nacional por fonte, série e ano |
| issues | Falhas de download, dados problemáticos e incompatibilidades |
| ingestion_runs | Configuração e versão do código de cada carga |

O banco e os Parquet ficam juntos em `data/processed/releases/IDENTIFICADOR/`. `database/current.json` identifica a construção publicada. Esse desenho evita atualizar o banco e os Parquet em momentos diferentes; não há uma segunda cópia mutável em `database/inequality.duckdb`.

IDs de observações são determinísticos por série, ano e grupo percentual. Cada construção contém uma captura, impedindo misturar revisões distintas silenciosamente. Novas construções não acumulam duplicatas da anterior.
