# Production Runbook

## Standard run
```bash
python main.py --config config-mappings/ups.yml --action all
```

## Strict gate run
```bash
python main.py --config config-mappings/ups.yml --action process --strict
```

Strict mode fails when:
- malformed rows > 0
- duplicate rows dropped > 0

Strict mode does not fail on repaired rows; it logs a warning.

## Post-run checks
- Output file exists:
  - `data/processed/<HERBARIUM>/dwc_<herbarium>.csv`
- Quality report exists:
  - `data/processed/<HERBARIUM>/quality_report_<herbarium>.json`
- Reconciliation exists:
  - `data/processed/<HERBARIUM>/reconciliation_<herbarium>.json`
- Validate key metrics:
  - `extraction.repaired_rows_total`
  - `extraction.malformed_rows_total`
  - `transformation.duplicates.duplicate_rows_dropped`
  - `row_counts.total_output_rows`
  - `output_checksum_sha256`

## Failure triage
1. Download failures:
- check API reachability and retry logs
- verify timeout/retry config
2. Strict mode failures:
- inspect malformed file under `data/malformed/`
- inspect duplicates audit under `data/processed/<HERBARIUM>/`
3. DB failures:
- verify env credentials (`ETL_DB_*`)
- verify table schema / PK constraints
- rerun with DB write disabled to isolate upstream stages

## Rollback
- Keep run-tagged quality + reconciliation reports.
- Re-run previous known-good config/image tag if output regression is detected.
