import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, insert, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.models import PackagedFoodCatalog

SOURCE_NAME = "packaged_foods_india"
EXPECTED_CSV_SHA256 = "f64832743d4918c428aab31fb8a3681cd2dee89f3c5f305185ec0edfabe8f303"
EXPECTED_RECORD_COUNT = 852
EXPECTED_HEADERS = (
    "S.No",
    "Item name",
    "Brand_Name",
    "Category",
    "Sub_Category",
    "Ingredients",
    "Serving_Size_g",
    "Calories_kcal",
    "Carbohydrates_g",
    "Proteins_g",
    "Total_Fat_g",
    "Saturated_Fat_g",
    "Trans_Fat_g",
    "Sugar_g",
    "Sodium_mg",
    "Dietary_Fiber_g",
    "Cholesterol_mg",
    "Calcium_mg",
    "Vitamin",
    "Iron_mg",
    "Price_INR",
    "Source_of_Data",
    "Collection_Date",
    "Collected_By",
    "Remarks",
)

NUMERIC_FIELDS = {
    "Serving_Size_g": ("serving_size_g", 2),
    "Calories_kcal": ("calories_kcal_per_serving", 6),
    "Carbohydrates_g": ("carbohydrates_g_per_serving", 6),
    "Proteins_g": ("protein_g_per_serving", 6),
    "Total_Fat_g": ("total_fat_g_per_serving", 6),
    "Saturated_Fat_g": ("saturated_fat_g_per_serving", 6),
    "Trans_Fat_g": ("trans_fat_g_per_serving", 6),
    "Sugar_g": ("sugar_g_per_serving", 6),
    "Sodium_mg": ("sodium_mg_per_serving", 6),
    "Dietary_Fiber_g": ("dietary_fiber_g_per_serving", 6),
    "Cholesterol_mg": ("cholesterol_mg_per_serving", 6),
    "Calcium_mg": ("calcium_mg_per_serving", 6),
    "Iron_mg": ("iron_mg_per_serving", 6),
    "Price_INR": ("price_inr", 2),
}
EXACT_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
UPPER_BOUND = re.compile(r"^<\s*(\d+(?:\.\d+)?)$")
POSITIVE_INTEGER = re.compile(r"^[1-9]\d*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GRAM_NUTRIENT_HEADERS = (
    "Carbohydrates_g",
    "Proteins_g",
    "Total_Fat_g",
    "Saturated_Fat_g",
    "Trans_Fat_g",
    "Sugar_g",
    "Dietary_Fiber_g",
)


class DatasetValidationError(ValueError):
    def __init__(self, message, total_csv_records=0, invalid_records=0):
        super().__init__(message)
        self.total_csv_records = total_csv_records
        self.invalid_records = invalid_records


class CatalogRecordError(ValueError):
    pass


class ImportReport:
    def __init__(self, total_csv_records=0):
        self.total_csv_records = total_csv_records
        self.successfully_inserted_records = 0
        self.identical_records_skipped = 0
        self.changed_record_conflicts = 0
        self.invalid_records = 0
        self.failed_records = 0
        self.final_catalog_record_count = 0
        self.conflict_source_row_ids = []
        self.errors = []

    def as_dict(self):
        return {
            "total_csv_records": self.total_csv_records,
            "successfully_inserted_records": self.successfully_inserted_records,
            "identical_records_skipped": self.identical_records_skipped,
            "changed_record_conflicts": self.changed_record_conflicts,
            "invalid_records": self.invalid_records,
            "failed_records": self.failed_records,
            "final_catalog_record_count": self.final_catalog_record_count,
            "conflict_source_row_ids": self.conflict_source_row_ids,
            "errors": self.errors,
        }


def read_source_bytes(path):
    source_path = Path(path)
    if source_path.suffix.lower() != ".zip":
        return source_path.read_bytes()

    with zipfile.ZipFile(source_path) as archive:
        candidates = [
            item.filename
            for item in archive.infolist()
            if not item.is_dir()
            and Path(item.filename).name == "packaged_foods_india.csv"
        ]
        if len(candidates) != 1:
            raise DatasetValidationError(
                "ZIP must contain exactly one packaged_foods_india.csv file."
            )
        return archive.read(candidates[0])


def validate_csv_bytes(
    content,
    expected_sha256=EXPECTED_CSV_SHA256,
    expected_record_count=EXPECTED_RECORD_COUNT,
):
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise DatasetValidationError(
            "CSV SHA-256 does not match the audited dataset; no rows were imported."
        )

    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded, newline=""))
        headers = tuple(reader.fieldnames or ())
        if headers != EXPECTED_HEADERS:
            raise DatasetValidationError(
                "CSV headers do not exactly match the audited 25-column header."
            )

        rows = []
        invalid_records = 0
        total_csv_records = 0
        invalid_serial_rows = 0
        for row in reader:
            total_csv_records += 1
            if None in row or any(row.get(header) is None for header in EXPECTED_HEADERS):
                invalid_records += 1
                continue
            normalized_row = {header: row[header] for header in EXPECTED_HEADERS}
            if normalized_row["S.No"].strip() != str(total_csv_records):
                invalid_serial_rows += 1
            rows.append(normalized_row)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DatasetValidationError(f"CSV could not be decoded or parsed: {exc}") from exc

    if expected_record_count is not None and total_csv_records != expected_record_count:
        raise DatasetValidationError(
            f"Expected {expected_record_count} CSV records; found {total_csv_records}.",
            total_csv_records=total_csv_records,
            invalid_records=invalid_records,
        )

    if invalid_records or invalid_serial_rows:
        raise DatasetValidationError(
            "CSV rows must have the complete 1-based S.No sequence and exactly 25 cells per row.",
            total_csv_records=total_csv_records,
            invalid_records=invalid_records + invalid_serial_rows,
        )

    return rows, actual_sha256


