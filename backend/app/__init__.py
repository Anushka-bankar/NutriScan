import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    app = Flask(__name__)
    app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "")
    app.config["JWT_ACCESS_TOKEN_MINUTES"] = int(
        os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")
    )
    try:
        mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as exc:
        raise ValueError("MYSQL_PORT must be a valid integer.") from exc
    if not 1 <= mysql_port <= 65535:
        raise ValueError("MYSQL_PORT must be between 1 and 65535.")

    app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=mysql_port,
        database=os.getenv("MYSQL_DATABASE", "nutriscan"),
        query={"charset": "utf8mb4"},
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 5},
    }
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    from app import models  # noqa: F401
    from app.auth import auth_bp
    from app.catalog import catalog_bp
    from app.catalog_comparison import catalog_comparison_bp
    from app.health_profile import health_profile_bp
    from app.food_claims import food_claims_bp
    from app.ingredient_analysis import ingredient_analysis_bp
    from app.product_activity import activity_bp
    from app.products import products_bp
    from app.recommendations import recommendations_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(catalog_bp, url_prefix="/api/catalog")
    app.register_blueprint(catalog_comparison_bp, url_prefix="/api/catalog")
    app.register_blueprint(health_profile_bp, url_prefix="/api/profile")
    app.register_blueprint(ingredient_analysis_bp, url_prefix="/api/products")
    app.register_blueprint(food_claims_bp, url_prefix="/api/products")
    app.register_blueprint(activity_bp, url_prefix="/api")
    app.register_blueprint(products_bp, url_prefix="/api/products")
    app.register_blueprint(recommendations_bp, url_prefix="/api/products")

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": os.getenv(
                    "FRONTEND_ORIGIN", "http://localhost:5173"
                )
            }
        },
    )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "nutriscan-api"})

    @app.get("/api/health/database")
    def database_health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "connected"})
        except SQLAlchemyError:
            app.logger.exception("Database health check failed.")
            db.session.rollback()
            return jsonify({"status": "error", "database": "unavailable"}), 503

    return app
