import logging
import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app import models  # noqa: E402,F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nutriscan.products")


def main():
    app = create_app()
    try:
        with app.app_context():
            db.create_all()
            inspector = inspect(db.engine)
            if "products" not in inspector.get_table_names():
                raise RuntimeError("SQLAlchemy did not create the products table.")
            column_info = {
                column["name"]: column
                for column in inspector.get_columns("products")
            }
            for name, definition in (
                ("category", "VARCHAR(50) NULL"),
                ("dietary_tags", "JSON NULL"),
                ("barcode", "VARCHAR(14) NULL"),
                ("ingredients", "TEXT NULL"),
                ("packaging_text", "TEXT NULL"),
                ("image_url", "VARCHAR(500) NULL"),
            ):
                if name not in column_info:
                    db.session.execute(
                        text(f"ALTER TABLE products ADD COLUMN {name} {definition}")
                    )
                    logger.info("Added products.%s.", name)

            nullable_nutrients = {
                "energy_kj": "NUMERIC(8, 2)",
                "calories_kcal": "NUMERIC(7, 2)",
                "carbohydrates_g": "NUMERIC(7, 2)",
                "sugars_g": "NUMERIC(7, 2)",
                "protein_g": "NUMERIC(7, 2)",
                "total_fat_g": "NUMERIC(7, 2)",
                "saturated_fat_g": "NUMERIC(7, 2)",
                "fibre_g": "NUMERIC(7, 2)",
                "sodium_mg": "NUMERIC(9, 2)",
            }
            for name, sql_type in nullable_nutrients.items():
                if name in column_info and not column_info[name]["nullable"]:
                    db.session.execute(
                        text(
                            f"ALTER TABLE products MODIFY COLUMN {name} {sql_type} NULL"
                        )
                    )
                    logger.info("Made products.%s nullable for unavailable values.", name)
            db.session.commit()

            inspector = inspect(db.engine)
            columns = {
                column["name"] for column in inspector.get_columns("products")
            }
            required = {
                "created_by",
                "name",
                "category",
                "dietary_tags",
                "energy_kj",
                "calories_kcal",
                "carbohydrates_g",
                "sugars_g",
                "protein_g",
                "total_fat_g",
                "saturated_fat_g",
                "fibre_g",
                "sodium_mg",
                "source_type",
                "source_label",
                "barcode",
                "ingredients",
                "packaging_text",
                "image_url",
            }
            missing = required - columns
            if missing:
                raise RuntimeError(
                    f"products table is missing columns: {', '.join(sorted(missing))}"
                )
            foreign_keys = inspector.get_foreign_keys("products")
            if not any(
                key["referred_table"] == "users"
                for key in foreign_keys
            ):
                raise RuntimeError("products.created_by foreign key is missing.")
            if not any(
                index["name"] == "ix_products_category"
                for index in inspector.get_indexes("products")
            ):
                db.session.execute(
                    text("CREATE INDEX ix_products_category ON products (category)")
                )
            if not any(
                index["name"] == "ix_products_barcode"
                for index in inspector.get_indexes("products")
            ):
                db.session.execute(
                    text("CREATE INDEX ix_products_barcode ON products (barcode)")
                )
            if not any(
                index["name"] == "uq_products_user_barcode"
                for index in inspector.get_indexes("products")
            ):
                duplicate_barcode = db.session.execute(
                    text(
                        "SELECT created_by, barcode FROM products "
                        "WHERE barcode IS NOT NULL "
                        "GROUP BY created_by, barcode HAVING COUNT(*) > 1 LIMIT 1"
                    )
                ).first()
                if duplicate_barcode is None:
                    db.session.execute(
                        text(
                            "CREATE UNIQUE INDEX uq_products_user_barcode "
                            "ON products (created_by, barcode)"
                        )
                    )
                else:
                    logger.warning(
                        "Existing duplicate product barcodes prevent the unique index; "
                        "barcode imports still check for existing entries."
                    )

            existing_tables = set(inspect(db.engine).get_table_names())
            expected_activity_tables = {
                "product_analysis_history",
                "product_watchlist",
                "product_ingredient_analyses",
                "product_food_claim_analyses",
            }
            if not expected_activity_tables.issubset(existing_tables):
                db.create_all()
            inspector = inspect(db.engine)
            for table, expected_fk in (
                ("product_analysis_history", "products"),
                ("product_watchlist", "products"),
                ("product_ingredient_analyses", "products"),
                ("product_food_claim_analyses", "products"),
            ):
                if table not in inspector.get_table_names():
                    raise RuntimeError(f"Could not initialize {table}.")
                foreign_keys = inspector.get_foreign_keys(table)
                if not any(key["referred_table"] == expected_fk for key in foreign_keys):
                    raise RuntimeError(f"{table} product foreign key is missing.")
                if table == "product_ingredient_analyses" and not any(
                    key["referred_table"] == "users" for key in foreign_keys
                ):
                    raise RuntimeError(
                        "product_ingredient_analyses user foreign key is missing."
                    )
                if table == "product_food_claim_analyses" and not any(
                    key["referred_table"] == "users" for key in foreign_keys
                ):
                    raise RuntimeError(
                        "product_food_claim_analyses user foreign key is missing."
                    )

            ingredient_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "product_ingredient_analyses"
                )
            }
            if "product_identity_snapshot" not in ingredient_columns:
                db.session.execute(
                    text(
                        "ALTER TABLE product_ingredient_analyses "
                        "ADD COLUMN product_identity_snapshot INTEGER NULL"
                    )
                )
                logger.info(
                    "Added product identity snapshots to ingredient analyses."
                )
            db.session.execute(
                text(
                    "UPDATE product_ingredient_analyses "
                    "SET product_identity_snapshot = product_id "
                    "WHERE product_identity_snapshot IS NULL AND product_id IS NOT NULL"
                )
            )
            ingredient_indexes = {
                index["name"]
                for index in inspect(db.engine).get_indexes(
                    "product_ingredient_analyses"
                )
            }
            identity_index = (
                "ix_product_ingredient_analyses_product_identity_snapshot"
            )
            if identity_index not in ingredient_indexes:
                db.session.execute(
                    text(
                        "CREATE INDEX "
                        f"{identity_index} ON product_ingredient_analyses "
                        "(product_identity_snapshot)"
                    )
                )
            db.session.commit()

            watchlist_constraints = inspector.get_unique_constraints(
                "product_watchlist"
            )
            has_unique_watchlist = any(
                constraint["name"] == "uq_watchlist_user_product"
                for constraint in watchlist_constraints
            )
            if not has_unique_watchlist:
                db.session.execute(
                    text(
                        "ALTER TABLE product_watchlist "
                        "ADD CONSTRAINT uq_watchlist_user_product "
                        "UNIQUE (user_id, product_id)"
                    )
                )
            db.session.execute(text("SELECT 1"))
            logger.info(
                "Product, activity, and ingredient comparison tables are ready in MySQL."
            )
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Could not initialize product nutrition storage in MySQL.")
        return 1
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
