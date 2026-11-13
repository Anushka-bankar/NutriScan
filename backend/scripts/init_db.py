import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app import models  # noqa: E402,F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nutriscan.database")


def main():
    parser = argparse.ArgumentParser(
        description="Check the NutriScan MySQL connection and initialize tables."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the database connection without creating tables.",
    )
    args = parser.parse_args()
    app = create_app()

    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
            logger.info("Successfully connected to the configured MySQL database.")
            if not args.check_only:
                db.create_all()
                logger.info("NutriScan tables are initialized.")
    except SQLAlchemyError:
        logger.exception(
            "Could not connect to or initialize MySQL. Check that the MySQL server "
            "is running, the database exists, and backend/.env has valid settings."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
