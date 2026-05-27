# etl_virtuellaherbariet - Virtuella Herbariet ETL Pipeline

ETL pipeline for downloading and transforming herbarium data from Virtuella Herbariet API (https://api.virtuellaherbariet.se/) to DarwinCore standard.

## Requirements

- Python 3.12+
- Docker (optional)

## Installation

### Local Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Configure environment variables
cp .env.example .env
# Edit .env with real credentials
```

### Docker Setup

```bash
# Configure environment variables
cp .env.example .env

# Build the image
docker-compose build
```

## Usage

### Local Execution

```bash
# Preferred (local dev): run via Python script
python main.py --config config-mappings/gb.yml --action all
python main.py --config config-mappings/gb.yml --action download
python main.py --config config-mappings/gb.yml --action process
python main.py --config config-mappings/gb.yml --action process --strict
```

### Docker Execution

```bash
# Build the image
docker-compose build

# Run full ETL pipeline (download + process)
# Uses docker-compose default command:
# --config /app/config-mappings/gb.yml --action all
docker-compose up etl

# Run in detached mode
docker-compose up -d etl

# Override command for download only
docker-compose run --rm etl --config /app/config-mappings/gb.yml --action download

# Override command for process only
docker-compose run --rm etl --config /app/config-mappings/gb.yml --action process

# View logs
docker-compose logs -f etl
```

## Configuration

Edit `config-mappings/gb.yml` to customize:

- **herbarium**: Institution code (e.g., "GB")
- **downloadDir**: Directory for raw data (default: "verbatim")
- **processedDir**: Directory for processed data (default: "processed")
- **chunkSize**: Number of rows processed per chunk (default: 50000)
- **mappings**: Column name mappings to Darwin Core terms
- **defaults**: Default values for columns
- **transformations**: Data transformations to apply
- **database**: Database configuration (non-secret values such as table and mode)
- **load.duplicatePolicy** (or `database.duplicatePolicy`): duplicate strategy
  - `drop_all_duplicates`
  - `keep_first` (default)
  - `keep_last`
  - `write_only`

Database credentials are read from environment variables:

- `ETL_DB_USER`
- `ETL_DB_PASSWORD`
- `ETL_DB_HOST`
- `ETL_DB_PORT`
- `ETL_DB_NAME`

`python main.py` loads `.env` automatically for local runs, and Docker Compose loads `.env` via `env_file`.

Database write mode:

- `database.mode="ignore"`: insert and skip duplicate-key rows (`INSERT IGNORE`)
- `database.mode="upsert"`: insert or update on duplicate key (`ON DUPLICATE KEY UPDATE`)

Strict mode:

- Enable with `--strict`
- Fails when:
  - malformed rows > 0
  - duplicate rows dropped > 0
- Repaired rows are allowed but logged as warning


## Output

- **CSV**: `data/processed/<HERBARIUM>/dwc_<herbarium>.csv` - Processed Darwin Core rows (tab-separated)
- **Duplicate audit**: `data/processed/<HERBARIUM>/duplicates_<herbarium>.csv` (when duplicates exist)
- **Malformed rows**: `data/malformed/<HERBARIUM>_malformed.csv` (when malformed rows exist)
- **Quality reports**:
  - `data/processed/<HERBARIUM>/quality_report_<herbarium>_<runid>.json`
  - `data/processed/<HERBARIUM>/quality_report_<herbarium>.json` (latest)
- **Reconciliation reports**:
  - `data/processed/<HERBARIUM>/reconciliation_<herbarium>_<runid>.json`
  - `data/processed/<HERBARIUM>/reconciliation_<herbarium>.json` (latest)
- **Database**: Rows are written directly to MySQL when `database.writeToDatabase=true`

## License

MIT
