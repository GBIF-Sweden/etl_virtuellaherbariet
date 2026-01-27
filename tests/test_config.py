import pytest
import yaml

from config import ConfigError, load_config


def _write_config(path, mode='ignore'):
    path.write_text(
        yaml.safe_dump(
            {
                'herbarium': 'GB',
                'mappings': {'catalog': 'catalogNumber'},
                'database': {
                    'writeToDatabase': False,
                    'hostname': 'localhost',
                    'port': 3306,
                    'dbname': 'db',
                    'table': 'tbl',
                    'pk_column': 'occurrenceID',
                    'mode': mode,
                },
            },
            sort_keys=False,
        ),
        encoding='utf-8',
    )


def test_load_config_accepts_valid_database_mode(tmp_path):
    cfg = tmp_path / 'valid.yml'
    _write_config(cfg, mode='upsert')

    loaded = load_config(str(cfg))
    assert loaded['database']['mode'] == 'upsert'


def test_load_config_rejects_invalid_database_mode(tmp_path):
    cfg = tmp_path / 'invalid.yml'
    _write_config(cfg, mode='merge')

    with pytest.raises(ConfigError, match="database.mode must be 'ignore' or 'upsert'"):
        load_config(str(cfg))


def test_load_config_rejects_invalid_chunk_size(tmp_path):
    cfg = tmp_path / 'invalid_chunk.yml'
    cfg.write_text(
        yaml.safe_dump(
            {
                'herbarium': 'GB',
                'chunkSize': 0,
                'mappings': {'catalog': 'catalogNumber'},
            },
            sort_keys=False,
        ),
        encoding='utf-8',
    )

    with pytest.raises(ConfigError, match="Field 'chunkSize' must be a positive integer"):
        load_config(str(cfg))


def test_load_config_rejects_invalid_download_dir(tmp_path):
    cfg = tmp_path / 'invalid_download_dir.yml'
    cfg.write_text(
        yaml.safe_dump(
            {
                'herbarium': 'GB',
                'downloadDir': '',
                'mappings': {'catalog': 'catalogNumber'},
            },
            sort_keys=False,
        ),
        encoding='utf-8',
    )

    with pytest.raises(ConfigError, match="Field 'downloadDir' must be a non-empty string"):
        load_config(str(cfg))
