import csv
import hashlib
import io
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.catalog_import import (  # noqa: E402
    EXPECTED_HEADERS,
    SOURCE_NAME,
    DatasetValidationError,
    create_catalog_table,
    import_catalog_records,
    prepare_catalog_record,
    validate_csv_bytes,
)
from app.models import PackagedFoodCatalog  # noqa: E402


def sample_row(source_row_id="1"):
    values = {
        "S.No": source_row_id,
        "Item name": f"Sample food {source_row_id}",
        "Brand_Name": "Example",
        "Category": "SNACKS",
        "Sub_Category": "CHIPS",
        "Ingredients": "Potato, oil, salt",
        "Serving_Size_g": "25",
        "Calories_kcal": "120",
        "Carbohydrates_g": "15",
        "Proteins_g": "2",
        "Total_Fat_g": "6",
        "Saturated_Fat_g": "1",
        "Trans_Fat_g": "0",
        "Sugar_g": "1",
        "Sodium_mg": "180",
        "Dietary_Fiber_g": "2",
        "Cholesterol_mg": "0",
        "Calcium_mg": "0",
        "Vitamin": "0",
        "Iron_mg": "0",
        "Price_INR": "20",
        "Source_of_Data": "",
        "Collection_Date": "",
        "Collected_By": "",
        "Remarks": "",
    }
    return values


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPECTED_HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


class CatalogImporterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.session = Session(self.engine)
        create_catalog_table(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_numeric_values_keep_missing_bounds_and_invalid_text_distinct(self):
        row = sample_row()
        row.update(
            {
                "Proteins_g": "<1",
                "Total_Fat_g": "7,65",
                "Sodium_mg": "9,4",
                "Cholesterol_mg": "4L8",
                "Vitamin": "0",
            }
        )
        prepared = prepare_catalog_record(row, "a" * 64)

        self.assertIsNone(prepared["protein_g_per_serving"])
        self.assertEqual(
            prepared["quality_flags"]["numeric_fields"]["Proteins_g"],
            {"status": "upper_bound", "operator": "<", "bound": "1"},
        )
        self.assertIsNone(prepared["total_fat_g_per_serving"])
        self.assertEqual(
            prepared["quality_flags"]["numeric_fields"]["Total_Fat_g"]["status"],
            "ambiguous_comma",
        )
        self.assertEqual(
            prepared["quality_flags"]["numeric_fields"]["Sodium_mg"]["status"],
            "ambiguous_comma",
        )
        self.assertEqual(
            prepared["quality_flags"]["numeric_fields"]["Cholesterol_mg"]["status"],
            "invalid",
        )
        self.assertEqual(prepared["source_row_raw"]["Proteins_g"], "<1")
        self.assertEqual(prepared["vitamin_details"], "0")

    def test_first_import_then_identical_import_is_idempotent(self):
        rows = [sample_row("1"), sample_row("2")]
        source_hash = "b" * 64

        first = import_catalog_records(self.session, rows, source_hash, batch_size=1)
        self.assertEqual(first.successfully_inserted_records, 2)
        self.assertEqual(first.identical_records_skipped, 0)
        self.assertEqual(first.final_catalog_record_count, 2)

        repeated = import_catalog_records(self.session, rows, source_hash)
        self.assertEqual(repeated.successfully_inserted_records, 0)
        self.assertEqual(repeated.identical_records_skipped, 2)
        self.assertEqual(repeated.final_catalog_record_count, 2)

    def test_changed_source_row_is_reported_without_overwriting(self):
        original = sample_row("1")
        inserted = import_catalog_records(self.session, [original], "c" * 64)
        self.assertEqual(inserted.successfully_inserted_records, 1)

        changed = dict(original, **{"Item name": "Changed source value"})
        conflict = import_catalog_records(self.session, [changed], "d" * 64)

        self.assertEqual(conflict.changed_record_conflicts, 1)
        self.assertEqual(conflict.conflict_source_row_ids, [1])
        self.assertEqual(conflict.successfully_inserted_records, 0)
        stored = self.session.get(PackagedFoodCatalog, 1)
        self.assertEqual(stored.product_name, "Sample food 1")
        self.assertEqual(conflict.final_catalog_record_count, 1)

    def test_invalid_record_is_reported_and_valid_record_is_preserved(self):
        invalid = sample_row("not-a-number")
        report = import_catalog_records(
            self.session,
            [sample_row("1"), invalid],
            "e" * 64,
        )

        self.assertEqual(report.invalid_records, 1)
        self.assertEqual(report.successfully_inserted_records, 1)
        self.assertEqual(report.final_catalog_record_count, 1)

    def test_database_failure_rolls_back_the_whole_import_transaction(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER reject_second_catalog_row "
                    "BEFORE INSERT ON packaged_food_catalog "
                    "WHEN NEW.source_row_id = 2 "
                    "BEGIN SELECT RAISE(ABORT, 'test rollback'); END"
                )
            )

        report = import_catalog_records(
            self.session,
            [sample_row("1"), sample_row("2")],
            "f" * 64,
            batch_size=1,
        )

        self.assertEqual(report.successfully_inserted_records, 0)
        self.assertEqual(report.failed_records, 2)
        self.assertEqual(report.final_catalog_record_count, 0)
        self.assertTrue(any("rolled back" in message for message in report.errors))

    def test_catalog_creation_and_import_do_not_change_products_table(self):
        with self.engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE products (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
            )
            connection.execute(
                text("INSERT INTO products (id, label) VALUES (7, 'keep me')")
            )
            before_columns = [
                row[1] for row in connection.execute(text("PRAGMA table_info(products)"))
            ]
            before_rows = connection.execute(
                text("SELECT id, label FROM products ORDER BY id")
            ).all()

        report = import_catalog_records(self.session, [sample_row()], "1" * 64)

        with self.engine.connect() as connection:
            after_columns = [
                row[1] for row in connection.execute(text("PRAGMA table_info(products)"))
            ]
            after_rows = connection.execute(
                text("SELECT id, label FROM products ORDER BY id")
            ).all()
            catalog_tables = connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name LIKE '%catalog%'"
                )
            ).scalars().all()

        self.assertEqual(before_columns, after_columns)
        self.assertEqual(before_rows, after_rows)
        self.assertEqual(catalog_tables, ["packaged_food_catalog"])
        self.assertEqual(report.successfully_inserted_records, 1)
        self.assertEqual(SOURCE_NAME, "packaged_foods_india")

    def test_csv_preflight_checks_hash_headers_count_and_serials(self):
        rows = [sample_row("1"), sample_row("2")]
        content = csv_bytes(rows)
        digest = hashlib.sha256(content).hexdigest()

        parsed, actual_hash = validate_csv_bytes(
            content,
            expected_sha256=digest,
            expected_record_count=2,
        )
        self.assertEqual(len(parsed), 2)
        self.assertEqual(actual_hash, digest)

        with self.assertRaises(DatasetValidationError):
            validate_csv_bytes(
                content,
                expected_sha256="0" * 64,
                expected_record_count=2,
            )
        with self.assertRaises(DatasetValidationError):
            validate_csv_bytes(
                csv_bytes([sample_row("2")]),
                expected_sha256=None,
                expected_record_count=1,
            )


if __name__ == "__main__":
    unittest.main()
