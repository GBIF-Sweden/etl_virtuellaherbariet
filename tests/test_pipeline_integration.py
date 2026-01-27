import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline import process_csv


def _write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for row in rows:
            fh.write(",".join(row) + "\n")


def _base_config(tmp_path: Path, duplicate_policy: str):
    return {
        "herbarium": "TST",
        "downloadDir": str(tmp_path / "verbatim"),
        "processedDir": str(tmp_path / "processed"),
        "chunkSize": 1000,
        "mappings": {
            "instcode": "institutionCode",
            "accessionno": "catalogNumber",
            "taxaname": "scientificName",
        },
        "defaults": {"collectionCode": "BOT"},
        "transformations": [
            {
                "column": "occurrenceID",
                "type": "combine_columns",
                "columns": ["institutionCode", "collectionCode", "catalogNumber"],
                "separator": ":",
            }
        ],
        "database": {"writeToDatabase": False, "duplicatePolicy": duplicate_policy},
    }


def test_integration_duplicate_policy_keep_first(tmp_path):
    csv_path = tmp_path / "verbatim" / "TST.csv"
    _write_csv(
        csv_path,
        ["instcode", "accessionno", "taxaname"],
        [["TST", "A1", "N1"], ["TST", "A1", "N1-dup"], ["TST", "A2", "N2"]],
    )
    config = _base_config(tmp_path, "keep_first")
    process_csv(config, str(csv_path), strict=False)

    out = pd.read_csv(tmp_path / "processed" / "dwc_tst.csv", sep="\t")
    assert len(out) == 2
    assert set(out["catalogNumber"]) == {"A1", "A2"}

    report = json.loads((tmp_path / "processed" / "quality_report_tst.json").read_text(encoding="utf-8"))
    assert report["transformation"]["duplicates"]["policy"] == "keep_first"
    assert report["transformation"]["duplicates"]["duplicate_rows_detected"] >= 1

    rec = json.loads((tmp_path / "processed" / "reconciliation_tst.json").read_text(encoding="utf-8"))
    assert rec["output_checksum_sha256"]
    assert rec["row_counts"]["total_output_rows"] == 2


def test_integration_duplicate_policy_drop_all_duplicates(tmp_path):
    csv_path = tmp_path / "verbatim" / "TST.csv"
    _write_csv(
        csv_path,
        ["instcode", "accessionno", "taxaname"],
        [["TST", "A1", "N1"], ["TST", "A1", "N1-dup"], ["TST", "A2", "N2"]],
    )
    config = _base_config(tmp_path, "drop_all_duplicates")
    process_csv(config, str(csv_path), strict=False)

    out = pd.read_csv(tmp_path / "processed" / "dwc_tst.csv", sep="\t")
    assert len(out) == 1
    assert set(out["catalogNumber"]) == {"A2"}


def test_integration_strict_mode_fails_and_writes_failed_reports(tmp_path):
    csv_path = tmp_path / "verbatim" / "TST.csv"
    _write_csv(
        csv_path,
        ["instcode", "accessionno", "taxaname"],
        [["TST", "A1", "N1"], ["TST", "A1", "N1-dup"]],
    )
    config = _base_config(tmp_path, "keep_first")

    with pytest.raises(ValueError, match="STRICT MODE FAILURE"):
        process_csv(config, str(csv_path), strict=True)

    report = json.loads((tmp_path / "processed" / "quality_report_tst.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert "STRICT MODE FAILURE" in report["error"]

    rec = json.loads((tmp_path / "processed" / "reconciliation_tst.json").read_text(encoding="utf-8"))
    assert rec["status"] == "failed"
    assert "STRICT MODE FAILURE" in rec["error"]
