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
logger = logging.getLogger("nutriscan.migration")

NEW_COLUMNS = {
    "age": "INTEGER NULL",
    "gender": "VARCHAR(50) NULL",
    "dietary_preferences": "JSON NULL",
}


def main():
    app = create_app()
    try:
        with app.app_context():
            db.create_all()
            inspector = inspect(db.engine)
            existing_columns = {
                column["name"]
                for column in inspector.get_columns("health_profiles")
            }
            for column, definition in NEW_COLUMNS.items():
                if column not in existing_columns:
                    db.session.execute(
                        text(
                            f"ALTER TABLE health_profiles ADD COLUMN {column} {definition}"
                        )
                    )
                    logger.info("Added health_profiles.%s.", column)
            db.session.commit()
            logger.info("Health profile schema is up to date.")
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Could not migrate health_profiles in MySQL.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