def _decimal_status(raw_value, max_scale):
    value = (raw_value or "").strip()
    if not value:
        return None, {"status": "blank"}

    upper_match = UPPER_BOUND.fullmatch(value)
    if upper_match:
        return None, {
            "status": "upper_bound",
            "operator": "<",
            "bound": upper_match.group(1),
        }
    if "," in value:
        return None, {"status": "ambiguous_comma", "raw": value}
    if not EXACT_NUMBER.fullmatch(value):
        return None, {"status": "invalid", "raw": value}

    try:
        number = Decimal(value)
    except InvalidOperation:
        return None, {"status": "invalid", "raw": value}
    if not number.is_finite() or number < 0:
        return None, {"status": "invalid", "raw": value}

    scale = max(0, -number.as_tuple().exponent)
    if scale > max_scale:
        quantizer = Decimal(1).scaleb(-max_scale)
        if number.quantize(quantizer) != number:
            return None, {
                "status": "precision_exceeds_storage",
                "raw": value,
            }
    return number, {"status": "exact"}


def _row_hash(raw_row):
    canonical = json.dumps(
        raw_row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _parse_collection_date(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return None, {"status": "blank"}
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None, {"status": "invalid", "raw": value}
    return parsed, {"status": "exact"}


def _quality_warnings(values, numeric_statuses):
    warnings = []
    serving = values.get("serving_size_g")
    exact_by_header = {
        header: values.get(column)
        for header, (column, _) in NUMERIC_FIELDS.items()
    }

    if serving is None or serving <= 0:
        warnings.append("serving_size_unavailable_for_per_100g_conversion")
    else:
        for header in GRAM_NUTRIENT_HEADERS:
            amount = exact_by_header.get(header)
            if amount is not None and amount > serving:
                warnings.append(f"{header}:exceeds_serving_mass")

        comparisons = (
            ("Sugar_g", "Carbohydrates_g", "sugar_exceeds_carbohydrates"),
            ("Saturated_Fat_g", "Total_Fat_g", "saturated_fat_exceeds_total_fat"),
            ("Trans_Fat_g", "Total_Fat_g", "trans_fat_exceeds_total_fat"),
        )
        for left, right, warning in comparisons:
            left_value = exact_by_header.get(left)
            right_value = exact_by_header.get(right)
            if (
                left_value is not None
                and right_value is not None
                and left_value > right_value
            ):
                warnings.append(warning)

        calories = exact_by_header.get("Calories_kcal")
        if calories is not None and calories * Decimal("100") / serving > Decimal("900"):
            warnings.append("calories_per_100g_over_900")

    for header, status in numeric_statuses.items():
        if status["status"] in {
            "upper_bound",
            "ambiguous_comma",
            "invalid",
            "precision_exceeds_storage",
        }:
            warnings.append(f"{header}:{status['status']}")
    return warnings


def prepare_catalog_record(raw_row, source_file_sha256):
    if not isinstance(raw_row, dict) or set(raw_row) != set(EXPECTED_HEADERS):
        raise CatalogRecordError("Record must contain exactly the audited CSV columns.")

    source_row_text = raw_row["S.No"].strip()
    if not POSITIVE_INTEGER.fullmatch(source_row_text):
        raise CatalogRecordError("S.No must be a positive integer.")
    product_name = raw_row["Item name"].strip()
    if not product_name or len(product_name) > 255:
        raise CatalogRecordError("Item name is required and must be at most 255 characters.")

    values = {}
    numeric_statuses = {}
    for header, (column_name, max_scale) in NUMERIC_FIELDS.items():
        parsed, status = _decimal_status(raw_row[header], max_scale)
        numeric_statuses[header] = status
        values[column_name] = parsed
    if values["serving_size_g"] is not None and values["serving_size_g"] <= 0:
        numeric_statuses["Serving_Size_g"] = {
            "status": "invalid",
            "raw": raw_row["Serving_Size_g"],
        }
        values["serving_size_g"] = None

    collection_date, collection_date_status = _parse_collection_date(
        raw_row["Collection_Date"]
    )
    quality_flags = {
        "numeric_fields": numeric_statuses,
        "collection_date": collection_date_status,
    }
    quality_flags["warnings"] = _quality_warnings(values, numeric_statuses)
    if collection_date_status["status"] == "invalid":
        quality_flags["warnings"].append("Collection_Date:invalid")

    return {
        "source_name": SOURCE_NAME,
        "source_row_id": int(source_row_text),
        "source_file_sha256": source_file_sha256,
        "source_row_sha256": _row_hash(raw_row),
        "product_name": product_name,
        "brand_name": raw_row["Brand_Name"].strip() or None,
        "category": raw_row["Category"].strip() or None,
        "sub_category": raw_row["Sub_Category"].strip() or None,
        "ingredients": raw_row["Ingredients"].strip() or None,
        "vitamin_details": raw_row["Vitamin"].strip() or None,
        "source_of_data": raw_row["Source_of_Data"].strip() or None,
        "collection_date": collection_date,
        "collected_by": raw_row["Collected_By"].strip() or None,
        "remarks": raw_row["Remarks"].strip() or None,
        "nutrition_basis": "per_serving_inferred",
        "source_row_raw": dict(raw_row),
        "quality_flags": quality_flags,
        **values,
    }


def create_catalog_table(engine):
    table = PackagedFoodCatalog.__table__
    inspector = inspect(engine)
    if table.name not in inspector.get_table_names():
        table.create(bind=engine, checkfirst=True)
        return

    actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
    expected_columns = {column.name for column in table.columns}
    if actual_columns != expected_columns:
        raise RuntimeError(
            "packaged_food_catalog exists with an unexpected schema; refusing to alter it."
        )

    unique_constraints = inspector.get_unique_constraints(table.name)
    unique_indexes = inspector.get_indexes(table.name)
    source_key_exists = any(
        constraint.get("name") == "uq_packaged_food_catalog_source_row"
        and constraint.get("column_names") == ["source_name", "source_row_id"]
        for constraint in unique_constraints
    ) or any(
        index.get("name") == "uq_packaged_food_catalog_source_row"
        and index.get("unique")
        and index.get("column_names") == ["source_name", "source_row_id"]
        for index in unique_indexes
    )
    if not source_key_exists:
        raise RuntimeError(
            "packaged_food_catalog is missing its source unique key; refusing to import."
        )


def import_catalog_records(session, raw_rows, source_file_sha256, batch_size=100):
    report = ImportReport(total_csv_records=len(raw_rows))
    if not SHA256.fullmatch(source_file_sha256):
        report.invalid_records = len(raw_rows)
        report.errors.append("Source file hash must be a lowercase SHA-256 hex digest.")
        return report
    if batch_size < 1:
        report.invalid_records = len(raw_rows)
        report.errors.append("Batch size must be a positive integer.")
        return report

    prepared = []
    seen = {}
    for raw_row in raw_rows:
        try:
            record = prepare_catalog_record(raw_row, source_file_sha256)
        except CatalogRecordError as exc:
            report.invalid_records += 1
            report.errors.append(str(exc))
            continue

        source_row_id = record["source_row_id"]
        previous = seen.get(source_row_id)
        if previous is not None:
            if previous == record["source_row_sha256"]:
                report.identical_records_skipped += 1
            else:
                report.changed_record_conflicts += 1
                report.conflict_source_row_ids.append(source_row_id)
            continue
        seen[source_row_id] = record["source_row_sha256"]
        prepared.append(record)

    try:
        with session.begin():
            ids = [record["source_row_id"] for record in prepared]
            existing = {}
            for start in range(0, len(ids), 500):
                chunk = ids[start : start + 500]
                if not chunk:
                    continue
                stored = session.execute(
                    select(
                        PackagedFoodCatalog.source_row_id,
                        PackagedFoodCatalog.source_row_sha256,
                    ).where(
                        PackagedFoodCatalog.source_name == SOURCE_NAME,
                        PackagedFoodCatalog.source_row_id.in_(chunk),
                    )
                ).all()
                existing.update(
                    {row.source_row_id: row.source_row_sha256 for row in stored}
                )

            to_insert = []
            for record in prepared:
                stored_hash = existing.get(record["source_row_id"])
                if stored_hash is None:
                    to_insert.append(record)
                elif stored_hash == record["source_row_sha256"]:
                    report.identical_records_skipped += 1
                else:
                    report.changed_record_conflicts += 1
                    report.conflict_source_row_ids.append(record["source_row_id"])

            for start in range(0, len(to_insert), batch_size):
                session.execute(insert(PackagedFoodCatalog), to_insert[start : start + batch_size])
            report.successfully_inserted_records = len(to_insert)
    except SQLAlchemyError as exc:
        report.failed_records = len(to_insert) if "to_insert" in locals() else len(prepared)
        report.successfully_inserted_records = 0
        report.errors.append(f"Database transaction rolled back: {exc.__class__.__name__}.")
        session.rollback()

    try:
        report.final_catalog_record_count = session.execute(
            select(func.count()).select_from(PackagedFoodCatalog)
        ).scalar_one()
        session.rollback()
    except SQLAlchemyError:
        session.rollback()
        report.errors.append("Could not read the final catalog record count.")
    return report
