import argparse
import json
import logging
import sys
import zipfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.catalog_import import (  # noqa: E402
    DatasetValidationError,
    create_catalog_table,
    import_catalog_records,
    read_source_bytes,
    validate_csv_bytes,
)
from app.extensions import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nutriscan.catalog_import")


def _print_report(report):
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Safely import the audited Indian packaged-food CSV into the separate "
            "packaged_food_catalog table."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to packaged_foods_india.csv or a ZIP containing that CSV.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of catalog rows sent per insert batch (default: 100).",
    )
    args = parser.parse_args(argv)

    try:
        content = read_source_bytes(args.source)
        rows, source_file_sha256 = validate_csv_bytes(content)
    except (OSError, zipfile.BadZipFile, DatasetValidationError) as exc:
        details = {
            "total_csv_records": getattr(exc, "total_csv_records", 0),
            "successfully_inserted_records": 0,
            "identical_records_skipped": 0,
            "changed_record_conflicts": 0,
            "invalid_records": getattr(exc, "invalid_records", 0),
            "failed_records": 0,
            "final_catalog_record_count": None,
            "conflict_source_row_ids": [],
            "errors": [str(exc)],
        }
        _print_report(details)
        return 1

    if args.batch_size < 1:
        _print_report(
            {
                "total_csv_records": len(rows),
                "successfully_inserted_records": 0,
                "identical_records_skipped": 0,
                "changed_record_conflicts": 0,
                "invalid_records": 0,
                "failed_records": len(rows),
                "final_catalog_record_count": None,
                "conflict_source_row_ids": [],
                "errors": ["Batch size must be a positive integer."],
            }
        )
        return 1

    app = create_app()
    try:
        with app.app_context():
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            create_catalog_table(db.engine)
            report = import_catalog_records(
                db.session,
                rows,
                source_file_sha256,
                batch_size=args.batch_size,
            )
            result = report.as_dict()
            _print_report(result)
            if (
                report.failed_records
                or report.invalid_records
                or report.changed_record_conflicts
            ):
                return 1
            return 0
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.exception("Could not initialize or import the packaged-food catalog.")
        _print_report(
            {
                "total_csv_records": len(rows),
                "successfully_inserted_records": 0,
                "identical_records_skipped": 0,
                "changed_record_conflicts": 0,
                "invalid_records": 0,
                "failed_records": len(rows),
                "final_catalog_record_count": None,
                "conflict_source_row_ids": [],
                "errors": [f"Database operation failed: {exc.__class__.__name__}."],
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
